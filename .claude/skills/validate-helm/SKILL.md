---
name: validate-helm
description: Validate HelmRelease configurations against chart schemas, diagnose helm validation errors, and fix app-template compatibility issues
tools: Read, Edit, MultiEdit, Bash, Grep, Glob
---

# Helm Validation

Validate and fix HelmRelease configurations in the dapper-cluster, with focus on bjw-s app-template compatibility.

## Instructions

### 1. Identify Target

If the user specifies a HelmRelease, read it directly. Otherwise check for failures:

```bash
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl get hr -A | grep -v "True"
```

### 2. Analyze the HelmRelease

Read the helmrelease.yaml and determine:
- **app-template**: uses `chartRef: { kind: OCIRepository, name: app-template }` — provided by the common component's repos
- **Traditional chart**: uses `chart.spec` with a `HelmRepository` sourceRef
- Current error messages from the cluster

### 3. Validate Against Schema

**Schema URLs (must match the yaml-language-server comment at top of file):**
- app-template: `https://raw.githubusercontent.com/bjw-s/helm-charts/main/charts/other/app-template/schemas/helmrelease-helm-v2.schema.json`
- Generic Flux HR: `https://kubernetes-schemas.pages.dev/helm.toolkit.fluxcd.io/helmrelease_v2.json`

Common validation errors:
- "Additional property X is not allowed"
- "Must validate all the schemas (allOf)"
- "Invalid type" errors
- Missing required properties

### 4. Check Canonical Structure

**HelmRelease spec order:** `interval -> chartRef -> install -> upgrade -> dependsOn -> values`

**app-template values order:** `controllers -> defaultPodOptions -> service -> ingress -> persistence`

**app-template patterns:**
- Controller named after the app: `controllers.<app-name>.containers.app`
- Service references controller: `service.app.controller: <app-name>`
- Ingress uses service identifier: `service.identifier: app, port: http`
- Reloader annotation: `reloader.stakater.com/auto: "true"`
- Security context: `runAsUser: 1000, runAsGroup: 150, fsGroup: 150, fsGroupChangePolicy: OnRootMismatch`
- Secrets via envFrom: `secretRef.name: <app-name>-secret` (from ExternalSecret)
- Cluster vars available: `${TIME_ZONE}`, `${SECRET_DOMAIN}`, `${SECRET_DOMAIN_MEDIA}`
- TLS secret: `${SECRET_DOMAIN/./-}-tls`

### 5. Apply Fixes

- Make minimal changes to achieve compatibility
- **NEVER rename `controllers.main`** on existing apps - controller name is immutable in Deployment selectors
- Use YAML anchor `&app` (not `&appname`)
- app-template chartRef omits namespace (resolved from common component)

### 6. Verify

```bash
KUBECONFIG=~/projects/dapper-cluster/kubeconfig flux reconcile hr <name> -n <namespace> --with-source
```

## Report

Provide:
- **Chart**: What chart/version is in use
- **Errors Found**: Specific validation problems
- **Fixes Applied**: What was changed and why
- **Verification**: Post-fix status
