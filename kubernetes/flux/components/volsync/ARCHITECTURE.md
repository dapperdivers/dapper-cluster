# VolSync Architecture

This document illustrates the PVC and snapshot lifecycle for VolSync two-phase backups.

## Component Flow

```mermaid
graph TB
    subgraph "Phase 1: Repository"
        RepoPV["PV: volsync-prowlarr-repo-pv<br/>(CephFS @ /volsync/prowlarr)<br/>Storage: cephfs-static"]
        RepoPVC["PVC: volsync-prowlarr-repo<br/>(5Ti RWX)<br/>Storage: cephfs-static"]
        RepoPV -->|binds to| RepoPVC
    end

    subgraph "Phase 2: Operations - Restore"
        RD["ReplicationDestination: prowlarr-dst<br/>(trigger: restore-once)"]

        CachePVC["PVC: volsync-dst-prowlarr-dst-cache<br/>(10Gi RWO)<br/>Storage: ceph-rbd<br/>Status: Bound → Deleted"]

        DestPVC["PVC: volsync-prowlarr-dst-dest<br/>(5Gi RWO)<br/>Storage: ceph-rbd<br/>Status: Bound → Terminating"]

        MoverPod["Mover Pod: volsync-dst-prowlarr-dst-*<br/>(Restic restore from repo)"]

        Snapshot["VolumeSnapshot:<br/>volsync-prowlarr-dst-dest-20251110210918<br/>Class: ceph-rbd-snapshot<br/>Status: readyToUse=false → true"]

        RD -->|creates| CachePVC
        RD -->|creates| DestPVC
        RD -->|schedules| MoverPod
        MoverPod -->|mounts| RepoPVC
        MoverPod -->|mounts| CachePVC
        MoverPod -->|restores data to| DestPVC
        DestPVC -->|creates snapshot| Snapshot
        Snapshot -->|cleanup after ready| DestPVC
        Snapshot -->|cleanup after ready| CachePVC
    end

    subgraph "Phase 2: Operations - App PVC"
        AppPVC["PVC: prowlarr<br/>(5Gi RWO)<br/>Storage: ceph-rbd<br/>Status: Pending"]

        Snapshot -->|dataSourceRef| AppPVC

        AppPVC -->|once bound| ProwlarrPod["Prowlarr Pod<br/>(uses restored data)"]
    end

    subgraph "Phase 2: Operations - Ongoing Backups"
        LocalRS["ReplicationSource: prowlarr-local<br/>(hourly @ 0 * * * *)"]
        RemoteRS["ReplicationSource: prowlarr-remote<br/>(daily @ 0 0 * * *)"]

        AppPVC -->|snapshot source| LocalRS
        AppPVC -->|snapshot source| RemoteRS

        LocalRS -->|backs up to| RepoPVC
        RemoteRS -->|backs up to| R2["Cloudflare R2<br/>(off-site)"]
    end

    style RepoPV fill:#e1f5fe
    style RepoPVC fill:#e1f5fe
    style DestPVC fill:#fff9c4
    style CachePVC fill:#fff9c4
    style Snapshot fill:#f3e5f5
    style AppPVC fill:#c8e6c9
    style MoverPod fill:#ffe0b2
```

## Lifecycle Phases

### Phase 1: Repository Setup
1. **PV Created**: Static CephFS PV points to `/volsync/${APP}` on cephfs_backups pool
2. **PVC Binds**: Repository PVC binds to PV using `cephfs-static` storage class

### Phase 2: One-Time Restore (on first deployment)
1. **ReplicationDestination Created**: With `trigger: restore-once`
2. **Temporary PVCs Created**:
   - Cache PVC (10Gi, for Restic cache)
   - Dest PVC (matches app size, receives restored data)
3. **Mover Pod Runs**: Mounts repo + cache + dest, runs Restic restore
4. **Snapshot Created**: VolumeSnapshot taken from dest PVC
5. **Cleanup**: Cache and dest PVCs deleted after snapshot ready

### Phase 2: App PVC Provisioning
1. **App PVC Created**: References snapshot via `dataSourceRef`
2. **CSI Provisions**: Creates new PV from snapshot data
3. **App Pod Starts**: Mounts PVC with restored data

### Phase 2: Ongoing Backups
1. **Local ReplicationSource**: Hourly snapshots → CephFS repo (24h + 7d retention)
2. **Remote ReplicationSource**: Daily backups → Cloudflare R2 (7d retention)

## Storage Classes

| Resource | Storage Class | Pool | Type | Access Mode |
|----------|---------------|------|------|-------------|
| Repository | `cephfs-static` | cephfs_backups | CephFS (static) | RWX |
| App PVC | `ceph-rbd` | rook-pvc-pool | RBD | RWO |
| Cache | `ceph-rbd` | rook-pvc-pool | RBD | RWO |
| Dest | `ceph-rbd` | rook-pvc-pool | RBD | RWO |
| Snapshots | `ceph-rbd-snapshot` | - | RBD Snapshot | - |

## Troubleshooting

### Snapshot Stuck at readyToUse: false
- Check if source PVC is terminating: `kubectl get pvc -n <namespace>`
- Check snapshot-controller logs: `kubectl logs -n kube-system -l app=snapshot-controller`
- Verify snapshot content exists: `kubectl get volumesnapshotcontent`

### App PVC Pending
- Verify snapshot is ready: `kubectl get volumesnapshot -n <namespace>`
- Check CSI provisioner logs: `kubectl logs -n rook-ceph -l app=csi-rbdplugin-provisioner -c csi-provisioner`

### Restore Failed
- Check mover pod logs: `kubectl logs -n <namespace> -l volsync.backube/replicationdestination=<app>-dst`
- Verify repository PVC is bound: `kubectl get pvc -n <namespace> volsync-<app>-repo`
