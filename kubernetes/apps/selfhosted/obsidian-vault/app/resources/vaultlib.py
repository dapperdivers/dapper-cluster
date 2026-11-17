"""Shared helpers for the obsidian-vault jobs (stdlib only).

Every job follows the vault's AGENTS.md contract: write <file>.tmp then rename, never touch
.obsidian/ .stfolder/ .stignore .trash/, and never edit a note someone is actively editing.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from zoneinfo import ZoneInfo

SKIP_DIRS = {".obsidian", ".trash", ".stversions", ".stfolder", ".git", "Templates"}
GENERATED_DIR = os.environ.get("OUTPUT_DIR", "Resources/Generated")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama.ai.svc.cluster.local:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")
DRY = "--dry-run" in sys.argv

try:
    TZ = ZoneInfo(os.environ.get("TZ", "America/Chicago"))
except Exception:  # image without tzdata: fall back rather than fail the job
    print("warning: timezone data unavailable, using UTC", file=sys.stderr)
    TZ = dt.timezone.utc

FM_KEY = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")


def vault_ready(vault):
    """A vault PVC Syncthing hasn't synced yet has no .stfolder marker: skip it, don't fail."""
    if os.path.exists(os.path.join(vault, ".stfolder")):
        return True
    print(f"warning: {vault} has no .stfolder marker (not synced yet?); skipping", file=sys.stderr)
    return False


def split_frontmatter(text):
    """Return (frontmatter_text, body, end_index) or (None, text, 0) when there is none."""
    if not text.startswith("---\n"):
        return None, text, 0
    end = text.find("\n---", 3)
    if end == -1:
        return None, text, 0
    nl = text.find("\n", end + 4)
    stop = nl + 1 if nl != -1 else len(text)
    return text[4:end + 1], text[stop:], stop


def parse_frontmatter(text):
    """Minimal YAML subset: top-level scalars and '- item' / [a, b] lists."""
    fm, _, _ = split_frontmatter(text)
    if fm is None:
        return {}
    data, key = {}, None
    for line in fm.split("\n"):
        m = FM_KEY.match(line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val.startswith("[") and val.endswith("]"):
                data[key] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
            else:
                data[key] = val.strip("'\"") if val else []
        elif key and line.lstrip().startswith("- ") and isinstance(data.get(key), list):
            data[key].append(line.lstrip()[2:].strip().strip("'\""))
    return data


def is_true(v):
    return str(v).lower() in ("true", "yes", "1")


def walk(vault, include_hidden=False, skip=SKIP_DIRS):
    """Yield (rel, abs) for every file, skipping Obsidian/Syncthing internals."""
    for root, dirs, files in os.walk(vault):
        dirs[:] = sorted(d for d in dirs if d not in skip and (include_hidden or not d.startswith(".")))
        for f in sorted(files):
            p = os.path.join(root, f)
            yield os.path.relpath(p, vault), p


def load_notes(vault, max_bytes=None):
    """All Markdown notes (excalidraw drawings excluded) with parsed frontmatter and text."""
    notes = []
    for rel, path in walk(vault):
        if not rel.endswith(".md") or rel.endswith(".excalidraw.md"):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read() if max_bytes is None else fh.read(max_bytes)
            st = os.stat(path)
        except (OSError, UnicodeDecodeError):
            continue
        fm = parse_frontmatter(text)
        notes.append({
            "rel": rel,
            "path": path,
            "name": os.path.basename(rel)[:-3],
            "top": rel.split(os.sep)[0] if os.sep in rel else "(root)",
            "mtime": dt.datetime.fromtimestamp(st.st_mtime, TZ),
            "mtime_raw": st.st_mtime,
            "text": text,
            "fm": fm,
            "type": str(fm.get("type", "")),
            "status": str(fm.get("status", "")),
            "description": fm.get("description", "") if isinstance(fm.get("description"), str) else "",
            "generated": is_true(fm.get("generated", "")) or rel.startswith(GENERATED_DIR + os.sep),
        })
    return notes


def wikilink(rel, label=None):
    target = rel[:-3] if rel.endswith(".md") else rel
    return f"[[{target}|{label}]]" if label else f"[[{target}]]"


def yaml_str(s):
    """Double-quoted YAML scalar on one line."""
    s = " ".join(str(s).split())
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def atomic_write(path, content, keep_mtime=None):
    if DRY:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
    os.replace(tmp, path)
    if keep_mtime is not None:
        os.utime(path, (keep_mtime, keep_mtime))


def strip_volatile(text):
    return re.sub(r"^> Generated \d{4}-\d{2}-\d{2}.*$", "> Generated", text, flags=re.M)


def write_if_changed(vault, rel, content):
    """Rewrite a generated note only when it changed (ignoring its 'Generated <date>' stamp)."""
    path = os.path.join(vault, rel)
    try:
        with open(path, encoding="utf-8") as fh:
            if strip_volatile(fh.read()) == strip_volatile(content):
                return "unchanged"
    except FileNotFoundError:
        pass
    if DRY:
        return "would write"
    atomic_write(path, content)
    return "written"


def safe_edit(path, transform, min_age_s=3600, keep_mtime=True):
    """Apply transform(text) -> new text to a note nobody is editing right now.

    Skips notes modified within min_age_s, re-checks the mtime just before writing (so an
    edit that landed meanwhile wins), and by default keeps the original mtime so machine
    fixes don't show up as 'recently edited'. Returns True when the file was changed.
    """
    st = os.stat(path)
    if dt.datetime.now().timestamp() - st.st_mtime < min_age_s:
        return False
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    new = transform(text)
    if new is None or new == text:
        return False
    if os.stat(path).st_mtime != st.st_mtime:
        return False
    atomic_write(path, new, keep_mtime=st.st_mtime if keep_mtime else None)
    return True


def ollama_json(system, user, schema, timeout=300):
    """Chat with the local model and return its JSON answer (Ollama structured outputs)."""
    body = json.dumps({
        "model": OLLAMA_MODEL,
        "stream": False,
        "think": False,
        "keep_alive": "10m",
        "options": {"temperature": 0.2},
        "format": schema,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(json.loads(resp.read())["message"]["content"])
