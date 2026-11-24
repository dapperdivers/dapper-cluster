# Kyverno Policies

Kyverno 1.20 (chart 3.10). Every policy here is a CEL policy type from
`policies.kyverno.io/v1`. Legacy `kyverno.io` ClusterPolicies no longer run
on 1.20, and the chart refuses to upgrade while any exist, so don't add one.

## Policies

| Policy                                       | Kind                  | What it does                                                                                                                                                                                                                                                                |
| -------------------------------------------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `httproute-authentik-forward-auth`           | GeneratingPolicy      | For an HTTPRoute annotated `authentik.home.arpa/forward-auth: "true"`, generates `<route>-forward-auth` SecurityPolicy (Envoy ext-auth → Authentik embedded outpost). Synchronized: removed with the route or annotation.                                                   |
| `httproute-authentik-outpost-referencegrant` | GeneratingPolicy      | Per source namespace, generates `securitypolicy-to-outpost-<ns>` ReferenceGrant in `security`, so the SecurityPolicy can reach the outpost Service. Sticky (not synchronized).                                                                                              |
| `postgres-init-container`                    | MutatingPolicy        | Injects the `init-db` init container into HelmReleases with `postgres-init.home.arpa/enabled: "true"`. See [postgres-init/](./postgres-init/README.md).                                                                                                                     |
| `postgres-init-externalsecret`               | GeneratingPolicy      | Generates the `<release>-postgres-init` ExternalSecret those init containers read.                                                                                                                                                                                          |
| `restrict-latest-tag`                        | ValidatingPolicy      | Rejects Pods (all container types) whose image is `:latest` or untagged without a digest; digest-pinned refs pass. Enforced (Deny) since #4726.                                                                                                                             |
| `verify-home-operations-images`              | ImageValidatingPolicy | Audit trial (#4727): checks `ghcr.io/home-operations/*` images for SLSA v1 provenance signed by the `home-operations/containers` app-builder workflow on `main`. echo/konflate/kromgo/tuppr are unsigned and excluded.                                                      |
| `volsync-repository-mkdir`                   | GeneratingPolicy      | When a `cephfs-static` PV rooted at `/volsync/<app>` is created, generates a one-shot Job `rook-ceph/mkdir-volsync-<app>` that creates the directory via libcephfs. Replaces running `task volsync:mkdir` before merging. Not synchronized; the Job self-deletes after 24h. |
| `volsync-schedule-stagger`                   | MutatingPolicy        | Rewrites the minute of any VolSync ReplicationSource left on a component default schedule (`0 * * * *` local, `30 0 * * *` remote) to `sha256(sourcePVC) % 60` (remote: plus 30), so backups don't all snapshot in the same minute. Explicit schedules are left alone.      |

The other audit-only pod-security ValidatingPolicies and the HelmRelease `maxHistory` default
were removed in #4713: nobody read their PolicyReports, and Flux already defaults `maxHistory` to 5.
`restrict-latest-tag` was kept because its failure list is short and fixable, so it can enforce.

## Usage

### Forward-auth an app behind Authentik

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  annotations:
    authentik.home.arpa/forward-auth: "true"
```

The app also needs a proxy provider + application in Authentik (blueprints). Kyverno
excludes `kube-system` globally, so routes there need a static SecurityPolicy
(see `kube-system/cilium/app/securitypolicy.yaml` for hubble-ui).

## Conventions

- **Generating policies use `generate[].template`** (YAML + `interpolate: cel` with
  `(( ... ))` placeholders), not CEL map literals. CEL map literals must be
  homogeneous, which means `dyn()` everywhere. Keep any `(( ... ))` from closing right
  before a literal `)` (build such strings in a `variables` entry instead).
- **Generating policies use `useServerSideApply: true` + `generateExisting`**, so a
  same-named policy update re-applies existing objects in place instead of recreating them.
- **Before deleting a synchronized generating policy**, set
  `evaluation.orphanDownstreamOnPolicyDelete.enabled: true` and let it reconcile.
  Otherwise its generated resources are deleted with it (for forward-auth, that's SSO).
- Controllers need RBAC for every trigger and generated kind. See `../app/rbac.yaml`
  (aggregated via `rbac.kyverno.io/aggregate-to-*` labels).

## Testing

`kubectl apply --dry-run=server` validates the schema only. It does **not** evaluate
CEL or render templates. Use the repo-pinned CLI (`.mise.toml`; Homebrew's may be older):

```bash
# Render what a GeneratingPolicy / MutatingPolicy produces for a live object
kubectl -n media get httproute radarr -o json > /tmp/route.json
kubectl get crd httproutes.gateway.networking.k8s.io -o yaml > /tmp/crd.yaml
mise exec aqua:kyverno/kyverno -- kyverno apply httproute-authentik-forward-auth.yaml \
  --resource /tmp/route.json --crd-paths /tmp/crd.yaml --output-dir /tmp/out
```

Diff the output against the live generated objects before merging. Policies that call
`resource.Get` need the looked-up objects supplied with `--context-file` (a
`cli.kyverno.io/v1alpha1` `Context`).

```bash
# Live status
kubectl get vpol,mpol,gpol
kubectl -n kyverno get updaterequests   # generate work items (auto-cleaned after 24h)
```
