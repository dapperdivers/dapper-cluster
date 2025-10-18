# Phase 3: Configure Arista VLAN 200 with Jumbo Frames

## Overview

This phase configures MTU 9216 on all Arista interfaces carrying VLAN 200 to support Ceph's jumbo frames requirement. Arista requires MTU 9216 (vs 9000) to account for VLAN tagging overhead.

**Current State:**
- VLAN 200 exists on Arista
- Arista has default MTU (likely 9214 or 1500) on interfaces
- Et27-29: Connected to Proxmox hosts (40Gb)
- Port-Channel1 (Et25-26): Connected to Brocade (configured in Phase 1)

**Target State:**
- MTU 9216 on all interfaces carrying VLAN 200:
  - Port-Channel1 (to Brocade)
  - Et27 (to Proxmox host)
  - Et28 (to Proxmox host)
  - Et29 (to Proxmox host)
- VLAN 200 properly configured on all trunk ports

---

## Pre-Change Verification

### 1. Check Current MTU Configuration

**On Arista:**
```bash
ssh admin@192.168.1.21

# Check Port-Channel1 MTU
show interface Port-Channel1 | grep MTU

# Check Ethernet interfaces MTU
show interface ethernet 25 | grep MTU
show interface ethernet 26 | grep MTU
show interface ethernet 27 | grep MTU
show interface ethernet 28 | grep MTU
show interface ethernet 29 | grep MTU

# Check current VLAN 200 configuration
show vlan id 200
```

**Expected:** MTU is likely 9214 (default) or 1500. VLAN 200 should be present on Et27-29 and the trunk to Brocade.

### 2. Document Current Interface Status

```bash
# Check interface status
show interface status | grep -E "(Et25|Et26|Et27|Et28|Et29|Po1)"

# Check trunk configuration
show interface trunk

# Document current traffic levels
show interface ethernet 27 counters rate
show interface ethernet 28 counters rate
show interface ethernet 29 counters rate
show interface Port-Channel1 counters rate
```

---

## Configuration Steps

### Step 1: Configure MTU on Port-Channel1 (Brocade Link)

**SSH to Arista:**
```bash
ssh admin@192.168.1.21
enable
configure
```

**Configure Port-Channel1:**
```bash
interface Port-Channel1
  mtu 9216
exit
```

**Note:** This also applies to member interfaces (Et25, Et26) automatically.

### Step 2: Configure MTU on Proxmox Host Links

**Configure Et27:**
```bash
interface Ethernet27
  mtu 9216
exit
```

**Configure Et28:**
```bash
interface Ethernet28
  mtu 9216
exit
```

**Configure Et29:**
```bash
interface Ethernet29
  mtu 9216
exit
```

### Step 3: Verify VLAN 200 Configuration on All Ports

**Check VLAN 200 trunk configuration:**
```bash
# Should already be configured, but verify:
show vlan id 200

# If VLAN 200 is not on a port, add it:
# interface Ethernet<port>
#   switchport trunk allowed vlan add 200
# exit
```

**Expected:** VLAN 200 should be tagged on Et27, Et28, Et29, and Port-Channel1 (or Et25/26 if no port-channel yet).

### Step 4: Save Configuration

```bash
# Exit configuration mode
exit

# Save configuration
write memory
```

---

## Post-Change Verification

### 1. Verify MTU Configuration

**Check Port-Channel1:**
```bash
show interface Port-Channel1 | grep MTU

# Expected: MTU 9216 bytes
```

**Check Ethernet interfaces:**
```bash
show interface ethernet 25 | grep MTU
show interface ethernet 26 | grep MTU
show interface ethernet 27 | grep MTU
show interface ethernet 28 | grep MTU
show interface ethernet 29 | grep MTU

# Expected: MTU 9216 bytes on all
```

### 2. Verify Interfaces Are Still Up

```bash
show interface status | grep -E "(Et25|Et26|Et27|Et28|Et29|Po1)"

# All should show "connected" status
```

### 3. Verify VLAN 200 Configuration

```bash
show vlan id 200

# Should show:
# VLAN 200 active
# Tagged on Et27, Et28, Et29, Port-Channel1 (or Et26)
```

### 4. Check for Errors

```bash
show logging | grep -i mtu
show logging | grep -i error | tail -20

# Should not show any MTU-related errors
```

### 5. Verify Traffic Flow

```bash
# Check that traffic is still flowing
show interface Port-Channel1 counters rate
show interface ethernet 27 counters rate
show interface ethernet 28 counters rate
show interface ethernet 29 counters rate

# Should see some traffic (even if minimal)
```

### 6. Test Connectivity from Brocade

**On Brocade:**
```bash
# Ping across to verify link still works
ping 192.168.1.21

# Ping Proxmox-03 through VLAN 200
ping 10.200.0.3 source 10.200.0.254
```

---

## Rollback Plan

**If issues occur:**

### Quick Rollback

**On Arista:**
```bash
enable
configure

# Revert MTU to default on affected interface
interface Port-Channel1
  mtu 9214
exit

# Or revert to 1500 if that was original:
# mtu 1500

exit
write memory
```

### Full Rollback (All Interfaces)

```bash
enable
configure

# Revert all interfaces to previous MTU
interface Port-Channel1
  mtu 9214
exit

interface Ethernet27
  mtu 9214
exit

interface Ethernet28
  mtu 9214
exit

interface Ethernet29
  mtu 9214
exit

exit
write memory
```

---

## Troubleshooting

### Issue: Interface Goes Down After MTU Change

**Symptoms:**
- Interface status changes to "notconnect" after MTU change
- Traffic stops flowing

**Diagnosis:**
```bash
# Check interface status
show interface ethernet <port>

# Check for errors
show logging | grep -i ethernet<port>

# Check connected device (LLDP if available)
show lldp neighbors ethernet <port>
```

**Resolution:**
1. **MTU mismatch with connected device** - Ensure connected device also supports jumbo frames
2. **Try intermediate MTU** - Some devices need gradual MTU changes
3. **Revert to default** - If interface won't come up, revert MTU and investigate

### Issue: MTU Change Doesn't Take Effect

**Symptoms:**
- `show interface` still shows old MTU value
- Jumbo frame tests still fail

**Diagnosis:**
```bash
# Check if change was applied
show running-config interface Ethernet<port> | grep mtu

# Check if saved
show startup-config interface Ethernet<port> | grep mtu

# Verify interface is up
show interface ethernet <port> status
```

**Resolution:**
1. **Interface must be up** - MTU changes require interface to be up
2. **May need interface reset** - Try: `shutdown` then `no shutdown`
3. **Reboot as last resort** - MTU changes should not require reboot on Arista

### Issue: Jumbo Frames Still Fragmented

**Symptoms:**
- `ping -M do -s 8972` still fails after MTU change

**Diagnosis:**
```bash
# Verify MTU on entire path:

# 1. Source Proxmox host
ssh root@<proxmox-ip>
ip link show <interface> | grep mtu

# 2. Arista switch
show interface ethernet <port> | grep MTU

# 3. Brocade switch (if routing through Brocade)
show interface ve 200 | include mtu

# 4. Destination Proxmox host
ssh root@<proxmox-ip>
ip link show <interface> | grep mtu
```

**Resolution:**
- Ensure **all** interfaces in the path support MTU 9000+
- Check for intermediate switches/devices limiting MTU
- Verify physical layer (SFP+ modules, cables) support jumbo frames

---

## Why MTU 9216 on Arista?

**Question:** Why MTU 9216 instead of 9000?

**Answer:**
- **Application Layer (Ceph):** Uses 9000 byte payloads
- **VLAN Tagging:** Adds 4 bytes (802.1Q tag)
- **Ethernet Frame:** Adds additional overhead
- **Switch MTU:** Must be ≥ 9216 to handle 9000 + VLAN tag + overhead

**Breakdown:**
```
Application payload:     9000 bytes (Ceph data)
IP header:                 20 bytes
TCP header:                20 bytes
Ethernet header:           14 bytes
VLAN tag:                   4 bytes
Ethernet FCS:               4 bytes
                         -----
Total frame size:       9062 bytes
```

**Arista default:** 9214 bytes (should work, but 9216 is safer)

---

## Success Criteria

- [ ] MTU 9216 configured on Port-Channel1
- [ ] MTU 9216 configured on Et27, Et28, Et29
- [ ] All interfaces remain "Up" after MTU change
- [ ] VLAN 200 still present on all required interfaces
- [ ] No errors in logs related to MTU changes
- [ ] Connectivity tests pass (ping to Brocade, other switches)
- [ ] Traffic counters show normal operation
- [ ] Configuration saved to startup-config

---

## Network Path MTU Summary

**After Phase 3, MTU configuration should be:**

| Device | Interface | MTU | Purpose |
|--------|-----------|-----|---------|
| Brocade | VE200 | 9000 | VLAN 200 routing interface |
| Brocade | LAG 11 (1/2/1, 1/2/6) | 9000 | Brocade-Arista link |
| Arista | Port-Channel1 (Et25, Et26) | 9216 | Brocade link |
| Arista | Et27 | 9216 | Proxmox host link |
| Arista | Et28 | 9216 | Proxmox host link |
| Arista | Et29 | 9216 | Proxmox host link |
| Proxmox-03 | bond1 | 9000 | 10Gb bond to Brocade |
| Proxmox-03 | vmbr200 | 9000 | VLAN 200 bridge |
| Proxmox-01,02,04 | 40Gb NIC | 9000 | Direct to Arista (Phase 5) |

---

## Next Steps

Once Phase 3 is complete and verified:
- Proceed to **Phase 4**: Identify 40GB NICs on Proxmox hosts
- This involves connecting to each Proxmox host and determining which physical NIC is the 40Gb interface
- We'll also need to identify which Arista port (Et27, Et28, or Et29) each host is connected to

---

## Reference Commands

### Arista MTU Commands
```bash
# Show MTU on interface
show interface <interface> | grep MTU

# Show interface status
show interface status

# Configure MTU
configure
interface <interface>
  mtu <mtu-value>
exit

# Show running config for interface
show running-config interface <interface>
```

### Testing Jumbo Frames
```bash
# From Linux host (Proxmox)
# Test 9000 byte frames (9000 - 28 bytes for IP+ICMP headers)
ping -M do -s 8972 <destination-ip>

# From Arista (not directly supported)
# Need to test from endpoints (Proxmox hosts)
```

### Arista VLAN Commands
```bash
# Show VLAN configuration
show vlan
show vlan id <vlan-id>

# Show trunk ports
show interface trunk

# Add VLAN to trunk
configure
interface <interface>
  switchport trunk allowed vlan add <vlan-id>
exit
```
