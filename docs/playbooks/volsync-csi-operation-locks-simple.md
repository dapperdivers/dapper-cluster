# Playbook: Fix VolSync CSI Operation Locks

## Problem
VolSync restore fails because CSI has operation locks preventing PVC provisioning from snapshots.

## Root Cause
ReplicationSources try to backup deleted PVCs → snapshot creation times out → CSI keeps locks → new operations fail.

## Solution Steps

### Step 1: Suspend All ReplicationSources

Stops new snapshot attempts while we clean up.

```bash
# Suspend ALL ReplicationSources
kubectl get replicationsource --all-namespaces -o json | \
  jq -r '.items[] | "\(.metadata.namespace) \(.metadata.name)"' | \
  while read ns name; do
    kubectl patch replicationsource -n $ns $name --type=merge -p '{"spec":{"suspend":true}}'
  done

# Verify all suspended
kubectl get replicationsource --all-namespaces | grep -v "true"
```

Expected: Only header line, no active sources.

### Step 2: Delete All Failed VolumeSnapshots

Removes snapshots that can't complete.

```bash
# Delete all VolumeSnapshots that are not ready
kubectl get volumesnapshot --all-namespaces -o json | \
  jq -r '.items[] | select(.status.readyToUse==false) | "\(.metadata.namespace) \(.metadata.name)"' | \
  while read ns name; do
    echo "Deleting $ns/$name"
    kubectl delete volumesnapshot -n $ns $name
  done

# Verify cleanup
kubectl get volumesnapshot --all-namespaces | grep false | wc -l
```

Expected: 0

### Step 3: Restart CSI Provisioner

Clears operation locks from memory.

```bash
# Restart provisioner (NOT the daemonset!)
kubectl rollout restart deployment -n rook-ceph csi-rbdplugin-provisioner

# Wait for completion
kubectl rollout status deployment -n rook-ceph csi-rbdplugin-provisioner --timeout=5m
```

### Step 4: Verify PVC Provisioning Works

Check that legitimate PVCs can now provision.

```bash
# Check Pending PVCs
kubectl get pvc --all-namespaces | grep Pending

# Watch for changes (should see PVCs move to Bound)
watch -n 5 'kubectl get pvc --all-namespaces | grep Pending'
```

Expected: PVCs for apps with valid restore sources should provision within 5 minutes.

### Step 5: Resume ReplicationSources

Only resume sources for apps that exist and are running.

```bash
# List apps that have running pods
kubectl get pods --all-namespaces | grep Running

# Resume ReplicationSource for each running app
# Example for specific apps:
kubectl patch replicationsource -n media prowlarr --type=merge -p '{"spec":{"suspend":false}}'
kubectl patch replicationsource -n media prowlarr-r2 --type=merge -p '{"spec":{"suspend":false}}'

# Or resume all (do this ONLY if most apps are recovered):
kubectl get replicationsource --all-namespaces -o json | \
  jq -r '.items[] | "\(.metadata.namespace) \(.metadata.name)"' | \
  while read ns name; do
    kubectl patch replicationsource -n $ns $name --type=merge -p '{"spec":{"suspend":false}}'
  done
```

## Verification

```bash
# 1. No operation lock errors
kubectl logs -n rook-ceph deploy/csi-rbdplugin-provisioner -c csi-rbdplugin --tail=50 | grep "already exists"

# 2. No failed snapshots
kubectl get volumesnapshot --all-namespaces | grep false

# 3. Apps running
kubectl get pods --all-namespaces | grep -E "media|ai|home-automation|selfhosted" | grep Running
```

## If It Fails Again

If PVCs go back to Pending with "already exists" errors:

1. Check CSI logs for which Volume IDs have locks
2. Check if ReplicationSources are creating snapshots of non-existent PVCs
3. Delete the specific ReplicationSource CRDs for deleted apps
4. Repeat from Step 2

## Prevention

After recovery, delete ReplicationSource CRDs for any apps you don't plan to restore:

```bash
# Example - delete backup configs for deleted apps
kubectl delete replicationsource -n ai archon archon-r2
kubectl delete replicationsource -n ai litellm litellm-r2
```
