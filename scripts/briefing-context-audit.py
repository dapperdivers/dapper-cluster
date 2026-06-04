#!/usr/bin/env python3
"""Audit morning-briefing artifacts for stale context and placeholder fiction.

This complements byte/shape checks. A report can be large, fresh, and still
unusable if it contradicts known ground truth or ships placeholder analysis.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date as date_cls
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from morning_briefing_topology import report_specs  # noqa: E402

def default_vault_root() -> Path:
    if os.environ.get("BRIEFING_VAULT"):
        return Path(os.environ["BRIEFING_VAULT"])
    if os.environ.get("VAULT_DIR"):
        return Path(os.environ["VAULT_DIR"]) / "Briefings"
    return Path("/home/node/obsidian-vault/Briefings")


DEFAULT_VAULT = default_vault_root()


@dataclass(frozen=True)
class Rule:
    rule_id: str
    description: str
    pattern: re.Pattern[str]
    severity: str = "error"
    domains: frozenset[str] | None = None
    active_from: date_cls | None = None

    def applies_to(self, *, label: str, target: date_cls) -> bool:
        if self.domains is not None and label not in self.domains:
            return False
        if self.active_from is not None and target < self.active_from:
            return False
        return True


RULES: tuple[Rule, ...] = (
    Rule(
        "emma-date-unknown",
        "Emma's birth date is known; reports must not say it is uncertain or approximate.",
        re.compile(r"Emma.{0,120}(?:exact date needs confirmation|late April/early May|late April|early May)", re.I | re.S),
        active_from=date_cls(2026, 4, 14),
    ),
    Rule(
        "emma-pending-birth",
        "Emma is already born; reports must not frame the birth as pending.",
        re.compile(r"\b(?:baby|Emma).{0,80}\b(?:due date|expected arrival|still pregnant|pregnancy countdown|pre[- ]birth)\b", re.I | re.S),
        active_from=date_cls(2026, 4, 14),
    ),
    Rule(
        "wedding-planning-stale",
        "Derek and Sara are already married; wedding-planning/RSVP language is stale.",
        re.compile(r"\b(?:wedding planning|wedding prep|wedding venue|baby shower RSVP|\bRSVPs?\b)", re.I),
        active_from=date_cls(2026, 2, 6),
    ),
    Rule(
        "security-placeholder-cve",
        "Security reports must not include placeholder or hypothetical CVEs.",
        re.compile(
            r"CVE-202X-XXXX|hypothetical critical vulnerability|replace with actual|placeholder for illustrative purposes|example CVE",
            re.I,
        ),
        domains=frozenset({"Security"}),
    ),
    Rule(
        "assumption-only-security",
        "Security reports must not substitute assumptions for verified posture without making the output explicitly non-authoritative.",
        re.compile(r"based on general knowledge and assumptions|assumptions based|assume the cluster is running", re.I),
        severity="warning",
        domains=frozenset({"Security", "HomeLab"}),
    ),
    Rule(
        "assistant-preamble",
        "Reports should be deliverables, not assistant planning/preamble prose.",
        re.compile(r"\bI will (?:perform|check|review|analyze|investigate|gather)\b|I would be happy to|\bCertainly,?\b", re.I),
        severity="warning",
    ),
    Rule(
        "capability-leakage",
        "Reports should surface unavailable data as findings, not first-person capability leakage.",
        re.compile(r"\b(?:I don't have|I do not have|I cannot|I can't access|limited .* permissions|Forbidden errors)\b", re.I),
        severity="warning",
    ),
)


def parse_date(value: str) -> date_cls:
    try:
        return date_cls.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid date {value!r}; expected YYYY-MM-DD") from exc


def line_col(text: str, index: int) -> tuple[int, int]:
    prefix = text[:index]
    line = prefix.count("\n") + 1
    last_newline = prefix.rfind("\n")
    col = index + 1 if last_newline == -1 else index - last_newline
    return line, col


def preview(text: str, start: int, end: int, *, width: int = 180) -> str:
    half = max(20, width // 2)
    left = max(0, start - half)
    right = min(len(text), end + half)
    snippet = text[left:right].replace("\n", " ")
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:width]


def iter_report_files(vault: Path, target: str) -> Iterable[tuple[str, str, Path]]:
    for spec in report_specs():
        label = spec["label"]
        rel_dir = spec["vault_dir"].split("/", 1)[1]
        yield label, spec["knight"], vault / rel_dir / f"{target}.md"


def audit_file(label: str, knight: str, path: Path, target: date_cls) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    findings: list[dict[str, Any]] = []
    for rule in RULES:
        if not rule.applies_to(label=label, target=target):
            continue
        for match in rule.pattern.finditer(text):
            line, col = line_col(text, match.start())
            findings.append(
                {
                    "severity": rule.severity,
                    "rule": rule.rule_id,
                    "description": rule.description,
                    "label": label,
                    "knight": knight,
                    "file": str(path),
                    "line": line,
                    "column": col,
                    "match": match.group(0)[:140],
                    "preview": preview(text, match.start(), match.end()),
                }
            )
    return findings


def audit(target: str, vault: Path) -> dict[str, Any]:
    target_date = parse_date(target)
    checked = []
    missing = []
    findings: list[dict[str, Any]] = []
    for label, knight, path in iter_report_files(vault, target):
        if path.is_file():
            checked.append({"label": label, "knight": knight, "file": str(path), "bytes": path.stat().st_size})
            findings.extend(audit_file(label, knight, path, target_date))
        else:
            missing.append({"label": label, "knight": knight, "file": str(path)})

    errors = sum(1 for item in findings if item["severity"] == "error")
    warnings = sum(1 for item in findings if item["severity"] == "warning")
    return {
        "date": target,
        "vault": str(vault),
        "checked_count": len(checked),
        "missing_count": len(missing),
        "checked": checked,
        "missing": missing,
        "findings": findings,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "total_findings": len(findings),
            "clean": len(findings) == 0,
        },
    }


def print_text(payload: dict[str, Any]) -> None:
    print(f"🔍 Briefing Content/Context Audit — {payload['date']}")
    print("════════════════════════════════════════════════════════════════")
    print(f"Checked reports: {payload['checked_count']}/7")
    if payload["missing_count"]:
        missing_labels = ", ".join(item["label"] for item in payload["missing"])
        print(f"Missing reports (content audit skipped): {missing_labels}")

    findings = payload["findings"]
    if not findings:
        print("✅ Clean — no stale context, placeholder CVEs, or assistant-preamble leakage detected.")
        return

    summary = payload["summary"]
    print(f"⚠️ Findings: {summary['errors']} error(s), {summary['warnings']} warning(s)")
    print("")
    for item in findings:
        icon = "❌" if item["severity"] == "error" else "⚠️"
        print(
            f"{icon} {item['label']} ({item['knight']}) {item['rule']} "
            f"line {item['line']}: {item['description']}"
        )
        print(f"   {item['preview']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="target date YYYY-MM-DD")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="Briefings vault root (default: %(default)s)")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--fail-on",
        choices=("error", "warning"),
        default="warning",
        help="exit non-zero on errors only, or on warnings too (default: warning)",
    )
    args = parser.parse_args()

    payload = audit(args.date, Path(args.vault))
    if args.json:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print_text(payload)

    summary = payload["summary"]
    if summary["errors"] > 0:
        return 2
    if args.fail_on == "warning" and summary["warnings"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
