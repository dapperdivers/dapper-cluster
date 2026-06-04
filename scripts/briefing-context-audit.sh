#!/usr/bin/env bash
# briefing-context-audit.sh — Check knight reports for stale/incorrect context.
# Usage: briefing-context-audit.sh [YYYY-MM-DD] [--json] [--fail-on error|warning] [--vault PATH]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ "$#" -eq 0 ]]; then
  set -- "$(date +%Y-%m-%d)"
fi

python3 "$SCRIPT_DIR/briefing-context-audit.py" "$@"
