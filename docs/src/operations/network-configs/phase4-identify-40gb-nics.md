# Phase 4: Identify 40GB NICs on Proxmox Hosts

## Overview

This phase identifies which physical network interfaces on Proxmox hosts are the 40Gb NICs and maps them to the Arista switch ports. This information is required before reconfiguring the hosts to use the 40Gb links for VLAN 200.

**Scope:**
- Proxmox-01: Has 40Gb link to Arista
- Proxmox-02: Has 40Gb link to Arista
- Proxmox-04: Has 40Gb link to Arista
- **Proxmox-03: Does NOT have 40Gb link (will keep using 10Gb bond)**

**Goal:**
- Identify physical interface name for 40Gb NIC on each host (e.g., `enp2s0`, `ens10f0`, etc.)
- Determine which Arista port (Et27, Et28, or Et29) each host is connected to
- Verify the 40Gb link is not currently in use (no IP, not in bond)
- Document MAC addresses for tracking

---

## Pre-Discovery Information

From the Proxmox host interface listings, we can see potential 40Gb interfaces:

**Proxmox-01 (Tower/Circe):**
```
enp2s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP
  - Shows as UP but not in bond
  - Potential 40Gb interface
```

**Proxmox-02 (Athena):**
```
enp7s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP
  - Shows as UP but not in bond
  - Potential 40Gb interface
```

**Proxmox-04:**
```
enp7s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP
  - Shows as UP but not in bond
  - Potential 40Gb interface
```

**Proxmox-03:**
```
No 40Gb interface available (will use 10Gb bond)
```

---

## Discovery Procedure

### Step 1: Identify Network Interfaces on Each Host

For each Proxmox host (01, 02, 04), run the following commands:

#### Connect to Proxmox Host

**Proxmox-01:**
```bash
ssh root@192.168.1.62
```

**Proxmox-02:**
```bash
ssh root@192.168.1.63
```

**Proxmox-04:**
```bash
ssh root@192.168.1.66
```

#### List All Network Interfaces

```bash
# List all interfaces with details
ip link show

# Get interface speeds (requires ethtool)
for iface in $(ls /sys/class/net/ | grep -v lo); do
  echo "=== $iface ==="
  ethtool $iface 2>/dev/null | grep -E "(Speed:|Link detected:|Supported link modes:)" || echo "No ethtool info"
done
```

#### Identify 40Gb Capable Interface

```bash
# Check for 40Gb interfaces specifically
for iface in $(ls /sys/class/net/ | grep -v lo); do
  speed=$(ethtool $iface 2>/dev/null | grep "Speed:" | awk '{print $2}')
  if [[ "$speed" == *"40"* ]] || [[ "$speed" == *"Unknown"* ]]; then
    echo "=== $iface ==="
    echo "Speed: $speed"
    ethtool $iface 2>/dev/null | grep "Link detected:"
    cat /sys/class/net/$iface/address  # MAC address
  fi
done
```

#### Check Current Interface Usage

```bash
# Check if interface is in a bond
for iface in $(ls /sys/class/net/ | grep -v lo); do
  if [ -L "/sys/class/net/$iface/master" ]; then
    master=$(basename $(readlink /sys/class/net/$iface/master))
    echo "$iface -> $master"
  fi
done

# Check if interface has an IP
ip addr show | grep -E "^[0-9]+:|inet "
```

#### Document Interface Details

For each potential 40Gb interface, record:
```bash
iface="<interface-name>"  # e.g., enp2s0

echo "Interface: $iface"
echo "MAC Address: $(cat /sys/class/net/$iface/address)"
echo "Speed: $(ethtool $iface 2>/dev/null | grep Speed:)"
echo "Link Status: $(ethtool $iface 2>/dev/null | grep 'Link detected:')"
echo "Current Config:"
ip addr show $iface
echo "In Bond: $([ -L /sys/class/net/$iface/master ] && echo Yes || echo No)"
echo "PCI Address: $(basename $(readlink /sys/class/net/$iface/device 2>/dev/null) 2>/dev/null)"
```

---

### Step 2: Map Interfaces to Arista Ports

#### Method 1: Using LLDP (if enabled)

**On Proxmox host:**
```bash
# Check if lldpd is installed
which lldpctl

# If not installed:
apt update && apt install lldpd -y

# Start LLDP daemon
systemctl start lldpd
sleep 10  # Wait for LLDP discovery

# Show LLDP neighbors
lldpctl show neighbors
```

**Expected output:**
```
Interface: enp2s0
  Chassis:
    ChassisID:    mac 44:4c:a8:15:e0:f7
    SysName:      arista-7050
  Port:
    PortID:       ifname Ethernet27
```

This tells you which Arista port the interface is connected to!

#### Method 2: Using MAC Address Tracking

**On Arista:**
```bash
ssh admin@192.168.1.21

# Show MAC addresses learned on each port
show mac address-table

# Filter for specific ports
show mac address-table interface ethernet 27
show mac address-table interface ethernet 28
show mac address-table interface ethernet 29
```

**On Proxmox host:**
```bash
# Get MAC address of 40Gb interface
cat /sys/class/net/<interface>/address
```

**Match the MAC:** Find which Arista port has learned the Proxmox interface's MAC address.

#### Method 3: Link Flap Test

**Warning:** This will briefly interrupt the link!

**On Proxmox host:**
```bash
# Note which interface you're testing
iface="enp2s0"

# Bring interface down and up
ip link set $iface down
sleep 2
ip link set $iface up
```

**On Arista (watch for link flaps):**
```bash
# Watch interface status
watch -n 1 'show interface status | grep -E "(Et27|Et28|Et29)"'

# Or check logs
show logging | grep -i "Ethernet2[7-9]" | tail -20
```

The interface that flapped is the one connected to that Proxmox host!

---

### Step 3: Document Findings

Create a mapping table:

| Proxmox Host | Management IP | Interface Name | MAC Address | Speed | Arista Port | PCI Address |
|--------------|---------------|----------------|-------------|-------|-------------|-------------|
| Proxmox-01   | 192.168.1.62  | ________ | __________ | 40Gb  | Et27/28/29? | ________ |
| Proxmox-02   | 192.168.1.63  | ________ | __________ | 40Gb  | Et27/28/29? | ________ |
| Proxmox-04   | 192.168.1.66  | ________ | __________ | 40Gb  | Et27/28/29? | ________ |
| Proxmox-03   | 192.168.1.64  | N/A (no 40Gb) | N/A       | N/A   | N/A         | N/A      |

**Example filled:**
| Proxmox Host | Management IP | Interface Name | MAC Address | Speed | Arista Port | PCI Address |
|--------------|---------------|----------------|-------------|-------|-------------|-------------|
| Proxmox-01   | 192.168.1.62  | enp2s0         | 24:be:05:cd:ed:51 | 40Gb | Et27 | 0000:02:00.0 |
| Proxmox-02   | 192.168.1.63  | enp7s0         | 80:c1:6e:09:31:80 | 40Gb | Et28 | 0000:07:00.0 |
| Proxmox-04   | 192.168.1.66  | enp7s0         | 00:02:c9:42:76:a0 | 40Gb | Et29 | 0000:07:00.0 |

---

### Step 4: Verify Interface is Ready for Configuration

For each 40Gb interface, verify:

**Check interface is UP:**
```bash
ip link show <interface> | grep "state UP"
```

**Check interface has no IP configured:**
```bash
ip addr show <interface> | grep inet
# Should return nothing
```

**Check interface is not in a bond:**
```bash
[ -L /sys/class/net/<interface>/master ] && echo "IN BOND - STOP!" || echo "Not in bond - OK"
```

**Check interface is not part of a bridge:**
```bash
bridge link show | grep <interface>
# Should return nothing
```

**Check physical link is UP:**
```bash
ethtool <interface> | grep "Link detected:"
# Should show: Link detected: yes
```

**If any of these checks fail:**
- **Interface has IP:** Remove IP before proceeding
- **Interface in bond:** Remove from bond first (requires network reconfiguration)
- **Interface in bridge:** Remove from bridge first
- **Link not detected:** Check cable, SFP+ module, Arista port status

---

## Troubleshooting

### Issue: Cannot Determine Interface Speed

**Symptoms:**
- `ethtool <interface> | grep Speed` shows "Unknown" or fails

**Diagnosis:**
```bash
# Check if interface is down
ip link show <interface>

# Check driver
ethtool -i <interface>

# Check link status
ethtool <interface>
```

**Resolution:**
1. **Interface must be UP** to show speed: `ip link set <interface> up`
2. **May need to trigger auto-negotiation:** `ethtool -r <interface>`
3. **Check module compatibility:** Some SFP+ modules don't report speed properly

### Issue: LLDP Not Working

**Symptoms:**
- `lldpctl` shows no neighbors

**Diagnosis:**
```bash
# Check lldpd is running
systemctl status lldpd

# Check interface is UP
ip link show <interface>

# Check Arista has LLDP enabled
# On Arista:
show lldp neighbors
```

**Resolution:**
1. Ensure lldpd is installed and running
2. Wait 30-60 seconds for LLDP discovery
3. Check if Arista has LLDP enabled globally
4. Use alternate method (MAC tracking or link flap)

### Issue: Multiple Interfaces Show 40Gb

**Symptoms:**
- More than one interface per host shows 40Gb speed

**Diagnosis:**
```bash
# Check which interfaces are physically connected
for iface in $(ls /sys/class/net/ | grep -E "^en"); do
  link=$(cat /sys/class/net/$iface/carrier 2>/dev/null || echo 0)
  echo "$iface: carrier=$link"
done
```

**Resolution:**
- Only one should have `carrier=1` (link detected)
- If multiple show link, check which is **not** in bond0/bond1
- Use LLDP or MAC tracking to definitively identify

### Issue: Cannot Find 40Gb Interface

**Symptoms:**
- No interface shows 40Gb speed

**Diagnosis:**
```bash
# List all network interfaces
ls /sys/class/net/

# Check PCI devices
lspci | grep -i ethernet

# Check all interface speeds
for iface in $(ls /sys/class/net/ | grep -v lo); do
  echo "=== $iface ==="
  ethtool $iface 2>/dev/null | grep -E "(Speed:|Supported link modes:)"
done
```

**Resolution:**
1. **Interface may be down:** Try bringing up unused interfaces
2. **Driver not loaded:** Check `dmesg | grep -i nic`
3. **Actually doesn't have 40Gb:** Verify physical hardware inventory
4. **SFP+ module not installed:** Check physical card

---

## Success Criteria

- [ ] Identified 40Gb interface name on Proxmox-01
- [ ] Identified 40Gb interface name on Proxmox-02
- [ ] Identified 40Gb interface name on Proxmox-04
- [ ] Mapped each Proxmox host to Arista port (Et27, Et28, Et29)
- [ ] Verified each 40Gb interface is:
  - [ ] UP (carrier detected)
  - [ ] Not in a bond
  - [ ] Not in a bridge
  - [ ] Has no IP configured
  - [ ] Shows 40Gb link speed
- [ ] Documented MAC addresses for each 40Gb interface
- [ ] Created mapping table for reference

---

## Documentation Template

Create a file: `docs/src/operations/network-configs/proxmox-40gb-interface-mapping.md`

```markdown
# Proxmox 40Gb Interface Mapping

**Last Updated:** [DATE]

## Interface Details

### Proxmox-01 (192.168.1.62)
- **Hostname:** [From Brocade: Tower/Circe/Athena?]
- **40Gb Interface:** enp2s0 (or actual interface found)
- **MAC Address:** XX:XX:XX:XX:XX:XX
- **PCI Address:** 0000:02:00.0
- **Connected to:** Arista Et27 (or actual port)
- **Speed:** 40000Mb/s
- **Current Status:** Not configured (ready for Phase 5)

### Proxmox-02 (192.168.1.63)
- **Hostname:** [From Brocade: Tower/Circe/Athena?]
- **40Gb Interface:** enp7s0 (or actual interface found)
- **MAC Address:** XX:XX:XX:XX:XX:XX
- **PCI Address:** 0000:07:00.0
- **Connected to:** Arista Et28 (or actual port)
- **Speed:** 40000Mb/s
- **Current Status:** Not configured (ready for Phase 5)

### Proxmox-04 (192.168.1.66)
- **Hostname:** [Px04 from Brocade]
- **40Gb Interface:** enp7s0 (or actual interface found)
- **MAC Address:** XX:XX:XX:XX:XX:XX
- **PCI Address:** 0000:07:00.0
- **Connected to:** Arista Et29 (or actual port)
- **Speed:** 40000Mb/s
- **Current Status:** Not configured (ready for Phase 5)

### Proxmox-03 (192.168.1.64)
- **Hostname:** Px03
- **40Gb Interface:** N/A (no 40Gb link installed yet)
- **VLAN 200 Configuration:** Using bond1 (2x 10Gb) to Brocade
- **Status:** Configured in Phase 2 with routing through Brocade

## Arista Port Mapping

| Arista Port | Proxmox Host | Interface | MAC Address |
|-------------|--------------|-----------|-------------|
| Ethernet27  | Proxmox-0X   | enpXsX    | XX:XX:XX:XX:XX:XX |
| Ethernet28  | Proxmox-0X   | enpXsX    | XX:XX:XX:XX:XX:XX |
| Ethernet29  | Proxmox-0X   | enpXsX    | XX:XX:XX:XX:XX:XX |

## Verification Commands

### Check Link Status on Arista
\`\`\`bash
ssh admin@192.168.1.21
show interface status | grep -E "(Et27|Et28|Et29)"
show mac address-table interface ethernet 27
show mac address-table interface ethernet 28
show mac address-table interface ethernet 29
\`\`\`

### Check Interface Status on Proxmox
\`\`\`bash
# Proxmox-01
ssh root@192.168.1.62
ip link show enp2s0  # or actual interface
ethtool enp2s0 | grep -E "(Speed:|Link detected:)"

# Proxmox-02
ssh root@192.168.1.63
ip link show enp7s0  # or actual interface
ethtool enp7s0 | grep -E "(Speed:|Link detected:)"

# Proxmox-04
ssh root@192.168.1.66
ip link show enp7s0  # or actual interface
ethtool enp7s0 | grep -E "(Speed:|Link detected:)"
\`\`\`
```

---

## Next Steps

Once Phase 4 is complete with all interfaces identified and documented:
- Proceed to **Phase 5**: Reconfigure Proxmox hosts to use 40GB links for VLAN 200
- Use the mapping created in this phase to configure each host correctly
- Phase 5 will create new vmbr200 bridges on the 40Gb interfaces

---

## Reference Commands

### Ethtool Commands
```bash
# Show interface speed and link status
ethtool <interface>

# Show only speed
ethtool <interface> | grep Speed

# Show driver info
ethtool -i <interface>

# Restart auto-negotiation
ethtool -r <interface>
```

### IP Commands
```bash
# Show all interfaces
ip link show

# Show interface details
ip link show <interface>

# Bring interface up
ip link set <interface> up

# Show IP configuration
ip addr show <interface>

# Check if interface is in bond
[ -L /sys/class/net/<interface>/master ] && echo "In bond" || echo "Not in bond"
```

### LLDP Commands
```bash
# Install lldpd
apt install lldpd

# Show LLDP neighbors
lldpctl show neighbors

# Show detailed info
lldpctl show neighbors ports <interface>
```
