#!/usr/bin/env bash
# Checks for the obsidian-vault job scripts and HelmRelease. CI runs exactly this
# (.github/workflows/obsidian-vault.yaml); run it before pushing a change to the app:
#
#   scripts/check-obsidian-vault.sh        (or: task kubernetes:check-obsidian-vault)
#
# 1. Unit tests for the scripts' pure functions, plus a smoke test that starts every script
#    the way its CronJob does (`python3 -I`, empty environment, empty vault folder).
# 2. `helm template` of the HelmRelease values with the chart version Flux uses, so the
#    chart's values schema checks them.
#
# Needs: python3, helm, yq. No cluster, no secrets; the only network use is the chart pull.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="${APP_DIR:-${ROOT}/kubernetes/apps/selfhosted/obsidian-vault/app}"

echo "== unit tests and isolated-mode smoke test ($(python3 --version))"
python3 -B -m unittest discover --start-directory "${APP}/tests" --top-level-directory "${APP}/tests"

echo "== chart render"
"${ROOT}/scripts/helm-values-check.sh" "${APP}/helmrelease.yaml"
