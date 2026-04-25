#!/usr/bin/env bash
# briefing-artifact-audit.sh — Audit morning briefing source artifacts and current chain output quality.
#
# Usage: briefing-artifact-audit.sh [YYYY-MM-DD]
# Exit codes:
#   0 = all 7 knight reports exist and look complete
#   2 = one or more artifacts are missing / partial / malformed

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DATE="${1:-$(date +%Y-%m-%d)}"
NATS="${NATS_CLI:-/home/node/.local/bin/nats}"
SERVER="${NATS_URL:-nats://nats.database.svc:4222}"
VAULT="${VAULT_DIR:-/home/node/obsidian-vault}"
INSPECTOR="${SCRIPT_DIR}/briefing-output-inspector.py"

if [ ! -x "$INSPECTOR" ]; then
  echo "ERROR: inspector missing or not executable: $INSPECTOR" >&2
  exit 2
fi

TARGET_DATE="$TARGET_DATE" NATS="$NATS" SERVER="$SERVER" VAULT="$VAULT" INSPECTOR="$INSPECTOR" python3 <<'PY'
import json, os, subprocess, sys
from datetime import datetime

inspector = os.environ['INSPECTOR']
target_date = os.environ['TARGET_DATE']
nats = os.environ['NATS']
server = os.environ['SERVER']
vault = os.environ['VAULT']
is_today = target_date == datetime.now().strftime('%Y-%m-%d')

specs = [
    ("galahad", "security", "Security", "Briefings/Security", "security_intel"),
    ("kay", "research", "Intel", "Briefings/Intel", "intel_digest"),
    ("tristan", "infra", "HomeLab", "Briefings/HomeLab", "infra_status"),
    ("bedivere", "home", "Home", "Briefings/Home", "home_tasks"),
    ("percival", "finance", "Finance", "Briefings/Finance", "finance_check"),
    ("lancelot", "career", "Career", "Briefings/Career", "career_update"),
    ("gareth", "wellness", "Wellness", "Briefings/Wellness", "wellness_check"),
]

issues = []
rows = []
complete = 0


def parse_duration_ms(duration):
    if not duration or not isinstance(duration, str):
        return 0
    duration = duration.strip()
    if duration.endswith("ms"):
        try:
            return int(float(duration[:-2]))
        except ValueError:
            return 0
    return 0


def load_current_kv(step_name):
    if not is_today:
        return None, 'historical-date'
    key = f'morning-briefing.{step_name}'
    cmd = [nats, 'kv', 'get', 'chain-outputs', key, '--server', server, '--raw']
    try:
        raw = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return None, 'missing'
    try:
        return json.loads(raw), 'kv-current'
    except json.JSONDecodeError:
        return None, 'malformed'


for knight, domain, label, report_dir, step_name in specs:
    vault_file = os.path.join(vault, report_dir, f"{target_date}.md")
    vault_exists = os.path.isfile(vault_file)
    vault_bytes = os.path.getsize(vault_file) if vault_exists else 0

    kv_data, kv_state = load_current_kv(step_name)
    nats_exists = kv_data is not None
    nats_success = False
    duration_ms = 0
    result_kind = 'missing'
    preview = ''

    if kv_data is not None:
        nats_success = not bool(kv_data.get('error'))
        duration_ms = parse_duration_ms(kv_data.get('duration', ''))
        result = kv_data.get('output', '')
        if not isinstance(result, str):
            result = json.dumps(result)
        inspected = json.loads(subprocess.check_output([inspector], input=result, text=True))
        preview = inspected.get('preview', result.strip().replace("\n", " ")[:140])
        result_kind = inspected.get('kind', 'unknown')
    elif kv_state == 'historical-date':
        result_kind = 'historical-unavailable'
    elif kv_state == 'malformed':
        result_kind = 'kv-malformed'

    if vault_exists and vault_bytes > 500:
        file_status = 'complete'
        complete += 1
    elif vault_exists:
        file_status = 'partial'
        issues.append(f"{label}: vault file is suspiciously small ({vault_bytes} bytes)")
    else:
        file_status = 'missing'
        issues.append(f"{label}: vault file missing")

    if is_today:
        if not nats_exists:
            if file_status != 'complete':
                issues.append(f"{label}: current chain KV output missing")
        elif not nats_success:
            issues.append(f"{label}: current chain KV output present but error was recorded")
        elif result_kind in {'truncated', 'malformed-json', 'thought-leakage', 'empty', 'kv-malformed', 'json-other', 'json-array', 'action-payload', 'reasoning-payload', 'too-deep', 'unknown'}:
            issues.append(f"{label}: suspicious current chain output ({result_kind})")

    rows.append({
        'label': label,
        'knight': knight,
        'domain': domain,
        'file_status': file_status,
        'vault_bytes': vault_bytes,
        'nats_exists': nats_exists,
        'nats_success': nats_success,
        'nats_source': kv_state,
        'result_kind': result_kind,
        'duration_ms': duration_ms,
        'preview': preview,
    })

print(f"🧪 Briefing Artifact Audit — {target_date}")
print("════════════════════════════════════════════════════════════════")
for row in rows:
    file_icon = {'complete':'✅', 'partial':'⚠️ ', 'missing':'❌'}[row['file_status']]
    if row['nats_source'] == 'historical-date':
        nats_icon = 'ℹ️ '
    elif row['nats_exists'] and row['nats_success'] and row['result_kind'] not in {'plain-text', 'bullet-summary', 'contract-json'}:
        nats_icon = '⚠️ '
    else:
        nats_icon = '✅' if row['nats_exists'] and row['nats_success'] else ('⚠️ ' if row['nats_exists'] else '❌')
    print(f"{file_icon} {row['label']:<10} file={row['file_status']:<8} {row['vault_bytes']:>6}B | {nats_icon} chain={row['result_kind']:<20} {row['duration_ms']:>6}ms | {row['preview']}")

print('')
print(f"📊 Complete reports: {complete}/7")
if not is_today:
    print("ℹ️ Current chain KV audit is only available for today's run. Historical dates are vault-only.")
if issues:
    print('⚠️ Findings:')
    deduped = []
    for item in issues:
        if item not in deduped:
            deduped.append(item)
    for item in deduped:
        print(f"  - {item}")
    sys.exit(2)

print('✅ All morning-briefing source artifacts are present and look healthy.')
PY
