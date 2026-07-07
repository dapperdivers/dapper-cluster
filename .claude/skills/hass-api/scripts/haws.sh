#!/usr/bin/env bash
# Home Assistant WebSocket API helper — covers what the REST API (ha.sh) can't:
# entity/device/area/floor registries, Assist exposure, labels, config subsystems.
#
# Reads a JSON ARRAY of command objects (WITHOUT ids) on stdin, runs them
# sequentially, prints one JSON line per command:
#   {"i": <index>, "success": bool, "result": ..., "error": ...}
#
# Like mqtt.sh, it runs inside the node-red pod (ws module + HA token in-pod,
# token never printed). Commands are the standard HA WS API:
#   https://developers.home-assistant.io/docs/api/websocket/
#
# Read-only examples:
#   echo '[{"type":"config/area_registry/list"},{"type":"config/floor_registry/list"}]' | haws.sh
#   echo '[{"type":"config/entity_registry/list"}]'  | haws.sh   # ~4000 entities, pipe to a file
#   echo '[{"type":"config/device_registry/list"}]'  | haws.sh
#   echo '[{"type":"homeassistant/expose_entity/list"}]' | haws.sh   # Assist/voice exposure
#
# Mutations (CHANGE the live registry — batch them deliberately):
#   {"type":"config/area_registry/create","name":"Pantry","floor_id":"main_floor"}
#   {"type":"config/device_registry/update","device_id":"<id>","area_id":"kitchen"}
#   {"type":"config/entity_registry/update","entity_id":"light.x","area_id":"kitchen"}
#   {"type":"config/entity_registry/update","entity_id":"light.x","name":"HA-layer name","aliases":["voice alias"]}
#   {"type":"homeassistant/expose_entity","assistants":["conversation"],"entity_ids":["light.x"],"should_expose":false}
#
# NOTE: an entity-registry "name"/aliases update is the SAFE way to rename for
# voice/TTS — entity_id and MQTT topics are untouched, so Node-RED flows keep
# working. Renaming a Zigbee2MQTT friendly name instead moves BOTH (breaks flows).
set -euo pipefail
export KUBECONFIG="${KUBECONFIG:-$HOME/projects/dapper-cluster/kubeconfig}"

kubectl exec -i -n home-automation deploy/node-red -- node -e '
const fs = require("fs");
const WebSocket = require("/usr/src/node-red/node_modules/ws");
const token = JSON.parse(fs.readFileSync(
  "/data/projects/Turtleassmanor-automations/flows_cred.json"))["4a296574.4626bc"].access_token;

let input = "";
process.stdin.on("data", d => input += d);
process.stdin.on("end", () => {
  const cmds = JSON.parse(input);
  const ws = new WebSocket("ws://home-assistant.home-automation.svc.cluster.local:8123/api/websocket");
  let id = 0, sent = 0;
  const next = () => {
    if (sent >= cmds.length) { ws.close(); process.exit(0); }
    ws.send(JSON.stringify(Object.assign({ id: ++id }, cmds[sent])));
  };
  ws.on("message", raw => {
    const msg = JSON.parse(raw);
    if (msg.type === "auth_required") { ws.send(JSON.stringify({ type: "auth", access_token: token })); return; }
    if (msg.type === "auth_ok") { next(); return; }
    if (msg.type === "auth_invalid") { console.error("auth failed"); process.exit(1); }
    if (msg.type === "result") {
      console.log(JSON.stringify({ i: sent, success: msg.success, result: msg.result, error: msg.error }));
      sent++; next();
    }
  });
  ws.on("error", e => { console.error("ws error: " + e.message); process.exit(1); });
  setTimeout(() => { console.error("timeout"); process.exit(1); }, 120000);
});
'
