# Playbook: Fix VolSync CSI Operation Locks (FINAL - TESTED)

## Problem
VolSync restore fails. PVCs stuck Pending. CSI has operation locks.

## Root Cause
ReplicationSources backup deleted PVCs → snapshots timeout → CSI keeps locks → everything fails.

## Solution (4 Steps)

### Step 1: Suspend Flux

Prevents recreation of resources while we clean up.

```bash
flux suspend source git flux-system
```

### Step 2: Delete All ReplicationSources

This is the source of the problem. Deleting them also cascades to delete VolumeSnapshots.

```bash
kubectl delete replicationsource --all -n ai
kubectl delete replicationsource --all -n home-automation
kubectl delete replicationsource --all -n media
kubectl delete replicationsource --all -n observability
kubectl delete replicationsource --all -n security
kubectl delete replicationsource --all -n selfhosted
```

**Verify:**
```bash
kubectl get replicationsource --all-namespaces
# Should show: No resources found
```

### Step 3: Restart CSI Provisioner

Clears operation locks from memory.

```bash
kubectl rollout restart deployment -n rook-ceph csi-rbdplugin-provisioner
kubectl rollout status deployment -n rook-ceph csi-rbdplugin-provisioner --timeout=5m
```

### Step 4: Resume Flux

Let Flux recreate everything clean.

```bash
flux resume source git flux-system
```

## Verification

```bash
# 1. No operation lock errors
kubectl logs -n rook-ceph deploy/csi-rbdplugin-provisioner -c csi-rbdplugin --tail=50 | grep "already exists"
# Expected: No output or very few errors

# 2. PVCs provisioning
kubectl get pvc --all-namespaces | grep Pending
# Expected: Count decreasing over 5-10 minutes

# 3. Apps recovering
kubectl get pods --all-namespaces | grep Running | wc -l
# Expected: Count increasing
```

## What This Fixed

1. ✅ Stopped ReplicationSources from creating failing snapshots
2. ✅ Cleaned up all orphaned VolumeSnapshots
3. ✅ Cleared CSI operation locks
4. ✅ Flux recreates ReplicationSources fresh for existing apps

## Notes

- ReplicationSources will be recreated by Flux for apps that exist
- Apps that were deleted won't have ReplicationSources recreated (correct behavior)
- If Pending PVCs remain, they need ReplicationDestinations to restore from backup first
- This is a complete reset of the VolSync backup system

## Prevention

When doing cleanup/deletes in the future:
1. Delete ReplicationSource CRDs along with PVCs
2. Or suspend ReplicationSources before deleting PVCs
3. Don't leave ReplicationSources orphaned without source PVCs
