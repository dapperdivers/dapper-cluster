#!/usr/bin/env bash
# Render the full Talos machine config for one node to stdout.
#
#   ./render.sh <hostname>
#
# Layers, in order (later layers strategically merge into earlier ones; lists append):
#   1. `talosctl gen config` base for the node's role, from the SOPS secrets bundle
#   2. patches/controller/*.yaml   (control-plane nodes only)
#   3. patches/global/*.yaml       (every node)
#   4. nodes/<role>/<hostname>.yaml
# Role patches go before global ones to keep list order identical to what talhelper
# produced (e.g. machine.files, kubernetesTalosAPIAccess namespaces).
#
# ${TALOS_VERSION} and ${KUBERNETES_VERSION} in patches are substituted from versions.yaml.
# Output contains cluster secrets: never write it inside the repo.
set -euo pipefail

CLUSTER_NAME="kubernetes"
CLUSTER_ENDPOINT="https://10.100.0.40:6443"

dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
node="${1:?usage: render.sh <hostname>}"

shopt -s nullglob
node_files=("$dir"/nodes/*/"$node".yaml)
if [ "${#node_files[@]}" -ne 1 ]; then
  echo "render.sh: expected exactly one nodes/<role>/$node.yaml, found ${#node_files[@]}" >&2
  exit 1
fi
node_file="${node_files[0]}"
role="$(basename "$(dirname "$node_file")")"
case "$role" in
  controlplane) gen_type=controlplane; role_patches=("$dir"/patches/controller/*.yaml) ;;
  worker) gen_type=worker; role_patches=() ;;
  *) echo "render.sh: unknown role directory nodes/$role" >&2; exit 1 ;;
esac

TALOS_VERSION="$(yq -e '.talosVersion' "$dir/versions.yaml")"
KUBERNETES_VERSION="$(yq -e '.kubernetesVersion' "$dir/versions.yaml")"
CONFIG_CONTRACT="$(yq -e '.configContract' "$dir/versions.yaml")"
export TALOS_VERSION KUBERNETES_VERSION

work="$(mktemp -d)"
chmod 700 "$work"
trap 'rm -rf "$work"' EXIT

sops --decrypt "$dir/talsecret.sops.yaml" > "$work/secrets.yaml"

talosctl gen config "$CLUSTER_NAME" "$CLUSTER_ENDPOINT" \
  --with-secrets "$work/secrets.yaml" \
  --talos-version "$CONFIG_CONTRACT" \
  --kubernetes-version "$KUBERNETES_VERSION" \
  --output-types "$gen_type" \
  --with-docs=false --with-examples=false \
  --output "$work/base.yaml" >/dev/null 2>&1

patch_args=()
i=0
for p in "${role_patches[@]}" "$dir"/patches/global/*.yaml "$node_file"; do
  envsubst '${TALOS_VERSION} ${KUBERNETES_VERSION}' < "$p" > "$work/patch-$i.yaml"
  patch_args+=(--patch "@$work/patch-$i.yaml")
  i=$((i + 1))
done

# No --output: it prints to stdout. (`--output -` writes a file literally named "-".)
talosctl machineconfig patch "$work/base.yaml" "${patch_args[@]}"
