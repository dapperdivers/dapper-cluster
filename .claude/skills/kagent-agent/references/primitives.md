# kagent 1.0.1 primitives: reference

Researched from the kagent and Substrate v1.0.1 source on 2026-11-18. **(live)** marks
what was also tested on this cluster; the rest is read from source and may need a live
test before you rely on it. API group `api.kagent.dev/v1alpha3`, namespace `kagent`.
Upstream source: `github.com/kagent-dev/kagent` (docs under `docs/architecture/`).

## AgentTemplate

| Field                               | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `systemPrompt` / `systemPromptFrom` | inline text, or `{name, key}` of a same-namespace ConfigMap. At most one.                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `promptTemplate`                    | When set (even `{}`), the prompt is rendered as a Go `text/template` by the controller. `dataSources: [{name: <configmap>, alias: shared}]` then `{{ include "shared/house-rules" }}`. Variables: `.AgentTemplateName`, `.Description`, `.ToolNames` (only names written in `tools[].mcp.tools`). No sprig. Works on both harnesses. Literal `{{` must be escaped. A ConfigMap content change rebuilds every agent that includes it, so shared blocks should be stable text. Not used here yet. |
| `outputSchema*`                     | Do not use. kagent-default: sends `response_format` on every turn, which stops tool calls on Ollama's OpenAI endpoint **(live)**; upstream bug #3460, fix PR #3502 not in 1.0.1. Claude: compile error. If hard validation is ever needed: a tool-using agent without a schema, then a tool-less formatter agent with one.                                                                                                                                                                      |
| `tools[].mcp`                       | `server: {kind: RemoteMCPServer, name}`; optional `tools: [...]` allowlist (max 50): enforced on kagent-default, ignored on Claude **(live)** with a warning in Agent status. `requireApproval` pauses the task until a human approves: never on unattended agents.                                                                                                                                                                                                                             |
| `tools[].subAgent`                  | `{name, description, templateRef: {name}}`: another same-namespace template compiled into the parent's runtime, one level deep. On Claude the child cannot have tools, skills or plugins. There is no way for an agent to call an independent Agent.                                                                                                                                                                                                                                            |
| `skills`                            | max 50. `source.oci` (digest-pinned; mounted read-only before the golden build; max 29 distinct images per Agent) **(live)**, `source.git` / `source.bucket.s3` (fetched inside the golden sandbox, which has no network: crash **(live)**). `source.path` is the directory holding SKILL.md. Claude exposes them as `kagent-skills:<name>`. kagent-default supports instructions-only skills (bash is disabled here).                                                                          |
| `plugins`                           | Agent Plugins packages (OCI) from which skills are selected by name. Not used here.                                                                                                                                                                                                                                                                                                                                                                                                             |

## Agent

`template.ref.name`, `harnessRef.name`, `egressPolicyRefs[]`. Status carries everything:
conditions `Accepted → ResolvedRefs → Compatible → Ready` (later ones show `Blocked`),
`warnings`, `latestSuccessfulRevision`. AgentTemplate has no status.

## What triggers a new revision (golden build)

Yes: prompt text; content of any ConfigMap the prompt or schema reads; description;
ModelConfig spec; RemoteMCPServer URL/headers; MCP bindings; skills; plugins; sub-agents;
Harness env or image; chart `runtimeDefaults`.
No: labels/annotations; YAML comments; `egressPolicyRefs` and EgressPolicy edits (applied
live); a Secret's value; adding unreferenced platform objects **(live)**.

A failed build keeps the last good revision serving; retries back off 15s, 1m, 4m, 10m.

## Harness

- Variants `kagent`, `claude`, `codex`, `byo`. Ours: `kagent-default` (chart-created),
  `claude-code`, `claude-code-tools`.
- `spec.workload.image` (digest-pinned) replaces the runtime image **(live)**. Contract for
  `claude: {}`: keep ENTRYPOINT (`/usr/local/bin/kagent-claude`), USER 65532, WORKDIR
  `/data`; nothing under `/data`, `/tmp`, `/run/kagent`; the Claude Code version must be the
  base's. The base (`ghcr.io/kagent-dev/kagent/claude-harness`, Alpine: bash, git, ripgrep)
  is listed in ConfigMap `kagent-controller` key `harnessImages`. Pulled anonymously by the
  node agent, so the image must be public.
- Our image: `github.com/dapperdivers/containers`, dir `claude-harness-tools` (default
  branch `master`). It adds curl, jq, python3 (+requests, yaml) and
  `/etc/claude-code/managed-settings.json` with `permissions.deny` rules. Denied tools
  disappear from the agent's tool list **(live)**. The policy is per image, so a different
  restriction means another image and Harness. MCP tools are named `mcp__<server>__<tool>`.
- `spec.env`: literals only; ~32 vars total. We rely on `ANTHROPIC_AUTH_TOKEN`
  (placeholder, swapped at the egress gateway) and `ANTHROPIC_CUSTOM_HEADERS`.
- Claude Code runs with `--dangerously-skip-permissions --setting-sources ""`: user and
  project settings are never read; only managed settings apply.
- `SandboxTemplate` is for standalone scratch sandboxes, not agents. `ModelProviderConfig`
  is not reconciled in 1.0.1.

## ModelConfig

One per model. Claude: `provider: Anthropic`, `model: <id>`, the dummy `apiKeySecret`
(the harness insists on one), `anthropic: {}`. The subscription EgressPolicy covers every
model. Local: the OpenAI provider pointed at Ollama with reasoning off (the native Ollama
provider cannot disable thinking).

## EgressPolicy

- `destinations[].origin`: scheme + DNS name + optional port; all paths allowed. One
  leftmost wildcard label (`https://*.example.com`). No bare `*`, no IPs. http is allowed
  (in-cluster FQDNs; the sandbox DNS has no search domains). Max 64 destinations per
  policy, 16 policies per Agent.
- `authentication: {header, prefix, secretKeyRef}` replaces a header the client already
  sends (so the client must send a placeholder).
- Enforcement: all sandbox TCP goes through the `atenet-egress` gateway in `ate-system`,
  which intercepts TLS; the trust bundle env vars are preset, so curl works unmodified
  **(live)**. Unlisted hosts fail DNS **(live)**. No WebSocket, no non-HTTP TCP.
- In-cluster targets protected by a CiliumNetworkPolicy must admit `ate-system` /
  `app=atenet-egress` (see `kagent/miniflux-mcp/app/ciliumnetworkpolicy.yaml`).
- Golden-build egress is hardcoded to the control plane only.

## Sandbox and sessions

- 1 CPU / 1 Gi per actor (global); one worker pod. Only `/data` survives between turns.
  No PVC mounts (use the vault MCP server).
- One A2A call without `contextId` = one new Session (7-day idle expiry). To continue a
  conversation pass the returned `contextId` in `params.message.contextId`.
- Reply shape: each model step is an artifact; tool calls/results are `data` parts with
  metadata `kagent.dev/a2a/part-type`; the final answer is the last text-bearing artifact
  (split into hundreds of parts on Claude). Token usage (kagent-default only) is in task
  metadata `https://kagent.dev/extensions/usage/v1`.

## Controller API

Port 8083: gRPC and gRPC-Web (`grpcurl -plaintext ... list`; reflection is on), A2A
JSON-RPC at `/agents/<ns>/<name>` (method `SendMessage`, header `A2A-Version: 1.0`), and
`/mcp`. Any other path returns 200 with an empty body. No auth in-cluster; the
CiliumNetworkPolicy `kagent-controller` decides who can connect.

Scheduled runs (`ScheduledRunService`, UI `/schedules`): Postgres only, no CRD, missed
runs are skipped, no overlap protection, open bug #3727 on gVisor workers. Use CronJobs.

## Not built yet

- Shared prompt blocks via `promptTemplate`.
- Read-only MCP servers for VictoriaLogs, Prometheus and Flux (researched: all three have
  official images with streamable HTTP and a server-side read-only mode).
- An operator archetype (agents that open pull requests).
