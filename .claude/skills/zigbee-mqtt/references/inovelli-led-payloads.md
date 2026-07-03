# Inovelli LED-bar payloads (Zigbee2MQTT `/set`)

Publish to `zigbee2mqtt/<Friendly Name>/set`. Automated writes must route through
the Node-RED LED Dispatcher (single owner of the LED store, night dimming,
re-announce) — raw publishes are for hand testing only and will be stomped by the
next dispatcher write.

## Full-bar effect

```json
{ "led_effect": { "effect": "pulse", "color": 170, "level": 100, "duration": 10 } }
```

## Single LED (bars have 7 LEDs, led "1" = bottom)

```json
{
  "individual_led_effect": {
    "led": "5",
    "effect": "solid",
    "color": 170,
    "level": 100,
    "duration": 255
  }
}
```

## Clearing

```json
{ "led_effect": { "effect": "clear_effect" } }
{ "individual_led_effect": { "led": "5", "effect": "clear_effect" } }
```

## Field reference

- `color`: 0–255 hue — 0 red, 21 orange, 42 yellow, 85 green, 170 blue, 195 purple.
- `level`: 0–100 brightness.
- `duration`: 1–60 = seconds, 61–120 = (value−60) minutes, 255 = indefinite until cleared.
- `effect` (full bar): off, solid, chase, fast_blink, slow_blink, pulse, open_close,
  small_to_big, aurora, slow_falling, medium_falling, fast_falling, slow_rising,
  medium_rising, fast_rising, medium_blink, slow_chase, fast_chase, fast_siren,
  slow_siren, clear_effect.
- `effect` (individual LED): off, solid, fast_blink, slow_blink, pulse, chase,
  aurora, clear_effect.

## Household slot allocation (see smart-home-map skill)

4 = alarm, 5 = washer (blue), 6 = dryer (green), 7 = dishwasher (purple);
1–3 free.

## Button events (`zigbee2mqtt/<name>/action`)

Notable: `config_single`, `config_double` (kitchen double-press = dismiss
appliance LEDs), `up_single|double|triple`, `down_single|double|triple`,
`up_held`, `down_held`.
