#!/usr/bin/env python3
"""Backfill missing `description:` frontmatter with the local Ollama model.

Only curated notes (not generated) that already have frontmatter, enough body text to
describe, and no edits in the last MIN_AGE_HOURS. The original mtime is kept so the
backfill doesn't flood "recently edited". At most MAX_NOTES per run; the rest wait
for the next night. Notes it can't describe are listed by the health check.

Usage: describe.py <vault-dir> [--dry-run]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vaultlib as vl  # noqa: E402

VAULT = sys.argv[1] if len(sys.argv) > 1 else "/vault"
MAX_NOTES = int(os.environ.get("MAX_NOTES", "40"))
MIN_AGE_S = float(os.environ.get("MIN_AGE_HOURS", "6")) * 3600
MIN_BODY = 40  # characters of real text; shorter notes are reported as empty instead
SKIP_FILES = {"CLAUDE.md", "AGENTS.md"}
SKIP_PREFIXES = ("Archive/Briefings/", "Briefings/", "Inbox/")

SYSTEM = (
    "You write the `description` field for notes in a personal knowledge base: one plain sentence "
    "(12-30 words) saying what the note is and why someone would open it. Start with a noun phrase naming "
    "what the note is, never with 'This note'. Be concrete: name the subject, people, place or project. "
    "No markdown or quotes. Examples:\n"
    "- Working reference on heat-pump sizing, with the load calculation and quotes gathered for the new house.\n"
    "- Contact details for the cleaning service used at the old house, with rates and scheduling notes.\n"
    "- Notes from the LazyVim tutorial: the Neovim keystrokes and config tweaks worth remembering."
)
SCHEMA = {"type": "object", "properties": {"description": {"type": "string"}}, "required": ["description"]}


def body_text(text):
    _, body, _ = vl.split_frontmatter(text)
    return re.sub(r"\s+", " ", re.sub(r"```.*?```", " ", body, flags=re.S)).strip()


def needs_description(n):
    if n["generated"] or n["description"] or os.path.basename(n["rel"]) in SKIP_FILES:
        return False
    if n["rel"].startswith(SKIP_PREFIXES) or vl.split_frontmatter(n["text"])[0] is None:
        return False
    return len(body_text(n["text"])) >= MIN_BODY


def insert_description(desc):
    def transform(text):
        fm, _, end = vl.split_frontmatter(text)
        if fm is None or re.search(r"^description:", fm, re.M):
            return None  # frontmatter vanished or someone added a description meanwhile
        return "---\n" + fm + f"description: {vl.yaml_str(desc)}\n" + text[text.find("\n---", 3) + 1:]
    return transform


def main():
    if not vl.vault_ready(VAULT):
        return 0
    now = vl.dt.datetime.now().timestamp()
    todo = [n for n in vl.load_notes(VAULT) if needs_description(n) and now - n["mtime_raw"] >= MIN_AGE_S]
    todo.sort(key=lambda n: n["mtime_raw"], reverse=True)  # recently touched notes first
    print(f"{len(todo)} notes need a description; doing up to {MAX_NOTES}")
    done = failed = 0
    for n in todo[:MAX_NOTES]:
        prompt = f"Path: {n['rel']}\nTitle: {n['name']}\n\n{body_text(n['text'])[:6000]}"
        try:
            desc = " ".join(vl.ollama_json(SYSTEM, prompt, SCHEMA)["description"].split()).strip("\"' ")
            desc = re.sub(r"^This (note|document|page|file) (is |contains |details |catalogs |summarizes |lists )?", "", desc)
            desc = desc[:1].upper() + desc[1:]
        except Exception as e:  # model down/timeout: stop early, try again tomorrow
            print(f"ollama error on {n['rel']}: {e}", file=sys.stderr)
            failed += 1
            if failed >= 3:
                break
            continue
        if not 20 <= len(desc) <= 300 or "\n" in desc:
            print(f"rejected description for {n['rel']}: {desc!r}")
            continue
        if vl.DRY:
            print(f"would describe {n['rel']}: {desc}")
            done += 1
        elif vl.safe_edit(n["path"], insert_description(desc), min_age_s=MIN_AGE_S):
            print(f"described {n['rel']}: {desc}")
            done += 1
    print(f"described {done} notes ({failed} model errors)")
    return 1 if failed >= 3 else 0


if __name__ == "__main__":
    sys.exit(main())
