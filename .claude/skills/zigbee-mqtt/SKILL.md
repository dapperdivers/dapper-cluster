---
name: zigbee-mqtt
description: Inspect and drive the Zigbee/MQTT layer — list Zigbee2MQTT devices, watch live MQTT traffic (button presses, sensor reports), read retained state, publish test payloads (e.g. Inovelli LED effects). Use when debugging "the button press never arrived", finding a device's friendly name/topic, or testing an LED/switch payload without touching Node-RED.
allowed-tools: Bash, Read
---

# Zigbee / MQTT layer

Two Zigbee2MQTT instances (`home-automation` namespace) publish to the EMQX broker
(`emqx-listeners.database.svc.cluster.local:1883`, `database` namespace):

| Instance             | Base topic            | Frontend                                  | Covers                             |
| -------------------- | --------------------- | ----------------------------------------- | ---------------------------------- |
| `zigbee2mqtt`        | `zigbee2mqtt/`        | <https://zigbee.chelonianlabs.com>        | house (Inovelli switches, sensors) |
| `zigbee2mqtt-garage` | `zigbee2mqtt-garage/` | <https://zigbee-garage.chelonianlabs.com> | garage/workshop                    |

There is **no mosquitto client anywhere** — `scripts/mqtt.sh` runs mqtt.js inside
the node-red pod instead (zero install, creds never leave the cluster).

## Usage

```bash
MQ=./.claude/skills/zigbee-mqtt/scripts/mqtt.sh

$MQ devices                        # house z2m: friendly name | vendor/model
$MQ devices garage                 # garage instance
$MQ get 'zigbee2mqtt/Kitchen Sink' # retained state of one device
$MQ sub 'zigbee2mqtt/+/action' 30  # watch button presses for 30 s (press one!)
$MQ sub 'home/#' 15                # app-level topics (appliance states etc.)
$MQ pub 'zigbee2mqtt/Main Office/set' '{"led_effect":{"effect":"pulse","color":195,"level":60,"duration":5}}'
```

`pub` sends real commands to real devices — lights will flash, sirens can sound.
Test on a single office switch first, never a zone. `--retain` publishes retained
(also how you clear a stale retained topic: retained empty payload).

## What lives where on the bus

- `zigbee2mqtt/<Friendly Name>` — retained device state; `.../set` — commands.
- `zigbee2mqtt/<Friendly Name>/action` — button events. Inovelli config button
  double-press = `config_double` (drives LED tap-to-dismiss).
- `zigbee2mqtt/bridge/#` — z2m health/devices/log; `bridge/devices` retained JSON
  is the authoritative device list (what `devices` parses).
- `home/#` — app-level topics for Node-RED publishes. `home/washer` /
  `home/dryer` were the pre-redesign appliance-state topics; currently nothing
  retained there (state moved to HA input_selects).
- Inovelli LED-bar payload reference: [references/inovelli-led-payloads.md](references/inovelli-led-payloads.md).
  All _automated_ LED writes must go through the Node-RED LED Dispatcher
  (smart-home-map skill) — direct `pub` is for testing only.

## Debug checklist: "device event never arrived"

1. `$MQ sub 'zigbee2mqtt/<name>/#' 30` and trigger the device — does z2m see it?
   - No → Zigbee problem: check device availability/LQI in the frontend, or
     `kubectl logs -n home-automation deploy/zigbee2mqtt --since=10m`.
   - Yes → broker fine; check the Node-RED side (`node-red-flows` skill): is the
     watch node's entity/topic exact, is the node disabled, did HA rename the entity?
2. Wrong instance? Garage devices are on `zigbee2mqtt-garage/...` — a house-topic
   subscription never sees them (this also bit the LED platform: garage switches
   aren't in the dispatcher ZONES map yet).
3. z2m → HA entity naming: HA discovers via MQTT discovery; entity ids derive from
   friendly names. After renaming a device, both MQTT topics AND HA entity ids move.
