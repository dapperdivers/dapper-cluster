#!/usr/bin/env bash
# MQTT swiss-army knife for the smart home. No local MQTT client needed:
# runs mqtt.js INSIDE the node-red pod; broker creds are read in-pod and never printed.
#
# Usage:
#   mqtt.sh devices [house|garage]     list Zigbee2MQTT devices (friendly name | vendor model)
#   mqtt.sh get <topic>                print first (retained) message on a topic, then exit
#   mqtt.sh sub <topic-filter> [secs]  stream messages for N seconds (default 10); + and # wildcards ok
#   mqtt.sh pub <topic> <payload> [--retain]   publish (REAL devices react!)
set -euo pipefail
export KUBECONFIG="${KUBECONFIG:-$HOME/projects/dapper-cluster/kubeconfig}"

CMD="${1:?usage: mqtt.sh devices|get|sub|pub ...}"
shift || true

case "$CMD" in
  devices)
    BASE="zigbee2mqtt"; [ "${1:-house}" = "garage" ] && BASE="zigbee2mqtt-garage"
    M_MODE=get M_TOPIC="$BASE/bridge/devices" M_FORMAT=devices M_SECS=10 run=1
    ;;
  get)
    M_MODE=get M_TOPIC="${1:?topic required}" M_FORMAT=raw M_SECS="${2:-10}"
    ;;
  sub)
    M_MODE=sub M_TOPIC="${1:?topic filter required}" M_FORMAT=raw M_SECS="${2:-10}"
    ;;
  pub)
    M_MODE=pub M_TOPIC="${1:?topic required}" M_PAYLOAD="${2:?payload required}" M_RETAIN="${3:-}"
    ;;
  *) echo "unknown command: $CMD" >&2; exit 1 ;;
esac

kubectl exec -i -n home-automation deploy/node-red -- \
  env M_MODE="$M_MODE" M_TOPIC="$M_TOPIC" M_SECS="${M_SECS:-10}" \
      M_FORMAT="${M_FORMAT:-raw}" M_PAYLOAD="${M_PAYLOAD:-}" M_RETAIN="${M_RETAIN:-}" \
  node -e '
const fs = require("fs");
const mqtt = require("/usr/src/node-red/node_modules/mqtt");
const creds = JSON.parse(fs.readFileSync(
  "/data/projects/Turtleassmanor-automations/flows_cred.json"))["329c148fa7c93659"];
const { M_MODE, M_TOPIC, M_SECS, M_FORMAT, M_PAYLOAD, M_RETAIN } = process.env;
const c = mqtt.connect("mqtt://emqx-listeners.database.svc.cluster.local:1883",
  { username: creds.user, password: creds.password, connectTimeout: 8000 });
const die = (code, msg) => { if (msg) console.error(msg); c.end(true, () => process.exit(code)); };
c.on("error", e => die(1, "mqtt error: " + e.message));

c.on("connect", () => {
  if (M_MODE === "pub") {
    c.publish(M_TOPIC, M_PAYLOAD, { qos: 1, retain: M_RETAIN === "--retain" },
      err => err ? die(1, "publish failed: " + err.message)
                 : die(0, `published to ${M_TOPIC}` + (M_RETAIN ? " (retained)" : "")));
    return;
  }
  c.subscribe(M_TOPIC, { qos: 0 }, err => { if (err) die(1, "subscribe failed: " + err.message); });
  setTimeout(() => die(M_MODE === "get" ? 1 : 0, M_MODE === "get" ? "no message within " + M_SECS + "s" : null),
    Number(M_SECS) * 1000);
});

c.on("message", (t, p) => {
  const s = p.toString();
  if (M_FORMAT === "devices") {
    let devs; try { devs = JSON.parse(s); } catch { return die(1, "unparseable bridge/devices"); }
    for (const d of devs) {
      if (d.type === "Coordinator") continue;
      const def = d.definition || {};
      console.log(`${(d.friendly_name || d.ieee_address).padEnd(35)} ${def.vendor || "?"} ${def.model || ""} ${d.disabled ? "DISABLED" : ""}`);
    }
    console.log(`-- ${devs.length - 1} devices --`);
    return die(0);
  }
  console.log(`${new Date().toISOString()} ${t} ${s}`);
  if (M_MODE === "get") die(0);
});
'
