#!/usr/bin/env python3
"""Audit Round Table Chain manifests for script dependencies that are missing from Git.

Checks:
- /workspace/scripts/<name> references inside Chain task blocks resolve to repo scripts/<name>
- referenced helper scripts recursively resolve local SCRIPT_DIR siblings
- shell/python helpers parse cleanly enough for a fast preflight

Exit codes:
  0 = all referenced dependencies exist and passed lightweight validation
  2 = missing dependency or validation failure detected
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except Exception as exc:  # pragma: no cover
    print(f"ERROR: missing PyYAML dependency: {exc}", file=sys.stderr)
    raise SystemExit(2)

REPO = Path(__file__).resolve().parents[1]
CHAINS_DIR = REPO / "kubernetes/apps/roundtable/chains/app"
SCRIPTS_DIR = REPO / "scripts"
WORKSPACE_REF_RE = re.compile(r"/workspace/scripts/([^\s\"']+)")
script_dir_token = re.escape("$") + r"(?:\{SCRIPT_DIR\}|SCRIPT_DIR)"
LOCAL_HELPER_RE = re.compile(rf"(?:{script_dir_token})/([A-Za-z0-9._-]+)")

issues: list[str] = []
checked: set[Path] = set()
script_refs: dict[Path, set[str]] = {}


def add_issue(message: str) -> None:
    if message not in issues:
        issues.append(message)


for manifest in sorted(CHAINS_DIR.rglob("*.yaml")):
    data = yaml.safe_load(manifest.read_text()) or {}
    if data.get("kind") != "Chain":
        continue
    for step in data.get("spec", {}).get("steps", []):
        task = step.get("task") or ""
        refs = sorted(set(WORKSPACE_REF_RE.findall(task)))
        if refs:
            script_refs[manifest] = set(refs)


def validate_file(path: Path, source: str) -> None:
    if path in checked:
        return
    checked.add(path)

    if not path.exists():
        add_issue(f"{source}: missing dependency {path.relative_to(REPO)}")
        return
    if not path.is_file():
        add_issue(f"{source}: dependency is not a file: {path.relative_to(REPO)}")
        return

    suffix = path.suffix
    if suffix == ".sh":
        proc = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
        if proc.returncode != 0:
            add_issue(f"{path.relative_to(REPO)}: bash -n failed: {(proc.stderr or proc.stdout).strip()}")
    elif suffix == ".py":
        try:
            ast.parse(path.read_text(), filename=str(path))
        except SyntaxError as exc:
            add_issue(f"{path.relative_to(REPO)}: python syntax error: {exc}")

    text = path.read_text()
    for helper_name in sorted(set(LOCAL_HELPER_RE.findall(text))):
        helper_path = path.parent / helper_name
        validate_file(helper_path, f"{path.relative_to(REPO)}")


for manifest, refs in sorted(script_refs.items()):
    for ref in sorted(refs):
        validate_file(SCRIPTS_DIR / ref, f"{manifest.relative_to(REPO)}")

print("🔎 Chain workspace dependency audit")
print("══════════════════════════════════")
if not script_refs:
    print("No /workspace/scripts references found in Round Table Chain manifests.")
    raise SystemExit(0)

for manifest, refs in sorted(script_refs.items()):
    joined = ", ".join(sorted(refs))
    print(f"- {manifest.relative_to(REPO)} -> {joined}")

print("")
if issues:
    print("❌ Problems detected:")
    for issue in issues:
        print(f"  - {issue}")
    raise SystemExit(2)

print("✅ All referenced workspace script dependencies exist and passed lightweight validation.")
