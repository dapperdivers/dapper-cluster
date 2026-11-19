#!/usr/bin/env python3
"""Sort a high-volume Miniflux category with a local embedding model (stdlib only).

The firehose category holds bulk-imported feeds: far more than anyone reads. This job
scores each new unread entry there and marks the low part as read, so what stays unread is
the part worth a look (by the owner, or by the agents that write the morning brief).
Marking read is all it does in Miniflux: nothing is deleted, starred or unsubscribed, and
a read entry stays in Miniflux's History.

What counts as interesting is NOT in this (public) repository. It lives in the owner's
private vault, in PROFILE_NOTE, with three sections of bullets:
  ## Interests   one topic per bullet; an entry is scored by its nearest one
  ## Noise       kinds of entry to push down
  ## Watchlist   names (companies, products); an entry that mentions one is always kept
If the note does not exist the job writes a starter with placeholder bullets and does
nothing else until the owner has edited it.

How an entry is scored (title + the start of its text, embedded with EMBED_MODEL on Ollama):
  + similarity to the nearest interest
  + similarity to the three nearest articles the owner starred (their own "keep" signal)
  - similarity to the nearest noise bullet
Each part is standardised against a 30-day sample of the category, and the cut-off is the
READ_BELOW_PCT percentile of that sample. The sample is re-measured when the profile note
changes and once a week; the numbers are kept in STATE. Before scoring, repeats of a title
seen this week and non-English entries are marked read.

Usage: feed-sorter.py <vault-dir> [--dry-run]
"""
import datetime as dt
import hashlib
import html
import json
import math
import os
import re
import sys
import urllib.request

# The jobs run `python3 -I`, which leaves the script's own folder off sys.path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vaultlib as vl  # noqa: E402

VAULT = sys.argv[1] if len(sys.argv) > 1 else "/vault"
MF = os.environ.get("MINIFLUX_URL", "").rstrip("/") + "/v1/"
KEY = os.environ.get("MINIFLUX_API_KEY", "")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "embeddinggemma")
CATEGORY = os.environ.get("SORT_CATEGORY", "Security firehose")
WINDOW_H = float(os.environ.get("SORT_WINDOW_HOURS", "3"))
READ_BELOW_PCT = float(os.environ.get("READ_BELOW_PCT", "50"))
PROFILE_NOTE = os.environ.get("PROFILE_NOTE", "System/Feed Interests.md")
STATE = os.environ.get("SORTER_STATE", os.path.join(vl.GENERATED_DIR, "feed-sorter-state.json"))
RECALIBRATE_DAYS = 7
W_STAR, W_NOISE = 0.5, 0.7
PLACEHOLDER = "(replace me)"
ENGLISH = set("the of and to in is for on with that this as are by from at an be it or has have was will not "
              "can how what new your you we our their its more after into over about than when which".split())

STARTER = f"""---
created: {{today}}
type: reference
status: active
tags:
  - system/feed-sorter
description: "What the feed sorter keeps unread in the Miniflux firehose category: interests, noise and a watchlist of names. Edit the bullets to retune it."
---

# Feed Interests

The `feed-sorter` job reads this note every run. It scores each new entry in the Miniflux
"{CATEGORY}" category against the bullets below and marks the lower-scoring part as read.
Edit freely from any device; the sorter re-measures itself after a change.

Write each bullet as a short description of a topic, with the words an article about it
would use. Lines that are not bullets are ignored.

## Interests

- {PLACEHOLDER} one topic you want to see, for example: software supply chain attacks, compromised packages, build pipeline compromise

## Noise

- {PLACEHOLDER} one kind of entry you never want, for example: vendor marketing, product launch, webinar invitation, press release

## Watchlist

Names that are always kept when an entry mentions them (one per bullet, matched as whole words).

"""


def api(path, body=None, method="GET"):
    req = urllib.request.Request(MF + path, data=json.dumps(body).encode() if body is not None else None,
                                 method=method, headers={"X-Auth-Token": KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def entries(query):
    out, off = [], 0
    while True:
        page = api(f"{query}&limit=500&offset={off}")
        out += page["entries"]
        off += 500
        if off >= page["total"]:
            return out


def embed(texts):
    out = []
    for i in range(0, len(texts), 32):
        req = urllib.request.Request(vl.OLLAMA_URL.rstrip("/") + "/api/embed", headers={"Content-Type": "application/json"},
                                     data=json.dumps({"model": EMBED_MODEL, "input": texts[i:i + 32]}).encode())
        with urllib.request.urlopen(req, timeout=600) as r:
            out += json.loads(r.read())["embeddings"]
    return [[x / (math.sqrt(sum(y * y for y in v)) or 1) for x in v] for v in out]


def text_of(e, n=400):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", e.get("content") or "")).split())[:n]


def doc(e):  # embeddinggemma's document prompt
    return f"title: {e['title']} | text: {text_of(e)}"


def query(s):  # embeddinggemma's query prompt
    return f"task: search result | query: {s}"


def cos(a, b):
    return sum(x * y for x, y in zip(a, b))


def is_english(e):
    words = re.findall(r"[a-z']+", (e["title"] + " " + text_of(e)).lower())
    return len(words) < 15 or sum(w in ENGLISH for w in words) / len(words) >= 0.08


def title_key(e):
    return re.sub(r"[^a-z0-9]+", " ", e["title"].lower()).strip()


def read_profile(text):
    """{'interests': [...], 'noise': [...], 'watchlist': [...]} from the note's ## sections."""
    _, body, _ = vl.split_frontmatter(text)
    out, key = {"interests": [], "noise": [], "watchlist": []}, None
    for line in body.split("\n"):
        h = re.match(r"^##\s+(.+?)\s*$", line)
        if h:
            key = h.group(1).strip().lower()
            continue
        b = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
        if b and key in out and PLACEHOLDER not in b.group(1):
            out[key].append(b.group(1))
    return out


def watch_hit(e, patterns):
    hay = e["title"] + " " + text_of(e, 2000)
    return next((name for name, rx in patterns if rx.search(hay)), None)


def raw_scores(batch, starred_vecs, vi, vn, star_default):
    rows = []
    for e, v in zip(batch, embed([doc(e) for e in batch]) if batch else []):
        near = sorted((cos(v, x) for x in starred_vecs), reverse=True)[:3]
        rows.append({"e": e, "interest": max(cos(v, x) for x in vi),
                     "noise": max(cos(v, x) for x in vn) if vn else 0.0,
                     "star": sum(near) / len(near) if near else star_default})
    return rows


def final(r, cal):
    z = {k: (r[k] - cal[k][0]) / (cal[k][1] or 1) for k in ("interest", "noise", "star")}
    return z["interest"] + W_STAR * z["star"] - W_NOISE * z["noise"]


def calibrate(cat, now, starred_vecs, vi, vn):
    since = int((now - dt.timedelta(days=30)).timestamp())
    rows = raw_scores(entries(f"categories/{cat}/entries?published_after={since}"), starred_vecs, vi, vn, 0.0)
    if len(rows) < 50:
        return None
    cal = {}
    for k in ("interest", "noise", "star"):
        vals = [r[k] for r in rows]
        m = sum(vals) / len(vals)
        cal[k] = [m, math.sqrt(sum((x - m) ** 2 for x in vals) / len(vals))]
    s = sorted(final(r, cal) for r in rows)
    cal["cut"] = s[min(len(s) - 1, int(len(s) * READ_BELOW_PCT / 100))]
    cal["sample"] = len(rows)
    return cal


def main():
    if not KEY or MF == "/v1/":
        print("feed-sorter: MINIFLUX_URL / MINIFLUX_API_KEY not set; nothing to do")
        return 0
    if not vl.vault_ready(VAULT):
        return 0
    now = dt.datetime.now(dt.timezone.utc)
    note = os.path.join(VAULT, PROFILE_NOTE)
    if not os.path.exists(note):
        print(f"feed-sorter: writing a starter {PROFILE_NOTE}; edit it to switch the sorter on")
        vl.atomic_write(note, STARTER.replace("{today}", dt.datetime.now(vl.TZ).strftime("%Y-%m-%d")))
        vl.request_rescan(VAULT, (os.path.dirname(PROFILE_NOTE),))
        return 0
    with open(note, encoding="utf-8") as fh:
        text = fh.read()
    profile = read_profile(text)
    if not profile["interests"]:
        print(f"feed-sorter: {PROFILE_NOTE} has no interests yet; nothing to do")
        return 0
    cat = next((c["id"] for c in api("categories") if c["title"] == CATEGORY), None)
    if cat is None:
        print(f"feed-sorter: no Miniflux category named {CATEGORY!r}; nothing to do")
        return 0
    patterns = [(n, re.compile(r"(?<!\w)" + re.escape(n) + r"(?!\w)", re.I)) for n in profile["watchlist"] if len(n) >= 3]

    vi, vn = embed([query(s) for s in profile["interests"]]), embed([query(s) for s in profile["noise"]])
    starred = api("entries?starred=true&limit=200&order=changed_at&direction=desc")["entries"]
    vs = embed([doc(e) for e in starred]) if starred else []

    state_path = os.path.join(VAULT, STATE)
    try:
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (FileNotFoundError, ValueError):
        state = {}
    digest = hashlib.sha256(json.dumps([profile["interests"], profile["noise"], READ_BELOW_PCT]).encode()).hexdigest()[:16]
    age = (now - dt.datetime.fromisoformat(state["at"])).days if state.get("at") else 999
    if state.get("profile") != digest or age >= RECALIBRATE_DAYS:
        cal = calibrate(cat, now, vs, vi, vn)
        if cal is None:
            print("feed-sorter: fewer than 50 entries in the last 30 days; too few to calibrate, nothing marked")
            return 0
        state = {"profile": digest, "at": now.isoformat(), "cal": cal}
        print(f"feed-sorter: calibrated on {cal['sample']} entries; cut-off {cal['cut']:+.2f} "
              f"(the {READ_BELOW_PCT:.0f}th percentile)")
        vl.atomic_write(state_path, json.dumps(state, indent=1) + "\n")
    cal = state["cal"]

    # New arrivals: an unread entry's changed_at is the moment Miniflux stored it.
    since = int((now - dt.timedelta(hours=WINDOW_H)).timestamp())
    batch = entries(f"categories/{cat}/entries?status=unread&changed_after={since}&order=published_at&direction=desc")
    if not batch:
        print("feed-sorter: no new unread entries")
        return 0
    # Titles already seen this week (read or unread), to catch the same story posted twice.
    week = int((now - dt.timedelta(days=7)).timestamp())
    ids = {e["id"] for e in batch}
    seen = {title_key(e) for e in entries(f"categories/{cat}/entries?published_after={week}") if e["id"] not in ids}
    drop, watched, to_score = {}, [], []
    for e in sorted(batch, key=lambda e: e["id"]):
        k, hit = title_key(e), watch_hit(e, patterns)
        if hit:
            watched.append(e)
        elif k in seen:
            drop[e["id"]] = "duplicate"
        elif not is_english(e):
            drop[e["id"]] = "non-English"
        else:
            to_score.append(e)
        seen.add(k)
    kept = []
    for r in raw_scores(to_score, vs, vi, vn, cal["star"][0]):
        s = final(r, cal)
        if s < cal["cut"]:
            drop[r["e"]["id"]] = "low score"
        else:
            kept.append((s, r["e"]))
    kept.sort(key=lambda x: -x[0])
    by_id = {e["id"]: e for e in batch}
    # Titles and feeds only in the log: never the watchlist names themselves.
    for s, e in kept[:8]:
        print(f"  keep {s:+.2f}  {e['title'][:90]}  [{e['feed']['title'][:28]}]")
    for i, why in list(drop.items())[:8]:
        print(f"  read ({why})  {by_id[i]['title'][:80]}  [{by_id[i]['feed']['title'][:28]}]")
    if drop and not vl.DRY:
        todo = list(drop)
        for i in range(0, len(todo), 200):
            api("entries", {"entry_ids": todo[i:i + 200], "status": "read"}, "PUT")
    reasons = {}
    for why in drop.values():
        reasons[why] = reasons.get(why, 0) + 1
    print(f"feed-sorter: {len(batch)} new; {len(kept)} left unread by score, {len(watched)} kept by the watchlist, "
          f"{len(drop)} {'would be ' if vl.DRY else ''}marked read "
          f"({', '.join(f'{v} {k}' for k, v in sorted(reasons.items())) or 'none'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
