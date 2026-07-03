# Appliance state machines (washer / dryer / dishwasher)

The canonical pattern for "is the appliance done?" logic. Live implementation:
Node-RED project, **Appliances** tab (state machines) + **LED Notifications** tab
(indicators). Verified working 2026-07-02.

## Durable state (Home Assistant)

| Entity                          | Options                     | Notes                                   |
| ------------------------------- | --------------------------- | --------------------------------------- |
| `input_select.washer_state`     | Idle, Running, Clean, Dirty | Dirty currently unused (flows disabled) |
| `input_select.dryer_state`      | Idle, Running, Clean, Dirty |                                         |
| `input_select.dishwasher_state` | Idle, Running, Clean        |                                         |

State lives in HA input_selects (survives Node-RED restarts), never in Node-RED
context. Node-RED writes them only via `input_select.select_option`.

## Inputs

| Sensor                               | Meaning                                       |
| ------------------------------------ | --------------------------------------------- |
| `sensor.washer_power_minute_average` | Emporia Vue circuit CT, W (idle draw ≈ 70 W!) |
| `sensor.dryer_power_minute_average`  | Emporia Vue circuit CT, W (0 when off)        |
| kitchen plugs power (dishwasher)     | third wire of the same 1-min poll             |

⚠️ Ignore `sensor.dryer_inferred_power` — it's a legacy template (whole-house
main panel minus the water heater = house baseload), NOT the dryer. It reads
~800 W with everything off. The automations correctly use the Emporia
`*_power_minute_average` circuit sensors.

## Transitions

**→ Running** (event-driven `trigger-state` on the power sensor):
washer fires at ≥ 200 W, dryer at ≥ 1000 W.

**Running → Clean** (poll + counter, NOT `for:`-timers — those flap-reset silently):

```
inject every 60 s
  → api-current-state (power avg into payload)
  → function counter: NaN → skip; power < threshold → count++; else count=0 + re-arm
      washer: < 120 W for 6 consecutive minutes
      dryer:  < 100 W for 10 consecutive minutes
      fires ONCE at count >= N (latch survives missed polls)
  → api-current-state gate "state == Running?"  (out0 = true!)
      true  → input_select.select_option → Clean
      false → drop (stale fire while Idle/Clean)
```

**Clean → notifications** (`trigger-state` on the input_select == Clean):
`notify.everyone` push + LED producer picks up the state change (see LED platform).

**Clean → Idle**: tap-to-dismiss — double-press the config button on any kitchen
Inovelli switch sweeps all three `*_state` selects that read Clean back to Idle
(which also clears their LEDs).

## Tuning watch-items

- Washer: a soak/fill phase spending > 6 consecutive minutes under 120 W while
  mid-cycle would fire "done" early (gate is on Running, so it WILL pass). If
  premature notifications appear, raise the 6-minute window, not the wattage.
- Dryer: a low-heat/delicates cycle that never reaches 1000 W never gets marked
  Running → no completion notification. If that happens, lower the Running
  threshold (but keep it above the ~70 W-class idle noise).
- Counters live in Node-RED memory context — a deploy/restart mid-cycle restarts
  the countdown (worst case: notification a few minutes late; never wrong-state).
