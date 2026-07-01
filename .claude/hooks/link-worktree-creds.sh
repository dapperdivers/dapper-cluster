#!/usr/bin/env bash
# SessionStart hook: git worktrees only contain tracked files, but the
# Taskfile pins these gitignored credentials to ROOT_DIR (kubeconfig,
# age.key, talosconfig). Symlink them in from the main checkout so
# `task kubernetes:*`, `task talos:*`, and sops decryption work in
# worktree sessions without manual setup.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}"

gitdir="$(git rev-parse --absolute-git-dir 2>/dev/null)" || exit 0
common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || exit 0

# Main checkout (git-dir == common-dir): nothing to link.
[ "$gitdir" = "$common" ] && exit 0

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
exit 0
