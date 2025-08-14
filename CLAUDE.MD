# Dapper Cluster - Home Operations Repository

## Overview
This is a GitOps-managed Kubernetes home cluster running on Talos Linux with Flux CD for automated deployments. The infrastructure follows Infrastructure as Code (IaC) principles with comprehensive monitoring, automation, and self-healing capabilities.

## Repository Structure

### Core Directories
- **`kubernetes/`** - Main Kubernetes manifests and configurations
- **`docs/`** - Documentation built with mdBook
- **`memory-bank/`** - Claude Code memory files for context persistence
- **`scripts/`** - Utility scripts for cluster operations
- **`resource-recommendations/`** - VPA and resource optimization data

### Kubernetes Applications Structure (`kubernetes/apps/`)
- **`actions-runner-system/`** - GitHub Actions self-hosted runners
- **`ai/`** - AI/ML workloads (LiteLLM, n8n, Ollama, Open WebUI, Wyoming Whisper)
- **`cert-manager/`** - TLS certificate management
- **`database/`** - Database services (CloudNative-PG, Dragonfly Redis, EMQX)
- **`default/`** - Default namespace applications
- **`external-secrets/`** - External secrets management
- **`flux-system/`** - Flux CD GitOps operator
- **`home-automation/`** - Home automation stack (ESPHome, Home Assistant, Node-RED, Zigbee2MQTT)
- **`kube-system/`** - Core Kubernetes system components
- **`kyverno/`** - Policy engine for Kubernetes
- **`media/`** - Media server stack (Plex, *arr apps, Overseerr, etc.)
- **`network/`** - Networking components (Ingress, DNS, SMTP relay)
- **`observability/`** - Monitoring stack (Prometheus, Grafana, Loki, Gatus)
- **`openebs-system/`** - OpenEBS storage system
- **`security/`** - Security applications (Authentik, Vaultwarden)
- **`selfhosted/`** - Self-hosted applications (Actual, Atuin, Paperless-NGX, etc.)
- **`storage/`** - Storage providers and volume management
- **`system-upgrade/`** - Automated system upgrades


## Key Patterns

### Common Components Pattern

**IMPORTANT**: All namespace-level kustomizations should inherit common components by including:
```yaml
components:
  - ../../flux/components/common
```

The common components at `/kubernetes/flux/components/common/` provide:
- Namespace creation
- Shared repository definitions (app-template, etc.)
- SOPS secret management configuration
- Centralized cluster configuration via substitutions

### Adding a New Application

1. Create namespace directory under `/kubernetes/apps/<namespace>/`
2. Create namespace `kustomization.yaml` with:
   ```yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization
   namespace: <namespace>
   components:
     - ../../flux/components/common  # Always include this!
   resources:
     - ./<app-name>/ks.yaml
   ```
3. Add `ks.yaml` defining the Flux Kustomization
4. Create `app/` subdirectory with:
   - `helmrelease.yaml` for Helm chart deployment
   - `kustomization.yaml` listing all resources
   - Any additional resources (secrets, configmaps, etc.)

## Standard File and Folder Naming Conventions

### Application Directory Structure

Each application follows this standardized structure:

```
/kubernetes/apps/<namespace>/<app-name>/
├── ks.yaml                        # Flux Kustomization (sync definition)
├── app/                           # Main application resources
│   ├── kustomization.yaml         # Lists all app resources
│   ├── helmrelease.yaml          # HelmRelease + HelmRepository
│   ├── helm/                     # Helm configuration (if needed)
│   │   ├── values.yaml           # Helm values
│   │   └── kustomizeconfig.yaml  # Kustomize configuration
│   ├── secrets.sops.yaml         # Encrypted secrets (optional)
│   ├── configmap.yaml            # ConfigMaps (optional)
│   └── <custom-resources>.yaml   # Additional K8s resources
├── gateway/                      # Gateway resources (if app exposes services)
│   ├── kustomization.yaml        # Lists gateway resources
│   ├── certificate.yaml          # TLS certificates
│   ├── external.yaml             # External gateway
│   └── internal.yaml             # Internal gateway
└── <component>/                  # Additional components (optional)
    ├── kustomization.yaml
    └── <resources>.yaml
```

### File Naming Standards

#### Core Infrastructure Files
- **`ks.yaml`**: Flux Kustomization (always at app root level)
- **`kustomization.yaml`**: Kustomize resource lists (in each directory)
- **`helmrelease.yaml`**: Combined HelmRepository + HelmRelease definitions
- **`values.yaml`**: Helm chart values (in `helm/` subdirectory)
- **`kustomizeconfig.yaml`**: Kustomize configuration (in `helm/` subdirectory)

#### Security and Configuration
- **`secret.sops.yaml`**: SOPS-encrypted secrets (single resource)
- **`secrets.sops.yaml`**: SOPS-encrypted secrets (multiple resources)
- **`configmap.yaml`**: Application configuration
- **`namespace.yaml`**: Namespace definitions (when not using common components)

#### Network and Gateway Resources
- **`certificate.yaml`**: TLS certificate definitions
- **`external.yaml`**: External-facing Gateway resources
- **`internal.yaml`**: Internal Gateway resources
- **`networks.yaml`**: Network policy and load balancer configurations
- **`httproute.yaml`**: HTTP routing definitions
- **`dnsendpoint.yaml`**: External DNS endpoint configurations
- **`gatewayclass.yaml`**: Gateway class definitions
- **`envoyproxy.yaml`**: Envoy proxy configurations
- **`security-policy.yaml`**: Security policies (OIDC, CORS, rate limiting)

#### Storage and Backup
- **`pvc.yaml`**: PersistentVolumeClaim definitions
- **`storageclass.yaml`**: StorageClass definitions
- **`schedule.yaml`**: K8up backup schedules
- **`check.yaml`**: Backup integrity checks
- **`prune.yaml`**: Backup pruning configurations

#### Cluster Management
- **`clusterissuer.yaml`**: cert-manager ClusterIssuer definitions
- **`receiver.yaml`**: Flux webhook receivers
- **`crds.yaml`**: Custom Resource Definitions (often just comments referencing Helm)

### Resource Type Placement

#### By Directory Structure
- **Flux Resources**: `ks.yaml` files at app/component root
- **Helm Charts**: `helmrelease.yaml` in `app/` directory
- **Helm Values**: `helm/values.yaml` with `helm/kustomizeconfig.yaml`
- **Secrets**: `secret.sops.yaml` or `secrets.sops.yaml` (always encrypted with SOPS)
- **Gateway/Ingress**: Separate `gateway/` subdirectory for apps with external access
- **Network Policies**: `networks.yaml` for CNI-specific configurations
- **Custom Resources**: Named by resource type (e.g., `serviceaccount.yaml`, `rbac.yaml`)

#### By Resource Category
- **Storage Resources**: `pvc.yaml`, `storageclass.yaml` in storage applications
- **Security Policies**: `security-policy.yaml` for authentication, authorization, CORS
- **DNS/Networking**: `dnsendpoint.yaml`, `httproute.yaml` for external connectivity
- **Backup Resources**: `schedule.yaml`, `check.yaml`, `prune.yaml` for K8up operations
- **Certificate Management**: `clusterissuer.yaml`, `certificate.yaml` for TLS
- **Monitoring/Observability**: Resources often embedded in `envoyproxy.yaml` or separate files


### Multi-Component Applications

For complex applications with multiple components (like Cilium with app + gateway):

```
<app-name>/
├── ks.yaml                    # Primary component Kustomization
├── app/                       # Main application
│   └── ...
├── <component>/               # Additional component (e.g., gateway)
│   ├── kustomization.yaml
│   └── ...
└── <component>/               # Another component
    ├── kustomization.yaml
    └── ...
```

### Bootstrap & Configuration (`kubernetes/bootstrap/`)
- **`talos/`** - Talos Linux cluster configuration
  - `clusterconfig/` - Node-specific configurations
  - `patches/` - Cluster patches and customizations
  - `talconfig.yaml` - Main Talos configuration
- **`apps/`** - Helmfile for initial application deployment

### Flux Configuration (`kubernetes/flux/`)
- **`cluster/`** - Cluster-wide Flux resources
- **`components/`** - Reusable components and templates
- **`meta/`** - Helm repositories and metadata

## Key Technologies
- **OS**: Talos Linux (immutable Kubernetes-focused OS)
- **GitOps**: Flux CD v2
- **Networking**: Cilium CNI with L2 announcements
- **Storage**: OpenEBS for local storage, CSI NFS driver for NAS
- **Monitoring**: Prometheus, Grafana, Loki, Promtail
- **Security**: Authentik (SSO), Vaultwarden, cert-manager
- **Secrets**: External Secrets Operator with SOPS/age encryption
- **Automation**: Renovate for dependency updates

## Common Tasks

### Cluster Operations
```bash
# Check cluster status
task kubernetes:check

# Apply Kubernetes resources
task kubernetes:apply

# View cluster resources
task resources:summary
```

### Talos Operations
```bash
# Generate Talos configuration
task talos:genconfig

# Apply Talos configuration
task talos:apply

# Bootstrap cluster
task talos:bootstrap
```

### Volume Management
```bash
# Unlock VolSync volumes
task volsync:unlock

# List VolSync jobs
task volsync:list
```

## Application Categories

### Media Stack
Complete media automation with Plex, Sonarr, Radarr, Prowlarr, Overseerr, and related tools for both standard and UHD content.

### Home Automation
Comprehensive home automation using Home Assistant, ESPHome, Node-RED, and Zigbee2MQTT for device management.

### AI/ML Services
Local AI inference with Ollama, LiteLLM proxy, Open WebUI, and automation workflows via n8n.

### Observability
Full-stack monitoring with Prometheus metrics, Grafana dashboards, Loki logging, and Gatus uptime monitoring.

### Self-hosted Applications
Various productivity and utility applications including Paperless-NGX, Actual budget, Atuin shell history, and more.

## External Integrations
- **DNS**: External DNS with Cloudflare
- **Ingress**: NGINX ingress controllers (internal/external)
- **Certificates**: Let's Encrypt via cert-manager
- **Monitoring**: Kromgo for external status reporting
- **Secrets**: Infisical for secret management

## Security Features
- Age-encrypted secrets with SOPS
- Authentik SSO for application access
- Network policies via Cilium
- Pod security standards enforcement
- Regular automated security updates

## Backup Strategy
- VolSync for application data replication
- PostgreSQL automated backups via CloudNative-PG
- Configuration stored in Git for disaster recovery

This cluster represents a production-ready home lab environment with enterprise-grade tooling and practices scaled for personal use.

## Important Notes


- Never commit unencrypted secrets
- Always test Talos config changes on a single node first
- Use `task reconcile` to force immediate Git sync
- Check `flux get all -A` before assuming changes aren't applied
- The cluster uses GitHub webhook for instant updates (configured separately)
- **API Gateway**: Envoy Gateway is configured for microservices with OIDC authentication
- **Gateway Routes**: Use HTTPRoute resources to expose services through the API gateway
