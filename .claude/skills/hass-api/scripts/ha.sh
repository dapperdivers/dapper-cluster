#!/usr/bin/env bash
# Home Assistant REST helper for the dapper-cluster smart home.
# Token comes from $HASS_TOKEN if set, else extracted from Node-RED's project creds.
#
# Usage:
#   ha.sh token                        print a usable long-lived token
#   ha.sh states [pattern]             entity_id + state, optionally filtered (grep -iE)
#   ha.sh state <entity_id>            full JSON for one entity
#   ha.sh template '<jinja>'           evaluate a template
#   ha.sh services [domain]            list services (all domains or one)
#   ha.sh history <entity_id> [hours]  state history (default 12h)
#   ha.sh call <domain> <service> '<json-payload>'   fire a service (MUTATES!)
set -euo pipefail
export KUBECONFIG="${KUBECONFIG:-$HOME/projects/dapper-cluster/kubeconfig}"
HASS_URL="${HASS_URL:-https://hass.chelonianlabs.com}"

get_token() {
  if [ -n "${HASS_TOKEN:-}" ]; then echo "$HASS_TOKEN"; return; fi
  kubectl exec -n home-automation deploy/node-red -- \
    cat /data/projects/Turtleassmanor-automations/flows_cred.json |
    python3 -c "import json,sys; print(json.load(sys.stdin)['4a296574.4626bc']['access_token'])"
}

pretty() { python3 -m json.tool 2>/dev/null || cat; }

cmd="${1:?usage: ha.sh token|states|state|template|services|history|call ...}"
shift || true
[ "$cmd" = token ] && { get_token; exit 0; }

TOKEN="$(get_token)"
api() {
  curl -sS -m 20 -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" "$@"
}

case "$cmd" in
  states)
    pattern="${1:-.}"
    api "$HASS_URL/api/states" | python3 -c "
import json, re, sys
pat = re.compile(sys.argv[1], re.I)
for e in json.load(sys.stdin):
    line = f\"{e['entity_id']:55s} {e['state']}\"
    if pat.search(line):
        print(line)
" "$pattern"
    ;;
  state)
    api "$HASS_URL/api/states/${1:?entity_id required}" | pretty
    ;;
  template)
    api -X POST "$HASS_URL/api/template" \
      --data-binary "$(python3 -c 'import json,sys; print(json.dumps({"template": sys.argv[1]}))' "${1:?template required}")"
    echo
    ;;
  services)
    api "$HASS_URL/api/services" | python3 -c "
import json, sys
domain = sys.argv[1] if len(sys.argv) > 1 else None
for d in json.load(sys.stdin):
    if domain and d['domain'] != domain: continue
    for s in sorted(d['services']):
        print(f\"{d['domain']}.{s}\")
" ${1:+"$1"}
    ;;
  history)
    entity="${1:?entity_id required}"; hours="${2:-12}"
    start=$(python3 -c "import datetime as d; print((d.datetime.now(d.timezone.utc)-d.timedelta(hours=$hours)).isoformat())")
    api "$HASS_URL/api/history/period/$start?filter_entity_id=$entity&minimal_response" | python3 -c "
import json, sys
for series in json.load(sys.stdin):
    for p in series:
        print(p.get('last_changed', p.get('lu', '?')), p.get('state', p.get('s')))
"
    ;;
  call)
    domain="${1:?domain}"; service="${2:?service}"; payload="${3:-{\}}"
    echo ">> calling $domain.$service with $payload" >&2
    api -X POST "$HASS_URL/api/services/$domain/$service" --data-binary "$payload" | pretty
    ;;
  *)
    echo "unknown command: $cmd" >&2; exit 1
    ;;
esac
