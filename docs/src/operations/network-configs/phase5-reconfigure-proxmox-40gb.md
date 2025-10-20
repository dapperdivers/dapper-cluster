# Phase 5: Reconfigure Proxmox Hosts to Use 40GB Links for VLAN 200

## Overview

This phase reconfigures Proxmox hosts with 40Gb links to use those links for VLAN 200 (Ceph cluster storage) instead of the current 10Gb bond. This will provide 40Gbps dedicated bandwidth per host for Ceph traffic.

**Scope:**
- **Proxmox-01, 02, 04:** Move VLAN 200 from bond1 to 40Gb interface
- **Proxmox-03:** No changes (keep using bond1, routing through Brocade)

**Impact:**
- Brief disruption to Ceph traffic on each host during reconfiguration
- VMs will continue running (only Ceph I/O affected)
- Management network (bond0) not affected

**Prerequisites:**
- Phase 4 completed with 40Gb interfaces identified
- Mapping document created with interface names and Arista ports

---

## Pre-Change Checklist

### 1. Verify Prerequisites

- [ ] Phase 1-4 completed successfully
- [ ] 40Gb interface identified on each host (from Phase 4)
- [ ] Arista port mapping documented
- [ ] MTU 9216 configured on Arista ports (Phase 3)
- [ ] Brocade-Arista LAG operational (Phase 1)

### 2. Backup Current Configuration

**On each Proxmox host:**
```bash
# SSH to host
ssh root@<proxmox-ip>

# Backup network configuration
cp /etc/network/interfaces /etc/network/interfaces.backup-$(date +%Y%m%d)

# Backup hosts file (just in case)
cp /etc/hosts /etc/hosts.backup-$(date +%Y%m%d)

# Document current IP configuration
ip addr show > /root/ip-addr-before-$(date +%Y%m%d).txt
ip route show > /root/ip-route-before-$(date +%Y%m%d).txt
```

### 3. Prepare for Potential Issues

**Have ready:**
- Console access to each Proxmox host (via IPMI: 192.168.1.162-165)
- Backup network configuration files
- This runbook open for rollback procedures
- At least 30 minutes of maintenance window per host

### 4. Check Ceph Status Before Starting

```bash
# From any Proxmox host or Kubernetes
ssh root@192.168.1.64  # Or any host

# Check Ceph health
ceph -s

# Should show HEALTH_OK or HEALTH_WARN (acceptable)
# Note any existing issues before proceeding
```

---

## Configuration Procedure

### Important: Configure Hosts One at a Time

**Do NOT configure all hosts simultaneously!**
- Configure one host
- Test thoroughly
- Wait for Ceph to rebalance if needed
- Then proceed to next host

**Recommended order:**
1. Proxmox-04 (test host)
2. Proxmox-02
3. Proxmox-01
4. (Proxmox-03 already configured in Phase 2)

---

## Per-Host Configuration Steps

### Step 0: Identify Your Interface Name

From Phase 4 documentation, identify:
- Interface name (e.g., `enp7s0`, `enp2s0`)
- Current VLAN 200 IP (e.g., `10.200.0.4` for Proxmox-04)

**Example values for this guide:**
- Host: Proxmox-04
- 40Gb Interface: `enp7s0`
- VLAN 200 IP: `10.200.0.4/24`

**Adjust these values for each host!**

### Step 1: Edit Network Configuration

**SSH to Proxmox host:**
```bash
ssh root@192.168.1.66  # Proxmox-04 example
```

**Edit network interfaces file:**
```bash
nano /etc/network/interfaces
```

### Step 2: Locate and Comment Out Old vmbr200 Configuration

**Find the existing vmbr200 section:**
```
auto vmbr1.200
iface vmbr1.200 inet manual
    vlan-raw-device vmbr1
    mtu 1500

auto vmbr200
iface vmbr200 inet static
    address 10.200.0.4/24
    bridge-ports vmbr1.200
    bridge-stp off
    bridge-fd 0
    mtu 1500
```

**Comment it out (add # at beginning of each line):**
```
# OLD VLAN 200 configuration (was on bond1)
#auto vmbr1.200
#iface vmbr1.200 inet manual
#    vlan-raw-device vmbr1
#    mtu 1500

#auto vmbr200
#iface vmbr200 inet static
#    address 10.200.0.4/24
#    bridge-ports vmbr1.200
#    bridge-stp off
#    bridge-fd 0
#    mtu 1500
```

### Step 3: Add New Configuration for 40Gb Interface

**At the end of the file, add:**
```
# 40Gb interface for VLAN 200 (Ceph cluster storage)
auto enp7s0
iface enp7s0 inet manual
    mtu 9000

# VLAN 200 on 40Gb interface
auto enp7s0.200
iface enp7s0.200 inet manual
    mtu 9000
    vlan-raw-device enp7s0

# Bridge for VLAN 200 (Ceph storage network)
auto vmbr200
iface vmbr200 inet static
    address 10.200.0.4/24
    bridge-ports enp7s0.200
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware no
    mtu 9000
    # No gateway - this is a non-routed storage network
```

**Key points:**
- Replace `enp7s0` with your actual 40Gb interface name
- Replace `10.200.0.4/24` with the correct IP for this host
- **MTU 9000** on all interfaces
- No gateway specified (storage network is non-routed for hosts with 40Gb links)

**Save and exit:** `Ctrl+X`, `Y`, `Enter`

### Step 4: Verify Configuration Syntax

```bash
# Test configuration without applying
ifreload -a -n

# Should output the changes to be made
# Check for any syntax errors
```

**Expected output:**
```
ifdown: interface vmbr200 not configured
ifup: interface enp7s0 is already configured
...
```

**If errors appear:**
- Review the configuration file for typos
- Ensure all sections are properly formatted
- Check that the interface name matches what was identified in Phase 4

### Step 5: Apply New Configuration

**Warning:** This will briefly interrupt Ceph traffic!

```bash
# Bring down old vmbr200 (from bond1)
ifdown vmbr200
ifdown vmbr1.200

# Bring up new vmbr200 (on 40Gb interface)
ifup enp7s0
ifup enp7s0.200
ifup vmbr200
```

**Alternative (reload all interfaces):**
```bash
# This may cause brief interruption to other services
ifreload -a
```

### Step 6: Verify New Configuration

**Check interface status:**
```bash
# Check all VLAN 200 related interfaces are UP
ip link show enp7s0
ip link show enp7s0.200
ip link show vmbr200

# All should show "state UP"
```

**Check IP address:**
```bash
ip addr show vmbr200

# Should show:
# inet 10.200.0.4/24 brd 10.200.0.255 scope global vmbr200
```

**Check MTU:**
```bash
ip link show enp7s0 | grep mtu
ip link show enp7s0.200 | grep mtu
ip link show vmbr200 | grep mtu

# All should show mtu 9000
```

**Check bridge configuration:**
```bash
bridge link show | grep vmbr200

# Should show enp7s0.200 as bridge port
```

### Step 7: Test Connectivity

**Test ping to Brocade gateway:**
```bash
ping -c 4 10.200.0.254

# Should succeed (routing through Brocade-Arista LAG)
```

**Test jumbo frames:**
```bash
# Test 9000 byte MTU
ping -M do -s 8972 -c 4 10.200.0.254

# Should succeed without fragmentation
# -M do = Don't fragment
# -s 8972 = 8972 + 28 (headers) = 9000 bytes
```

**Test connectivity to Proxmox-03 (through Brocade):**
```bash
ping -c 4 10.200.0.3

# Should succeed
```

**If other hosts are already configured, test them:**
```bash
# Test to other Proxmox hosts on VLAN 200
ping -c 4 10.200.0.1  # If Proxmox-01 configured
ping -c 4 10.200.0.2  # If Proxmox-02 configured
```

### Step 8: Monitor Ceph Recovery

**Check Ceph status:**
```bash
ceph -s

# Watch for:
# - OSDs should remain UP
# - May see brief degradation during rebalance
# - Should return to HEALTH_OK after a few minutes
```

**Watch Ceph recovery:**
```bash
watch -n 5 'ceph -s'

# Monitor until health returns to OK
# This may take 5-30 minutes depending on data movement
```

---

## Post-Configuration for All Hosts

After all three hosts (Proxmox-01, 02, 04) are configured:

### Verify VLAN 200 Network Connectivity

**Test from Proxmox-01:**
```bash
ssh root@192.168.1.62

# Test to all other hosts
ping -c 4 10.200.0.2  # Proxmox-02
ping -c 4 10.200.0.3  # Proxmox-03 (through Brocade)
ping -c 4 10.200.0.4  # Proxmox-04

# Test jumbo frames
ping -M do -s 8972 -c 4 10.200.0.2
ping -M do -s 8972 -c 4 10.200.0.3
ping -M do -s 8972 -c 4 10.200.0.4
```

**Test from Proxmox-03 (using 10Gb bond to Brocade):**
```bash
ssh root@192.168.1.64

# Test to all other hosts (should route through Brocade)
ping -c 4 10.200.0.1
ping -c 4 10.200.0.2
ping -c 4 10.200.0.4

# Test jumbo frames
ping -M do -s 8972 -c 4 10.200.0.1
```

### Verify Traffic Flows Through Correct Links

**On Arista:**
```bash
ssh admin@192.168.1.21

# Check traffic on 40Gb links
show interface ethernet 27 counters rate  # Proxmox-01 (or whichever)
show interface ethernet 28 counters rate  # Proxmox-02
show interface ethernet 29 counters rate  # Proxmox-04

# Should show traffic on all three ports
```

**On Brocade:**
```bash
ssh admin@192.168.1.20

# Check traffic on Proxmox-03's bond (LAG 2)
show lag 2

# Should show traffic to/from Proxmox-03
```

---

## Rollback Procedure

**If issues occur on a host:**

### Quick Rollback (Revert to 10Gb bond)

**On affected Proxmox host:**
```bash
# Bring down new configuration
ifdown vmbr200
ifdown enp7s0.200
ifdown enp7s0

# Restore backup configuration
cp /etc/network/interfaces.backup-<date> /etc/network/interfaces

# Bring up old configuration
ifup vmbr1.200
ifup vmbr200

# Verify old config is working
ip addr show vmbr200
ping -c 4 10.200.0.254
```

### Full Rollback (Edit Configuration)

```bash
# Edit network configuration
nano /etc/network/interfaces

# Remove the new 40Gb configuration section:
# - Delete "auto enp7s0" section
# - Delete "auto enp7s0.200" section
# - Delete "auto vmbr200" section (new one)

# Uncomment the old configuration:
# - Remove # from "auto vmbr1.200" section
# - Remove # from "auto vmbr200" section (old one)

# Save and reload
ifreload -a

# Test
ip addr show vmbr200
ping -c 4 10.200.0.254
```

---

## Troubleshooting

### Issue: vmbr200 Won't Come Up

**Symptoms:**
- `ip link show vmbr200` shows "state DOWN"
- Cannot ping on VLAN 200

**Diagnosis:**
```bash
# Check parent interface is UP
ip link show enp7s0 | grep "state UP"
ip link show enp7s0.200 | grep "state UP"

# Check bridge configuration
bridge link show

# Check for errors
dmesg | tail -50 | grep -i enp7s0
journalctl -xe | grep -i network
```

**Resolution:**
1. **Parent interface not UP:** `ip link set enp7s0 up`
2. **VLAN interface issues:** Delete and recreate: `ip link del enp7s0.200` then `ifup enp7s0.200`
3. **Bridge issues:** Delete and recreate bridge: `ip link del vmbr200` then `ifup vmbr200`
4. **Configuration syntax error:** Review /etc/network/interfaces for typos

### Issue: MTU Mismatch / Jumbo Frames Don't Work

**Symptoms:**
- Ping works but `ping -M do -s 8972` fails
- Ceph slow or errors about fragmentation

**Diagnosis:**
```bash
# Check MTU on all interfaces in path
ip link show enp7s0 | grep mtu        # Should be 9000
ip link show enp7s0.200 | grep mtu    # Should be 9000
ip link show vmbr200 | grep mtu       # Should be 9000

# Check Arista port MTU
# On Arista:
show interface ethernet <port> | grep MTU  # Should be 9216
```

**Resolution:**
```bash
# Manually set MTU if needed
ip link set enp7s0 mtu 9000
ip link set enp7s0.200 mtu 9000
ip link set vmbr200 mtu 9000

# Or fix in /etc/network/interfaces and reload
nano /etc/network/interfaces
ifreload -a
```

### Issue: Cannot Reach Other Hosts on VLAN 200

**Symptoms:**
- Ping to 10.200.0.254 (Brocade) works
- Ping to other Proxmox hosts fails

**Diagnosis:**
```bash
# Check routing table
ip route show | grep 10.200.0

# Check ARP table
ip neighbor show | grep 10.200.0

# Check if traffic is leaving interface
tcpdump -i enp7s0.200 icmp
# Then try ping from another terminal

# On Arista, check MAC learning
ssh admin@192.168.1.21
show mac address-table interface ethernet <port>
```

**Resolution:**
1. **No route:** Should not need explicit route for 10.200.0.0/24 (directly connected)
2. **ARP not working:** Check VLAN 200 is properly configured on Arista
3. **Firewall blocking:** Check iptables rules: `iptables -L -v -n`
4. **Switch configuration:** Verify VLAN 200 on Arista port

### Issue: Ceph OSDs Go Down

**Symptoms:**
- Ceph shows OSDs as DOWN after reconfiguration
- `ceph osd tree` shows OSDs offline

**Diagnosis:**
```bash
# Check OSD status
ceph osd tree

# Check OSD logs (if OSDs are on this host)
journalctl -u ceph-osd@* -n 100

# Check network connectivity
ping -c 4 <other-osd-host-ip>
```

**Resolution:**
1. **Network unreachable:** Fix network configuration
2. **Timeout waiting for network:** Restart OSDs: `systemctl restart ceph-osd@*`
3. **Configuration error:** Rollback network configuration
4. **Ceph bind address wrong:** Check Ceph config points to new vmbr200

---

## Success Criteria (Per Host)

- [ ] 40Gb interface (enp7s0 or similar) is UP
- [ ] VLAN interface (enp7s0.200) is UP with MTU 9000
- [ ] vmbr200 is UP with correct IP and MTU 9000
- [ ] Can ping Brocade gateway (10.200.0.254)
- [ ] Can ping other Proxmox hosts on VLAN 200
- [ ] Jumbo frames work (ping -M do -s 8972 succeeds)
- [ ] Ceph OSDs remain UP (or come back UP after rebalance)
- [ ] Ceph status returns to HEALTH_OK
- [ ] Traffic visible on Arista 40Gb port
- [ ] Configuration saved and persistent across reboot (test optional)

---

## Summary of Network Paths After Phase 5

**VLAN 200 (Ceph Cluster Storage) Traffic Paths:**

1. **Proxmox-01 ↔ Proxmox-02:**
   - Direct through Arista (40Gb → 40Gb)
   - Full 40Gbps bandwidth

2. **Proxmox-01 ↔ Proxmox-04:**
   - Direct through Arista (40Gb → 40Gb)
   - Full 40Gbps bandwidth

3. **Proxmox-02 ↔ Proxmox-04:**
   - Direct through Arista (40Gb → 40Gb)
   - Full 40Gbps bandwidth

4. **Proxmox-03 ↔ Proxmox-01/02/04:**
   - Proxmox-03 → bond1 (10Gb) → Brocade VE200
   - Brocade → LAG 11 (80Gb) → Arista
   - Arista → 40Gb → Proxmox-01/02/04
   - Bandwidth: Limited to 10Gb at Proxmox-03, but no bottleneck at switches

5. **All hosts ↔ Brocade routing:**
   - Via LAG 11 (80Gbps) between Brocade and Arista
   - No bottleneck for Proxmox-03 traffic

---

## Next Steps

Once Phase 5 is complete for all hosts:
- Proceed to **Phase 6**: Comprehensive testing and performance verification
- Test Ceph performance with iperf3
- Monitor production traffic patterns
- Document final configuration and lessons learned

---

## Reference: Example Full Configuration

**Complete /etc/network/interfaces section for vmbr200 on 40Gb host:**
```
# 40Gb interface for VLAN 200 (Ceph cluster storage)
auto enp7s0
iface enp7s0 inet manual
    mtu 9000

# VLAN 200 on 40Gb interface
auto enp7s0.200
iface enp7s0.200 inet manual
    mtu 9000
    vlan-raw-device enp7s0

# Bridge for VLAN 200 (Ceph storage network)
auto vmbr200
iface vmbr200 inet static
    address 10.200.0.X/24
    bridge-ports enp7s0.200
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware no
    mtu 9000
```

**For Proxmox-03 (no changes, reference only):**
```
# VLAN 200 on 10Gb bond to Brocade
auto vmbr1.200
iface vmbr1.200 inet manual
    vlan-raw-device vmbr1
    mtu 9000

auto vmbr200
iface vmbr200 inet static
    address 10.200.0.3/24
    gateway 10.200.0.254
    bridge-ports vmbr1.200
    bridge-stp off
    bridge-fd 0
    mtu 9000
```
