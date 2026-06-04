#!/usr/bin/env python3
"""Validate hardened invariants for the morning-briefing Chain manifest.

Exit codes:
  0 = manifest passes all checks
  2 = one or more invariants failed
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except Exception as exc:  # pragma: no cover
    print(f"ERROR: missing PyYAML dependency: {exc}", file=sys.stderr)
    raise SystemExit(2)

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "kubernetes/apps/roundtable/chains/app/morning-briefing.yaml"
EXPECTED_DOMAIN_STEPS = {
    "security_intel": {"knightRef": "galahad", "timeout": 900, "continueOnFailure": True},
    "intel_digest": {"knightRef": "kay", "timeout": 1200, "continueOnFailure": True},
    "infra_status": {"knightRef": "tristan", "timeout": 900, "continueOnFailure": True},
    "home_tasks": {"knightRef": "bedivere", "timeout": 900, "continueOnFailure": True},
    "finance_check": {"knightRef": "percival", "timeout": 900, "continueOnFailure": True},
    "career_update": {"knightRef": "lancelot", "timeout": 900, "continueOnFailure": True},
    "wellness_check": {"knightRef": "gareth", "timeout": 900, "continueOnFailure": True},
}
EXPECTED_SYNTH_DEPS = list(EXPECTED_DOMAIN_STEPS)
EXPECTED_VERIFY_DEPS = EXPECTED_SYNTH_DEPS + ["synthesize"]
REQUIRED_DOMAIN_GUARDRAILS = [
    "Never return an empty response.",
    "OUTPUT CONSTRAINT:",
]
issues: list[str] = []


def add_issue(message: str) -> None:
    if message not in issues:
        issues.append(message)


if not MANIFEST.exists():
    add_issue(f"manifest missing: {MANIFEST.relative_to(REPO)}")
else:
    data = yaml.safe_load(MANIFEST.read_text()) or {}
    spec = data.get("spec", {})
    steps = spec.get("steps", [])
    steps_by_name = {step.get("name"): step for step in steps if step.get("name")}

    if spec.get("timeout") != 2400:
        add_issue(f"top-level timeout must be 2400, got {spec.get('timeout')!r}")
    if spec.get("outputKnight") != "gawain":
        add_issue(f"outputKnight must be 'gawain', got {spec.get('outputKnight')!r}")

    step_names = [step.get("name") for step in steps]
    if "verify_artifacts" not in step_names:
        add_issue("verify_artifacts step is missing")
    elif step_names[-1] != "verify_artifacts":
        add_issue("verify_artifacts must be the final step")

    for name, expected in EXPECTED_DOMAIN_STEPS.items():
        step = steps_by_name.get(name)
        if not step:
            add_issue(f"missing domain step: {name}")
            continue
        for key, value in expected.items():
            if step.get(key) != value:
                add_issue(f"{name}.{key} must be {value!r}, got {step.get(key)!r}")
        task = step.get("task") or ""
        if "Write your full report to /vault/Briefings/" not in task:
            add_issue(f"{name} task missing mandatory vault write instruction")
        if "FILENAME MUST be exactly YYYY-MM-DD.md" not in task:
            add_issue(f"{name} task missing exact-filename guardrail")
        for marker in REQUIRED_DOMAIN_GUARDRAILS:
            if marker not in task:
                add_issue(f"{name} task missing guardrail marker: {marker}")

    synth = steps_by_name.get("synthesize")
    if not synth:
        add_issue("missing synthesize step")
    else:
        if synth.get("knightRef") != "gawain":
            add_issue(f"synthesize.knightRef must be 'gawain', got {synth.get('knightRef')!r}")
        if synth.get("timeout") != 900:
            add_issue(f"synthesize.timeout must be 900, got {synth.get('timeout')!r}")
        if synth.get("dependsOn") != EXPECTED_SYNTH_DEPS:
            add_issue(f"synthesize.dependsOn must be {EXPECTED_SYNTH_DEPS!r}, got {synth.get('dependsOn')!r}")
        if "write" not in (synth.get("task") or ""):
            add_issue("synthesize task must explicitly instruct Gawain to use the write tool")
        if "Your NATS response text should be a SHORT summary" not in (synth.get("task") or ""):
            add_issue("synthesize task missing NATS-summary contract")
        if "Never return an empty response." not in (synth.get("task") or ""):
            add_issue("synthesize task missing non-empty-response guardrail")

    verify = steps_by_name.get("verify_artifacts")
    if not verify:
        add_issue("missing verify_artifacts step")
    else:
        if verify.get("knightRef") != "gawain":
            add_issue(f"verify_artifacts.knightRef must be 'gawain', got {verify.get('knightRef')!r}")
        if verify.get("timeout") != 300:
            add_issue(f"verify_artifacts.timeout must be 300, got {verify.get('timeout')!r}")
        if verify.get("dependsOn") != EXPECTED_VERIFY_DEPS:
            add_issue(f"verify_artifacts.dependsOn must be {EXPECTED_VERIFY_DEPS!r}, got {verify.get('dependsOn')!r}")
        task = verify.get("task") or ""
        if "bash /workspace/scripts/briefing-artifact-audit.sh YYYY-MM-DD" not in task:
            add_issue("verify_artifacts task missing artifact-audit script call")
        if "bash /workspace/scripts/briefing-context-audit.sh YYYY-MM-DD" not in task:
            add_issue("verify_artifacts task missing content/context audit script call")
        if "placeholder CVEs" not in task or "stale Emma/birth facts" not in task:
            add_issue("verify_artifacts task missing content-quality failure contract")
        if "ARTIFACT_AUDIT_OK" not in task:
            add_issue("verify_artifacts task missing explicit healthy success token")

print("🔒 Morning briefing chain audit")
print("═══════════════════════════════")
print(f"manifest: {MANIFEST.relative_to(REPO)}")

if issues:
    print("❌ Problems detected:")
    for issue in issues:
        print(f"  - {issue}")
    raise SystemExit(2)

print("✅ Morning briefing manifest passes hardened guardrails.")
