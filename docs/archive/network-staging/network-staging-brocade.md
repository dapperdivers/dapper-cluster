## 🔧 Brocade ICX6610 (192.168.1.20)

### Connection

```bash
ssh admin@192.168.1.20
```

---

### 1. Basic System Information

**Command:**
```bash
show version
```

**Output:**
```txt
  Copyright (c) 1996-2016 Brocade Communications Systems, Inc. All rights reserved.
    UNIT 1: compiled on Apr 23 2020 at 13:17:12 labeled as FCXR08030u
		(10545591 bytes) from Primary ICX6610-FCX/FCXR08030u.bin
        SW: Version 08.0.30uT7f3
  Boot-Monitor Image size = 370695, Version:10.1.00T7f5 (grz10100)
  HW: Stackable ICX6610-48-HPOE
==========================================================================
UNIT 1: SL 1: ICX6610-48P POE 48-port Management Module
 	Serial  #: 2ax5o2jk68e
 	License: ICX6610_ADV_ROUTER_SOFT_PACKAGE   (LID: H4CKTH3PLN8)
 	P-ENGINE  0: type E02B, rev 01
 	P-ENGINE  1: type E02B, rev 01
==========================================================================
UNIT 1: SL 2: ICX6610-QSFP 10-port 160G Module
==========================================================================
UNIT 1: SL 3: ICX6610-8-port Dual Mode(SFP/SFP+) Module
==========================================================================
  800 MHz Power PC processor 8544E (version 0021/0023) 400 MHz bus
65536 KB flash memory
  512 MB DRAM
STACKID 1  system uptime is 62 day(s) 14 hour(s) 12 minute(s) 17 second(s)
The system started at 22:45:13 GMT-06 Tue Aug 12 2025

 The system : started=warm start	reloaded=by "reload"
```

---

### 2. VLAN Configuration

**Command:**
```bash
show vlan
```

**Output:**
```txt
Total PORT-VLAN entries: 6
Maximum PORT-VLAN entries: 64

Legend: [Stk=Stack-Id, S=Slot]

PORT-VLAN 1, Name DEFAULT, Priority level0, Spanning tree Off
 Untagged Ports: None
   Tagged Ports: None
   Uplink Ports: None
 DualMode Ports: (U1/M1)   1   2   3   4   5   6   7   8   9  10  11  12
 DualMode Ports: (U1/M1)  13  14  15  16  17  18  19  20  21  22  23  24
 DualMode Ports: (U1/M1)  25  26  27  28  29  30  31  32  33  34  35  36
 DualMode Ports: (U1/M1)  37  38  39  40  41  42  43  44  45  46  47  48

 DualMode Ports: (U1/M2)   1   2   3   4   5   6   7   8   9  10
 DualMode Ports: (U1/M3)   1   2   3   4   5   6   7   8
 Mac-Vlan Ports: None
     Monitoring: Disabled

PORT-VLAN 20, Name LAB, Priority level0, Spanning tree Off
 Untagged Ports: None
   Tagged Ports: (U1/M1)   1   2   3   4   5   6   7   8   9  10  11  12
   Tagged Ports: (U1/M1)  13  14  15  16  17  18  19  20  21  22  23  24
   Tagged Ports: (U1/M1)  25  26  27  28  29  30  31  32  33  34  35  36
   Tagged Ports: (U1/M1)  37  38  39  40  41  42  43  44  45  46  47  48

   Tagged Ports: (U1/M2)   1   2   3   4   5   6   7   8   9  10
   Tagged Ports: (U1/M3)   1   2   3   4   5   6   7   8
   Uplink Ports: None
 DualMode Ports: None
 Mac-Vlan Ports: None
     Monitoring: Disabled

PORT-VLAN 100, Name KUBERNETES, Priority level0, Spanning tree Off
 Untagged Ports: None
   Tagged Ports: (U1/M1)   1   2   3   4   5   6   7   8   9  10  11  12
   Tagged Ports: (U1/M1)  13  14  15  16  17  18  19  20  21  22  23  24
   Tagged Ports: (U1/M1)  25  26  27  28  29  30  31  32  33  34  35  36
   Tagged Ports: (U1/M1)  37  38  39  40  41  42  43  44  45  46  47  48

   Tagged Ports: (U1/M2)   1   2   3   4   5   6   7   8   9  10
   Tagged Ports: (U1/M3)   1   2   3   4   5   6   7   8
   Uplink Ports: None
 DualMode Ports: None
 Mac-Vlan Ports: None
     Monitoring: Disabled

PORT-VLAN 150, Name CEPH-PUBLIC, Priority level0, Spanning tree Off
 Untagged Ports: None
   Tagged Ports: (U1/M1)   1   2   3   4   5   6   7   8   9  10  11  12
   Tagged Ports: (U1/M1)  13  14  15  16  17  18  19  20  21  22  23  24
   Tagged Ports: (U1/M1)  25  26  27  28  29  30  31  32  33  34  35  36
   Tagged Ports: (U1/M1)  37  38  39  40  41  42  43  44  45  46  47  48

   Tagged Ports: (U1/M2)   1   2   3   4   5   6   7   8   9  10
   Tagged Ports: (U1/M3)   1   2   3   4   5   6   7   8
   Uplink Ports: None
 DualMode Ports: None
 Mac-Vlan Ports: None
     Monitoring: Disabled

PORT-VLAN 200, Name CEPH-STORAGE, Priority level0, Spanning tree Off
 Untagged Ports: None
   Tagged Ports: (U1/M1)   1   2   3   4   5   6   7   8   9  10  11  12
   Tagged Ports: (U1/M1)  13  14  15  16  17  18  19  20  21  22  23  24
   Tagged Ports: (U1/M1)  25  26  27  28  29  30  31  32  33  34  35  36
   Tagged Ports: (U1/M1)  37  38  39  40  41  42  43  44  45  46  47  48

   Tagged Ports: (U1/M2)   1   2   3   4   5   6   7   8   9  10
   Tagged Ports: (U1/M3)   1   2   3   4   5   6   7   8
   Uplink Ports: None
 DualMode Ports: None
 Mac-Vlan Ports: None
     Monitoring: Disabled

PORT-VLAN 1024, Name DEFAULT-VLAN, Priority level0, Spanning tree Off
 Untagged Ports: None
   Tagged Ports: None
   Uplink Ports: None
 DualMode Ports: None
 Mac-Vlan Ports: None
     Monitoring: Disabled
```

---

### 3. VLAN Interfaces (SVIs) with IPs

**Command:**
```bash
show interface brief | include ve
```

**Output:**
```
ve1        Up      N/A     N/A  N/A   None  N/A N/A  N/A 748e.f8e6.a3b4
ve100      Up      N/A     N/A  N/A   None  N/A N/A  N/A 748e.f8e6.a3b4
```

**Command:**
```bash
show running-config | begin "interface ve"
```

**Output:**
```
No Output
```

---

### 4. Port Descriptions and Assignments

**Command:**
```bash
show interface description
```

**Output:**
```
No Output
```

**Command:**
```bash
show interface brief
```

**Output:**
```
Port       Link    State   Dupl Speed Trunk Tag Pvid Pri MAC             Name
1/1/1      Disable None    None None  None  Yes 1    0   748e.f8e6.a3b4  "Uplink-1G-Back
1/1/2      Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/3      Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/4      Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/5      Up      Forward Full 1G    None  Yes 1    0   748e.f8e6.a3b4
1/1/6      Up      Forward Full 100M  None  Yes 1    0   748e.f8e6.a3b4  "Athena-IPMI"
1/1/7      Up      Forward Full 100M  None  Yes 1    0   748e.f8e6.a3b4  "Px03-IPMI"
1/1/8      Up      Forward Full 1G    None  Yes 1    0   748e.f8e6.a3b4  "Px04-IPMI"
1/1/9      Up      Forward Full 100M  None  Yes 1    0   748e.f8e6.a3b4  "Circe-IPMI"
1/1/10     Up      Forward Full 100M  None  Yes 1    0   748e.f8e6.a3b4  "Tower-IPMI"
1/1/11     Up      Forward Full 100M  None  Yes 1    0   748e.f8e6.a3b4
1/1/12     Up      Forward Full 100M  None  Yes 1    0   748e.f8e6.a3b4
1/1/13     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/14     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/15     Up      Forward Full 1G    10    Yes 1    0   748e.f8e6.a3b4  "Tower-1Gb-Pri"
1/1/16     Up      Forward Full 1G    10    Yes 1    0   748e.f8e6.a3b4  Tower-1Gb-Sec
1/1/17     Up      Forward Full 1G    9     Yes 1    0   748e.f8e6.a3b4  Circe-1Gb-Pri
1/1/18     Up      Forward Full 1G    9     Yes 1    0   748e.f8e6.a3b4  Circe-1Gb-Sec
1/1/19     Up      Forward Full 1G    8     Yes 1    0   748e.f8e6.a3b4  Px04-1Gb-Pri
1/1/20     Up      Forward Full 1G    8     Yes 1    0   748e.f8e6.a3b4  Px04-1Gb-Sec
1/1/21     Up      Forward Full 1G    7     Yes 1    0   748e.f8e6.a3b4  Px03-1Gb-Pri
1/1/22     Up      Forward Full 1G    7     Yes 1    0   748e.f8e6.a3b4  Px03-1Gb-Sec
1/1/23     Up      Forward Full 1G    6     Yes 1    0   748e.f8e6.a3b4  Athena-1Gb-Pri
1/1/24     Up      Forward Full 1G    6     Yes 1    0   748e.f8e6.a3b4  Athena-1Gb-Sec
1/1/25     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/26     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/27     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/28     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/29     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/30     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/31     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/32     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/33     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/34     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/35     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/36     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/37     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/38     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/39     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/40     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/41     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/42     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/43     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/44     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/45     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/46     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/1/47     Up      Forward Full 100M  None  Yes 1    0   748e.f8e6.a3b4  "Zigbee-Router"
1/1/48     Up      Forward Full 1G    None  Yes 1    0   748e.f8e6.a3b4  "UniFi-AP"
1/2/1      Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/2/2      Up      Forward Full 10G   2     Yes 1    0   748e.f8e6.a3b4  Px03-10Gb-Pri
1/2/3      Up      Forward Full 10G   2     Yes 1    0   748e.f8e6.a3b4  Px03-10Gb-Sec
1/2/4      Up      Forward Full 10G   3     Yes 1    0   748e.f8e6.a3b4  Px04-10Gb-Pri
1/2/5      Up      Forward Full 10G   3     Yes 1    0   748e.f8e6.a3b4  Px04-10Gb-Sec
1/2/6      Up      Forward Full 40G   None  Yes 1    0   748e.f8e6.a3b4
1/2/7      Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/2/8      Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/2/9      Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/2/10     Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
1/3/1      Up      Forward Full 10G   None  Yes 1    0   748e.f8e6.a3b4  "Uplink-10Gb-Pr
1/3/2      Up      Forward Full 10G   4     Yes 1    0   748e.f8e6.a3b4  Athena-10Gb-Pri
1/3/3      Up      Forward Full 10G   4     Yes 1    0   748e.f8e6.a3b4  Athena-10Gb-Sec
1/3/4      Up      Forward Full 10G   1     Yes 1    0   748e.f8e6.a3b4  Circe-10Gb-Pri
1/3/5      Up      Forward Full 10G   1     Yes 1    0   748e.f8e6.a3b4  Circe-10Gb-Sec
1/3/6      Up      Forward Full 10G   5     Yes 1    0   748e.f8e6.a3b4  "Tower-10Gb-Pri
1/3/7      Up      Forward Full 10G   5     Yes 1    0   748e.f8e6.a3b4  Tower-10Gb-Sec
1/3/8      Down    None    None None  None  Yes 1    0   748e.f8e6.a3b4
mgmt1      Up      None    Full 1G    None  No  None 0   748e.f8e6.a3b4

Port       Link    State   Dupl Speed Trunk Tag Pvid Pri MAC             Name
ve1        Up      N/A     N/A  N/A   None  N/A N/A  N/A 748e.f8e6.a3b4
ve100      Up      N/A     N/A  N/A   None  N/A N/A  N/A 748e.f8e6.a3b4
```

---

### 5. LAG Configuration

**Command:**
```bash
show lag
```

**Output:**
```
Total number of LAGs:          10
Total number of deployed LAGs: 10
Total number of trunks created:10 (110 available)
LACP System Priority / ID:     1 / 748e.f8e6.a3b4
LACP Long timeout:             120, default: 120
LACP Short timeout:            3, default: 3

=== LAG "athena-mgmt" ID 6 (dynamic Deployed) ===
LAG Configuration:
   Ports:         e 1/1/23 to 1/1/24
   Port Count:    2
   Primary Port:  1/1/23
   Trunk Type:    hash-based
   LACP Key:      20006
Deployment: HW Trunk ID 1
Port       Link    State   Dupl Speed Trunk Tag Pvid Pri MAC             Name
1/1/23     Up      Forward Full 1G    6     Yes 1    0   748e.f8e6.a3b4  Athena-1Gb-Pri
1/1/24     Up      Forward Full 1G    6     Yes 1    0   748e.f8e6.a3b4  Athena-1Gb-Sec

Port       [Sys P] [Port P] [ Key ] [Act][Tio][Agg][Syn][Col][Dis][Def][Exp][Ope]
1/1/23          1        1   20006   Yes   L   Agg  Syn  Col  Dis  No   No   Ope
1/1/24          1        1   20006   Yes   L   Agg  Syn  Col  Dis  No   No   Ope


 Partner Info and PDU Statistics
Port          Partner         Partner     LACP      LACP
             System ID         Key     Rx Count  Tx Count
1/1/23   65535-0025.9087.0bf8        9   172845   4895230
1/1/24   65535-0025.9087.0bf8        9   172845   4894988

=== LAG "athena-vm" ID 4 (dynamic Deployed) ===
LAG Configuration:
   Ports:         e 1/3/2 to 1/3/3
   Port Count:    2
   Primary Port:  1/3/2
   Trunk Type:    hash-based
   LACP Key:      20004
Deployment: HW Trunk ID 2
Port       Link    State   Dupl Speed Trunk Tag Pvid Pri MAC             Name
1/3/2      Up      Forward Full 10G   4     Yes 1    0   748e.f8e6.a3b4  Athena-10Gb-Pri
1/3/3      Up      Forward Full 10G   4     Yes 1    0   748e.f8e6.a3b4  Athena-10Gb-Sec

Port       [Sys P] [Port P] [ Key ] [Act][Tio][Agg][Syn][Col][Dis][Def][Exp][Ope]
1/3/2           1        1   20004   Yes   L   Agg  Syn  Col  Dis  No   No   Ope
1/3/3           1        1   20004   Yes   L   Agg  Syn  Col  Dis  No   No   Ope


 Partner Info and PDU Statistics
Port          Partner         Partner     LACP      LACP
             System ID         Key     Rx Count  Tx Count
1/3/2    65535-ec0d.9a75.ee42       15   172862   4894200
1/3/3    65535-ec0d.9a75.ee42       15   172858   4894199

=== LAG "circe-mgmt" ID 9 (dynamic Deployed) ===
LAG Configuration:
   Ports:         e 1/1/17 to 1/1/18
   Port Count:    2
   Primary Port:  1/1/17
   Trunk Type:    hash-based
   LACP Key:      20009
Deployment: HW Trunk ID 3
Port       Link    State   Dupl Speed Trunk Tag Pvid Pri MAC             Name
1/1/17     Up      Forward Full 1G    9     Yes 1    0   748e.f8e6.a3b4  Circe-1Gb-Pri
1/1/18     Up      Forward Full 1G    9     Yes 1    0   748e.f8e6.a3b4  Circe-1Gb-Sec

Port       [Sys P] [Port P] [ Key ] [Act][Tio][Agg][Syn][Col][Dis][Def][Exp][Ope]
1/1/17          1        1   20009   Yes   L   Agg  Syn  Col  Dis  No   No   Ope
1/1/18          1        1   20009   Yes   L   Agg  Syn  Col  Dis  No   No   Ope


 Partner Info and PDU Statistics
Port          Partner         Partner     LACP      LACP
             System ID         Key     Rx Count  Tx Count
1/1/17   65535-0cc4.7a0c.142a        9   172877   4023296
1/1/18   65535-0cc4.7a0c.142a        9   170595   4085636

=== LAG "circe-vm" ID 1 (dynamic Deployed) ===
LAG Configuration:
   Ports:         e 1/3/4 to 1/3/5
   Port Count:    2
   Primary Port:  1/3/4
   Trunk Type:    hash-based
   LACP Key:      20001
Deployment: HW Trunk ID 4
Port       Link    State   Dupl Speed Trunk Tag Pvid Pri MAC             Name
1/3/4      Up      Forward Full 10G   1     Yes 1    0   748e.f8e6.a3b4  Circe-10Gb-Pri
1/3/5      Up      Forward Full 10G   1     Yes 1    0   748e.f8e6.a3b4  Circe-10Gb-Sec

Port       [Sys P] [Port P] [ Key ] [Act][Tio][Agg][Syn][Col][Dis][Def][Exp][Ope]
1/3/4           1        1   20001   Yes   L   Agg  Syn  Col  Dis  No   No   Ope
1/3/5           1        1   20001   Yes   L   Agg  Syn  Col  Dis  No   No   Ope


 Partner Info and PDU Statistics
Port          Partner         Partner     LACP      LACP
             System ID         Key     Rx Count  Tx Count
1/3/4    65535-305a.3a78.c1ae       15   172815   4892873
1/3/5    65535-305a.3a78.c1ae       15   172817   4892758

=== LAG "px03-mgmt" ID 7 (dynamic Deployed) ===
LAG Configuration:
   Ports:         e 1/1/21 to 1/1/22
   Port Count:    2
   Primary Port:  1/1/21
   Trunk Type:    hash-based
   LACP Key:      20007
Deployment: HW Trunk ID 5
Port       Link    State   Dupl Speed Trunk Tag Pvid Pri MAC             Name
1/1/21     Up      Forward Full 1G    7     Yes 1    0   748e.f8e6.a3b4  Px03-1Gb-Pri
1/1/22     Up      Forward Full 1G    7     Yes 1    0   748e.f8e6.a3b4  Px03-1Gb-Sec

Port       [Sys P] [Port P] [ Key ] [Act][Tio][Agg][Syn][Col][Dis][Def][Exp][Ope]
1/1/21          1        1   20007   Yes   L   Agg  Syn  Col  Dis  No   No   Ope
1/1/22          1        1   20007   Yes   L   Agg  Syn  Col  Dis  No   No   Ope


 Partner Info and PDU Statistics
Port          Partner         Partner     LACP      LACP
             System ID         Key     Rx Count  Tx Count
1/1/21   65535-0025.9066.3f26        9     4839      5153
1/1/22   65535-0025.9066.3f26        9     4840      5164

=== LAG "px03-vm" ID 2 (dynamic Deployed) ===
LAG Configuration:
   Ports:         e 1/2/2 to 1/2/3
   Port Count:    2
   Primary Port:  1/2/2
   Trunk Type:    hash-based
   LACP Key:      20002
Deployment: HW Trunk ID 6
Port       Link    State   Dupl Speed Trunk Tag Pvid Pri MAC             Name
1/2/2      Up      Forward Full 10G   2     Yes 1    0   748e.f8e6.a3b4  Px03-10Gb-Pri
1/2/3      Up      Forward Full 10G   2     Yes 1    0   748e.f8e6.a3b4  Px03-10Gb-Sec

Port       [Sys P] [Port P] [ Key ] [Act][Tio][Agg][Syn][Col][Dis][Def][Exp][Ope]
1/2/2           1        1   20002   Yes   L   Agg  Syn  Col  Dis  No   No   Ope
1/2/3           1        1   20002   Yes   L   Agg  Syn  Col  Dis  No   No   Ope


 Partner Info and PDU Statistics
Port          Partner         Partner     LACP      LACP
             System ID         Key     Rx Count  Tx Count
1/2/2    65535-ec0d.9ad2.f854       15   156603   4152244
1/2/3    65535-ec0d.9ad2.f854       15   160035   4215910

=== LAG "px04-mgmt" ID 8 (dynamic Deployed) ===
LAG Configuration:
   Ports:         e 1/1/19 to 1/1/20
   Port Count:    2
   Primary Port:  1/1/19
   Trunk Type:    hash-based
   LACP Key:      20008
Deployment: HW Trunk ID 7
Port       Link    State   Dupl Speed Trunk Tag Pvid Pri MAC             Name
1/1/19     Up      Forward Full 1G    8     Yes 1    0   748e.f8e6.a3b4  Px04-1Gb-Pri
1/1/20     Up      Forward Full 1G    8     Yes 1    0   748e.f8e6.a3b4  Px04-1Gb-Sec

Port       [Sys P] [Port P] [ Key ] [Act][Tio][Agg][Syn][Col][Dis][Def][Exp][Ope]
1/1/19          1        1   20008   Yes   L   Agg  Syn  Col  Dis  No   No   Ope
1/1/20          1        1   20008   Yes   L   Agg  Syn  Col  Dis  No   No   Ope


 Partner Info and PDU Statistics
Port          Partner         Partner     LACP      LACP
             System ID         Key     Rx Count  Tx Count
1/1/19   65535-b06e.bf3a.6439        9   172806   4898260
1/1/20   65535-b06e.bf3a.6439        9   172801   4898191

=== LAG "px04-vm" ID 3 (dynamic Deployed) ===
LAG Configuration:
   Ports:         e 1/2/4 to 1/2/5
   Port Count:    2
   Primary Port:  1/2/4
   Trunk Type:    hash-based
   LACP Key:      20003
Deployment: HW Trunk ID 8
Port       Link    State   Dupl Speed Trunk Tag Pvid Pri MAC             Name
1/2/4      Up      Forward Full 10G   3     Yes 1    0   748e.f8e6.a3b4  Px04-10Gb-Pri
1/2/5      Up      Forward Full 10G   3     Yes 1    0   748e.f8e6.a3b4  Px04-10Gb-Sec

Port       [Sys P] [Port P] [ Key ] [Act][Tio][Agg][Syn][Col][Dis][Def][Exp][Ope]
1/2/4           1        1   20003   Yes   L   Agg  Syn  Col  Dis  No   No   Ope
1/2/5           1        1   20003   Yes   L   Agg  Syn  Col  Dis  No   No   Ope


 Partner Info and PDU Statistics
Port          Partner         Partner     LACP      LACP
             System ID         Key     Rx Count  Tx Count
1/2/4    65535-ec0d.9ad2.fb80       15   172797   4893782
1/2/5    65535-ec0d.9ad2.fb80       15   172797   4893777

=== LAG "tower-mgmt" ID 10 (dynamic Deployed) ===
LAG Configuration:
   Ports:         e 1/1/15 to 1/1/16
   Port Count:    2
   Primary Port:  1/1/15
   Trunk Type:    hash-based
   LACP Key:      20010
Deployment: HW Trunk ID 9
Port       Link    State   Dupl Speed Trunk Tag Pvid Pri MAC             Name
1/1/15     Up      Forward Full 1G    10    Yes 1    0   748e.f8e6.a3b4  "Tower-1Gb-Pri"
1/1/16     Up      Forward Full 1G    10    Yes 1    0   748e.f8e6.a3b4  Tower-1Gb-Sec

Port       [Sys P] [Port P] [ Key ] [Act][Tio][Agg][Syn][Col][Dis][Def][Exp][Ope]
1/1/15          1        1   20010   Yes   L   Agg  Syn  Col  Dis  No   No   Ope
1/1/16          1        1   20010   Yes   L   Agg  Syn  Col  Dis  No   No   Ope


 Partner Info and PDU Statistics
Port          Partner         Partner     LACP      LACP
             System ID         Key     Rx Count  Tx Count
1/1/15   65535-0025.9064.580a        9    38002    916321
1/1/16   65535-0025.9064.580a        9    38005    916381

=== LAG "tower-vm" ID 5 (dynamic Deployed) ===
LAG Configuration:
   Ports:         e 1/3/6 to 1/3/7
   Port Count:    2
   Primary Port:  1/3/6
   Trunk Type:    hash-based
   LACP Key:      20005
Deployment: HW Trunk ID 10
Port       Link    State   Dupl Speed Trunk Tag Pvid Pri MAC             Name
1/3/6      Up      Forward Full 10G   5     Yes 1    0   748e.f8e6.a3b4  "Tower-10Gb-Pri
1/3/7      Up      Forward Full 10G   5     Yes 1    0   748e.f8e6.a3b4  Tower-10Gb-Sec

Port       [Sys P] [Port P] [ Key ] [Act][Tio][Agg][Syn][Col][Dis][Def][Exp][Ope]
1/3/6           1        1   20005   Yes   L   Agg  Syn  Col  Dis  No   No   Ope
1/3/7           1        1   20005   Yes   L   Agg  Syn  Col  Dis  No   No   Ope


 Partner Info and PDU Statistics
Port          Partner         Partner     LACP      LACP
             System ID         Key     Rx Count  Tx Count
1/3/6    65535-ec0d.9abf.7f92       15   171286    253450
1/3/7    65535-ec0d.9abf.7f92       15   170056    246860
```

**Command:**
```bash
show lag brief
```

**Output:**
```
Total number of LAGs:          10
Total number of deployed LAGs: 10
Total number of trunks created:10 (110 available)
LACP System Priority / ID:     1 / 748e.f8e6.a3b4
LACP Long timeout:             120, default: 120
LACP Short timeout:            3, default: 3

LAG           Type   Deploy Trunk Primary  Port List
athena-mgmt   dynamic  Y    6     1/1/23   e 1/1/23 to 1/1/24
athena-vm     dynamic  Y    4     1/3/2    e 1/3/2 to 1/3/3
circe-mgmt    dynamic  Y    9     1/1/17   e 1/1/17 to 1/1/18
circe-vm      dynamic  Y    1     1/3/4    e 1/3/4 to 1/3/5
px03-mgmt     dynamic  Y    7     1/1/21   e 1/1/21 to 1/1/22
px03-vm       dynamic  Y    2     1/2/2    e 1/2/2 to 1/2/3
px04-mgmt     dynamic  Y    8     1/1/19   e 1/1/19 to 1/1/20
px04-vm       dynamic  Y    3     1/2/4    e 1/2/4 to 1/2/5
tower-mgmt    dynamic  Y    10    1/1/15   e 1/1/15 to 1/1/16
tower-vm      dynamic  Y    5     1/3/6    e 1/3/6 to 1/3/7
```

---

### 6. Specific Interface Details (40Gb links to Arista)

**Command:**
```bash
show interface ethernet 1/2/1
```

**Output:**
```
40GigabitEthernet1/2/1 is down, line protocol is down
  Port down for 14 hour(s) 29 minute(s) 20 second(s)
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
  Not member of any active trunks
  Not member of any configured trunks
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
```

**Command:**
```bash
show interface ethernet 1/2/6
```

**Output:**
```
40GigabitEthernet1/2/6 is up, line protocol is up
  Port up for 16 hour(s) 7 minute(s) 58 second(s)
  Hardware is 40GigabitEthernet, address is 748e.f8e6.a3b4 (bia 748e.f8e6.a3ea)
  Interface type is 40Gig Fiber
  Configured speed 40Gbit, actual 40Gbit, configured duplex fdx, actual fdx
  Configured mdi mode AUTO, actual none
  Member of 5 L2 VLANs, port is dual mode in Vlan 1, port state is FORWARDING
  BPDU guard is Disabled, ROOT protect is Disabled, Designated protect is Disabled
  Link Error Dampening is Disabled
  STP configured to ON, priority is level0, mac-learning is enabled
  Openflow is Disabled, Openflow Hybrid mode is Disabled,  Flow Control is enabled
  Mirror disabled, Monitor disabled
  Mac-notification is disabled
  Not member of any active trunks
  Not member of any configured trunks
  No port name
  MTU 1500 bytes, encapsulation ethernet
  300 second input rate: 56 bits/sec, 0 packets/sec, 0.00% utilization
  300 second output rate: 711632 bits/sec, 874 packets/sec, 0.00% utilization
  3169 packets input, 750017 bytes, 0 no buffer
  Received 672 broadcasts, 2486 multicasts, 11 unicasts
  0 input errors, 0 CRC, 0 frame, 0 ignored
  0 runts, 0 giants
  46378233 packets output, 9907335582 bytes, 0 underruns
  Transmitted 175236 broadcasts, 580725 multicasts, 45622272 unicasts
  0 output errors, 0 collisions
  Relay Agent Information option: Disabled

Egress queues:
Queue counters    Queued packets    Dropped Packets
    0            46377915                   0
    1                   0                   0
    2                   0                   0
    3                   0                   0
    4                   0                   0
    5                 323                   0
    6                   0                   0
    7                   0                   0
```

---

### 7. Routing Table

**Command:**
```bash
show ip route
```

**Output:**
```
Total number of IP routes: 3
Type Codes - B:BGP D:Connected O:OSPF R:RIP S:Static; Cost - Dist/Metric
BGP  Codes - i:iBGP e:eBGP
OSPF Codes - i:Inter Area 1:External Type 1 2:External Type 2
        Destination        Gateway         Port          Cost          Type Uptime
1       0.0.0.0/0          10.100.0.1      ve 100        1/1           S    62d14h
        0.0.0.0/0          192.168.1.1     ve 1          1/1           S    62d14h
2       10.100.0.0/24      DIRECT          ve 100        0/0           D    62d14h
3       192.168.1.0/24     DIRECT          ve 1          0/0           D    62d14h
```

**Command:**
```bash
show running-config | include "ip route"
```

**Output:**
```
No Output
```

---

### 8. VLAN Port Membership (for trunk identification)

**Command:**
```bash
show vlan brief
```

**Output:**
```
System-max vlan Params: Max(4095) Default(64) Current(64)
Default vlan Id :1024
Total Number of Vlan Configured :6
VLANs Configured :1 20 100 150 200 1024
```

---

### 9. Full Running Config (Optional - for backup)

**Command:**
```bash
show running-config
```

**Output:**
```
[PASTE OUTPUT HERE - Or save to separate file]
```

---
