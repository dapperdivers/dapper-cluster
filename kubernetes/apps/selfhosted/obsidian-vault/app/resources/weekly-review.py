#!/usr/bin/env python3
"""Write the weekly review: Journal/<YYYY>/Weekly/<YYYY>-W<ww> Weekly Review.md

Covers the 7 days ending yesterday (run it Sunday morning -> Sunday..Saturday):
  - Week in brief: a few bullets from the local Ollama model, grounded in the lists below
  - New and edited notes by area (curated notes only), daily notes, voice memos
  - Open to-dos from this week's new notes, daily notes and voice memos; the Inbox backlog
  - Vault Health: counts plus anything new or needing attention since the nightly check
Never overwrites an existing review (once written, the note is the owner's to annotate).

Usage: weekly-review.py <vault-dir> [--dry-run] [--end YYYY-MM-DD]
"""
import datetime as dt
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vaultlib as vl  # noqa: E402

VAULT = sys.argv[1] if len(sys.argv) > 1 else "/vault"
AUTHOR = "vault-review"
HEALTH_REL = os.path.join(vl.GENERATED_DIR, "Vault Health.md")
SKIP = ("Archive/Briefings/", "Agents/Briefings/", vl.GENERATED_DIR + "/")
TASK = re.compile(r"^\s*[-*] \[ \] +(\S.*)$", re.M)

SYSTEM = (
    "You write the 'Week in brief' section of a weekly review of someone's personal knowledge base. "
    "From the activity list, write 3-6 bullets on what they actually worked on or thought about this week, "
    "grouping related notes into themes. Be concrete and factual; only use what's in the list; "
    "no advice, no praise, no filler. Each bullet under 30 words."
)
SCHEMA = {"type": "object", "properties": {"bullets": {"type": "array", "items": {"type": "string"}}},
          "required": ["bullets"]}


def area(rel):
    parts = rel.split("/")
    return "/".join(parts[:2]) if len(parts) > 2 else parts[0] if len(parts) > 1 else "(root)"


def created_on(n):
    try:
        return dt.date.fromisoformat(str(n["fm"].get("created", ""))[:10])
    except ValueError:
        return None


def health_summary():
    try:
        with open(os.path.join(VAULT, HEALTH_REL), encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        return ["*No health report yet.*"]
    fm = vl.parse_frontmatter(text)
    out = [f"From [[{HEALTH_REL[:-3]}|Vault Health]]: **{fm.get('attention', '?')}** need attention, "
           f"**{fm.get('new_issues', '?')}** new issues, {fm.get('issues', '?')} standing, "
           f"{fm.get('fixed', '?')} fixed automatically last night.", ""]
    sec, picked = None, []
    for line in text.split("\n"):
        if line.startswith("## "):
            sec = line[3:].strip()
        elif line.startswith("- ") and (sec == "Needs attention" or "🆕" in line):
            picked.append(line if sec == "Needs attention" else line.replace("- 🆕 ", f"- 🆕 *{sec}:* ", 1))
    out += picked[:25] + ([f"- …and {len(picked) - 25} more"] if len(picked) > 25 else [])
    return out


def main():
    if not vl.vault_ready(VAULT):
        return 0
    if "--end" in sys.argv:
        end = dt.date.fromisoformat(sys.argv[sys.argv.index("--end") + 1])
    else:
        end = dt.datetime.now(vl.TZ).date() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=6)
    iy, iw, _ = end.isocalendar()
    week = f"{iy}-W{iw:02d}"
    rel = f"Journal/{end.year}/Weekly/{week} Weekly Review.md"
    if os.path.exists(os.path.join(VAULT, rel)):
        print(f"{rel} already exists; leaving it alone")
        return 0

    notes = vl.load_notes(VAULT)
    in_week = lambda d: d is not None and start <= d <= end  # noqa: E731
    touched = [n for n in notes if in_week(n["mtime"].date()) and not n["rel"].startswith(SKIP)]
    dailies = sorted((n for n in touched if n["type"] == "daily"), key=lambda n: n["name"])
    voice = sorted((n for n in notes if n["type"] == "voice-note" and in_week(created_on(n))), key=lambda n: n["name"])
    curated = [n for n in touched if not n["generated"] and n["type"] != "daily"]
    new = [n for n in curated if in_week(created_on(n))]
    edited = [n for n in curated if n not in new]

    tasks = []
    for n in new + dailies + voice:  # to-dos that came up this week (old checklists stay out)
        for t in TASK.findall(n["text"]):
            tasks.append(f"- [ ] {t.strip()} — {vl.wikilink(n['rel'], n['name'])}")
    inbox = [n for n in notes if n["rel"].startswith("Inbox/") and n["status"] in ("inbox", "")]

    # Week in brief from the local model, grounded only in this activity list
    activity = [f"NEW {n['rel']}: {n['description']}" for n in new] + \
               [f"EDITED {n['rel']}: {n['description']}" for n in edited[:60]] + \
               [f"VOICE MEMO {n['name']}: {n['description']}" for n in voice] + \
               [f"DAILY NOTE {n['name']}: {vl.split_frontmatter(n['text'])[1][:800]}" for n in dailies]
    brief = []
    if activity:
        try:
            brief = vl.ollama_json(SYSTEM, f"Week {week} ({start} to {end}).\n\n" + "\n".join(activity)[:14000],
                                   SCHEMA)["bullets"]
        except Exception as e:
            print(f"week-in-brief failed: {e}", file=sys.stderr)

    def grouped(items):
        by = defaultdict(list)
        for n in items:
            by[area(n["rel"])].append(n)
        out = []
        for a in sorted(by):
            out.append(f"**{a}**")
            for n in sorted(by[a], key=lambda n: n["mtime"], reverse=True)[:15]:
                out.append(f"- {vl.wikilink(n['rel'], n['name'])}" + (f" — {n['description']}" if n["description"] else ""))
            if len(by[a]) > 15:
                out.append(f"- …and {len(by[a]) - 15} more")
            out.append("")
        return out or ["None.", ""]

    span = f"{start:%b %-d}–{end:%b %-d, %Y}"
    desc = (f"Weekly review for {week} ({span}): {len(new)} new and {len(edited)} edited notes, "
            f"{len(voice)} voice memos, {len(tasks)} new to-dos, plus vault health.")
    out = ["---", f"created: {dt.datetime.now(vl.TZ):%Y-%m-%d}", "type: weekly-review", "status: active",
           "tags:", "  - weekly", "  - meta/generated", f"week: {week}", f"period_start: {start}", f"period_end: {end}",
           f"description: {vl.yaml_str(desc)}", "generated: true", f"author: {AUTHOR}", "---", "",
           f"# Weekly Review — {week}", "",
           f"*{span}. Written by the `{AUTHOR}` CronJob from the vault's files; add your own notes below.*", "",
           "## Week in brief", ""]
    out += [f"- {b.strip()}" for b in brief if b.strip()] or ["*Quiet week: nothing to summarize.*" if not activity
                                                             else "*(summary unavailable this week)*"]
    out += ["", f"## New notes ({len(new)})", "", *grouped(new),
            f"## Edited notes ({len(edited)})", "", *grouped(edited),
            f"## Daily notes ({len(dailies)})", ""]
    out += [f"- {vl.wikilink(n['rel'], n['name'])}" for n in dailies] or ["None."]
    out += ["", f"## Voice memos ({len(voice)})", ""]
    out += [f"- {vl.wikilink(n['rel'], n['name'])} — {n['description']}" for n in voice] or ["None."]
    out += ["", f"## New to-dos ({len(tasks)})", "", *(tasks[:30] or ["None."])]
    if len(tasks) > 30:
        out.append(f"- …and {len(tasks) - 30} more")
    out += ["", f"## Inbox ({len(inbox)})", ""]
    out += [f"{len(inbox)} notes waiting in `Inbox/` to be filed." if inbox else "Inbox is empty."]
    out += ["", "## Vault health", "", *health_summary(), "", "## My notes", "", ""]

    content = "\n".join(out)
    if vl.DRY:
        print(content)
        return 0
    vl.atomic_write(os.path.join(VAULT, rel), content)
    print(f"wrote {rel}: {desc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
