# Envoy Gateway Deployment for dapper-cluster

Comprehensive Envoy Gateway deployment using Gateway API for modern, declarative ingress management.

## Overview

This deployment provides:
- **Two GatewayClasses**: `external-envoy` (public) and `internal-envoy` (cluster-internal)
- **Automatic TLS**: cert-manager integration with Let's Encrypt
- **Automatic DNS**: external-dns creates DNS records from HTTPRoute annotations
- **Resource-efficient**: ~400m-2000m CPU, 512Mi-2Gi RAM total
- **Cilium LoadBalancer**: L2 IPAM for external IPs

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  External Traffic (derekmackley.com)                         │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Cilium LoadBalancer  │
            │   IP: 192.168.1.240   │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  external-gateway     │
            │  (GatewayClass:       │
            │   external-envoy)     │
            │  - HTTPS:443 (TLS)    │
            │  - HTTP:80 (redirect) │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  HTTPRoute            │
            │  - resume-site        │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Backend Service      │
            │  resume:8080          │
            │  (selfhosted ns)      │
            └───────────────────────┘
```

## Files

1. **helmrelease.yaml** - Flux HelmRelease for Envoy Gateway
   - Installs Envoy Gateway controller
   - Creates external and internal GatewayClasses
   - Defines EnvoyProxy configurations for each class

2. **gateway-external.yaml** - External Gateway for public traffic
   - Gateway with HTTPS (443) and HTTP (80) listeners
   - cert-manager Certificate for wildcard TLS
   - HTTP→HTTPS redirect

3. **gateway-internal.yaml** - Internal Gateway for cluster traffic
   - Separate Gateway for internal services
   - Uses internal subdomain (internal.derekmackley.com)
   - Lower resource footprint (1 replica)

4. **httproute-resume.yaml** - HTTPRoute for resume site
   - Replaces existing nginx Ingress
   - Routes derekmackley.com, www, and resume subdomain
   - Backend: resume service (port 8080) in selfhosted namespace
   - Includes security headers

5. **kustomization.yaml** - Kustomize overlay
   - Lists all resources
   - Applies common labels

## Prerequisites

1. **Gateway API CRDs** must be installed:
   ```bash
   kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.0.0/standard-install.yaml
   ```

2. **cert-manager** must be installed and configured:
   - ClusterIssuer named `letsencrypt-production` must exist
   - Supports HTTP-01 or DNS-01 challenges

3. **external-dns** should be configured to watch Gateway API resources:
   - Watches `gateway-httproute` source
   - Creates DNS records from annotations

4. **Cilium LoadBalancer** with L2 IPAM:
   - IP pool includes 192.168.1.240-241
   - Annotation: `io.cilium/lb-ipam-ips`

5. **Flux variable substitution**:
   - `${SECRET_DOMAIN_PERSONAL}` = derekmackley.com
   - Configured in cluster ConfigMap or Secret

## Deployment Steps

### 1. Install Gateway API CRDs (if not already installed)
```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.0.0/standard-install.yaml
```

### 2. Apply Envoy Gateway manifests via Flux
```bash
# Add to your flux repository structure:
# cluster/apps/envoy-gateway/
#   ├── namespace.yaml
#   └── kustomization.yaml (referencing this directory)

# Or apply directly:
kubectl apply -k /shared/envoy-gateway/
```

### 3. Verify Installation
```bash
# Check Envoy Gateway controller
kubectl get pods -n envoy-gateway-system

# Check GatewayClasses
kubectl get gatewayclass
# Should show: external-envoy, internal-envoy

# Check Gateways
kubectl get gateway -n gateway-system
# Should show: external-gateway, internal-gateway

# Check HTTPRoutes
kubectl get httproute -n selfhosted
# Should show: resume-site

# Check LoadBalancer IPs
kubectl get svc -n envoy-gateway-system
# Should show LoadBalancer services with IPs assigned
```

### 4. Verify DNS and TLS
```bash
# Check Certificate status
kubectl get certificate -n gateway-system
kubectl describe certificate wildcard-personal-domain -n gateway-system

# Check DNS records (if external-dns is configured)
# Should see A records for derekmackley.com, www, resume pointing to LoadBalancer IP

# Test HTTPS
curl -v https://derekmackley.com
curl -v https://resume.derekmackley.com
```

## Migration from Nginx Ingress

To migrate from your existing nginx Ingress to Envoy Gateway:

1. **Keep both running initially** (different LoadBalancer IPs)
2. **Update DNS** to point to new Envoy Gateway LoadBalancer IP
3. **Test thoroughly** with the new Gateway
4. **Delete old Ingress** once confident:
   ```bash
   kubectl delete ingress <old-ingress-name> -n selfhosted
   ```

## Resource Allocation

| Component | Replicas | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-----------|----------|-------------|-----------|----------------|--------------|
| Gateway Controller | 1 | 100m | 500m | 128Mi | 512Mi |
| External Proxy | 2 | 200m | 1000m | 256Mi | 1Gi |
| Internal Proxy | 1 | 100m | 500m | 128Mi | 512Mi |
| **Total** | **4** | **400m** | **2000m** | **512Mi** | **2Gi** |

## Advanced Features

### Authentik SSO Integration (Future)

To add forward authentication with Authentik, create a SecurityPolicy:

```yaml
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: SecurityPolicy
metadata:
  name: authentik-sso
  namespace: gateway-system
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: external-gateway
  
  extAuth:
    http:
      backendRef:
        name: authentik-outpost
        namespace: authentik
        port: 9000
      path: /outpost.goauthentik.io/auth/envoy
      headersToBackend:
        - header: {name: X-Forwarded-Proto}
          mode: Append
        - header: {name: X-Forwarded-Host}
          mode: Append
      headersToDownstream:
        - header: {name: X-Auth-User}
          mode: Override
```

See `/shared/envoy-gw-research.md` section 6 for complete SecurityPolicy examples.

### Traffic Splitting (Canary Deployments)

HTTPRoute supports native traffic splitting:

```yaml
backendRefs:
  - name: app-stable
    port: 8080
    weight: 90
  - name: app-canary
    port: 8080
    weight: 10
```

### Custom Headers

Add headers to requests or responses:

```yaml
filters:
  - type: RequestHeaderModifier
    requestHeaderModifier:
      add:
        - name: X-Custom-Header
          value: "custom-value"
```

## Troubleshooting

### Gateway not ready
```bash
kubectl describe gateway external-gateway -n gateway-system
# Check status.conditions for errors
```

### HTTPRoute not attached
```bash
kubectl describe httproute resume-site -n selfhosted
# Check parentRefs and conditions
```

### TLS certificate issues
```bash
kubectl get certificate -n gateway-system
kubectl describe certificate wildcard-personal-domain -n gateway-system
kubectl logs -n cert-manager deploy/cert-manager
```

### Envoy proxy logs
```bash
# Find Envoy proxy pods
kubectl get pods -n envoy-gateway-system -l gateway.envoyproxy.io/owning-gateway-namespace=gateway-system

# View logs
kubectl logs -n envoy-gateway-system <envoy-pod-name> -f
```

### Envoy admin interface
```bash
kubectl port-forward -n envoy-gateway-system <envoy-pod-name> 19000:19000
# Visit http://localhost:19000
# Useful endpoints: /stats, /config_dump, /clusters
```

## Open Questions / Next Steps

1. **IP Addresses**: Confirm 192.168.1.240-241 are available in your Cilium IPAM pool
2. **ClusterIssuer**: Verify `letsencrypt-production` exists or adjust name
3. **DNS Provider**: Confirm external-dns DNS provider (Cloudflare, Route53, etc.)
4. **Resume Service**: Verify service name and port (assumed `resume:8080` in `selfhosted` namespace)
5. **Authentik Integration**: If you want SSO, we can add SecurityPolicy CRD
6. **Monitoring**: Consider adding ServiceMonitor for Prometheus scraping

## References

- Research document: `/shared/envoy-gw-research.md`
- Envoy Gateway docs: https://gateway.envoyproxy.io
- Gateway API docs: https://gateway-api.sigs.k8s.io
- Flux docs: https://fluxcd.io

## Author

Generated for dapper-cluster homelab deployment  
Date: March 13, 2026
