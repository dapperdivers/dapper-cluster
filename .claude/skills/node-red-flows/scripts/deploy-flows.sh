#!/usr/bin/env bash
# Deploy an edited flows.json to the LIVE Node-RED via the admin API (full deploy).
# Backs up the current flows first. Does NOT git-commit — do that afterwards (see SKILL.md).
#
# Usage: deploy-flows.sh /path/to/flows-edited.json
set -euo pipefail
export KUBECONFIG="${KUBECONFIG:-$HOME/projects/dapper-cluster/kubeconfig}"

FLOWS_FILE="${1:?usage: deploy-flows.sh <flows.json>}"
python3 -c "import json,sys; f=json.load(open(sys.argv[1])); assert isinstance(f,list) and any(n.get('type')=='tab' for n in f), 'not a flows array'" "$FLOWS_FILE"

BACKUP="/tmp/flows-backup-$(date +%Y%m%d-%H%M%S).json"
kubectl exec -n home-automation deploy/node-red -- \
  cat /data/projects/Turtleassmanor-automations/flows.json > "$BACKUP"
echo "backed up current flows -> $BACKUP"

kubectl port-forward -n home-automation deploy/node-red 18800:1880 >/dev/null 2>&1 &
PF=$!
trap 'kill $PF 2>/dev/null' EXIT
for _ in $(seq 1 20); do curl -sf -m 2 http://127.0.0.1:18800/flows >/dev/null 2>&1 && break; sleep 0.5; done

HTTP=$(curl -s -o /tmp/deploy-resp.json -w '%{http_code}' -X POST http://127.0.0.1:18800/flows \
  -H 'Content-Type: application/json' \
  -H 'Node-RED-Deployment-Type: full' \
  --data-binary @"$FLOWS_FILE")
if [ "$HTTP" != "204" ] && [ "$HTTP" != "200" ]; then
  echo "DEPLOY FAILED (HTTP $HTTP):"; cat /tmp/deploy-resp.json; exit 1
fi
echo "deployed OK (HTTP $HTTP). Watch: kubectl logs -n home-automation deploy/node-red --since=2m"
echo "REMEMBER to commit in the project repo (see node-red-flows SKILL.md)."
