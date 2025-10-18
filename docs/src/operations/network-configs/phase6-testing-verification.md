# Phase 6: Testing and Verification

## Overview

This phase performs comprehensive testing and verification of the complete 40GB Ceph storage network configuration. It ensures all components are working correctly, validates performance improvements, and confirms the system is production-ready.

**Scope:**
- Connectivity testing between all hosts
- MTU/Jumbo frame verification
- Bandwidth/throughput testing with iperf3
- Ceph performance validation
- Traffic flow verification on switches
- Production readiness assessment

**Prerequisites:**
- Phases 1-5 completed successfully
- All hosts configured and online
- Ceph cluster healthy

---

## Test Plan Summary

### Test Categories

1. **Layer 2/3 Connectivity Tests**
   - Ping tests between all hosts
   - ARP resolution
   - VLAN 200 reachability

2. **MTU Tests**
   - Jumbo frame verification (9000 MTU)
   - Path MTU discovery
   - Fragmentation detection

3. **Bandwidth Tests**
   - iperf3 throughput tests (40Gb links)
   - Multi-stream performance
   - Bidirectional testing

4. **Ceph Performance Tests**
   - OSD network performance
   - Replication bandwidth
   - Client I/O patterns

5. **Switch Verification**
   - LAG/Port-Channel status
   - Traffic distribution
   - Error counters

6. **Production Readiness**
   - Failover scenarios
   - Monitoring setup
   - Documentation review

---

## Test 1: Basic Connectivity

### 1.1 Ping Tests Between All Hosts

**From Proxmox-01 (10.200.0.1):**
```bash
ssh root@192.168.1.62

# Test to all other hosts
ping -c 10 10.200.0.2  # Proxmox-02 (40Gb via Arista)
ping -c 10 10.200.0.3  # Proxmox-03 (via Brocade)
ping -c 10 10.200.0.4  # Proxmox-04 (40Gb via Arista)
ping -c 10 10.200.0.254  # Brocade gateway

# Record results: packet loss, RTT (avg/min/max)
```

**From Proxmox-02 (10.200.0.2):**
```bash
ssh root@192.168.1.63

ping -c 10 10.200.0.1  # Proxmox-01
ping -c 10 10.200.0.3  # Proxmox-03 (via Brocade)
ping -c 10 10.200.0.4  # Proxmox-04
ping -c 10 10.200.0.254  # Brocade gateway
```

**From Proxmox-03 (10.200.0.3):**
```bash
ssh root@192.168.1.64

ping -c 10 10.200.0.1  # Proxmox-01 (via Brocade)
ping -c 10 10.200.0.2  # Proxmox-02 (via Brocade)
ping -c 10 10.200.0.4  # Proxmox-04 (via Brocade)
ping -c 10 10.200.0.254  # Brocade gateway
```

**From Proxmox-04 (10.200.0.4):**
```bash
ssh root@192.168.1.66

ping -c 10 10.200.0.1  # Proxmox-01
ping -c 10 10.200.0.2  # Proxmox-02
ping -c 10 10.200.0.3  # Proxmox-03 (via Brocade)
ping -c 10 10.200.0.254  # Brocade gateway
```

**Expected Results:**
- **0% packet loss** on all tests
- **RTT < 1ms** for direct 40Gb links (hosts on Arista)
- **RTT < 2ms** for traffic through Brocade (Proxmox-03)
- Consistent RTT (low jitter)

**Record Results:**

| Source | Destination | Packet Loss | Avg RTT | Min RTT | Max RTT | Path |
|--------|-------------|-------------|---------|---------|---------|------|
| Px-01 | Px-02 | 0% | ___ ms | ___ ms | ___ ms | Direct (Arista) |
| Px-01 | Px-03 | 0% | ___ ms | ___ ms | ___ ms | Via Brocade |
| Px-01 | Px-04 | 0% | ___ ms | ___ ms | ___ ms | Direct (Arista) |
| Px-02 | Px-03 | 0% | ___ ms | ___ ms | ___ ms | Via Brocade |
| ... | ... | ... | ... | ... | ... | ... |

### 1.2 ARP Resolution Test

**On each host, check ARP table:**
```bash
# Show ARP entries for VLAN 200
ip neighbor show dev vmbr200

# Should show all other VLAN 200 hosts
# Example output:
# 10.200.0.2 lladdr xx:xx:xx:xx:xx:xx REACHABLE
# 10.200.0.3 lladdr xx:xx:xx:xx:xx:xx REACHABLE
```

**Expected:** All hosts resolve ARP for all other VLAN 200 hosts.

### 1.3 Verify No Routing Loops

**On each host:**
```bash
# Check routing table
ip route show | grep 10.200.0

# Proxmox-01, 02, 04 should show:
# 10.200.0.0/24 dev vmbr200 proto kernel scope link src 10.200.0.X

# Proxmox-03 should show:
# 10.200.0.0/24 dev vmbr200 proto kernel scope link src 10.200.0.3
# default via 10.200.0.254 dev vmbr200  # (if configured as gateway)
```

**Expected:** No duplicate routes, no routing loops.

---

## Test 2: MTU / Jumbo Frame Testing

### 2.1 MTU Verification on All Interfaces

**Check MTU on each host:**
```bash
# On Proxmox-01, 02, 04 (40Gb hosts):
ssh root@<proxmox-ip>

ip link show <40gb-interface> | grep mtu  # Should be 9000
ip link show <40gb-interface>.200 | grep mtu  # Should be 9000
ip link show vmbr200 | grep mtu  # Should be 9000

# On Proxmox-03 (10Gb bond):
ssh root@192.168.1.64

ip link show bond1 | grep mtu  # Should be 9000
ip link show vmbr1 | grep mtu  # Should be 9000
ip link show vmbr1.200 | grep mtu  # Should be 9000
ip link show vmbr200 | grep mtu  # Should be 9000
```

**Expected:** MTU 9000 on all interfaces in VLAN 200 path.

### 2.2 Jumbo Frame Ping Tests

**From each host, test jumbo frames to all other hosts:**

**From Proxmox-01:**
```bash
ssh root@192.168.1.62

# Test maximum MTU (9000 - 28 for IP+ICMP = 8972)
ping -M do -s 8972 -c 10 10.200.0.2  # To Proxmox-02 (direct 40Gb)
ping -M do -s 8972 -c 10 10.200.0.3  # To Proxmox-03 (via Brocade)
ping -M do -s 8972 -c 10 10.200.0.4  # To Proxmox-04 (direct 40Gb)

# Test slightly larger than standard MTU (to confirm jumbo is working)
ping -M do -s 1500 -c 10 10.200.0.2
```

**Repeat from each host to all other hosts.**

**Expected Results:**
- ✅ `ping -M do -s 8972` succeeds (0% loss)
- ✅ `ping -M do -s 1500` succeeds
- ❌ If ping fails with "Frag needed", MTU is too small somewhere

**If any test fails:**
```bash
# Find where MTU breaks
# Try progressively smaller sizes:
ping -M do -s 8000 -c 4 <ip>
ping -M do -s 7000 -c 4 <ip>
ping -M do -s 1472 -c 4 <ip>  # Standard 1500 MTU

# The largest size that works indicates the path MTU
```

### 2.3 Path MTU Discovery Test

**Test automatic path MTU discovery:**
```bash
# From Proxmox-01
ssh root@192.168.1.62

# Send large packet WITHOUT Don't Fragment flag
ping -s 8972 -c 10 10.200.0.2

# Should succeed (will fragment if needed)
# Compare RTT to ping with -M do (no fragmentation)
# If much slower, indicates fragmentation is occurring (bad!)
```

**Expected:** Similar RTT with and without `-M do` flag.

### 2.4 Switch MTU Verification

**On Arista:**
```bash
ssh admin@192.168.1.21

# Check MTU on all VLAN 200 ports
show interface Port-Channel1 | grep MTU  # Should be 9216
show interface ethernet 27 | grep MTU     # Should be 9216
show interface ethernet 28 | grep MTU     # Should be 9216
show interface ethernet 29 | grep MTU     # Should be 9216
```

**On Brocade:**
```bash
ssh admin@192.168.1.20

# Check MTU on VLAN 200 interface
show interface ve 200 | include mtu  # Should be 9000

# Check MTU on LAG to Arista
show lag 11  # Check if MTU 9000 is set
```

**Expected:** All switch interfaces support jumbo frames.

---

## Test 3: Bandwidth / Throughput Testing

### 3.1 Install iperf3 on All Hosts

**On each Proxmox host:**
```bash
apt update && apt install iperf3 -y
```

### 3.2 Direct 40Gb Link Tests (Proxmox-01, 02, 04)

**Test: Proxmox-01 → Proxmox-02 (40Gb direct via Arista)**

**On Proxmox-02 (server):**
```bash
ssh root@192.168.1.63

# Start iperf3 server on VLAN 200 IP
iperf3 -s -B 10.200.0.2
```

**On Proxmox-01 (client):**
```bash
ssh root@192.168.1.62

# Single stream test (30 seconds)
iperf3 -c 10.200.0.2 -B 10.200.0.1 -t 30

# Multi-stream test (10 parallel streams)
iperf3 -c 10.200.0.2 -B 10.200.0.1 -t 30 -P 10

# Bidirectional test
iperf3 -c 10.200.0.2 -B 10.200.0.1 -t 30 --bidir

# Record results: bandwidth achieved
```

**Expected Results:**
- **Single stream:** ~30-35 Gbps (80-90% of 40Gb line rate)
- **Multi-stream:** ~38-40 Gbps (close to line rate)
- **Bidirectional:** ~35-38 Gbps each direction

**Note:** Achieving exactly 40Gbps is difficult due to TCP overhead, CPU limits, etc. 35+ Gbps is excellent.

**Repeat for other 40Gb link pairs:**
- Proxmox-01 ↔ Proxmox-04
- Proxmox-02 ↔ Proxmox-04

### 3.3 Traffic Through Brocade (Proxmox-03)

**Test: Proxmox-03 → Proxmox-01 (10Gb → Brocade → Arista → 40Gb)**

**On Proxmox-01 (server):**
```bash
iperf3 -s -B 10.200.0.1
```

**On Proxmox-03 (client):**
```bash
ssh root@192.168.1.64

# Single stream test
iperf3 -c 10.200.0.1 -B 10.200.0.3 -t 30

# Multi-stream test
iperf3 -c 10.200.0.1 -B 10.200.0.3 -t 30 -P 10

# Record results
```

**Expected Results:**
- **Single stream:** ~8-9 Gbps (limited by Proxmox-03's 10Gb bond)
- **Multi-stream:** ~9-10 Gbps (approaching 10Gb limit)

**Note:** Traffic is limited by Proxmox-03's 10Gb uplink, NOT by the Brocade-Arista LAG (which is 80Gbps).

**Repeat from Proxmox-03 to Proxmox-02 and Proxmox-04.**

### 3.4 Concurrent Traffic Tests

**Test multiple simultaneous transfers to verify no bottlenecks:**

**Setup:**
- Proxmox-01 → Proxmox-02 (iperf3 test)
- Proxmox-01 → Proxmox-04 (iperf3 test)
- Proxmox-03 → Proxmox-02 (iperf3 test)

**Expected:** All three streams should maintain near-maximum throughput:
- Px-01 → Px-02: ~35 Gbps
- Px-01 → Px-04: ~35 Gbps (total 70Gbps from Px-01, might be CPU limited)
- Px-03 → Px-02: ~9 Gbps

**If bandwidth drops significantly:**
- Check switch CPU usage
- Check for congestion on Brocade-Arista LAG
- Verify LAG is load-balancing correctly

### 3.5 Record All Bandwidth Results

| Source | Destination | Path | Single Stream | Multi-Stream | Bidirectional |
|--------|-------------|------|---------------|--------------|---------------|
| Px-01 | Px-02 | Direct 40Gb | ___ Gbps | ___ Gbps | ___ Gbps |
| Px-01 | Px-04 | Direct 40Gb | ___ Gbps | ___ Gbps | ___ Gbps |
| Px-02 | Px-04 | Direct 40Gb | ___ Gbps | ___ Gbps | ___ Gbps |
| Px-03 | Px-01 | Via Brocade | ___ Gbps | ___ Gbps | ___ Gbps |
| Px-03 | Px-02 | Via Brocade | ___ Gbps | ___ Gbps | ___ Gbps |
| Px-03 | Px-04 | Via Brocade | ___ Gbps | ___ Gbps | ___ Gbps |

---

## Test 4: Ceph Performance Validation

### 4.1 Check Ceph Network Configuration

**Verify Ceph is using VLAN 200 for cluster traffic:**

**On any Proxmox host with Ceph:**
```bash
# Check Ceph configuration
cat /etc/ceph/ceph.conf

# Should show cluster_network pointing to 10.200.0.0/24
# Example:
# [global]
# cluster_network = 10.200.0.0/24
# public_network = 10.150.0.0/24
```

**Check Ceph OSD network binding:**
```bash
# Show which IPs OSDs are using
ceph osd metadata | jq -r '.[] | "\(.id): \(.front_iface) \(.back_iface)"'

# Should show VLAN 200 IPs (10.200.0.x) for cluster/backend traffic
```

### 4.2 Ceph OSD Network Benchmark

**Run Ceph's built-in network test:**
```bash
# On one Proxmox host
ssh root@192.168.1.62

# Test network between OSDs
ceph tell osd.* bench
```

**Expected:** High throughput numbers reflecting 40Gb (or 10Gb for Px-03) links.

### 4.3 Monitor Ceph Rebalance Performance

**Trigger a rebalance by changing a CRUSH weight (optional, may impact production):**
```bash
# Get current OSD tree
ceph osd tree

# Temporarily adjust a weight (very slight change)
# ceph osd crush reweight osd.X 0.95
# Wait for rebalance to start
# ceph -s
# Watch rebalance speed
# Restore weight when done
# ceph osd crush reweight osd.X 1.0
```

**Monitor rebalance speed:**
```bash
watch -n 2 'ceph -s | grep -A 5 recovery'

# Note the MB/s or objects/s recovery rate
```

**Expected:** Significantly faster rebalance than before (4x improvement on 40Gb hosts).

### 4.4 Real-World Ceph I/O Test (from Kubernetes)

**From Kubernetes cluster:**
```bash
# Create test pod with RBD volume
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-rbd-pvc
  namespace: default
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: ceph-block
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: Pod
metadata:
  name: fio-test
  namespace: default
spec:
  containers:
  - name: fio
    image: ljishen/fio:latest
    command: ["sleep", "3600"]
    volumeMounts:
    - name: test-vol
      mountPath: /test
  volumes:
  - name: test-vol
    persistentVolumeClaim:
      claimName: test-rbd-pvc
EOF
```

**Run FIO benchmark:**
```bash
# Wait for pod to be ready
kubectl wait --for=condition=Ready pod/fio-test -n default --timeout=300s

# Run sequential write test
kubectl exec -it fio-test -n default -- fio \
  --name=seqwrite \
  --rw=write \
  --bs=1M \
  --size=5G \
  --numjobs=1 \
  --filename=/test/testfile \
  --direct=1 \
  --ioengine=libaio \
  --iodepth=32 \
  --group_reporting

# Run random read test
kubectl exec -it fio-test -n default -- fio \
  --name=randread \
  --rw=randread \
  --bs=4k \
  --size=1G \
  --numjobs=4 \
  --filename=/test/testfile \
  --direct=1 \
  --ioengine=libaio \
  --iodepth=32 \
  --group_reporting
```

**Record results:** Bandwidth (MB/s), IOPS, latency

**Cleanup:**
```bash
kubectl delete pod fio-test -n default
kubectl delete pvc test-rbd-pvc -n default
```

---

## Test 5: Switch Verification

### 5.1 Verify LAG/Port-Channel Status

**On Brocade:**
```bash
ssh admin@192.168.1.20

# Check LAG 11 status (Brocade-Arista)
show lag 11

# Should show:
# - 2 ports active (1/2/1 and 1/2/6)
# - LACP negotiated
# - No errors

# Check LACP partner
show lacp

# Should show Arista as partner
```

**On Arista:**
```bash
ssh admin@192.168.1.21

# Check Port-Channel status
show port-channel summary

# Should show:
# Po1(U) - Port-Channel is Up
# Et25(P) - Member port bundled
# Et26(P) - Member port bundled

# Check LACP neighbor
show lacp neighbor

# Should show Brocade as partner
```

**Expected:** Both LAG/Port-Channel up with 2 active members.

### 5.2 Verify Traffic Distribution Across LAG

**During iperf3 tests, check traffic distribution:**

**On Brocade:**
```bash
# Check traffic counters on both LAG members
show interface ethernet 1/2/1 | include rate
show interface ethernet 1/2/6 | include rate

# Both should show traffic (may not be exactly equal due to hashing)
```

**On Arista:**
```bash
# Check traffic on Port-Channel members
show interface ethernet 25 counters rate
show interface ethernet 26 counters rate

# Both should show traffic
```

**Expected:** Traffic is distributed across both links (doesn't need to be 50/50).

### 5.3 Check for Errors on All Interfaces

**On Arista:**
```bash
# Check all VLAN 200 interfaces for errors
show interface ethernet 25 | grep -i error
show interface ethernet 26 | grep -i error
show interface ethernet 27 | grep -i error
show interface ethernet 28 | grep -i error
show interface ethernet 29 | grep -i error

# Should show 0 errors
```

**On Brocade:**
```bash
# Check LAG and host interfaces
show interface ethernet 1/2/1 | include error
show interface ethernet 1/2/6 | include error

# Check Proxmox-03 LAG (LAG 2)
show lag 2

# All should show 0 errors
```

**Expected:** Zero input/output errors, CRC errors, or drops.

### 5.4 Monitor Switch CPU and Memory

**On Brocade:**
```bash
show cpu
show memory

# CPU should be < 30%
# Memory should be < 70%
```

**On Arista:**
```bash
show processes top once

# CPU should be < 20%
```

**Expected:** Normal CPU/memory usage, no signs of resource exhaustion.

---

## Test 6: Failover and Resilience

### 6.1 Test LAG Failover (Optional - Disruptive!)

**Test single link failure in Brocade-Arista LAG:**

**On Arista:**
```bash
# Disable one member of Port-Channel
configure
interface ethernet 25
  shutdown
exit
exit
```

**Verify failover:**
```bash
# Check Port-Channel still up with 1 member
show port-channel summary

# Should show:
# Po1(U) - Still Up
# Et25(D) - Down
# Et26(P) - Active
```

**Test traffic during failover:**
```bash
# From Proxmox-03, ping during failover
ping 10.200.0.1

# Should see 1-2 packet losses during switchover, then recovery
```

**Re-enable link:**
```bash
configure
interface ethernet 25
  no shutdown
exit
exit

# Verify both members active again
show port-channel summary
```

**Expected:** Brief interruption (< 2 seconds), then automatic recovery.

### 6.2 Test Single Proxmox Host Failure

**Simulate Proxmox-01 offline:**
```bash
# On Proxmox-01, bring down vmbr200 temporarily
ssh root@192.168.1.62
ifdown vmbr200
```

**From other hosts, verify:**
```bash
# From Proxmox-02
ping 10.200.0.1  # Should timeout

# From Proxmox-03
ping 10.200.0.1  # Should timeout

# Test connectivity between remaining hosts
# From Proxmox-02
ping 10.200.0.3  # Should work
ping 10.200.0.4  # Should work
```

**Check Ceph status:**
```bash
ceph -s

# May show OSDs on Px-01 as down
# Other OSDs should remain healthy
```

**Restore Proxmox-01:**
```bash
# On Proxmox-01
ifup vmbr200

# From other hosts
ping 10.200.0.1  # Should work again
```

**Expected:** Other hosts continue communicating; Ceph marks OSDs down but cluster remains operational (if sufficient redundancy).

---

## Test 7: Production Readiness

### 7.1 Configuration Backup Verification

**Verify all switch configs are saved:**

**On Brocade:**
```bash
show running-config
# Compare to startup-config
show startup-config

# Should be identical (or write memory if different)
```

**On Arista:**
```bash
show running-config
show startup-config

# Should be identical
```

### 7.2 Documentation Review

**Verify all documentation is complete:**
- [ ] Phase 1-6 configuration guides completed
- [ ] Interface mapping documented (Phase 4)
- [ ] Test results recorded (this phase)
- [ ] Network topology diagram updated
- [ ] Runbook updated with new configuration

### 7.3 Monitoring Setup (Optional)

**If monitoring is in place, verify:**
- [ ] Switch SNMP monitoring for:
  - Interface utilization
  - Error counters
  - LAG/Port-Channel status
  - CPU/memory usage
- [ ] Ceph monitoring shows correct network configuration
- [ ] Alerting configured for:
  - Link failures
  - High error rates
  - LAG member failures

### 7.4 Create Operational Runbook

**Document procedures for:**
- [ ] Adding a new Proxmox host to VLAN 200
- [ ] Troubleshooting connectivity issues
- [ ] Replacing a failed 40Gb cable/SFP+
- [ ] Upgrading switch firmware (maintenance window)

---

## Success Criteria

### Connectivity
- [ ] All ping tests pass (0% loss)
- [ ] RTT < 1ms for direct 40Gb links
- [ ] RTT < 2ms for traffic through Brocade
- [ ] ARP resolution works for all hosts

### MTU / Jumbo Frames
- [ ] MTU 9000 configured on all VLAN 200 interfaces
- [ ] MTU 9216 configured on Arista switch ports
- [ ] Jumbo frame ping tests pass (ping -M do -s 8972)
- [ ] No fragmentation detected

### Bandwidth
- [ ] 40Gb links achieve 35+ Gbps in iperf3 tests
- [ ] Proxmox-03 achieves 9+ Gbps through 10Gb bond
- [ ] Concurrent traffic tests show no bottlenecks
- [ ] LAG distributes traffic across both members

### Ceph
- [ ] Ceph cluster healthy (HEALTH_OK)
- [ ] OSDs using correct network (10.200.0.x)
- [ ] Ceph rebalance speed improved vs. before
- [ ] Kubernetes I/O tests show good performance

### Switch
- [ ] LAG/Port-Channel operational with 2 members
- [ ] No errors on any interfaces
- [ ] Traffic distributed across LAG members
- [ ] CPU/memory usage normal
- [ ] Configurations saved

### Production Readiness
- [ ] All documentation complete and accurate
- [ ] Configuration backups taken
- [ ] Monitoring configured (if applicable)
- [ ] Runbook procedures documented
- [ ] Team trained on new configuration

---

## Performance Baseline

**Record final performance metrics for future reference:**

### Network Performance
| Metric | Before (10Gb) | After (40Gb) | Improvement |
|--------|---------------|--------------|-------------|
| Proxmox-01 ↔ Proxmox-02 | ~9 Gbps | ~35 Gbps | 3.9x |
| Proxmox-01 ↔ Proxmox-04 | ~9 Gbps | ~35 Gbps | 3.9x |
| Proxmox-02 ↔ Proxmox-04 | ~9 Gbps | ~35 Gbps | 3.9x |
| Proxmox-03 ↔ Others | ~9 Gbps | ~9 Gbps | 1x (limited by Px-03) |

### Ceph Performance
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Rebalance speed | ___ MB/s | ___ MB/s | ___x |
| Sequential write | ___ MB/s | ___ MB/s | ___x |
| Random read IOPS | ___ IOPS | ___ IOPS | ___x |
| Average latency | ___ ms | ___ ms | ___x |

### Latency (RTT)
| Path | Before | After | Improvement |
|------|--------|-------|-------------|
| Px-01 ↔ Px-02 | ___ ms | ___ ms | ___% |
| Px-01 ↔ Px-04 | ___ ms | ___ ms | ___% |
| Px-02 ↔ Px-04 | ___ ms | ___ ms | ___% |

---

## Troubleshooting Guide

### Issue: Lower Than Expected Bandwidth

**Symptoms:**
- iperf3 shows < 30 Gbps on 40Gb links

**Diagnosis:**
```bash
# Check CPU usage during iperf3
# On both source and dest
top

# Check network card offloading
ethtool -k <interface> | grep offload

# Check for packet drops
netstat -s | grep -i drop
```

**Potential Causes:**
1. CPU bottleneck (single-stream test)
2. Network card offloading disabled
3. Switch port configuration issue
4. Cable/SFP+ quality issue

**Resolution:**
- Use multi-stream iperf3 test (-P 10)
- Enable offloading: `ethtool -K <interface> tso on gso on`
- Check switch port speed: should show 40Gb

### Issue: High Packet Loss

**Symptoms:**
- Ping tests show > 1% packet loss

**Diagnosis:**
```bash
# Check interface errors
ip -s link show <interface>

# Check switch errors
# On Arista:
show interface <port> | grep -i error

# Check for speed/duplex mismatch
ethtool <interface> | grep -E "(Speed|Duplex)"
```

**Resolution:**
- Check cable quality
- Replace SFP+ module if errors on switch
- Check for CRC errors (indicates physical layer problem)

### Issue: Jumbo Frames Not Working

**Symptoms:**
- ping -M do -s 8972 fails

**See MTU troubleshooting in Phase 2 and Phase 3 documents.**

---

## Sign-Off

**Project Completion Checklist:**

- [ ] All 6 phases completed successfully
- [ ] All tests passed
- [ ] Performance meets or exceeds expectations
- [ ] Documentation complete
- [ ] Team trained
- [ ] Monitoring configured
- [ ] Backup/rollback procedures documented

**Sign-off:**
- [ ] Network Administrator: ________________ Date: ________
- [ ] System Administrator: ________________ Date: ________
- [ ] Storage Administrator: ________________ Date: ________

---

## Appendix: Quick Reference Commands

### Connectivity Test One-Liner
```bash
# Test from one host to all others
for ip in 10.200.0.1 10.200.0.2 10.200.0.3 10.200.0.4 10.200.0.254; do
  echo "Testing $ip:"
  ping -c 4 -q $ip | tail -2
done
```

### MTU Test One-Liner
```bash
# Test jumbo frames to all hosts
for ip in 10.200.0.1 10.200.0.2 10.200.0.3 10.200.0.4; do
  echo "Testing MTU to $ip:"
  ping -M do -s 8972 -c 4 -q $ip | tail -2 || echo "FAILED"
done
```

### iperf3 Quick Test
```bash
# On server (all hosts)
iperf3 -s -B 10.200.0.X -D  # Daemonize

# On client
iperf3 -c <server-ip> -B 10.200.0.X -t 10 -P 4
```

### Ceph Status Quick Check
```bash
# One-liner for Ceph health
ceph -s --format json | jq -r '.health.status, .osdmap, .pgmap.pgs_by_state'
```
