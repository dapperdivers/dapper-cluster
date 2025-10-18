# Phase 1: Configure Brocade-Arista 40GB LAG

## Overview

This phase enables the second 40Gb link between Brocade and Arista by configuring a proper LACP LAG/Port-Channel. This will double the interconnect bandwidth from 40Gbps to 80Gbps.

**Current State:**
- Brocade port 1/2/6: UP and connected to Arista Et26
- Brocade port 1/2/1: DOWN (disabled to prevent loop)
- Arista Et26: UP and connected to Brocade
- Arista Et25: Administratively DOWN
- No LAG/Port-Channel configured

**Target State:**
- Both 40Gb links active in a LAG/Port-Channel
- LACP negotiation successful
- 80Gbps total bandwidth
- VLANs 1, 100, 150, 200 tagged on LAG

---

## Pre-Change Verification

### 1. Check Current State

**On Brocade:**
```bash
ssh admin@192.168.1.20

# Check current interface status
show interface ethernet 1/2/1
show interface ethernet 1/2/6

# Check current VLANs on these ports
show vlan brief

# Document current traffic (for comparison later)
show interface ethernet 1/2/6 | include rate
```

**On Arista:**
```bash
ssh admin@192.168.1.21

# Check current interface status
show interface ethernet 25
show interface ethernet 26

# Check current VLANs
show vlan

# Document current traffic
show interface ethernet 26 counters rate
```

### 2. Backup Configurations

**Brocade:**
```bash
show running-config
# Save output to: brocade-config-backup-$(date +%Y%m%d).txt
```

**Arista:**
```bash
show running-config
# Save output to: arista-config-backup-$(date +%Y%m%d).txt
```

---

## Configuration Steps

### Step 1: Prepare Brocade for LAG

**SSH to Brocade:**
```bash
ssh admin@192.168.1.20
enable
```

**Check available LAG IDs:**
```bash
show lag brief
```

**Note:** Based on the current configuration, LAG IDs 1-10 are in use. We'll use LAG ID 11 for the Brocade-Arista link.

### Step 2: Configure Brocade LAG

**Enter configuration mode:**
```bash
configure terminal

# Create LAG for Brocade-to-Arista interconnect
lag "brocade-to-arista" dynamic id 11
  ports ethernet 1/2/1 to 1/2/6
  primary-port 1/2/6
  lacp-timeout short
  deploy
exit

# Configure VLANs on the LAG
vlan 1
  tagged lag 11
exit

vlan 20
  tagged lag 11
exit

vlan 100
  tagged lag 11
exit

vlan 150
  tagged lag 11
exit

vlan 200
  tagged lag 11
exit

# Configure interfaces to participate in LAG
interface ethernet 1/2/1
  link-aggregate active
exit

interface ethernet 1/2/6
  link-aggregate active
exit

# Exit configuration mode
exit
```

**Save configuration:**
```bash
write memory
```

**Verify LAG configuration:**
```bash
show lag brief
show lag 11
show interface ethernet 1/2/1
show interface ethernet 1/2/6
```

**Expected output:**
- LAG "brocade-to-arista" with ID 11 should be listed
- Both ports 1/2/1 and 1/2/6 should show as members
- Ports should be in "link-aggregate active" mode

**Actual Output:**
```
40GigabitEthernet1/2/1 is down, line protocol is down
  Port down for 15 hour(s) 47 minute(s) 41 second(s)
  Hardware is 40GigabitEthernet, address is 748e.f8e6.a3b4 (bia 748e.f8e6.a3e5)
  Interface type is 40Gig Fiber
  Configured speed 40Gbit, actual unknown, configured duplex fdx, actual unknown
  Configured mdi mode AUTO, actual unknown
  Member of 5 L2 VLANs, port is dual mode in Vlan 1, port state is BLOCKING
  BPDU guard is Disabled, ROOT protect is Disabled, Designated protect is Disabled
  Link Error Dampening is Disabled
  STP configured to ON, priority is level0, mac-learning is enabled
  Openflow is Disabled, Openflow Hybrid mode is Disabled,  Flow Control is enabled
  Mirror disabled, Monitor disabled
  Mac-notification is disabled
  Member of active trunk ports 1/2/1,1/2/6, primary port is 1/2/6
  Member of configured trunk ports 1/2/1,1/2/6, primary port is 1/2/6
  No port name
  MTU 1500 bytes, encapsulation ethernet
  300 second input rate: 0 bits/sec, 0 packets/sec, 0.00% utilization
  300 second output rate: 0 bits/sec, 0 packets/sec, 0.00% utilization
  1740 packets input, 466965 bytes, 0 no buffer
  Received 853 broadcasts, 887 multicasts, 0 unicasts
  0 input errors, 0 CRC, 0 frame, 0 ignored
  0 runts, 0 giants
  4753847 packets output, 6687825864 bytes, 0 underruns
  Transmitted 74882 broadcasts, 229074 multicasts, 4449891 unicasts
  0 output errors, 0 collisions
  Relay Agent Information option: Disabled

Egress queues:
Queue counters    Queued packets    Dropped Packets
    0             4753739                   0
    1                   0                   0
    2                   0                   0
    3                   0                   0
    4                   0                   0
    5                 107                   0
    6                   0                   0
    7                   1                   0
SSH@brocade-turtleass-manor#show interface ethernet 1/2/6
40GigabitEthernet1/2/6 is up, line protocol is down (LACP-BLOCKED)
  Port down (LACP-BLOCKED) for 17 hour(s) 26 minute(s) 56 second(s)
  Hardware is 40GigabitEthernet, address is 748e.f8e6.a3b4 (bia 748e.f8e6.a3ea)
  Interface type is 40Gig Fiber
  Configured speed 40Gbit, actual 40Gbit, configured duplex fdx, actual fdx
  Configured mdi mode AUTO, actual none
  Member of 5 L2 VLANs, port is dual mode in Vlan 1, port state is BLOCKING
  BPDU guard is Disabled, ROOT protect is Disabled, Designated protect is Disabled
  Link Error Dampening is Disabled
  STP configured to ON, priority is level0, mac-learning is enabled
  Openflow is Disabled, Openflow Hybrid mode is Disabled,  Flow Control is enabled
  Mirror disabled, Monitor disabled
  Mac-notification is disabled
  Member of active trunk ports 1/2/1,1/2/6, primary port is 1/2/6
  Member of configured trunk ports 1/2/1,1/2/6, primary port is 1/2/6
  No port name
  MTU 1500 bytes, encapsulation ethernet
  300 second input rate: 544 bits/sec, 0 packets/sec, 0.00% utilization
  300 second output rate: 920 bits/sec, 0 packets/sec, 0.00% utilization
  3480 packets input, 802871 bytes, 0 no buffer
  Received 672 broadcasts, 2797 multicasts, 11 unicasts
  0 input errors, 0 CRC, 0 frame, 0 ignored
  0 runts, 0 giants
  46494237 packets output, 9921095422 bytes, 0 underruns
  Transmitted 184996 broadcasts, 612973 multicasts, 45696268 unicasts
  0 output errors, 0 collisions
  Relay Agent Information option: Disabled

Egress queues:
Queue counters    Queued packets    Dropped Packets
    0            46493607                   0
    1                   0                   0
    2                   0                   0
    3                   0                   0
    4                   0                   0
    5                 347                   0
    6                   0                   0
    7                 284                   0
```

### Step 3: Configure Arista Port-Channel

**SSH to Arista:**
```bash
ssh admin@192.168.1.21
enable
configure
```

**Create Port-Channel:**
```bash
# Create Port-Channel 1 for Brocade interconnect
interface Port-Channel1
  description Link to Brocade ICX6610
  switchport mode trunk
  switchport trunk allowed vlan 1,20,100,150,200
  mtu 9216
exit

# Configure Ethernet25 to join Port-Channel
interface Ethernet25
  description Brocade 40G Link 1
  switchport mode trunk
  switchport trunk allowed vlan 1,20,100,150,200
  channel-group 1 mode active
  lacp rate fast
  no shutdown
exit

# Configure Ethernet26 to join Port-Channel
interface Ethernet26
  description Brocade 40G Link 2
  switchport mode trunk
  switchport trunk allowed vlan 1,20,100,150,200
  channel-group 1 mode active
  lacp rate fast
exit

# Exit configuration mode
exit
```

**Save configuration:**
```bash
write memory
```

**Verify Port-Channel configuration:**
```bash
show port-channel summary
show port-channel 1 detail
show lacp neighbor
show interface Port-Channel1
show interface ethernet 25
show interface ethernet 26
```

**Expected output:**
```
Port-Channel1 is up
  Protocol: LACP
  Members:
    Ethernet25: Active (P)
    Ethernet26: Active (P)
  Trunk VLANs: 1,20,100,150,200
```

---

## Post-Change Verification

### 1. Verify LAG/Port-Channel Status

**On Brocade:**
```bash
show lag 11

# Should show:
# - Status: Deployed
# - 2 ports active (1/2/1 and 1/2/6)
# - LACP partner information from Arista

# Check LACP status
show lacp

# Check for errors
show log | include lag
show log | include 1/2/1
show log | include 1/2/6
```

**On Arista:**
```bash
show port-channel summary

# Should show:
# Po1(U) with Et25(P), Et26(P)
# U = Up, P = Port-channel (bundled)

# Check LACP neighbor
show lacp neighbor

# Should show Brocade as partner with system ID

# Check for errors
show logging | grep -i port-channel
show logging | grep -i ethernet25
show logging | grep -i ethernet26
```

### 2. Verify Traffic Distribution

**On Brocade:**
```bash
# Check traffic on both links
show interface ethernet 1/2/1 | include rate
show interface ethernet 1/2/6 | include rate

# Both should show traffic (load balancing)
```

**On Arista:**
```bash
# Check traffic on both links
show interface ethernet 25 counters rate
show interface ethernet 26 counters rate

# Both should show traffic
```

### 3. Verify VLAN Connectivity

**From your workstation, test connectivity across VLANs:**
```bash
# Test VLAN 100 (Kubernetes)
ping -c 4 10.100.0.50

# Test VLAN 150 (Ceph Public)
ping -c 4 10.150.0.10

# Test VLAN 200 (Ceph Cluster)
# (This will be tested after Proxmox reconfiguration in Phase 5)
```

### 4. Monitor for Issues

**Run these commands for 10-15 minutes and watch for problems:**

**On Brocade:**
```bash
# Watch LAG status
show lag 11

# Watch for errors
show log tail

# Monitor CPU (should be normal, not spiking)
show cpu
```

**On Arista:**
```bash
# Watch Port-Channel status
show port-channel summary

# Watch for errors
show logging last 50

# Monitor CPU
show processes top once
```

---

## Rollback Plan

**If issues occur, immediately rollback:**

### Quick Rollback (Emergency)

**On Arista (fastest access):**
```bash
enable
configure
interface ethernet 25
  shutdown
exit
exit
```

This disables the second link, returning to the original single-link state.

### Full Rollback

**On Arista:**
```bash
enable
configure

# Remove Port-Channel configuration
no interface Port-Channel1

# Reset Ethernet25
interface Ethernet25
  shutdown
exit

# Reset Ethernet26 to original config
interface Ethernet26
  no channel-group 1
exit

exit
write memory
```

**On Brocade:**
```bash
enable
configure terminal

# Remove LAG
no lag brocade-to-arista

# Reset interfaces
interface ethernet 1/2/1
  no link-aggregate
  shutdown
exit

interface ethernet 1/2/6
  no link-aggregate
exit

exit
write memory
```

---

## Troubleshooting

### Issue: LAG/Port-Channel Not Forming

**Symptoms:**
- Brocade shows LAG as "Not Deployed" or members not active
- Arista shows Port-Channel as "Down" or members not bundled

**Diagnosis:**
```bash
# On Brocade
show lag 11
show lacp

# On Arista
show port-channel summary
show lacp neighbor
show lacp internal
```

**Common Causes:**
1. **LACP mode mismatch** - Verify both sides are set to "active"
2. **VLAN mismatch** - Ensure same VLANs are allowed on both sides
3. **Speed/duplex mismatch** - Both should auto-negotiate to 40Gb
4. **Cable issue** - One cable may be faulty

**Resolution:**
- Check cable connections
- Verify both links show "Up" before bundling
- Check LACP timeout settings match

### Issue: Traffic Only on One Link

**Symptoms:**
- LAG/Port-Channel shows as "Up"
- Only one link shows traffic in counters

**Diagnosis:**
```bash
# Check load balancing algorithm
# Brocade:
show lag 11

# Arista:
show port-channel load-balance
```

**Resolution:**
- This may be normal if traffic is asymmetric
- LACP load-balancing is hash-based (src/dst MAC, IP, port)
- If truly all traffic on one link, check for configuration mismatch

### Issue: Network Loop / Broadcast Storm

**Symptoms:**
- Network performance severely degraded
- High CPU on switches
- Massive packet rates

**Immediate Action:**
```bash
# Disable second link immediately
# On Arista:
configure
interface ethernet 25
shutdown
```

**Diagnosis:**
- Check if Spanning Tree is running properly
- Verify LAG is properly formed (not two separate trunks)

---

## Success Criteria

- [ ] Both 40Gb links show "Up" status
- [ ] LAG/Port-Channel shows "Active" with 2 members
- [ ] LACP neighbor information shows correct partner
- [ ] Traffic is distributed across both links
- [ ] No errors in logs related to LAG/LACP
- [ ] No increase in CPU utilization
- [ ] All VLANs still accessible across the link
- [ ] Ping tests to all VLANs successful

---

## Next Steps

Once Phase 1 is complete and verified:
- Proceed to **Phase 2**: Configure VLAN 200 routing on Brocade
- This will enable routing for Proxmox-03 (without 40Gb link) to reach other hosts

---

## Reference Commands

### Brocade Quick Reference
```bash
# Show LAG status
show lag brief
show lag <id>

# Show LACP status
show lacp
show lacp | include <port>

# Show interface status
show interface ethernet <port>
show interface brief

# Show logs
show log
show log tail
```

### Arista Quick Reference
```bash
# Show Port-Channel status
show port-channel summary
show port-channel <id> detail

# Show LACP status
show lacp neighbor
show lacp internal

# Show interface status
show interface <interface>
show interface status

# Show logs
show logging
show logging last <n>
```
