# find-app scaffolding templates

Canonical YAML for scaffolding a new dapper-cluster app — reference for the
`find-app` skill, step 3 ("Scaffold Using Canonical Structure"). Copy the block
that matches the app and substitute `<app-name>`, `<namespace>`, image/chart, ports.

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
        name:
          regexp: ^POSTGRES_SUPER_(USER|PASS|HOST_RW)$
```

> **Use `find: name: { regexp }`, never `find: path:`.** Infisical keys live in nested
> folders (`/Infrastructure/Postgres`), and `find: path:` does a folder match that resolves
> to nothing — this once broke ExternalSecrets cluster-wide. See the `externalsecrets` skill.
