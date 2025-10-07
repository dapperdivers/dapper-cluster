# Storage Migration Hub

This directory contains migration documentation and jobs for moving all workloads to CephFS.

**📋 Key Documents:**
- **[MIGRATION_CHECKLIST.md](./MIGRATION_CHECKLIST.md)** - Complete migration plan with detailed steps
- **[MIGRATION_STATUS.md](./MIGRATION_STATUS.md)** - Current progress tracker
- This README - Legacy safe-nfs migration details

**Migration Targets:**
- `safe-nfs` → `cephfs-shared` (2 PVCs) - Uses rsync jobs
- `mayastor-single-replica` → `cephfs-shared` (36 PVCs) - Uses korb tool

---

# Legacy: NFS to CephFS Migration

This section contains the original safe-nfs migration plan. See MIGRATION_CHECKLIST.md for current status.

## Migration Plan

### Part 1: Paperless-ngx (Zero Downtime - Data Already on CephFS)

Data is already at `/truenas/Paperless-ngx` on CephFS. Just using Kyverno injection instead of direct NFS mount.

**Steps:**
1. Commit and push changes
2. Reconcile Kyverno policies:
   ```bash
   flux reconcile kustomization kyverno
   ```
3. Reconcile paperless-ngx (will restart with CephFS mount):
   ```bash
   flux reconcile helmrelease -n selfhosted paperless-ngx
   ```
4. Verify paperless can see data at `/safe`

**Verification:**
```bash
kubectl exec -n selfhosted deploy/paperless-ngx-main -c app -- ls -la /safe
```

---

### Part 2: K8s Workload Storage (Requires Migration)

**Services affected:**
- plex (plex-posters: 75Gi)
- posterizarr (posterizarr-watcher: 1Gi, plex-posters: 75Gi shared with plex)
- authentik (authentik-media: 1Gi)

#### Step 1: Create New CephFS PVCs

```bash
# Commit and push changes first, then:
flux reconcile kustomization plex --with-source
flux reconcile kustomization posterizarr --with-source
flux reconcile kustomization authentik --with-source
```

Verify PVCs are created:
```bash
kubectl get pvc -n media plex-posters-cephfs posterizarr-watcher-cephfs
kubectl get pvc -n security authentik-media-cephfs
```

#### Step 2: Scale Down Services

```bash
kubectl scale -n media deploy/plex-plex --replicas=0
kubectl scale -n media deploy/posterizarr-posterizarr --replicas=0
kubectl scale -n security deploy/authentik-server --replicas=0
kubectl scale -n security deploy/authentik-worker --replicas=0
```

#### Step 3: Run Migration Jobs

```bash
# Plex posters (will take longest ~15-30min for 75Gi)
kubectl apply -f kubernetes/_migrations/plex-posters-migration.yaml
kubectl logs -n media job/migrate-plex-posters -f

# Posterizarr watcher (~2-5min)
kubectl apply -f kubernetes/_migrations/posterizarr-watcher-migration.yaml
kubectl logs -n media job/migrate-posterizarr-watcher -f

# Authentik media (~2-5min)
kubectl apply -f kubernetes/_migrations/authentik-media-migration.yaml
kubectl logs -n security job/migrate-authentik-media -f
```

**Monitor progress:**
```bash
# Check job status
kubectl get jobs -n media
kubectl get jobs -n security

# Check sizes
kubectl exec -n media job/migrate-plex-posters -- du -sh /dest
```

#### Step 4: Update Services to Use New PVCs

Changes already made in helmreleases. Reconcile to apply:

```bash
flux reconcile helmrelease -n media posterizarr
flux reconcile helmrelease -n security authentik
```

This will restart services with new PVCs automatically.

#### Step 5: Verify Services

```bash
# Check pods are running
kubectl get pods -n media -l app.kubernetes.io/name=plex
kubectl get pods -n media -l app.kubernetes.io/name=posterizarr
kubectl get pods -n security -l app.kubernetes.io/name=authentik

# Verify mounts
kubectl exec -n media deploy/posterizarr-posterizarr -- ls -la /config/watcher
kubectl exec -n media deploy/posterizarr-posterizarr -- ls -la /assets
kubectl exec -n security deploy/authentik-server -- ls -la /media
```

#### Step 6: Cleanup (After Verification)

Once everything works:

```bash
# Delete migration jobs
kubectl delete -f kubernetes/_migrations/plex-posters-migration.yaml
kubectl delete -f kubernetes/_migrations/posterizarr-watcher-migration.yaml
kubectl delete -f kubernetes/_migrations/authentik-media-migration.yaml

# Delete old safe-nfs PVCs
kubectl delete pvc -n media plex-posters posterizarr-watcher
kubectl delete pvc -n security authentik-media

# Remove old PVC manifests from git
git rm kubernetes/apps/media/plex/app/pvc.yaml
git rm kubernetes/apps/media/posterizarr/app/pvc.yaml
git rm kubernetes/apps/security/authentik/app/pvc.yaml

# Update kustomizations to remove old pvc.yaml references
# Then delete this migrations directory
```

---

## Rollback Plan

If something goes wrong:

### For Paperless-ngx:
1. Remove label from helmrelease
2. Add back NFS mount
3. Reconcile

### For PVC migrations:
1. Scale down services
2. Revert helmrelease PVC names back to old ones
3. Scale services back up
4. Delete new CephFS PVCs

---

## Expected Downtime

- **Paperless-ngx**: ~30 seconds (pod restart only)
- **Plex**: ~15-30 minutes (75Gi rsync + startup)
- **Posterizarr**: ~2-5 minutes (1Gi rsync + startup)
- **Authentik**: ~2-5 minutes (1Gi rsync + startup)

---

## Storage Summary

### Before:
- plex-posters: safe-nfs (vault.manor NFS) - 75Gi
- posterizarr-watcher: safe-nfs (vault.manor NFS) - 1Gi
- authentik-media: safe-nfs (vault.manor NFS) - 1Gi
- paperless data: vault.manor NFS direct mount

### After:
- plex-posters-cephfs: CephFS dynamic PVC - 100Gi
- posterizarr-watcher-cephfs: CephFS dynamic PVC - 5Gi
- authentik-media-cephfs: CephFS dynamic PVC - 5Gi
- paperless data: CephFS Kyverno injection (direct mount)

**Benefits:**
- ✅ All on CephFS (no NFS dependency on vault.manor)
- ✅ Dynamic PVCs support snapshots, resize, lifecycle
- ✅ Room to grow (increased sizes)
- ✅ Better performance
- ✅ Centralized storage on Ceph cluster
