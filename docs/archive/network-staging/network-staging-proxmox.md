## 🖥️ Proxmox Hosts

### Identify Hosts and IPs

**Method 1: From any Proxmox host shell**

```bash
# List all cluster members
pvecm nodes

# Show network configuration
ip addr show

# Show bond status
cat /proc/net/bonding/bond0
cat /proc/net/bonding/bond1
```

**Output:**
```
[PASTE OUTPUT HERE]
```

---

### Host 1 Details

**Hostname:**
```
Proxmox-01
```

**Management IP (bond0):**
```
192.168.1.62
```

**IPMI IP:**
```
192.168.1.162
```

**VLAN 150 IP (Ceph cluster public network):**
```
10.150.0.1

```

**VLAN 200 IP (Ceph cluster storage network):**
```
10.200.0.1
```

**Network Interfaces:**
```bash
# Run on Proxmox host
ip link show
```

**Output:**
```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: enp0s25: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master bond0 state UP mode DEFAULT group default qlen 1000
    link/ether 0c:c4:7a:0c:14:2a brd ff:ff:ff:ff:ff:ff permaddr 0c:c4:7a:0c:14:2b
3: eno1: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master bond0 state UP mode DEFAULT group default qlen 1000
    link/ether 0c:c4:7a:0c:14:2a brd ff:ff:ff:ff:ff:ff
    altname enp4s0
19: tap102i0: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master vmbr1 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether fe:75:d4:4a:8a:87 brd ff:ff:ff:ff:ff:ff
21: bond0: <BROADCAST,MULTICAST,MASTER,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr0 state UP mode DEFAULT group default qlen 1000
    link/ether 0c:c4:7a:0c:14:2a brd ff:ff:ff:ff:ff:ff
22: vmbr0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether 0c:c4:7a:0c:14:2a brd ff:ff:ff:ff:ff:ff
23: bond1: <BROADCAST,MULTICAST,MASTER,UP,LOWER_UP> mtu 9000 qdisc noqueue master vmbr1 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff
24: vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff
25: vmbr1.200@vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr200 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff
26: vmbr200: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff
27: vmbr1.150@vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr150 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff
28: vmbr150: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff
29: enp1s0f0np0: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 9000 qdisc mq master bond1 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff
30: enp1s0f1np1: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 9000 qdisc mq master bond1 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff permaddr ec:0d:9a:bf:7f:93
31: enp2s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode DEFAULT group default qlen 1000
    link/ether 24:be:05:cd:ed:51 brd ff:ff:ff:ff:ff:ff
32: enp2s0d1: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc mq state DOWN mode DEFAULT group default qlen 1000
    link/ether 24:be:05:cd:ed:52 brd ff:ff:ff:ff:ff:ff
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: enp0s25: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master bond0 state UP mode DEFAULT group default qlen 1000
    link/ether 0c:c4:7a:0c:14:2a brd ff:ff:ff:ff:ff:ff permaddr 0c:c4:7a:0c:14:2b
3: eno1: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master bond0 state UP mode DEFAULT group default qlen 1000
    link/ether 0c:c4:7a:0c:14:2a brd ff:ff:ff:ff:ff:ff
    altname enp4s0
19: tap102i0: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master vmbr1 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether fe:75:d4:4a:8a:87 brd ff:ff:ff:ff:ff:ff
21: bond0: <BROADCAST,MULTICAST,MASTER,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr0 state UP mode DEFAULT group default qlen 1000
    link/ether 0c:c4:7a:0c:14:2a brd ff:ff:ff:ff:ff:ff
22: vmbr0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether 0c:c4:7a:0c:14:2a brd ff:ff:ff:ff:ff:ff
23: bond1: <BROADCAST,MULTICAST,MASTER,UP,LOWER_UP> mtu 9000 qdisc noqueue master vmbr1 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff
24: vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff
25: vmbr1.200@vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr200 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff
26: vmbr200: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff
27: vmbr1.150@vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr150 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff
28: vmbr150: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff
29: enp1s0f0np0: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 9000 qdisc mq master bond1 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff
30: enp1s0f1np1: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 9000 qdisc mq master bond1 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:bf:7f:92 brd ff:ff:ff:ff:ff:ff permaddr ec:0d:9a:bf:7f:93
31: enp2s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode DEFAULT group default qlen 1000
    link/ether 24:be:05:cd:ed:51 brd ff:ff:ff:ff:ff:ff
32: enp2s0d1: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc mq state DOWN mode DEFAULT group default qlen 1000
    link/ether 24:be:05:cd:ed:52 brd ff:ff:ff:ff:ff:ff
```

---

### Host 2 Details

**Hostname:**
```
Proxmox-02
```

**Management IP:**
```
192.168.1.63
```

**IPMI IP:**
```
192.168.1.165
```

**VLAN 150 IP (Ceph cluster public network):**
```
10.150.0.2

```

**VLAN 200 IP (Ceph cluster storage network):**
```
10.200.0.2
```

**Network Interfaces:**
```bash
# Run on Proxmox host
ip link show
```

**Output:**
```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: enp3s0: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master bond0 state UP mode DEFAULT group default qlen 1000
    link/ether 00:25:90:66:3f:26 brd ff:ff:ff:ff:ff:ff
3: enp4s0: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master bond0 state UP mode DEFAULT group default qlen 1000
    link/ether 00:25:90:66:3f:26 brd ff:ff:ff:ff:ff:ff permaddr 00:25:90:66:3f:27
4: enp8s0f0np0: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 1500 qdisc mq master bond1 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:f8:54 brd ff:ff:ff:ff:ff:ff
5: enp8s0f1np1: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 1500 qdisc mq master bond1 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:f8:54 brd ff:ff:ff:ff:ff:ff permaddr ec:0d:9a:d2:f8:55
6: enp7s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode DEFAULT group default qlen 1000
    link/ether 80:c1:6e:09:31:80 brd ff:ff:ff:ff:ff:ff
7: enp7s0d1: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc mq state DOWN mode DEFAULT group default qlen 1000
    link/ether 80:c1:6e:09:31:81 brd ff:ff:ff:ff:ff:ff
8: bond0: <BROADCAST,MULTICAST,MASTER,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr0 state UP mode DEFAULT group default qlen 1000
    link/ether 00:25:90:66:3f:26 brd ff:ff:ff:ff:ff:ff
9: vmbr0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether 00:25:90:66:3f:26 brd ff:ff:ff:ff:ff:ff
10: bond1: <BROADCAST,MULTICAST,MASTER,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr1 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:f8:54 brd ff:ff:ff:ff:ff:ff
11: vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:f8:54 brd ff:ff:ff:ff:ff:ff
12: vmbr1.200@vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr200 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:f8:54 brd ff:ff:ff:ff:ff:ff
13: vmbr200: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:f8:54 brd ff:ff:ff:ff:ff:ff
14: vmbr1.150@vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr150 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:f8:54 brd ff:ff:ff:ff:ff:ff
15: vmbr150: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:f8:54 brd ff:ff:ff:ff:ff:ff
16: vmbr1.100@vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr100 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:f8:54 brd ff:ff:ff:ff:ff:ff
17: vmbr100: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:f8:54 brd ff:ff:ff:ff:ff:ff
18: tap4001i0: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master vmbr0 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether b6:47:f2:88:ff:b5 brd ff:ff:ff:ff:ff:ff
19: tap6000i0: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master vmbr1 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether 3e:4a:5d:6c:26:8d brd ff:ff:ff:ff:ff:ff
20: tap6001i0: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master vmbr1 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether 4a:a7:e2:34:1c:a3 brd ff:ff:ff:ff:ff:ff
22: veth101i0@if2: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr0 state UP mode DEFAULT group default qlen 1000
    link/ether fe:b1:08:e4:6b:3a brd ff:ff:ff:ff:ff:ff link-netnsid 0
33: tap7002i0: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master fwbr7002i0 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether 0a:c1:98:35:4b:be brd ff:ff:ff:ff:ff:ff
34: fwbr7002i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether 5a:ab:4b:f8:2a:1e brd ff:ff:ff:ff:ff:ff
35: fwpr7002p0@fwln7002i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr1 state UP mode DEFAULT group default qlen 1000
    link/ether 1a:47:f0:fe:78:3f brd ff:ff:ff:ff:ff:ff
36: fwln7002i0@fwpr7002p0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master fwbr7002i0 state UP mode DEFAULT group default qlen 1000
    link/ether 5a:ab:4b:f8:2a:1e brd ff:ff:ff:ff:ff:ff
37: tap7002i1: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master vmbr150 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether e2:fe:00:19:12:6d brd ff:ff:ff:ff:ff:ff
```
---

### Host 3 Details

**Hostname:**
```
Proxmox-03
```

**Management IP:**
```
192.168.1.64
```

**IPMI IP:**
```
192.168.1.163
```

**VLAN 150 IP (Ceph cluster public network):**
```
10.150.0.3

```

**VLAN 200 IP (Ceph cluster storage network):**
```
10.200.0.3
```

**Network Interfaces:**
```bash
# Run on Proxmox host
ip link show
```

**Output:**
```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: enp5s0: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 1500 qdisc mq master bond0 state UP mode DEFAULT group default qlen 1000
    link/ether b0:6e:bf:3a:64:39 brd ff:ff:ff:ff:ff:ff
3: enp6s0: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 1500 qdisc mq master bond0 state UP mode DEFAULT group default qlen 1000
    link/ether b0:6e:bf:3a:64:39 brd ff:ff:ff:ff:ff:ff permaddr b0:6e:bf:3a:64:3a
4: ens10f0: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 9000 qdisc mq master bond1 state UP mode DEFAULT group default qlen 1000
    link/ether 30:5a:3a:78:c1:ae brd ff:ff:ff:ff:ff:ff
    altname enp129s0f0
5: ens10f1: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 9000 qdisc mq master bond1 state UP mode DEFAULT group default qlen 1000
    link/ether 30:5a:3a:78:c1:ae brd ff:ff:ff:ff:ff:ff permaddr 30:5a:3a:78:c1:af
    altname enp129s0f1
6: bond0: <BROADCAST,MULTICAST,MASTER,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr0 state UP mode DEFAULT group default qlen 1000
    link/ether b0:6e:bf:3a:64:39 brd ff:ff:ff:ff:ff:ff
7: vmbr0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether b0:6e:bf:3a:64:39 brd ff:ff:ff:ff:ff:ff
8: bond1: <BROADCAST,MULTICAST,MASTER,UP,LOWER_UP> mtu 9000 qdisc noqueue master vmbr1 state UP mode DEFAULT group default qlen 1000
    link/ether 30:5a:3a:78:c1:ae brd ff:ff:ff:ff:ff:ff
9: vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether 30:5a:3a:78:c1:ae brd ff:ff:ff:ff:ff:ff
10: vmbr1.150@vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr150 state UP mode DEFAULT group default qlen 1000
    link/ether 30:5a:3a:78:c1:ae brd ff:ff:ff:ff:ff:ff
11: vmbr150: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether 30:5a:3a:78:c1:ae brd ff:ff:ff:ff:ff:ff
12: vmbr1.200@vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr200 state UP mode DEFAULT group default qlen 1000
    link/ether 30:5a:3a:78:c1:ae brd ff:ff:ff:ff:ff:ff
13: vmbr200: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether 30:5a:3a:78:c1:ae brd ff:ff:ff:ff:ff:ff
14: tap7000i0: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master fwbr7000i0 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether 62:9a:f9:77:6d:c2 brd ff:ff:ff:ff:ff:ff
15: fwbr7000i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ee:9c:e1:e1:ac:6a brd ff:ff:ff:ff:ff:ff
16: fwpr7000p0@fwln7000i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr1 state UP mode DEFAULT group default qlen 1000
    link/ether f6:ea:30:8d:9b:6b brd ff:ff:ff:ff:ff:ff
17: fwln7000i0@fwpr7000p0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master fwbr7000i0 state UP mode DEFAULT group default qlen 1000
    link/ether ee:9c:e1:e1:ac:6a brd ff:ff:ff:ff:ff:ff
18: tap7000i1: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master vmbr150 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether 26:90:f2:94:2e:9b brd ff:ff:ff:ff:ff:ff
30: tap7003i0: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master fwbr7003i0 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether f6:71:65:a7:d3:6a brd ff:ff:ff:ff:ff:ff
31: fwbr7003i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether 06:d8:24:1a:75:d6 brd ff:ff:ff:ff:ff:ff
32: fwpr7003p0@fwln7003i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr1 state UP mode DEFAULT group default qlen 1000
    link/ether b2:ed:71:d9:c5:bc brd ff:ff:ff:ff:ff:ff
33: fwln7003i0@fwpr7003p0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master fwbr7003i0 state UP mode DEFAULT group default qlen 1000
    link/ether 06:d8:24:1a:75:d6 brd ff:ff:ff:ff:ff:ff
34: tap7003i1: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master vmbr150 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether 02:96:e4:fd:29:17 brd ff:ff:ff:ff:ff:ff
35: tap7004i0: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master fwbr7004i0 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether be:14:22:f3:0b:d4 brd ff:ff:ff:ff:ff:ff
36: fwbr7004i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether d2:80:2f:d9:da:6c brd ff:ff:ff:ff:ff:ff
37: fwpr7004p0@fwln7004i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr1 state UP mode DEFAULT group default qlen 1000
    link/ether 2e:13:ac:c5:db:69 brd ff:ff:ff:ff:ff:ff
38: fwln7004i0@fwpr7004p0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master fwbr7004i0 state UP mode DEFAULT group default qlen 1000
    link/ether d2:80:2f:d9:da:6c brd ff:ff:ff:ff:ff:ff
39: tap7004i1: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master vmbr150 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether 52:b7:7c:a4:fe:4e brd ff:ff:ff:ff:ff:ff
40: tap7005i0: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master fwbr7005i0 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether 16:5a:84:a8:a9:d7 brd ff:ff:ff:ff:ff:ff
41: fwbr7005i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether de:d0:df:71:bf:a4 brd ff:ff:ff:ff:ff:ff
42: fwpr7005p0@fwln7005i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr1 state UP mode DEFAULT group default qlen 1000
    link/ether f6:de:85:c7:43:6c brd ff:ff:ff:ff:ff:ff
43: fwln7005i0@fwpr7005p0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master fwbr7005i0 state UP mode DEFAULT group default qlen 1000
    link/ether de:d0:df:71:bf:a4 brd ff:ff:ff:ff:ff:ff
44: tap7005i1: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master vmbr150 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether 8e:c1:99:33:4d:5f brd ff:ff:ff:ff:ff:ff
45: tap7006i0: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master fwbr7006i0 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether 32:f9:b3:76:7f:c9 brd ff:ff:ff:ff:ff:ff
46: fwbr7006i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether 5a:0e:d9:8c:7a:94 brd ff:ff:ff:ff:ff:ff
47: fwpr7006p0@fwln7006i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr1 state UP mode DEFAULT group default qlen 1000
    link/ether b6:69:f2:df:53:d2 brd ff:ff:ff:ff:ff:ff
48: fwln7006i0@fwpr7006p0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master fwbr7006i0 state UP mode DEFAULT group default qlen 1000
    link/ether 5a:0e:d9:8c:7a:94 brd ff:ff:ff:ff:ff:ff
49: tap7006i1: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master vmbr150 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether 7e:70:2c:1f:63:f7 brd ff:ff:ff:ff:ff:ff
55: vmbr201: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether ae:0e:48:4b:d9:1f brd ff:ff:ff:ff:ff:ff
```
---

### Host 4 Details

**Hostname:**
```
Proxmox-04
```

**Management IP:**
```
192.168.1.66
```

**IPMI IP:**
```
192.168.1.164
```

**VLAN 150 IP (Ceph cluster public network):**
```
10.150.0.4

```

**VLAN 200 IP (Ceph cluster storage network):**
```
10.200.0.4
```

**Network Interfaces:**
```bash
# Run on Proxmox host
ip link show
```

**Output:**
```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: enp3s0: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master bond0 state UP mode DEFAULT group default qlen 1000
    link/ether 00:25:90:64:58:0a brd ff:ff:ff:ff:ff:ff
3: enp4s0: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master bond0 state UP mode DEFAULT group default qlen 1000
    link/ether 00:25:90:64:58:0a brd ff:ff:ff:ff:ff:ff permaddr 00:25:90:64:58:0b
4: enp8s0f0np0: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 9000 qdisc mq master bond1 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:fb:80 brd ff:ff:ff:ff:ff:ff
5: enp8s0f1np1: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 9000 qdisc mq master bond1 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:fb:80 brd ff:ff:ff:ff:ff:ff permaddr ec:0d:9a:d2:fb:81
6: enp7s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode DEFAULT group default qlen 1000
    link/ether 00:02:c9:42:76:a0 brd ff:ff:ff:ff:ff:ff
7: enp7s0d1: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc mq state DOWN mode DEFAULT group default qlen 1000
    link/ether 00:02:c9:42:76:a1 brd ff:ff:ff:ff:ff:ff
8: bond0: <BROADCAST,MULTICAST,MASTER,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr0 state UP mode DEFAULT group default qlen 1000
    link/ether 00:25:90:64:58:0a brd ff:ff:ff:ff:ff:ff
9: vmbr0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether 00:25:90:64:58:0a brd ff:ff:ff:ff:ff:ff
10: bond1: <BROADCAST,MULTICAST,MASTER,UP,LOWER_UP> mtu 9000 qdisc noqueue master vmbr1 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:fb:80 brd ff:ff:ff:ff:ff:ff
11: vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:fb:80 brd ff:ff:ff:ff:ff:ff
12: vmbr1.150@vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr150 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:fb:80 brd ff:ff:ff:ff:ff:ff
13: vmbr150: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:fb:80 brd ff:ff:ff:ff:ff:ff
14: vmbr1.200@vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr200 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:fb:80 brd ff:ff:ff:ff:ff:ff
15: vmbr200: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:fb:80 brd ff:ff:ff:ff:ff:ff
16: vmbr1.100@vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr100 state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:fb:80 brd ff:ff:ff:ff:ff:ff
17: vmbr100: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether ec:0d:9a:d2:fb:80 brd ff:ff:ff:ff:ff:ff
23: tap7001i0: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master fwbr7001i0 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether 9e:7b:ef:19:1f:da brd ff:ff:ff:ff:ff:ff
24: fwbr7001i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether 8a:79:ee:48:96:34 brd ff:ff:ff:ff:ff:ff
25: fwpr7001p0@fwln7001i0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr1 state UP mode DEFAULT group default qlen 1000
    link/ether 8e:df:28:23:9b:d9 brd ff:ff:ff:ff:ff:ff
26: fwln7001i0@fwpr7001p0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master fwbr7001i0 state UP mode DEFAULT group default qlen 1000
    link/ether 8a:79:ee:48:96:34 brd ff:ff:ff:ff:ff:ff
27: tap7001i1: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master vmbr150 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether 7a:05:ba:b5:35:72 brd ff:ff:ff:ff:ff:ff
28: tap6002i0: <BROADCAST,MULTICAST,PROMISC,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast master vmbr1 state UNKNOWN mode DEFAULT group default qlen 1000
    link/ether a2:cf:f1:87:66:38 brd ff:ff:ff:ff:ff:ff
34: veth103i0@if2: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master vmbr1 state UP mode DEFAULT group default qlen 1000
    link/ether fe:c3:36:63:9f:a4 brd ff:ff:ff:ff:ff:ff link-netnsid 0
```

---

### Ceph Configuration

**Command (from any Proxmox host):**
```bash
# Get Ceph monitor IPs
pveceph mon list

# Or from Kubernetes if Ceph is external
kubectl -n rook-ceph get configmap rook-ceph-mon-endpoints -o yaml
```

**Output:**
```
e6: 2 mons at {Proxmox-04=[v2:10.150.0.4:3300/0,v1:10.150.0.4:6789/0],proxmox-02=[v2:10.150.0.2:3300/0,v1:10.150.0.2:6789/0]} removed_ranks: {} disallowed_leaders: {}, election epoch 46, leader 0 Proxmox-04, quorum 0,1 Proxmox-04,proxmox-02
```

---

### VM to Host Mapping

**Command (from Proxmox):**
```bash
# List all VMs and their host
pvesh get /cluster/resources --type vm --output-format json | jq -r '.[] | "\(.name) -> \(.node)"'

# Or simpler
qm list
```

**Output:**
### Proxmox-01
```
VMID NAME                 STATUS     MEM(MB)    BOOTDISK(GB) PID
102 tower                running    11444              0.00 77791
```

### Proxmox-02
```
VMID NAME                 STATUS     MEM(MB)    BOOTDISK(GB) PID
4001 Unraid-2             running    24576              0.00 37250
6000 chelonianlabs-dev-control-1 running    20480             32.00 37300
6001 chelonianlabs-dev-control-2 running    20480             32.00 37328
7002 talos-control-3      running    16384             15.00 149944
```

### Proxmox-03
```
VMID NAME                 STATUS     MEM(MB)    BOOTDISK(GB) PID
7000 talos-control-1      running    16384             15.00 2706
7003 talos-node-gpu-1     running    131072           110.00 3672
7004 talos-node-large-1   running    131072           110.00 4855
7005 talos-node-large-2   running    131072           110.00 5107
7006 talos-node-large-3   running    131072           110.00 5507
```

### Proxmox-04
```
VMID NAME                 STATUS     MEM(MB)    BOOTDISK(GB) PID
6002 chelonianlabs-dev-control-3 running    20480             32.00 532525
7001 talos-control-2      running    16384             15.00 530574
```

---
