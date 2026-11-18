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
GENERATED_DIR = os.environ.get("OUTPUT_DIR", "Agents/Generated")
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


def request_rescan(vault, subdirs=()):
    """Ask the Syncthing hub to rescan now. Its watcher doesn't see files written by these
    job pods (the vault is on CephFS), so without this new notes wait for the hourly full
    rescan. Needs SYNCTHING_URL + SYNCTHING_API_KEY; silently does nothing without them."""
    base, key = os.environ.get("SYNCTHING_URL"), os.environ.get("SYNCTHING_API_KEY")
    if DRY or not base or not key:
        return False
    import urllib.parse
    h = {"X-API-Key": key}
    name = os.path.basename(os.path.normpath(vault))
    try:
        req = urllib.request.Request(base.rstrip("/") + "/rest/config/folders", headers=h)
        with urllib.request.urlopen(req, timeout=15) as resp:
            folders = json.loads(resp.read())
        folder = next((f for f in folders if os.path.basename(os.path.normpath(f["path"])) == name), None)
        if not folder:
            print(f"warning: no Syncthing folder for {name}; not rescanning", file=sys.stderr)
            return False
        q = "folder=" + urllib.parse.quote(folder["id"]) + "".join(
            "&sub=" + urllib.parse.quote(d) for d in subdirs)
        req = urllib.request.Request(base.rstrip("/") + "/rest/db/scan?" + q, data=b"", headers=h, method="POST")
        urllib.request.urlopen(req, timeout=60).close()
        return True
    except Exception as e:  # sync still happens on the hourly rescan
        print(f"warning: Syncthing rescan request failed: {e}", file=sys.stderr)
        return False


class AgentLimitError(RuntimeError):
    """The agent's model provider refused for usage/rate limits: stop making calls."""


def agent_reply(url, text, timeout=900):
    """Send one message to a kagent agent over A2A (JSON-RPC, blocking); return its final
    answer as text. Raises AgentLimitError on rate/usage limits, RuntimeError otherwise."""
    import uuid
    body = {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": "SendMessage",
            "params": {"message": {"messageId": uuid.uuid4().hex, "role": "ROLE_USER",
                                   "parts": [{"text": text}]}}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "A2A-Version": "1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    if "error" in data:
        raise RuntimeError(f"agent error: {data['error']}")
    task = data.get("result", {}).get("task", {})
    usage = (task.get("metadata") or {}).get("https://kagent.dev/extensions/usage/v1")
    if isinstance(usage, dict):  # reported by kagent-harness agents only
        print(f"agent {url.rstrip('/').rsplit('/', 1)[-1]}: tokens in={usage.get('inputTokens')} "
              f"out={usage.get('outputTokens')} total={usage.get('totalTokens')}", file=sys.stderr)
    status = task.get("status", {})
    if status.get("state") != "TASK_STATE_COMPLETED":
        msg = " ".join(p.get("text", "") for p in (status.get("message") or {}).get("parts") or [])
        if re.search(r"rate.?limit|usage limit|\b429\b|overloaded|limit reached", msg, re.I):
            raise AgentLimitError(msg.strip()[:300])
        raise RuntimeError(f"agent finished in state {status.get('state')}: {msg.strip()[:300]}")
    # Every model step is its own artifact, so the answer is the last one that holds any: the
    # earlier ones are narration between tool calls. One answer can be split over hundreds of
    # text parts (join them as-is); parts flagged as model thinking are not part of it.
    for art in reversed(task.get("artifacts") or []):
        parts = [p for p in art.get("parts") or [] if isinstance(p, dict)]
        text = "".join(p.get("text") or "" for p in parts
                       if not (p.get("metadata") or {}).get("kagent.dev/a2a/thought")).strip()
        if text:
            return text
        # No text: an agent with an outputSchema answers in a structured `data` part. Tool calls
        # and tool results are `data` parts too (they carry args/response), so skip those.
        answers = [p["data"] for p in parts if isinstance(p.get("data"), dict)
                   and not {"args", "response"} & p["data"].keys()]
        if answers:
            return json.dumps(answers[-1])
    return ""


def json_from_text(t):
    """The last complete JSON object in a model's text answer. Models often write prose or
    fenced blocks around the object, or show a draft before the final one."""
    dec, found, i = json.JSONDecoder(), None, 0
    while (i := t.find("{", i)) != -1:
        try:
            obj, end = dec.raw_decode(t, i)
        except ValueError:
            i += 1
            continue
        if isinstance(obj, dict):
            found = obj
        i = end
    if found is None:
        raise ValueError("no JSON object in answer")
    return found


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
