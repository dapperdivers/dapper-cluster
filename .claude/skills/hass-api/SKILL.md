---
name: hass-api
description: Query and control Home Assistant from the CLI — entity states, service calls, templates, history. Use when verifying what an automation reads/writes, checking whether an entity exists or is stale, firing a test service call, or debugging "why didn't X trigger". Works via the HA REST API with a token borrowed from Node-RED.
allowed-tools: Bash, Read
---

# Home Assistant API

HA runs at <https://hass.chelonianlabs.com> (`home-automation` namespace). Its config
lives on the PVC (VolSync-backed), **not in this repo** — the repo only has the
HelmRelease (`kubernetes/apps/home-automation/home-assistant/`).

## The helper script

`scripts/ha.sh` wraps the REST API and auto-extracts a long-lived token from
Node-RED's project credentials (plaintext on the pod). Export `HASS_TOKEN` to skip
the kubectl round-trip when making several calls.

```bash
HA=./.claude/skills/hass-api/scripts/ha.sh

$HA states washer                 # list entity_ids matching a pattern (+ state)
$HA state sensor.washer_power_minute_average    # one entity, full JSON
$HA template '{{ states("input_select.washer_state") }}'   # evaluate a Jinja template
$HA services notify               # what services exist in a domain
$HA history sensor.dryer_power_minute_average 6 # last 6h of states
$HA call input_select select_option '{"entity_id":"input_select.washer_state","option":"Idle"}'
```

`call` CHANGES real state in the house — use for deliberate tests only, and prefer
reversible targets (input_selects, notify to your own phone) over lights/locks.

Cache the token for a session:

```bash
export HASS_TOKEN=$($HA token)
```

## Conventions worth knowing

- Appliance state machines: `input_select.{washer,dryer,dishwasher}_state`
  (options `Idle/Running/Clean[/Dirty]`) — owned by Node-RED flows, see the
  smart-home-map skill.
- Power sensing: `sensor.{washer,dryer}_power_minute_average` (smoothed
  statistics sensors over the raw plug power).
- Notifications: `notify.everyone` fans out to all phones; per-device
  `notify.mobile_app_*` also exist. Anything new that notifies must pass the
  notification-design skill first.
- HA version is pinned/rolled back at times (2026.7.0 broke the websocket API that
  Node-RED depends on — PR #3553). Before blaming a flow, check
  `kubectl logs -n home-automation deploy/node-red` for websocket reconnect loops.

## WebSocket API — registries, areas, voice exposure

`scripts/haws.sh` covers what REST can't: entity/device/area/floor registries and
Assist exposure. It pipes a JSON array of WS commands (no ids) through node inside
the node-red pod and prints one JSON result line per command:

```bash
WS=./.claude/skills/hass-api/scripts/haws.sh

echo '[{"type":"config/area_registry/list"},{"type":"config/floor_registry/list"}]' | $WS
echo '[{"type":"config/entity_registry/list"}]' | $WS > /tmp/ents.jsonl   # ~4000 entities
echo '[{"type":"homeassistant/expose_entity/list"}]' | $WS               # what Assist can hear
echo '[{"type":"config/device_registry/update","device_id":"<id>","area_id":"kitchen"}]' | $WS
```

Conventions learned the hard way (2026-07 voice-naming pass):

- **Rename for voice at the HA layer** (`config/entity_registry/update` with
  `name:`/`aliases:`) — entity_id and MQTT topics stay put, Node-RED keeps working.
  Renaming a Zigbee2MQTT friendly name moves both and silently breaks flows.
- Prefer `device_registry/update` for areas (entities inherit); use entity-level
  `area_id` only for helper groups with no device.
- Zigbee2MQTT **groups** show up as underscore-named devices (`Living_Room_Sides`)
  whose entity_ids collided with same-named switches → `light.living_room_sides_2`
  IS the group, not a stale duplicate. Voice-expose the group, not the smart-bulb-mode
  switch.
- Exposure gotcha: everything defaulted to exposed — including
  `switch.zigbee2mqtt_bridge_permit_join` (unexposed 2026-07-02; keep it that way).

## Raw API (when the scripts don't cover it)

```bash
curl -s -H "Authorization: Bearer $HASS_TOKEN" https://hass.chelonianlabs.com/api/states | jq length
# Docs: https://developers.home-assistant.io/docs/api/rest/
#       https://developers.home-assistant.io/docs/api/websocket/
```
