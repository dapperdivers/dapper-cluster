# Playbook: VolSync CSI Operation Locks

## Problem Statement
VolSync restore operations stuck because CSI RBD provisioner has in-memory operation locks preventing `vs-prime-*` PVCs from provisioning from VolumeSnapshots.

**Symptoms:**
- Multiple `vs-prime-*` PVCs stuck in Pending state
- ReplicationDestinations show `Synchronizing: True` but restore pods can't schedule
- CSI logs show: `rpc error: code = Aborted desc = an operation with the given Volume ID pvc-XXX already exists`
- Main application PVCs waiting for VolSync populator (show `VolSyncPopulatorReplicationDestinationNoLatestImage`)
- First provision attempt shows `DeadlineExceeded` (timed out after 10 minutes)
- Subsequent attempts immediately fail with "already exists"

**Root Cause:**
VolumeSnapshot objects referencing deleted PVCs cause CSI snapshot operations to timeout, which then creates operation locks that block subsequent operations.

**The Cascade:**
1. **PVCs deleted** (during cleanup) but VolumeSnapshot objects remain
2. **CSI tries to create RBD snapshots** from non-existent volumes
3. **Operations timeout** (DeadlineExceeded after 10m) - can't snapshot deleted volumes
4. **CSI keeps operation lock** in memory despite timeout (CSI bug)
5. **Kubernetes retries** → CSI rejects: "operation already exists"
6. **Lock persists indefinitely**, blocking all snapshot operations
7. **VolSync restore fails** because it can't create snapshots from backup repos
8. **vs-prime PVCs stuck** waiting for snapshots that will never complete

**Critical Finding:** The CSI operation lock bug is a SYMPTOM. The ROOT CAUSE is orphaned VolumeSnapshot objects trying to snapshot deleted volumes. Restarting CSI clears locks but snapshots will timeout again unless orphaned VolumeSnapshots are cleaned up.

## Pre-Flight Checks

```bash
# 1. Verify CSI provisioner uptime (if > 24h, likely has stale locks)
kubectl get pod -n rook-ceph -l app=csi-rbdplugin-provisioner -o jsonpath='{.items[0].status.startTime}'

# 2. Count stuck vs-prime PVCs
kubectl get pvc --all-namespaces | grep "vs-prime" | grep Pending | wc -l

# 3. Check CSI logs for operation lock errors
kubectl logs -n rook-ceph deploy/csi-rbdplugin-provisioner -c csi-rbdplugin --tail=50 | grep "already exists"

# 4. Verify VolumeSnapshots exist and are ready
kubectl get volumesnapshot --all-namespaces | grep volsync

# 5. Check ReplicationDestinations have latestImage
kubectl get replicationdestination --all-namespaces -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}: {.status.latestImage.name}{"\n"}{end}' | grep -v ": $"
```

## Solution: Clean Up Orphaned VolumeSnapshots + Restart CSI

**Two-Step Fix Required:**
1. **Delete orphaned VolumeSnapshot objects** (snapshots of deleted PVCs)
2. **Restart CSI provisioner** to clear accumulated operation locks

### Why Both Steps Are Needed

**Step 1 - Delete Orphaned VolumeSnapshots:**
- Removes the SOURCE of timeout errors
- Prevents new operation locks from being created
- Without this, locks will accumulate again after CSI restart

**Step 2 - Restart CSI Provisioner:**
- Clears existing operation locks from memory
- Allows legitimate snapshot operations to proceed
- Without Step 1, this is only a temporary fix

### CSI Provisioner vs CSI Plugin (Important Distinction)

**⚠️ RESTART ONLY THE PROVISIONER, NOT THE PLUGIN:**

- `csi-rbdplugin-provisioner` (Deployment) ✅ - Safe to restart
  - Handles PVC provisioning (CreateVolume, DeleteVolume)
  - Does NOT create Ceph watchers
  - Does NOT mount volumes on nodes

- `csi-rbdplugin` (DaemonSet) ❌ - DO NOT RESTART
  - Runs on every node
  - Mounts volumes to nodes (creates Ceph watchers)
  - Restarting creates orphaned watchers

### Step 1: Identify Orphaned VolumeSnapshots

**Orphaned VolumeSnapshots** = snapshots referencing PVCs that no longer exist

```bash
# Find VolumeSnapshots with missing source PVCs
kubectl get volumesnapshot --all-namespaces -o json | \
  jq -r '.items[] | select(.spec.source.persistentVolumeClaimName != null) |
  "\(.metadata.namespace) \(.metadata.name) \(.spec.source.persistentVolumeClaimName)"' | \
  while read ns snap pvc; do
    kubectl get pvc -n $ns $pvc &>/dev/null || echo "ORPHANED: $ns/$snap (PVC $pvc missing)"
  done
```

Expected: List of snapshots trying to snapshot deleted PVCs (archon, home-assistant, zigbee2mqtt, etc.)

### Step 2: Delete Orphaned VolumeSnapshots

**Why this is safe:**
- These snapshots reference PVCs that were deleted
- They can never complete (timeout after 10m trying to snapshot non-existent volumes)
- They're blocking CSI snapshot operations
- Deleting them removes the source of timeouts

```bash
# Delete all VolumeSnapshots with missing source PVCs
kubectl get volumesnapshot --all-namespaces -o json | \
  jq -r '.items[] | select(.spec.source.persistentVolumeClaimName != null) |
  "\(.metadata.namespace) \(.metadata.name) \(.spec.source.persistentVolumeClaimName)"' | \
  while read ns snap pvc; do
    if ! kubectl get pvc -n $ns $pvc &>/dev/null; then
      echo "Deleting orphaned snapshot: $ns/$snap (PVC $pvc missing)"
      kubectl delete volumesnapshot -n $ns $snap
    fi
  done
```

### Step 3: Document Current State

```bash
# Count remaining issues before CSI restart
echo "Orphaned snapshots deleted. Remaining failed snapshots:"
kubectl get volumesnapshot --all-namespaces | grep false | wc -l

echo "Stuck vs-prime PVCs:"
kubectl get pvc --all-namespaces | grep "vs-prime" | grep Pending | wc -l

# Document state
kubectl get volumesnapshot --all-namespaces -o yaml > /tmp/snapshots-before-csi-restart.yaml
kubectl get pvc --all-namespaces -o yaml > /tmp/pvcs-before-csi-restart.yaml
```

### Step 4: Restart CSI Provisioner Deployment

```bash
# Restart ONLY the provisioner deployment (NOT the daemonset)
kubectl rollout restart deployment -n rook-ceph csi-rbdplugin-provisioner

# Wait for rollout to complete
kubectl rollout status deployment -n rook-ceph csi-rbdplugin-provisioner --timeout=5m
```

### Step 5: Monitor PVC Provisioning (First 5 Minutes)

```bash
# Watch vs-prime PVCs - should start provisioning immediately
watch -n 2 'kubectl get pvc --all-namespaces | grep "vs-prime"'

# In another terminal, watch for CSI errors
kubectl logs -n rook-ceph deploy/csi-rbdplugin-provisioner -c csi-rbdplugin --follow | grep -E "error|Error|ERROR"
```

**Expected behavior:**
- vs-prime PVCs should change from Pending → Bound within 1-2 minutes
- CSI logs should show successful CreateVolume operations
- No "already exists" errors

### Step 6: Monitor for Orphaned Watchers (Next 30 Minutes)

**⚠️ IMPORTANT:** While the provisioner restart is safe, monitor for any unexpected side effects:

```bash
# Watch for Multi-Attach errors (indicates orphaned watchers)
kubectl get events --all-namespaces --watch | grep -E "Multi-Attach|FailedAttachVolume"

# Check if any pods become stuck
kubectl get pods --all-namespaces | grep -E "ContainerCreating|Init:0/1"
```

**If Multi-Attach errors appear:**
- You have orphaned watchers (rare but possible)
- Follow Phase 6 of orphaned-volumes doc to clean up stuck cache/src PVCs

## Verification

```bash
# 1. All vs-prime PVCs should be Bound
kubectl get pvc --all-namespaces | grep "vs-prime" | grep -v Bound

# 2. Application PVCs should move from Pending to Bound
kubectl get pvc -n media prowlarr tdarr kometa threadfin

# 3. ReplicationDestination restore jobs should be running
kubectl get pods --all-namespaces | grep "volsync-dst"

# 4. Applications should start
kubectl get pods -n media prowlarr tdarr kometa threadfin
```

## Success Criteria
- All `vs-prime-*` PVCs in Bound state
- All application PVCs in Bound state
- ReplicationDestination restore pods running (not Pending)
- Application pods running

## Prevention

**Monitor CSI provisioner uptime:**
```bash
# Alert if CSI provisioner pod age > 7 days
kubectl get pod -n rook-ceph -l app=csi-rbdplugin-provisioner --sort-by=.status.startTime
```

Consider periodic CSI provisioner restarts during maintenance windows to prevent lock accumulation.

## References
- Main troubleshooting doc: `/docs/troubleshooting/2025-11-03-rook-ceph-orphaned-volumes-snapshot-deadlock.md`
- Phase 6: VolSync cache/src PVC cleanup pattern
- Rook Ceph Issue #134: CSI operation lock persistence
