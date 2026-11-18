#!/usr/bin/env python3
"""Night Shift: overnight work on the Claude subscription, written to the vault.

Morning brief -> Briefings/Morning/<YYYY-MM-DD>.md
  - one section per "## Heading" in Resources/System/Morning Brief Topics.md (the owner
    edits that note; this job only reads it), each researched by the kagent `claude`
    agent (web search, web-fetch, read-only vault);
  - vault gaps: up to GAPS_PER_NIGHT notes with TODO/TBD/?? markers or a needs-research
    tag (Projects, Research, Reference, Resources; any area when tagged) are researched
    and answered as "ready to paste" suggestions. Notes are never edited;
  - links to the night's NightWatch report and new zettels, when there are any.
Stops at the first usage/rate-limit refusal and says so in the brief.
State (which gap notes were checked when) lives in Briefings/Morning/ledger.json.

Usage: night-shift.py <vault-dir> [--dry-run]
"""
import datetime as dt
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vaultlib as vl  # noqa: E402

VAULT = sys.argv[1] if len(sys.argv) > 1 else "/vault"
AGENT_URL = os.environ.get("CLAUDE_AGENT_URL", "")
TOPICS = os.environ.get("BRIEF_TOPICS_NOTE", "Resources/System/Morning Brief Topics.md")
OUT_DIR = "Briefings/Morning"
LEDGER = f"{OUT_DIR}/ledger.json"
GAPS_PER_NIGHT = int(os.environ.get("GAPS_PER_NIGHT", "3"))
BUDGET_S = int(os.environ.get("BUDGET_MINUTES", "75")) * 60
AUTHOR = "night-shift"
GAP_AREAS = ("Projects", "Research", "Reference", "Resources")
GAP_SKIP = re.compile(r"(^|/)(Archive|Generated|Templates|Briefings|Journal|Inbox|Zettels|NightWatch)(/|$)")
MARKER = re.compile(r"\bTODO\b|\bTBD\b|\?\?")
START = time.monotonic()


class Stop(Exception):
    pass


def ask(prompt, timeout=900):
    if time.monotonic() - START > BUDGET_S:
        raise Stop("time budget used up")
    try:
        return vl.agent_reply(AGENT_URL, prompt, timeout=timeout)
    except vl.AgentLimitError as e:
        raise Stop(f"Claude usage limit reached ({e})")


def topic_sections():
    with open(os.path.join(VAULT, TOPICS), encoding="utf-8") as fh:
        _, body, _ = vl.split_frontmatter(fh.read())
    sections, name, lines = [], None, []
    for line in body.split("\n"):
        if line.startswith("## "):
            if name:
                sections.append((name, "\n".join(lines).strip()))
            name, lines = line[3:].strip(), []
        elif name:
            lines.append(line)
    if name:
        sections.append((name, "\n".join(lines).strip()))
    return [(n, b) for n, b in sections if b]


def brief_section(today, name, instructions):
    return ask(
        f"Today is {today:%A %Y-%m-%d}. Write the \"{name}\" section of my morning brief.\n\n"
        f"My instructions for this section:\n{instructions}\n\n"
        "Use WebSearch and the web-fetch tools for anything current, and the vault tools for my "
        "own context (projects, location, what I run). Keep it quick to read.\n"
        "Format: Markdown bullets only. No heading, no preamble, no closing remarks. At most 6 "
        "top-level bullets, each one or two short lines, most important first; nested bullets only "
        "when essential. Link a source for every news or factual claim. If there is nothing "
        "important, say so in one bullet. Never invent facts.")


def bullets_only(text):
    """Drop any preamble/closing prose around the bullet list ("Checking the forecast...")."""
    lines = text.strip().split("\n")
    first = next((i for i, l in enumerate(lines) if l.lstrip().startswith(("- ", "* "))), None)
    if first is None:
        return text.strip()
    last = max(i for i, l in enumerate(lines) if l.lstrip().startswith(("- ", "* ")) or
               (l.startswith(("  ", "\t")) and l.strip()))
    return "\n".join(lines[first:last + 1]).strip()


def gap_candidates(ledger):
    found = []
    for rel, path in vl.walk(VAULT):
        if not rel.endswith(".md") or GAP_SKIP.search(rel):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        meta = vl.parse_frontmatter(text)
        tags = meta.get("tags") if isinstance(meta.get("tags"), list) else [meta.get("tags", "")]
        tagged = any("needs-research" in str(t) for t in tags)
        if vl.is_true(meta.get("generated")):
            continue
        if tagged or (rel.split("/", 1)[0] in GAP_AREAS and MARKER.search(text)):
            found.append((0 if tagged else 1, ledger.get(rel, ""), rel))
    found.sort()  # tagged first, then never-checked / least recently checked
    return [rel for _, _, rel in found]


def research_gaps(rel):
    raw = ask(
        f"Read the vault note \"{rel}\" with read_note. Find its gaps: places marked TODO, TBD or "
        "??, or facts it is clearly missing, that public sources can answer. Skip personal to-dos "
        "and anything only I can know. Research up to 3 gaps with WebSearch and web-fetch.\n"
        "Reply with only a JSON object: {\"researchable\": true|false, \"items\": [{\"gap\": "
        "\"what was missing, quoting the marker line if there is one\", \"suggestion\": \"Markdown "
        "to paste into the note, written in the note's style\", \"sources\": [\"url\", ...]}]}. "
        "Use researchable=false with no items if nothing in the note can be answered from public "
        "sources. Never invent facts.", timeout=900)
    data = vl.json_from_text(raw)
    items = []
    for it in (data.get("items") or [])[:3]:
        if isinstance(it, dict) and str(it.get("suggestion", "")).strip():
            items.append({"gap": " ".join(str(it.get("gap", "")).split())[:300],
                          "suggestion": str(it["suggestion"]).strip()[:3000],
                          "sources": [str(u) for u in (it.get("sources") or [])[:5] if str(u).startswith("http")]})
    return items


def overnight(today):
    lines = []
    nw = f"NightWatch/{today}.md"
    if os.path.exists(os.path.join(VAULT, nw)):
        lines.append(f"- Cluster: {vl.wikilink(nw, 'Night Watch report')}")
    zdir = os.path.join(VAULT, "Zettels")
    if os.path.isdir(zdir):
        cutoff = time.time() - 86400
        new = sorted(f[:-3] for f in os.listdir(zdir)
                     if f.endswith(".md") and os.path.getmtime(os.path.join(zdir, f)) > cutoff)
        if new:
            lines.append(f"- New zettels ({len(new)}): " + ", ".join(vl.wikilink(f"Zettels/{n}.md", n) for n in new[:8]))
    return lines


def main():
    if not vl.vault_ready(VAULT) or not AGENT_URL:
        return 0
    today = dt.datetime.now(vl.TZ).date()
    try:
        with open(os.path.join(VAULT, LEDGER), encoding="utf-8") as fh:
            ledger = json.load(fh)
    except (OSError, ValueError):
        ledger = {}

    sections, gaps, stopped, problems = [], [], None, []
    try:
        for name, instructions in topic_sections():
            try:
                sections.append((name, bullets_only(brief_section(today, name, instructions))))
                print(f"section {name}: done")
            except Stop:
                raise
            except Exception as e:
                problems.append(f"{name}: {e}")
                print(f"section {name} failed: {e}", file=sys.stderr)
        for rel in gap_candidates(ledger)[:GAPS_PER_NIGHT]:
            ledger[rel] = today.isoformat()
            try:
                items = research_gaps(rel)
                gaps.append((rel, items))
                print(f"gaps {rel}: {len(items)} suggestion(s)")
            except Stop:
                raise
            except Exception as e:
                problems.append(f"{rel}: {e}")
                print(f"gaps {rel} failed: {e}", file=sys.stderr)
    except Stop as e:
        stopped = str(e)
        print(f"stopped early: {stopped}", file=sys.stderr)

    found = sum(len(i) for _, i in gaps)
    desc = (f"Morning brief for {today}: {', '.join(n for n, _ in sections) or 'no sections'}"
            f"{f'; {found} vault gap suggestion(s)' if found else ''}.")
    fm = ["---", f"created: {today}", "type: briefing", "status: complete", "tags:", "  - briefing/morning",
          f"description: {vl.yaml_str(desc)}", "generated: true", f"author: {AUTHOR}", "---", ""]
    b = [f"# Morning Brief: {today:%A %Y-%m-%d}", "",
         f"*Researched overnight by the `claude` agent (Night Shift). Edit what it covers in "
         f"{vl.wikilink(TOPICS, 'Morning Brief Topics')}.*", ""]
    if stopped:
        b += [f"> [!warning] Stopped early: {stopped}. Some sections are missing.", ""]
    for name, text in sections:
        b += [f"## {name}", "", text, ""]
    useful = [(rel, items) for rel, items in gaps if items]
    if useful:
        b += ["## Vault gaps (ready to paste)", ""]
        for rel, items in useful:
            b += [f"### {vl.wikilink(rel)}", ""]
            for it in items:
                b += [f"- **Gap:** {it['gap']}", "", it["suggestion"], ""]
                if it["sources"]:
                    b += ["  Sources: " + ", ".join(f"<{u}>" for u in it["sources"]), ""]
    ov = overnight(today)
    if ov:
        b += ["## Overnight", ""] + ov + [""]
    if problems:
        b += ["## Problems", ""] + [f"- {p[:300]}" for p in problems] + [""]

    text = "\n".join(fm + b)
    out = os.path.join(VAULT, OUT_DIR, f"{today}.md")
    if vl.DRY:
        print(text)
        return 0
    vl.atomic_write(out, text)
    vl.atomic_write(os.path.join(VAULT, LEDGER), json.dumps(ledger, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT_DIR}/{today}.md ({len(sections)} sections, {found} gap suggestions"
          f"{', stopped early' if stopped else ''})")
    vl.request_rescan(VAULT, [OUT_DIR])
    return 0


if __name__ == "__main__":
    sys.exit(main())
