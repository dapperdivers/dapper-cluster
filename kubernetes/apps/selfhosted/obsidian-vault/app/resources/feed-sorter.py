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
Any other section is ignored here ("## Priority categories" is read by night-shift.py).
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

Which entries are new: STATE remembers the highest entry id handled so far (`last_id`) and
each run asks Miniflux for the unread entries after it, oldest first, at most
SORT_MAX_PER_RUN at a time. So nothing is skipped when the job or Ollama was down for a
while: the backlog is worked off over the next runs. Only the very first run, with no
`last_id` yet, looks back SORT_WINDOW_HOURS instead.

What it writes in the vault (all under OUTPUT_DIR, only when something changed):
  STATE      calibration, `last_id`, the time of the last run that did work, and per-day
             counts for the last KEEP_DAYS days (new, kept by score / by the watchlist,
             marked read as low score / duplicate / non-English)
  DECISIONS  one row per entry handled in the last KEEP_DAYS days (id, title, feed, score,
             decision, date), at most MAX_ROWS rows
  REVIEW     a note rewritten on the first run of each day: the counts, the best kept
             entries, the marked-read ones nearest the cut-off, a sample of the rest, and
             "misses" (entries the owner starred that the sorter had marked read). It is
             the place to check the sorter's calls before editing PROFILE_NOTE.
The log (stdout) only ever shows titles and feed names, never the watchlist.

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
DECISIONS = os.environ.get("SORTER_DECISIONS", os.path.join(vl.GENERATED_DIR, "feed-sorter-decisions.json"))
REVIEW = os.environ.get("SORTER_REVIEW", os.path.join(vl.GENERATED_DIR, "Feed Sorter Review.md"))
MAX_PER_RUN = int(os.environ.get("SORT_MAX_PER_RUN", "1500"))
AUTHOR = "feed-sorter"
RECALIBRATE_DAYS = 7
KEEP_DAYS = 14
MAX_ROWS = 5000
# An entry gets its id before Miniflux commits it, so a slightly lower id can still show up
# beside a brand-new one. Entries this fresh wait for the next run, so `last_id` never
# passes one that is not visible yet.
SETTLE_S = 60
# decision -> its per-day counter. The first two leave the entry unread, the rest mark it read.
COUNTERS = {"keep": "kept_score", "watchlist": "kept_watchlist", "low score": "read_low_score",
            "duplicate": "read_duplicate", "non-English": "read_non_english"}
READ = ("low score", "duplicate", "non-English")
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
    """{'interests': [...], 'noise': [...], 'watchlist': [...]} from the note's ## sections.
    Sections with any other heading are not the sorter's and are ignored (night-shift.py
    reads "## Priority categories" from the same note)."""
    sections = vl.note_sections(text)
    return {key: [b for b in sections.get(key, []) if PLACEHOLDER not in b]
            for key in ("interests", "noise", "watchlist")}


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


def load(path, default):
    """(data, text as stored) of a JSON file; the default when it is missing or unusable."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        data = json.loads(text)
        if isinstance(data, type(default)):
            return data, text
    except (FileNotFoundError, ValueError):
        pass
    return default, ""


def save(path, text, old):
    """Write only when the content changed, so Syncthing has nothing to do on a quiet run."""
    if text != old:
        vl.atomic_write(path, text)
    return text


def state_text(state):
    return json.dumps(state, indent=1) + "\n"


def rows_text(rows):  # one row per line
    return "[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n]\n"


def settled(found, now):
    """The entries (sorted by id) up to the first one stored less than SETTLE_S ago."""
    out = []
    for e in found:
        try:
            age = (now - dt.datetime.fromisoformat(e["created_at"])).total_seconds()
        except (KeyError, TypeError, ValueError):
            age = SETTLE_S
        if age < SETTLE_S:
            break
        out.append(e)
    return out


def fetch_new(cat, last_id, now):
    """(unread entries not handled yet, oldest first and at most MAX_PER_RUN; how many more wait)."""
    base = f"categories/{cat}/entries?status=unread&order=id&direction=asc"
    if last_id is None:
        # First run. An unread entry's changed_at is the moment Miniflux stored it.
        since = int((now - dt.timedelta(hours=WINDOW_H)).timestamp())
        found = sorted(entries(f"{base}&changed_after={since}"), key=lambda e: e["id"])
        total = len(found)
    else:
        found, after, total = [], last_id, 0
        while len(found) < MAX_PER_RUN:
            page = api(f"{base}&after_entry_id={after}&limit={min(500, MAX_PER_RUN - len(found))}")
            if not found:
                total = page["total"]
            found += page["entries"]
            if not page["entries"] or len(found) >= total:
                break
            after = page["entries"][-1]["id"]
    batch = settled(found, now)[:MAX_PER_RUN]
    return batch, max(0, total - len(batch))


def decide(batch, seen, patterns, vs, vi, vn, cal):
    """[(entry, decision, score or None)] in batch order. `seen` holds the title keys of earlier entries."""
    out, to_score = {}, []
    for e in batch:
        k = title_key(e)
        if watch_hit(e, patterns):
            out[e["id"]] = ("watchlist", None)
        elif k in seen:
            out[e["id"]] = ("duplicate", None)
        elif not is_english(e):
            out[e["id"]] = ("non-English", None)
        else:
            to_score.append(e)
        seen.add(k)
    for r in raw_scores(to_score, vs, vi, vn, cal["star"][0]):
        s = final(r, cal)
        out[r["e"]["id"]] = ("low score" if s < cal["cut"] else "keep", s)
    return [(e, *out[e["id"]]) for e in batch]


def record(state, rows, decided, now):
    """Add one run's decisions to the day counters, the decision rows and the high-water mark."""
    today = now.astimezone(vl.TZ).date().isoformat()
    day = state.setdefault("days", {}).setdefault(today, dict.fromkeys(["new", *COUNTERS.values()], 0))
    day["new"] += len(decided)
    for _, decision, _ in decided:
        day[COUNTERS[decision]] += 1
    handled = {e["id"] for e, _, _ in decided}
    rows[:] = [r for r in rows if r["id"] not in handled] + [
        {"id": e["id"], "title": " ".join(e["title"].split())[:200], "feed": e["feed"]["title"],
         "score": None if s is None else round(s, 3), "decision": decision, "date": today}
        for e, decision, s in decided]
    state["last_id"] = max(handled | {state.get("last_id") or 0})
    state["last_run"] = now.isoformat()


def prune(state, rows, today):
    """Drop day counters and decision rows older than KEEP_DAYS, and keep at most MAX_ROWS rows."""
    first = (today - dt.timedelta(days=KEEP_DAYS - 1)).isoformat()
    if "days" in state:
        state["days"] = {d: c for d, c in sorted(state["days"].items()) if d >= first}
    rows[:] = [r for r in rows if r["date"] >= first][-MAX_ROWS:]


def spread(rows, n):
    """n rows evenly spaced over a list (all of it when shorter)."""
    if len(rows) <= n:
        return list(rows)
    return [rows[round(i * (len(rows) - 1) / (n - 1))] for i in range(n)]


def cell(s):
    return " ".join(str(s).split()).replace("|", "\\|").replace("[[", "[ [")


def table(rows, decision=False):
    if not rows:
        return ["None.", ""]
    out = ["| Title | Feed | Score |" + (" Decision |" if decision else ""),
           "| --- | --- | ---: |" + (" --- |" if decision else "")]
    for r in rows:
        score = "n/a" if r["score"] is None else f"{r['score']:+.2f}"
        out.append(f"| {cell(r['title'])[:140]} | {cell(r['feed'])[:40]} | {score} |"
                   + (f" {r['decision']} |" if decision else ""))
    return out + [""]


def review_note(days, rows, starred_ids, cut, today):
    """The daily review note: counts, the calls worth checking, and starred entries the sorter got wrong."""
    yday = today - dt.timedelta(days=1)
    week = [(yday - dt.timedelta(days=i)).isoformat() for i in range(7)]
    keys = ["new"] + list(COUNTERS.values())

    def counts(label, dates):
        return f"| {label} | " + " | ".join(str(sum(days.get(d, {}).get(k, 0) for d in dates)) for k in keys) + " |"

    recent = [r for r in rows if r["date"] >= yday.isoformat()]
    kept = sorted((r for r in recent if r["decision"] == "keep"), key=lambda r: -r["score"])
    low = sorted((r for r in recent if r["decision"] == "low score"), key=lambda r: -r["score"])
    misses = [r for r in reversed(rows) if r["id"] in starred_ids
              and (r["decision"] in READ or (r["score"] is not None and r["score"] < cut))]
    profile = vl.wikilink(PROFILE_NOTE)
    return "\n".join([
        "---", "type: index", "status: active", "tags:", "  - system/feed-sorter", "generated: true",
        f"author: {AUTHOR}",
        "description: " + vl.yaml_str(
            f'Daily check on the feed sorter\'s calls in the Miniflux "{CATEGORY}" category: counts, the best '
            "kept entries, the marked-read ones nearest the cut-off, and starred entries it had marked read."),
        "---", "",
        "# Feed Sorter Review", "",
        f"> Generated {today.isoformat()} by the `{AUTHOR}` CronJob, once a day. Do not edit; changes are overwritten.",
        f"> To act on it, edit {profile}: add or reword an interest for something that should have been kept, "
        "add a noise bullet for something that should not. The sorter re-measures itself on its next run.", "",
        f"Entries scoring below {cut:+.2f} are marked read. Nothing is deleted: a marked-read entry is still "
        "in Miniflux's History, and starring one there lists it under Misses.", "",
        "## Counts", "",
        "| Period | New | Kept by score | Kept by watchlist | Read: low score | Read: duplicate | Read: non-English |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        counts(f"Yesterday ({yday.isoformat()})", week[:1]), counts("Last 7 days", week), "",
        "## Misses", "",
        f"Entries you starred in the last {KEEP_DAYS} days that the sorter had marked read, or scored below "
        "today's cut-off.", "", *table(misses, decision=True),
        "## Top kept", "", "The highest-scoring entries left unread since yesterday.", "", *table(kept[:15]),
        "## Borderline", "", "Marked read since yesterday, closest below the cut-off.", "", *table(low[:15]),
        "## Other marked read", "", "A sample across the rest of the scores.", "", *table(spread(low[15:], 10)),
    ])


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

    state_path, rows_path = os.path.join(VAULT, STATE), os.path.join(VAULT, DECISIONS)
    state, state_old = load(state_path, {})
    rows, rows_old = load(rows_path, [])
    digest = hashlib.sha256(json.dumps([profile["interests"], profile["noise"], READ_BELOW_PCT]).encode()).hexdigest()[:16]
    age = (now - dt.datetime.fromisoformat(state["at"])).days if state.get("at") else 999
    if state.get("profile") != digest or age >= RECALIBRATE_DAYS:
        cal = calibrate(cat, now, vs, vi, vn)
        if cal is None:
            print("feed-sorter: fewer than 50 entries in the last 30 days; too few to calibrate, nothing marked")
            return 0
        state.update(profile=digest, at=now.isoformat(), cal=cal)
        print(f"feed-sorter: calibrated on {cal['sample']} entries; cut-off {cal['cut']:+.2f} "
              f"(the {READ_BELOW_PCT:.0f}th percentile)")
        state_old = save(state_path, state_text(state), state_old)  # now: measuring is the slow part
    cal = state["cal"]

    batch, waiting = fetch_new(cat, state.get("last_id"), now)
    if not batch:
        print("feed-sorter: no new unread entries")
    else:
        # Titles of earlier entries this week (read or unread), to catch the same story posted twice.
        week = int((now - dt.timedelta(days=7)).timestamp())
        ids = {e["id"] for e in batch}
        seen = {title_key(e) for e in entries(f"categories/{cat}/entries?published_after={week}")
                if e["id"] not in ids and e["id"] < batch[-1]["id"]}
        decided = decide(batch, seen, patterns, vs, vi, vn, cal)
        kept = sorted(((s, e) for e, d, s in decided if d == "keep"), key=lambda x: -x[0])
        drop = [(e, d) for e, d, _ in decided if d in READ]
        # Titles and feeds only in the log: never the watchlist names themselves.
        for s, e in kept[:8]:
            print(f"  keep {s:+.2f}  {e['title'][:90]}  [{e['feed']['title'][:28]}]")
        for e, why in drop[:8]:
            print(f"  read ({why})  {e['title'][:80]}  [{e['feed']['title'][:28]}]")
        if drop and not vl.DRY:
            todo = [e["id"] for e, _ in drop]
            for i in range(0, len(todo), 200):
                api("entries", {"entry_ids": todo[i:i + 200], "status": "read"}, "PUT")
        record(state, rows, decided, now)  # after Miniflux took the changes: a failed run is redone
        reasons = {}
        for _, why in drop:
            reasons[why] = reasons.get(why, 0) + 1
        print(f"feed-sorter: {len(batch)} new; {len(kept)} left unread by score, "
              f"{sum(d == 'watchlist' for _, d, _ in decided)} kept by the watchlist, "
              f"{len(drop)} {'would be ' if vl.DRY else ''}marked read "
              f"({', '.join(f'{v} {k}' for k, v in sorted(reasons.items())) or 'none'})"
              + (f"; {waiting} more wait for the next run" if waiting else ""))

    today = now.astimezone(vl.TZ).date()
    prune(state, rows, today)
    if state.get("review") != today.isoformat():  # the first run of the day
        review = review_note(state.get("days", {}), rows, {e["id"] for e in starred}, cal["cut"], today)
        print(f"feed-sorter: {REVIEW}: {vl.write_if_changed(VAULT, REVIEW, review)}")
        state["review"] = today.isoformat()
        vl.request_rescan(VAULT, (os.path.dirname(REVIEW),))
    save(rows_path, rows_text(rows), rows_old)
    save(state_path, state_text(state), state_old)
    return 0


if __name__ == "__main__":
    sys.exit(main())
