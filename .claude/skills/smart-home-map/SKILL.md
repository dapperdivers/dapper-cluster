---
name: smart-home-map
description: Orientation map of the smart-home platform — where each system's config actually lives (mostly NOT in this repo), how the pieces connect (HA, Node-RED, Zigbee2MQTT, EMQX, ESPHome), and the standing architectural patterns (appliance state machines, Inovelli LED notification platform). Read FIRST when starting any smart-home task, before searching this repo.
allowed-tools: Bash, Read, Grep, Glob
---

# Smart-Home Map

This repo (dapper-cluster) only deploys the smart-home apps. **Their behavior lives
in app-managed state on PVCs**, reachable via kubectl — searching the repo for an
automation finds nothing. Start here instead.

## Where things actually live

| System                       | Runs as                                                            | Behavior/config lives in                                                   | How to work with it                                                     |
| ---------------------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Home Assistant               | `home-automation/home-assistant`                                   | `/config` on PVC (UI-managed helpers, dashboards, integrations)            | `hass-api` skill (REST)                                                 |
| Node-RED (most automations)  | `home-automation/node-red`                                         | git project on PVC: `/data/projects/Turtleassmanor-automations/flows.json` | `node-red-flows` skill                                                  |
| Zigbee2MQTT (house + garage) | `home-automation/zigbee2mqtt`, `zigbee2mqtt-garage`                | `/app/data/configuration.yaml` + devices on PVC                            | `zigbee-mqtt` skill; frontends zigbee[-garage].chelonianlabs.com        |
| MQTT broker                  | `database/emqx` (`emqx-listeners.database.svc.cluster.local:1883`) | —                                                                          | `zigbee-mqtt` skill (sub/pub via node-red pod)                          |
| ESPHome devices              | `home-automation/esphome`                                          | device YAMLs on PVC                                                        | kubectl exec / ESPHome dashboard                                        |
| Design docs / intent         | Obsidian vault `~/second-brain/Projects/HomeLab/`                  | markdown (e.g. Inovelli LED platform design)                               | grep the vault before designing                                         |
| Alert philosophy             | this repo + memory                                                 | EEMUA 191 overhaul (issue #3541)                                           | `notification-design` skill — MANDATORY gate for anything that notifies |

Event flow: Zigbee2MQTT / ESPHome / plugs → HA entities → Node-RED (websocket) →
HA service calls + MQTT publishes → notifications (push via `notify.everyone`,
Inovelli LED bars, TTS).

## Standing patterns

Two platform patterns are documented in detail in
[references/appliance-state-machines.md](references/appliance-state-machines.md) and
[references/led-notification-platform.md](references/led-notification-platform.md):

1. **Appliance state machines** — washer/dryer/dishwasher each have a durable
   `input_select.<x>_state` in HA (`Idle/Running/Clean[/Dirty]`), driven by
   Node-RED from smoothed power sensors (poll + consecutive-low-minutes counter,
   gated on `Running`). Completion → `notify.everyone` + LED.
2. **LED notification platform** — Inovelli switch LED bars as the household
   "annunciator panel": producers watch state, a dispatcher owns the LEDs,
   announce-then-rest (full-bar pulse, then per-appliance LED slot until
   tap-to-dismiss). LEDs are the _household_ console — infrastructure alerts never
   light the panel.

## Backups / disaster recovery

All smart-home PVCs have VolSync (hourly on-site + daily R2 offsite):
`home-assistant`, `node-red`, `esphome`, `zigbee2mqtt-config`,
`zigbee2mqtt-garage-config`. Restore: `task volsync:restore APP=<name> NS=home-automation PREVIOUS=<n>`.

⚠️ The Node-RED project repo cannot `git push` from the pod (no SSH key) — its
GitHub remote is ~200 commits stale. VolSync is the real backup. If asked to "back
up the automations", fixing the push (deploy key or HTTPS PAT) is the durable fix.

## First moves for a new smart-home task

```bash
# 1. What automations exist / recent work?
./.claude/skills/node-red-flows/scripts/fetch-flows.sh > /tmp/flows-live.json
./.claude/skills/node-red-flows/scripts/flowdump.py /tmp/flows-live.json
kubectl exec -n home-automation deploy/node-red -- sh -c \
  'cd /data/projects/Turtleassmanor-automations && git log --oneline -10'

# 2. What entities are involved?
./.claude/skills/hass-api/scripts/ha.sh states <keyword>

# 3. Any design intent already written down?
grep -ril "<topic>" ~/second-brain/Projects/HomeLab/
```

If the task adds or changes any notification (push/TTS/LED), run the
`notification-design` skill before building.
