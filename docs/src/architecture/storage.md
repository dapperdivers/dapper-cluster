# Storage Architecture

> **Note (2025-12-01):** CephFS filesystem was recreated after a failed recovery. All CephFS data pools are empty. The cluster now uses three dedicated CephFS data pools: `cephfs_data`, `cephfs_media`, and `cephfs_backups`.

## Storage Overview

The Dapper Cluster uses Rook Ceph as its primary storage solution, providing unified storage for all Kubernetes workloads. The external Ceph cluster runs on Proxmox hosts and is connected to the Kubernetes cluster via Rook's external cluster mode.

```mermaid
graph TD
    subgraph External Ceph Cluster
        MON[Ceph Monitors]
        OSD[Ceph OSDs]
        MDS[Ceph MDS - CephFS]
    end

    subgraph Kubernetes Cluster
        ROOK[Rook Operator]
        CSI[Ceph CSI Drivers]
        SC[Storage Classes]
    end

    subgraph Applications
        APPS[Application Pods]
        PVC[Persistent Volume Claims]
    end

    MON --> ROOK
    ROOK --> CSI
    CSI --> SC
    SC --> PVC
    PVC --> APPS
    CSI --> MDS
    CSI --> OSD
```

## Storage Architecture Decision

### Why Rook Ceph?

The cluster migrated from OpenEBS Mayastor and various NFS backends to Rook Ceph for several key reasons:

1. **Unified Storage Platform**: Single storage solution for all workload types
2. **External Cluster Design**: Leverages existing Proxmox Ceph cluster infrastructure
3. **High Performance**: Direct Ceph integration without NFS overhead
4. **Scalability**: Native Ceph scalability for growing storage needs
5. **Feature Rich**: Snapshots, cloning, expansion, and advanced storage features
6. **ReadWriteMany Support**: CephFS provides shared filesystem access
7. **Production Proven**: Mature, widely-adopted storage solution

### Migration History

- **Previous**: OpenEBS Mayastor (block storage) + Unraid NFS backends (shared storage)
- **Current**: Rook Ceph with CephFS and RBD (unified storage platform)
- **In Progress**: Decommissioning Unraid servers (tower/tower-2) in favor of Ceph

## Current Storage Classes

### CephFS Shared Storage (Default)

**Storage Class**: `cephfs-shared`

Primary storage class for all workloads requiring dynamic provisioning.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: cephfs-shared
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: rook-ceph.cephfs.csi.ceph.com
parameters:
  clusterID: rook-ceph
  fsName: cephfs
  pool: cephfs_data
allowVolumeExpansion: true
reclaimPolicy: Delete
volumeBindingMode: Immediate
```

**Characteristics**:
- **Access Mode**: ReadWriteMany (RWX) - Multiple pods can read/write simultaneously
- **Use Cases**:
  - Applications requiring shared storage
  - Media applications
  - Backup repositories (VolSync)
  - Configuration storage
  - General application storage
- **Performance**: Good performance for most workloads, shared filesystem overhead
- **Default**: Yes - all PVCs without explicit storageClassName use this

### CephFS Static Storage

**Storage Class**: `cephfs-static`

Used for pre-existing CephFS paths that need to be mounted into Kubernetes.

**Characteristics**:
- **Access Mode**: ReadWriteMany (RWX)
- **Use Cases**:
  - Mounting existing data directories (e.g., `/truenas/*` paths)
  - Large media libraries
  - Shared configuration repositories
  - Data migration scenarios
- **Provisioning**: Manual - requires creating both PV and PVC
- **Pattern**: See "Static PV Pattern" section below

**Example**: Media storage at `/media` on cephfs_media pool
```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: media-cephfs-pv
spec:
  capacity:
    storage: 100Ti
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: cephfs-static
  csi:
    driver: rook-ceph.cephfs.csi.ceph.com
    nodeStageSecretRef:
      name: rook-csi-cephfs-static
      namespace: rook-ceph
    volumeAttributes:
      clusterID: rook-ceph
      fsName: cephfs
      staticVolume: "true"
      rootPath: /media
      pool: cephfs_media
      mounter: kernel
```

### RBD Block Storage

**Storage Classes**: `ceph-rbd`, `ceph-bulk`

High-performance block storage using Ceph RADOS Block Devices.

**Characteristics**:
- **Access Mode**: ReadWriteOnce (RWO) - Single pod exclusive access
- **Performance**: Superior to CephFS for block workloads (databases, etc.)
- **Thin Provisioning**: Efficient storage allocation
- **Features**: Snapshots, clones, fast resizing

**Use Cases**:
- PostgreSQL and other databases
- Stateful applications requiring block storage
- Applications needing high IOPS
- Workloads migrating from OpenEBS Mayastor

**Storage Classes**:
- `ceph-rbd`: General-purpose RBD storage
- `ceph-bulk`: Erasure-coded pool for large, less-critical data

### Legacy Unraid NFS Storage (Being Decommissioned)

**Storage Class**: `used-nfs` (no storage class for static tower/tower-2 PVs)

Legacy NFS storage from Unraid servers, currently being migrated to Ceph.

**Servers**:
- `tower.manor` - Primary Unraid server (100Ti NFS) - **Decommissioning**
- `tower-2.manor` - Secondary Unraid server (100Ti NFS) - **Decommissioning**

**Current Status**:
- Some media applications still use hybrid approach during migration
- Active data migration to CephFS in progress
- Will be fully retired once migration complete

**Migration Plan**: All workloads being moved to Ceph (CephFS or RBD as appropriate)

## Storage Provisioning Patterns

### Dynamic Provisioning (Default)

For most applications, simply create a PVC and Kubernetes will automatically provision storage:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-app-data
  namespace: my-namespace
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 10Gi
  # No storageClassName specified = uses default (cephfs-shared)
```

### Static PV Pattern

For mounting pre-existing CephFS paths:

**Step 1**: Create PersistentVolume
```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: my-static-pv
spec:
  capacity:
    storage: 5Ti
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: cephfs-static
  csi:
    driver: rook-ceph.cephfs.csi.ceph.com
    nodeStageSecretRef:
      name: rook-csi-cephfs-static
      namespace: rook-ceph
    volumeAttributes:
      clusterID: rook-ceph
      fsName: cephfs
      staticVolume: "true"
      rootPath: /my-data  # Path in CephFS
      pool: cephfs_data   # Target data pool
      mounter: kernel     # Kernel mounter for better performance
```

**Step 2**: Create matching PersistentVolumeClaim
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-static-pvc
  namespace: my-namespace
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 5Ti
  storageClassName: cephfs-static
  volumeName: my-static-pv
```

**Current Static PVs in Use**:
- `media-cephfs-pv` → `/media` on cephfs_media pool (100Ti)
- `minio-cephfs-pv` → `/minio` on cephfs_data pool (10Ti)
- `paperless-cephfs-pv` → `/paperless` on cephfs_data pool (5Ti)

## Storage Decision Matrix

| Workload Type | Storage Class | Access Mode | Rationale |
|---------------|---------------|-------------|-----------|
| Databases (PostgreSQL, etc.) | `ceph-rbd` | RWO | Best performance for block storage workloads |
| Media Libraries | `cephfs-static` or `cephfs-shared` | RWX | Shared access for media servers |
| Media Downloads | `cephfs-shared` | RWX | Multi-pod write access |
| Application Data (single pod) | `ceph-rbd` | RWO | High performance block storage |
| Application Data (multi-pod) | `cephfs-shared` | RWX | Concurrent access required |
| Backup Repositories | `cephfs-shared` | RWX | VolSync requires RWX |
| Shared Config | `cephfs-shared` | RWX | Multiple pods need access |
| Bulk Storage | `ceph-bulk` or `cephfs-static` | RWO/RWX | Large datasets, erasure coding |
| Legacy Apps (during migration) | `used-nfs` | RWX | Temporary until Unraid decom complete |

## Backup Strategy

### VolSync with CephFS

All persistent data is backed up using VolSync, which now uses CephFS for its repository storage:

- **Backup Frequency**: Hourly snapshots via ReplicationSource
- **Repository Storage**: CephFS PVC (migrated from NFS)
- **Backend**: Restic repositories on CephFS
- **Retention**: Configurable per-application
- **Recovery**: Supports restore to same or different PVC

**VolSync Repository Location**: `/repository/{APP}` on CephFS

## Network Configuration

### Ceph Networks

The external Ceph cluster uses two networks:

- **Public Network**: 10.150.0.0/24
  - Client connections from Kubernetes
  - Ceph monitor communication
  - Used by CSI drivers
- **Cluster Network**: 10.200.0.0/24
  - OSD-to-OSD replication
  - Not directly accessed by Kubernetes

### Connection Method

Kubernetes connects to Ceph via:
1. **Rook Operator**: Manages connection to external cluster
2. **CSI Drivers**: cephfs.csi.ceph.com for CephFS volumes
3. **Mon Endpoints**: ConfigMap with Ceph monitor addresses
4. **Authentication**: Ceph client.kubernetes credentials

## Performance Characteristics

### CephFS Performance

- **Sequential Read**: Excellent (limited by network, ~10 Gbps)
- **Sequential Write**: Very Good (COW overhead, CRUSH rebalancing)
- **Random I/O**: Good (shared filesystem overhead)
- **Concurrent Access**: Excellent (native RWX support)
- **Metadata Operations**: Good (dedicated MDS servers)

### Optimization Tips

1. **Use RWO when possible**: Even on CephFS, specify RWO if no sharing needed
2. **Size appropriately**: CephFS handles small and large files well
3. **Monitor MDS health**: CephFS performance depends on MDS responsiveness
4. **Enable client caching**: Default CSI settings enable attribute caching

## Storage Operations

### Common Operations

**Expand a PVC**:
```bash
kubectl patch pvc my-pvc -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
```

**Check storage usage**:
```bash
kubectl get pvc -A
kubectl exec -it <pod> -- df -h
```

**Monitor Ceph cluster health**:
```bash
kubectl -n rook-ceph get cephcluster
kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph status
```

**List CephFS mounts**:
```bash
kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph fs status
```

### Troubleshooting

**PVC stuck in Pending**:
```bash
kubectl describe pvc <pvc-name>
kubectl -n rook-ceph logs -l app=rook-ceph-operator
```

**Slow performance**:
```bash
# Check Ceph cluster health
kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph health detail

# Check MDS status
kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph fs status

# Check OSD performance
kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph osd perf
```

**Mount issues**:
```bash
# Check CSI driver logs
kubectl -n rook-ceph logs -l app=csi-cephfsplugin

# Verify connection to monitors
kubectl -n rook-ceph get configmap rook-ceph-mon-endpoints -o yaml
```

## Current Migration Status

### Completed
- ✅ RBD storage classes implemented and available
- ✅ CephFS as default storage class
- ✅ VolSync migrated to CephFS backend
- ✅ Static PV pattern established for existing data
- ✅ Migrated from OpenEBS Mayastor to Ceph RBD

### In Progress
- 🔄 Decommissioning Unraid NFS servers (tower/tower-2)
- 🔄 Migrating remaining media workloads from NFS to CephFS
- 🔄 Consolidating all storage onto Ceph platform

### Future Enhancements
- 📋 Additional RBD pool with SSD backing for critical workloads
- 📋 Erasure coding optimization for bulk media storage
- 📋 Advanced snapshot scheduling and retention policies
- 📋 Ceph performance tuning and optimization

## Best Practices

### Storage Selection

1. **Databases and single-pod apps**: Use `ceph-rbd` for best performance
2. **Shared storage needs**: Use `cephfs-shared` for RWX access
3. **Use static PVs for existing data**: Don't duplicate large datasets
4. **Specify requests accurately**: Helps with capacity planning
5. **Choose appropriate access modes**: RWO for RBD, RWX for CephFS

### Capacity Planning

1. **Monitor Ceph cluster capacity**:
   ```bash
   kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph df
   ```
2. **Set appropriate PVC sizes**: CephFS supports expansion
3. **Plan for growth**: Ceph cluster can scale by adding OSDs
4. **Regular capacity reviews**: Check usage trends

### Data Protection

1. **Enable VolSync**: For all stateful applications
2. **Test restores regularly**: Ensure backup viability
3. **Monitor backup success**: Check ReplicationSource status
4. **Retain snapshots appropriately**: Balance storage cost vs recovery needs

### Security

1. **Use namespace isolation**: PVCs are namespace-scoped
2. **Limit access with RBAC**: Control who can create PVCs
3. **Monitor access patterns**: Unusual I/O may indicate issues
4. **Rotate Ceph credentials**: Periodically update client keys

## Monitoring and Observability

### Key Metrics

Monitor these metrics via Prometheus/Grafana:

- Ceph cluster health status
- OSD utilization and performance
- MDS cache hit rates
- PVC capacity usage
- CSI operation latencies
- VolSync backup success rates

### Alerts

Critical alerts configured:

- Ceph cluster health warnings
- High OSD utilization (>80%)
- MDS performance degradation
- PVC approaching capacity
- VolSync backup failures

## References

- **Rook Documentation**: [rook.io/docs](https://rook.io/docs/rook/latest/)
- **Ceph Documentation**: [docs.ceph.com](https://docs.ceph.com/)
- **Local Setup**: `kubernetes/apps/rook-ceph/README.md`
- **Storage Classes**: `kubernetes/apps/rook-ceph/rook-ceph-cluster/app/storageclasses.yaml`
