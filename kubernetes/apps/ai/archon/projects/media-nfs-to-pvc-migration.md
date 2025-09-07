# Media Services NFS to PVC Migration Project

## Overview
Migrate all media services from inline NFS mounts to shared PersistentVolumeClaims (PVCs) for centralized storage management and optimized mount options.

## Benefits
- **Centralized Management**: Single source of truth for NFS mount options
- **Performance**: Optimized mount options with 4MB buffers for large media files
- **Consistency**: All services use the same optimized settings
- **Node Affinity**: Can schedule pods to NFS-optimized worker nodes
- **Reduced Duplication**: No need to repeat mount configurations

## Current State
- **10 services** use vault.manor
- **7 services** use tower.manor
- **5 services** use tower-2.manor
- All using inline NFS mounts with default/varied mount options

## Target Architecture
```
PersistentVolumes (Optimized NFS) → PersistentVolumeClaims → Media Services
```

## Phase 1: Infrastructure Setup ✅

### 1.1 Talos Node Configuration ✅
**Note**: NFS optimizations are handled at the PVC mount options level
- [x] nfsrahead extension already configured on all nodes
- [x] Mount options optimized in PV definitions (4MB buffers, caching)
- [x] No Talos patches required (fs-cache not supported)

### 1.2 Create PersistentVolumes and PVCs ✅
**File**: `kubernetes/apps/media/media-nfs-storage/app/pvcs.yaml`
- [x] Created PV/PVC for vault.manor (NFS v4.1)
- [x] Created PV/PVC for tower.manor (NFS v4.2)
- [x] Created PV/PVC for tower-2.manor (NFS v4.2, fs-cache removed)
- [x] Applied to cluster via Flux
- [x] PVs are bound: `media-vault-pv`, `media-tower-pv`, `media-tower-2-pv`
- [x] PVCs are bound in media namespace

## Phase 2: Service Migration

### 2.1 Test Service - Radarr (Start Here)
**Why Radarr**: Good test case - uses 2 NFS mounts (vault and tower-2)

#### Pre-Migration Checklist
- [ ] Backup current Radarr configuration
- [ ] Note current mount paths: `/safe` (vault) and `/tower-2`
- [ ] Verify PVCs are ready in media namespace
- [ ] Schedule maintenance window (if needed)

#### Migration Steps
1. [ ] Update `kubernetes/apps/media/radarr/app/helmrelease.yaml`:
   ```yaml
   # Replace this:
   persistence:
     safe:
       type: nfs
       server: vault.manor
       path: /mnt/Tank/Media
       globalMounts:
         - path: /safe
     tower-2:
       type: nfs
       server: tower-2.manor
       path: /mnt/user/Media
       globalMounts:
         - path: /tower-2

   # With this:
   persistence:
     vault-media:
       existingClaim: media-vault-pvc
       globalMounts:
         - path: /safe
     tower-2-media:
       existingClaim: media-tower-2-pvc
       globalMounts:
         - path: /tower-2
   ```

2. [ ] Apply the changes: `kubectl apply -f kubernetes/apps/media/radarr/app/helmrelease.yaml`

3. [ ] Verify pod restart: `kubectl rollout status deployment/radarr -n media`

4. [ ] Test Radarr functionality:
   - [ ] Web UI accessible
   - [ ] Can browse media files at /safe
   - [ ] Can browse media files at /tower-2
   - [ ] Can import/move files successfully
   - [ ] Check logs for NFS errors: `kubectl logs -n media deployment/radarr`

5. [ ] Monitor for 24 hours for stability

### 2.2 Remaining Services Migration Order

#### High Priority (Multiple Mounts)
- [ ] **Plex** (3 mounts: vault, tower, tower-2)
- [ ] **Sabnzbd** (3 mounts: vault, tower, tower-2)
- [ ] **Bazarr** (3 mounts: vault, tower, tower-2)
- [ ] **Bazarr-UHD** (3 mounts: vault, tower, tower-2)

#### Medium Priority (2 mounts)
- [ ] **Sonarr** (vault, tower)
- [ ] **Sonarr-UHD** (vault, tower)
- [ ] **Radarr-UHD** (vault, tower)

#### Low Priority (1 mount)
- [ ] **Tdarr** (vault only)
- [ ] **Nzbget** (vault only)
- [ ] **Cross-seed** (already updated ✅)

## Phase 3: Validation & Cleanup

### 3.1 Final Validation
- [ ] All services using PVCs
- [ ] No inline NFS mounts remaining
- [ ] All services functional
- [ ] Performance metrics improved
- [ ] NFS read-ahead optimizations working

### 3.2 Documentation
- [ ] Update service documentation
- [ ] Document mount paths for each service
- [ ] Create troubleshooting guide
- [ ] Update backup procedures

### 3.3 Cleanup
- [ ] Remove migration examples
- [ ] Archive old configurations
- [ ] Update monitoring alerts

## Rollback Plan

If issues occur during migration:

1. **Quick Rollback** (per service):
   ```bash
   # Revert the helmrelease.yaml to previous version
   git checkout HEAD~1 kubernetes/apps/media/<service>/app/helmrelease.yaml
   kubectl apply -f kubernetes/apps/media/<service>/app/helmrelease.yaml
   ```

2. **Full Rollback** (if PVCs have issues):
   - Keep inline NFS mounts
   - Delete PVCs/PVs if needed
   - Revert all services to inline mounts

## Success Metrics
- ✅ All media services using PVCs
- ✅ Zero NFS-related errors in logs
- ✅ Improved read performance (measure with `iostat`)
- ✅ Reduced network traffic (NFS cache hits)
- ✅ Consistent mount options across all services

## Commands Reference

```bash
# Apply PVs and PVCs
kubectl apply -f kubernetes/apps/storage/media-nfs-pvs.yaml

# Check PV/PVC status
kubectl get pv -l storage.type=nfs-media
kubectl get pvc -n media

# Watch service rollout
kubectl rollout status -n media deployment/<service-name>

# Check logs for NFS issues
kubectl logs -n media deployment/<service-name> | grep -i "nfs\|stale\|mount"

# Check NFS statistics (on worker nodes)
nfsstat -c

# Monitor NFS performance
nfsstat -c
```

## Notes
- Start with Radarr as test case
- Monitor each service for 24 hours before proceeding to next
- Keep original configurations backed up
- Consider maintenance windows for critical services (Plex)
