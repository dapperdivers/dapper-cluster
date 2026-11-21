#!/usr/bin/env bash
# List the nodes defined under nodes/<role>/<hostname>.yaml, one per line:
#   <hostname> <ip> <role> <install-image>
# The IP is the first address on link ethSel0 (the management network).
#
#   ./nodes.sh              all nodes
#   ./nodes.sh <ip|host>    just that node (exit 1 if unknown)
set -euo pipefail
dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TALOS_VERSION="$(yq -e '.talosVersion' "$dir/versions.yaml")"
export TALOS_VERSION
found=0
for f in "$dir"/nodes/*/*.yaml; do
  host="$(basename "$f" .yaml)"
  role="$(basename "$(dirname "$f")")"
  ip="$(yq -e 'select(.kind == "LinkConfig" and .name == "ethSel0") | .addresses[0].address' "$f" | cut -d/ -f1)"
  image="$(yq -e 'select(document_index == 0) | .machine.install.image' "$f" | envsubst '${TALOS_VERSION}')"
  if [ $# -eq 0 ] || [ "$1" = "$ip" ] || [ "$1" = "$host" ]; then
    echo "$host $ip $role $image"
    found=1
  fi
done
[ "$found" -eq 1 ] || { echo "nodes.sh: no node matches '${1:-}'" >&2; exit 1; }
