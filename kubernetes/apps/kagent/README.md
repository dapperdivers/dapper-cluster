# kagent (on Agent Substrate)

Kubernetes-native AI agents ([kagent](https://kagent.dev) 1.x), sandboxed in gVisor by
Agent Substrate, with the in-cluster Ollama instances as the model backend.
Tracking issue: #4777.

**This is one stack spread over three namespaces.** Upstream fixes the split: agents
run in `kagent`, kept apart from the Substrate control plane and its signing keys.

| Folder (= namespace)                | Flux Kustomizations                               | What it runs                                                                                                                  |
| ----------------------------------- | ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `podcertificate-controller-system/` | `substrate-podcert`                               | Cluster-wide signer for Kubernetes PodCertificates. Issues the service TLS and pod identity certs every Substrate pod mounts. |
| `ate-system/`                       | `substrate-crds`, `substrate-atelet`, `substrate` | Agent Substrate: API, identity server, router, egress gateway, RustFS snapshot store, and the `atelet` node agent.            |
| `kagent/` (here)                    | `kagent-crds`, `kagent`, `kagent-agents`          | kagent controller and UI, the gVisor `WorkerPool` where agents actually run, the Ollama `ModelConfig`, and the agents.        |

Install order (enforced with `dependsOn`):

```
substrate-crds → substrate-podcert → substrate-atelet → substrate ─┐
                                    cloudnative-pg-cluster ────────┤
kagent-crds ───────────────────────────────────────────────────────┴→ kagent → kagent-agents
```

Every Kustomization in the stack carries `app.kubernetes.io/part-of: kagent`:

```bash
kubectl get kustomizations -A -l app.kubernetes.io/part-of=kagent
```

## Charts

All six charts are kagent's own, published at `oci://ghcr.io/kagent-dev/...`. The
Substrate charts come from kagent's fork (`kagent-dev/substrate`); upstream
`agent-substrate/substrate` has no Helm chart, only the `ate-setup` CLI.

## Done by hand (not in Git)

These have no declarative path yet (see #4777). Recreate them before reinstalling:

- **Key pools** (`kubectl ate admin make-ca-pool` / `make-jwt-pool`, plugin from the
  `kagent-dev/substrate` release): `service-dns-ca-pool`, `postgres-ca-pool`,
  `pod-identity-ca-pool` in `podcertificate-controller-system`; `actor-id-jwt-pool`,
  `actor-id-ca-pool`, `egress-mitm-ca-pool` in `ate-system`; plus `actor-id-ca-certs`
  (the PEM root of `actor-id-ca-pool`).
- **Postgres**: database `kagent` on the CNPG cluster, with the kagent and substrate
  roles and schemas from each project's `setup.sql`.
- **Secrets**: `kagent-postgres-owner`, `kagent-postgres-readwrite` (in `kagent`);
  `substrate-postgres-owner`, `substrate-postgres-readwrite`, `kagent-rustfs-credentials`
  (in `ate-system`).

## Using it

```bash
kubectl port-forward -n kagent svc/kagent-ui 8082:8080   # UI (no auth; don't expose)
kubectl get agents,workerpools -n kagent
```
