# 40GB Ceph Storage Network Configuration

## Project Overview

This project configures the 40GB network infrastructure for Ceph cluster storage (VLAN 200), providing dedicated high-bandwidth links for Ceph OSD replication traffic. The configuration enables 40Gbps connectivity for three Proxmox hosts with routing support for the fourth host through a Brocade-Arista link aggregation.

**Key Benefits:**
- 🚀 **4x bandwidth increase** for hosts with 40Gb links (10Gb → 40Gb)
- 🔗 **80Gbps aggregated bandwidth** between Brocade and Arista switches
- 📦 **Jumbo frame support** (MTU 9000) for improved Ceph performance
- 🔀 **No bottlenecks** for mixed-speed traffic (10Gb and 40Gb hosts)
- 🛡️ **Resilient design** with LACP link aggregation and failover

**Project Status:** ✅ Ready for Implementation

---

## Architecture Summary

### Current State (Before Configuration)

**VLAN 200 Traffic:**
- All Proxmox hosts using 2x 10Gb bonds to Brocade
- Shared bandwidth with VLAN 100, 150
- MTU 1500 (no jumbo frames)
- Brocade-Arista: Only 1x 40Gb link active (2nd disabled due to loop)

**Limitations:**
- Ceph replication limited to ~9-10 Gbps per host
- Contention with other VLAN traffic
- No jumbo frame support

### Target State (After Configuration)

**VLAN 200 Traffic:**
- Proxmox-01, 02, 04: Dedicated 40Gb links to Arista
- Proxmox-03: 10Gb bond to Brocade (no 40Gb link available)
- Brocade-Arista: 2x 40Gb LAG (80Gbps total)
- MTU 9000 throughout the path
- Layer 3 routing on Brocade for Proxmox-03

**Benefits:**
- Proxmox-01, 02, 04: 40 Gbps dedicated Ceph bandwidth
- Proxmox-03: 10 Gbps Ceph bandwidth (no bottleneck at switches)
- Direct switching for 40Gb hosts (no routing latency)
- Optimized for large Ceph object transfers (jumbo frames)

---

## Network Topology

### Physical Connections

```
┌─────────────┐
│ Proxmox-01  │───────40Gb───────┐
│ (10.200.0.1)│                  │
└─────────────┘                  │
                                 │
┌─────────────┐                  │
│ Proxmox-02  │───────40Gb───────┤
│ (10.200.0.2)│                  │
└─────────────┘                  │    ┌──────────────┐
                                 ├────│ Arista 7050  │
┌─────────────┐                  │    │              │
│ Proxmox-04  │───────40Gb───────┤    │ Et27: Px-01  │
│ (10.200.0.4)│                  │    │ Et28: Px-02  │
└─────────────┘                  │    │ Et29: Px-04  │
                                 │    └──────┬───────┘
                                 │           │
┌─────────────┐                  │      2x 40Gb LAG
│ Proxmox-03  │─┐                │    (Port-Channel1)
│ (10.200.0.3)│ │                │           │
└─────────────┘ │                │    ┌──────┴───────┐
                │                │    │ Brocade 6610 │
          2x 10Gb bond           │    │              │
          (LAG to Brocade)       │    │ LAG 11: 80Gb │
                │                │    │ VE200: GW    │
                └────────────────┘    └──────────────┘
                                      (10.200.0.254)
```

### Traffic Paths

**Direct 40Gb Paths (no routing):**
- Proxmox-01 ↔ Proxmox-02: Via Arista (switched)
- Proxmox-01 ↔ Proxmox-04: Via Arista (switched)
- Proxmox-02 ↔ Proxmox-04: Via Arista (switched)

**Routed Paths (through Brocade):**
- Proxmox-03 ↔ Proxmox-01/02/04:
  - Px-03 → 10Gb bond → Brocade VE200 (Layer 3 routing)
  - Brocade → 80Gb LAG → Arista
  - Arista → 40Gb → Px-01/02/04
  - Bandwidth: Limited to 10Gb at Px-03, but LAG prevents bottleneck

---

## Configuration Phases

This project is divided into 6 phases that must be completed in order:

### Phase 1: Configure Brocade-Arista 40GB LAG ⚙️
**[Documentation](./phase1-brocade-arista-lag.md)**

Enable the second 40Gb link between Brocade and Arista by configuring LACP link aggregation.

**Key Tasks:**
- Create LAG on Brocade (LAG ID 11)
- Create Port-Channel on Arista (Port-Channel1)
- Enable both 40Gb links (Et25, Et26 on Arista)
- Configure LACP with fast timeout

**Outcome:** 80Gbps bandwidth between switches, eliminating potential bottleneck.

---

### Phase 2: Configure VLAN 200 Routing on Brocade 🌐
**[Documentation](./phase2-brocade-vlan200-routing.md)**

Configure Layer 3 routing on Brocade for Proxmox-03 to reach other hosts via VLAN 200.

**Key Tasks:**
- Create VLAN interface VE200 on Brocade (10.200.0.254/24)
- Set MTU 9000 on VE200
- Configure default route on Proxmox-03 pointing to Brocade

**Outcome:** Proxmox-03 can route to all other hosts on VLAN 200 through Brocade.

---

### Phase 3: Configure Arista VLAN 200 with Jumbo Frames 📦
**[Documentation](./phase3-arista-vlan200-jumbo-frames.md)**

Enable jumbo frame support (MTU 9216) on all Arista interfaces carrying VLAN 200 traffic.

**Key Tasks:**
- Set MTU 9216 on Port-Channel1 (Brocade link)
- Set MTU 9216 on Et27, Et28, Et29 (Proxmox links)
- Verify VLAN 200 trunk configuration

**Outcome:** Arista switch supports jumbo frames for optimal Ceph performance.

---

### Phase 4: Identify 40GB NICs on Proxmox Hosts 🔍
**[Documentation](./phase4-identify-40gb-nics.md)**

Identify which physical network interfaces are the 40Gb NICs on each Proxmox host and map them to Arista switch ports.

**Key Tasks:**
- Use ethtool/LLDP/link flap to identify 40Gb interfaces
- Document interface names (e.g., enp2s0, enp7s0)
- Map Proxmox hosts to Arista ports (Et27, Et28, Et29)
- Record MAC addresses for tracking

**Outcome:** Complete mapping of Proxmox hosts to Arista ports with interface names documented.

---

### Phase 5: Reconfigure Proxmox Hosts to Use 40GB Links 🖥️
**[Documentation](./phase5-reconfigure-proxmox-40gb.md)**

Reconfigure Proxmox hosts to move VLAN 200 from 10Gb bonds to dedicated 40Gb interfaces.

**Key Tasks:**
- Edit `/etc/network/interfaces` on each host
- Move vmbr200 from bond1 to 40Gb interface (with VLAN 200 tag)
- Set MTU 9000 on all interfaces
- Test connectivity after each host (one at a time!)

**Outcome:** Proxmox-01, 02, 04 using 40Gb links; Proxmox-03 using 10Gb bond with routing.

**⚠️ Important:** Configure hosts one at a time to minimize Ceph disruption!

---

### Phase 6: Testing and Verification ✅
**[Documentation](./phase6-testing-verification.md)**

Comprehensive testing to validate the configuration and measure performance improvements.

**Test Categories:**
1. **Connectivity Tests:** Ping between all hosts, ARP resolution
2. **MTU Tests:** Jumbo frame validation (ping -M do -s 8972)
3. **Bandwidth Tests:** iperf3 throughput measurements
4. **Ceph Performance:** OSD network tests, rebalance speed
5. **Switch Verification:** LAG status, traffic distribution, error counters
6. **Failover Tests:** LAG member failure, host failure scenarios

**Outcome:** Validated 4x performance improvement with comprehensive test results.

---

## Quick Start Guide

### Prerequisites

Before starting, ensure you have:
- [ ] SSH access to all switches (Brocade, Arista)
- [ ] SSH/IPMI access to all Proxmox hosts
- [ ] Backup of all current configurations
- [ ] Maintenance window scheduled (recommended: 2-4 hours)
- [ ] Console access ready (IPMI) in case of network issues
- [ ] This documentation downloaded and available offline

### Execution Order

**Follow phases in strict order:**

1. **Phase 1** (30 min): Configure switch LAG - minimal disruption
2. **Phase 2** (15 min): Add Brocade routing - no disruption to existing hosts
3. **Phase 3** (15 min): Set MTU on Arista - minimal disruption
4. **Phase 4** (30 min): Identify interfaces - read-only, no disruption
5. **Phase 5** (60 min): Reconfigure hosts - brief Ceph disruption per host
6. **Phase 6** (60+ min): Testing - monitor for issues

**Total time:** 3-4 hours (including testing)

### Rollback Strategy

Each phase includes a rollback procedure. Key rollback points:

- **Phase 1:** Disable 2nd 40Gb link on Arista (immediate)
- **Phase 2:** Disable VE200 on Brocade (immediate)
- **Phase 3:** Revert MTU on Arista (immediate)
- **Phase 5:** Restore `/etc/network/interfaces` backup on each host

**Critical:** Keep one SSH session open to each device before making changes!

---

## Configuration Reference

### IP Addressing (VLAN 200)

| Host | Management IP | VLAN 200 IP | Interface | Link Speed | Connected To |
|------|---------------|-------------|-----------|------------|--------------|
| Proxmox-01 | 192.168.1.62 | 10.200.0.1/24 | enp2s0.200 | 40Gb | Arista Et27 |
| Proxmox-02 | 192.168.1.63 | 10.200.0.2/24 | enp7s0.200 | 40Gb | Arista Et28 |
| Proxmox-03 | 192.168.1.64 | 10.200.0.3/24 | bond1.200 | 2x 10Gb | Brocade LAG 2 |
| Proxmox-04 | 192.168.1.66 | 10.200.0.4/24 | enp7s0.200 | 40Gb | Arista Et29 |
| Brocade | 192.168.1.20 | 10.200.0.254/24 | VE200 | - | Gateway |

**Note:** Interface names may vary - update based on Phase 4 findings.

### Switch Configuration Summary

**Brocade ICX6610:**
- LAG 11: "brocade-to-arista" (ports 1/2/1, 1/2/6)
  - LACP dynamic, short timeout
  - VLANs 1, 20, 100, 150, 200 tagged
  - MTU 9000
- VLAN 200:
  - VE200: 10.200.0.254/24, MTU 9000
  - Routing enabled

**Arista 7050:**
- Port-Channel1: (Et25, Et26)
  - LACP active, fast rate
  - Trunk: VLANs 1, 20, 100, 150, 200
  - MTU 9216
- Et27, Et28, Et29:
  - Trunk mode
  - VLAN 200 tagged
  - MTU 9216

### MTU Configuration

| Device | Interface | MTU | Notes |
|--------|-----------|-----|-------|
| Brocade | VE200 | 9000 | VLAN 200 gateway |
| Brocade | LAG 11 | 9000 | To Arista |
| Arista | Port-Channel1 | 9216 | From Brocade |
| Arista | Et27-29 | 9216 | To Proxmox |
| Proxmox | 40Gb NIC | 9000 | Physical interface |
| Proxmox | VLAN interface | 9000 | enp*.200 |
| Proxmox | vmbr200 | 9000 | Bridge |

**Why 9216 on Arista?** Arista requires extra overhead for VLAN tagging (9000 + 216 = 9216).

---

## Expected Performance

### Bandwidth Improvements

| Connection | Before (10Gb) | After (40Gb) | Improvement |
|------------|---------------|--------------|-------------|
| Px-01 ↔ Px-02 | ~9 Gbps | ~35-38 Gbps | **4.0x** |
| Px-01 ↔ Px-04 | ~9 Gbps | ~35-38 Gbps | **4.0x** |
| Px-02 ↔ Px-04 | ~9 Gbps | ~35-38 Gbps | **4.0x** |
| Px-03 ↔ Others | ~9 Gbps | ~9-10 Gbps | 1.0x* |

\* Proxmox-03 limited by 10Gb uplink, but no switch bottleneck due to 80Gb LAG.

### Latency Improvements

| Path | Expected RTT | Notes |
|------|--------------|-------|
| 40Gb direct | < 0.5 ms | Switched only (no routing) |
| Via Brocade | < 1.5 ms | One Layer 3 hop |
| Before (10Gb shared) | 1-2 ms | Shared bandwidth, potential queuing |

### Ceph Performance

**Expected improvements:**
- **Rebalance speed:** 4x faster on hosts with 40Gb links
- **OSD recovery:** Significantly reduced time for large objects
- **Client I/O:** Reduced latency for Kubernetes pods using RBD/CephFS
- **Concurrent operations:** Better performance under load

---

## Troubleshooting

### Common Issues

**Issue:** LAG/Port-Channel won't form
- **Check:** LACP mode (both sides "active"), VLAN configuration matches
- **Verify:** Physical links are up, no cable/SFP issues
- **Ref:** [Phase 1 Troubleshooting](./phase1-brocade-arista-lag.md#troubleshooting)

**Issue:** Jumbo frames don't work
- **Check:** MTU on every hop (host → switch → switch → host)
- **Test:** `ping -M do -s 8972 <destination>`
- **Ref:** [Phase 3 Troubleshooting](./phase3-arista-vlan200-jumbo-frames.md#troubleshooting)

**Issue:** Proxmox-03 can't reach other hosts
- **Check:** VE200 is up, routing table on Px-03, gateway configured
- **Verify:** LAG 11 is up between Brocade and Arista
- **Ref:** [Phase 2 Troubleshooting](./phase2-brocade-vlan200-routing.md#troubleshooting)

**Issue:** Lower than expected bandwidth
- **Check:** CPU usage during iperf3, network card offloading settings
- **Test:** Multi-stream iperf3 (`-P 10`)
- **Ref:** [Phase 6 Troubleshooting](./phase6-testing-verification.md#troubleshooting-guide)

### Emergency Contacts

| Role | Responsibility | Contact |
|------|----------------|---------|
| Network Admin | Switch configuration | [FILL IN] |
| System Admin | Proxmox hosts | [FILL IN] |
| Storage Admin | Ceph cluster | [FILL IN] |

---

## Maintenance and Operations

### Regular Checks

**Weekly:**
- Monitor switch logs for errors
- Check LAG/Port-Channel status
- Review interface error counters

**Monthly:**
- Verify bandwidth utilization trends
- Test failover procedures
- Review and update documentation

**Quarterly:**
- Full connectivity and performance test
- Review configurations for optimization
- Plan for firmware updates

### Backup Procedures

**Switch Configurations:**
```bash
# Brocade
show running-config > brocade-backup-$(date +%Y%m%d).txt

# Arista
show running-config > arista-backup-$(date +%Y%m%d).txt
```

**Proxmox Network Configs:**
```bash
# On each host
cp /etc/network/interfaces /etc/network/interfaces.backup-$(date +%Y%m%d)
```

**Store backups in:** `/home/derek/projects/dapper-cluster/docs/src/operations/network-configs/backups/`

### Future Enhancements

**Potential Improvements:**
- [ ] Add 40Gb link to Proxmox-03 (hardware upgrade)
- [ ] Implement network monitoring with Prometheus SNMP exporter
- [ ] Configure sFlow for traffic analysis
- [ ] Set up automated configuration backups (Ansible)
- [ ] Add redundant Brocade-Arista links (if needed)
- [ ] Upgrade to 100Gb links (future-proofing)

---

## Success Metrics

### Technical Metrics

- ✅ **Bandwidth:** 40Gb links achieve 35+ Gbps throughput
- ✅ **Latency:** < 1ms RTT between hosts on Arista
- ✅ **MTU:** 9000 byte frames work end-to-end
- ✅ **Availability:** 99.9%+ uptime (LAG provides redundancy)
- ✅ **Ceph:** Rebalance speed increased by 4x

### Operational Metrics

- ✅ **Deployment Time:** < 4 hours total
- ✅ **Downtime:** < 5 minutes per host (during reconfiguration)
- ✅ **Documentation:** Complete and accurate
- ✅ **Rollback:** < 2 minutes to revert changes
- ✅ **Team Readiness:** All staff trained on new configuration

---

## References

### Internal Documentation
- [Network Topology](../../architecture/network-topology.md)
- [Network Runbook](../network-runbook.md)
- [Storage Architecture](../../architecture/storage.md)

### Phase Documentation
- [Phase 1: Brocade-Arista LAG](./phase1-brocade-arista-lag.md)
- [Phase 2: Brocade VLAN 200 Routing](./phase2-brocade-vlan200-routing.md)
- [Phase 3: Arista Jumbo Frames](./phase3-arista-vlan200-jumbo-frames.md)
- [Phase 4: Identify 40GB NICs](./phase4-identify-40gb-nics.md)
- [Phase 5: Reconfigure Proxmox](./phase5-reconfigure-proxmox-40gb.md)
- [Phase 6: Testing & Verification](./phase6-testing-verification.md)

### Vendor Documentation
- Brocade ICX6610 Command Reference
- Arista 7050 Configuration Guide
- Proxmox Network Configuration
- Ceph Network Recommendations

---

## Project History

| Date | Milestone | Status |
|------|-----------|--------|
| 2025-10-14 | Project planning and documentation | ✅ Complete |
| TBD | Phase 1: Brocade-Arista LAG | 📋 Ready |
| TBD | Phase 2: Brocade routing | 📋 Ready |
| TBD | Phase 3: Arista MTU | 📋 Ready |
| TBD | Phase 4: Interface identification | 📋 Ready |
| TBD | Phase 5: Proxmox reconfiguration | 📋 Ready |
| TBD | Phase 6: Testing | 📋 Ready |
| TBD | Project completion | ⏳ Pending |

---

## License and Credits

**Documentation created by:** Claude (Anthropic AI Assistant)
**Date:** October 14, 2025
**Version:** 1.0
**Project:** Dapper Cluster 40GB Storage Network Upgrade

**Contributors:**
- Network architecture review and validation
- Configuration procedures and best practices
- Testing methodology and verification procedures

---

**Ready to begin? Start with [Phase 1: Configure Brocade-Arista LAG](./phase1-brocade-arista-lag.md)**
