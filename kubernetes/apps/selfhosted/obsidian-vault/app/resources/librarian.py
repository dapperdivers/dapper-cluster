"""Ask the kagent voice-librarian agent about one voice note (stdlib only).

The agent gets the transcript plus the vault's candidate folders and returns
{"folder", "related", "zettels"}; this module validates that against what is
actually in the vault so a confused answer can't produce a bad link or path.
"""
import json
import os
import re
import urllib.request
import uuid

AGENT_URL = os.environ.get(
    "LIBRARIAN_URL", "http://kagent-controller.kagent.svc.cluster.local:8083/agents/kagent/voice-librarian")
AREAS = ("Personal", "Projects", "Work", "Research", "Reference", "Resources")
SKIP = {"Archive", "90 Archive", "Attachments", "evidence"}
CONFIDENCE = {"high", "medium", "low", "speculative"}
TAG_OK = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
MIN_TAKE_WORDS = 6


def candidate_folders(vault):
    """Areas and their subfolders, two levels deep, without archives or hidden dirs."""
    out = []
    for area in AREAS:
        top = os.path.join(vault, area)
        if not os.path.isdir(top):
            continue
        out.append(area)
        for root, dirs, _ in os.walk(top):
            depth = os.path.relpath(root, top).count(os.sep) + (0 if root == top else 1)
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIP)
            if depth >= 2:
                dirs[:] = []
                continue
            out += [os.path.relpath(os.path.join(root, d), vault) for d in dirs]
    return out


def _call(text, timeout):
    body = {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": "SendMessage",
            "params": {"message": {"messageId": uuid.uuid4().hex, "role": "ROLE_USER",
                                   "parts": [{"text": text}]}}}
    req = urllib.request.Request(AGENT_URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "A2A-Version": "1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    if "error" in data:
        raise RuntimeError(f"agent error: {data['error']}")
    task = data.get("result", {}).get("task", {})
    state = task.get("status", {}).get("state")
    if state != "TASK_STATE_COMPLETED":
        raise RuntimeError(f"agent finished in state {state}")
    for art in reversed(task.get("artifacts") or []):
        for part in art.get("parts") or []:
            if isinstance(part.get("data"), dict):
                return part["data"]
            if part.get("text"):
                t = part["text"].strip()
                t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
                start, end = t.find("{"), t.rfind("}")
                if start != -1 and end > start:
                    return json.loads(t[start:end + 1])
    raise RuntimeError("agent returned no JSON")


def ask(vault, title, transcript, timeout=300):
    folders = candidate_folders(vault)
    prompt = (f"Voice memo: {title}\n\nCandidate folders:\n" + "\n".join(folders) +
              f"\n\nTranscript:\n{transcript[:12000]}")
    raw = _call(prompt, timeout)
    folder = str(raw.get("folder") or "").strip().strip("/")
    related = []
    for p in raw.get("related") or []:
        p = str(p).strip().lstrip("/")
        if p.endswith(".md") and not p.startswith("Inbox/") and os.path.isfile(os.path.join(vault, p)) \
                and p not in related:
            related.append(p)
    flat = " ".join(transcript.lower().split())
    zettels, takes = [], set()
    for z in (raw.get("zettels") or [])[:3]:
        if not isinstance(z, dict):
            continue
        take = " ".join(str(z.get("take") or "").split()).strip(" \"'“”")
        title_z = re.sub(r"[\\/:*?\"<>|#^\[\]]", "", " ".join(str(z.get("title") or "").split())).strip(" .")[:80]
        claim = " ".join(str(z.get("claim") or "").split())
        if not (title_z and claim and take):
            continue
        # The take must be the speaker's words: drop any zettel whose quote isn't in the
        # transcript, is too short to carry an opinion ("Yes."), or repeats another's quote.
        key = take.lower().rstrip(".!?")
        if key not in flat or len(key.split()) < MIN_TAKE_WORDS or key in takes:
            continue
        takes.add(key)
        conf = str(z.get("confidence") or "").lower()
        zettels.append({
            "title": title_z, "claim": claim, "take": take,
            "context": " ".join(str(z.get("context") or "").split()),
            "domain": re.sub(r"[^a-z0-9-]", "", str(z.get("domain") or "").lower()) or "general",
            "confidence": conf if conf in CONFIDENCE else "medium",
            "tags": [t for t in (str(x).lower().strip().lstrip("#") for x in z.get("tags") or []) if TAG_OK.match(t)][:4],
        })
    return {"folder": folder if folder in folders else "", "related": related[:5], "zettels": zettels,
            "dropped": len((raw.get("zettels") or [])[:3]) - len(zettels)}
