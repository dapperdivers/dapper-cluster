# Network Operations Runbook

## Overview

This runbook provides step-by-step procedures for common network operations, troubleshooting, and emergency recovery scenarios for the Dapper Cluster network.

**Quick Reference:**
- [Network Topology Documentation](../architecture/network-topology.md)
- Brocade Core: 192.168.1.20
- Arista Distribution: 192.168.1.21
- Aruba Access: 192.168.1.26

---

## Table of Contents

1. [Common Operations](#common-operations)
2. [Troubleshooting Procedures](#troubleshooting-procedures)
3. [Emergency Procedures](#emergency-procedures)
4. [Switch Configuration](#switch-configuration)
5. [Performance Monitoring](#performance-monitoring)
6. [Maintenance Windows](#maintenance-windows)

---

## Common Operations

### Accessing Network Equipment

#### SSH to Switches

**Brocade ICX6610:**
```bash
ssh admin@192.168.1.20
# [TODO: Document default credentials location]
```

**Arista 7050:**
```bash
ssh admin@192.168.1.21
# [TODO: Document default credentials location]
```

**Aruba S2500-48p:**
```bash
ssh admin@192.168.1.26
# [TODO: Document default credentials location]
```

#### Console Access

**When SSH is unavailable:**
```bash
# [TODO: Document console server or direct serial access]
# Brocade: Serial settings [TODO: baud rate, etc]
# Arista: Serial settings [TODO: baud rate, etc]
```

### Checking Switch Health

#### Brocade ICX6610

```bash
# Basic health check
show version
show chassis
show cpu
show memory
show log tail 50

# Temperature and power
show inline power
show environment

# Check for errors
show logging | include error
show logging | include warn
```

#### Arista 7050

```bash
# Basic health check
show version
show environment all
show processes top

# Check for errors
show logging last 100
show logging | grep -i error
```

### Verifying VLAN Configuration

#### Check VLAN Assignments

**Brocade:**
```bash
show vlan

# Check specific VLAN
show vlan 100
show vlan 150
show vlan 200

# Check which ports are in which VLANs
show vlan ethernet 1/1/1
```

**Arista:**
```bash
show vlan

# Check VLAN details
show vlan id 200

# Show interfaces by VLAN
show interfaces status
```

#### Verify Trunk Ports

**Brocade:**
```bash
# Show trunk configuration
show interface brief | include Trunk

# Show specific trunk
show interface ethernet 1/1/41
show interface ethernet 1/1/42
```

**Arista:**
```bash
# Show trunk ports
show interface trunk

# Show specific interface
show interface ethernet 49
show interface ethernet 50
```

### Checking Link Aggregation (LAG) Status

#### Brocade LAG Status

```bash
# Show all LAG groups
show lag brief

# Show specific LAG details
show lag [lag-id]

# Show which ports are in LAG
show lag | include active

# Check individual LAG port status
show interface ethernet 1/1/41
show interface ethernet 1/1/42
```

**Expected Output When Working:**
```
LAG "brocade-to-arista" (lag-id [X]) has 2 active ports:
  ethernet 1/1/41 (40Gb) - Active
  ethernet 1/1/42 (40Gb) - Active
```

#### Arista Port-Channel Status

```bash
# Show port-channel summary
show port-channel summary

# Show specific port-channel
show interface port-channel 1

# Check member interfaces
show interface ethernet 49 port-channel
show interface ethernet 50 port-channel
```

**Expected Output When Working:**
```
Port-Channel1:
  Active Ports: 2
  Et49: Active
  Et50: Active
  Protocol: LACP
```

### Monitoring Traffic and Bandwidth

#### Real-Time Interface Statistics

**Brocade:**
```bash
# Show interface rates
show interface ethernet 1/1/41 | include rate
show interface ethernet 1/1/42 | include rate

# Show all interface statistics
show interface ethernet 1/1/41

# Monitor in real-time (if supported)
monitor interface ethernet 1/1/41
```

**Arista:**
```bash
# Show interface counters
show interface ethernet 49 counters

# Show interface rates
show interface ethernet 49 | grep rate

# Real-time monitoring
watch 1 show interface ethernet 49 counters rate
```

#### Identify Top Talkers

**Brocade:**
```bash
# [TODO: Document method to identify top talkers]
# May require SNMP monitoring or sFlow
```

**Arista:**
```bash
# Check interface utilization
show interface counters utilization

# If sFlow configured:
# [TODO: Document sFlow commands]
```

### Testing Connectivity

#### From Your Workstation

**Test Management Plane:**
```bash
# Ping all management interfaces
ping -c 4 192.168.1.20  # Brocade
ping -c 4 192.168.1.21  # Arista
ping -c 4 192.168.1.26  # Aruba
ping -c 4 192.168.1.7   # Mikrotik House
ping -c 4 192.168.1.8   # Mikrotik Shop

# Test wireless bridge latency
ping -c 100 192.168.1.8 | tail -3
```

**Test Server Network (VLAN 100):**
```bash
# Test Kubernetes nodes
ping -c 4 10.100.0.40   # K8s VIP
ping -c 4 10.100.0.50   # talos-control-1
ping -c 4 10.100.0.51   # talos-control-2
ping -c 4 10.100.0.52   # talos-control-3
```

**Test from Kubernetes Nodes:**
```bash
# SSH to a Talos node (if enabled) or use kubectl exec
kubectl exec -it -n default <pod-name> -- sh

# Test connectivity
ping 10.150.0.10   # Storage network
ping 10.100.0.1    # Gateway
ping 8.8.8.8       # Internet
```

#### MTU Testing (Jumbo Frames)

**Test VLAN 150/200 MTU 9000:**
```bash
# From a host on VLAN 150
ping -M do -s 8972 10.150.0.10

# -M do: Don't fragment
# -s 8972: 8972 + 28 (IP+ICMP headers) = 9000

# If this fails but smaller packets work, MTU is misconfigured
```

#### Path Testing

**Trace route across networks:**
```bash
# From your workstation
traceroute 10.100.0.50

# Expected path (if everything is working):
# 1. Local gateway
# 2. Wireless bridge
# 3. Brocade/OPNsense
# 4. Destination
```

---

## Troubleshooting Procedures

### Issue: No Connectivity to Garage Switches

**Symptoms:**
- Cannot ping/SSH to Brocade (192.168.1.20) or Arista (192.168.1.21)
- Can ping Aruba switch (192.168.1.26)

**Diagnosis:**

1. **Test wireless bridge:**
   ```bash
   ping 192.168.1.7   # Mikrotik House
   ping 192.168.1.8   # Mikrotik Shop
   ```

   - If 192.168.1.7 responds but 192.168.1.8 doesn't: **Wireless link down**
   - If neither respond: **Mikrotik issue or config problem**

2. **Check Aruba-to-Mikrotik connection:**
   ```bash
   # SSH to Aruba
   ssh admin@192.168.1.26

   # Check port status for Mikrotik connection
   show interface [TODO: port ID]
   ```

**Resolution:**

**If wireless bridge is down:**
1. Check Mikrotik radios web interface (192.168.1.7, 192.168.1.8)
2. Check alignment and signal strength
3. Verify power to both radios
4. Check for interference (weather, obstacles)
5. **Emergency:** Use physical console access to switches in garage

**If Mikrotik is up but switches unreachable:**
1. Check VLAN 1 configuration on trunk ports
2. Verify Mikrotik is not blocking traffic
3. Check Brocade port connected to Mikrotik is up

### Issue: Kubernetes Pods Can't Access Storage

**Symptoms:**
- Pods stuck in `ContainerCreating`
- PVC stuck in `Pending`
- Errors about unable to mount CephFS

**Diagnosis:**

1. **Check Rook/Ceph health:**
   ```bash
   kubectl -n rook-ceph get cephcluster
   kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph status
   ```

2. **Check network connectivity from Kubernetes nodes to Ceph monitors:**
   ```bash
   # From a Talos node or debug pod
   ping 10.150.0.10   # Test VLAN 150 connectivity

   # Test Ceph monitor port
   nc -zv <monitor-ip> 6789
   ```

3. **Verify VLAN 150 MTU:**
   ```bash
   # Test jumbo frames
   ping -M do -s 8972 10.150.0.10
   ```

4. **Check CSI driver logs:**
   ```bash
   kubectl -n rook-ceph logs -l app=csi-cephfsplugin --tail=100
   ```

**Resolution:**

**If MTU mismatch:**
1. Verify MTU 9000 on all VLAN 150 interfaces
2. Check Proxmox bridge MTU settings
3. Check switch port MTU configuration

**If connectivity issue:**
1. Check VLAN 150 is properly tagged on trunk ports
2. Verify Proxmox host network configuration
3. Check Brocade routing for VLAN 150

### Issue: Slow Ceph Performance

**Symptoms:**
- Slow pod startup times
- High I/O latency in applications
- Ceph health warnings about slow ops

**Diagnosis:**

1. **Check Ceph cluster health:**
   ```bash
   kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph health detail
   kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph osd perf
   ```

2. **Check network bandwidth utilization:**

   **On Brocade (VLAN 150 - Ceph Public):**
   ```bash
   # Check 10Gb bonds to Proxmox hosts
   show interface ethernet 1/1/[TODO: ports] | include rate
   ```

   **On Arista (VLAN 200 - Ceph Cluster):**
   ```bash
   # Check 40Gb links to Proxmox hosts
   show interface ethernet [TODO: ports] counters rate
   ```

3. **Identify bottlenecks:**
   - Are 10Gb links saturated? (VLAN 150)
   - Are 40Gb links saturated? (VLAN 200)
   - Is the Brocade-Arista link saturated?

**Resolution:**

**If Brocade-Arista link is bottleneck:**
- **Primary Issue:** Only one 40Gb link active (see below to enable second link)
- Enabling second 40Gb link will double bandwidth to 80Gbps

**If MTU not configured:**
- Verify MTU 9000 on VLAN 150 and 200
- Check each hop in the path

**If switch CPU is high:**
- Check for broadcast storms
- Verify STP is working correctly
- Look for loops in topology

### Issue: Network Loop / Broadcast Storm

**Symptoms:**
- Network performance severely degraded
- High CPU usage on switches
- Connectivity flapping
- Massive packet rates on interfaces

**Diagnosis:**

1. **Check for duplicate MAC addresses:**
   ```bash
   # Brocade
   show mac-address

   # Look for same MAC on multiple ports
   ```

2. **Check STP status:**
   ```bash
   # Brocade
   show spanning-tree

   # Arista
   show spanning-tree
   ```

3. **Look for physical loops:**
   - Review physical topology diagram
   - Check for accidental double connections
   - **Known issue:** Brocade-Arista 2x 40Gb links not in LAG

**Resolution:**

**Immediate (Emergency):**
1. **Disable one link causing loop:**
   ```bash
   # On Arista (already done in current config)
   configure
   interface ethernet 50
   shutdown
   ```

2. **Verify spanning-tree is enabled:**
   ```bash
   # Brocade
   show spanning-tree

   # If not enabled:
   configure terminal
   spanning-tree
   ```

**Permanent Fix:**
- Configure proper LAG/port-channel (see section below)

### Issue: Proxmox Host Loses Network Connectivity

**Symptoms:**
- Cannot ping Proxmox host management IP
- VMs on host also offline
- IPMI still accessible

**Diagnosis:**

1. **Access via IPMI console:**
   ```bash
   # [TODO: Document IPMI access method]
   ```

2. **Check bond status on Proxmox:**
   ```bash
   # From Proxmox console
   ip link show

   # Check bond interfaces
   cat /proc/net/bonding/bond0
   cat /proc/net/bonding/bond1
   ```

3. **Check switch ports:**
   ```bash
   # On Brocade
   show interface ethernet 1/1/[TODO: ports for this host]
   show lag [TODO: lag-id for this host]
   ```

**Resolution:**

**If bond is down on Proxmox:**
1. Check physical cables
2. Restart networking on Proxmox (WARNING: will disrupt VMs)
3. Check switch port status

**If ports down on switch:**
1. Check for error counters
2. Re-enable port if administratively down
3. Check for physical issues (SFP, cable)

### Issue: High Latency Across Wireless Bridge

**Symptoms:**
- Ping times to garage > 10ms (normally 1-2ms)
- Slow access to services in garage
- Packet loss

**Diagnosis:**

1. **Test latency:**
   ```bash
   ping -c 100 192.168.1.8

   # Look at:
   # - Average latency
   # - Packet loss %
   # - Jitter (variation)
   ```

2. **Check Mikrotik radio status:**
   - Access web interface: 192.168.1.7 and 192.168.1.8
   - Check signal strength
   - Check throughput/bandwidth utilization
   - Look for interference

3. **Test with iperf:**
   ```bash
   # On server side (garage)
   iperf3 -s

   # On client side (house)
   iperf3 -c 192.168.1.8 -t 30

   # Should see ~1 Gbps
   ```

**Resolution:**

**If signal degraded:**
1. Check for obstructions (trees, weather)
2. Check alignment
3. Check for interference sources
4. Consider backup link or failover

**If bandwidth saturated:**
1. Identify high-bandwidth users/applications
2. Implement QoS if available
3. Consider upgrade to higher bandwidth link

---

## Emergency Procedures

### Complete Network Outage (Wireless Bridge Down)

**Impact:**
- No remote access to garage infrastructure
- Kubernetes cluster still functions internally
- No internet access from garage
- Management access requires physical presence

**Emergency Access Methods:**

1. **Physical console access:**
   ```bash
   # [TODO: Document where console cables are stored]
   # Connect laptop directly to switch console port
   ```

2. **IPMI access (if VPN or alternative route exists):**
   ```bash
   # [TODO: Document IPMI network topology]
   ```

**Restoration Steps:**

1. **Check Mikrotik radios:**
   - Physical inspection of both radios
   - Power cycle if needed
   - Check alignment

2. **Temporary workaround:**
   - [TODO: Document backup connectivity method]
   - VPN tunnel over alternative route?
   - Temporary cable run?

3. **Verify restoration:**
   ```bash
   ping 192.168.1.8
   ping 192.168.1.20
   ssh admin@192.168.1.20
   ```

### Core Switch (Brocade) Failure

**Impact:**
- Loss of VLAN 150/200 routing
- Kubernetes cluster degraded (storage issues)
- Loss of 10Gb connectivity to Proxmox hosts

**Emergency Actions:**

1. **Do NOT reboot all Proxmox hosts simultaneously**
   - Cluster may be operational on running workloads
   - Storage connections via VLAN 200 through Arista may still work

2. **Check Brocade status:**
   - Physical inspection (power, fans, LEDs)
   - Console access
   - Review logs

3. **If Brocade must be replaced:**
   - [TODO: Document backup configuration location]
   - [TODO: Document restoration procedure]
   - [TODO: Document spare hardware location]

### Spanning Tree Failure / Network Loop

**Impact:**
- Network completely unusable
- High CPU on all switches
- Broadcast storm

**Emergency Actions:**

1. **Disconnect Brocade-Arista links:**
   ```bash
   # On Arista (fastest access if SSH still works)
   configure
   interface ethernet 49
   shutdown
   interface ethernet 50
   shutdown
   ```

2. **Or physically disconnect:**
   - Unplug both 40Gb QSFP+ cables between Brocade and Arista

3. **Wait for network to stabilize** (30-60 seconds)

4. **Reconnect ONE link only:**
   ```bash
   # On Arista
   configure
   interface ethernet 49
   no shutdown
   ```

5. **Verify stability before enabling second link**

### Accidental Configuration Change

**Symptoms:**
- Network suddenly degraded after change
- New errors appearing
- Connectivity loss

**Emergency Actions:**

1. **Rollback configuration:**

   **Brocade:**
   ```bash
   # Show configuration history
   show configuration

   # Revert to previous config
   # [TODO: Document Brocade config rollback method]
   ```

   **Arista:**
   ```bash
   # Show rollback options
   show configuration sessions

   # Rollback to previous
   configure session rollback <session-name>
   ```

2. **If rollback not available:**
   - Reboot switch (loads startup-config)
   - WARNING: Brief outage during reboot

---

## Switch Configuration

### Configure Brocade-Arista LAG (Fix Loop Issue)

**Prerequisites:**
- Maintenance window scheduled
- Both 40Gb QSFP+ cables connected and working
- Console access to both switches available
- Configuration backed up

**Step 1: Pre-Change Verification**

```bash
# Verify current state
# On Brocade:
show interface ethernet 1/1/41
show interface ethernet 1/1/42

# On Arista:
show interface ethernet 49
show interface ethernet 50  # Currently disabled

# Document current traffic levels
show interface ethernet 1/1/41 | include rate
```

**Step 2: Configure Brocade LAG**

```bash
# SSH to Brocade
ssh admin@192.168.1.20

# Enter configuration mode
enable
configure terminal

# Create LAG
lag brocade-to-arista dynamic id [TODO: Choose available LAG ID, e.g., 10]
  ports ethernet 1/1/41 to 1/1/42
  primary-port 1/1/41
  lacp-timeout short
  deploy
exit

# Configure VLAN on LAG
vlan 1
  tagged lag [LAG-ID]
exit

vlan 100
  tagged lag [LAG-ID]
exit

vlan 150
  tagged lag [LAG-ID]
exit

vlan 200
  tagged lag [LAG-ID]
exit

# Apply to interfaces
interface ethernet 1/1/41
  link-aggregate active
exit

interface ethernet 1/1/42
  link-aggregate active
exit

# Save configuration
write memory

# Verify
show lag brief
show lag [LAG-ID]
```

**Step 3: Configure Arista Port-Channel**

```bash
# SSH to Arista
ssh admin@192.168.1.21

# Enter configuration mode
enable
configure

# Create port-channel
interface Port-Channel1
  description Link to Brocade ICX6610
  switchport mode trunk
  switchport trunk allowed vlan 1,100,150,200
exit

# Add member interfaces
interface Ethernet49
  description Brocade 40G Link 1
  channel-group 1 mode active
  lacp rate fast
exit

interface Ethernet50
  description Brocade 40G Link 2
  channel-group 1 mode active
  lacp rate fast
exit

# Save configuration
write memory

# Verify
show port-channel summary
show interface Port-Channel1
show lacp neighbor
```

**Step 4: Verify Configuration**

```bash
# On Brocade:
show lag [LAG-ID]
# Should show: 2 ports active

show lacp
# Should show: Negotiated with neighbor

# On Arista:
show port-channel summary
# Should show: Po1(U) with Et49(P), Et50(P)

show lacp neighbor
# Should show: Brocade as partner

# Test traffic balancing
show interface Port-Channel1 counters
show interface ethernet 49 counters
show interface ethernet 50 counters
# Both Et49 and Et50 should show traffic
```

**Step 5: Monitor for Issues**

```bash
# Watch for 15 minutes
# On Arista:
watch 10 show port-channel summary

# Check for errors
show logging | grep -i Port-Channel1

# Monitor CPU (should be normal)
show processes top
```

**Rollback Plan (if issues occur):**

```bash
# On Arista (fastest to disable)
configure
interface ethernet 50
shutdown

# On Brocade (if needed)
configure terminal
no lag brocade-to-arista
interface ethernet 1/1/41
  no link-aggregate
interface ethernet 1/1/42
  no link-aggregate
```

### Adding a New VLAN

**Example: Adding VLAN 300 for IoT devices**

**Step 1: Plan VLAN**
- VLAN ID: 300
- Network: [TODO: e.g., 10.30.0.0/24]
- Gateway: [TODO: Which device?]
- Required on: [TODO: Which switches/trunks?]

**Step 2: Create VLAN on Brocade**

```bash
ssh admin@192.168.1.20
enable
configure terminal

# Create VLAN
vlan 300
  name IoT-Network
  tagged ethernet 1/1/41 to 1/1/42  # Trunk to Arista
  tagged ethernet 1/1/[TODO]         # Trunk to Mikrotik
  untagged ethernet 1/1/[TODO]       # Access ports if needed
exit

# If Brocade is gateway:
interface ve 300
  ip address [TODO: IP]/24
exit

# Save
write memory
```

**Step 3: Add to other switches as needed**

```bash
# On Arista:
configure
vlan 300
  name IoT-Network
exit

interface Port-Channel1
  switchport trunk allowed vlan add 300
exit

write memory
```

### Configuring Jumbo Frames (MTU 9000)

**For VLAN 150 and 200 (Ceph networks)**

**On Brocade:**

```bash
# Configure MTU on VLAN interfaces
interface ve 150
  mtu 9000
exit

interface ve 200
  mtu 9000
exit

# Configure MTU on physical/LAG interfaces
interface ethernet 1/1/[TODO: storage network ports]
  mtu 9000
exit

write memory
```

**On Arista:**

```bash
# Configure MTU on interfaces carrying VLAN 150/200
interface ethernet [TODO: ports]
  mtu 9216  # 9000 + overhead
exit

write memory
```

**Verify MTU:**

```bash
# From Talos node
ping -M do -s 8972 10.150.0.10
# Should succeed without fragmentation
```

---

## Performance Monitoring

### Key Metrics to Monitor

**Switch Health:**
- CPU utilization (should be <30% normally)
- Memory utilization (should be <70%)
- Temperature (within operating range)
- Power supply status

**Interface Health:**
- Error counters (input/output errors)
- CRC errors
- Interface resets
- Utilization percentage

**Traffic Patterns:**
- Bandwidth utilization per interface
- Top talkers per VLAN
- Broadcast/multicast rates

### Setting Up Monitoring

**[TODO: Document monitoring setup]**

**Options:**
1. SNMP monitoring to Prometheus
2. sFlow for traffic analysis
3. Switch logging to Loki
4. Grafana dashboards

**Example Prometheus Targets:**
```yaml
# [TODO: Example prometheus config for SNMP exporter]
```

### Baseline Performance Metrics

**Normal Operating Conditions:**

| Metric | Expected Value | Alert Threshold |
|--------|---------------|-----------------|
| Wireless Bridge Latency | 1-2ms | > 5ms |
| Wireless Bridge Loss | 0% | > 1% |
| Brocade CPU | < 20% | > 60% |
| Arista CPU | < 15% | > 50% |
| 40Gb Link Utilization | < 50% | > 80% |
| 10Gb Link Utilization | < 60% | > 85% |

**[TODO: Add baseline measurements]**

---

## Maintenance Windows

### Pre-Maintenance Checklist

**Before any network maintenance:**

- [ ] Schedule maintenance window
- [ ] Notify all users
- [ ] Back up switch configurations
  ```bash
  # Brocade
  show running-config > backup-$(date +%Y%m%d).cfg

  # Arista
  show running-config > backup-$(date +%Y%m%d).cfg
  ```
- [ ] Document current state
- [ ] Have rollback plan ready
- [ ] Ensure console access available
- [ ] Test backup connectivity method

### Post-Maintenance Checklist

**After any network maintenance:**

- [ ] Verify all links are up
  ```bash
  show interface brief
  show lag brief  # Brocade
  show port-channel summary  # Arista
  ```
- [ ] Check for errors
  ```bash
  show logging | include error
  ```
- [ ] Test connectivity to all VLANs
- [ ] Monitor for 30 minutes for issues
- [ ] Update documentation with any changes
- [ ] Save configurations
  ```bash
  write memory
  ```

### Regular Maintenance Tasks

**Weekly:**
- Review switch logs for errors/warnings
- Check interface error counters
- Verify wireless bridge performance

**Monthly:**
- Review bandwidth utilization trends
- Check for firmware updates
- Verify backup configurations are current

**Quarterly:**
- Review and update network documentation
- Test emergency procedures
- Review and optimize switch configurations

---

## Configuration Backup

### Backing Up Switch Configurations

**Brocade ICX6610:**

```bash
# Method 1: Copy to TFTP server
copy running-config tftp [TODO: TFTP server IP] brocade-backup-$(date +%Y%m%d).cfg

# Method 2: Display and save manually
show running-config > /tmp/brocade-config.txt

# [TODO: Document automated backup method]
```

**Arista 7050:**

```bash
# Show running config
show running-config

# Copy to USB (if available)
copy running-config usb:/brocade-backup-$(date +%Y%m%d).cfg

# [TODO: Document automated backup method]
```

**Storage Location:**
- [TODO: Document where configurations are backed up]
- Consider: Git repository for version control
- Consider: Automated daily backups via Ansible

### Restoring Configurations

**Brocade:**

```bash
# Load config from file
copy tftp running-config [TFTP-IP] [filename]

# Or manually paste config
configure terminal
# Paste configuration
```

**Arista:**

```bash
# Copy config from file
copy usb:/backup.cfg running-config

# Or configure manually
configure
# Paste configuration
```

---

## Security Considerations

### Access Control

**[TODO: Document security policies]**

- Who has access to switch management?
- How are credentials managed?
- Is 2FA available/configured?
- Are management VLANs isolated?

### Security Best Practices

1. **Change default passwords**
2. **Disable unused ports**
3. **Enable port security where appropriate**
4. **Configure DHCP snooping**
5. **Enable storm control**
6. **Regular firmware updates**
7. **Monitor for unauthorized devices**

---

## Useful Commands Reference

### Brocade ICX6610 Quick Reference

```bash
# Basic show commands
show version
show running-config
show interface brief
show vlan
show lag
show mac-address
show spanning-tree
show log

# Interface management
interface ethernet 1/1/1
  enable
  disable
  description [text]

# Save configuration
write memory
```

### Arista 7050 Quick Reference

```bash
# Basic show commands
show version
show running-config
show interfaces status
show vlan
show port-channel summary
show mac address-table
show spanning-tree
show logging

# Interface management
configure
interface ethernet 1
  shutdown
  no shutdown
  description [text]

# Save configuration
write memory
```

---

## Contacts and Escalation

**[TODO: Fill in contact information]**

| Role | Name | Contact | Escalation Level |
|------|------|---------|-----------------|
| Primary Network Admin | [TODO] | [TODO] | 1 |
| Secondary Contact | [TODO] | [TODO] | 2 |
| Vendor Support - Brocade | [TODO] | [TODO] | 3 |
| Vendor Support - Arista | [TODO] | [TODO] | 3 |

---

## Change Log

| Date | Change | Person | Impact | Notes |
|------|--------|--------|--------|-------|
| 2025-10-14 | Initial runbook created | Claude | None | Baseline documentation |
| [TODO] | [TODO] | [TODO] | [TODO] | [TODO] |

---

## References

- [Network Topology Documentation](../architecture/network-topology.md)
- [Storage Architecture](../architecture/storage.md) - For Ceph network details
- Brocade ICX6610 Documentation: [TODO: Link]
- Arista 7050 Documentation: [TODO: Link]
- [TODO: Add other relevant documentation links]
