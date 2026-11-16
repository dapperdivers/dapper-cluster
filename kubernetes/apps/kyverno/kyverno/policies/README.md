# Kyverno Policies

Kyverno 1.20 (chart 3.10). Every policy here is a CEL policy type from
`policies.kyverno.io/v1`. Legacy `kyverno.io` ClusterPolicies no longer run
on 1.20, and the chart refuses to upgrade while any exist, so don't add one.

## Policies

| Policy                                       | Kind                     | What it does                                                                                                                                                                                                              |
| -------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `httproute-authentik-forward-auth`           | GeneratingPolicy         | For an HTTPRoute annotated `authentik.home.arpa/forward-auth: "true"`, generates `<route>-forward-auth` SecurityPolicy (Envoy ext-auth → Authentik embedded outpost). Synchronized: removed with the route or annotation. |
| `httproute-authentik-outpost-referencegrant` | GeneratingPolicy         | Per source namespace, generates `securitypolicy-to-outpost-<ns>` ReferenceGrant in `security`, so the SecurityPolicy can reach the outpost Service. Sticky (not synchronized).                                            |
| `postgres-init-container`                    | MutatingPolicy           | Injects the `init-db` init container into HelmReleases with `postgres-init.home.arpa/enabled: "true"`. See [postgres-init/](./postgres-init/README.md).                                                                   |
| `postgres-init-externalsecret`               | GeneratingPolicy         | Generates the `<release>-postgres-init` ExternalSecret those init containers read.                                                                                                                                        |
| `helmrelease-default-maxhistory`             | MutatingPolicy           | Defaults `spec.maxHistory: 3` on HelmReleases that don't set it (caps Helm history Secrets in etcd).                                                                                                                      |
| `default-security-context`                   | ValidatingPolicy (Audit) | Reports containers without `runAsNonRoot: true` / `allowPrivilegeEscalation: false`. Opt out: `kyverno.io/skip-security-defaults: "true"` on the Pod.                                                                     |
| `disable-automount-sa-token`                 | ValidatingPolicy (Audit) | Reports Pods that don't set `automountServiceAccountToken: false`. Opt out: `kyverno.io/automount-sa-token: "true"`.                                                                                                      |
| `require-probes`                             | ValidatingPolicy (Audit) | Reports containers without a `readinessProbe` (Job pods exempt).                                                                                                                                                          |
| `restrict-latest-tag`                        | ValidatingPolicy (Audit) | Reports images using `:latest`.                                                                                                                                                                                           |

The four ValidatingPolicies only report (`validationActions: [Audit]`), so they never block a deploy.
Results land in PolicyReports.

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
