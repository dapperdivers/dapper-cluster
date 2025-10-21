# Postgres Init Policy

Automatic PostgreSQL database and user initialization for HelmReleases using Kyverno policies.

## Overview

This policy set provides a **3-annotation solution** to add postgres-init functionality to any HelmRelease. It automatically:

1. ✅ Injects a postgres-init container
2. ✅ Generates an ExternalSecret with credentials
3. ✅ Manages image versions centrally (Renovate-friendly)

**Boilerplate reduction: 50+ lines → 3 annotations per app**

## Files

- **`configmap.yaml`** - Stores the postgres-init image reference (Renovate updates this automatically)
- **`clusterpolicy-container.yaml`** - Injects init container into HelmRelease
- **`clusterpolicy-externalsecret.yaml`** - Generates ExternalSecret for postgres credentials
- **`kustomization.yaml`** - Kustomize resources for this policy set

## Usage

Add these 3 annotations to any HelmRelease:

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: myapp
  annotations:
    postgres-init.home.arpa/enabled: "true"
    postgres-init.home.arpa/user-key: "MYAPP_POSTGRES_USER"      # Infisical key
    postgres-init.home.arpa/pass-key: "MYAPP_POSTGRES_PASSWORD"  # Infisical key
spec:
  values:
    controllers:
      myapp:
        # No initContainers section needed - automatically injected!
        containers:
          app:
            # Your app configuration
```

### Optional Annotations

```yaml
postgres-init.home.arpa/dbname: "custom-db-name"        # Default: release name
postgres-init.home.arpa/controller: "custom-controller" # Default: release name
```

## What Happens Automatically

### 1. Init Container Injection

The `clusterpolicy-container.yaml` policy injects this into your HelmRelease:

```yaml
spec:
  values:
    controllers:
      myapp:
        initContainers:
          init-db:
            image:
              repository: ghcr.io/home-operations/postgres-init  # From ConfigMap
              tag: 17.6@sha256:...                               # From ConfigMap
            envFrom:
              - secretRef:
                  name: myapp-postgres-init  # Auto-generated secret
```

### 2. ExternalSecret Generation

The `clusterpolicy-externalsecret.yaml` policy creates:

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: myapp-postgres-init
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: infisical
  target:
    name: myapp-postgres-init
    template:
      data:
        INIT_POSTGRES_HOST: postgres-rw.database.svc.cluster.local
        INIT_POSTGRES_SUPER_USER: "{{ .POSTGRES_SUPER_USER }}"
        INIT_POSTGRES_SUPER_PASS: "{{ .POSTGRES_SUPER_PASS }}"
        INIT_POSTGRES_PORT: "5432"
        INIT_POSTGRES_DBNAME: "myapp"  # From annotation or release name
        INIT_POSTGRES_USER: "{{ .MYAPP_POSTGRES_USER }}"
        INIT_POSTGRES_PASS: "{{ .MYAPP_POSTGRES_PASSWORD }}"
  dataFrom:
    - find:
        path: POSTGRES_SUPER_USER
    # ... etc
```

## Required Infisical Secrets

For each app, create these secrets in Infisical:

1. **Cluster-wide** (one-time setup):
   - `POSTGRES_SUPER_USER` - PostgreSQL superuser name
   - `POSTGRES_SUPER_PASS` - PostgreSQL superuser password

2. **Per-app**:
   - `{MYAPP}_POSTGRES_USER` - App-specific database user
   - `{MYAPP}_POSTGRES_PASSWORD` - App-specific database password

## Example: Miniflux RSS Reader

See `kubernetes/apps/selfhosted/miniflux/app/helmrelease.yaml` for a complete example.

**Before (manual pattern):**
- 100+ lines in helmrelease.yaml (with init container)
- 40+ lines for postgres-init externalsecret.yaml

**After (Kyverno automation):**
- 3 annotations in helmrelease.yaml
- No separate postgres-init externalsecret needed

## Image Version Management

The postgres-init image is stored in `configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: postgres-init-config
  namespace: kyverno
data:
  image-repository: ghcr.io/home-operations/postgres-init
  image-tag: 17.6@sha256:86a1992d46273c58fd4ad95b626081dfaabfe16bd56944675169e406d1a660dd
```

**Renovate automatically:**
- ✅ Detects the image in the ConfigMap
- ✅ Creates PRs when new versions are available
- ✅ Updates all apps cluster-wide via single ConfigMap change

**Manual update:**
1. Edit `configmap.yaml` with new image tag
2. Run: `flux reconcile kustomization kyverno-policies -n kyverno`
3. All apps use new version on next pod restart

## Verification

After adding annotations to a HelmRelease:

```bash
# Check that ClusterPolicies are ready
kubectl get clusterpolicy | grep postgres-init

# Verify ExternalSecret was generated
kubectl get externalsecret {app}-postgres-init -n {namespace}

# Check that HelmRelease was mutated with init container
kubectl get helmrelease {app} -n {namespace} -o yaml | grep -A 10 init-db

# Watch pod start with init container
kubectl get pods -n {namespace} -w

# View init container logs
kubectl logs -n {namespace} {pod} -c init-db
```

## Troubleshooting

### ExternalSecret not generated

**Check:**
1. Required annotations present: `enabled`, `user-key`, `pass-key`
2. Policy is applied: `kubectl get clusterpolicy postgres-init-externalsecret`
3. Kyverno logs: `kubectl logs -n kyverno -l app.kubernetes.io/component=admission-controller`

### Init container not injected

**Check:**
1. Annotation is string value: `postgres-init.home.arpa/enabled: "true"` (not boolean)
2. Policy is applied: `kubectl get clusterpolicy postgres-init-container`
3. ConfigMap exists: `kubectl get configmap postgres-init-config -n kyverno`

### Database initialization fails

**Check init logs:**
```bash
kubectl logs -n {namespace} {pod} -c init-db
```

**Common issues:**
- Infisical secrets not found (verify ExternalSecret status)
- PostgreSQL cluster not ready (check cloudnative-pg)
- Incorrect credentials in Infisical
- Superuser credentials incorrect

## Migration from Manual Pattern

To migrate an existing app using manual postgres-init:

1. **Add annotations to HelmRelease**
2. **Remove manual init container definition**
3. **Delete the postgres-init ExternalSecret file**
4. **Commit and apply**

Example:

```bash
# Edit HelmRelease - add 3 annotations, remove initContainers.init-db section
# Delete old ExternalSecret file
rm kubernetes/apps/{namespace}/{app}/app/postgres-init-externalsecret.yaml

# Commit
git add .
git commit -m "feat({app}): migrate to Kyverno postgres-init automation"

# Apply
flux reconcile kustomization {app} -n {namespace}

# Verify
kubectl get externalsecret {app}-postgres-init -n {namespace}
kubectl get pods -n {namespace}
```

## Related Documentation

- [Kyverno Documentation](https://kyverno.io/docs/)
- [postgres-init Container Source](https://github.com/home-operations/containers/tree/main/apps/postgres-init)
- [CloudNativePG](https://cloudnative-pg.io/)
- [External Secrets Operator](https://external-secrets.io/)
