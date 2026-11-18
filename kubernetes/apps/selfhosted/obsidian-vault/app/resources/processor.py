"""Process one voice memo with the kagent `claude` agent (stdlib only).

One call turns a transcript into everything the pipeline routes: a title and summary,
tasks with due dates, zettel candidates, a filing folder with related notes, and facts
that belong with a project. Everything is validated here before anything is written:
folders must exist, dates must parse, and zettel quotes must be in the transcript.
"""
import datetime as dt
import os

import librarian
import vaultlib as vl

AGENT_URL = os.environ.get("PROCESSOR_URL", "")
MAX_TASKS, MAX_FACTS = 10, 5

PROMPT = """You are processing one voice memo from the owner of a personal Obsidian vault.
The transcript is machine-made speech-to-text: expect misheard words and no punctuation.
Use the vault tools (search_notes, read_note, list_directory) only to find related notes;
do not use web tools. Change nothing. Answer with one JSON object and nothing else:

{{"title": "", "description": "", "summary": [], "tasks": [{{"text": "", "due": null}}],
 "folder": "", "related": [], "facts": [{{"folder": "", "text": ""}}],
 "zettels": [{{"title": "", "claim": "", "context": "", "take": "", "domain": "",
              "confidence": "medium", "tags": []}}]}}

- title: 2-6 words, Title Case, no punctuation or dates.
- description: one sentence (12-30 words) saying what the memo is about.
- summary: 1-5 short bullets with the substance, in the speaker's own terms.
- tasks: only things the speaker says they or someone else needs to do, as imperatives
  ("Call the county about the permit"). "due" is YYYY-MM-DD when the speaker gives or
  clearly implies a date ("by Friday", "tomorrow", "next week" = the Monday), worked out
  from the recording time below; otherwise null. Never guess a date. Empty list if none.
- folder: the single best home for this memo's topic, copied exactly from the candidate
  folders. Empty string if none fits.
- related: up to 5 existing note paths on the same topic, exactly as search_notes returned
  them. Nothing under Inbox/, Agents/ or Archive/. Empty list if nothing is clearly related.
- facts: 0-5 concrete facts, measurements, decisions or status updates about a project or
  area that are worth keeping with it ("Greenhouse low was 41F last night"). Each needs a
  folder copied exactly from the candidate folders and one self-contained sentence.
  Not tasks, not opinions, not anything already in the related notes.
- zettels: 0-3 atomic ideas: one claim plus the speaker's own opinion or decision about it.
  "take" is that opinion quoted word for word from the transcript (a full sentence, 6+
  words); never paraphrase or invent it. Reminders, to-dos and questions are not zettels;
  none is a fine answer. domain is one lowercase word (homelab, finance, family, career,
  home, garden, health, learning, business, ai). confidence is high, medium, low or
  speculative. tags are 1-4 lowercase words.

If the transcript is empty or unintelligible, say so in the description and leave the
lists empty.

Recorded: {when:%A %Y-%m-%d %H:%M}

Candidate folders:
{folders}

Transcript:
{transcript}
"""


def _date(v, when):
    try:
        d = dt.date.fromisoformat(str(v).strip()[:10])
    except (TypeError, ValueError):
        return None
    # A due date before the recording or years away is a model slip, not a deadline.
    return d if when.date() <= d <= when.date() + dt.timedelta(days=730) else None


def _line(v, limit=300):
    return " ".join(str(v or "").split())[:limit]


def ask(vault, when, transcript, timeout=600):
    """Raises vl.AgentLimitError on usage limits and RuntimeError/ValueError otherwise."""
    folders = librarian.candidate_folders(vault)
    raw = vl.json_from_text(vl.agent_reply(AGENT_URL, PROMPT.format(
        when=when, folders="\n".join(folders), transcript=transcript[:20000]), timeout=timeout))
    out = librarian.validate(vault, raw, transcript, folders)
    out["title"], out["description"] = _line(raw.get("title"), 80), _line(raw.get("description"))
    out["summary"] = [s for s in (_line(x) for x in (raw.get("summary") or [])[:5] if isinstance(x, str)) if s]
    tasks = []
    for t in (raw.get("tasks") or [])[:MAX_TASKS]:
        t = t if isinstance(t, dict) else {"text": t}
        text = _line(t.get("text"), 200).lstrip("-[] ")
        if text:
            tasks.append({"text": text, "due": _date(t.get("due"), when)})
    out["tasks"] = tasks
    facts = []
    for f in (raw.get("facts") or [])[:MAX_FACTS]:
        if isinstance(f, dict):
            folder, text = str(f.get("folder") or "").strip().strip("/"), _line(f.get("text"), 400)
            if folder in folders and text:
                facts.append({"folder": folder, "text": text})
    out["facts"] = facts
    return out
