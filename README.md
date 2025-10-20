<div align="center">

<img src="https://raw.githubusercontent.com/dapperdivers/dapper-cluster/main/docs/src/assets/logo.png" align="center" width="144px" height="144px"/>

### <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f680/512.gif" alt="🚀" width="16" height="16"> My Home Operations Repository <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f6a7/512.gif" alt="🚧" width="16" height="16">

_... managed with Flux, Renovate, and GitHub Actions_ <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f916/512.gif" alt="🤖" width="16" height="16">

</div>

<div align="center">

[![Discord](https://img.shields.io/discord/673534664354430999?style=for-the-badge&label&logo=discord&logoColor=white&color=blue)](https://discord.gg/home-operations)&nbsp;&nbsp;
[![Talos](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.chelonianlabs.com%2Ftalos_version&style=for-the-badge&logo=talos&logoColor=white&color=blue&label=%20)](https://talos.dev)&nbsp;&nbsp;
[![Kubernetes](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.chelonianlabs.com%2Fkubernetes_version&style=for-the-badge&logo=kubernetes&logoColor=white&color=blue&label=%20)](https://kubernetes.io)&nbsp;&nbsp;
[![Flux](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.chelonianlabs.com%2Fflux_version&style=for-the-badge&logo=flux&logoColor=white&color=blue&label=%20)](https://fluxcd.io)&nbsp;&nbsp;
[![Renovate](https://img.shields.io/github/actions/workflow/status/dapperdivers/dapper-cluster/renovate.yaml?branch=main&label=&logo=renovatebot&style=for-the-badge&color=blue)](https://github.com/dapperdivers/dapper-cluster/actions/workflows/renovate.yaml)

</div>

<div align="center">

[![Home-Internet](https://img.shields.io/uptimerobot/status/m793494864-dfc695db066960233ac70f45?color=brightgreeen&label=Home%20Internet&style=for-the-badge&logo=ubiquiti&logoColor=white)](https://status.chelonianlabs.com)&nbsp;&nbsp;
[![Status-Page](https://img.shields.io/uptimerobot/status/m793599155-ba1b18e51c9f8653acd0f5c1?color=brightgreeen&label=Status%20Page&style=for-the-badge&logo=statuspage&logoColor=white)](https://status.chelonianlabs.com)&nbsp;&nbsp;
[![Alertmanager](https://img.shields.io/uptimerobot/status/m793494864-dfc695db066960233ac70f45?color=brightgreeen&label=Alertmanager&style=for-the-badge&logo=prometheus&logoColor=white)](https://status.chelonianlabs.com)

</div>

<div align="center">

[![Age-Days](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.chelonianlabs.com%2Fcluster_age_days&style=flat-square&label=Age)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Uptime-Days](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.chelonianlabs.com%2Fcluster_uptime_days&style=flat-square&label=Uptime)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Node-Count](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.chelonianlabs.com%2Fcluster_node_count&style=flat-square&label=Nodes)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Pod-Count](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.chelonianlabs.com%2Fcluster_pod_count&style=flat-square&label=Pods)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![CPU-Usage](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.chelonianlabs.com%2Fcluster_cpu_usage&style=flat-square&label=CPU)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Memory-Usage](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.chelonianlabs.com%2Fcluster_memory_usage&style=flat-square&label=Memory)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Power-Usage](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.chelonianlabs.com%2Fcluster_power_usage&style=flat-square&label=Power)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Alerts](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.chelonianlabs.com%2Fcluster_alert_count&style=flat-square&label=Alerts)](https://github.com/kashalls/kromgo)

</div>

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f4a1/512.gif" alt="💡" width="20" height="20"> Overview

This is a mono repository for my home infrastructure and Kubernetes cluster. I try to adhere to Infrastructure as Code (IaC) and GitOps practices using tools like [Ansible](https://www.ansible.com/), [Terraform](https://www.terraform.io/), [Kubernetes](https://kubernetes.io/), [Flux](https://github.com/fluxcd/flux2), [Renovate](https://github.com/renovatebot/renovate), and [GitHub Actions](https://github.com/features/actions).

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f331/512.gif" alt="🌱" width="20" height="20"> Kubernetes

My Kubernetes cluster is deployed with [Talos](https://www.talos.dev). Storage is provided by multiple solutions including NFS via democratic-csi and local storage options.

**Storage Architecture:**
- **NFS Storage**: democratic-csi for shared filesystem access
- **Local Storage**: Talos local storage for high-performance workloads
- **Legacy Storage**: 2x Unraid VMs providing media storage (migration in progress)
- **Network**: Multi-tier network with 40Gb links for storage traffic
- **Total Capacity**: 476.96TB raw across 76 drives

There is a template over at [onedr0p/cluster-template](https://github.com/onedr0p/cluster-template) if you want to try and follow along with some of the practices used here.

### Core Components

**Networking:**
- [cilium](https://github.com/cilium/cilium): eBPF-based CNI with kube-proxy replacement, L2 announcements, and advanced networking features.
- [multus-cni](https://github.com/k8snetworkplumbingwg/multus-cni): Multiple network interfaces per pod for IoT and legacy network integration.
- [ingress-nginx](https://github.com/kubernetes/ingress-nginx): Dual ingress controllers (internal + external) for service routing.
- [external-dns](https://github.com/kubernetes-sigs/external-dns): Automatic DNS management (internal via UniFi, external via Cloudflare).
- [k8s-gateway](https://github.com/ori-edge/k8s_gateway): Internal DNS server for cluster services.
- [cloudflared](https://github.com/cloudflare/cloudflared): Secure Cloudflare tunnels for external access.

**Storage:**
- [democratic-csi](https://github.com/democratic-csi/democratic-csi): NFS storage provisioner for shared workloads.
- [volsync](https://github.com/backube/volsync): PVC backup and recovery.

**Security & Secrets:**
- [cert-manager](https://github.com/cert-manager/cert-manager): Automated SSL/TLS certificate management.
- [external-secrets](https://github.com/external-secrets/external-secrets): Secrets management using [Infisical](https://infisical.com/).
- [sops](https://github.com/getsops/sops): Encrypted secrets in Git.

**Observability:**
- [kube-prometheus-stack](https://github.com/prometheus-operator/kube-prometheus-stack): Prometheus, Grafana, and Alertmanager.
- [loki](https://github.com/grafana/loki): Log aggregation and query.
- [promtail](https://github.com/grafana/promtail): Log shipper for Loki.
- [gatus](https://github.com/TwiN/gatus): Service health monitoring and status page.

**GPU & Hardware:**
- [nvidia-device-plugin](https://github.com/NVIDIA/k8s-device-plugin): GPU support for 4x Tesla P100 GPUs.
- [intel-device-plugin](https://github.com/intel/intel-device-plugins-for-kubernetes): Intel hardware acceleration.
- [node-feature-discovery](https://github.com/kubernetes-sigs/node-feature-discovery): Automatic hardware capability detection.

**GitOps & Automation:**
- [actions-runner-controller](https://github.com/actions/actions-runner-controller): Self-hosted GitHub runners.
- [spegel](https://github.com/spegel-org/spegel): Stateless cluster-local OCI registry mirror.
- [system-upgrade-controller](https://github.com/rancher/system-upgrade-controller): Automated Talos system upgrades.

### GitOps

[Flux](https://github.com/fluxcd/flux2) watches the clusters in my [kubernetes](./kubernetes/) folder (see Directories below) and makes the changes to my clusters based on the state of my Git repository.

The way Flux works for me here is it will recursively search the `kubernetes/apps` folder until it finds the most top level `kustomization.yaml` per directory and then apply all the resources listed in it. That aforementioned `kustomization.yaml` will generally only have a namespace resource and one or many Flux kustomizations (`ks.yaml`). Under the control of those Flux kustomizations there will be a `HelmRelease` or other resources related to the application which will be applied.

[Renovate](https://github.com/renovatebot/renovate) watches my **entire** repository looking for dependency updates, when they are found a PR is automatically created. When some PRs are merged Flux applies the changes to my cluster.

### Directories

This Git repository contains the following directories under [Kubernetes](./kubernetes/).

```sh
📁 kubernetes
├── 📁 apps           # applications
├── 📁 bootstrap      # bootstrap procedures
├── 📁 components     # re-useable components
└── 📁 flux           # flux system configuration
```

### Flux Workflow

This is a high-level look how Flux deploys my applications with dependencies. In most cases a `HelmRelease` will depend on other `HelmRelease`'s, in other cases a `Kustomization` will depend on other `Kustomization`'s, and in rare situations an app can depend on a `HelmRelease` and a `Kustomization`. The example below shows that `plex` won't be deployed or upgrade until the storage dependencies are installed and in a healthy state.

```mermaid
graph TD
    %% Styling
    classDef kustomization fill:#2f73d8,stroke:#fff,stroke-width:2px,color:#fff
    classDef helmRelease fill:#389826,stroke:#fff,stroke-width:2px,color:#fff

    %% Nodes
    A>Kustomization: democratic-csi]:::kustomization
    B[HelmRelease: democratic-csi]:::helmRelease
    C[Kustomization: democratic-csi-driver]:::kustomization
    D>Kustomization: plex]:::kustomization
    E[HelmRelease: plex]:::helmRelease

    %% Relationships with styled edges
    A -->|Creates| B
    A -->|Creates| C
    C -->|Depends on| B
    D -->|Creates| E
    E -->|Depends on| C

    %% Link styling
    linkStyle default stroke:#666,stroke-width:2px
```

### Networking

My network spans two physical locations connected via a 60GHz wireless bridge, featuring a multi-tier switching architecture optimized for high-performance storage and compute workloads.

<details>
  <summary>Physical Network Topology</summary>

```mermaid
graph TB
    %% Styling
    classDef router fill:#d83933,stroke:#fff,stroke-width:2px,color:#fff
    classDef coreswitch fill:#2f73d8,stroke:#fff,stroke-width:2px,color:#fff
    classDef distswitch fill:#389826,stroke:#fff,stroke-width:2px,color:#fff
    classDef accessswitch fill:#f39c12,stroke:#fff,stroke-width:2px,color:#fff
    classDef server fill:#8e44ad,stroke:#fff,stroke-width:2px,color:#fff
    classDef wireless fill:#e74c3c,stroke:#fff,stroke-width:2px,color:#fff

    subgraph House["🏠 House"]
        OPN["OPNsense<br/>192.168.1.1<br/>Gateway"]:::router
        ARUBA["Aruba S2500-48p<br/>192.168.1.26<br/>PoE Access Switch"]:::accessswitch
        CLIENTS["Client Devices"]
        WHOUSE["Mikrotik NRay60<br/>192.168.1.7"]:::wireless

        OPN --- ARUBA
        ARUBA --- CLIENTS
        ARUBA --- WHOUSE
    end

    subgraph Bridge["⚡ 60GHz Bridge"]
        WHOUSE -.1Gbps Wireless.-> WSHOP
    end

    subgraph Garage["🏭 Garage/Shop"]
        WSHOP["Mikrotik NRay60<br/>192.168.1.8"]:::wireless
        BROCADE["Brocade ICX6610<br/>192.168.1.20<br/>Core L3 Switch"]:::coreswitch
        ARISTA["Arista 7050<br/>192.168.1.21<br/>40Gb Distribution"]:::distswitch

        PX1["Proxmox-01<br/>4C/16GB"]:::server
        PX2["Proxmox-02<br/>24C/196GB"]:::server
        PX3["Proxmox-03<br/>64C/516GB"]:::server
        PX4["Proxmox-04<br/>24C/196GB"]:::server

        WSHOP --- BROCADE
        BROCADE <-->|2x 40Gb LAG| ARISTA

        PX1 -->|2x10Gb + 2x1Gb| BROCADE
        PX2 -->|2x10Gb + 2x1Gb| BROCADE
        PX3 -->|2x10Gb + 2x1Gb| BROCADE
        PX4 -->|2x10Gb + 2x1Gb| BROCADE

        PX1 -.40Gb Storage.-> ARISTA
        PX2 -.40Gb Storage.-> ARISTA
        PX3 -.40Gb Storage.-> ARISTA
        PX4 -.40Gb Storage.-> ARISTA
    end

    style House fill:#ecf0f1,stroke:#34495e,stroke-width:3px
    style Garage fill:#ecf0f1,stroke:#34495e,stroke-width:3px
    style Bridge fill:#ffebee,stroke:#c62828,stroke-width:2px
```

**Key Features:**
- Dual locations connected via 60GHz wireless (1Gbps)
- Multi-tier switching: Core (Brocade), Distribution (Arista), Access (Aruba)
- Dedicated 40Gb storage network on Arista
- LACP bonding on server links for redundancy

</details>

<details>
  <summary>Kubernetes Cluster</summary>

```mermaid
graph TB
    %% Styling
    classDef control fill:#2f73d8,stroke:#fff,stroke-width:2px,color:#fff
    classDef worker fill:#389826,stroke:#fff,stroke-width:2px,color:#fff
    classDef gpu fill:#e74c3c,stroke:#fff,stroke-width:2px,color:#fff
    classDef vip fill:#f39c12,stroke:#fff,stroke-width:3px,color:#000

    VIP["Kubernetes API VIP<br/>10.100.0.40:6443"]:::vip

    subgraph ControlPlane["Control Plane Nodes"]
        CP1["talos-control-1<br/>10.100.0.50<br/>4 CPU / 16GB"]:::control
        CP2["talos-control-2<br/>10.100.0.51<br/>4 CPU / 16GB"]:::control
        CP3["talos-control-3<br/>10.100.0.52<br/>4 CPU / 16GB"]:::control
    end

    subgraph Workers["Worker Nodes"]
        GPU["talos-node-gpu-1<br/>10.100.0.53<br/>16 CPU / 128GB<br/>4x Tesla P100"]:::gpu
        W1["talos-node-large-1<br/>10.100.0.54<br/>16 CPU / 128GB"]:::worker
        W2["talos-node-large-2<br/>10.100.0.55<br/>16 CPU / 128GB"]:::worker
        W3["talos-node-large-3<br/>10.100.0.56<br/>16 CPU / 128GB"]:::worker
    end

    VIP -.-> CP1
    VIP -.-> CP2
    VIP -.-> CP3

    style ControlPlane fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Workers fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
```

**Cluster Configuration:**
- **Total Nodes:** 7 (3 control plane, 4 workers)
- **Total Resources:** 76 CPU cores, 560GB RAM, 4x Tesla P100 GPUs
- **OS:** Talos Linux
- **CNI:** Cilium with eBPF (10.69.0.0/16 pod CIDR)
- **API VIP:** 10.100.0.40 (shared across control plane)

</details>

<details>
  <summary>VLAN & Network Segmentation</summary>

```mermaid
graph LR
    %% Styling
    classDef mgmt fill:#95a5a6,stroke:#fff,stroke-width:2px,color:#fff
    classDef servers fill:#3498db,stroke:#fff,stroke-width:2px,color:#fff
    classDef storage fill:#e74c3c,stroke:#fff,stroke-width:2px,color:#fff
    classDef k8s fill:#2ecc71,stroke:#fff,stroke-width:2px,color:#fff

    subgraph Physical["Physical Networks"]
        V1["VLAN 1<br/>192.168.1.0/24<br/>Management<br/>MTU 1500"]:::mgmt
        V100["VLAN 100<br/>10.100.0.0/24<br/>Servers/VMs<br/>MTU 1500"]:::servers
        V150["VLAN 150<br/>10.150.0.0/24<br/>Storage Public<br/>MTU 9000"]:::storage
        V200["VLAN 200<br/>10.200.0.0/24<br/>Storage Cluster<br/>MTU 9000"]:::storage
    end

    subgraph Kubernetes["Kubernetes Networks"]
        POD["Pod Network<br/>10.69.0.0/16<br/>Cilium CNI"]:::k8s
        SVC["Service Network<br/>10.96.0.0/16<br/>ClusterIP"]:::k8s
    end

    V100 -.Talos VMs.-> POD
    V100 -.Talos VMs.-> SVC
    V150 -.CSI Drivers.-> POD

    style Physical fill:#ecf0f1,stroke:#34495e,stroke-width:2px
    style Kubernetes fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
```

**Network Details:**
- **VLAN 1:** Switch management, IPMI, gateway: OPNsense
- **VLAN 100:** Kubernetes nodes, gateway: OPNsense, internet access
- **VLAN 150:** Storage client connections, jumbo frames, L2 only
- **VLAN 200:** Storage cluster traffic (40Gb dedicated), jumbo frames, L2 only
- **Pod Network:** Cilium eBPF-based CNI with native routing
- **Service Network:** Standard Kubernetes ClusterIP services

</details>

For detailed network documentation including switch configurations, see [Network Architecture](./docs/src/architecture/network-topology.md).

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f636_200d_1f32b_fe0f/512.gif" alt="😶" width="20" height="20"> Cloud Dependencies

While most of my infrastructure and workloads are self-hosted I do rely upon the cloud for certain key parts of my setup. This saves me from having to worry about three things. (1) Dealing with chicken/egg scenarios, (2) services I critically need whether my cluster is online or not and (3) The "hit by a bus factor" - what happens to critical apps (e.g. Email, Password Manager, Photos) that my family relies on when I no longer around.

Alternative solutions to the first two of these problems would be to host a Kubernetes cluster in the cloud and deploy applications like [HCVault](https://www.vaultproject.io/), [Vaultwarden](https://github.com/dani-garcia/vaultwarden), [ntfy](https://ntfy.sh/), and [Gatus](https://gatus.io/); however, maintaining another cluster and monitoring another group of workloads would be more work and probably be more or equal out to the same costs as described below.

| Service                                         | Use                                                               | Cost           |
|-------------------------------------------------|-------------------------------------------------------------------|----------------|
| [Infisical](https://infisical.com/)            | Secrets with [External Secrets](https://external-secrets.io/)     | Free           |
| [Cloudflare](https://www.cloudflare.com/)       | Domain and S3                                                     | Free           |
| [GCP](https://cloud.google.com/)                | Voice interactions with Home Assistant over Google Assistant      | Free           |
| [GitHub](https://github.com/)                   | Hosting this repository and continuous integration/deployments    | Free           |
| [Migadu](https://migadu.com/)                   | Email hosting                                                     | ~$20/yr        |
| [Pushover](https://pushover.net/)               | Kubernetes Alerts and application notifications                   | $5 OTP         |
| [UptimeRobot](https://uptimerobot.com/)         | Monitoring internet connectivity and external facing applications | Free           |
|                                                 |                                                                   | Total: ~$2/mo  |

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f30e/512.gif" alt="🌎" width="20" height="20"> DNS

In my cluster there are two instances of [ExternalDNS](https://github.com/kubernetes-sigs/external-dns) running. One for syncing private DNS records to my `UDM Pro Max` using [ExternalDNS webhook provider for UniFi](https://github.com/kashalls/external-dns-unifi-webhook), while another instance syncs public DNS to `Cloudflare`. This setup is managed by creating ingresses with two specific classes: `internal` for private DNS and `external` for public DNS. The `external-dns` instances then syncs the DNS records to their respective platforms accordingly.

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/2699_fe0f/512.gif" alt="⚙" width="20" height="20"> Hardware

### Compute Infrastructure

| Device | CPU | RAM | Storage | Network | Function |
|--------|-----|-----|---------|---------|----------|
| **Proxmox-01** | Intel Xeon E3-1230 V2<br/>(4 cores @ 3.30GHz) | 16GB | 24x 4TB HDD | 1Gb IPMI<br/>2x 1Gb<br/>2x 10Gb<br/>2x 40Gb | Primary Storage |
| **Proxmox-02** | 2x Intel Xeon X5680<br/>(24 cores @ 3.33GHz) | 196GB | 2x 120GB ZFS mirror | 1Gb IPMI<br/>2x 1Gb<br/>2x 10Gb<br/>2x 40Gb | Kubernetes + Ceph |
| **Proxmox-03** | 2x Intel Xeon E5-2697A v4<br/>(64 cores @ 2.60GHz) | 516GB | 1x 3.92TB SSD + 1x 800GB<br/>**4x Tesla P100 16GB** | 1Gb IPMI<br/>2x 1Gb<br/>2x 10Gb<br/>2x 40Gb | Kubernetes + Ceph<br/>**GPU Passthrough** |
| **Proxmox-04** | 2x Intel Xeon X5680<br/>(24 cores @ 3.33GHz) | 196GB | 8x 10TB + 1x 3.84TB + 1x 800GB | 1Gb IPMI<br/>2x 1Gb<br/>2x 10Gb<br/>2x 40Gb | Kubernetes + Ceph |

**Total Cluster Resources:**
- **CPU:** 116 cores total
- **RAM:** 924GB total
- **Storage:** 476.96TB raw (76 drives across all hosts + JBOD)
- **GPU:** 4x NVIDIA Tesla P100 16GB (64GB VRAM total)
- **Network:** Multi-tier switching with 40Gb Ceph network

### Kubernetes VMs (Talos Linux)

| VM Name | vCPU | RAM | Host | Role | Notes |
|---------|------|-----|------|------|-------|
| talos-control-1 | 4 | 16GB | Proxmox-03 | Control Plane | |
| talos-control-2 | 4 | 16GB | Proxmox-04 | Control Plane | |
| talos-control-3 | 4 | 16GB | Proxmox-02 | Control Plane | |
| talos-node-gpu-1 | 16 | 128GB | Proxmox-03 | Worker | 4x P100 GPU passthrough |
| talos-node-large-1 | 16 | 128GB | Proxmox-03 | Worker | |
| talos-node-large-2 | 16 | 128GB | Proxmox-03 | Worker | |
| talos-node-large-3 | 16 | 128GB | Proxmox-03 | Worker | |

**Kubernetes Cluster Totals:** 76 vCPU, 560GB RAM, 4x Tesla P100 GPUs

### Network Equipment

| Device | Model | Location | Role | Specs |
|--------|-------|----------|------|-------|
| **OPNsense Router** | Custom (i3-4130T) | House | Gateway/Firewall | 2C/4T @ 2.90GHz, 16GB RAM, 2.5Gb ATT Fiber |
| **Brocade ICX6610** | Enterprise Switch | Garage | Core L3 Switch | 48x 1/10Gb ports, 4x 40Gb QSFP+, VLAN routing |
| **Arista 7050** | Data Center Switch | Garage | Distribution | 48x 10Gb SFP+, 4x 40Gb QSFP+ |
| **Aruba S2500-48p** | Access Switch | House | PoE Access | 48x 1Gb PoE+ ports |
| **Mikrotik NRay60** | 60GHz Radio (x2) | Both | Wireless Bridge | 1Gbps point-to-point link |

### Storage

**Storage Distribution:**
- **Proxmox-01:** 24x 4TB HDD (96TB) - Unraid VM
- **Proxmox-03:** 3x 4TB + 7x 10TB + 2x 12TB (106TB) - Unraid VM
- **Proxmox-04:** 8x 10TB + 1x 3.84TB + 1x 800GB (84.64TB)
- **JBOD Shelf:** 18x 10TB + 1x 3.84TB + 1x 800GB (184.64TB)
- **Total Raw Capacity:** 476.96TB across 76 drives
- **Network:** Dedicated 40Gb network for storage traffic

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f31f/512.gif" alt="🌟" width="20" height="20"> Stargazers

<div align="center">

<a href="https://star-history.com/#dapperdivers/dapper-cluster&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=dapperdivers/dapper-cluster&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=dapperdivers/dapper-cluster&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=dapperdivers/dapper-cluster&type=Date" />
  </picture>
</a>

</div>

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f64f/512.gif" alt="🙏" width="20" height="20"> Gratitude and Thanks

Thanks to all the people who donate their time to the [Home Operations](https://discord.gg/home-operations) Discord community. Be sure to check out [kubesearch.dev](https://kubesearch.dev/) for ideas on how to deploy applications or get ideas on what you could deploy.
