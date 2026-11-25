#!/usr/bin/env bash
# Bump Round Table images in this repo to the newest roundtable-k8s main builds.
# Pins: operator image + chart tag and digest (the newest chart version is
# republished on every roundtable main push with appVersion = that SHA, so the
# operator tag is taken from the chart itself and the two always match), pi-knight + dashboard tags in
# the operator HelmRelease, and the claude-knight image in Knight manifests.
# Prints a markdown summary of what changed; exits 0 with no changes if current.
set -euo pipefail

HR=kubernetes/apps/roundtable/operator/app/helmrelease.yaml
OCI=kubernetes/apps/roundtable/operator/app/ocirepository.yaml
KNIGHTS_DIR=kubernetes/apps/roundtable/knights/app
CHART=ghcr.io/roundtable-k8s/charts/roundtable-operator
CUR_CHART_TAG=$(yq '.spec.ref.tag' "$OCI")

# Set the `tag:` on the line right after `repository: <repo>` (keeps the file's
# formatting; yq would drop blank lines).
set_tag() { # <file> <repository> <new tag>
  awk -v repo="$2" -v tag="$3" '
    hit && $1 == "tag:" { sub(/tag: .*/, "tag: " tag); hit = 0 }
    $1 == "repository:" && $2 == repo { hit = 1 }
    { print }' "$1" > "$1.tmp" && mv "$1.tmp" "$1"
}

# Anonymous GHCR manifest digest (public packages). Empty if missing.
ghcr_digest() { # <repo path without ghcr.io/> <tag>
  local tok
  tok=$(curl -fsS "https://ghcr.io/token?scope=repository:$1:pull" | jq -r .token)
  curl -fsSI -H "Authorization: Bearer $tok" \
    -H 'Accept: application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.docker.distribution.manifest.list.v2+json' \
    "https://ghcr.io/v2/$1/manifests/$2" 2>/dev/null | tr -d '\r' | awk -F': ' 'tolower($1)=="docker-content-digest"{print $2}'
}

# Newest main SHA whose push build succeeded AND whose image exists.
latest_built() { # <repo> <workflow name> <image path>
  local sha
  for sha in $(gh run list -R "roundtable-k8s/$1" --branch main --event push --workflow "$2" \
      --status success -L 5 --json headSha --jq '.[].headSha'); do
    if [ -n "$(ghcr_digest "$3" "$sha")" ]; then echo "$sha"; return; fi
  done
}

# Newest released chart version (plain x.y.z tags, highest by version sort).
# Feature PRs bump the chart version, so following only the pinned tag would
# leave the operator on the last build of an old version. Falls back to the
# pinned tag if the registry cannot be listed.
latest_chart_tag() {
  local tok
  tok=$(curl -fsS "https://ghcr.io/token?scope=repository:roundtable-k8s/charts/roundtable-operator:pull" | jq -r .token)
  curl -fsS -H "Authorization: Bearer $tok" \
    "https://ghcr.io/v2/roundtable-k8s/charts/roundtable-operator/tags/list?n=1000" 2>/dev/null \
    | jq -r '.tags[]' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1
}
CHART_TAG=$(latest_chart_tag || true)
CHART_TAG=${CHART_TAG:-$CUR_CHART_TAG}
# Never go backwards.
if [ "$(printf '%s\n%s\n' "$CUR_CHART_TAG" "$CHART_TAG" | sort -V | tail -1)" != "$CHART_TAG" ]; then
  CHART_TAG=$CUR_CHART_TAG
fi

summary=()

# --- operator + chart -------------------------------------------------------
chart_digest=$(ghcr_digest roundtable-k8s/charts/roundtable-operator "$CHART_TAG")
cur_digest=$(yq '.spec.ref.digest' "$OCI")
if [ -n "$chart_digest" ] && [ "$chart_digest" != "$cur_digest" ]; then
  app_sha=$(helm show chart "oci://$CHART" --version "$CHART_TAG" 2>/dev/null | yq '.appVersion')
  if [ -n "$app_sha" ] && [ -n "$(ghcr_digest roundtable-k8s/roundtable "$app_sha")" ]; then
    cur_op=$(yq '.spec.values.image.tag' "$HR")
    sed -i -E "s#^(\s+digest: )sha256:[0-9a-f]{64}#\1$chart_digest#" "$OCI"
    sed -i -E "s#^(\s+tag: )$CUR_CHART_TAG\$#\1$CHART_TAG#" "$OCI"
    set_tag "$HR" ghcr.io/roundtable-k8s/roundtable "$app_sha"
    summary+=("- **operator + chart** \`$CUR_CHART_TAG\` → \`$CHART_TAG\`: [\`${cur_op:0:7}\` → \`${app_sha:0:7}\`](https://github.com/roundtable-k8s/roundtable/compare/$cur_op...$app_sha)")
  fi
fi

# --- pi-knight / dashboard (HelmRelease values) -----------------------------
bump_hr() { # <label> <repo> <workflow> <yq path> [image name, default = repo]
  local new cur img=${5:-$2}
  new=$(latest_built "$2" "$3" "roundtable-k8s/$img")
  cur=$(yq "$4" "$HR")
  if [ -n "$new" ] && [ "$new" != "$cur" ]; then
    set_tag "$HR" "ghcr.io/roundtable-k8s/$img" "$new"
    summary+=("- **$1**: [\`${cur:0:7}\` → \`${new:0:7}\`](https://github.com/roundtable-k8s/$2/compare/$cur...$new)")
  fi
}
# pi-knight and claude-knight build from the roundtable-k8s/knights monorepo
# (workflows named after the image); the image names did not change. The first
# knights SHA is not a descendant of the old repo's, so that one compare link
# is empty.
# HOLD_KNIGHT_IMAGES=true pins the knight runtime images (pi-knight and
# claude-knight) where they are: the operator, chart and dashboard still roll
# out. Set while the runtimes are being restructured in roundtable-k8s/knights
# (shared core, roundtable-k8s/roundtable#437), so a half-migrated runtime never
# reaches the knights that run the factory. Set it back to false to resume, after
# trying the new image on one knight first.
HOLD_KNIGHT_IMAGES=true

if [ "$HOLD_KNIGHT_IMAGES" != true ]; then
  bump_hr pi-knight knights pi-knight '.spec.values.images.piKnight.tag' pi-knight
fi
bump_hr dashboard roundtable-ui 'Build & Push' '.spec.values.images.dashboard.tag'

# --- claude-knight (Knight manifests) ---------------------------------------
new_ck=""
if [ "$HOLD_KNIGHT_IMAGES" != true ]; then
  new_ck=$(latest_built knights claude-knight roundtable-k8s/claude-knight)
fi
if [ -n "$new_ck" ]; then
  changed=()
  for f in $(grep -l 'image: ghcr.io/roundtable-k8s/claude-knight:' "$KNIGHTS_DIR"/*.yaml); do
    cur_ck=$(grep -oE 'claude-knight:[0-9a-f]{40}' "$f" | head -1 | cut -d: -f2)
    if [ "$cur_ck" != "$new_ck" ]; then
      sed -i -E "s#(image: ghcr.io/roundtable-k8s/claude-knight:)[0-9a-f]{40}#\1$new_ck#" "$f"
      changed+=("$(basename "$f" .yaml)"); old_ck=$cur_ck
    fi
  done
  [ ${#changed[@]} -gt 0 ] && summary+=("- **claude-knight** (${changed[*]}): [\`${old_ck:0:7}\` → \`${new_ck:0:7}\`](https://github.com/roundtable-k8s/knights/compare/$old_ck...$new_ck)")
fi

printf '%s\n' "${summary[@]}"
