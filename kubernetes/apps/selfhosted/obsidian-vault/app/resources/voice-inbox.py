#!/usr/bin/env python3
"""Turn audio dropped into <vault>/Inbox/Voice/ into transcribed, summarized notes.

Any device that syncs the vault can drop a recording (mp3, m4a, wav, ogg, opus, webm, flac,
aac, amr, 3gp) anywhere under Inbox/Voice/. For each one this:
  1. transcribes it with Speaches (OpenAI-compatible Whisper API),
  2. asks the local Ollama model for a title, one-line description, summary and to-dos,
  3. writes Inbox/Voice/<YYYY-MM-DD HHMM> <Title>.md (raw transcript included),
  4. moves the audio to Attachments/Voice/<YYYY-MM>/ and embeds it in the note.
With LIBRARIAN_URL set, step 3 also asks the kagent voice-librarian agent for a filing
suggestion, related notes and zettel candidates: the note gets a "Librarian" section and
each zettel becomes a status: stub note in Zettels/. Earlier inbox notes written by this
pipeline are backfilled a few per run (BACKFILL_PER_RUN). If the agent fails, the note is
written exactly as before.
The note is written before the audio moves, so a crash never loses a recording; a file that
fails stays put and is retried next run (the health check flags ones stuck for hours).
If the summary step fails the note is still written with the transcript alone.

Usage: voice-inbox.py <vault-dir> [--dry-run]
"""
import datetime as dt
import json
import os
import re
import shutil
import sys
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import librarian  # noqa: E402
import processor  # noqa: E402
import vaultlib as vl  # noqa: E402

VAULT = sys.argv[1] if len(sys.argv) > 1 else "/vault"
INBOX = "Inbox/Voice"
AUDIO_DIR = "Attachments/Voice"
STT_URL = os.environ.get("STT_URL", "http://speaches.ai.svc.cluster.local:8000")
STT_MODEL = os.environ.get("STT_MODEL", "deepdml/faster-whisper-large-v3-turbo-ct2")
# Names and jargon Whisper should spell right live in the vault itself (private, editable
# from any device): every bullet / comma-separated term in this note's body is passed as the
# transcription prompt. Missing note = no hint.
VOCAB_NOTE = os.environ.get("STT_VOCAB_NOTE", "System/Voice Vocabulary.md")


def vocabulary():
    try:
        with open(os.path.join(VAULT, VOCAB_NOTE), encoding="utf-8") as fh:
            _, body, _ = vl.split_frontmatter(fh.read())
    except (OSError, UnicodeDecodeError):
        return ""
    terms = []
    for line in body.split("\n"):
        line = line.strip()
        if not line.startswith(("- ", "* ")):
            continue  # headings and prose are for humans
        terms += [t.strip() for t in line[2:].split(",") if t.strip()]
    return ", ".join(dict.fromkeys(terms))[:800]  # Whisper's prompt window is ~224 tokens
MIN_AGE_S = 60  # let a still-arriving file settle
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "10"))
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".ogg", ".opus", ".webm", ".flac", ".aac", ".amr", ".3gp"}
AUTHOR = "voice-inbox"
ZETTEL_DIR = "Zettels"
LIBRARIAN_ON = bool(os.environ.get("LIBRARIAN_URL"))
BACKFILL_PER_RUN = int(os.environ.get("BACKFILL_PER_RUN", "2"))
# The kagent `claude` agent does the whole processing step when set; the local model and
# the voice-librarian agent remain the fallback when it fails or is out of usage.
PROCESSOR_ON = bool(os.environ.get("PROCESSOR_URL"))
FACTS_NOTE = "Voice Notes.md"
TOUCHED = set()  # folders that got a Voice Notes entry this run, for the Syncthing rescan

# Filenames recorders commonly use: 260227_1158, 2026-02-07 18-03-17, 20260207_180317, voice-2026-02-26-073130
STAMPS = [
    (re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})?(?!\d)"), lambda g: (2000 + int(g[0]), g[1], g[2], g[3], g[4])),
    (re.compile(r"(20\d{2})-?(\d{2})-?(\d{2})[ _T-]+(\d{2})[-:.]?(\d{2})"), lambda g: (int(g[0]), g[1], g[2], g[3], g[4])),
]

SYSTEM = (
    "You turn the vault owner's voice memo transcripts into notes for their knowledge base. "
    "title: 2-6 words, Title Case, no punctuation or dates. "
    "description: one sentence (12-30 words) saying what the memo is about. "
    "summary: 1-5 short bullets capturing the substance, in the speaker's own terms; no filler. "
    "tasks: only things the speaker says they or someone needs to do, phrased as imperatives; empty if none. "
    "If the transcript is empty or unintelligible say so in the description and leave the rest empty."
)
SCHEMA = {"type": "object", "properties": {
    "title": {"type": "string"}, "description": {"type": "string"},
    "summary": {"type": "array", "items": {"type": "string"}},
    "tasks": {"type": "array", "items": {"type": "string"}},
}, "required": ["title", "description", "summary", "tasks"]}


def recorded_at(path):
    name = os.path.basename(path)
    for rx, conv in STAMPS:
        m = rx.search(name)
        if m:
            try:
                y, mo, d, h, mi = conv(m.groups())
                return dt.datetime(int(y), int(mo), int(d), int(h), int(mi), tzinfo=vl.TZ)
            except ValueError:
                pass
    return dt.datetime.fromtimestamp(os.path.getmtime(path), vl.TZ)


def transcribe(path):
    boundary = uuid.uuid4().hex
    parts = []
    vocab = vocabulary()
    fields = [("model", STT_MODEL), ("response_format", "verbose_json")] + ([("prompt", vocab + ".")] if vocab else [])
    for k, v in fields:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    with open(path, "rb") as fh:
        audio = fh.read()
    fname = os.path.basename(path).replace('"', "")
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"\r\n'
                 f"Content-Type: application/octet-stream\r\n\r\n".encode() + audio + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(f"{STT_URL}/v1/audio/transcriptions", data=b"".join(parts),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=900) as resp:
        data = json.loads(resp.read())
    return data.get("text", "").strip(), data.get("language", ""), data.get("duration")


def collapse_repeats(text):
    """Whisper loops on trailing silence ("Thank you. Thank you. ..."): keep one copy of any
    sentence repeated 3+ times in a row."""
    sents = re.split(r"(?<=[.!?])\s+", text)
    out = []
    for s in sents:
        if len(out) >= 1 and s.strip().lower() == out[-1].strip().lower():
            continue
        out.append(s)
    return " ".join(out) if len(sents) - len(out) >= 2 else text


def clean(s, limit=80):
    s = re.sub(r"[\\/:*?\"<>|#^\[\]]", "", " ".join(str(s).split())).strip(" .")
    return s[:limit].rstrip()


def unique_path(path):
    base, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(path):
        path = f"{base} {n}{ext}"
        n += 1
    return path


def ask_librarian(rel, title, text):
    """The agent's suggestions, or None (agent off, failed, or nothing to say)."""
    if not (LIBRARIAN_ON and text.strip()):
        return None
    try:
        lib = librarian.ask(VAULT, title, text)
    except Exception as e:
        print(f"{rel}: librarian failed ({e}); continuing without it", file=sys.stderr)
        return None
    print(f"{rel}: librarian folder={lib['folder'] or '-'} related={len(lib['related'])} "
          f"zettels={len(lib['zettels'])} dropped={lib['dropped']}")
    return lib


def ask_processor(rel, when, text):
    """Everything the claude agent extracted, validated, or None to use the local fallback."""
    if not (PROCESSOR_ON and text.strip()):
        return None
    try:
        proc = processor.ask(VAULT, when, text)
    except Exception as e:
        print(f"{rel}: processor failed ({e}); falling back to the local model", file=sys.stderr)
        return None
    print(f"{rel}: processor tasks={len(proc['tasks'])} facts={len(proc['facts'])} "
          f"zettels={len(proc['zettels'])} folder={proc['folder'] or '-'} dropped={proc['dropped']}")
    return proc


def task_lines(tasks):
    """Tasks-plugin checkboxes; a due date becomes its calendar marker."""
    out = []
    for t in tasks:
        t = t if isinstance(t, dict) else {"text": t, "due": None}
        if str(t["text"]).strip():
            out.append(f"- [ ] {str(t['text']).strip()}" + (f" 📅 {t['due']}" if t.get("due") else ""))
    return out


def write_facts(proc, note_rel, title, when):
    """Append each fact to '<folder>/Voice Notes.md', a pipeline-owned note per folder."""
    by_folder = {}
    for f in proc["facts"]:
        by_folder.setdefault(f["folder"], []).append(f["text"])
    rels = []
    for folder, texts in by_folder.items():
        rel = os.path.join(folder, FACTS_NOTE)
        path = os.path.join(VAULT, rel)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                cur = fh.read().rstrip("\n") + "\n"
        else:
            name = os.path.basename(folder)
            cur = "\n".join([
                "---", f"created: {dt.date.today()}", "type: log", "status: active", "tags:", "  - voice-note",
                f"description: {vl.yaml_str(f'Facts and updates about {name} captured from voice memos, oldest first.')}",
                "generated: true", f"author: {AUTHOR}", "---", "", f"# Voice Notes: {name}", "",
                "*Appended by the voice pipeline. Move anything worth keeping into the real notes.*", ""])
        entry = [f"## {when:%Y-%m-%d} {title}", ""] + [f"- {t}" for t in texts] + \
                ["", f"From {vl.wikilink(note_rel)}.", ""]
        vl.atomic_write(path, cur + "\n" + "\n".join(entry))
        TOUCHED.add(folder)
        rels.append(rel)
    return rels


def routed_section(proc, zettel_rels, fact_rels):
    lines = ["## Routed", "", "*Sorted by the `claude` agent. This memo stays here as the record.*", ""]
    dated = sum(1 for t in proc["tasks"] if t.get("due"))
    if proc["tasks"]:
        lines.append(f"- **Tasks:** {len(proc['tasks'])} above ({dated} with a due date); they show on the daily page")
    if fact_rels:
        lines.append("- **Facts filed in:** " + ", ".join(vl.wikilink(r) for r in fact_rels))
    if zettel_rels:
        lines.append("- **Zettels:** " + ", ".join(vl.wikilink(r) for r in zettel_rels))
    if proc["folder"]:
        lines.append(f"- **Topic folder:** `{proc['folder']}/`")
    if proc["related"]:
        lines.append("- **Related:** " + ", ".join(vl.wikilink(r) for r in proc["related"]))
    if len(lines) == 4:
        lines.append("- Nothing to route.")
    return lines + [""]


def write_zettels(lib, note_rel, when):
    """One status: stub note per zettel (schema from Library/Research/Second Brain Architecture -
    Dual Layer Design). Returns their vault paths."""
    today = dt.date.today()
    rels = []
    for z in lib["zettels"]:
        rel = os.path.relpath(unique_path(os.path.join(VAULT, ZETTEL_DIR, f"{z['title']}.md")), VAULT)
        tags = list(dict.fromkeys(["zettel", z["domain"]] + z["tags"]))
        fm = ["---", f"created: {today}", f"updated: {today}", "type: zettel", "status: stub",
              f"domain: {z['domain']}", f"source: {vl.yaml_str(vl.wikilink(note_rel))}",
              f"claim: {vl.yaml_str(z['claim'])}", "perspective: owner", f"confidence: {z['confidence']}",
              "related:"] + [f"  - {vl.yaml_str(vl.wikilink(r))}" for r in lib["related"]]
        if not lib["related"]:
            fm[-1] = "related: []"
        fm += ["tags:"] + [f"  - {t}" for t in tags]
        fm += [f"description: {vl.yaml_str(z['claim'])}", "generated: true", f"author: {AUTHOR}", "---", ""]
        body = [f"# {z['title']}", "", "## Context", "", z["context"] or z["claim"], "",
                "## My Take", "", f"> {z['take']}", "",
                "## Source", "",
                f"Extracted from {vl.wikilink(note_rel)} (voice memo, {when:%Y-%m-%d}) by the "
                f"`voice-librarian` agent. The take is quoted from the transcript; edit it, add to it, "
                f"then set `status: active`.", ""]
        vl.atomic_write(os.path.join(VAULT, rel), "\n".join(fm + body))
        rels.append(rel)
    return rels


def librarian_section(lib, zettel_rels):
    lines = ["## Librarian", "",
             "*Suggestions from the `voice-librarian` agent; nothing was moved.*", ""]
    if lib["folder"]:
        lines.append(f"- **Suggested folder:** `{lib['folder']}/`")
    if lib["related"]:
        lines.append("- **Related:** " + ", ".join(vl.wikilink(r) for r in lib["related"]))
    if zettel_rels:
        lines.append("- **Zettels:** " + ", ".join(vl.wikilink(r) for r in zettel_rels))
    if len(lines) == 4:
        lines.append("- Nothing to suggest.")
    return lines + [""]


def process(src):
    rel_src = os.path.relpath(src, VAULT)
    when = recorded_at(src)
    text, lang, duration = transcribe(src)
    text = collapse_repeats(text)
    print(f"{rel_src}: transcribed {len(text)} chars ({lang}, {duration}s)")
    info = {"title": "", "description": "", "summary": [], "tasks": []}
    proc = ask_processor(rel_src, when, text)
    if proc:
        info = proc
    elif text:
        try:
            info = vl.ollama_json(SYSTEM, f"Recorded {when:%Y-%m-%d %H:%M}.\nTranscript:\n{text[:12000]}", SCHEMA)
        except Exception as e:  # keep the transcript even without a summary
            print(f"{rel_src}: summary failed ({e}); writing transcript only", file=sys.stderr)
    title = clean(info.get("title") or "") or "Voice Note"
    desc = " ".join(str(info.get("description") or "").split()) or \
        (f"Voice memo recorded {when:%Y-%m-%d %H:%M}." if text else f"Voice memo recorded {when:%Y-%m-%d %H:%M}; no speech detected.")

    audio_rel = os.path.join(AUDIO_DIR, f"{when:%Y-%m}", os.path.basename(src))
    audio_rel = os.path.relpath(unique_path(os.path.join(VAULT, audio_rel)), VAULT)
    note_rel = os.path.relpath(unique_path(os.path.join(VAULT, INBOX, f"{when:%Y-%m-%d %H%M} {title}.md")), VAULT)

    dur = f"{int(duration // 60)}m{int(duration % 60):02d}s" if isinstance(duration, (int, float)) else ""
    fm = ["---", f"created: {when:%Y-%m-%d}", f"recorded: {when:%Y-%m-%dT%H:%M}", "type: voice-note",
          "source: voice", f"status: {'processed' if proc else 'inbox'}", "tags:", "  - voice-note",
          f"description: {vl.yaml_str(desc)}", f"audio_file: {vl.yaml_str(audio_rel)}"]
    fm += [f"duration: {vl.yaml_str(dur)}"] if dur else []
    fm += [f"language: {lang}"] if lang else []
    fm += ["generated: true", f"author: {AUTHOR}", "---", ""]
    body = [f"# {title}", "", f"![[{audio_rel}]]", "",
            f"*Recorded {when:%A %Y-%m-%d %H:%M}{' · ' + dur if dur else ''}. Transcribed by the local "
            f"`{AUTHOR}` pipeline" + ("; summarized and routed by the `claude` agent.*" if proc else
                                      " and summarized by the local model; edit freely, then file it out of the inbox.*"), ""]
    if info.get("summary"):
        body += ["## Summary", ""] + [f"- {s.strip()}" for s in info["summary"] if s.strip()] + [""]
    if info.get("tasks"):
        body += ["## To-do", ""] + task_lines(info["tasks"]) + [""]
    lib = proc or ask_librarian(rel_src, title, text)
    zettel_rels = write_zettels(lib, note_rel, when) if lib and not vl.DRY else []
    if proc:
        body += routed_section(proc, zettel_rels, [] if vl.DRY else write_facts(proc, note_rel, title, when))
    elif lib:
        body += librarian_section(lib, zettel_rels)
    body += ["## Transcript", "", text or "*(no speech detected)*", ""]

    if vl.DRY:
        print(f"would write {note_rel} and move audio to {audio_rel}\n" + "\n".join(fm + body))
        return
    vl.atomic_write(os.path.join(VAULT, note_rel), "\n".join(fm + body))
    os.makedirs(os.path.dirname(os.path.join(VAULT, audio_rel)), exist_ok=True)
    shutil.move(src, os.path.join(VAULT, audio_rel))
    print(f"{rel_src} -> {note_rel} (audio: {audio_rel})")


def backfill(limit):
    """Route earlier inbox notes this pipeline wrote: with the processor, add tasks, facts,
    zettels and a Routed section and mark them processed; without it, the Librarian section."""
    if not (LIBRARIAN_ON or PROCESSOR_ON) or limit <= 0:
        return 0
    inbox = os.path.join(VAULT, INBOX)
    done = 0
    for f in sorted(os.listdir(inbox)):
        if done >= limit:
            break
        path = os.path.join(inbox, f)
        if not f.endswith(".md") or not os.path.isfile(path) \
                or dt.datetime.now().timestamp() - os.path.getmtime(path) < 3600:
            continue  # leave notes someone touched in the last hour alone
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        meta = vl.parse_frontmatter(text)
        if meta.get("author") != AUTHOR or meta.get("status") != "inbox" or "\n## Routed\n" in text \
                or "\n## Transcript\n" not in text or (not PROCESSOR_ON and "\n## Librarian\n" in text):
            continue
        rel = os.path.relpath(path, VAULT)
        transcript = text.split("\n## Transcript\n", 1)[1].strip()
        title = os.path.splitext(f)[0][16:] or os.path.splitext(f)[0]
        done += 1
        try:
            when = dt.datetime.fromisoformat(str(meta.get("recorded", "")))
        except ValueError:
            when = dt.datetime.fromtimestamp(os.path.getmtime(path))
        proc = ask_processor(rel, when, transcript)
        lib = proc or (ask_librarian(rel, title, transcript) if "\n## Librarian\n" not in text else None)
        if not lib:
            continue
        if vl.DRY:
            print(f"would route {rel}: {json.dumps(lib, default=str)}")
            continue
        # A note that already has a Librarian section already has its zettels.
        zettel_rels = write_zettels(lib, rel, when) if "\n## Librarian\n" not in text else []
        todo = ""
        if proc:
            section = "\n".join(routed_section(proc, zettel_rels, write_facts(proc, rel, title, when)))
            if proc["tasks"] and "\n## To-do\n" not in text:
                todo = "\n".join(["## To-do", ""] + task_lines(proc["tasks"]) + [""]) + "\n"
        else:
            section = "\n".join(librarian_section(lib, zettel_rels))

        def add(t, section=section, todo=todo, routed=bool(proc)):
            if "\n## Routed\n" in t or "\n## Transcript\n" not in t or (not routed and "\n## Librarian\n" in t):
                return None
            head, tail = t.split("\n## Transcript\n", 1)
            if routed:
                head = head.replace("\nstatus: inbox\n", "\nstatus: processed\n", 1)
            return head.rstrip("\n") + "\n\n" + todo + section + "\n## Transcript\n" + tail
        # Only notes nobody has touched for an hour; an edit that lands meanwhile wins.
        if vl.safe_edit(path, add, min_age_s=3600, keep_mtime=False):
            print(f"{rel}: backfilled ({'routed' if proc else 'librarian'}, {len(zettel_rels)} zettels)")
        else:
            print(f"{rel}: changed meanwhile, section not added", file=sys.stderr)
    return done


def main():
    inbox = os.path.join(VAULT, INBOX)
    if not vl.vault_ready(VAULT) or not os.path.isdir(inbox):
        return 0
    now = dt.datetime.now().timestamp()
    todo = []
    for root, dirs, files in os.walk(inbox):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            p = os.path.join(root, f)
            if not f.startswith((".", "~")) and os.path.splitext(f)[1].lower() in AUDIO_EXT \
                    and now - os.path.getmtime(p) >= MIN_AGE_S:
                todo.append(p)
    todo.sort(key=os.path.getmtime)
    rc, wrote = 0, False
    for p in todo[:MAX_PER_RUN]:
        try:
            process(p)
            wrote = True
        except Exception as e:
            print(f"error processing {os.path.relpath(p, VAULT)}: {e}", file=sys.stderr)
            rc = 1
    if len(todo) > MAX_PER_RUN:
        print(f"{len(todo) - MAX_PER_RUN} recordings left for the next run")
    elif not todo:
        try:
            wrote = backfill(BACKFILL_PER_RUN) > 0 or wrote  # quiet runs only, so new recordings never wait
        except Exception as e:
            print(f"backfill failed: {e}", file=sys.stderr)
            rc = 1
    if wrote and vl.request_rescan(VAULT, [INBOX, ZETTEL_DIR, AUDIO_DIR] + sorted(TOUCHED)):
        print("asked Syncthing to rescan")
    return rc


if __name__ == "__main__":
    sys.exit(main())
