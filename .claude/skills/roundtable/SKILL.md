---
name: roundtable
description: Work on the Round Table agent fleet's cluster config (roundtable namespace) — bump the operator chart/image, add or retune a Knight, edit a Chain, fix fleet RBAC/secrets. Use for "bump roundtable", "operator <sha> + chart 0.x.y", knight/chain changes, or fleet resources not reconciling. Development of the operator, chart, and knight images happens in ~/projects/roundtable, NOT here.
allowed-tools: Read, Edit, Write, Bash, Grep, Glob
---

# Round Table fleet (cluster side)

This repo only **deploys** the fleet. The operator code, Helm chart, knight/dashboard
images, and arsenal skills live in `~/projects/roundtable` (chart + images publish to
`ghcr.io/dapperdivers/roundtable*`). If the task is "fix the operator's behavior",
that's the other repo; this skill covers wiring it into the cluster.

## Layout (`kubernetes/apps/roundtable/`)

| Dir               | Holds                                                                                                                      |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `operator/`       | `roundtable-operator` HelmRelease (chart + operator image pin), nix store/buildqueue PVCs, dashboard HTTPRoute             |
| `knights/`        | `Knight` CRs (one per agent) + per-knight secrets, and the `RoundTable` CRs (`personal`, `roundtable-dev`) that group them |
| `chains/`         | `Chain` CRs — scheduled multi-knight workflows (morning-briefing, night-watch, fleet-self-improvement)                     |
| `chelonian/`      | The chelonian dev-team table (`cl-*` knights)                                                                              |
| `infrastructure/` | RBAC, `roundtable-secret`, shared-workspace/vault PVCs, LimitRange, Prometheus monitors + rules                            |
| `agent-sandbox/`  | Sandbox GitRepository + controller                                                                                         |

All CRs are `ai.roundtable.io/v1alpha1`. CRDs come from the chart
(`install/upgrade.crds: CreateReplace` on the HelmRelease).

## The routine job: bump operator chart + image

The most common roundtable commit. In `operator/app/helmrelease.yaml`, **two pins move
together**:

- `spec.chart.spec.version` — chart version (HelmRepository: `kubernetes/flux/meta/repositories/helm/roundtable.yaml`)
- `spec.values.image.tag` — operator image, pinned to the **full git SHA** from the
  roundtable repo (`git -C ~/projects/roundtable log -1 --format=%H` once CI has published it)

Commit style (see `git log --oneline -- kubernetes/apps/roundtable`):
`fix(roundtable): chart 0.14.4 — session history/replay` or
`fix(roundtable): operator <short-sha> + chart 0.x.y — <what>`.

piKnight and dashboard image tags are pinned **inside the chart's values.yaml** (since
chart 0.12.3) — bump those in the roundtable repo, not here.

Verify after merge/reconcile:

```bash
flux reconcile kustomization roundtable-operator -n flux-system
kubectl -n roundtable get pods
kubectl -n roundtable get knights,chains   # READY/last-run columns
```

## Knights and Chains

- A `Knight` pins its `domain`, `model`, `skills`, nix `tools`, and NATS subjects. The
  `ai.roundtable.io/table` label + NATS subject prefix must match its table — **chains
  cannot span tables** (step subjects use the chain's table prefix), so every `knightRef`
  in a Chain must live on that Chain's `roundTableRef` table.
- Chain kill switch: `spec.suspended: true` (patchable live for an emergency stop).
- Knight env secrets: per-knight `*-secret.yaml` in `knights/app/` plus the shared
  `roundtable-secret` (infrastructure/) referenced by the `RoundTable` CRs.

## Gotchas

- **`notify.allowedURLPrefixes` on the operator HR is the SSRF guard** for completion
  webhooks — anyone who can create a Chain controls `notify.url`. Keep it pinned to
  molt's gateway hook endpoint; don't loosen it to "fix" a webhook.
- **The shared workspace PVC persists across missions.** Uncommitted leftovers from a
  previous mission pollute later diffs/verifications — if a knight reports mysterious
  unrelated changes, suspect stale workspace state, not the current mission.
- **A chain that stops progressing may be wedged on cached NATS KV state**, not broken
  config — check the operator logs and the chain's KV entries before rewriting the Chain.
- The `LimitRange` in `infrastructure/` applies to knight pods — a knight OOMKilled or
  refusing to schedule may be hitting it rather than its own resources block.
