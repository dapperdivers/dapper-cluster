#!/usr/bin/env bash
# Render a HelmRelease's values with its chart, so the chart's values schema checks them.
#
# `kustomize build` and flate never hand the values to the chart's schema, so a value the
# schema rejects only shows up when helm-controller tries the upgrade in the cluster. This
# does what helm-controller does first: `helm template` with the same chart and version.
#
# The chart comes from the OCIRepository the HelmRelease's chartRef names: one beside the
# HelmRelease, or a shared one under kubernetes/flux/components/common/repos. Flux
# ${VAR} substitutions stay as plain strings. `valuesFrom` is not followed.
#
# Usage: scripts/helm-values-check.sh <helmrelease.yaml>...
# Needs: helm, yq (mikefarah). Pulls public charts only; needs no cluster and no secrets.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHARED_REPOS="${ROOT}/kubernetes/flux/components/common/repos"

if [ "$#" -eq 0 ]; then
    echo "usage: $0 <helmrelease.yaml>..." >&2
    exit 2
fi

work="$(mktemp -d)"
trap 'rm -rf "${work}"' EXIT

# Path of the file that defines OCIRepository $1, looking beside the HelmRelease in $2 first.
find_repo() {
    local name="$1" dir="$2" f
    while IFS= read -r f; do
        if [ "$(NAME="${name}" yq 'select(.kind == "OCIRepository" and .metadata.name == strenv(NAME)) | .metadata.name' "${f}" 2>/dev/null | head -n1)" = "${name}" ]; then
            echo "${f}"
            return 0
        fi
    done < <(grep -rlsE '^kind: OCIRepository' "${dir}" "${SHARED_REPOS}" --include='*.yaml' || true)
    return 1
}

failed=0
skipped=0
passed=0
for hr in "$@"; do
    label="${hr#"${ROOT}/"}"
    # explode() resolves YAML anchors first, so the values stand on their own.
    doc="${work}/helmrelease.yaml"
    if ! yq --yaml-fix-merge-anchor-to-spec=true 'explode(.) | select(.kind == "HelmRelease")' "${hr}" > "${doc}" || [ ! -s "${doc}" ]; then
        echo "FAIL ${label}: no HelmRelease found in the file"
        failed=$((failed + 1))
        continue
    fi
    release="$(yq '.spec.releaseName // .metadata.name' "${doc}")"
    kind="$(yq '.spec.chartRef.kind // ""' "${doc}")"
    ref="$(yq '.spec.chartRef.name // ""' "${doc}")"
    if [ "${kind}" != "OCIRepository" ] || [ -z "${ref}" ]; then
        echo "SKIP ${label}: no chartRef to an OCIRepository"
        skipped=$((skipped + 1))
        continue
    fi
    if ! repo="$(find_repo "${ref}" "$(dirname "${hr}")")"; then
        echo "FAIL ${label}: OCIRepository ${ref} not found beside it or in ${SHARED_REPOS#"${ROOT}/"}"
        failed=$((failed + 1))
        continue
    fi
    url="$(NAME="${ref}" yq 'select(.kind == "OCIRepository" and .metadata.name == strenv(NAME)) | .spec.url' "${repo}")"
    tag="$(NAME="${ref}" yq 'select(.kind == "OCIRepository" and .metadata.name == strenv(NAME)) | .spec.ref.tag // ""' "${repo}")"
    if [ -z "${tag}" ]; then
        echo "SKIP ${label}: OCIRepository ${ref} has no spec.ref.tag"
        skipped=$((skipped + 1))
        continue
    fi
    # One pull per chart version, however many HelmReleases use it.
    cache="${work}/charts/$(printf '%s' "${url}:${tag}" | tr -c 'A-Za-z0-9._-' '_')"
    if [ ! -d "${cache}" ]; then
        mkdir -p "${cache}"
        if ! helm pull "${url}" --version "${tag}" --destination "${cache}" > "${work}/pull.log" 2>&1; then
            echo "FAIL ${label}: could not pull ${url}:${tag}"
            sed 's/^/     /' "${work}/pull.log"
            failed=$((failed + 1))
            rmdir "${cache}"
            continue
        fi
    fi
    chart="$(find "${cache}" -name '*.tgz' | head -n1)"
    yq '.spec.values // {}' "${doc}" > "${work}/values.yaml"
    if helm template "${release}" "${chart}" --values "${work}/values.yaml" > /dev/null 2> "${work}/render.log"; then
        echo "ok   ${label} (${url##*/} ${tag})"
        passed=$((passed + 1))
    else
        echo "FAIL ${label} (${url##*/} ${tag})"
        sed 's/^/     /' "${work}/render.log"
        failed=$((failed + 1))
    fi
done

echo "helm-values-check: ${passed} ok, ${failed} failed, ${skipped} skipped"
[ "${failed}" -eq 0 ]
