# VolSync NFS to CephFS Migration

**Status:** In Progress - Phase 1 & 2 Complete, Ready for Data Migration
**Date Started:** 2025-10-09
**Target Completion:** TBD
**Goal:** Migrate VolSync backup repository from NFS (vault.manor TrueNAS) to CephFS to enable TrueNAS VM decommissioning

**Data Confirmed:** VolSync data exists at `/k8s/volsync/*` on NFS (vault.manor)

## Current State

### NFS Configuration
- **Server:** `vault.manor` (TrueNAS VM)
- **Path:** `/mnt/Tank/k8s/volsync`
- **Usage:** Restic repository backend for all VolSync backups
- **Hardcoded in:**
  1. `kubernetes/apps/storage/volsync/app/mutations/volsync-mover-nfs.yaml` (mutation policy)
  2. `.taskfiles/volsync/resources/templates/unlock.yaml` (manual unlock task)

### CephFS Availability
- CephFS cluster is operational via Rook
- Data already exists on CephFS at `/truenas/*` paths (Media, Minio, Paperless)
- Static PV pattern established and working for other apps
- Secret `rook-csi-cephfs-static` available in `rook-ceph` namespace

## Migration Tasks

### Phase 1: Create CephFS Infrastructure ✅

- [x] **Create Static PV/PVC for VolSync Repository**
  - File: `kubernetes/apps/storage/volsync/app/volsync-cephfs-pv.yaml`
  - Pattern: Follow existing static PV examples (media, minio, paperless)
  - CephFS Path: `/truenas/volsync`
  - Capacity: 5Ti
  - Namespace: `storage`
  - Storage Class: `cephfs-static`
  - Secret Reference: `rook-csi-cephfs-static` in `rook-ceph` namespace

- [x] **Update Main App Kustomization**
  - File: `kubernetes/apps/storage/volsync/app/kustomization.yaml`
  - Add `volsync-cephfs-pv.yaml` to resources list

### Phase 2: Update VolSync Configuration ✅

- [x] **Update Mover Mutation Policy**
  - Created new file: `kubernetes/apps/storage/volsync/app/mutations/volsync-mover-cephfs.yaml`
  - Changed metadata names: `volsync-mover-nfs` → `volsync-mover-cephfs`
  - Replaced NFS volume definition with PVC:
    ```yaml
    # OLD (NFS):
    nfs:
      server: vault.manor
      path: /mnt/Tank/k8s/volsync

    # NEW (CephFS via PVC):
    persistentVolumeClaim:
      claimName: volsync-cephfs-pvc
    ```

- [x] **Update Unlock Task Template**
  - File: `.taskfiles/volsync/resources/templates/unlock.yaml`
  - Replaced NFS volume definition with PVC reference
  - Updated container name from `nfs` to `repository`

- [x] **Update Mutations Kustomization**
  - File: `kubernetes/apps/storage/volsync/app/mutations/kustomization.yaml`
  - Updated resource reference to `volsync-mover-cephfs.yaml`

### Phase 3: Data Migration 🚧

- [x] **Assess Current NFS Data**
  - ✅ Data exists at `/k8s/volsync/*` on vault.manor NFS
  - ⏳ Determine total size (TODO)
  - ⏳ List all app repositories (TODO)
  - ⏳ Document current backup schedule/timing (TODO)

- [ ] **Verify CephFS Target Path**
  - Confirm path `/truenas/volsync` exists or create it
  - Verify permissions match requirements (Restic needs write access)

- [x] **Migration Pod Created**
  - Created: `kubernetes/apps/storage/volsync/app/volsync-migration-pod.yaml`
  - Mounts both NFS (read-only) and CephFS PVC (read-write)
  - Ready to use for rsync data transfer

- [ ] **Perform Data Migration**
  - Apply migration pod: `kubectl apply -f volsync-migration-pod.yaml`
  - Wait for pod ready: `kubectl -n storage wait --for=condition=ready pod/volsync-migration`
  - Install rsync: `kubectl -n storage exec -it volsync-migration -- apk add rsync`
  - Execute rsync: `kubectl -n storage exec -it volsync-migration -- rsync -avP --stats /nfs-source/ /cephfs-target/`
  - Verify data integrity after migration
  - Confirm directory structure: `/repository/{app-name}/` for each app
  - Delete migration pod: `kubectl delete -f volsync-migration-pod.yaml`

### Phase 4: Testing & Validation

- [ ] **Deploy CephFS Configuration**
  - Apply PV/PVC manifests
  - Verify PVC binds successfully
  - Apply updated mutation policy
  - Verify old mutation policy is replaced

- [ ] **Test Manual Unlock Task**
  - Pick a test app with existing backup
  - Run: `task volsync:unlock-local NS=<namespace> APP=<app>`
  - Verify job completes successfully
  - Check logs for any CephFS-specific errors

- [ ] **Test Backup Job**
  - Trigger manual backup: `task volsync:snapshot NS=<namespace> APP=<app>`
  - Monitor job execution
  - Verify backup completes successfully
  - Check repository integrity: `task volsync:run NS=<namespace> REPO=<app> -- snapshots`

- [ ] **Monitor Scheduled Backups**
  - Wait for next scheduled backup cycle
  - Verify all apps backup successfully
  - Check Prometheus metrics for VolSync
  - Review logs for any warnings/errors

### Phase 5: Cleanup & Documentation

- [ ] **Remove NFS Dependencies**
  - Verify all backups working on CephFS for 7+ days
  - Update any documentation referencing NFS paths
  - Remove/archive old mutation policy if renamed

- [ ] **Decommission TrueNAS VM Prerequisites**
  - Document this as completed prerequisite for TrueNAS decommission
  - Verify no other services depend on `vault.manor` NFS
  - Add to broader TrueNAS decommission checklist

## Rollback Plan

If issues occur during migration:

1. **Immediate Rollback:**
   - Revert mutation policy to NFS version
   - Remove CephFS PV/PVC
   - Re-deploy VolSync helmrelease to reset state

2. **Partial Rollback:**
   - Keep CephFS infrastructure
   - Configure specific apps to use NFS temporarily
   - Investigate issues per-app basis

## References

- Existing CephFS Static PV Examples:
  - `kubernetes/apps/media/storage/app/media-cephfs-pv.yaml`
  - `kubernetes/apps/storage/minio/app/minio-cephfs-pv.yaml`
  - `kubernetes/apps/selfhosted/paperless-ngx/app/paperless-cephfs-pv.yaml`

- VolSync Components:
  - Mutation: `kubernetes/apps/storage/volsync/app/mutations/volsync-mover-nfs.yaml`
  - Tasks: `.taskfiles/volsync/Taskfile.yaml`
  - ReplicationSource Template: `kubernetes/flux/components/volsync/local/replicationsource.yaml`

## Notes

- **Why CephFS over RBD?** ReadWriteMany access mode needed for backup repositories
- **Storage Class:** Using `cephfs-static` for pre-existing path, not `cephfs-shared` (dynamic provisioning)
- **Backup Schedule:** Current schedule is hourly (`0 * * * *`) per ReplicationSource template
- **Repository Format:** Restic repositories, one per app at `/repository/{APP}` path

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-10-09 | Use CephFS instead of continuing NFS | CephFS cluster operational, enables TrueNAS VM decommission |
| 2025-10-09 | Rename mutation file to `volsync-mover-cephfs.yaml` | Clearer naming reflects the backend storage type |
| 2025-10-09 | Use temporary migration pod for data transfer | Allows safe, in-cluster rsync with both volumes mounted |
| 2025-10-09 | Create PVCs via common component instead of Reflector | Reflector doesn't support PVC reflection; common component creates PVC in all namespaces via Kustomize |
| 2025-10-09 | Update VolSync dependencies from NFS to Rook Ceph | Changed from `csi-driver-nfs-classes` to `rook-ceph-cluster` dependency |
