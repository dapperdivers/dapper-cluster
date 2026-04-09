---
name: find-app
description: Search for Kubernetes application configurations and scaffold them to match the dapper-cluster template structure
tools: Read, Edit, Write, Bash, Grep, Glob, WebFetch, WebSearch
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
- `media/` - media server stack (*arr, plex, etc.)
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

#### ks.yaml - Stateless (no persistent data)

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/kustomize.toolkit.fluxcd.io/kustomization_v1.json
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: &app <app-name>
  namespace: flux-system
spec:
  targetNamespace: <namespace>
  commonMetadata:
    labels:
      app.kubernetes.io/name: *app
  path: ./kubernetes/apps/<namespace>/<app-name>/app
  prune: true
  sourceRef:
    kind: GitRepository
    name: flux-system
    namespace: flux-system
  wait: false
  interval: 30m
  retryInterval: 1m
  timeout: 5m
```

#### ks.yaml - With VolSync + Gatus (most common for stateful apps)

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/kustomize.toolkit.fluxcd.io/kustomization_v1.json
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: &app <app-name>
  namespace: &namespace <namespace>
spec:
  targetNamespace: *namespace
  components:
    - ../../../../flux/components/gatus/guarded
    - ../../../../flux/components/volsync/repository
    - ../../../../flux/components/volsync/operations
  commonMetadata:
    labels:
      app.kubernetes.io/name: *app
  dependsOn:
    - name: volsync
      namespace: storage
    - name: external-secrets-stores
      namespace: external-secrets
  path: ./kubernetes/apps/<namespace>/<app-name>/app
  prune: true
  sourceRef:
    kind: GitRepository
    name: flux-system
    namespace: flux-system
  wait: true
  interval: 30m
  retryInterval: 1m
  timeout: 10m
  postBuild:
    substitute:
      APP: *app
      GATUS_SUBDOMAIN: <app-name>
      GATUS_DOMAIN: ${SECRET_DOMAIN}
      VOLSYNC_CAPACITY: 5Gi
```

#### helmrelease.yaml (app-template via OCIRepository)

```yaml
---
# yaml-language-server: $schema=https://raw.githubusercontent.com/bjw-s/helm-charts/main/charts/other/app-template/schemas/helmrelease-helm-v2.schema.json
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: <app-name>
spec:
  interval: 30m
  chartRef:
    kind: OCIRepository
    name: app-template
  install:
    remediation:
      retries: 3
  upgrade:
    cleanupOnFail: true
    remediation:
      strategy: rollback
      retries: 3
  values:
    controllers:
      <app-name>:
        annotations:
          reloader.stakater.com/auto: "true"
        containers:
          app:
            image:
              repository: <image>
              tag: <tag>
            env:
              TZ: "${TIME_ZONE}"
            envFrom:
              - secretRef:
                  name: <app-name>-secret
            securityContext:
              allowPrivilegeEscalation: false
              readOnlyRootFilesystem: true
              capabilities: { drop: ["ALL"] }
            resources:
              requests:
                cpu: 10m
                memory: 128Mi
              limits:
                memory: 512Mi
    defaultPodOptions:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 150
        fsGroup: 150
        fsGroupChangePolicy: OnRootMismatch
        seccompProfile: { type: RuntimeDefault }
    service:
      app:
        controller: <app-name>
        ports:
          http:
            port: &port <port>
    ingress:
      app:
        annotations:
          external-dns.alpha.kubernetes.io/target: "internal.${SECRET_DOMAIN}"
        className: internal
        hosts:
          - host: &host "<app-name>.${SECRET_DOMAIN}"
            paths:
              - path: /
                service:
                  identifier: app
                  port: http
        tls:
          - hosts:
              - *host
            secretName: "${SECRET_DOMAIN/./-}-tls"
    persistence:
      config:
        existingClaim: <app-name>
      tmp:
        type: emptyDir
```

#### helmrelease.yaml (traditional HelmRepository chart)

For apps that use their own Helm chart (not app-template):

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/helm.toolkit.fluxcd.io/helmrelease_v2.json
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: <app-name>
spec:
  interval: 30m
  chart:
    spec:
      chart: <chart-name>
      version: <version>
      sourceRef:
        kind: HelmRepository
        name: <repo-name>
        namespace: flux-system
  install:
    remediation:
      retries: 3
  upgrade:
    cleanupOnFail: true
    remediation:
      strategy: rollback
      retries: 3
  values:
    # Chart-specific values here
```

Note: Non-app-template charts need a HelmRepository defined. Check if one exists in `kubernetes/flux/meta/` or create one.

#### app/kustomization.yaml

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./helmrelease.yaml
```

If the app has an ExternalSecret:

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./externalsecret.yaml
  - ./helmrelease.yaml
```

#### externalsecret.yaml (if app needs secrets)

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/external-secrets.io/externalsecret_v1beta1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: <app-name>
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: infisical
  target:
    name: <app-name>-secret
    template:
      engineVersion: v2
      data:
        # Map Infisical secrets to env vars the app expects
        SOME_SECRET: "{{ .APP_SOME_SECRET }}"
  dataFrom:
    - find:
        name:
          regexp: ^APP_.*
```

For apps with postgres, add a second ExternalSecret:

```yaml
---
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: <app-name>-postgres
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: infisical-postgres
  target:
    name: <app-name>-postgres-secret
    template:
      engineVersion: v2
      data:
        INIT_POSTGRES_DBNAME: <app-name>
        INIT_POSTGRES_HOST: "{{ .POSTGRES_SUPER_HOST_RW }}.database.svc.cluster.local"
        INIT_POSTGRES_USER: "{{ .APP_POSTGRES_USER }}"
        INIT_POSTGRES_PASS: "{{ .APP_POSTGRES_PASSWORD }}"
        INIT_POSTGRES_SUPER_PASS: "{{ .POSTGRES_SUPER_PASS }}"
        INIT_POSTGRES_SUPER_USER: "{{ .POSTGRES_SUPER_USER }}"
  dataFrom:
    - find:
        name:
          regexp: ^APP_.*
    - find:
        path: POSTGRES_SUPER_USER
    - find:
        path: POSTGRES_SUPER_PASS
    - find:
        path: POSTGRES_SUPER_HOST_RW
```

### 4. Register in Namespace Kustomization

Add the app's `ks.yaml` to the namespace's `kustomization.yaml`:

```yaml
resources:
  - ./<app-name>/ks.yaml
```

### 5. Critical Rules

- YAML anchor: always use `&app` (not `&appname`)
- **NEVER rename `controllers.main`** on existing apps - controller name is immutable in Deployment selectors
- For NEW apps, name the controller after the app (e.g., `controllers.sonarr`) with `service.app.controller: sonarr`
- HelmRelease spec order: `interval -> chartRef -> install -> upgrade -> dependsOn -> values`
- Values order: `controllers -> defaultPodOptions -> service -> ingress -> persistence`
- VolSync apps: set `wait: true` and `timeout: 10m` in ks.yaml
- Stateless apps: set `wait: false` and `timeout: 5m` in ks.yaml
- VolSync ks.yaml needs `postBuild.substitute.APP` and `VOLSYNC_CAPACITY`
- Gatus ks.yaml needs `postBuild.substitute.GATUS_SUBDOMAIN` and `GATUS_DOMAIN`
- sourceRef is always `name: flux-system, namespace: flux-system`
- app-template chartRef omits namespace (resolved from common component)
- Cluster substitution variables available: `${TIME_ZONE}`, `${SECRET_DOMAIN}`, `${SECRET_DOMAIN_MEDIA}`, `${SECRET_DOMAIN_PERSONAL}`
- Internal ingress: `className: internal` with `external-dns.alpha.kubernetes.io/target: "internal.${SECRET_DOMAIN}"`
- TLS secret naming: `${SECRET_DOMAIN/./-}-tls` (dots replaced with dashes)
- Default security context: `runAsUser: 1000, runAsGroup: 150, fsGroup: 150`
- Secrets come from Infisical via ExternalSecret, not SOPS (SOPS is only for cluster-level secrets)

## Report

Provide:
- **App**: What it does, what chart/image is used
- **Files Created**: List of scaffolded files
- **Dependencies**: Any prerequisites (secrets in Infisical, databases, PVCs)
- **Next Steps**: What the user needs to configure (add secrets to Infisical, etc.)
