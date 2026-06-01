#!/usr/bin/env python3
"""Inspect morning-briefing step outputs and classify whether they contain usable content."""

from __future__ import annotations

import json
import re
import sys
from typing import Any, Dict, Tuple

THOUGHT_MARKERS = ("<thinking", "assistant to=", "tool_call", "function_call", "analysis:")
NO_OUTPUT_MARKERS = {"", "[No output from agent]", "[no output from agent]"}
ACTION_KEYS = {"action", "action_input", "tool", "tool_name", "function", "function_call"}
RESULT_KEYS = ("output", "result", "content", "text", "final")
BRIEFING_RE = re.compile(r"^#\s+Daily Briefing\b", re.MULTILINE)
META_RESPONSE_PATTERNS = (
    re.compile(r"\b(?:this|the)\s+(?:task|request|process|analysis|audit)\s+requires\s+(?:access|accessing)\b"),
    re.compile(r"\bi\s+will\s+(?:perform|check|review|analyze|investigate|gather)\b"),
    re.compile(r"\b(?:unable|cannot|can't|do not have|don't have|lack|without)\b.{0,60}\b(?:access|credentials|permission|permissions|tools|context)\b"),
    re.compile(r"\bto\s+complete\s+(?:this|the)\s+(?:task|request|analysis|audit)\b"),
)
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
MONTH_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})"
)
MONTHS = {
    "January": "01", "February": "02", "March": "03", "April": "04", "May": "05", "June": "06",
    "July": "07", "August": "08", "September": "09", "October": "10", "November": "11", "December": "12",
}


def to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def extract_date(text: str) -> str:
    m = DATE_RE.search(text)
    if m:
        return m.group(1)
    m = MONTH_RE.search(text)
    if m:
        return f"{m.group(3)}-{MONTHS[m.group(1)]}-{m.group(2).zfill(2)}"
    return "unknown"


def looks_like_meta_response(text: str) -> bool:
    lowered = text.lower()
    if not lowered:
        return False
    matches = sum(1 for pattern in META_RESPONSE_PATTERNS if pattern.search(lowered))
    if matches >= 2:
        return True
    return bool(
        matches
        and ("requires access" in lowered or "requires accessing" in lowered or "i will " in lowered)
    )


def inspect_text(text: str, *, allow_briefing_markdown: bool = False) -> Tuple[str, Dict[str, Any]]:
    stripped = text.strip()
    lowered = stripped.lower()
    meta: Dict[str, Any] = {
        "preview": stripped.replace("\n", " ")[:200],
        "length": len(stripped),
    }

    if stripped in NO_OUTPUT_MARKERS:
        return "empty", meta
    if "... [truncated" in lowered or "... (truncated)" in lowered:
        return "truncated", meta
    if any(marker in lowered for marker in THOUGHT_MARKERS):
        return "thought-leakage", meta
    if allow_briefing_markdown and BRIEFING_RE.search(stripped):
        meta["briefing_date"] = extract_date(stripped[:400])
        return "briefing-markdown", meta
    if stripped.startswith(("-", "•", "*")):
        return "bullet-summary", meta
    if looks_like_meta_response(stripped):
        return "meta-response", meta
    return "plain-text", meta


def inspect_payload(value: Any, *, allow_briefing_markdown: bool = False, _depth: int = 0) -> Dict[str, Any]:
    if _depth > 4:
        return {"kind": "too-deep", "usable": False, "preview": to_text(value)[:200], "length": len(to_text(value))}

    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                kind, meta = inspect_text(value, allow_briefing_markdown=allow_briefing_markdown)
                effective_kind = "malformed-json" if stripped.startswith("{") else kind
                return {"kind": effective_kind, "usable": effective_kind in {"plain-text", "bullet-summary", "briefing-markdown"}, **meta}
            nested = inspect_payload(parsed, allow_briefing_markdown=allow_briefing_markdown, _depth=_depth + 1)
            nested.setdefault("raw_kind", "json-string")
            return nested
        kind, meta = inspect_text(value, allow_briefing_markdown=allow_briefing_markdown)
        return {"kind": kind, "usable": kind in {"plain-text", "bullet-summary", "briefing-markdown"}, **meta}

    if isinstance(value, list):
        return {
            "kind": "json-array",
            "usable": False,
            "preview": to_text(value)[:200],
            "length": len(to_text(value)),
        }

    if isinstance(value, dict):
        keys = set(value.keys())
        if {"knight", "sections"}.issubset(keys):
            return {
                "kind": "contract-json",
                "usable": True,
                "preview": to_text(value)[:200],
                "length": len(to_text(value)),
            }
        if keys & ACTION_KEYS:
            return {
                "kind": "action-payload",
                "usable": False,
                "preview": to_text(value)[:200],
                "length": len(to_text(value)),
            }
        if "thought" in keys and not any(k in keys for k in RESULT_KEYS):
            return {
                "kind": "reasoning-payload",
                "usable": False,
                "preview": to_text(value)[:200],
                "length": len(to_text(value)),
            }
        for key in RESULT_KEYS:
            if key in value:
                nested = inspect_payload(value[key], allow_briefing_markdown=allow_briefing_markdown, _depth=_depth + 1)
                nested.setdefault("wrapped_by", key)
                return nested
        return {
            "kind": "json-other",
            "usable": False,
            "preview": to_text(value)[:200],
            "length": len(to_text(value)),
        }

    return {
        "kind": "unknown",
        "usable": False,
        "preview": to_text(value)[:200],
        "length": len(to_text(value)),
    }


def main() -> int:
    args = sys.argv[1:]
    allow_briefing_markdown = "--briefing" in args
    paths = [arg for arg in args if not arg.startswith("--")]
    if paths:
        with open(paths[0], "r", encoding="utf-8") as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()
    if not raw:
        print(json.dumps({"kind": "empty", "usable": False, "preview": "", "length": 0}))
        return 0
    result = inspect_payload(raw, allow_briefing_markdown=allow_briefing_markdown)
    if allow_briefing_markdown and result.get("kind") == "briefing-markdown":
        result["briefing_text"] = raw.strip() if BRIEFING_RE.search(raw) else None
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
