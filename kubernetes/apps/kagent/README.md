# kagent (on Agent Substrate)

Kubernetes-native AI agents ([kagent](https://kagent.dev) 1.x), sandboxed in gVisor by
Agent Substrate, with the in-cluster Ollama instances as the model backend.
UI: `https://kagent.${SECRET_DOMAIN}` (internal gateway, Authentik forward-auth).
Tracking issue: #4777.

**This is one stack spread over three namespaces** (plus the vault tool server in `selfhosted`). Upstream fixes the split: agents
run in `kagent`, kept apart from the Substrate control plane and its signing keys.

| Folder (= namespace)                | Flux Kustomizations                               | What it runs                                                                                                                                             |
| ----------------------------------- | ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `podcertificate-controller-system/` | `substrate-podcert`                               | Cluster-wide signer for Kubernetes PodCertificates. Issues the service TLS and pod identity certs every Substrate pod mounts.                            |
| `ate-system/`                       | `substrate-crds`, `substrate-atelet`, `substrate` | Agent Substrate: API, identity server, router, egress gateway, RustFS snapshot store, and the `atelet` node agent.                                       |
| `kagent/` (here)                    | `kagent-crds`, `kagent`, `kagent-agents`          | kagent controller and UI, the gVisor `WorkerPool` where agents actually run, the Ollama `ModelConfig`, and the agents.                                   |
| `selfhosted/vault-mcp/`             | `vault-mcp`                                       | The Obsidian vault, mounted read-only, served to agents as an MCP tool server (`RemoteMCPServer` `vault`).                                               |
| `kagent/web-fetch/`                 | `web-fetch`                                       | Reads public web pages as Markdown for agents (`RemoteMCPServer` `web-fetch`); network policy allows the public internet only, never the cluster or LAN. |

Install order (enforced with `dependsOn`):

```
substrate-crds → substrate-podcert → substrate-atelet → substrate ─┐
                                    cloudnative-pg-cluster ────────┤
kagent-crds ───────────────────────────────────────────────────────┴→ kagent → kagent-agents
```

Everything the stack's Kustomizations apply (HelmReleases, chart sources, agents) carries
`app.kubernetes.io/part-of: kagent`:

```bash
kubectl get helmreleases -A -l app.kubernetes.io/part-of=kagent
```

## Charts

All six charts are kagent's own, published at `oci://ghcr.io/kagent-dev/...`. The `kagent`
chart is pulled through the `kagent` HelmRepository (`flux/meta/repositories/helm/`)
rather than an OCIRepository: it puts the chart version into labels and image tags,
which breaks on the `+<digest>` suffix an OCIRepository adds. The
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

## The `claude` agent (subscription)

`kagent/agents/claude.yaml` runs Claude Sonnet 5.5 on kagent's Claude Code harness, on the
Claude subscription (setup-token `MOLT_ANTHROPIC_SETUP_TOKEN`, shared with OpenClaw). The
token never enters the sandbox: Claude Code sends `Authorization: Bearer <placeholder>` and
the `claude-subscription` EgressPolicy swaps in the real token at the egress gateway.

This is undocumented in kagent 1.0.1. It relies on kagent allowing `ANTHROPIC_AUTH_TOKEN` and
`ANTHROPIC_CUSTOM_HEADERS` in Harness env, on Claude Code preferring `ANTHROPIC_AUTH_TOKEN`
over the (dummy) API key, and on the OAuth beta header. Upgrades can break it; check this
agent after bumping kagent. Usage counts against the subscription's 5-hour limits.
Tools: `WebSearch` (Anthropic-side), `web-fetch` and the read-only `vault`.
