# kagent (on Agent Substrate)

Kubernetes-native AI agents ([kagent](https://kagent.dev) 1.x), sandboxed in gVisor by
Agent Substrate, with the in-cluster Ollama instances as the model backend.
UI: `https://kagent.${SECRET_DOMAIN}` (internal gateway, Authentik forward-auth).
Tracking issue: #4777.

**This is one stack spread over three namespaces** (plus the vault tool server in `selfhosted`). Upstream fixes the split: agents
run in `kagent`, kept apart from the Substrate control plane and its signing keys.

| Folder (= namespace)                | Flux Kustomizations                               | What it runs                                                                                                                                                                    |
| ----------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `podcertificate-controller-system/` | `substrate-podcert`                               | Cluster-wide signer for Kubernetes PodCertificates. Issues the service TLS and pod identity certs every Substrate pod mounts.                                                   |
| `ate-system/`                       | `substrate-crds`, `substrate-atelet`, `substrate` | Agent Substrate: API, identity server, router, egress gateway, RustFS snapshot store, and the `atelet` node agent.                                                              |
| `kagent/` (here)                    | `kagent-crds`, `kagent`, `kagent-agents`          | kagent controller and UI, the gVisor `WorkerPool` where agents actually run, the Ollama `ModelConfig`, and the agents.                                                          |
| `selfhosted/vault-mcp/`             | `vault-mcp`                                       | The Obsidian vault, mounted read-only, served to agents as an MCP tool server (`RemoteMCPServer` `vault`).                                                                      |
| `kagent/miniflux-mcp/`              | `miniflux-mcp`                                    | The Miniflux RSS reader served to agents as an MCP tool server (`RemoteMCPServer` `miniflux`); network policy lets it reach Miniflux only, and only kagent may call it.         |
| `kagent/web-fetch/`                 | `web-fetch`                                       | Reads public web pages as Markdown for agents (`RemoteMCPServer` `web-fetch`); network policy allows the public internet only, never the cluster or LAN.                        |
| `kagent/deals-mcp/`                 | `deals-mcp`                                       | Hardware price lookups from official APIs, eBay Browse and GSA Auctions (`RemoteMCPServer` `deals`, two read-only search tools); public internet only, callable by kagent only. |

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

## Called from OpenClaw

OpenClaw (`molt` in `ai`) can hand tasks to these agents. The `kagent-controller`
network policy admits the molt pod, and OpenClaw has the controller's MCP endpoint
registered as the `kagent` server. That registration lives in OpenClaw's config on
the molt PVC, not in Git:

```bash
openclaw config set mcp.servers.kagent '{
  "url": "http://kagent-controller.kagent.svc.cluster.local:8083/mcp",
  "transport": "streamable-http",
  "toolFilter": {"include": ["list_agents", "invoke_agent", "get_session", "get_task", "list_tasks"]}
}' --strict-json
```

`config set` applies without a restart. `openclaw mcp add` and `openclaw mcp probe`
only run with the gateway stopped. To test, run a turn in a scratch session:
`openclaw agent --agent main --session-key kagent-smoke --json -m "ask k8s-reader ..."`.

The include list leaves out the endpoint's sandbox and session-delete tools.
`invoke_agent` returns the answer itself for short tasks; for longer ones it returns
a session ID and the reply is read with `get_session`. kagent's API has no auth of
its own, so the network policy is the only gate: whoever can prompt OpenClaw can
invoke any agent here.

## Layout of `kagent/agents/` (adding an agent)

```
kagent/agents/
├── kustomization.yaml     # ./platform + one line per agent file
├── platform/              # shared pieces any agent can reference
│   ├── models.yaml        # ModelConfigs claude-opus / claude-sonnet / claude-haiku + the dummy key
│   ├── harnesses.yaml     # Harnesses claude-code and claude-code-tools (see "Harnesses")
│   ├── egress.yaml        # EgressPolicies (see "Egress policies") + the setup-token ExternalSecret
│   ├── miniflux.yaml      # tool servers: one RemoteMCPServer per file,
│   ├── vault-mcp.yaml     #   with its ExternalSecret if it has one
│   ├── web-fetch.yaml
│   └── deals.yaml
└── <agent>.yaml           # one file per agent: its AgentTemplate + Agent, nothing else
```

To add an agent, copy an existing agent file, point it at a ModelConfig, Harness and tool
servers from `platform/`, and add it to `kustomization.yaml`. Editing an agent file
rebuilds only that agent's golden snapshot; editing a `platform/` resource rebuilds every
agent that references it (several minutes each). EgressPolicies are the exception: an edit
applies live. The `kagent-agent` skill (`.claude/skills/kagent-agent/`) has the full
recipe, templates and a test script.

### Agents

The live agents are the files listed in `kagent/agents/kustomization.yaml`:

| Agent               | Model                          | Harness             | Tool servers                                     | Called by                                                                                        |
| ------------------- | ------------------------------ | ------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| `claude`            | `claude-opus`                  | `claude-code`       | `vault`, `web-fetch`, `miniflux`                 | The owner, interactively (UI, or OpenClaw through `invoke_agent`).                               |
| `night-editor`      | `claude-opus`                  | `claude-code`       | `vault`, `web-fetch`                             | The `night-shift` vault job: brief topic sections, vault gap research, the curated-note pass.    |
| `security-brief`    | `claude-sonnet`                | `claude-code-tools` | `web-fetch`, `miniflux`                          | The `night-shift` vault job, for the brief's Security section. Also has `security-feeds` egress. |
| `feeds-digest`      | `claude-sonnet`                | `claude-code-tools` | `miniflux`                                       | The `night-shift` vault job, for the brief's Feeds section. Reads only.                          |
| `feeds-curator`     | `claude-sonnet`                | `claude-code-tools` | `miniflux`                                       | The owner (UI or OpenClaw). Changes feeds only on an explicit instruction; cannot delete.        |
| `reading-processor` | `claude-haiku`                 | `claude-code`       | `vault`                                          | The `reading-process` vault job, hourly, one saved article per call.                             |
| `link-suggester`    | `claude-haiku`                 | `claude-code`       | `vault`                                          | The `link-suggester` vault job, nightly, one unlinked note per call.                             |
| `blog-scout`        | `claude-sonnet`                | `claude-code`       | `vault`                                          | The `blog-scout` vault job, Sundays and Wednesdays, one call with recent saved articles.         |
| `blog-drafter`      | `claude-opus`                  | `claude-code`       | `vault`                                          | The `blog-drafter` vault job, hourly, one blog note at `stage: drafting` per call.               |
| `voice-processor`   | `claude-sonnet`                | `claude-code`       | `vault`                                          | The `voice-inbox` vault job, one voice memo per call.                                            |
| `voice-librarian`   | `default-model-config` (local) | `kagent-default`    | `vault`                                          | The `voice-inbox` vault job, as the fallback when `voice-processor` fails or is out of usage.    |
| `nightwatch`        | `default-model-config` (local) | `kagent-default`    | `kagent-tool-server` (4 read tools), `web-fetch` | The `nightwatch` vault job, once per new finding.                                                |
| `k8s-reader`        | `default-model-config` (local) | `kagent-default`    | `kagent-tool-server` (4 read tools)              | Nobody on a schedule; a test agent for questions about the cluster.                              |
| `flux-ops`          | `default-model-config` (local) | `kagent-default`    | `kagent-tool-server` (4 read tools)              | The owner or a working session, by hand (below).                                                 |

Every Claude agent also lists the `claude-subscription` EgressPolicy. The vault jobs are the
CronJobs of the `vault-jobs` HelmRelease (`selfhosted/obsidian-vault/jobs`); each calls its
agent over A2A at
`http://kagent-controller.kagent.svc.cluster.local:8083/agents/kagent/<agent>`. The
`kagent-controller` network policy (`kagent/app/ciliumnetworkpolicy.yaml`) admits pods in
`selfhosted` that carry the label `kagent-client: "true"`; today seven job controllers set it:
`voice-inbox`, `night-shift`, `nightwatch`, `reading-process`, `link-suggester`, `blog-scout` and `blog-drafter`. A new job that calls an
agent sets the same label (`pod.labels: *callsAgents`); the policy needs no change. The reading pipeline's side of this is in
`kubernetes/apps/selfhosted/obsidian-vault/README.md`.

### `flux-ops` (read-only Flux sweep)

Lists Flux Kustomizations and HelmReleases that are not Ready, and Kustomizations behind
the current Git revision. It runs on the local model with the four read tools of
`kagent-tool-server`, so it can change nothing. It copies matching rows exactly and never
counts them (a small model miscounts long listings); count the rows yourself.

```sh
.claude/skills/kagent-agent/scripts/ask-agent.sh flux-ops 'Run a full sweep.'
```

It does not look at pull requests. Flagging mergeable PRs needs GitHub access: either a
read-only GitHub MCP server, or a Claude agent on `claude-code-tools` with the
`github-read` egress policy and `curl` (which in turn cannot hold the Kubernetes tools,
because the Claude harness would expose the whole tool server, `shell` included).

## Harnesses

A Harness is the runtime an Agent runs on (`Agent.spec.harnessRef`). One Harness per
toolset: to give agents different tooling, add a Harness, do not change a shared one.

| Harness             | Runtime                                                                                                    | Use it for                                                                                    |
| ------------------- | ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `kagent-default`    | kagent's own runtime (from the chart)                                                                      | Agents on the local Ollama model (`k8s-reader`, `flux-ops`, `nightwatch`, `voice-librarian`). |
| `claude-code`       | Claude Code, kagent's stock image                                                                          | Claude agents that only need MCP tool servers.                                                |
| `claude-code-tools` | Claude Code on `ghcr.io/dapperdivers/claude-harness-tools` (adds curl, jq, python3, pip, requests, pyyaml) | Claude agents that need a shell with HTTP and JSON tooling, together with egress policies.    |

Notes on `claude-code-tools`:

- The image is built in `github.com/dapperdivers/containers` (`claude-harness-tools`) FROM
  kagent's claude harness image and pinned by digest. **Rebuild and re-pin it on every
  kagent upgrade**; the base must match
  `kubectl -n kagent get cm kagent-controller -o yaml | grep -A3 harnessImages`.
- It bakes in `/etc/claude-code/managed-settings.json`, which denies the destructive
  Miniflux MCP tools (deletes, flush history, mark-all-read, API key and user management)
  for every agent on the harness. Verified live 2026-11-18: denied tools are absent from the
  agent's tool list. This is the only per-tool restriction for Claude agents (the harness
  ignores per-tool allowlists), and it is per image, not per agent: tools not on the deny
  list stay callable, so a different restriction needs a different image and harness.

## Egress policies

A sandbox reaches its model and its bound tool servers, nothing else. An EgressPolicy
opens a named set of origins (scheme + host + port, every path), and only for Agents that
list it in `spec.egressPolicyRefs` (up to 16). All are in `platform/egress.yaml`.

| EgressPolicy            | Opens                                                                                          | Use it for                                                                            |
| ----------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `claude-subscription`   | `api.anthropic.com`, with the subscription token injected                                      | Required on every Claude agent.                                                       |
| `web-search`            | In-cluster SearXNG (`searxng.selfhosted.svc.cluster.local:8080`)                               | Web search from the shell: `/search?q=...&format=json`.                               |
| `security-feeds`        | NVD, FIRST EPSS, CISA KEV, OSV, GitHub advisories (`api.github.com`)                           | CVE and advisory lookups.                                                             |
| `github-read`           | `github.com`, `api.github.com`, raw, codeload and release-asset hosts                          | Reading public repos and releases. No token: 60 API requests per hour, shared.        |
| `package-docs`          | `pypi.org`, `registry.npmjs.org`, `pkg.go.dev`, `artifacthub.io`, `kubernetes.io`, `fluxcd.io` | Package versions and reference docs.                                                  |
| `cluster-observability` | In-cluster Prometheus (`:9090`) and VictoriaLogs (`:9428`)                                     | **Bound to no agent, on purpose.** No auth, and Prometheus has its admin API enabled. |

In-cluster targets must be written as `http://<svc>.<ns>.svc.cluster.local:<port>`. The
request leaves from the egress gateway (`app=atenet-egress` in `ate-system`), so a
CiliumNetworkPolicy on the target has to admit that source.

## The `claude` agent (subscription)

`kagent/agents/claude.yaml` runs Claude Opus 5.5 on kagent's Claude Code harness (shared
pieces in `kagent/agents/platform/`: `models.yaml`, `harnesses.yaml`, `egress.yaml`), on the
Claude subscription (setup-token `MOLT_ANTHROPIC_SETUP_TOKEN`, shared with OpenClaw). The
token never enters the sandbox: Claude Code sends `Authorization: Bearer <placeholder>` and
the `claude-subscription` EgressPolicy swaps in the real token at the egress gateway.

This is undocumented in kagent 1.0.1. It relies on kagent allowing `ANTHROPIC_AUTH_TOKEN` and
`ANTHROPIC_CUSTOM_HEADERS` in Harness env, on Claude Code preferring `ANTHROPIC_AUTH_TOKEN`
over the (dummy) API key, and on the OAuth beta header. Upgrades can break it; check this
agent after bumping kagent. Usage counts against the subscription's 5-hour limits.
Tools: `WebSearch` (Anthropic-side), `web-fetch`, the read-only `vault` and `miniflux`. The
Miniflux allowlist in `claude.yaml` is documentation only: on this harness the agent holds
every Miniflux tool, deletes included, which is accepted because it is interactive. The
unattended agents either do not bind `miniflux` or run on `claude-code-tools`.
