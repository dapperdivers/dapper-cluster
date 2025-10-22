# Kyverno Cluster Policies

This directory contains Kyverno ClusterPolicies that automate common patterns across the cluster.

## Available Policies

### 1. Authentik Ingress Annotation (`ingress-authentik-annotation.yaml`)

Automatically configures nginx authentication annotations for Ingresses when using Authentik.

**Usage:**
```yaml
metadata:
  annotations:
    authentik.home.arpa/internal: "true"  # or "external"
```

See: [ingress-authentik-annotation.yaml](./ingress-authentik-annotation.yaml)

---

### 2. NFS Health Checks (`nfs-health-checks.yaml`)

Adds liveness probes to containers in the `media` namespace that mount NFS PVCs, providing automatic pod restart when NFS mounts become stale.

**Scope:** Automatically applied to pods in `media` namespace with NFS PVCs

See: [nfs-health-checks.yaml](./nfs-health-checks.yaml)

---

### 3. Postgres Init Config (`postgres-init-config.yaml`)

ConfigMap containing the postgres-init container image reference. This serves as the single source of truth for the image version and is automatically updated by Renovate.

**Contents:**
```yaml
data:
  image-repository: ghcr.io/home-operations/postgres-init
  image-tag: 17.6@sha256:...
```

See: [postgres-init-config.yaml](./postgres-init-config.yaml)

---

### 4. Postgres Init Container (`postgres-init-container.yaml`)

Automatically injects a postgres-init container into HelmReleases to initialize PostgreSQL databases and users. The container image is dynamically loaded from the `postgres-init-config` ConfigMap.

**Usage:**
```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: myapp
  annotations:
    postgres-init.home.arpa/enabled: "true"
    postgres-init.home.arpa/user-key: "MYAPP_POSTGRES_USER"      # Infisical key
    postgres-init.home.arpa/pass-key: "MYAPP_POSTGRES_PASSWORD"  # Infisical key
```

**Optional annotations:**
```yaml
metadata:
  annotations:
    postgres-init.home.arpa/dbname: "custom-db-name"        # Default: release name
    postgres-init.home.arpa/controller: "custom-controller" # Default: release name
```

**What it does:**
- Injects a postgres-init container into `spec.values.controllers.{controller}.initContainers.init-db`
- References the auto-generated secret `{release-name}-postgres-init`
- Uses image: `ghcr.io/home-operations/postgres-init:17.6`

See: [postgres-init-container.yaml](./postgres-init-container.yaml)

---

### 5. Postgres Init ExternalSecret (`postgres-init-externalsecret.yaml`)

Auto-generates an ExternalSecret for postgres-init credentials when a HelmRelease has postgres-init enabled.

**Automatically triggered by:** HelmRelease with `postgres-init.home.arpa/enabled: "true"`

**Generated ExternalSecret contains:**
- `INIT_POSTGRES_HOST`: postgres-rw.database.svc.cluster.local
- `INIT_POSTGRES_SUPER_USER`: From Infisical
- `INIT_POSTGRES_SUPER_PASS`: From Infisical
- `INIT_POSTGRES_PORT`: 5432
- `INIT_POSTGRES_DBNAME`: From annotation or release name
- `INIT_POSTGRES_USER`: From Infisical (key specified in annotation)
- `INIT_POSTGRES_PASS`: From Infisical (key specified in annotation)

**Required Infisical secrets:**
1. `POSTGRES_SUPER_USER` - Cluster-wide superuser
2. `POSTGRES_SUPER_PASS` - Cluster-wide superuser password
3. `{MYAPP}_POSTGRES_USER` - App-specific database user
4. `{MYAPP}_POSTGRES_PASSWORD` - App-specific database password

**Auto-cleanup:** The generated ExternalSecret is automatically deleted when the source HelmRelease is deleted.

See: [postgres-init-externalsecret.yaml](./postgres-init-externalsecret.yaml)

---

## Complete Postgres Init Example

### Before (Manual Pattern)

**helmrelease.yaml** - 100+ lines with init container:
```yaml
spec:
  values:
    controllers:
      myapp:
        initContainers:
          init-db:
            image:
              repository: ghcr.io/home-operations/postgres-init
              tag: 17.6@sha256:...
            envFrom:
              - secretRef:
                  name: myapp-postgres-init
        containers:
          app:
            # ... app config
```

**externalsecret.yaml** - 40+ lines:
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
      engineVersion: v2
      data:
        INIT_POSTGRES_HOST: postgres-rw.database.svc.cluster.local
        INIT_POSTGRES_SUPER_USER: "{{ .POSTGRES_SUPER_USER }}"
        INIT_POSTGRES_SUPER_PASS: "{{ .POSTGRES_SUPER_PASS }}"
        INIT_POSTGRES_PORT: "5432"
        INIT_POSTGRES_DBNAME: myapp
        INIT_POSTGRES_USER: "{{ .MYAPP_POSTGRES_USER }}"
        INIT_POSTGRES_PASS: "{{ .MYAPP_POSTGRES_PASSWORD }}"
  dataFrom:
    - find:
        path: POSTGRES_SUPER_USER
    # ... more config
```

### After (Kyverno Automation)

**helmrelease.yaml** - Just 3 annotations:
```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: myapp
  annotations:
    postgres-init.home.arpa/enabled: "true"
    postgres-init.home.arpa/user-key: "MYAPP_POSTGRES_USER"
    postgres-init.home.arpa/pass-key: "MYAPP_POSTGRES_PASSWORD"
spec:
  values:
    controllers:
      myapp:
        # No initContainers section needed - Kyverno injects it!
        containers:
          app:
            # ... app config
```

**externalsecret.yaml** - DELETE IT! Auto-generated by Kyverno

### Boilerplate Reduction

- **Init container definition**: ❌ Removed (15+ lines)
- **Postgres-init ExternalSecret**: ❌ Removed (40+ lines)
- **Annotations**: ✅ Added (3 lines)

**Total savings: 50+ lines → 3 lines per app**

---

## Real Example: Miniflux RSS Reader

See [kubernetes/apps/selfhosted/miniflux/app/helmrelease.yaml](../../../../selfhosted/miniflux/app/helmrelease.yaml) for a complete working example of the postgres-init pattern.

**What you need:**

1. **HelmRelease with annotations** (3 lines):
   ```yaml
   annotations:
     postgres-init.home.arpa/enabled: "true"
     postgres-init.home.arpa/user-key: "MINIFLUX_POSTGRES_USER"
     postgres-init.home.arpa/pass-key: "MINIFLUX_POSTGRES_PASSWORD"
   ```

2. **Infisical secrets** (create once per app):
   - `MINIFLUX_POSTGRES_USER`
   - `MINIFLUX_POSTGRES_PASSWORD`

3. **That's it!** Kyverno handles:
   - Injecting init container
   - Generating ExternalSecret
   - Configuring environment variables
   - Database initialization

---

## Testing Policies

### Validate Kyverno policies

```bash
# Check policy status
kubectl get clusterpolicies

# View policy details
kubectl describe clusterpolicy postgres-init-container
kubectl describe clusterpolicy postgres-init-externalsecret

# Check generated resources
kubectl get externalsecrets -A | grep postgres-init

# View Kyverno logs
kubectl logs -n kyverno -l app.kubernetes.io/component=admission-controller
```

### Test on a new app

1. Create HelmRelease with annotations
2. Apply and verify ExternalSecret is generated:
   ```bash
   kubectl get externalsecret {app}-postgres-init -n {namespace}
   ```
3. Verify HelmRelease is mutated with init container:
   ```bash
   kubectl get helmrelease {app} -n {namespace} -o yaml | grep -A 10 initContainers
   ```
4. Check pod starts successfully:
   ```bash
   kubectl get pods -n {namespace}
   kubectl logs -n {namespace} {pod} -c init-db
   ```

---

## Migration Guide

### Migrating Existing Apps

To migrate an existing app using manual postgres-init to the Kyverno pattern:

1. **Add annotations to HelmRelease:**
   ```yaml
   metadata:
     annotations:
       postgres-init.home.arpa/enabled: "true"
       postgres-init.home.arpa/user-key: "MYAPP_POSTGRES_USER"
       postgres-init.home.arpa/pass-key: "MYAPP_POSTGRES_PASSWORD"
   ```

2. **Remove manual init container from HelmRelease:**
   ```yaml
   # DELETE THIS SECTION:
   initContainers:
     init-db:
       image:
         repository: ghcr.io/home-operations/postgres-init
         # ...
   ```

3. **Delete the postgres-init ExternalSecret:**
   ```bash
   rm kubernetes/apps/{namespace}/{app}/app/postgres-init-externalsecret.yaml
   # Or remove it from the kustomization resources
   ```

4. **Commit and apply:**
   ```bash
   git add .
   git commit -m "feat({app}): migrate to Kyverno postgres-init automation"
   flux reconcile kustomization {app} -n {namespace}
   ```

5. **Verify:**
   ```bash
   # Check ExternalSecret was auto-generated
   kubectl get externalsecret {app}-postgres-init -n {namespace}

   # Check pod restarts successfully
   kubectl get pods -n {namespace}
   ```

---

## Troubleshooting

### ExternalSecret not generated

**Check:**
1. Policy is applied: `kubectl get clusterpolicy postgres-init-externalsecret`
2. Required annotations present: `kubectl get helmrelease {app} -n {namespace} -o yaml | grep postgres-init`
3. Kyverno logs: `kubectl logs -n kyverno -l app.kubernetes.io/component=admission-controller`

**Common issues:**
- Missing `user-key` or `pass-key` annotations (required)
- HelmRelease not in a reconciled state
- Kyverno admission controller not running

### Init container not injected

**Check:**
1. Policy is applied: `kubectl get clusterpolicy postgres-init-container`
2. Annotation is correct: `postgres-init.home.arpa/enabled: "true"` (string, not boolean)
3. Controller name matches: Default is release name, override with `postgres-init.home.arpa/controller`

### Database initialization fails

**Check init container logs:**
```bash
kubectl logs -n {namespace} {pod} -c init-db
```

**Common issues:**
- Infisical secrets not found (check ExternalSecret status)
- PostgreSQL cluster not ready (check cloudnative-pg)
- Incorrect credentials in Infisical

---

## Updating Postgres-Init Image Version

The postgres-init image is managed via ConfigMap, making it Renovate-friendly!

**Automatic updates via Renovate:**
- Renovate automatically detects the image in `postgres-init-config.yaml`
- Creates PRs when new versions are available
- No manual intervention needed! 🎉

**Manual update (if needed):**

1. Edit `postgres-init-config.yaml`:
   ```yaml
   data:
     image-repository: ghcr.io/home-operations/postgres-init
     image-tag: NEW_VERSION@sha256:NEW_HASH  # Update this
   ```

2. Apply:
   ```bash
   flux reconcile kustomization kyverno-policies -n kyverno
   ```

3. All apps will use the new version on next pod restart

**How it works:**
- The ConfigMap stores the image reference centrally
- The ClusterPolicy uses `lookup()` to fetch values from the ConfigMap
- Single source of truth for all postgres-init containers across the cluster

---

## Related Documentation

- [Kyverno Documentation](https://kyverno.io/docs/)
- [postgres-init Container Source](https://github.com/home-operations/containers/tree/main/apps/postgres-init)
- [CloudNativePG](https://cloudnative-pg.io/)
- [External Secrets Operator](https://external-secrets.io/)
