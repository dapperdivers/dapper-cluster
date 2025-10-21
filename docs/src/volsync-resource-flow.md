# VolSync Resource Flow and Cleanup Guide

**Date:** 2025-10-21
**Purpose:** Document VolSync resource hierarchy and cleanup procedures for infrastructure changes

## Overview

VolSync creates a complex chain of Kubernetes resources for backup and replication. Understanding this flow is critical when making infrastructure changes to avoid orphaned resources or provisioning conflicts.

## Resource Hierarchy

```
Flux Kustomization (volsync)
  └── App Kustomization (e.g., archon)
      ├── ReplicationSource (archon)
      │   ├── Snapshot PVC (volsync-archon-src)
      │   ├── Cache PVC (volsync-src-archon-cache) [RBD]
      │   ├── Repository PVC (volsync-archon-repo)
      │   │   └── Repository PV (volsync-archon-repo-pv) [Static CephFS]
      │   └── Mover Pod (volsync-src-archon-xxxxx)
      │
      ├── ReplicationSource (archon-r2) [Remote/R2]
      │   ├── Snapshot PVC (volsync-archon-r2-src)
      │   ├── Cache PVC (volsync-src-archon-r2-cache) [RBD]
      │   └── Mover Pod (volsync-src-archon-r2-xxxxx)
      │
      └── ReplicationDestination (archon-dst)
          ├── Destination PVC (volsync-archon-dst-dest)
          ├── Cache PVC (volsync-dst-archon-dst-cache) [RBD]
          ├── Repository PVC (volsync-archon-repo)
          │   └── Repository PV (volsync-archon-repo-pv) [Static CephFS]
          └── Mover Pod (volsync-dst-archon-dst-xxxxx)
```

## Resource Types Explained

### Static Resources (Pre-created via Kustomize)

1. **Repository PV** (`volsync-${APP}-repo-pv`)
   - Type: Static CephFS PersistentVolume
   - Points to: `/k8s-backups/volsync/${APP}` on external Ceph cluster
   - Purpose: Houses restic repository data
   - Created by: `flux/components/volsync/repository-pv.yaml` template
   - Key attributes:
     ```yaml
     volumeAttributes:
       clusterID: rook-ceph
       fsName: cephfs
       staticVolume: "true"
       pool: k8s-backups
       rootPath: "/k8s-backups/volsync/${APP}"
     ```

2. **Repository PVC** (`volsync-${APP}-repo`)
   - Type: PersistentVolumeClaim
   - Binds to: Static PV above via `volumeName` field
   - Created by: `flux/components/volsync/repository-pvc.yaml` template

### Dynamic Resources (Created by VolSync Operator)

3. **ReplicationSource/Destination**
   - Type: VolSync CRDs
   - Created by: App kustomizations (when volsync component is included)
   - Manages: Backup/restore jobs

4. **Cache PVCs** (e.g., `volsync-src-${APP}-cache`, `volsync-dst-${APP}-dst-cache`)
   - Type: Dynamic RBD PersistentVolumeClaims
   - Created by: VolSync operator (from ReplicationSource/Destination specs)
   - Purpose: Temporary staging for restic operations
   - Storage Class: `ceph-rbd` (block storage)

5. **Snapshot PVCs** (e.g., `volsync-${APP}-src`)
   - Type: Dynamic CephFS PersistentVolumeClaims
   - Created by: VolSync operator from source data snapshots
   - Storage Class: `cephfs-shared`

6. **Mover Pods**
   - Type: Kubernetes Pods
   - Created by: VolSync operator
   - Purpose: Execute restic backup/restore operations
   - Mounts: Source/destination PVCs, cache PVCs, repository PVC

## Common Cleanup Scenarios

### Scenario 1: Changing Repository PV Configuration

**When:** Modifying `repository-pv.yaml` (path, pool, monitors, etc.)

**Why cleanup needed:** Static PVs are immutable once created. Changes require delete/recreate.

**Cleanup Order:**

```bash
# 1. Suspend the volsync kustomization to prevent recreation
flux suspend kustomization volsync -n storage

# 2. Scale down volsync operator
kubectl scale deployment volsync -n storage --replicas=0

# 3. Delete ReplicationSources
kubectl get replicationsource -A -o json | \
  jq -r '.items[] | "\(.metadata.namespace) \(.metadata.name)"' | \
  xargs -n 2 sh -c 'kubectl delete replicationsource -n $0 $1'

# 4. Delete ReplicationDestinations
kubectl get replicationdestination -A -o json | \
  jq -r '.items[] | "\(.metadata.namespace) \(.metadata.name)"' | \
  xargs -n 2 sh -c 'kubectl delete replicationdestination -n $0 $1'

# 5. Delete Repository PVCs (unbinds from PVs)
kubectl get pvc -A -o json | \
  jq -r '.items[] | select(.metadata.name | test("volsync-.*-repo$")) | "\(.metadata.namespace) \(.metadata.name)"' | \
  xargs -n 2 sh -c 'kubectl delete pvc -n $0 $1'

# 6. Delete Repository PVs
kubectl get pv -o name | \
  grep "persistentvolume/volsync-.*-repo-pv$" | \
  xargs kubectl delete

# 7. Wait for cleanup to complete
sleep 10

# 8. Commit and push your repository-pv.yaml changes
git add kubernetes/flux/components/volsync/repository-pv.yaml
git commit -m "fix(volsync): update repository PV configuration"
git push

# 9. Resume volsync kustomization (recreates PVs/PVCs with new config)
flux resume kustomization volsync -n storage

# 10. Scale volsync operator back up
kubectl scale deployment volsync -n storage --replicas=1

# 11. Watch for recreation
watch kubectl get pv,pvc -A | grep volsync
```

### Scenario 2: Stuck Cache PVC Provisioning

**When:** Cache PVCs stuck in Pending with "Volume ID already exists" errors

**Why this happens:** Orphaned provisioning operations in Ceph RBD from previous deletion attempts

**Cleanup Order:**

```bash
# 1. Delete stuck cache PVCs
kubectl get pvc -A -o json | \
  jq -r '.items[] | select(.metadata.name | test("cache")) | select(.status.phase == "Pending") | "\(.metadata.namespace) \(.metadata.name)"' | \
  xargs -n 2 sh -c 'kubectl delete pvc -n $0 $1'

# 2. Wait for VolSync operator to recreate with fresh UIDs
# Cache PVCs are owned by ReplicationSource/Destination resources
# and will auto-recreate with new UIDs that don't conflict
```

### Scenario 3: Full VolSync Reset

**When:** Major infrastructure changes, migrating storage backends, etc.

**Cleanup Order:**

```bash
# Complete reset - destroys all VolSync resources but preserves data in /k8s-backups/volsync/

# 1. Suspend volsync
flux suspend kustomization volsync -n storage

# 2. Scale down operator
kubectl scale deployment volsync -n storage --replicas=0

# 3. Delete all ReplicationSources
kubectl get replicationsource -A -o json | \
  jq -r '.items[] | "\(.metadata.namespace) \(.metadata.name)"' | \
  xargs -n 2 sh -c 'kubectl delete replicationsource -n $0 $1'

# 4. Delete all ReplicationDestinations
kubectl get replicationdestination -A -o json | \
  jq -r '.items[] | "\(.metadata.namespace) \(.metadata.name)"' | \
  xargs -n 2 sh -c 'kubectl delete replicationdestination -n $0 $1'

# 5. Delete all cache PVCs
kubectl get pvc -A -o json | \
  jq -r '.items[] | select(.metadata.name | test("cache")) | "\(.metadata.namespace) \(.metadata.name)"' | \
  xargs -n 2 sh -c 'kubectl delete pvc -n $0 $1'

# 6. Delete all snapshot PVCs
kubectl get pvc -A -o json | \
  jq -r '.items[] | select(.metadata.name | test("volsync-.*-src$|volsync-.*-dst-dest$")) | "\(.metadata.namespace) \(.metadata.name)"' | \
  xargs -n 2 sh -c 'kubectl delete pvc -n $0 $1'

# 7. Delete repository PVCs
kubectl get pvc -A -o json | \
  jq -r '.items[] | select(.metadata.name | test("volsync-.*-repo$")) | "\(.metadata.namespace) \(.metadata.name)"' | \
  xargs -n 2 sh -c 'kubectl delete pvc -n $0 $1'

# 8. Delete repository PVs
kubectl get pv -o name | \
  grep "persistentvolume/volsync-.*-repo-pv$" | \
  xargs kubectl delete

# 9. Resume after changes
flux resume kustomization volsync -n storage
kubectl scale deployment volsync -n storage --replicas=1
```

## Critical Configuration Details

### Static CephFS PV Requirements

For static PVs pointing to existing CephFS directories:

```yaml
volumeAttributes:
  clusterID: rook-ceph          # References mon-endpoints ConfigMap
  fsName: cephfs                 # CephFS filesystem name
  staticVolume: "true"           # REQUIRED for static PVs
  pool: k8s-backups             # Data pool (doesn't affect mount path)
  rootPath: "/k8s-backups/volsync/${APP}"  # FULL path in filesystem
```

**Important Notes:**
- `staticVolume: "true"` is **mandatory** - without it, CSI driver won't properly discover monitors
- `pool` parameter specifies which data pool stores the data, NOT the mount path
- `rootPath` must be the **full filesystem path** where data exists
- `monitors` field is **NOT required** - auto-discovered from `rook-ceph-mon-endpoints` ConfigMap when `staticVolume: "true"`

### Why Pool Doesn't Change Mount Path

The `pool` parameter in CephFS tells Ceph which data pool to use for **new data storage**, but:
- Mount paths are at the **filesystem level**, not pool level
- All pools share the same namespace/directory structure
- Path `/k8s-backups/volsync/archon` exists in the filesystem regardless of pool
- The `pool` only matters for data placement on OSDs

Example:
```
Filesystem: cephfs
  ├── /volumes/csi/...          (data in cephfs_data pool)
  ├── /k8s-backups/volsync/...  (data in k8s-backups pool)
  └── /truenas/k8s/...          (data could be in different pool)
```

## Troubleshooting

### Mount Error: "No such file or directory"

```
mount error 2 = No such file or directory
```

**Cause:** `rootPath` doesn't exist in CephFS filesystem
**Solution:** Verify path exists: `ls /mnt/cephfs/k8s-backups/volsync/${APP}`
**Fix:** Update `rootPath` in `repository-pv.yaml` to match actual filesystem path

### DNS SRV Lookup Warnings

```
unable to get monitor info from DNS SRV with service name: ceph-mon
```

**Impact:** Warning only - mount proceeds with explicit monitors from ConfigMap
**Cause:** Ceph client tries DNS discovery before using explicit monitors
**Action:** None required if mount succeeds

### Cache PVC: "Volume ID already exists"

```
rpc error: code = Aborted desc = an operation with the given Volume ID already exists
```

**Cause:** Orphaned provisioning operation in RBD from previous PVC with same UID
**Solution:** Delete the PVC - VolSync will recreate with fresh UID

## Data Safety

### What Gets Deleted

When following cleanup procedures:
- ✅ Kubernetes PVs/PVCs (metadata only)
- ✅ ReplicationSource/Destination CRDs
- ✅ Temporary cache volumes
- ✅ Snapshot PVCs

### What Gets Preserved

The cleanup procedures **DO NOT** delete:
- ✅ Actual restic repository data in `/k8s-backups/volsync/${APP}/`
- ✅ Application data in source PVCs
- ✅ R2/remote backup data

**Recovery:** Once resources are recreated, VolSync reconnects to existing restic repositories automatically.

## Monitoring Recovery

After cleanup and resume:

```bash
# Watch PVs being created
watch kubectl get pv | grep volsync

# Watch PVCs binding
watch kubectl get pvc -A | grep volsync

# Watch ReplicationSources
watch kubectl get replicationsource -A

# Check mover pod logs
kubectl logs -n <namespace> <volsync-src-pod> -f

# Verify mounts succeeded
kubectl get events -A --sort-by='.lastTimestamp' | grep -i mount | grep volsync
```

## Quick Reference Commands

```bash
# Count resources
echo "PVs: $(kubectl get pv | grep 'volsync-.*-repo-pv' | wc -l)"
echo "Repo PVCs: $(kubectl get pvc -A | grep 'volsync.*repo' | wc -l)"
echo "Cache PVCs: $(kubectl get pvc -A | grep 'cache' | wc -l)"
echo "Sources: $(kubectl get replicationsource -A --no-headers | wc -l)"
echo "Destinations: $(kubectl get replicationdestination -A --no-headers | wc -l)"

# Suspend/Resume
flux suspend kustomization volsync -n storage
flux resume kustomization volsync -n storage

# Scale operator
kubectl scale deployment volsync -n storage --replicas=0
kubectl scale deployment volsync -n storage --replicas=1

# Check volsync kustomization status
kubectl get ks volsync -n storage
```

## Lessons Learned (2025-10-21)

### Issue: Mount failures with "missing required field monitors"

**Root Cause:** Missing `staticVolume: "true"` attribute in PV spec
**Impact:** CSI driver couldn't discover monitors from ConfigMap
**Resolution:** Added `staticVolume: "true"` to volumeAttributes

### Issue: Mount failures with "No such file or directory"

**Root Cause:** `rootPath: "/volsync/${APP}"` but data at `/k8s-backups/volsync/${APP}`
**Impact:** Paths didn't exist, mounts failed
**Resolution:** Changed rootPath to `/k8s-backups/volsync/${APP}`

### Issue: Cache PVCs stuck provisioning

**Root Cause:** Orphaned RBD volume IDs from rapid delete/create cycles
**Impact:** "Volume ID already exists" errors
**Resolution:** Delete stuck PVCs, let VolSync recreate with fresh UIDs

## Related Documentation

- [VolSync Official Docs](https://volsync.readthedocs.io/)
- [Ceph CSI Static PV Guide](https://github.com/ceph/ceph-csi/blob/devel/docs/static-pvc.md)
- [Rook CephFS Documentation](https://rook.io/docs/rook/latest/Storage-Configuration/Shared-Filesystem-CephFS/filesystem-storage/)
