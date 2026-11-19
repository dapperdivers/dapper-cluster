#!/usr/bin/env python3
"""Process saved articles with the kagent `reading-processor` agent (stdlib only).

reading-inbox.py drops each starred Miniflux article into READING_DIR as a raw note (link
plus article text). This job takes the notes that have not been processed yet and asks the
agent, one article per call, for a summary, why it matters to the owner, related vault
notes, a filing folder and a few ideas worth keeping. Everything is validated here before
it is written: note paths and the folder must exist, and every quote must be in the
article text. The result goes into the note as a "## Digest" section above "## My notes",
and `processed: <date>` is added to its frontmatter.

It never touches a note edited in the last few minutes, never rewrites the owner's own
sections, and leaves `status: inbox` alone (reading and filing are still the owner's).
On a usage limit it stops; a note that fails three times is left as it is.

Usage: reading-process.py <vault-dir> [--dry-run]
"""
import datetime as dt
import json
import os
import re
import sys

# The jobs run `python3 -I`, which leaves the script's own folder off sys.path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import librarian  # noqa: E402
import vaultlib as vl  # noqa: E402

VAULT = sys.argv[1] if len(sys.argv) > 1 else "/vault"
AGENT_URL = os.environ.get("READING_AGENT_URL", "")
READING_DIR = os.environ.get("READING_DIR", "Inbox/Reading")
STATE = os.path.join(READING_DIR, "process-ledger.json")
PER_RUN = int(os.environ.get("READING_PROCESS_PER_RUN", "5"))
MIN_AGE_S = int(os.environ.get("READING_MIN_AGE_S", "300"))
MAX_TRIES = 3
MAX_TEXT = 30000
MIN_QUOTE_WORDS = 6
ARTICLE_H, NOTES_H, DIGEST_H = "## Article", "## My notes", "## Digest"

PROMPT = """You are processing one article the owner of a personal Obsidian vault saved from
their feed reader. Use the vault tools (search_notes, read_note, list_directory) to find
what the owner already has on this topic; do not use web tools and do not open the link.
Change nothing. Answer with one JSON object and nothing else:

{{"summary": [], "why": "", "related": [], "folder": "",
 "ideas": [{{"claim": "", "quote": ""}}], "tags": []}}

- summary: 3-5 bullets of at most 35 words each with what the article says: the finding, the
  numbers, the recommendation. No filler ("the article discusses"), nothing that is not
  in the text.
- why: one or two sentences on why this matters to the owner, grounded in what you found
  in the vault (a project, something they run, a decision they are weighing). If the
  vault shows no connection, write exactly: No clear link to existing notes.
- related: up to 5 existing note paths on the same topic, exactly as search_notes returned
  them. Nothing under Inbox/, Agents/ or Archive/. Empty list if nothing is clearly related.
- folder: the single best home for this article, copied exactly from the candidate
  folders. Empty string if none fits.
- ideas: 0-3 ideas from the article worth keeping as a note of their own. "claim" is the
  idea in one plain sentence. "quote" is one sentence copied word for word from the
  article text that carries it (6+ words); never paraphrase or invent it. None is a fine
  answer for news or release notes.
- tags: 1-4 lowercase topic words.

If the article text is empty or too broken to read, say so in the summary and leave the
other lists empty.

Title: {title}
Feed: {feed}
Link: {url}

Candidate folders:
{folders}

Article text:
{text}
"""


def _line(v, limit=400):
    return " ".join(str(v or "").split())[:limit]


def article_text(body):
    i = body.find("\n" + ARTICLE_H + "\n")
    return body[i + len(ARTICLE_H) + 2:].strip() if i != -1 else ""


def ask(meta, text, folders):
    """Raises vl.AgentLimitError on usage limits and RuntimeError/ValueError otherwise."""
    raw = vl.json_from_text(vl.agent_reply(AGENT_URL, PROMPT.format(
        title=meta.get("title", ""), feed=meta.get("feed", ""), url=meta.get("url", ""),
        folders="\n".join(folders), text=text[:MAX_TEXT]), timeout=600))
    out = librarian.validate(VAULT, raw, text, folders)  # checks folder and related paths
    out["summary"] = [s for s in (_line(x, 600) for x in (raw.get("summary") or [])[:5] if isinstance(x, str)) if s]
    out["why"] = _line(raw.get("why"), 500)
    flat = " ".join(text.lower().split())
    ideas, seen = [], set()
    for it in (raw.get("ideas") or [])[:3]:
        if not isinstance(it, dict):
            continue
        claim, quote = _line(it.get("claim")), _line(it.get("quote"), 600).strip(" \"'“”")
        key = quote.lower().rstrip(".!?")
        # The quote must be the article's own words, long enough to carry an idea.
        if claim and key and key in flat and len(key.split()) >= MIN_QUOTE_WORDS and key not in seen:
            seen.add(key)
            ideas.append({"claim": claim, "quote": quote})
    out["ideas"] = ideas
    out["dropped"] = len([i for i in (raw.get("ideas") or [])[:3] if isinstance(i, dict)]) - len(ideas)
    tags = raw.get("tags") if isinstance(raw.get("tags"), list) else []
    out["tags"] = [t for t in (str(x).lower().strip().lstrip("#") for x in tags) if librarian.TAG_OK.match(t)][:4]
    if not out["summary"]:
        raise ValueError("agent returned no summary")
    return out


def digest(res, today):
    lines = [DIGEST_H, "", f"*Written by the reading-processor agent on {today}. Check it against the article below.*", ""]
    lines += [f"- {s}" for s in res["summary"]]
    if res["why"]:
        lines += ["", f"**Why it matters:** {res['why']}"]
    if res["related"]:
        lines += ["", "**Related notes:** " + ", ".join(vl.wikilink(p) for p in res["related"])]
    if res["folder"]:
        lines += ["", f"**Suggested folder:** `{res['folder']}`"]
    if res["ideas"]:
        lines += ["", "**Ideas worth a note of their own:**", ""]
        for it in res["ideas"]:
            lines += [f"- {it['claim']}", f"  > {it['quote']}"]
    return "\n".join(lines) + "\n"


def apply(text, res, today):
    """New note text with the digest inserted and `processed` set, or None to leave it."""
    fm, body, stop = vl.split_frontmatter(text)
    if fm is None or ("\n" + DIGEST_H + "\n") in body or re.search(r"^processed:", fm, re.M):
        return None
    fm = fm.rstrip("\n") + f"\nprocessed: {today}\n"
    if res["tags"]:
        fm = re.sub(r"^tags: \[(.*)\]$", lambda m: "tags: [" + ", ".join(
            dict.fromkeys([t.strip() for t in m.group(1).split(",") if t.strip()] + res["tags"])) + "]",
            fm, count=1, flags=re.M)
    block = digest(res, today)
    i = body.find("\n" + NOTES_H + "\n")
    if i == -1:
        i = body.find("\n" + ARTICLE_H + "\n")
    body = body[:i + 1] + block + "\n" + body[i + 1:] if i != -1 else body.rstrip("\n") + "\n\n" + block
    return "---\n" + fm + "---\n" + body


def main():
    if not AGENT_URL:
        print("reading-process: READING_AGENT_URL not set; nothing to do")
        return 0
    if not vl.vault_ready(VAULT):
        return 0
    folder = os.path.join(VAULT, READING_DIR)
    if not os.path.isdir(folder):
        print("reading-process: no reading folder yet")
        return 0
    state_path = os.path.join(VAULT, STATE)
    try:
        with open(state_path, encoding="utf-8") as fh:
            tries = json.load(fh)
    except (FileNotFoundError, ValueError):
        tries = {}
    now, today = dt.datetime.now().timestamp(), dt.datetime.now(vl.TZ).strftime("%Y-%m-%d")
    todo = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not name.endswith(".md") or now - os.stat(path).st_mtime < MIN_AGE_S:
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        meta = vl.parse_frontmatter(text)
        if meta.get("type") != "article" or meta.get("processed") or tries.get(name, 0) >= MAX_TRIES:
            continue
        todo.append((name, path, text, meta))
    if not todo:
        print("reading-process: nothing to process")
        return 0
    folders, done, rc = librarian.candidate_folders(VAULT), 0, 0
    for name, path, text, meta in todo[:PER_RUN]:
        _, body, _ = vl.split_frontmatter(text)
        head = re.search(r"^# (.+)$", body, re.M)
        meta["title"] = head.group(1).strip() if head else name[:-3]
        try:
            res = ask(meta, article_text(body), folders)
        except vl.AgentLimitError as e:
            print(f"reading-process: usage limit, stopping: {e}", file=sys.stderr)
            break
        except Exception as e:  # bad JSON, agent error, timeout: count it and move on
            tries[name] = tries.get(name, 0) + 1
            print(f"warning: {name}: {e} (attempt {tries[name]} of {MAX_TRIES})", file=sys.stderr)
            rc = 1 if tries[name] >= MAX_TRIES else rc
            continue
        print(f"{'would update' if vl.DRY else 'updating'}: {name}: {len(res['summary'])} bullets, "
              f"{len(res['related'])} related, {len(res['ideas'])} ideas ({res['dropped']} dropped), "
              f"folder={res['folder'] or '-'}")
        if vl.DRY:
            print(digest(res, today))
            continue
        # keep_mtime=False: the digest is new content the owner should see as recently changed.
        if vl.safe_edit(path, lambda t: apply(t, res, today), min_age_s=MIN_AGE_S, keep_mtime=False):
            done += 1
            tries.pop(name, None)
        else:
            print(f"note: {name} changed while it was being processed; will retry next run")
    if not vl.DRY:
        vl.atomic_write(state_path, json.dumps(tries, indent=1, sort_keys=True) + "\n")
        if done:
            vl.request_rescan(VAULT, (READING_DIR,))
    print(f"reading-process: {done} processed, {max(0, len(todo) - PER_RUN)} left for the next run")
    return rc


if __name__ == "__main__":
    sys.exit(main())
