---
name: node-red-flows
description: Read, analyze, edit, and deploy Node-RED automation flows for the smart home. Use when checking on an automation, debugging why a flow didn't fire, adding/modifying flows, or answering "what does Node-RED do when X". The flows are NOT in this repo — they live in the Node-RED pod's git project.
allowed-tools: Bash, Read, Grep, Glob
---

# Node-RED Flows

Node-RED (`home-automation` namespace) holds most of the smart-home automation logic.
It runs in **projects mode** — this is the #1 trap:

> **The live flows file is `/data/projects/Turtleassmanor-automations/flows.json`.**
> `/data/flows.json` also exists but is a STALE pre-projects leftover. Never read or edit it.

The project is a git repo (`git@github.com:DapperDivers/Turtleassmanor-automations.git`),
but **the pod cannot push** (no SSH key) — history lives on the PVC, protected by hourly
VolSync backups (`node-red` ReplicationSource) plus daily R2 offsite.

## Fast start

```bash
# Pull the live flows to a scratch file
./.claude/skills/node-red-flows/scripts/fetch-flows.sh > /tmp/flows-live.json

# Explore: tabs → nodes on a tab → one node's full config + wiring
./.claude/skills/node-red-flows/scripts/flowdump.py /tmp/flows-live.json
./.claude/skills/node-red-flows/scripts/flowdump.py /tmp/flows-live.json --tab Appliances
./.claude/skills/node-red-flows/scripts/flowdump.py /tmp/flows-live.json --grep washer
./.claude/skills/node-red-flows/scripts/flowdump.py /tmp/flows-live.json --node <node-id>
```

`flowdump.py --node` shows a node's full JSON plus **incoming and outgoing wires by
name** — use it to trace trigger → gate → action chains without hand-parsing JSON.

## Checking recent work / history

The project repo's git log is the change history for all automations:

```bash
kubectl exec -n home-automation deploy/node-red -- \
  sh -c 'cd /data/projects/Turtleassmanor-automations && git log --oneline -15'
```

## Runtime checks

```bash
kubectl logs -n home-automation deploy/node-red --since=2h   # HA/MQTT connects, call-service errors
```

A healthy log shows `Connected to https://hass.chelonianlabs.com` and
`Connected to broker: mqtt://emqx-listeners.database.svc.cluster.local`.
To verify the Home Assistant entities a flow reads/writes, use the `hass-api` skill.

## Editing and deploying

Preferred for anything non-trivial: the editor at <https://node-red.chelonianlabs.com>
(user does it interactively). For programmatic changes, the admin API has **no auth
in-cluster** (adminAuth commented out in settings.js):

```bash
./.claude/skills/node-red-flows/scripts/deploy-flows.sh /tmp/flows-edited.json
```

The script backs up the current flows, POSTs a **full deploy** via the admin API
(port-forward to 1880), and reminds you to commit. Deploys write the project
`flows.json` on the PVC but do NOT git-commit; commit afterwards:

```bash
kubectl exec -n home-automation deploy/node-red -- sh -c \
  'cd /data/projects/Turtleassmanor-automations && git add flows.json && git commit -m "<msg>"'
```

Always run the notification-design skill first if the change adds/modifies anything
that notifies (push, TTS, LED bar).

## Known gotchas (hard-won — read before editing)

See [references/node-gotchas.md](references/node-gotchas.md) for the full list with
examples. Headlines:

- **`api-current-state` gate outputs**: output 1 (wires[0]) = condition TRUE,
  output 2 = false. 14 gates were once wired backwards (commit d4ed0be).
- **`server-state-changed` with "for X hours" is fragile** — any state flap resets the
  timer silently. The laundry flows replaced it with a 1-minute poll + counter
  function (commit 1b2b74a). Prefer that pattern for "low for N minutes" logic.
- **Function-node `context` is in-memory** (`contextStorage` default) — counters and
  latches reset on pod restart. Design so a reset is safe (gate on an
  `input_select` state, as the appliance flows do).
- **Disabled nodes** have `"d": true`. A trigger wired to an enabled action does
  nothing if the trigger itself is disabled — check both ends.
- **`outputInitially: true` on trigger/watch nodes replays on every reconnect** —
  caused light/notification spam on each restart (commit b226955). Leave it false.
- **Durable appliance state lives in HA `input_select` helpers**
  (`input_select.washer_state` etc.), not in Node-RED context — see the
  smart-home-map skill for the architecture.

Config-node IDs (referenced by most nodes): HA server = `4a296574.4626bc`,
MQTT broker (EMQX) = `329c148fa7c93659`. Credentials for both are in the project's
`flows_cred.json` on the pod (plaintext — "Using unencrypted credentials" in log).
Never copy credential VALUES into this repo.
