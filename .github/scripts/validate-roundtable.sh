#!/usr/bin/env bash
# Validate the Round Table custom resources in this repo against the CRDs of
# the chart Flux actually deploys (the OCIRepository's pinned digest), so a
# manifest using old or invalid fields fails in CI instead of at apply time
# (roundtable-k8s/roundtable#254). Autodeploy PRs bump that digest, so they are
# checked against the new CRDs.
#
# Needs: helm, yq (mikefarah), kubeconform, python3. Run from anywhere in the repo.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
oci="$root/kubernetes/apps/roundtable/operator/app/ocirepository.yaml"
fixtures="$root/.github/tests/roundtable"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

url="$(yq '.spec.url' "$oci")"
tag="$(yq '.spec.ref.tag' "$oci")"
digest="$(yq '.spec.ref.digest' "$oci")"
echo "Chart: $url:$tag@$digest"
# By digest only: with tag@digest Helm compares the chart blob digest, but
# Flux pins the manifest digest.
helm pull "$url@$digest" --untar --untardir "$tmp/chart" >/dev/null

# CRD -> one JSON schema per served version, at <group>/<kind>_<version>.json.
# Objects with declared properties get additionalProperties: false (unless
# they preserve unknown fields) so -strict rejects removed or misspelled fields.
mkdir -p "$tmp/crds" "$tmp/schemas"
for crd in "$tmp"/chart/*/crds/*.yaml; do
  yq -o=json '.' "$crd" > "$tmp/crds/$(basename "$crd" .yaml).json"
done
python3 - "$tmp/crds" "$tmp/schemas" <<'PY'
import json, os, sys

src, out = sys.argv[1], sys.argv[2]

def strict(node):
    if isinstance(node, dict):
        if (node.get("type") == "object" and "properties" in node
                and "additionalProperties" not in node
                and not node.get("x-kubernetes-preserve-unknown-fields")):
            node["additionalProperties"] = False
        for v in node.values():
            strict(v)
    elif isinstance(node, list):
        for v in node:
            strict(v)

for name in sorted(os.listdir(src)):
    crd = json.load(open(os.path.join(src, name)))
    group = crd["spec"]["group"]
    kind = crd["spec"]["names"]["kind"].lower()
    for v in crd["spec"]["versions"]:
        schema = v["schema"]["openAPIV3Schema"]
        strict(schema)
        # apiVersion/kind/metadata are validated by the API server, not the CRD.
        schema.setdefault("properties", {})
        for f in ("apiVersion", "kind"):
            schema["properties"].setdefault(f, {"type": "string"})
        schema["properties"]["metadata"] = {"type": "object"}
        os.makedirs(os.path.join(out, group), exist_ok=True)
        path = os.path.join(out, group, f"{kind}_{v['name']}.json")
        json.dump(schema, open(path, "w"))
        print("schema:", os.path.relpath(path, out))
PY

kc() {
  kubeconform -strict -summary -ignore-missing-schemas \
    -schema-location default \
    -schema-location "$tmp/schemas/{{ .Group }}/{{ .ResourceKind }}_{{ .ResourceAPIVersion }}.json" \
    "$@"
}

mapfile -t files < <(grep -rl --include='*.yaml' '^apiVersion: ai\.roundtable\.io/' "$root/kubernetes" | sort)
if [ "${#files[@]}" -eq 0 ]; then
  echo "No Round Table resources found under kubernetes/." >&2
  exit 1
fi
echo "Validating ${#files[@]} files:"
printf '  %s\n' "${files[@]#"$root/"}"
kc "${files[@]}"

# Negative test: an old-shape manifest must fail, or the schemas aren't wired up.
for f in "$fixtures"/invalid-*.yaml; do
  if kc "$f"; then
    echo "Negative test failed: ${f#"$root/"} validated but must not." >&2
    exit 1
  fi
  echo "Negative test ok: ${f#"$root/"} rejected."
done
