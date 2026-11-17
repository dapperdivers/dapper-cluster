#!/usr/bin/env python3
"""Turn audio dropped into <vault>/Inbox/Voice/ into transcribed, summarized notes.

Any device that syncs the vault can drop a recording (mp3, m4a, wav, ogg, opus, webm, flac,
aac, amr, 3gp) anywhere under Inbox/Voice/. For each one this:
  1. transcribes it with Speaches (OpenAI-compatible Whisper API),
  2. asks the local Ollama model for a title, one-line description, summary and to-dos,
  3. writes Inbox/Voice/<YYYY-MM-DD HHMM> <Title>.md (raw transcript included),
  4. moves the audio to Attachments/Voice/<YYYY-MM>/ and embeds it in the note.
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
import vaultlib as vl  # noqa: E402

VAULT = sys.argv[1] if len(sys.argv) > 1 else "/vault"
INBOX = "Inbox/Voice"
AUDIO_DIR = "Attachments/Voice"
STT_URL = os.environ.get("STT_URL", "http://speaches.ai.svc.cluster.local:8000")
STT_MODEL = os.environ.get("STT_MODEL", "deepdml/faster-whisper-large-v3-turbo-ct2")
STT_PROMPT = os.environ.get("STT_PROMPT", "")  # vocabulary hint: names and jargon Whisper should spell right
MIN_AGE_S = 60  # let a still-arriving file settle
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "10"))
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".ogg", ".opus", ".webm", ".flac", ".aac", ".amr", ".3gp"}
AUTHOR = "voice-inbox"

# Filenames recorders commonly use: 260227_1158, 2026-02-07 18-03-17, 20260207_180317, voice-2026-02-26-073130
STAMPS = [
    (re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})?(?!\d)"), lambda g: (2000 + int(g[0]), g[1], g[2], g[3], g[4])),
    (re.compile(r"(20\d{2})-?(\d{2})-?(\d{2})[ _T-]+(\d{2})[-:.]?(\d{2})"), lambda g: (int(g[0]), g[1], g[2], g[3], g[4])),
]

SYSTEM = (
    "You turn Derek's voice memo transcripts into notes for his knowledge base. "
    "title: 2-6 words, Title Case, no punctuation or dates. "
    "description: one sentence (12-30 words) saying what the memo is about. "
    "summary: 1-5 short bullets capturing the substance, in Derek's own terms; no filler. "
    "tasks: only things Derek says he or someone needs to do, phrased as imperatives; empty if none. "
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
    fields = [("model", STT_MODEL), ("response_format", "verbose_json")] + ([("prompt", STT_PROMPT)] if STT_PROMPT else [])
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


def process(src):
    rel_src = os.path.relpath(src, VAULT)
    when = recorded_at(src)
    text, lang, duration = transcribe(src)
    print(f"{rel_src}: transcribed {len(text)} chars ({lang}, {duration}s)")
    info = {"title": "", "description": "", "summary": [], "tasks": []}
    if text:
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
          "source: voice", "status: inbox", "tags:", "  - voice-note",
          f"description: {vl.yaml_str(desc)}", f"audio_file: {vl.yaml_str(audio_rel)}"]
    fm += [f"duration: {vl.yaml_str(dur)}"] if dur else []
    fm += [f"language: {lang}"] if lang else []
    fm += ["generated: true", f"author: {AUTHOR}", "---", ""]
    body = [f"# {title}", "", f"![[{audio_rel}]]", "",
            f"*Recorded {when:%A %Y-%m-%d %H:%M}{' · ' + dur if dur else ''}. Transcribed and summarized by the local "
            f"`{AUTHOR}` pipeline; edit freely, then file it out of the inbox.*", ""]
    if info.get("summary"):
        body += ["## Summary", ""] + [f"- {s.strip()}" for s in info["summary"] if s.strip()] + [""]
    if info.get("tasks"):
        body += ["## To-do", ""] + [f"- [ ] {t.strip()}" for t in info["tasks"] if t.strip()] + [""]
    body += ["## Transcript", "", text or "*(no speech detected)*", ""]

    if vl.DRY:
        print(f"would write {note_rel} and move audio to {audio_rel}\n" + "\n".join(fm + body))
        return
    vl.atomic_write(os.path.join(VAULT, note_rel), "\n".join(fm + body))
    os.makedirs(os.path.dirname(os.path.join(VAULT, audio_rel)), exist_ok=True)
    shutil.move(src, os.path.join(VAULT, audio_rel))
    print(f"{rel_src} -> {note_rel} (audio: {audio_rel})")


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
    rc = 0
    for p in todo[:MAX_PER_RUN]:
        try:
            process(p)
        except Exception as e:
            print(f"error processing {os.path.relpath(p, VAULT)}: {e}", file=sys.stderr)
            rc = 1
    if len(todo) > MAX_PER_RUN:
        print(f"{len(todo) - MAX_PER_RUN} recordings left for the next run")
    return rc


if __name__ == "__main__":
    sys.exit(main())
