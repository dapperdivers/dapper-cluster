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

### Phase 1: Initial Connection & Mayastor Migration ✅ COMPLETED
**Goal**: Connect to external Ceph, migrate workloads from OpenEBS Mayastor to CephFS

**Status**: ✅ PRODUCTION - Migration Complete
- ✅ ConfigMap configured (mon endpoints, FSID)
- ✅ CephFS storage class configured (default storage class)
- ✅ Rook operator configured (CephFS driver enabled)
- ✅ Ceph credentials configured and working
- ✅ Static PVs deployed (media, minio, paperless)
- ✅ VolSync migrated to CephFS backend
- ✅ Workloads migrated from Mayastor to CephFS

**Current Setup**:
- CephFS is the primary storage solution
- RBD driver disabled (Phase 2 future work)
- RBD storage classes commented out (Phase 2)

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

## Operations - Phase 1 (Production)

### Verify Cluster Health
```bash
# Check CephCluster resource
kubectl -n rook-ceph get cephcluster

# Check Ceph health via toolbox
kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph status

# Check CephFS status
kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph fs status

# List storage classes
kubectl get sc
```

### Monitor Storage
```bash
# Check Ceph capacity
kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph df

# Check OSD status
kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph osd tree

# Check MDS performance
kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph fs status cephfs
```

### Common Operations
```bash
# Expand a PVC
kubectl patch pvc <pvc-name> -n <namespace> -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'

# Check all PVCs using CephFS
kubectl get pvc -A -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,STORAGECLASS:.spec.storageClassName | grep cephfs
```
