# Network Information Gathering - STAGING

This document serves as the main index for network configuration gathering. The information has been split into manageable sections for easier navigation and completion.

## 📊 Status Overview

**✅ Pre-Filled Information:**
- All Proxmox host management IPs (192.168.1.62-66)
- All IPMI IPs (192.168.1.162-165)
- Proxmox hostnames (Proxmox-01 through Proxmox-04)
- Ceph monitor IPs (10.150.0.2, 10.150.0.4)
- VM to host mapping
- OPNsense details (model, IP, WAN interface)
- Mikrotik CSS326 switch details
- Brocade and Arista basic system info

**⚠️ Still Needed:**
- VLAN 200 (Ceph cluster) IPs for Proxmox hosts (not yet configured)
- Complete Brocade port assignments and descriptions
- Complete Arista port assignments
- Brocade VLAN interface IPs for VLAN 150/200 (if configured)
- Static routing configuration on Brocade

---

## 📂 Staging Documents

Work on each section independently by opening the appropriate file:

### 🔧 [Brocade ICX6610 (192.168.1.20)](./network-staging-brocade.md)

**Size:** 699 lines

Commands and outputs for:
- System information and version
- VLAN configuration
- VLAN interfaces (SVIs) and IPs
- Port descriptions and assignments
- LAG configuration
- Routing table
- Interface statistics

**Key Tasks:**
- [ ] Complete port descriptions
- [ ] Document LAG configurations
- [ ] Capture VLAN interface IPs (ve 150, ve 200)
- [ ] Document static routes
- [ ] Note 40Gb links to Arista (ports 1/1/41-42)

---

### 🔧 [Arista 7050 (192.168.1.21)](./network-staging-arista.md)

**Size:** 471 lines

Commands and outputs for:
- System information and version
- VLAN configuration
- Interface status and descriptions
- Port-channel/LAG configuration
- LACP status
- 40Gb interface details

**Key Tasks:**
- [ ] Identify ports connected to Proxmox hosts (which Et# to which host?)
- [ ] Document 40Gb links to Brocade (Et49-50)
- [ ] Check port-channel configuration
- [ ] Capture LACP neighbor info

---

### 🖥️ [Proxmox Hosts](./network-staging-proxmox.md)

**Size:** 470 lines

Information for all 4 Proxmox hosts:
- Host details (IPs, IPMI, hostnames)
- Network interface configurations
- Bond configurations
- Ceph monitor configuration
- VM to host mapping

**Key Tasks:**
- [ ] Configure and document VLAN 200 IPs for Ceph cluster network
- [ ] Verify bond configurations
- [ ] Document which physical interfaces are in which bonds

---

### 📝 [Manual Information & Notes](./network-staging-notes.md)

**Size:** 150 lines

Additional information:
- OPNsense configuration details
- Mikrotik switches (NRay60 radios, CSS326)
- Physical cable documentation
- Additional notes and observations

**Key Tasks:**
- [ ] Document cable colors/labels
- [ ] Note any physical topology quirks
- [ ] Add troubleshooting observations

---

## 🚀 Quick Command Reference

### Copy & Paste Command Blocks

**Brocade Quick Gather:**

```bash
ssh admin@192.168.1.20

# Run these commands:
show version
show vlan
show interface brief | include ve
show running-config | begin "interface ve"
show lag
show lag brief
show ip route
show interface description
show interface ethernet 1/1/41
show interface ethernet 1/1/42
```

**Arista Quick Gather:**

```bash
ssh admin@192.168.1.21

# Run these commands:
show version
show vlan
show interface status
show interface description
show port-channel summary
show lacp neighbor
show interface ethernet 49
show interface ethernet 50
show interface ethernet 1-10 status
```

**Proxmox Quick Gather:**

```bash
# SSH to each Proxmox host
ssh root@192.168.1.62  # Proxmox-01
ssh root@192.168.1.63  # Proxmox-02
ssh root@192.168.1.64  # Proxmox-03
ssh root@192.168.1.66  # Proxmox-04

# Run on each:
hostname
ip addr show
cat /proc/net/bonding/bond0 2>/dev/null || echo "bond0 not found"
cat /proc/net/bonding/bond1 2>/dev/null || echo "bond1 not found"
pvecm nodes
qm list
```

---

## ✅ Master Completion Checklist

Track your overall progress:

### Brocade ICX6610

- [x] Basic system info gathered
- [x] VLAN configuration captured
- [ ] VLAN interface IPs documented (ve 150, ve 200)
- [ ] Port descriptions completed
- [ ] LAG configurations documented
- [ ] Routing table captured
- [ ] 40Gb interconnect details noted

### Arista 7050

- [x] Basic system info gathered
- [ ] Port assignments to Proxmox identified
- [ ] Port-channel status checked
- [ ] LACP configuration documented
- [ ] 40Gb links to Brocade identified

### Proxmox Hosts

- [x] All host IPs documented
- [x] All IPMI IPs documented
- [ ] VLAN 200 IPs configured and documented
- [x] VM-to-host mapping completed
- [x] Ceph monitor IPs identified
- [ ] Bond configurations verified

### Manual Information

- [x] OPNsense details filled
- [x] Mikrotik switch purposes documented
- [ ] Physical cable documentation completed
- [ ] Additional observations noted

---

## 📄 Next Steps After Completion

Once all staging documents are complete:

1. **Review all outputs** for accuracy and completeness
2. **Update main topology document** (`network-topology.md`) with gathered details
3. **Update runbook** (`network-runbook.md`) with specific port numbers and configurations
4. **Create LAG configuration** for Brocade-Arista interconnect fix
5. **Archive staging documents** as reference or move to a `staging/` subdirectory

---

## 🗂️ File Structure

```
docs/src/architecture/
├── network-topology.md              # Main network documentation
├── network-runbook.md               # Operations runbook
├── network-staging.md               # This file (index)
├── network-staging-brocade.md       # Brocade switch details
├── network-staging-arista.md        # Arista switch details
├── network-staging-proxmox.md       # Proxmox hosts & VMs
├── network-staging-notes.md         # Manual info & notes
└── network-staging-BACKUP.md        # Original unified document (backup)
```

---

**Last Updated:** 2025-10-14
