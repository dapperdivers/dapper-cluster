# Phase 2: Configure VLAN 200 Routing on Brocade

## Overview

This phase configures Layer 3 routing for VLAN 200 on the Brocade switch. This is critical for Proxmox-03, which doesn't have a 40Gb link to Arista and must route through Brocade to reach other hosts.

**Current State:**
- VLAN 200 exists on Brocade but has no IP interface (no VE200)
- Proxmox-03 has IP 10.200.0.3 on vmbr200 (via 10Gb bond to Brocade)
- Other Proxmox hosts will use 40Gb links directly to Arista (configured in Phase 5)

**Target State:**
- Brocade VE200 interface with IP 10.200.0.254/24 (gateway for VLAN 200)
- MTU 9000 configured on VE200 for jumbo frames
- Routing enabled for traffic between Proxmox-03 (on Brocade) and other hosts (on Arista)

---

## Pre-Change Verification

### 1. Check Current VLAN 200 Configuration

**On Brocade:**
```bash
ssh admin@192.168.1.20

# Check if VE200 exists
show interface brief | include ve

# Check VLAN 200 configuration
show vlan 200

# Check current IP routing table
show ip route

# Check which ports have VLAN 200
show vlan 200 | include "Tagged Ports"
```

**Expected:** VE200 should NOT exist yet. VLAN 200 should be tagged on LAG 11 (Brocade-Arista) and on Proxmox host ports.

### 2. Verify IP Forwarding is Enabled

**On Brocade:**
```bash
show ip
```

**Expected:** IP routing should be enabled (Brocade has Advanced Router license).

### 3. Document Current Proxmox-03 Configuration

**SSH to Proxmox-03:**
```bash
ssh root@192.168.1.64

# Check current VLAN 200 interface
ip addr show vmbr200

# Check current routing
ip route show | grep 10.200.0

# Check current MTU
ip link show vmbr200 | grep mtu
```

**Expected:** Proxmox-03 should have 10.200.0.3/24 on vmbr200, no specific gateway configured yet.

---

## Configuration Steps

### Step 1: Create VLAN 200 Interface on Brocade

**SSH to Brocade:**
```bash
ssh admin@192.168.1.20
enable
configure terminal

# Create VLAN interface for VLAN 200
interface ve 200
  ip address 10.200.0.254/24
  no ip address dhcp
  mtu 9000
exit

# Ensure VLAN 200 is properly configured
vlan 200
  name CEPH-STORAGE
  router-interface ve 200
exit

# Exit configuration mode
exit
```

**Save configuration:**
```bash
write memory
```

### Step 2: Verify VLAN 200 Interface

**Check VE200 status:**
```bash
show interface ve 200

# Should show:
# - Status: Up
# - IP: 10.200.0.254/24
# - MTU: 9000
```

**Check IP routing table:**
```bash
show ip route

# Should show new entry:
# 10.200.0.0/24 -> DIRECT via ve 200
```

**Check VLAN 200 configuration:**
```bash
show vlan 200

# Should show:
# - Router interface: ve 200
# - Tagged ports include LAG 11 and Proxmox ports
```

### Step 3: Verify MTU on VLAN 200 Ports

**Check MTU on LAG 11 (Brocade-Arista link):**
```bash
show lag 11

# MTU should be 9000 or default (verify it supports jumbo frames)
```

**Check MTU on Proxmox-03 ports:**
```bash
# Check which LAG is for Px03
show lag brief

# For px03-vm LAG (should be LAG 2 based on earlier output)
show lag 2

# Verify MTU is 9000
```

**If MTU needs to be set on interfaces:**
```bash
enable
configure terminal

# Set MTU on VLAN 200 ports if needed
# For LAG 11 (Brocade-Arista)
lag "brocade-to-arista" dynamic id 11
  mtu 9000
exit

# For Proxmox host LAGs (if needed)
# Check current MTU first, may already be set
```

---

## Configure Proxmox-03 Default Route

### Step 1: Test Connectivity from Brocade

**On Brocade:**
```bash
# Ping Proxmox-03 on VLAN 200
ping 10.200.0.3 source 10.200.0.254 count 4

# Should succeed if Proxmox-03's vmbr200 is up
```

### Step 2: Configure Default Route on Proxmox-03

**SSH to Proxmox-03:**
```bash
ssh root@192.168.1.64

# Add route for VLAN 200 network via Brocade
ip route add 10.200.0.0/24 via 10.200.0.254 dev vmbr200 || true

# Test connectivity to Brocade
ping -c 4 10.200.0.254

# Test MTU (jumbo frames)
ping -M do -s 8972 -c 4 10.200.0.254
```

### Step 3: Make Route Persistent on Proxmox-03

**Edit network configuration:**
```bash
nano /etc/network/interfaces
```

**Find the vmbr200 section and add gateway:**
```
auto vmbr200
iface vmbr200 inet static
    address 10.200.0.3/24
    gateway 10.200.0.254
    bridge-ports vmbr1.200
    bridge-stp off
    bridge-fd 0
    mtu 9000
```

**Note:** The gateway line ensures routing through Brocade for VLAN 200 traffic.

**Apply changes:**
```bash
# Test the configuration syntax
ifreload -a -n

# If no errors, apply
ifreload -a

# Verify route is present
ip route show | grep 10.200.0
```

---

## Post-Change Verification

### 1. Verify VE200 Interface Status

**On Brocade:**
```bash
show interface ve 200

# Check:
# - Status: Up
# - IP: 10.200.0.254/24
# - MTU: 9000
# - No errors

show interface ve 200 | include rate
# Should show minimal traffic initially
```

### 2. Verify Routing Table

**On Brocade:**
```bash
show ip route

# Should show:
# 10.200.0.0/24 -> DIRECT via ve 200
```

### 3. Verify MTU End-to-End

**From Proxmox-03 to Brocade:**
```bash
ssh root@192.168.1.64

# Test jumbo frames to Brocade
ping -M do -s 8972 -c 10 10.200.0.254

# Should succeed with no fragmentation
# -M do = Don't fragment
# -s 8972 = 8972 + 28 (IP+ICMP headers) = 9000 MTU
```

### 4. Test Connectivity Between Proxmox Hosts

**Note:** Full end-to-end testing will be done in Phase 6, after Proxmox hosts with 40Gb links are reconfigured.

**For now, test Proxmox-03 to Brocade:**
```bash
# From Proxmox-03
ssh root@192.168.1.64

# Ping Brocade gateway
ping -c 4 10.200.0.254

# Test bandwidth to Brocade (using iperf3 if available)
# On Brocade: Not available
# Will test Proxmox-to-Proxmox in Phase 6
```

### 5. Check for Errors

**On Brocade:**
```bash
show log | include ve
show log | include 200

# Should see VE200 interface up messages
# No error messages
```

---

## Rollback Plan

**If issues occur:**

### Quick Rollback

**On Brocade:**
```bash
enable
configure terminal

# Disable VE200 interface
interface ve 200
  shutdown
exit

exit
write memory
```

This disables the routing interface without removing the configuration.

### Full Rollback

**On Brocade:**
```bash
enable
configure terminal

# Remove VLAN 200 interface
no interface ve 200

# Remove router interface from VLAN
vlan 200
  no router-interface ve 200
exit

exit
write memory
```

**On Proxmox-03:**
```bash
# Remove gateway from vmbr200 configuration
nano /etc/network/interfaces
# Remove the "gateway 10.200.0.254" line

# Delete the route
ip route del 10.200.0.0/24 via 10.200.0.254 dev vmbr200

# Reload network config
ifreload -a
```

---

## Troubleshooting

### Issue: VE200 Won't Come Up

**Symptoms:**
- `show interface ve 200` shows "Down"
- Cannot ping 10.200.0.254 from Proxmox-03

**Diagnosis:**
```bash
# Check if VLAN 200 exists
show vlan 200

# Check if router-interface is configured
show vlan 200 | include "router"

# Check IP configuration
show running-config | section "interface ve 200"
```

**Resolution:**
1. Ensure VLAN 200 has `router-interface ve 200` configured
2. Ensure VE200 has IP address configured
3. Check if interface is administratively down: `no shutdown`

### Issue: Cannot Ping Proxmox-03 from Brocade

**Symptoms:**
- `ping 10.200.0.3 source 10.200.0.254` fails from Brocade

**Diagnosis:**
```bash
# On Brocade: Check ARP table
show arp | include 10.200.0.3

# Check MAC address table
show mac-address | include <VLAN-200>

# Check if VLAN 200 is on correct ports
show vlan 200
```

**On Proxmox-03:**
```bash
# Check if vmbr200 is up
ip link show vmbr200

# Check IP address
ip addr show vmbr200

# Check if VLAN 200 is properly tagged
bridge vlan show
```

**Resolution:**
1. Verify vmbr200 is "UP" on Proxmox-03
2. Verify VLAN 200 is tagged on correct bond/ports on Brocade
3. Check firewall rules on Proxmox-03: `iptables -L -v -n`

### Issue: MTU Mismatch / Fragmentation

**Symptoms:**
- Ping with large packets fails
- `ping -M do -s 8972` times out or fails

**Diagnosis:**
```bash
# Check MTU on each hop

# On Brocade:
show interface ve 200 | include mtu

# On Proxmox-03:
ip link show vmbr200 | grep mtu
ip link show bond1 | grep mtu
ip link show vmbr1.200 | grep mtu
```

**Resolution:**
Ensure MTU is 9000 on all interfaces in the path:
- Brocade VE200
- Brocade physical/LAG ports for VLAN 200
- Proxmox-03 bond1
- Proxmox-03 vmbr1
- Proxmox-03 vmbr1.200
- Proxmox-03 vmbr200

---

## Success Criteria

- [ ] VE200 interface shows "Up" status
- [ ] VE200 has IP 10.200.0.254/24 configured
- [ ] VE200 has MTU 9000 configured
- [ ] Routing table shows 10.200.0.0/24 via VE200
- [ ] Can ping 10.200.0.254 from Proxmox-03
- [ ] Can ping 10.200.0.3 from Brocade
- [ ] Jumbo frames work (ping -M do -s 8972 succeeds)
- [ ] No errors in Brocade logs
- [ ] Gateway route is persistent on Proxmox-03

---

## Network Traffic Flow

**After Phase 2, the traffic flow for VLAN 200 is:**

1. **Proxmox-03 to Brocade:**
   - Proxmox-03 (10.200.0.3) → bond1 (10Gb) → Brocade VE200 (10.200.0.254)
   - Fully routed by Brocade

2. **Proxmox-03 to Other Proxmox Hosts (after Phase 5):**
   - Proxmox-03 → Brocade VE200 → LAG 11 (40Gb x2) → Arista → 40Gb link → Other Proxmox
   - Path: 10Gb → 80Gb → 40Gb (no bottleneck due to LAG)

3. **Proxmox hosts on Arista (after Phase 5):**
   - Direct communication via Arista switching (no routing needed)
   - Full 40Gb bandwidth per host

---

## Next Steps

Once Phase 2 is complete and verified:
- Proceed to **Phase 3**: Configure Arista VLAN 200 with jumbo frames
- Then **Phase 4**: Identify 40GB NICs on Proxmox hosts
- Then **Phase 5**: Reconfigure Proxmox hosts to use 40GB links

---

## Reference Commands

### Brocade VLAN Interface Commands
```bash
# Create VLAN interface
interface ve <vlan-id>
  ip address <ip>/<mask>
  mtu <mtu>
exit

# Assign router interface to VLAN
vlan <vlan-id>
  router-interface ve <vlan-id>
exit

# Show VLAN interface status
show interface ve <vlan-id>
show interface brief | include ve

# Show IP routes
show ip route
```

### Proxmox Network Commands
```bash
# Show interface details
ip addr show <interface>
ip link show <interface>

# Show routing table
ip route show

# Test MTU
ping -M do -s 8972 <ip>

# Edit network config
nano /etc/network/interfaces

# Reload network config
ifreload -a
ifreload -a -n  # Dry-run to check syntax
```
