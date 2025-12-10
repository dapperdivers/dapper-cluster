# VolSync Component

Two-phase component for automatic backup and restore using VolSync + Restic.

## Usage

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: prowlarr
  namespace: media
spec:
  components:
    - ../../../../flux/components/volsync/repository
    - ../../../../flux/components/volsync/operations
  wait: true
  timeout: 10m
  postBuild:
    substitute:
      APP: prowlarr
      VOLSYNC_CAPACITY: 5Gi
```

## Required Variables

```yaml
APP: <app-name>               # Application name
VOLSYNC_CAPACITY: <size>      # PVC size (e.g., 5Gi)
```

## Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VOLSYNC_STORAGECLASS` | `ceph-rbd` | App PVC storage class |
| `VOLSYNC_SNAPSHOTCLASS` | `ceph-rbd-snapshot` | Snapshot class |
| `VOLSYNC_CACHE_STORAGECLASS` | `ceph-rbd` | Cache PVC storage class |
| `VOLSYNC_CACHE_CAPACITY` | `10Gi` | Cache size |
| `VOLSYNC_COPYMETHOD` | `Snapshot` | Copy method |
| `VOLSYNC_ACCESSMODES` | `ReadWriteOnce` | App PVC access mode |
| `VOLSYNC_SCHEDULE` | `0 * * * *` | Local backup schedule |
| `VOLSYNC_PUID` | `1000` | Mover pod user ID |
| `VOLSYNC_PGID` | `150` | Mover pod group ID |

## Architecture

### Phase 1: Repository
Creates CephFS repository at `/k8s-backups/volsync/${APP}` for storing Restic backups.

### Phase 2: Operations
- **ReplicationDestination**: Restores from backup on first deployment
- **App PVC**: Uses `dataSourceRef` to restore from snapshot
- **Local ReplicationSource**: Hourly backups to CephFS (24h + 7d retention)
- **Remote ReplicationSource**: Daily backups to Cloudflare R2 (7d retention)

## Storage Classes

| Resource | Storage Class | Pool | Type |
|----------|---------------|------|------|
| Repository | `cephfs-static` | cephfs_backups | CephFS RWX (static PV) |
| App PVC | `ceph-rbd` | rook-pvc-pool | RBD RWO |
| Cache | `ceph-rbd` | rook-pvc-pool | RBD RWO |
| Snapshots | `ceph-rbd-snapshot` | - | RBD |

## Troubleshooting

```bash
# Check repository PVC
kubectl get pvc -n <namespace> volsync-<app>-repo

# Check restore status
kubectl get replicationdestination -n <namespace> <app>-dst -o yaml

# View mover logs
kubectl logs -n <namespace> -l volsync.backube/replicationdestination=<app>-dst
```
