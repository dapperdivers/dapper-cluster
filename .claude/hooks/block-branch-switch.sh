#!/usr/bin/env bash
# PreToolUse hook (Bash tool): deny git branch switching in the MAIN checkout.
# Concurrent Claude sessions share it, so its HEAD must stay on `main`.
# Worktrees (git-dir != common-dir) are per-session and unrestricted.
set -euo pipefail

input="$(cat)"
cmd="$(jq -r '.tool_input.command // empty' <<<"$input")"
cwd="$(jq -r '.cwd // empty' <<<"$input")"

# Only care about commands that move HEAD.
grep -qE '(^|[;&|]\s*)git\s+(checkout|switch)\b' <<<"$cmd" || exit 0

gitdir="$(git -C "$cwd" rev-parse --absolute-git-dir 2>/dev/null)" || exit 0
common="$(git -C "$cwd" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || exit 0

if [ "$gitdir" = "$common" ]; then
  cat >&2 <<'EOF'
Blocked: `git checkout`/`git switch` in the main dapper-cluster checkout is not
allowed — other Claude sessions share it and it must stay on `main`. Do your
work in a git worktree instead: use the EnterWorktree tool to move this session
into one, or tell the user to launch sessions with plain `claude` inside the
repo (the mise PATH wrapper adds --worktree automatically).
EOF
  exit 2
fi
exit 0
