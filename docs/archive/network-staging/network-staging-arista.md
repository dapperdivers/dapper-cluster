## 🔧 Arista 7050 (192.168.1.21)

### Connection

```bash
ssh admin@192.168.1.21
```

---

### 1. Basic System Information

**Command:**
```bash
show version
```

**Output:**
```
Arista DCS-7050QX-32-R
Hardware version:    02.11
Serial number:       JPE15362579
System MAC address:  444c.a815.e0f7

Software image version: 4.20.11M
Architecture:           i386
Internal build version: 4.20.11M-10590868.42011M
Internal build ID:      107ed632-2ade-481f-afb4-86f6991f46a5

Uptime:                 0 weeks, 0 days, 16 hours and 15 minutes
Total memory:           3956120 kB
Free memory:            2649824 kB
```

---

### 2. VLAN Configuration

**Command:**
```bash
show vlan
```

**Output:**
```
VLAN  Name                             Status    Ports
----- -------------------------------- --------- -------------------------------
1     default                          active    Cpu, Et27, Et28, Et29
200   ceph-storage                     active    Et26, Et27, Et28, Et29

```

---

### 3. Interface Status

**Command:**
```bash
show interface status
```

**Output:**
```
Port       Name                         Status       Vlan     Duplex Speed  Type         Flags
Et1/1                                   notconnect   1        full   10G    Not Present
Et1/2                                   notconnect   1        full   10G    Not Present
Et1/3                                   notconnect   1        full   10G    Not Present
Et1/4                                   notconnect   1        full   10G    Not Present
Et2/1                                   notconnect   1        full   10G    Not Present
Et2/2                                   notconnect   1        full   10G    Not Present
Et2/3                                   notconnect   1        full   10G    Not Present
Et2/4                                   notconnect   1        full   10G    Not Present
Et3/1                                   notconnect   1        full   10G    Not Present
Et3/2                                   notconnect   1        full   10G    Not Present
Et3/3                                   notconnect   1        full   10G    Not Present
Et3/4                                   notconnect   1        full   10G    Not Present
Et4/1                                   notconnect   1        full   10G    Not Present
Et4/2                                   notconnect   1        full   10G    Not Present
Et4/3                                   notconnect   1        full   10G    Not Present
Et4/4                                   notconnect   1        full   10G    Not Present
Et5/1                                   notconnect   1        full   10G    Not Present
Et5/2                                   notconnect   1        full   10G    Not Present
Et5/3                                   notconnect   1        full   10G    Not Present
Et5/4                                   notconnect   1        full   10G    Not Present
Et6/1                                   notconnect   1        full   10G    Not Present
Et6/2                                   notconnect   1        full   10G    Not Present
Et6/3                                   notconnect   1        full   10G    Not Present
Et6/4                                   notconnect   1        full   10G    Not Present
Et7/1                                   notconnect   1        full   10G    Not Present
Et7/2                                   notconnect   1        full   10G    Not Present
Et7/3                                   notconnect   1        full   10G    Not Present
Et7/4                                   notconnect   1        full   10G    Not Present
Et8/1                                   notconnect   1        full   10G    Not Present
Et8/2                                   notconnect   1        full   10G    Not Present
Et8/3                                   notconnect   1        full   10G    Not Present
Et8/4                                   notconnect   1        full   10G    Not Present
Et9/1                                   notconnect   1        full   10G    Not Present
Et9/2                                   notconnect   1        full   10G    Not Present
Et9/3                                   notconnect   1        full   10G    Not Present
Et9/4                                   notconnect   1        full   10G    Not Present
Et10/1                                  notconnect   1        full   10G    Not Present
Et10/2                                  notconnect   1        full   10G    Not Present
Et10/3                                  notconnect   1        full   10G    Not Present
Et10/4                                  notconnect   1        full   10G    Not Present
Et11/1                                  notconnect   1        full   10G    Not Present
Et11/2                                  notconnect   1        full   10G    Not Present
Et11/3                                  notconnect   1        full   10G    Not Present
Et11/4                                  notconnect   1        full   10G    Not Present
Et12/1                                  notconnect   1        full   10G    Not Present
Et12/2                                  notconnect   1        full   10G    Not Present
Et12/3                                  notconnect   1        full   10G    Not Present
Et12/4                                  notconnect   1        full   10G    Not Present
Et13/1                                  notconnect   1        full   10G    Not Present
Et13/2                                  notconnect   1        full   10G    Not Present
Et13/3                                  notconnect   1        full   10G    Not Present
Et13/4                                  notconnect   1        full   10G    Not Present
Et14/1                                  notconnect   1        full   10G    Not Present
Et14/2                                  notconnect   1        full   10G    Not Present
Et14/3                                  notconnect   1        full   10G    Not Present
Et14/4                                  notconnect   1        full   10G    Not Present
Et15/1                                  notconnect   1        full   10G    Not Present
Et15/2                                  notconnect   1        full   10G    Not Present
Et15/3                                  notconnect   1        full   10G    Not Present
Et15/4                                  notconnect   1        full   10G    Not Present
Et16/1                                  notconnect   1        full   10G    Not Present
Et16/2                                  notconnect   1        full   10G    Not Present
Et16/3                                  notconnect   1        full   10G    Not Present
Et16/4                                  notconnect   1        full   10G    Not Present
Et17/1                                  notconnect   1        full   10G    Not Present
Et17/2                                  notconnect   1        full   10G    Not Present
Et17/3                                  notconnect   1        full   10G    Not Present
Et17/4                                  notconnect   1        full   10G    Not Present
Et18/1                                  notconnect   1        full   10G    Not Present
Et18/2                                  notconnect   1        full   10G    Not Present
Et18/3                                  notconnect   1        full   10G    Not Present
Et18/4                                  notconnect   1        full   10G    Not Present
Et19/1                                  notconnect   1        full   10G    Not Present
Et19/2                                  notconnect   1        full   10G    Not Present
Et19/3                                  notconnect   1        full   10G    Not Present
Et19/4                                  notconnect   1        full   10G    Not Present
Et20/1                                  notconnect   1        full   10G    Not Present
Et20/2                                  notconnect   1        full   10G    Not Present
Et20/3                                  notconnect   1        full   10G    Not Present
Et20/4                                  notconnect   1        full   10G    Not Present
Et21/1                                  notconnect   1        full   10G    Not Present
Et21/2                                  notconnect   1        full   10G    Not Present
Et21/3                                  notconnect   1        full   10G    Not Present
Et21/4                                  notconnect   1        full   10G    Not Present
Et22/1                                  notconnect   1        full   10G    Not Present
Et22/2                                  notconnect   1        full   10G    Not Present
Et22/3                                  notconnect   1        full   10G    Not Present
Et22/4                                  notconnect   1        full   10G    Not Present
Et23/1                                  notconnect   1        full   10G    Not Present
Et23/2                                  notconnect   1        full   10G    Not Present
Et23/3                                  notconnect   1        full   10G    Not Present
Et23/4                                  notconnect   1        full   10G    Not Present
Et24/1                                  notconnect   1        full   10G    Not Present
Et24/2                                  notconnect   1        full   10G    Not Present
Et24/3                                  notconnect   1        full   10G    Not Present
Et24/4                                  notconnect   1        full   10G    Not Present
Et25                                    disabled     1        full   40G    40GBASE-AR4
Et26       Inter-Switch Link to Brocade connected    trunk    full   40G    40GBASE-AR4
Et27       Proxmox Host                 connected    trunk    full   40G    40GBASE-AR4
Et28       Proxmox Host                 connected    trunk    full   40G    40GBASE-AR4
Et29       Proxmox Host                 connected    trunk    full   40G    40GBASE-AR4
Et30                                    notconnect   1        full   40G    Not Present
Et31                                    notconnect   1        full   40G    Not Present
Et32                                    notconnect   1        full   40G    Not Present
Ma1                                     connected    routed   a-full a-1G   10/100/1000
```

---

### 4. Interface Descriptions

**Command:**
```bash
show interface description
```

**Output:**
```
Interface                      Status         Protocol           Description
Et1/1                          down           notpresent
Et1/2                          down           notpresent
Et1/3                          down           notpresent
Et1/4                          down           notpresent
Et2/1                          down           notpresent
Et2/2                          down           notpresent
Et2/3                          down           notpresent
Et2/4                          down           notpresent
Et3/1                          down           notpresent
Et3/2                          down           notpresent
Et3/3                          down           notpresent
Et3/4                          down           notpresent
Et4/1                          down           notpresent
Et4/2                          down           notpresent
Et4/3                          down           notpresent
Et4/4                          down           notpresent
Et5/1                          down           notpresent
Et5/2                          down           notpresent
Et5/3                          down           notpresent
Et5/4                          down           notpresent
Et6/1                          down           notpresent
Et6/2                          down           notpresent
Et6/3                          down           notpresent
Et6/4                          down           notpresent
Et7/1                          down           notpresent
Et7/2                          down           notpresent
Et7/3                          down           notpresent
Et7/4                          down           notpresent
Et8/1                          down           notpresent
Et8/2                          down           notpresent
Et8/3                          down           notpresent
Et8/4                          down           notpresent
Et9/1                          down           notpresent
Et9/2                          down           notpresent
Et9/3                          down           notpresent
Et9/4                          down           notpresent
Et10/1                         down           notpresent
Et10/2                         down           notpresent
Et10/3                         down           notpresent
Et10/4                         down           notpresent
Et11/1                         down           notpresent
Et11/2                         down           notpresent
Et11/3                         down           notpresent
Et11/4                         down           notpresent
Et12/1                         down           notpresent
Et12/2                         down           notpresent
Et12/3                         down           notpresent
Et12/4                         down           notpresent
Et13/1                         down           notpresent
Et13/2                         down           notpresent
Et13/3                         down           notpresent
Et13/4                         down           notpresent
Et14/1                         down           notpresent
Et14/2                         down           notpresent
Et14/3                         down           notpresent
Et14/4                         down           notpresent
Et15/1                         down           notpresent
Et15/2                         down           notpresent
Et15/3                         down           notpresent
Et15/4                         down           notpresent
Et16/1                         down           notpresent
Et16/2                         down           notpresent
Et16/3                         down           notpresent
Et16/4                         down           notpresent
Et17/1                         down           notpresent
Et17/2                         down           notpresent
Et17/3                         down           notpresent
Et17/4                         down           notpresent
Et18/1                         down           notpresent
Et18/2                         down           notpresent
Et18/3                         down           notpresent
Et18/4                         down           notpresent
Et19/1                         down           notpresent
Et19/2                         down           notpresent
Et19/3                         down           notpresent
Et19/4                         down           notpresent
Et20/1                         down           notpresent
Et20/2                         down           notpresent
Et20/3                         down           notpresent
Et20/4                         down           notpresent
Et21/1                         down           notpresent
Et21/2                         down           notpresent
Et21/3                         down           notpresent
Et21/4                         down           notpresent
Et22/1                         down           notpresent
Et22/2                         down           notpresent
Et22/3                         down           notpresent
Et22/4                         down           notpresent
Et23/1                         down           notpresent
Et23/2                         down           notpresent
Et23/3                         down           notpresent
Et23/4                         down           notpresent
Et24/1                         down           notpresent
Et24/2                         down           notpresent
Et24/3                         down           notpresent
Et24/4                         down           notpresent
Et25                           admin down     down
Et26                           up             up                 Inter-Switch Link to Brocade
Et27                           up             up                 Proxmox Host
Et28                           up             up                 Proxmox Host
Et29                           up             up                 Proxmox Host
Et30                           down           notpresent
Et31                           down           notpresent
Et32                           down           notpresent
Ma1                            up             up
Vl1                            up             up
```

---

### 5. Port-Channel Configuration

**Command:**
```bash
show port-channel summary
```

**Output:**
```

                  Flags
-------------------------- ----------------------------- -------------------------
   a - LACP Active            p - LACP Passive           * - static fallback
   F - Fallback enabled       f - Fallback configured    ^ - individual fallback
   U - In Use                 D - Down
   + - In-Sync                - - Out-of-Sync            i - incompatible with agg
   P - bundled in Po          s - suspended              G - Aggregable
   I - Individual             S - ShortTimeout           w - wait for agg

Number of channels in use: 0
Number of aggregators: 0

   Port-Channel       Protocol    Ports
------------------ -------------- -----

```

**Command:**
```bash
show port-channel detailed
```

**Output:**
```
No Output
```

---

### 6. LACP Status

**Command:**
```bash
show lacp neighbor
```

**Output:**
```
No Output
```

---

### 7. Specific Interface Details (40Gb links to Brocade)

**Command:**
```bash
show interface ethernet 25
```

**Output:**
```
Ethernet25 is administratively down, line protocol is down (disabled)
  Hardware is Ethernet, address is 444c.a815.e158 (bia 444c.a815.e158)
  Ethernet MTU 9214 bytes , BW 40000000 kbit
  Full-duplex, 40Gb/s, auto negotiation: off, uni-link: n/a
  Down 14 hours, 33 minutes, 12 seconds
  Loopback Mode : None
  5 link status changes since last clear
  Last clearing of "show interface" counters 16:18:26 ago
  5 minutes input rate 0 bps (0.0% with framing overhead), 0 packets/sec
  5 minutes output rate 0 bps (0.0% with framing overhead), 0 packets/sec
     4450102 packets input, 6633930106 bytes
     Received 13981 broadcasts, 57797 multicast
     0 runts, 0 giants
     0 input errors, 0 CRC, 0 alignment, 0 symbol, 0 input discards
     0 PAUSE input
     201 packets output, 37260 bytes
     Sent 0 broadcasts, 201 multicast
     0 output errors, 0 collisions
     0 late collision, 0 deferred, 0 output discards
     0 PAUSE output
```

**Command:**
```bash
show interface ethernet 26
```

**Output:**
```
Ethernet26 is up, line protocol is up (connected)
  Hardware is Ethernet, address is 444c.a815.e159 (bia 444c.a815.e159)
  Description: Inter-Switch Link to Brocade
  Ethernet MTU 9214 bytes , BW 40000000 kbit
  Full-duplex, 40Gb/s, auto negotiation: off, uni-link: n/a
  Up 16 hours, 12 minutes, 33 seconds
  Loopback Mode : None
  4 link status changes since last clear
  Last clearing of "show interface" counters 16:18:39 ago
  5 minutes input rate 254 kbps (0.0% with framing overhead), 305 packets/sec
  5 minutes output rate 59 bps (0.0% with framing overhead), 0 packets/sec
     46136774 packets input, 9863804658 bytes
     Received 132346 broadcasts, 453253 multicast
     0 runts, 0 giants
     0 input errors, 0 CRC, 0 alignment, 0 symbol, 0 input discards
     0 PAUSE input
     1972 packets output, 415112 bytes
     Sent 3 broadcasts, 1958 multicast
     0 output errors, 0 collisions
     0 late collision, 0 deferred, 0 output discards
     0 PAUSE output
```

---

### 8. Specific Interface Details (40Gb links to Proxmox - identify ports)

**Command:**
```bash
show interface ethernet 1-10 status
```

**Output:**
```
No Output
```

---

### 9. Running Configuration Snippet (Port-Channel and relevant interfaces)

**Command:**
```bash
show running-config | section Port-Channel
```

**Output:**
```
No Output
```

**Command:**
```bash
show running-config | section Ethernet49
```

**Output:**
```
No Output
```

**Command:**
```bash
show running-config | section Ethernet50
```

**Output:**
```
No Output
```

---

### 10. Full Running Config (Optional - for backup)

**Command:**
```bash
show running-config
```

**Output:**
```
[PASTE OUTPUT HERE - Or save to separate file]
```

---
