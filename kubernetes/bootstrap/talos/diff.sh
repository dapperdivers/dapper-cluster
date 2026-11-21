#!/usr/bin/env bash
# Dry-run the rendered config against a node and summarise what would change, without
# printing any value: the diff of a machine config contains CA keys and tokens.
#
#   ./diff.sh <hostname>          summary: apply mode, line counts, changed keys and documents
#   FULL=true ./diff.sh <host>    the raw diff from talosctl (contains secrets; needs a terminal
#                                 you trust, never a log or an agent session)
set -euo pipefail

dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
host="${1:?usage: diff.sh <hostname>}"
ip="$("$dir/nodes.sh" "$host" | cut -d' ' -f2)"

work="$(mktemp -d)"
chmod 700 "$work"
trap 'rm -rf "$work"' EXIT

# talosctl writes the dry-run report (summary and diff) to stderr.
if ! talosctl --nodes "$ip" apply-config --dry-run --file <("$dir/render.sh" "$host") > "$work/out" 2>&1; then
  # A failure message can quote config lines: show only its first line.
  echo "$host ($ip): dry run failed: $(grep -vE '^([+ -]|@@|$)' "$work/out" | head -1 | cut -c1-200)" >&2
  exit 1
fi

if [ "${FULL:-false}" = "true" ]; then
  cat "$work/out"
  exit 0
fi

if grep -q 'No changes' "$work/out"; then
  echo "$host ($ip): no changes"
  exit 0
fi

mode="$(grep -E '^Applied configuration' "$work/out" | head -1 || true)"
added="$(grep -cE '^\+([^+]|$)' "$work/out" || true)"
removed="$(grep -cE '^-([^-]|$)' "$work/out" || true)"
echo "$host ($ip): ${mode:-changes} +$added -$removed lines"

# Changed lines reduced to "<sign><indent><key>:". Values, list items and block text are dropped.
keys() { grep -oE "^\\$1 *[A-Za-z0-9_.\$/-]+:" "$work/out" | sed -E "s/^\\$1//; s/:\$//" | sort -u | tr '\n' ' ' | sed -E 's/ +/ /g'; }
docs() { grep -E "^\\$1kind: [A-Za-z0-9]+\$" "$work/out" | sed -E "s/^\\$1kind: //" | sort | uniq -c | awk '{printf "%s%s ", $2, ($1 > 1 ? "×" $1 : "")}'; }
echo "  documents added:   $(docs +)"
echo "  documents removed: $(docs -)"
echo "  keys added:   $(keys +)"
echo "  keys removed: $(keys -)"
echo "  (values are hidden; FULL=true shows the raw diff, secrets included)"
