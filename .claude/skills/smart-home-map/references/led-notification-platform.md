# Inovelli LED notification platform

The household "annunciator panel": LED bars on Inovelli switches show
household-relevant states. **Infrastructure alerts never light the panel** (EEMUA
overhaul rule). Full design doc: Second Brain vault →
`~/second-brain/Projects/HomeLab/` (Inovelli LED platform).

Live implementation: Node-RED project, **LED Notifications** tab
(`led_notify_tab`). Architecture: **producers → dispatcher → MQTT**.

## Dispatcher contract

All LED-bar writes go through one function node (`LED Dispatcher`, fed by a
`link in` named `led-notify`). Producers send:

```json
{ "id": "washer_done", "action": "set|clear",
  "slot": 1-7 | null,          // null = full bar
  "zone": "kitchen|living|office|master|guest|outdoor|downstairs|house|<switch name>",
  "effect": "pulse|solid|...",
  "color": 0-255,              // hue: 0 red, 21 orange, 42 yellow, 85 green, 170 blue, 195 purple
  "level": 0-100, "duration": "1-60 s | 61-120 min | 255 = until cleared",
  "announce": true,            // announce-then-rest: 10 s full-bar pulse first
  "priority": n }
```

The dispatcher owns: zone → switch-name fan-out (topics
`zigbee2mqtt/<Switch Name>/set`), night-mode dimming (house_mode Night caps level
at 20), the active-notification store (`flow.led_notifications`), and the 10-minute
re-announce tick that replays the full-bar pulse for anything still active.

## Slot allocation

| Slot | Use                        | Color            |
| ---- | -------------------------- | ---------------- |
| 4    | alarm panel / siren states | (alarm producer) |
| 5    | washer done                | blue (170)       |
| 6    | dryer done                 | green (85)       |
| 7    | dishwasher done            | purple (195)     |

Appliance producers watch `input_select.<x>_state`: `Clean` → set (announce +
persistent slot LED at level 100 in the kitchen zone, duration 255), anything else
→ clear.

## Dismissal

Double-press of the **config button on any kitchen switch** (z2m action
`config_double`) resets every appliance select currently at Clean back to Idle;
the producers then emit `clear`. Gates use `api-current-state` — remember out0 =
condition-true.

## Adding a new notification

1. Run the `notification-design` skill — does this deserve an LED? Which severity/channel?
2. Add a producer: watch node → small function mapping state → dispatcher contract
   msg → `link out` to `led-notify`. Never publish to `zigbee2mqtt/*/set` directly.
3. Pick a free slot (1-3 currently unallocated) and a distinct hue.
4. Test with the 🧪 inject nodes on the LED tab before wiring the real trigger.

Workshop/garage switches are on the `zigbee2mqtt-garage` base topic and are NOT in
the dispatcher's ZONES map yet (planned Phase 3, with a z2m broadcast group).
