# Rook Ceph External Cluster

This directory contains the configuration for connecting Kubernetes to the external Ceph cluster running on Proxmox hosts.

## Structure

```
rook-ceph/
├── README.md                          # This file
├── kustomization.yaml                 # Main kustomization
├── rook-ceph-operator/               # Rook operator deployment
│   ├── ks.yaml                       # Flux Kustomization
│   └── app/
│       ├── kustomization.yaml
│       ├── namespace.yaml            # rook-ceph namespace
│       └── helmrelease.yaml          # Rook operator Helm release
└── rook-ceph-cluster/                # External cluster configuration
    ├── ks.yaml                       # Flux Kustomization
    └── app/
        ├── kustomization.yaml
        ├── configmap.yaml            # Mon endpoints (NEEDS CONFIGURATION)
        ├── secret.sops.yaml          # Ceph credentials (NEEDS CONFIGURATION)
        ├── cluster-external.yaml     # CephCluster CR
        └── storageclasses.yaml       # Storage classes

```

## Project Phases

### Phase 1: Initial Connection & Mayastor Migration (Current)
**Goal**: Connect to external Ceph, migrate workloads from OpenEBS Mayastor to CephFS

**Status**:
- ✅ ConfigMap configured (mon endpoints, FSID)
- ✅ CephFS storage class configured
- ✅ Rook operator configured (CephFS driver only)
- ⚠️ Secret needs Ceph credentials

**Current Setup**:
- Only CephFS filesystem available
- RBD driver disabled (Phase 2)
- RBD storage classes commented out

### Phase 2: Optimized Pool Creation (Future)
After hardware migration from Mayastor:
1. Create RBD pools (ssd-db, rook-pvc-pool, media-bulk)
2. Enable RBD driver in operator
3. Uncomment RBD storage classes
4. Update client.kubernetes permissions
5. Migrate workloads to optimized pools

## Storage Classes

### Phase 1 (Active)
| Class Name | Type | Use Case |
|------------|------|----------|
| `cephfs-shared` | CephFS (RWX) | All workloads during Mayastor migration |

### Phase 2 (Future - After Pool Creation)
| Class Name | Pool | Type | Use Case |
|------------|------|------|----------|
| `ceph-ssd-critical` | ssd-db | RBD | Databases, etcd, critical apps |
| `ceph-rbd` | rook-pvc-pool | RBD | General application storage |
| `ceph-bulk` | media-bulk | RBD (EC) | Media, backups, large files |

## Network

- **Ceph Public Network**: 10.150.0.0/24 - Client connections
- **Ceph Storage Network**: 10.200.0.0/24 - OSD replication (not used by K8s)

## Documentation

### Phase 1 (Current)
- **📋 Quick Start**: `docs/rook-phase1-quickstart.md` - **START HERE** for deployment
- **📖 Deployment Steps**: `docs/rook-deployment-steps.md` - Detailed step-by-step guide
- **🔧 Complete Setup**: `docs/rook-external-ceph-setup.md` - Full documentation with troubleshooting

### Phase 2 (Future)
- **🚀 Migration Guide**: `docs/rook-phase2-migration.md` - Pool optimization and RBD migration

## Next Steps - Phase 1

### On Proxmox Ceph Cluster:
1. Create `client.kubernetes` user with CephFS permissions:
   ```bash
   ceph auth get-or-create client.kubernetes \
     mon 'allow r' \
     osd 'allow rw pool=cephfs_data, allow rw pool=cephfs_metadata' \
     mds 'allow rw' \
     -o /etc/ceph/ceph.client.kubernetes.keyring
   ```
2. Get the key: `ceph auth get-key client.kubernetes`
   - Save this key! You'll use it for ALL secret fields

### In This Repository:
1. Fill in **4 instances** of the same key in `rook-ceph-cluster/app/secret.sops.yaml`:
   - `admin-secret`: your-key-here
   - `mon-secret`: your-key-here (same key)
   - `adminKey` in rook-csi-cephfs-provisioner: your-key-here
   - `adminKey` in rook-csi-cephfs-node: your-key-here
2. Encrypt: `sops -e -i kubernetes/apps/rook-ceph/rook-ceph-cluster/app/secret.sops.yaml`
3. Commit and push to deploy via Flux
4. Verify connection: `kubectl -n rook-ceph get cephcluster`
5. Test with CephFS PVC

### Migration from Mayastor:
After Rook is deployed, migrate workloads to `cephfs-shared` storage class to free up Mayastor hardware.
