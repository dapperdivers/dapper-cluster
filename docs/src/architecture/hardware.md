## 1. Server Nodes

### Proxmox-01 (CSE-846) - Primary Storage Node

- **Proxmox Version**: 8.4.1
- **Chassis**: Supermicro CSE-846 (24x 3.5" bays)
- **Motherboard**: X9SCL/X9SCM v1.11A
- **Backplane**: BPN-SAS2-846EL1
- **CPU**: Intel Xeon E3-1230 V2 @ 3.30GHz (4 cores + HT)
- **RAM**: 16 GiB
- **Power**: PWS-920P-SQ (920W 80+ Platinum)
- **Network**: 2x1Gbe, 2x 10GbE, 2x 40Gbe
- **OS Drive**: 2x120GB ZFS mirror

### Proxmox-02 (CSE-826) - Storage Node

- **Proxmox Version**: 8.4.1
- **Chassis**: Supermicro CSE-826 (12x 3.5" bays)
- **Motherboard**: X8DT6-F-EM09B
- **CPU**: 2x Intel Xeon X5680 @ 3.33GHz (24 cores total)
- **RAM**: 196 GiB
- **Network**: 2x1Gbe, 2x 10GbE, 2x 40Gbe
- **OS Drive**: 2x120GB ZFS mirror

### Proxmox-03 (ESC4000 G3) - GPU Compute Node

- **Proxmox Version**: 8.4.1
- **Chassis**: ASUS ESC4000 G3 (8x 3.5" bays)
- **CPU**: 2x Intel Xeon E5-2697A v4 @ 2.60GHz (64 cores total)
- **RAM**: 516 GiB
- **GPU**: 2x NVIDIA P100 16GB
- **Network**: 2x1Gbe, 2x 10GbE, 2x 40Gbe
- **OS Drive**: 2x120GB ZFS mirror

### Proxmox-04 (CSE-826) - Storage Node

- **Proxmox Version**: 8.4.1
- **Chassis**: Supermicro CSE-826 (12x 3.5" bays)
- **Motherboard**: X8DT6-F-EM09B
- **CPU**: 2x Intel Xeon X5680 @ 3.33GHz (24 cores total)
- **RAM**: 196 GiB
- **Network**: 2x1Gbe, 2x 10GbE, 2x 40Gbe
- **OS Drive**: 2x120GB ZFS mirror

### JBOD Shelf

- **Model**: SuperMicro 847E16-RJBOD1
- **Capacity**: 45 bays (3.5")
- **Interface**: 4x SAS ports (SFF-8088)
- **Power**: Dual PSU
- **Expanders**: Dual SAS expanders
- **Current Drives**: 18x 10TB, 1x 3.84TB PM883, 1x 800GB
- **Connections**:
  - Ports 1&2 → Proxmox-01 (via LSI 9207-8E)
  - Ports 3&4 → Proxmox-04 (via LSI 9207-8E)

---

## 2. Storage System (Current)

All drives are pooled into a single **Ceph 18.2.x (Reef)** cluster that runs directly on the Proxmox hosts (no Unraid/NFS VMs). Kubernetes consumes it through Rook in external-cluster mode (RBD + CephFS CSI).

- **Monitors**: proxmox-02, proxmox-03, proxmox-04
- **OSDs**: HDDs and SSDs across all four Proxmox hosts and the JBOD shelf (see drive inventory below)
- **Public network**: 10.150.0.0/24 (client/CSI traffic)
- **Cluster network**: 10.200.0.0/24 (OSD replication, dedicated 40Gb, VLAN 200)

---

## 3. Drive Inventory

These physical drives are the Ceph OSD backing store.

### Current Drive Distribution

| Location   | Drive Config                          | Count  | Raw Total    |
| ---------- | ------------------------------------- | ------ | ------------ |
| Proxmox-01 | 24x 4TB                               | 24     | 96TB         |
| Proxmox-03 | 3x 4TB + 7x 10TB + 2x 12TB            | 12     | 106TB        |
| Proxmox-04 | 1x 800GB + 1x 3.84TB PM883 + 8x 10TB  | 10     | 84.64TB      |
| Proxmox-03 | 1x 3.92TB SSD + 1x 800GB              | 2      | 4.72TB       |
| JBOD Shelf | 18x 10TB + 1x 3.84TB PM883 + 1x 800GB | 20     | 184.64TB     |
| Various    | 8x 120GB SSD (OS drives)              | 8      | 0.96TB       |
| **Total**  | -                                     | **76** | **476.96TB** |
