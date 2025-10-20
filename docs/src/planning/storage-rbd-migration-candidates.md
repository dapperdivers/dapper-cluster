# Ceph RBD Storage Migration Candidates

Analysis performed: 2025-10-17

## Overview

This document identifies workloads in the cluster that would benefit from migrating to **ceph-rbd** (Ceph block storage) instead of cephfs-shared (CephFS shared filesystem).

**Key Principle:** Databases, time-series stores, and stateful services requiring high I/O performance should use block storage (RBD). Shared files, media libraries, and backups should use filesystem storage (CephFS).

---

## Current Status

### Already Using ceph-rbd ✓
- **PostgreSQL (CloudNativePG)** - 20Gi data + 5Gi WAL

### Storage Classes Available
- `ceph-rbd` - Block storage (RWO) - Best for databases
- `cephfs-shared` - Shared filesystem (RWX) - Best for shared files/media
- `cephfs-static` - Static CephFS volumes

---

## Storage Configuration Patterns

Before migrating workloads, it's important to understand how PVCs are created in this cluster:

### Pattern 1: Volsync Component Pattern (Most Apps)

**Used by:** 41+ applications including all media apps, self-hosted apps, home automation, AI apps

**How it works:**
1. Application's `ks.yaml` includes the volsync component:
   ```yaml
   components:
     - ../../../../flux/components/volsync
   ```

2. PVC is created by the volsync component template (`flux/components/volsync/pvc.yaml`)

3. Storage configuration is set via `postBuild.substitute` in the `ks.yaml`:
   ```yaml
   postBuild:
     substitute:
       APP: prowlarr
       VOLSYNC_CAPACITY: 5Gi
       VOLSYNC_STORAGECLASS: cephfs-shared      # Default if not specified
       VOLSYNC_ACCESSMODES: ReadWriteMany       # Default if not specified
       VOLSYNC_SNAPSHOTCLASS: cephfs-snapshot   # Default if not specified
   ```

**Default values:**
- Storage Class: `cephfs-shared`
- Access Modes: `ReadWriteMany`
- Snapshot Class: `cephfs-snapshot`

**Examples:**
- Prowlarr: `kubernetes/apps/media/prowlarr/ks.yaml`
- Obsidian CouchDB: `kubernetes/apps/selfhosted/obsidian-couchdb/ks.yaml`
- Most workloads with < 100Gi storage needs

### Pattern 2: Direct HelmRelease Pattern

**Used by:** Large observability workloads (Prometheus, Loki, AlertManager)

**How it works:**
1. Storage is defined directly in the HelmRelease values
2. No volsync component used
3. PVC created by Helm chart templates

**Example (Prometheus):**
```yaml
# kubernetes/apps/observability/kube-prometheus-stack/app/helmrelease.yaml
prometheus:
  prometheusSpec:
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: cephfs-shared
          resources:
            requests:
              storage: 100Gi
```

**Examples:**
- Prometheus: `kubernetes/apps/observability/kube-prometheus-stack/app/helmrelease.yaml`
- Loki: `kubernetes/apps/observability/loki/app/helmrelease.yaml`
- AlertManager: `kubernetes/apps/observability/kube-prometheus-stack/app/helmrelease.yaml`

---

## Migration Candidates

### 🔴 HIGH Priority - Data Durability Risk

#### 1. Dragonfly Redis
- **Namespace:** database
- **Current Storage:** NONE (ephemeral, in-memory only)
- **Current Size:** N/A (data lost on restart)
- **Replicas:** 3
- **Recommended:** Add ceph-rbd PVCs (~10Gi each for snapshots/persistence)
- **Why:** Redis alternative running in cluster mode needs persistent snapshots for:
  - Data durability across restarts
  - Cluster state recovery
  - Snapshot-based backups
- **Impact:** HIGH - Currently losing all data on pod restart
- **Config Location:** `kubernetes/apps/database/dragonfly-redis/cluster/cluster.yaml`
- **Migration Complexity:** Medium - requires modifying Dragonfly CRD to add volumeClaimTemplates

#### 2. EMQX MQTT Broker
- **Namespace:** database
- **Current Storage:** NONE (emptyDir, ephemeral)
- **Current Size:** N/A (data lost on restart)
- **Replicas:** 3 (StatefulSet)
- **Recommended:** Add ceph-rbd PVCs (~5-10Gi each for session/message persistence)
- **Why:** MQTT brokers need persistent storage for:
  - Retained messages
  - Client subscriptions
  - Session state for QoS > 0
  - Cluster configuration
- **Impact:** HIGH - Currently losing retained messages and sessions on restart
- **Config Location:** `kubernetes/apps/database/emqx/cluster/cluster.yaml`
- **Migration Complexity:** Medium - requires modifying EMQX CRD to add persistent volumes

---

### 🟡 MEDIUM Priority - Performance & Best Practices

#### 3. CouchDB (obsidian-couchdb)
- **Namespace:** selfhosted
- **Current Storage:** cephfs-shared
- **Current Size:** 5Gi
- **Replicas:** 1 (Deployment)
- **Storage Pattern:** ✅ **Volsync Component** (`kubernetes/apps/selfhosted/obsidian-couchdb/ks.yaml`)
- **Recommended:** Migrate to ceph-rbd
- **Why:** NoSQL database benefits from:
  - Better I/O performance for document reads/writes
  - Improved fsync performance for data integrity
  - Block-level snapshots for consistent backups
- **Impact:** Medium - requires backup, PVC migration, restore
- **Migration Complexity:** Medium - GitOps workflow with volsync pattern
  - Update ks.yaml postBuild substitutions
  - Commit and push changes
  - Flux recreates PVC with new storage class
  - Volsync handles data restoration

#### 4. Prometheus
- **Namespace:** observability
- **Current Storage:** cephfs-shared
- **Current Size:** 2x100Gi (200Gi total across 2 replicas)
- **Replicas:** 2 (StatefulSet)
- **Storage Pattern:** 🔧 **Direct HelmRelease** (`kubernetes/apps/observability/kube-prometheus-stack/app/helmrelease.yaml`)
- **Recommended:** Migrate to ceph-rbd
- **Why:** Time-series database with:
  - Heavy write workload (constant metric ingestion)
  - Random read patterns for queries
  - Significant performance gains with block storage
  - Better compaction performance
- **Impact:** HIGH - Largest performance improvement opportunity
- **Migration Complexity:** High
  - Large data volume (200Gi total)
  - Update HelmRelease volumeClaimTemplate.spec.storageClassName
  - Commit and push changes
  - Flux recreates StatefulSet with new storage
  - Consider data retention during migration

#### 5. Loki
- **Namespace:** observability
- **Current Storage:** cephfs-shared
- **Current Size:** 30Gi
- **Replicas:** 1 (StatefulSet)
- **Storage Pattern:** 🔧 **Direct HelmRelease** (`kubernetes/apps/observability/loki/app/helmrelease.yaml`)
- **Recommended:** Migrate to ceph-rbd
- **Why:** Log aggregation database benefits from:
  - Better write performance for high-volume log ingestion
  - Improved compaction and chunk management
  - Block storage better suited for LSM-tree based storage
- **Impact:** Medium - noticeable improvement in log write performance
- **Migration Complexity:** Medium
  - Moderate data size
  - Update HelmRelease singleBinary.persistence.storageClass
  - Commit and push changes
  - Flux recreates StatefulSet with new storage
  - Can tolerate some log loss during migration

#### 6. AlertManager
- **Namespace:** observability
- **Current Storage:** cephfs-shared
- **Current Size:** 2Gi
- **Replicas:** 1 (StatefulSet)
- **Storage Pattern:** 🔧 **Direct HelmRelease** (`kubernetes/apps/observability/kube-prometheus-stack/app/helmrelease.yaml`)
- **Recommended:** Migrate to ceph-rbd
- **Why:** Alert state persistence benefits from:
  - Consistent snapshot capabilities
  - Better fsync performance for state writes
- **Impact:** Low - small storage footprint, quick migration
- **Migration Complexity:** Low
  - Small data size
  - Update HelmRelease alertmanager.alertmanagerSpec.storage.volumeClaimTemplate.spec.storageClassName
  - Commit and push changes
  - Flux recreates StatefulSet with new storage
  - Minimal downtime

---

## What Should Stay on CephFS

The following workloads are correctly using CephFS and should NOT be migrated:

### Media & Shared Files (RWX Access Required)
- **Media libraries** (Plex, Sonarr, Radarr, etc.) - Need shared filesystem access
- **AI models** (Ollama 100Gi) - Large files with potential shared access
- **Application configs** - Often need shared access across pods

### Backup Storage
- **Volsync repositories** (cephfs-static) - Restic repositories work well on filesystem
- **MinIO data** (cephfs-static, 10Ti) - Object storage on filesystem is appropriate

### Other
- **OpenEBS etcd/minio** - Already using local PVs (mayastor-etcd-localpv, openebs-minio-localpv)
- **Runner work volumes** - Ephemeral workload storage

---

## Migration Summary

### Total Storage to Migrate
- **Dragonfly:** +30Gi (3 replicas x 10Gi) - NEW storage
- **EMQX:** +15-30Gi (3 replicas x 5-10Gi) - NEW storage
- **CouchDB:** 5Gi (migrate from cephfs)
- **Prometheus:** 200Gi (migrate from cephfs)
- **Loki:** 30Gi (migrate from cephfs)
- **AlertManager:** 2Gi (migrate from cephfs)

**Total New ceph-rbd Needed:** ~280-295Gi
**Currently Migrating from CephFS:** ~237Gi

### Recommended Migration Order

1. **Phase 0: Validation (Test the process)**
   - ✅ **AlertManager** - LOW RISK test case to validate GitOps workflow

2. **Phase 1: Data Durability (Immediate)**
   - Dragonfly - Add persistent storage
   - EMQX - Add persistent storage

3. **Phase 2: Small Databases (Quick Wins)**
   - CouchDB - Medium complexity, important for Obsidian data

4. **Phase 3: Large Time-Series DBs (Performance)**
   - Loki - Medium size, good performance gains
   - Prometheus - Large size, significant performance gains

---

## Migration Checklists

### Phase 0: AlertManager Migration (Validation Test)

**Goal:** Validate the GitOps migration workflow with a low-risk workload

**Pre-Migration Checklist:**
- [ ] Verify current AlertManager state
  ```bash
  kubectl get pod -n observability -l app.kubernetes.io/name=alertmanager
  kubectl get pvc -n observability -l app.kubernetes.io/name=alertmanager
  kubectl describe pvc -n observability alertmanager-kube-prometheus-stack-alertmanager-db-alertmanager-kube-prometheus-stack-alertmanager-0 | grep "StorageClass:"
  ```
- [ ] Check current storage usage
  ```bash
  kubectl exec -n observability alertmanager-kube-prometheus-stack-alertmanager-0 -- df -h /alertmanager
  ```
- [ ] Document current alerts (optional - state will rebuild)
  ```bash
  kubectl get prometheusrule -A
  ```
- [ ] Verify ceph-rbd storage class exists
  ```bash
  kubectl get storageclass ceph-rbd
  kubectl get volumesnapshotclass ceph-rbd-snapshot
  ```

**Migration Steps:**
- [ ] Create feature branch
  ```bash
  git checkout -b feat/alertmanager-rbd-migration
  ```
- [ ] Update HelmRelease configuration
  - File: `kubernetes/apps/observability/kube-prometheus-stack/app/helmrelease.yaml`
  - Change: `alertmanager.alertmanagerSpec.storage.volumeClaimTemplate.spec.storageClassName: ceph-rbd`
  - Line: ~104 (search for alertmanager storageClassName)
- [ ] Commit changes
  ```bash
  git add kubernetes/apps/observability/kube-prometheus-stack/app/helmrelease.yaml
  git commit -m "feat(alertmanager): migrate to ceph-rbd storage"
  ```
- [ ] Push to remote
  ```bash
  git push origin feat/alertmanager-rbd-migration
  ```
- [ ] Monitor Flux reconciliation
  ```bash
  flux reconcile kustomization kube-prometheus-stack -n observability --with-source
  watch kubectl get pods -n observability -l app.kubernetes.io/name=alertmanager
  ```
- [ ] Verify new PVC created with ceph-rbd
  ```bash
  kubectl get pvc -n observability -l app.kubernetes.io/name=alertmanager
  kubectl describe pvc -n observability <new-pvc-name> | grep "StorageClass:"
  ```
- [ ] Verify AlertManager is running
  ```bash
  kubectl get pod -n observability -l app.kubernetes.io/name=alertmanager
  kubectl logs -n observability -l app.kubernetes.io/name=alertmanager --tail=50
  ```
- [ ] Check AlertManager UI (https://alertmanager.${SECRET_DOMAIN})
  - [ ] UI loads successfully
  - [ ] Alerts are being received
  - [ ] Silences can be created
- [ ] Wait 24 hours to verify stability
- [ ] Merge to main
  ```bash
  git checkout main
  git merge feat/alertmanager-rbd-migration
  git push origin main
  ```

**Post-Migration Validation:**
- [ ] Verify old PVC is deleted (should happen automatically)
  ```bash
  kubectl get pvc -A | grep alertmanager
  ```
- [ ] Check Ceph RBD usage
  ```bash
  kubectl exec -n rook-ceph deploy/rook-ceph-tools -- ceph df
  ```
- [ ] Document lessons learned for larger migrations
- [ ] Update this checklist with any issues encountered

**Rollback Plan (if needed):**
- [ ] Revert the commit
  ```bash
  git revert HEAD
  git push origin main
  ```
- [ ] Flux will recreate AlertManager with cephfs-shared
- [ ] Alert state will rebuild (acceptable data loss)

---

## Migration Procedures

### Pattern 1: Volsync Component Apps (GitOps Workflow)

**Used for:** CouchDB, and any app using the volsync component

**Steps:**
1. **Update ks.yaml** - Add storage class overrides to `postBuild.substitute`:
   ```yaml
   postBuild:
     substitute:
       APP: obsidian-couchdb
       VOLSYNC_CAPACITY: 5Gi
       VOLSYNC_STORAGECLASS: ceph-rbd              # Changed from default
       VOLSYNC_ACCESSMODES: ReadWriteOnce          # Changed from ReadWriteMany
       VOLSYNC_SNAPSHOTCLASS: ceph-rbd-snapshot    # Changed from cephfs-snapshot
       VOLSYNC_CACHE_STORAGECLASS: ceph-rbd        # For volsync cache
       VOLSYNC_CACHE_ACCESSMODES: ReadWriteOnce    # For volsync cache
   ```

2. **Commit and push** changes to Git repository

3. **Flux reconciles automatically**:
   - Flux detects the change in Git
   - Recreates the PVC with new storage class
   - Volsync ReplicationDestination restores data from backup
   - Application pod starts with new RBD-backed storage

4. **Verify** the application is running correctly with new storage:
   ```bash
   kubectl get pvc -n <namespace> <app>
   kubectl describe pvc -n <namespace> <app> | grep StorageClass
   ```

**Example files:**
- CouchDB: `kubernetes/apps/selfhosted/obsidian-couchdb/ks.yaml`

---

### Pattern 2: Direct HelmRelease Apps (GitOps Workflow)

**Used for:** Prometheus, Loki, AlertManager

**Steps:**

#### For Prometheus & AlertManager:
1. **Update helmrelease.yaml** - Change storageClassName in volumeClaimTemplate:
   ```yaml
   # kubernetes/apps/observability/kube-prometheus-stack/app/helmrelease.yaml
   prometheus:
     prometheusSpec:
       storageSpec:
         volumeClaimTemplate:
           spec:
             storageClassName: ceph-rbd  # Changed from cephfs-shared
             resources:
               requests:
                 storage: 100Gi

   alertmanager:
     alertmanagerSpec:
       storage:
         volumeClaimTemplate:
           spec:
             storageClassName: ceph-rbd  # Changed from cephfs-shared
             resources:
               requests:
                 storage: 2Gi
   ```

2. **Commit and push** changes to Git repository

3. **Flux reconciles automatically**:
   - Flux detects the HelmRelease change
   - Helm recreates the StatefulSet
   - New PVCs created with ceph-rbd storage class
   - Pods start with new storage (data loss acceptable for metrics/alerts)

#### For Loki:
1. **Update helmrelease.yaml** - Change storageClass in persistence config:
   ```yaml
   # kubernetes/apps/observability/loki/app/helmrelease.yaml
   singleBinary:
     persistence:
       enabled: true
       storageClass: ceph-rbd  # Changed from cephfs-shared
       size: 30Gi
   ```

2. **Commit and push** changes to Git repository

3. **Flux reconciles automatically** - Same process as Prometheus

**Note:** For observability workloads, some data loss during migration is typically acceptable since:
- Prometheus has 14d retention - new data will accumulate
- Loki has 14d retention - new logs will accumulate
- AlertManager state is ephemeral and will rebuild

---

### For Services Without Storage (Dragonfly, EMQX)

**Steps:**
1. Update CRD to add volumeClaimTemplates with ceph-rbd
2. Commit and push changes
3. Flux recreates StatefulSet with persistent storage
4. Configure volsync backup strategy (optional)

---

## Important Migration Considerations

### Snapshot Class Compatibility

When migrating from CephFS to Ceph RBD, **snapshot classes must match the storage backend**:

| Storage Class | Compatible Snapshot Class |
|--------------|---------------------------|
| `cephfs-shared` | `cephfs-snapshot` |
| `ceph-rbd` | `ceph-rbd-snapshot` |

**Why this matters:**
- Volsync uses snapshots for backup/restore operations
- Using the wrong snapshot class will cause volsync to fail
- Both the main storage and cache storage need matching snapshot classes

**Available VolumeSnapshotClasses in cluster:**
```bash
$ kubectl get volumesnapshotclass
NAME                DRIVER                          DELETIONPOLICY
ceph-rbd-snapshot   rook-ceph.rbd.csi.ceph.com      Delete
cephfs-snapshot     rook-ceph.cephfs.csi.ceph.com   Delete
csi-nfs-snapclass   nfs.csi.k8s.io                  Delete
```

### Access Mode Changes

| Storage Type | Access Mode | Use Case |
|--------------|-------------|----------|
| CephFS (`cephfs-shared`) | ReadWriteMany (RWX) | Shared filesystems, media libraries |
| Ceph RBD (`ceph-rbd`) | ReadWriteOnce (RWO) | Databases, block storage |

**Impact:**
- RBD volumes can only be mounted by one node at a time
- Applications must be single-replica or use StatefulSet with pod affinity
- Most database workloads already use RWO - minimal impact

### Volsync Cache Storage

When using volsync with RBD, **both the main storage and cache storage should use RBD**:

```yaml
postBuild:
  substitute:
    # Main PVC settings
    VOLSYNC_STORAGECLASS: ceph-rbd
    VOLSYNC_ACCESSMODES: ReadWriteOnce
    VOLSYNC_SNAPSHOTCLASS: ceph-rbd-snapshot

    # Cache PVC settings (must also match RBD)
    VOLSYNC_CACHE_STORAGECLASS: ceph-rbd
    VOLSYNC_CACHE_ACCESSMODES: ReadWriteOnce
    VOLSYNC_CACHE_CAPACITY: 10Gi
```

**Why?** Mixing CephFS cache with RBD main storage can cause:
- Snapshot compatibility issues
- Performance inconsistencies
- Backup/restore failures

---

## Technical Notes

- **Ceph RBD Pool:** Backed by `rook-pvc-pool`
- **Storage Class:** `ceph-rbd`
- **Access Mode:** RWO (ReadWriteOnce) - single node access
- **Features:** Volume expansion enabled, snapshot support
- **Reclaim Policy:** Delete
- **CSI Driver:** `rook-ceph.rbd.csi.ceph.com`

## References

- Current cluster storage: `kubernetes/apps/storage/`
- Database configs: `kubernetes/apps/database/*/cluster/cluster.yaml`
- Storage class definition: Managed by Rook operator
