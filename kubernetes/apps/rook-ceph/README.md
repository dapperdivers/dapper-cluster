# Rook Ceph External Cluster

This directory contains the configuration for connecting Kubernetes to an external Ceph cluster running on Proxmox hosts.

## Overview

**Status**: ✅ PRODUCTION

This configuration connects the Kubernetes cluster to an external Ceph 18.2.7 (Reef) cluster via Rook v1.18.6 in external mode. Both RBD and CephFS storage drivers are active and operational.

### External Ceph Cluster
- **Version**: Ceph 18.2.7 (Reef)
- **Location**: Proxmox hosts (10.150.0.0/24)
- **Monitors**: proxmox-02, proxmox-03, proxmox-04
- **Connection**: External cluster mode (no Ceph daemons in Kubernetes)

### Rook Configuration
- **Rook Version**: v1.18.6
- **Operator**: Deployed via Helm
- **CSI Drivers**: Both RBD and CephFS enabled
- **Default Storage Class**: `ceph-rbd` (RBD)

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
│       └── helmrelease.yaml          # Rook operator Helm release (v1.18.6)
└── rook-ceph-cluster/                # External cluster configuration
    ├── ks.yaml                       # Flux Kustomization
    └── app/
        ├── kustomization.yaml
        ├── configmap.yaml            # Mon endpoints and cluster info
        ├── secret.sops.yaml          # Ceph credentials (SOPS encrypted)
        ├── cluster-external.yaml     # CephCluster CR (external mode)
        ├── storageclasses.yaml       # Storage classes and snapshot classes
        └── toolbox.yaml              # Ceph toolbox deployment
```

## Storage Classes

### Active Storage Classes
| Class Name | Pool | Type | Default | Use Case |
|------------|------|------|---------|----------|
| `ceph-rbd` | rook-pvc-pool | RBD (RWO) | ✅ Yes | General application storage (default) |
| `cephfs-shared` | cephfs_data | CephFS (RWX) | No | Shared storage, multi-pod access |
| `cephfs-backups` | k8s-backups | CephFS (RWX) | No | Backups with Retain reclaim policy |

**Snapshot Classes**:
- `ceph-rbd-snapshot` - RBD snapshots with Delete retention
- `cephfs-snapshot` - CephFS snapshots with Delete retention

### Planned Storage Classes
| Class Name | Pool | Type | Use Case |
|------------|------|------|----------|
| `ceph-ssd-critical` | ssd-db | RBD | Databases, etcd, critical apps (when pool created) |
| `ceph-bulk` | media-bulk | RBD (EC) | Media, backups, large files (when pool created) |

## Network

- **Ceph Public Network**: 10.150.0.0/24 - Client connections to monitors and OSDs
- **Ceph Storage Network**: 10.200.0.0/24 - OSD replication (not used by Kubernetes)
- **Kubernetes Access**: Via CSI drivers (RBD and CephFS)

## Documentation

### Setup & Deployment
- **📋 Quick Start**: `docs/rook-phase1-quickstart.md` - Initial deployment guide
- **📖 Deployment Steps**: `docs/rook-deployment-steps.md` - Detailed step-by-step guide
- **🔧 Complete Setup**: `docs/rook-external-ceph-setup.md` - Full documentation with troubleshooting

### Migration & History
- **🚀 RBD Integration**: `docs/rook-phase2-migration.md` - RBD driver migration guide
- **📜 Migration History**: Migrated from OpenEBS Mayastor → CephFS → CephFS + RBD

## Operations

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

# Check all PVCs using RBD
kubectl get pvc -A -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,STORAGECLASS:.spec.storageClassName | grep ceph-rbd
```

## Operational Notes

### CSI Timeout Configuration for External Clusters

**Background**: External Ceph clusters have higher network latency compared to in-cluster Ceph. The default CSI timeout of 150 seconds (2.5 minutes) is insufficient for snapshot operations and can cause failures.

**Current Configuration**: ✅ Fully GitOps-Managed

The HelmRelease configuration sets `grpcTimeoutInSeconds: 600` which applies **10-minute timeouts** to all CSI sidecar containers:
- ✅ RBD provisioner sidecars: `--timeout=10m0s`
- ✅ CephFS provisioner sidecars: `--timeout=10m0s`
- ✅ Kubernetes API rate limits: 100 QPS, 200 burst (increased for snapshot operations)

**Verification**:
```bash
# Verify CSI timeout configuration
kubectl -n rook-ceph get deployment csi-rbdplugin-provisioner -o yaml | grep "timeout="
kubectl -n rook-ceph get deployment csi-cephfsplugin-provisioner -o yaml | grep "timeout="
# Should show: --timeout=10m0s
```

**No manual patches required** - all timeout configuration is managed via the HelmRelease in `rook-ceph-operator/app/helmrelease.yaml`.

**Reference**: See `docs/troubleshooting/2025-10-30-rook-version-comparison-analysis.md` for historical context on timeout issues.
