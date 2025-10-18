## 📝 Manual Information

### OPNsense Details

**Model:**
```
Intel i3-4130T - 16GB RAM
```

**Management IP:**
```
192.168.1.1
```

**WAN Interface:**
```
2.5Gb AT&T Fiber
```

**VLAN Interfaces:**
- VLAN 1 (192.168.1.1): Default LAN network for management and clients
- VLAN 100 (10.100.0.1): Kubernetes/server network gateway

---

### Mikrotik CSS326-24G-2S (192.168.1.27)

**Location:**
```
Garage
```

**Purpose:**
```
Wireless Bridge - Brocade Core interconnect
Always-up backup interconnect between house and garage
```

**Connection:**
```
Connected between Mikrotik NRay60 (shop) and Brocade Core switch
Provides redundant path if main wireless bridge fails
```

---

### Additional Notes

**Physical Cable Identification:**

Document any cable colors, labels, or identifying features that help map physical to logical:

```
[FILL IN]

Example:
- Blue cables: 1Gb management
- Orange cables: 10Gb VM traffic
- Yellow cables: 40Gb storage
```

**MAC Address to Port Mapping (if helpful):**

```
[FILL IN - If you want to document MAC addresses for easier identification]
```

---

## 🎯 Quick Command Reference

### Copy these command blocks for quick execution:

**Brocade Quick Gather:**
```bash
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
pvecm nodes
hostname
ip addr show
cat /proc/net/bonding/bond0 2>/dev/null || echo "bond0 not found"
cat /proc/net/bonding/bond1 2>/dev/null || echo "bond1 not found"
pvesh get /cluster/resources --type vm --output-format json | jq -r '.[] | "\(.name) -> \(.node)"' 2>/dev/null || qm list
```

---

## ✅ Completion Checklist

Mark items as you complete them:

- [ ] Brocade: Basic info gathered
- [ ] Brocade: VLAN configuration captured
- [ ] Brocade: VLAN interface IPs identified
- [ ] Brocade: LAG configuration documented
- [ ] Brocade: Port assignments identified
- [ ] Brocade: Routing table captured
- [ ] Arista: Basic info gathered
- [ ] Arista: Port assignments identified
- [ ] Arista: Port-channel status checked
- [ ] Arista: 40Gb links to Proxmox identified
- [ ] Proxmox: All host IPs documented
- [ ] Proxmox: All IPMI IPs documented
- [ ] Proxmox: VLAN 200 IPs documented
- [ ] Proxmox: VM-to-host mapping completed
- [ ] Ceph: Monitor IPs identified
- [ ] Manual info: OPNsense details filled
- [ ] Manual info: Mikrotik switch purpose documented

---

## 📄 Next Steps

Once this staging document is complete:

1. Review all outputs for accuracy
2. Identify any missing information
3. Update the main `network-topology.md` document with the gathered info
4. Update the `network-runbook.md` with specific port numbers and configurations
5. Create proper LAG configuration for Brocade-Arista interconnect
6. Archive this staging doc or save as a backup reference

---

**Last Updated:** [Add timestamp when you complete sections]
