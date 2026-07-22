---
name: find-app
description: Search for Kubernetes application configurations and scaffold them to match the dapper-cluster template structure
allowed-tools: Read, Edit, Write, Bash, Grep, Glob, WebFetch, WebSearch
---

# Find & Scaffold App

Search for Kubernetes application configurations (kubesearch.dev, ArtifactHub, GitHub) and scaffold them into the dapper-cluster's canonical structure.

Takes an app name as argument, e.g. `/find-app jellyfin`.

## Instructions

### 1. Search for Configurations

Search kubesearch.dev and other sources for the requested app:

```
https://kubesearch.dev/search/?q=<app-name>
```

Also check ArtifactHub for official Helm charts. Prioritize:

- Configurations using bjw-s app-template (easiest to integrate)
- Well-maintained repos with recent updates
- Configurations already using Flux CD

### 2. Determine Namespace

Check existing namespaces in `kubernetes/apps/` and pick the most appropriate one:

- `media/` - media server stack (\*arr, plex, etc.)
- `selfhosted/` - productivity/utility apps
- `ai/` - AI/ML workloads
- `home-automation/` - home assistant, esphome, etc.
- `observability/` - monitoring/logging
- `database/` - database services
- `network/` - networking components
- `security/` - auth/security apps

### 3. Scaffold Using Canonical Structure

Create the app following the exact structure:

```
kubernetes/apps/<namespace>/<app-name>/
├── ks.yaml
└── app/
    ├── kustomization.yaml
    ├── helmrelease.yaml
    └── externalsecret.yaml    (if app needs secrets)
```

The full canonical YAML for every scaffolded file lives in
[`references/templates.md`](references/templates.md): `ks.yaml` (stateless and
VolSync+Gatus), `helmrelease.yaml` (app-template and traditional chart),
`app/kustomization.yaml`, and `externalsecret.yaml` (plain + postgres). Copy the
block matching the app's needs and substitute `<app-name>` / `<namespace>` / image.

### 4. Register in Namespace Kustomization

Add the app's `ks.yaml` to the namespace's `kustomization.yaml`:

```yaml
resources:
  - ./<app-name>/ks.yaml
```

### 5. Critical Rules

This list is the **canonical copy** — other skills (validate-helm) point here; edit it in one place.

- YAML anchor: always use `&app` (not `&appname`)
- **NEVER rename `controllers.main`** on existing apps - controller name is immutable in Deployment selectors
- For NEW apps, name the controller after the app (e.g., `controllers.sonarr`) with `service.app.controller: sonarr`
- HelmRelease spec order: `interval -> chartRef -> install -> upgrade -> dependsOn -> values`
- Values order: `controllers -> defaultPodOptions -> service -> route -> persistence`
- Expose HTTP via a `route:` block on the Envoy Gateways (`parentRefs: internal | external`, namespace `network`) — **never an `ingress:` block; nginx is gone.** Details/edge cases: `gateway-route` skill
- Uptime monitoring is automatic once the app has a route (gatus-sidecar auto-discovery) — no Gatus components or `GATUS_*` substitutions; see the `gatus-monitoring` skill for probe overrides
- VolSync apps: set `wait: true` and `timeout: 10m` in ks.yaml
- Stateless apps: set `wait: false` and `timeout: 5m` in ks.yaml
- VolSync ks.yaml needs `postBuild.substitute.APP` and `VOLSYNC_CAPACITY`
- sourceRef is always `name: flux-system, namespace: flux-system`
- app-template chartRef omits namespace (resolved from common component)
- Cluster substitution variables available: `${TIME_ZONE}`, `${SECRET_DOMAIN}`, `${SECRET_DOMAIN_MEDIA}`, `${SECRET_DOMAIN_PERSONAL}`
- Default security context: `runAsUser: 1000, runAsGroup: 150, fsGroup: 150`
- Secrets come from Infisical via ExternalSecret, not SOPS (SOPS is only for cluster-level secrets)

## Report

Provide:

- **App**: What it does, what chart/image is used
- **Files Created**: List of scaffolded files
- **Dependencies**: Any prerequisites (secrets in Infisical, databases, PVCs)
- **Next Steps**: What the user needs to configure (add secrets to Infisical, etc.)
