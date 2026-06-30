# Dapper Cluster Documentation

This documentation covers the architecture, configuration, and operations of the Dapper Kubernetes cluster, a high-performance home lab infrastructure with GPU capabilities.

## Cluster Overview

```mermaid
graph TD
    subgraph Control Plane
        CP1[Control Plane 1<br>4 CPU, 16GB]
        CP2[Control Plane 2<br>4 CPU, 16GB]
        CP3[Control Plane 3<br>4 CPU, 16GB]
    end

    subgraph Worker Nodes
        W1[Worker 1<br>16 CPU, 128GB]
        W2[Worker 2<br>16 CPU, 128GB]
        GPU[GPU Node<br>16 CPU, 128GB<br>4x Tesla P100]
    end

    CP1 --- CP2
    CP2 --- CP3
    CP3 --- CP1

    Control Plane --> Worker Nodes
```

## Hardware Specifications

### Control Plane

- 3 nodes for high availability
- 4 CPU cores per node
- 16GB RAM per node
- Dedicated to cluster control plane operations

### Worker Nodes

- 8 worker nodes total: 1 GPU node, 3 large (16 CPU / 128GB), 4 small (6 CPU / 16GB)
- Handles general workloads, databases, media, and applications

### GPU Node

- Specialized GPU worker node
- 16 CPU cores
- 128GB RAM
- 4x NVIDIA Tesla P100 GPUs
- Handles ML/AI and GPU-accelerated workloads

## Key Features

- High-availability Kubernetes cluster
- GPU acceleration support
- Automated deployment using Flux CD
- Secure secrets management with SOPS + External Secrets (Infisical)
- External Ceph storage (RBD + CephFS) via Rook
- Comprehensive monitoring and observability
- Media services automation

## Infrastructure Components

```mermaid
graph TD
    subgraph Core Services
        Flux[Flux CD]
        Storage[Storage Layer]
        Network[Network Layer]
    end

    subgraph Applications
        Media[Media Stack]
        Monitor[Monitoring]
        GPU[GPU Workloads]
    end

    Core Services --> Applications

    Storage --> |Ceph RBD/CephFS| Applications
    Network --> |Envoy Gateway/DNS| Applications
```

## Documentation Structure

- **Architecture**: Detailed technical documentation about cluster design and components
  - High-availability control plane design
  - Storage architecture and configuration
  - Network topology and policies
  - GPU integration and management

- **Applications**: Information about deployed applications and their configurations
  - Media services stack
  - Monitoring and observability
  - GPU-accelerated applications

- **Operations**: Guides for installation, maintenance, and troubleshooting
  - Cluster setup procedures
  - Node management
  - GPU configuration
  - Maintenance tasks

## Getting Started

For new users, we recommend starting with:

1. [Architecture Overview](architecture/overview.md) - Understanding the cluster design
2. [Installation Guide](operations/installation.md) - Setting up the cluster
3. [Application Stack](apps/media.md) - Deploying applications

## Quick Links

- [Storage Configuration](architecture/storage.md)
- [Network Setup](architecture/network.md)
- [Maintenance Guide](operations/maintenance.md)
- [Troubleshooting](operations/troubleshooting.md)
