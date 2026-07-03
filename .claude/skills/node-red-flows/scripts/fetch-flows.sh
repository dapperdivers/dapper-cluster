#!/usr/bin/env bash
# Print the LIVE Node-RED flows.json (projects mode) to stdout.
# Usage: fetch-flows.sh [> /tmp/flows-live.json]
set -euo pipefail
export KUBECONFIG="${KUBECONFIG:-$HOME/projects/dapper-cluster/kubeconfig}"
kubectl exec -n home-automation deploy/node-red -- \
  cat /data/projects/Turtleassmanor-automations/flows.json
