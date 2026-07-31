#!/usr/bin/env bash
# SessionStart hook: make a checkout usable by an agent session.
#
#  1. Credentials — git worktrees only contain tracked files, but the Taskfile
#     pins these gitignored credentials to ROOT_DIR (kubeconfig, age.key,
#     talosconfig). Symlink them in from the main checkout so `task
#     kubernetes:*`, `task talos:*`, and sops decryption work in worktree
#     sessions without manual setup. Worktrees only.
#
#  2. Tools — Renovate bumps .mise.toml pins continuously and nothing else runs
#     `mise install`, so pinned tools silently go missing until someone trips
#     over it. Installs live in ~/.local/share/mise/installs keyed by
#     tool@version and are shared across worktrees, so this is a fast no-op
#     whenever the current pins already resolve. Runs everywhere, since the
#     main checkout drifts the same way.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}"

link_creds() {
  local gitdir common main_root f

  gitdir="$(git rev-parse --absolute-git-dir 2>/dev/null)" || return 0
  common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || return 0

  # Main checkout (git-dir == common-dir): nothing to link.
  [ "$gitdir" = "$common" ] && return 0

  main_root="$(dirname "$common")"

  for f in \
    kubeconfig \
    age.key \
    kubernetes/bootstrap/talos/clusterconfig/talosconfig; do
    if [ -e "$main_root/$f" ] && [ ! -e "$f" ]; then
      mkdir -p "$(dirname "$f")"
      ln -s "$main_root/$f" "$f"
    fi
  done
}

install_tools() {
  local mise out
  mise="$(command -v mise || true)"
  [ -n "$mise" ] || mise="$HOME/.local/bin/mise"
  [ -x "$mise" ] || return 0

  # Buffer all output: a no-op run still emits `sync hooks:` on stderr from the
  # [hooks].postinstall lefthook call, and SessionStart chatter lands in the
  # session context. Replay it only on failure, and never fail the session over
  # it — the tools are a convenience, not a gate.
  if ! out="$("$mise" install --quiet 2>&1)"; then
    printf 'session-bootstrap: mise install failed; pinned tools may be missing\n%s\n' \
      "$out" >&2
  fi
}

link_creds
install_tools
exit 0
