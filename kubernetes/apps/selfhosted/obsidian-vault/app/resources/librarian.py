"""Ask the kagent voice-librarian agent about one voice note (stdlib only).

The agent gets the transcript plus the vault's candidate folders and returns
{"folder", "related", "zettels"}; this module validates that against what is
actually in the vault so a confused answer can't produce a bad link or path.
"""
import os
import re

import vaultlib as vl

AGENT_URL = os.environ.get(
    "LIBRARIAN_URL", "http://kagent-controller.kagent.svc.cluster.local:8083/agents/kagent/voice-librarian")
AREAS = ("Personal", "Projects", "Work", "Library")
SKIP = {"Archive", "90 Archive", "Attachments", "evidence"}
CONFIDENCE = {"high", "medium", "low", "speculative"}
TAG_OK = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
MIN_TAKE_WORDS = 6
MAX_CLAIM, MAX_CONTEXT, MAX_TAKE = 400, 1000, 1500


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
    """The agent's answer as a dict. It replies in plain text (the template has no
    outputSchema, which would switch its vault tools off), so take the last JSON object."""
    return vl.json_from_text(vl.agent_reply(AGENT_URL, text, timeout=timeout))


def ask(vault, title, transcript, timeout=300):
    folders = candidate_folders(vault)
    prompt = (f"Voice memo: {title}\n\nCandidate folders:\n" + "\n".join(folders) +
              f"\n\nTranscript:\n{transcript[:12000]}")
    return validate(vault, _call(prompt, timeout), transcript, folders)


def validate(vault, raw, transcript, folders):
    """Keep only what checks out against the vault and the transcript."""
    if not isinstance(raw, dict):
        raise ValueError("agent answer is not a JSON object")

    def items(key, kind):  # a list of the expected type, whatever the model sent
        v = raw.get(key)
        return [x for x in v if isinstance(x, kind)] if isinstance(v, list) else []

    folder = raw.get("folder")
    folder = folder.strip().strip("/") if isinstance(folder, str) else ""
    related = []
    for p in items("related", str)[:20]:
        p = p.strip().lstrip("/")
        if ".." in p.split("/"):
            continue
        if p.endswith(".md") and not p.startswith("Inbox/") and os.path.isfile(os.path.join(vault, p)) \
                and p not in related:
            related.append(p)
    flat = " ".join(transcript.lower().split())
    zettels, takes = [], set()
    proposed = items("zettels", dict)[:3]
    for z in proposed:
        take = " ".join(str(z.get("take") or "").split()).strip(" \"'“”")
        title_z = re.sub(r"[\\/:*?\"<>|#^\[\]]", "", " ".join(str(z.get("title") or "").split())).strip(" .")[:80]
        claim = " ".join(str(z.get("claim") or "").split())[:MAX_CLAIM]
        if not (title_z and claim and take) or len(take) > MAX_TAKE:
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
            "context": " ".join(str(z.get("context") or "").split())[:MAX_CONTEXT],
            "domain": re.sub(r"[^a-z0-9-]", "", str(z.get("domain") or "").lower())[:30] or "general",
            "confidence": conf if conf in CONFIDENCE else "medium",
            "tags": [t for t in (str(x).lower().strip().lstrip("#") for x in (z.get("tags") if isinstance(z.get("tags"), list) else []))
                     if TAG_OK.match(t)][:4],
        })
    return {"folder": folder if folder in folders else "", "related": related[:5], "zettels": zettels,
            "dropped": len(proposed) - len(zettels)}
