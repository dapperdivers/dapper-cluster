# fleet-restore drafts (2026-11-24)

Drafts for a human to turn into dapper-cluster PRs. Nothing here was applied. All 32 files (1 table, 13 knights,
14 chains, 4 infra) passed `kubectl apply --dry-run=server --validate=strict` against dapper-cluster on 2026-11-24,
after the whiteboard update; the cluster was checked unchanged afterwards.
`_orig/` is the fleet as it was before retirement (`git show 12cbac303^:kubernetes/apps/roundtable/...`), for diffing.

Tracking: roundtable-k8s/roundtable #369 (restore the personal fleet) and #214 (retire kagent).

Updated 2026-11-24 for the product whiteboard (#377):

- **Decision 13: a knight is a persona, a chain is a job.** Each migrated kagent agent is a Chain in `chains/jobs/`
  run by one persona knight; the kagent prompt moved into the Chain's step. Five agents retire.
- **Decision 8: every knight is isolated by default** (gVisor + default-deny egress). Every knight draft has a
  commented-out isolation block with its placeholder egress allowlist. The fields do not exist in the CRD yet.
- **Decision 12: at most once.** No job chain has retries; the caller retries on its next run.

## Files

| File                                                                                      | What                                                                                                           | Phase             |
| ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ----------------- |
| `tables/personal.yaml`                                                                    | RoundTable `personal` (fleet-a streams)                                                                        | 1                 |
| `knights/galahad.yaml`                                                                    | today's galahad + table labels; persona for `security-brief`                                                   | 1                 |
| `knights/kay.yaml`, `tristan.yaml`, `gawain.yaml`                                         | research/intel (persona for `feeds-digest`, `night-editor`), infra (persona for `nightwatch`), briefing editor | 1                 |
| `chains/morning-briefing-phase1.yaml`                                                     | daily brief with the phase-1 knights                                                                           | 1                 |
| `knights/lancelot.yaml`, `gareth.yaml`, `patsy.yaml` + `infra/patsy-rbac.yaml`            | career, wellness, vault curator                                                                                | 2                 |
| `knights/bedivere.yaml`, `percival.yaml`, `agravain.yaml` + `infra/*-externalsecret.yaml` | home, finance, pentest (credentials)                                                                           | 3                 |
| `chains/morning-briefing.yaml`, `chains/fleet-self-improvement.yaml`                      | full daily brief, weekly self-improvement                                                                      | 3                 |
| `knights/watchman.yaml`, `chains/night-watch.yaml`                                        | platform night watch (roundtable-dev table)                                                                    | 4                 |
| `knights/intel-triage.yaml`                                                               | NEW persona: tool-less, vault-less clerk (pilot, #357)                                                         | kagent pilot      |
| `knights/librarian.yaml`                                                                  | NEW persona: read-only vault reader for the five vault jobs                                                    | kagent batch A    |
| `chains/jobs/*.yaml`                                                                      | the 10 kagent jobs as Chains (table below)                                                                     | with their knight |

(`callable/` is gone: its two knights are personas now and live in `knights/`.)

## Persona knights and their jobs (decision 13)

| Job chain (`chains/jobs/`) | Persona knight | Step model                      | Caller (unchanged CronJob)          | Was the kagent agent |
| -------------------------- | -------------- | ------------------------------- | ----------------------------------- | -------------------- |
| `intel-triage`             | intel-triage   | haiku                           | `security/opencti-feed-sync`, daily | intel-triage         |
| `security-brief`           | galahad        | sonnet                          | vault-jobs `night-shift`            | security-brief       |
| `feeds-digest`             | kay            | knight default (kagent: sonnet) | vault-jobs `night-shift`            | feeds-digest         |
| `night-editor`             | kay            | knight default (kagent: opus)   | vault-jobs `night-shift`            | night-editor         |
| `nightwatch`               | tristan        | knight default (kagent: local)  | vault-jobs `nightwatch`             | nightwatch           |
| `reading-processor`        | librarian      | haiku                           | vault-jobs `reading-process`        | reading-processor    |
| `link-suggester`           | librarian      | haiku                           | vault-jobs `link-suggester`         | link-suggester       |
| `blog-scout`               | librarian      | sonnet                          | vault-jobs `blog-scout`             | blog-scout           |
| `blog-drafter`             | librarian      | opus                            | vault-jobs `blog-drafter`           | blog-drafter         |
| `voice-processor`          | librarian      | sonnet                          | vault-jobs `voice-inbox`            | voice-processor      |

Retired, not ported: `flux-ops`, `k8s-reader` (tristan covers them), `claude`, `feeds-curator` (kay covers them, asked
through the gateway MCP endpoint or dashboard chat), `voice-librarian` (unused fallback).

How a job chain is built: one step, `knightRef` = the persona, `model` = the job's model where the knight's runtime
allows it, `task` = the kagent AgentTemplate `systemPrompt` verbatim, then `{{ .Input }}` for the caller's request.
No `schedule`: the caller starts the run. Persona knights keep only who they are and their limits in `spec.prompt`.

Grouping rule: jobs share a persona only when they need the same trust level. That is why the five vault jobs are on
`librarian` (read-only vault, no shell, no web) and not on patsy (vault write + cluster read), and why `intel-triage`
(no tools at all) is not on kay.

Still to do in each job chain before applying (marked `PORT BEFORE APPLY` in the file headers): the kagent prompts name
kagent MCP tools (`miniflux` get_*, `cve_lookup`, `web-fetch`, `k8s_get_resources`, vault `search_notes`...). On Round
Table those are CLI skills, the `/vault` mount or MCP servers (#211). The prompts are kept verbatim so the diff is
reviewable; rewrite the tool paragraphs when the tool choice in #214 is made.

Models: kay and tristan are pi-knights on OpenRouter models, so a Claude model on their steps would fail (a step
`model` must suit the knight's runtime). Either leave the knight default, set an OpenRouter model, or move the persona
to claude-knight (#378 decision 1).

### What the callers need from the gateway API (not built yet)

The callers (seven vault-jobs CronJobs, the OpenCTI feed-sync) run a chain and wait for its output:

1. a "run this chain and wait for the result" call (the gateway only invokes single knights today);
2. synchronous waits longer than 10 minutes (callers wait up to 1500 s; `gateway.maxTimeout` is 10m), or a
   documented poll on HTTP 202;
3. chain input passed per run through the API (today `spec.input` is static on the Chain);
4. runs that queue instead of coalescing: a Chain runs one run at a time and a second run-trigger annotation
   while one is in flight only keeps the last value. The issue-pickup controller works around this by creating a
   Chain per run (`pr-pipeline-<repo>-<n>`); the API may do the same from a job chain used as a template;
5. a usage-limited signal on the run result (#355) so a job waits for its next run instead of failing.
   These belong to the gateway front-door work (see #214 for the issue numbers).

## Isolation blocks (decision 8)

Every knight draft carries this, commented out, just before `nats:`:

```yaml
# runtimeClassName: gvisor          # field from #164 (PR #383); RuntimeClass from #212
# egress:                           # field from #348; table default from #349
#   allowedHosts: [...]             # placeholder list, one comment per host saying why
#   allowedPorts: [443]
```

Both fields are missing from the CRD on `main` (checked 2026-11-24 at 76fb408), so they cannot be set yet; a strict
dry run would reject them. Order before any of these knights is applied (decision 8): #164/#383 → #212 → #347–#349
→ the defaults turned on in the chart → uncomment the blocks. Only the tool-less `intel-triage` may go first.

Gaps the host lists exposed (passed on to the egress work, #348/#349):

- **Ports per host.** #348 has one `allowedPorts` list for all hosts. In-cluster services listen on 8080
  (SearXNG, Miniflux), 8123 (Home Assistant), 8000 (Paperless), 80 (OpenCTI).
- **Non-hostname destinations.** `kubectl` needs the kube-apiserver (a Cilium `toEntities` rule), `talosctl` the node
  IPs. tristan, patsy and watchman need the first.
- **Open-web readers.** kay, lancelot and galahad read arbitrary pages today ("full internet access" in kay's prompt).
  A hostname list cannot express that; it needs an allowlisted fetch proxy or a fixed site list (#382).
- **Scanners.** galahad's nmap/testssl and agravain's toolset scan arbitrary targets; they need a per-engagement list
  or an ephemeral mission knight (#368).
- **git-sync.** Every knight needs `github.com` for its arsenal until the OCI arsenal (#350) lands.
- **claude-knight.** Needs `api.anthropic.com`; set `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` so it needs nothing else
  (untested).

Not drafted: `coder-1`/`coder-2` (superseded by `rt-coder`; restore only if a coder for non-Round-Table repos is wanted),
the chelonian table (8 `cl-*` knights; needs a model decision, the `infisical-chelonian` store and `chelonian-secret`),
the old `rt-runtime`/`rt-arsenal` knights (today's dev team is rt-lead, rt-operator, rt-ui, rt-coder).

## What the conversion changed (all knights)

- `taskTimeout` -> `taskTimeoutSeconds`, `arsenal.period: "300s"` -> `periodSeconds: 300`, `image: ""` dropped (operator default = pi-knight).
- Both table labels: `ai.roundtable.io/round-table` (current) and `ai.roundtable.io/table` (the shared-workspace mount still reads only the old one).
- Vault writable paths and prompt paths: `Briefings/` -> `Agents/Briefings/`, `Roundtable/` -> `Agents/Roundtable/`, `NightWatch/` -> `Agents/NightWatch/` (the vault was re-organised; see dapper-cluster #5095).
- The ollama-pool env block (`OPENAI_BASE_URL`, `MODEL_CONTEXT_WINDOW`, `MODEL_MAX_TOKENS`) was removed. It only took effect when the model was not in pi-knight's catalog.
- Models are the originals (not a recommendation): deepseek-v3.2 (kay, tristan, bedivere, percival, lancelot, gareth), deepseek-v4-pro (watchman, old galahad), kimi-k2.6:exacto (patsy, gawain, agravain), claude-sonnet-4.6 via OpenRouter (coder-1). Today's galahad runs claude-knight `sonnet`.

## What each piece needs that does not exist yet

| Need                                                                                    | For                               | State today                                                                                                                                                                                |
| --------------------------------------------------------------------------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| RoundTable `personal`                                                                   | everything                        | missing (galahad runs table-less on `fleet_a_tasks`)                                                                                                                                       |
| Secret `roundtable-secret` (OpenRouter key)                                             | all pi-knights                    | exists; `ANTHROPIC_API_KEY` in it is empty now (Infisical key removed)                                                                                                                     |
| PVC `roundtable-vault`, `roundtable-workspace`                                          | all                               | exist and are Bound; the vault PV is molt's Syncthing replica of the vault, live (today's brief is in it)                                                                                  |
| SA `tristan` + 2 ClusterRoleBindings                                                    | tristan                           | exist on main                                                                                                                                                                              |
| SA `watchman` + RBAC (create Missions)                                                  | watchman                          | exist on main                                                                                                                                                                              |
| SA `patsy` + ClusterRoleBinding                                                         | patsy                             | missing: `infra/patsy-rbac.yaml`                                                                                                                                                           |
| ExternalSecrets `bedivere`, `percival`, `agravain`                                      | those knights                     | missing: `infra/*-externalsecret.yaml`. Infisical keys: `MOLT_HOMEASSISTANT_TOKEN` and `SHODAN_API_KEY` are still referenced elsewhere on main; `PAPERLESS_TOKEN` is not (check it exists) |
| `galahad-secret` (OPENCTI token, Shodan), browser sidecar, the 20-tool list             | old galahad's full powers         | not restored; today's galahad is deliberately minimal. Owner decision                                                                                                                      |
| GitHub token for gawain/tristan/watchman                                                | `gh`                              | old shared PAT (`GAWAIN_GITHUB_TOKEN`) is gone. gawain draft uses the dunce-bot token file (roundtable-k8s repos only)                                                                     |
| Personal arsenal skills with old vault paths                                            | all briefing knights              | `dapperdivers/roundtable-arsenal`: 6 skill files still say `/vault/Briefings/`, `/vault/Roundtable/`; fix by hand (knights cannot push there)                                              |
| Org arsenal skills (`project/*`, `watch/*`, `operator/planner.md`) in the current shape | gawain, watchman, planner         | stale: old Mission shape, retired knight names, old vault paths (issues filed in roundtable-k8s/arsenal)                                                                                   |
| `runtimeClassName`, `spec.egress` on Knight                                             | every knight (decision 8)         | not in the CRD yet: #164 (PR #383), #348, #349; gVisor on the cluster: #212                                                                                                                |
| Tools images for each new `tools.nix` list                                              | every knight                      | built on first apply by the operator; untested for the big lists (agravain: 28 packages incl. hashcat, netexec; tristan: 26)                                                               |
| Invoke gateway + run-chain-and-wait API                                                 | `chains/jobs/*`, kagent migration | gateway built, not deployed (#356); chain runs through the API not built (see above)                                                                                                       |
| Chain notifications                                                                     | optional                          | `notify.allowedURLPrefixes: []` on dapper-cluster (molt receiver dropped): chains cannot notify anyone                                                                                     |

## Known platform bugs that touch these drafts

1. (#370) Shared workspace (`/shared`) is mounted only for knights carrying the legacy `ai.roundtable.io/table` label
   (`internal/knight/pod_builder.go` `WithSharedWorkspace`). Drafts carry both labels.
2. (#371) `spec.vault.readOnly: false` (patsy) and `spec.vault.writablePaths: []` (librarian) do not survive the operator's own
   `Update` when it adds the finalizer: both fields are `omitempty` with CRD defaults (`true`, `[Briefings/, Roundtable/]`),
   so they snap back until Flux re-applies. For `librarian` that means two writable sub-mounts (and two stray folders in
   the vault root) for up to one Flux interval. Found by reading the code, not reproduced. Do not apply `librarian` or `patsy` before the fix.
3. Table-level `spec.vault` (and table defaults) are not applied to standing knights (#372); each knight sets its own (drafts do).

## Suggested layout in dapper-cluster

`kubernetes/apps/roundtable/knights/app/` for tables and knights (as today), a restored `chains/` Kustomization
(`chains/ks.yaml` + `chains/app/`, as in `_orig/chains/`) depending on `roundtable-knights`, and the RBAC/ExternalSecret
files in `infrastructure/app/`. The job chains (`chains/jobs/`) can sit in the same `chains/app/`; they have no schedule, so
they do nothing until a caller runs them.
