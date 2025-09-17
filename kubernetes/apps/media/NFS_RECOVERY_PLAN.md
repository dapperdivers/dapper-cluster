# NFS Mount Recovery Implementation

## Overview
This document outlines the changes made to improve NFS mount resilience for Unraid servers (tower.manor and tower-2.manor) that have been experiencing stale file handle issues.

## Changes Implemented

### 1. PV Mount Options Updates
**File:** `kubernetes/apps/media/media-nfs-storage/app/pvc.yaml`

Changed mount options from `hard` to `soft` with optimized timeouts:
- **soft**: Fail operations instead of hanging indefinitely
- **vers=4.1**: Downgraded from 4.2 for better Unraid compatibility
- **timeo=100**: Reduced from 600 (10 seconds vs 60 seconds)
- **retrans=3**: Increased retry count
- **actimeo=60**: Reduced cache time from 3600
- **lookupcache=positive**: Only cache successful lookups
- **noresvport**: Use non-reserved ports for reconnects
- **bg**: Background mount retries

### 2. Liveness Probes Added
Updated the following applications to check NFS mount health:
- `sabnzbd/app/helmrelease.yaml` - Checks all three mounts
- `plex/app/helmrelease.yaml` - Checks tower and tower-2
- `radarr/app/helmrelease.yaml` - Checks tower-2
- `sonarr/app/helmrelease.yaml` - Checks tower
- `bazarr/app/helmrelease.yaml` - Checks both tower mounts

Each probe:
- Runs every 60 seconds
- Times out after 15 seconds
- Restarts pod after 3 consecutive failures

### 3. NFS Monitor DaemonSet
**New Directory:** `kubernetes/apps/media/nfs-monitor/`

Created a DaemonSet that:
- Runs on every node
- Monitors all NFS mounts
- Logs stale mount detections
- Checks server connectivity
- Reports mount options

## Rollout Process

### Step 1: Review and Commit
```bash
git add kubernetes/apps/media/
git commit -m "fix: implement NFS mount recovery for Unraid servers

- Update PV mount options from hard to soft with optimized timeouts
- Add liveness probes to detect and recover from stale NFS handles
- Create NFS monitor DaemonSet for visibility
- Addresses long-standing stale file handle issues with tower.manor and tower-2.manor"
git push
```

### Step 2: Apply PV Changes
Since PVs are immutable, you need to delete and recreate them:

```bash
# First, note which pods are using these PVCs
kubectl get pods -n media -o wide | grep -E "tower|sabnzbd|plex|radarr|sonarr|bazarr"

# Delete the PVs (PVCs will remain, data is safe on NFS)
kubectl delete pv media-tower-pv media-tower-2-pv

# Apply the new PV definitions
kubectl apply -f kubernetes/apps/media/media-nfs-storage/app/pvc.yaml

# Verify PVs are bound
kubectl get pv | grep media-tower
```

### Step 3: Restart Affected Pods
The pods need to be restarted to pick up the new mount options:

```bash
# Restart deployments one by one to minimize disruption
kubectl rollout restart deployment/sabnzbd -n media
kubectl rollout restart deployment/plex -n media
kubectl rollout restart deployment/radarr -n media
kubectl rollout restart deployment/sonarr -n media
kubectl rollout restart deployment/bazarr -n media

# Monitor rollout status
kubectl rollout status deployment/sabnzbd -n media
```

### Step 4: Deploy NFS Monitor
```bash
# Apply the NFS monitor
kubectl apply -k kubernetes/apps/media/nfs-monitor/app/

# Check it's running on all nodes
kubectl get daemonset -n media nfs-monitor
kubectl logs -n media -l app.kubernetes.io/name=nfs-monitor --tail=50
```

### Step 5: Verify Recovery
```bash
# Test mount health in a pod
kubectl exec -n media deployment/sabnzbd -- df -h | grep tower

# Check for stale handles (should return without error)
kubectl exec -n media deployment/sabnzbd -- ls /tower/downloads/usenet
kubectl exec -n media deployment/sabnzbd -- ls /tower-2/downloads/usenet

# Monitor pod restarts
kubectl get pods -n media -w
```

## Monitoring

### Check NFS Monitor Logs
```bash
kubectl logs -n media -l app.kubernetes.io/name=nfs-monitor -f
```

### Check Pod Events for Liveness Failures
```bash
kubectl get events -n media --field-selector reason=Unhealthy
```

### Manual Health Check
```bash
for pod in $(kubectl get pods -n media -o name | grep -E "sabnzbd|plex|radarr|sonarr|bazarr"); do
  echo "Checking $pod..."
  kubectl exec -n media $pod -- df 2>&1 | grep -E "tower|Stale" || echo "OK"
done
```

## Rollback Process
If issues occur:

1. **Revert PV Changes:**
```bash
git revert HEAD
git push
kubectl delete pv media-tower-pv media-tower-2-pv
kubectl apply -f kubernetes/apps/media/media-nfs-storage/app/pvc.yaml
```

2. **Remove Monitor:**
```bash
kubectl delete -k kubernetes/apps/media/nfs-monitor/app/
```

3. **Flux will automatically revert the helmrelease changes**

## Expected Benefits
1. **Faster Recovery**: Soft mounts with short timeouts prevent indefinite hangs
2. **Automatic Recovery**: Liveness probes restart pods when mounts become stale
3. **Better Visibility**: NFS monitor provides real-time mount health status
4. **Reduced Downtime**: Issues are detected and resolved within 2-3 minutes

## Known Limitations
- Pods must restart to recover from stale handles (Kubernetes limitation)
- Some I/O operations may fail during mount issues (soft mount behavior)
- Brief service interruption during pod restarts

## Future Improvements
Consider:
1. Migrating to CSI-based NFS driver for better mount management
2. Implementing a service mesh with circuit breakers
3. Adding Prometheus metrics for NFS health monitoring
4. Creating alerts based on mount failures
