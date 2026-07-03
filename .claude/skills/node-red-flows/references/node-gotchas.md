# node-red-contrib-home-assistant-websocket gotchas

Hard-won lessons from the Turtleassmanor-automations project (commit refs are in that
repo, on the pod — `git log` there for context).

## api-current-state as an if-gate

With "If State" set and 2 outputs: **wires[0] fires when the condition is TRUE,
wires[1] when false.** The editor labels can mislead; 14 gates were wired backwards
until commit d4ed0be. When adding a gate, always test both branches with an inject.

Useful pattern (appliance completion):

```
counter fires once -> api-current-state "If State == Running" on input_select.X_state
    out0 (true)  -> set input_select to Clean
    out1 (false) -> nothing (was Idle/Clean already — stale fire, drop it)
```

## server-state-changed "for: N hours" is fragile

The `for` timer restarts on ANY state change of the watched entity, including
unavailable-flaps and attribute-driven re-fires. Long "has been X for hours" logic
silently never fires. Replaced in the laundry flows (commit 1b2b74a) by:

```
inject (repeat 60s) -> api-current-state (read sensor into payload)
  -> function: parseFloat; NaN => return null (skip flap, keep count);
     below-threshold => count++; above => count=0 + re-arm latch;
     count >= N && !fired => fired=true, return msg (fire once)
```

Properties that make this robust: NaN skip (sensor unavailable doesn't reset),
`>=` latch (survives missed polls), re-arm only on genuinely-high power,
`node.status()` so the counter is visible in the editor.

## trigger-state constraint pitfalls

- Every constraint's `propertyValue: new_state.state` compares against the SAME
  watched entity — two constraints on `new_state.state` with different values can
  never both be true. To cross-check ANOTHER entity, set `targetType: entity_id`.
- `comparatorType: "is"` with a number is exact equality — a power reading almost
  never equals exactly 50. Use `<=` / `>=`.
- The old (pre-redesign) washer/dryer completion triggers had both bugs; the
  stale `/data/flows.json` still contains them. Don't resurrect it.

## Context & restarts

- Function-node `context` uses the default in-memory store — pod restart zeroes
  counters and latches. Any latch must be safe to lose (gate on durable HA state).
- Durable state belongs in HA `input_select` helpers, set via
  `input_select.select_option` with `entityId` targeting, `data: {"option": "..."}`.
- `homeassistant.update_entity` does NOT set state — it only asks HA to poll the
  entity. An earlier design misused it as a state-setter; nothing happened.

## Replay on reconnect

`outputInitially: true` (a.k.a. "output on connect") on watch nodes replays the
current state every time Node-RED reconnects to HA — after every deploy, HA
restart, or pod restart. Commit b226955 fixed light/notification spam caused by
this. Only enable it when a replay is genuinely idempotent.

## Editor/JSON trivia

- Disabled node: `"d": true`. Disabled tab: `"disabled": true` on the tab node.
- `z` = owning tab id; `g` = owning group id; nodes without `z` are global config
  nodes (servers, brokers).
- MQTT out with `retain: true` keeps the last state on the broker — remember to
  clear the retained message (publish empty payload) if a topic is decommissioned.
