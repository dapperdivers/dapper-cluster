#!/usr/bin/env python3
"""Nightly vault health check -> <OUTPUT_DIR>/Vault Health.md

Fixes only what has exactly one right answer:
  - stale *.tmp files (interrupted atomic writes) older than an hour
  - path-qualified wikilinks whose folder moved, when the note name is unique in the vault
Everything else is reported. Items not in the previous report are marked 🆕, so the
weekly review can surface what's new. "Needs attention" holds problems that mean data is
diverging or at risk (sync conflicts, sync/backup failures, broken frontmatter in notes
edited in the last few days, voice recordings that failed to process).

Optional integrations (skipped when unset):
  SYNCTHING_URL + SYNCTHING_API_KEY  hub folder errors, peers' last-seen and completion
  in-cluster service account          volsync ReplicationSource freshness for this vault

Usage: health.py <vault-dir> [--dry-run]
"""
import datetime as dt
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vaultlib as vl  # noqa: E402

VAULT = sys.argv[1] if len(sys.argv) > 1 else "/vault"
VAULT_NAME = os.path.basename(os.path.normpath(VAULT))
OUT_REL = os.path.join(vl.GENERATED_DIR, "Vault Health.md")
AUTHOR = "vault-health"
NOW = dt.datetime.now(vl.TZ)
PEER_STALE_DAYS = float(os.environ.get("PEER_STALE_DAYS", "3"))
RECENT_DAYS = 3  # broken frontmatter in notes edited this recently goes to "Needs attention"
SECTION_CAP = 150
ATTACHMENT_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".heic", ".pdf", ".mp4", ".mov",
                  ".webm", ".mp3", ".m4a", ".wav", ".ogg", ".docx", ".xlsx", ".pptx"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".ogg", ".opus", ".webm", ".flac", ".aac", ".amr", ".3gp"}
OWN_REPORTS = {"vault-health", "vault-review", "vault-snapshot"}
REPORT_SKIP = ("Archive/Briefings/", "Briefings/")  # historical generated notes: don't lint

WIKILINK = re.compile(r"(!?)\[\[([^\[\]\|#\^\n]*)((?:[#\^][^\]\|\n]*)?)(\\?\|[^\]\n]*)?\]\]")
CODE = re.compile(r"```.*?```|~~~.*?~~~|`[^`\n]*`", re.S)


def ago(ts):
    d = NOW - ts
    if d.days >= 1:
        return f"{d.days}d ago"
    return f"{int(d.total_seconds() // 3600)}h ago"


# ---------------------------------------------------------------- file index + links

def build_index():
    paths, names, dirs = set(), {}, set()
    files = []
    for rel, path in vl.walk(VAULT, skip=vl.SKIP_DIRS - {"Templates"}):
        files.append((rel, path))
        low = rel.lower()
        paths.add(low)
        d = os.path.dirname(low)
        while d and d not in dirs:
            dirs.add(d)
            d = os.path.dirname(d)
        key = os.path.basename(low)
        if key.endswith(".md"):
            paths.add(low[:-3])
            key = key[:-3]
        names.setdefault(key, []).append(rel)
    return files, (paths, names, dirs)


def resolve(target, note_rel, idx):
    """Does Obsidian resolve this link target? (exact path, relative path, unique-suffix, or name)"""
    paths, names, dirs = idx
    t = target.strip().lower()
    if not t:
        return True  # [[#heading]] inside the same note
    if t.endswith("/"):
        return t.strip("/") in dirs  # folder link (folder-notes style)
    if t.startswith(("./", "../")):
        t = os.path.normpath(os.path.join(os.path.dirname(note_rel.lower()), t))
    t = t.lstrip("/")
    if t in paths or t + ".md" in paths:
        return True
    if "/" not in t:
        return t in names or t.removesuffix(".md") in names
    suffix = "/" + t
    return any(p.endswith(suffix) or p.endswith(suffix + ".md") for p in paths)


def link_targets(text):
    for m in WIKILINK.finditer(CODE.sub("", text)):
        yield m, m.group(2).rstrip("\\")


DATED = re.compile(r"^\d{4}-\d{2}(-\d{2})?\b")


def fix_moved_links(rel, path, idx):
    """Repoint [[Old/Folder/Some Note]] when exactly one note named "Some Note" exists.

    Date-named notes (2026-02-01, 2026-03 ...) are never repointed: the same date names a
    journal entry, a briefing and a check, so a unique name match there proves nothing.
    """
    names = idx[1]
    fixes = []

    def sub(m):
        bang, target, sub_, alias = m.groups()
        t = target.rstrip("\\")
        if "/" not in t or t.endswith("/") or resolve(t, rel, idx):
            return m.group(0)
        base = os.path.basename(t).lower()
        hits = names.get(base.removesuffix(".md"), [])
        if len(hits) != 1 or DATED.match(base) or hits[0] == rel:
            return m.group(0)
        new = hits[0][:-3] if hits[0].endswith(".md") and not t.endswith(".md") else hits[0]
        fixes.append(f"{vl.wikilink(rel)}: `{t}` → `{new}`")
        return f"{bang}[[{new}{target[len(t):]}{sub_ or ''}{alias or ''}]]"

    def transform(s):  # rewrite outside code spans/blocks only
        out, pos = [], 0
        for c in CODE.finditer(s):
            out += [WIKILINK.sub(sub, s[pos:c.start()]), c.group(0)]
            pos = c.end()
        return "".join(out) + WIKILINK.sub(sub, s[pos:])

    changed = vl.safe_edit(path, transform, min_age_s=3600)
    return fixes if changed else []


# ---------------------------------------------------------------- frontmatter lint

def lint_frontmatter(text):
    """Problems a YAML parser (and Obsidian's Properties view) would choke on."""
    if not text.startswith("---\n"):
        return None  # no frontmatter: reported separately
    fm, _, _ = vl.split_frontmatter(text)
    if fm is None:
        return "frontmatter is never closed with `---`"
    seen = set()
    for i, line in enumerate(fm.split("\n"), 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" in line[: len(line) - len(line.lstrip())]:
            return f"line {i}: tab indentation"
        if line[0] in " -":
            continue  # list item / nested value
        m = re.match(r"^([^\s#][^:]*?):(?:\s+(.*))?$", line)
        if not m:
            return f"line {i}: not a `key: value` line"
        key, val = m.group(1), (m.group(2) or "").strip()
        if key in seen:
            return f"line {i}: duplicate key `{key}`"
        seen.add(key)
        if not val:
            continue
        q = val[0]
        if q in "\"'":
            closed = re.match(r'^"(?:[^"\\]|\\.)*"\s*(#.*)?$', val) if q == '"' else \
                re.match(r"^'(?:[^']|'')*'\s*(#.*)?$", val)
            if not closed:
                return f"line {i}: `{key}` has an unclosed or stray quote"
        elif q in "[{":
            if val[-1] != ("]" if q == "[" else "}"):
                return f"line {i}: `{key}` has an unclosed `{q}`"
        elif q in "@`%*":
            return f"line {i}: `{key}` starts with reserved character `{q}`"
        elif re.search(r":\s", val) and not val.startswith(("http://", "https://")):
            return f"line {i}: `{key}` value contains `: `; quote it"
    return None


def body_len(text):
    _, body, _ = vl.split_frontmatter(text)
    return len(re.sub(r"[\s#>*\-_|]+", "", body))


# ---------------------------------------------------------------- integrations

def http_json(url, headers=None, ctx=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read())


def check_syncthing(attention):
    """Rows for the sync table; problems appended to attention."""
    base, key = os.environ.get("SYNCTHING_URL"), os.environ.get("SYNCTHING_API_KEY")
    if not base or not key:
        return ["| (not configured) | | |"]
    h = {"X-API-Key": key}
    get = lambda p: http_json(base.rstrip("/") + p, h)  # noqa: E731
    try:
        me = get("/rest/system/status")["myID"]
        folder = next((f for f in get("/rest/config/folders")
                       if os.path.basename(os.path.normpath(f["path"])) == VAULT_NAME), None)
        if not folder:
            attention.append(f"Syncthing hub has no folder for `{VAULT_NAME}`")
            return []
        fid = urllib.parse.quote(folder["id"])
        st = get(f"/rest/db/status?folder={fid}")
        errs = get(f"/rest/folder/errors?folder={fid}").get("errors") or []
        rows = [f"| hub folder `{folder['id']}` | {st.get('state', '?')} | {len(errs)} errors, "
                f"{st.get('needFiles', 0)} files needed |"]
        if errs:
            attention.append(f"Syncthing hub folder `{folder['id']}` has {len(errs)} errors, e.g. "
                             f"`{errs[0].get('path', '')}`: {errs[0].get('error', '')}")
        names = {d["deviceID"]: d["name"] for d in get("/rest/config/devices")}
        stats, conns = get("/rest/stats/device"), get("/rest/system/connections")["connections"]
        for d in folder["devices"]:
            did = d["deviceID"]
            if did == me:
                continue
            name = names.get(did, did[:7])
            connected = conns.get(did, {}).get("connected", False)
            seen_raw = stats.get(did, {}).get("lastSeen", "")
            try:
                seen = dt.datetime.fromisoformat(seen_raw).astimezone(vl.TZ)
            except ValueError:
                seen = None
            if connected:
                comp = get(f"/rest/db/completion?folder={fid}&device={did}")
                state = f"connected, {comp.get('completion', 0):.0f}% in sync"
            else:
                state = f"offline, last seen {ago(seen)}" if seen and seen.year > 1970 else "never seen"
                if not seen or seen.year <= 1970 or (NOW - seen).days >= PEER_STALE_DAYS:
                    attention.append(f"Sync peer **{name}** hasn't connected to the hub "
                                     f"{'ever' if not seen or seen.year <= 1970 else 'since ' + seen.date().isoformat()}")
            rows.append(f"| {name} | {'online' if connected else 'offline'} | {state} |")
        return rows
    except Exception as e:
        attention.append(f"Couldn't query the Syncthing hub: {e}")
        return []


def check_backups(attention):
    sa = "/var/run/secrets/kubernetes.io/serviceaccount"
    pvc = os.environ.get("BACKUP_PVC_PREFIX", "obsidian-") + VAULT_NAME
    if not os.path.exists(f"{sa}/token"):
        return ["| (not configured) | | |"]
    try:
        ns = open(f"{sa}/namespace").read().strip()
        tok = open(f"{sa}/token").read().strip()
        ctx = ssl.create_default_context(cafile=f"{sa}/ca.crt")
        data = http_json(f"https://kubernetes.default.svc/apis/volsync.backube/v1alpha1/namespaces/{ns}/replicationsources",
                         {"Authorization": f"Bearer {tok}"}, ctx)
    except Exception as e:
        attention.append(f"Couldn't read backup status: {e}")
        return []
    rows = []
    for rs in data.get("items", []):
        if rs["spec"].get("sourcePVC") != pvc:
            continue
        name, status = rs["metadata"]["name"], rs.get("status", {})
        last = status.get("lastSyncTime")
        result = (status.get("latestMoverStatus") or {}).get("result", "")
        limit_h = 30 if name.endswith("-r2") else 3  # daily offsite vs hourly local
        when = dt.datetime.fromisoformat(last.replace("Z", "+00:00")).astimezone(vl.TZ) if last else None
        if not when or (NOW - when).total_seconds() > limit_h * 3600:
            attention.append(f"Backup `{name}` last succeeded {ago(when) if when else 'never'}")
        if result and result != "Successful":
            attention.append(f"Backup `{name}` latest run: {result}")
        rows.append(f"| `{name}` | {when.strftime('%Y-%m-%d %H:%M') if when else 'never'} | {result or '?'} |")
    if not rows:
        attention.append(f"No backups found for PVC `{pvc}`")
    return rows


# ---------------------------------------------------------------- report

def previous_items():
    try:
        with open(os.path.join(VAULT, OUT_REL), encoding="utf-8") as fh:
            return {ln[2:].removeprefix("🆕 ").strip() for ln in fh if ln.startswith("- ")}
    except FileNotFoundError:
        return set()


def main():
    if not vl.vault_ready(VAULT):
        return 0
    files, idx = build_index()
    notes = vl.load_notes(VAULT)
    fixed, attention = [], []
    sections = {k: [] for k in ("Broken links", "Frontmatter problems", "Missing frontmatter",
                                "Missing descriptions", "Empty notes", "Orphaned attachments")}

    # stale temp files + conflict copies (hidden dirs included, Syncthing internals excluded)
    for rel, path in vl.walk(VAULT, include_hidden=True):
        base = os.path.basename(rel)
        if ".sync-conflict-" in base:
            attention.append(f"Sync conflict copy `{rel}`: merge it into the original, then delete it")
        elif base.endswith(".tmp") and not base.startswith(".syncthing."):
            if NOW.timestamp() - os.path.getmtime(path) > 3600:
                if not vl.DRY:
                    os.remove(path)
                fixed.append(f"Deleted stale temp file `{rel}`")

    # voice recordings that should have been processed by now
    for rel, path in files:
        if rel.startswith("Inbox/Voice/") and os.path.splitext(rel)[1].lower() in AUDIO_EXT \
                and NOW.timestamp() - os.path.getmtime(path) > 3 * 3600:
            attention.append(f"Voice recording `{rel}` hasn't been transcribed (check the voice-inbox job logs)")

    referenced = []
    for n in notes:
        rel, text = n["rel"], n["text"]
        if rel.startswith(vl.GENERATED_DIR + os.sep) or n["fm"].get("author") in OWN_REPORTS:
            continue  # our own reports list orphan names; they don't count as references
        referenced.append(text.lower())
        if rel.startswith(REPORT_SKIP):
            continue
        # links
        broken = [t for _, t in link_targets(text) if not resolve(t, rel, idx)]
        if broken and not n["generated"]:
            fixes = fix_moved_links(rel, n["path"], idx)
            fixed += [f"Repointed link in {f}" for f in fixes]
            if fixes:
                with open(n["path"], encoding="utf-8") as fh:
                    broken = [t for _, t in link_targets(fh.read()) if not resolve(t, rel, idx)]
        for t in dict.fromkeys(broken):
            sections["Broken links"].append(f"{vl.wikilink(rel)} → `{t}`")
        # frontmatter
        problem = lint_frontmatter(text)
        if problem:
            item = f"{vl.wikilink(rel)}: {problem}"
            sections["Frontmatter problems"].append(item)
            if (NOW - n["mtime"]).days < RECENT_DAYS:
                attention.append(f"Broken frontmatter in recently edited {item}")
        elif not text.startswith("---\n") and not n["generated"] and os.path.basename(rel) != "CLAUDE.md":
            sections["Missing frontmatter"].append(vl.wikilink(rel))
        if n["generated"]:
            continue
        size = body_len(text)
        if size < 20 and os.path.basename(rel) != "CLAUDE.md":
            sections["Empty notes"].append(f"{vl.wikilink(rel)} ({size} characters)")
        elif text.startswith("---\n") and not n["description"] and os.path.basename(rel) != "CLAUDE.md" \
                and not rel.startswith("Inbox/"):
            sections["Missing descriptions"].append(vl.wikilink(rel))

    # files in Attachments/ nothing embeds (Excalidraw drawings and canvases count as references)
    for rel, path in files:
        if rel.endswith(".canvas"):
            referenced.append(open(path, encoding="utf-8", errors="ignore").read().lower())
    blob = "\n".join(referenced)
    for rel, _ in files:
        ext = os.path.splitext(rel)[1].lower()
        if ext not in ATTACHMENT_EXT or not rel.startswith("Attachments/"):  # elsewhere = filed documents
            continue
        base = os.path.basename(rel).lower()
        if base not in blob and urllib.parse.quote(base) not in blob:
            sections["Orphaned attachments"].append(f"`{rel}`")

    sync_rows = check_syncthing(attention)
    backup_rows = check_backups(attention)

    prev = previous_items()
    mark = lambda item: ("🆕 " if prev and item not in prev else "") + item  # noqa: E731
    new_count = sum(1 for items in [attention, *sections.values()] for i in items if prev and i not in prev)

    out = ["---", "type: report", "status: active", "tags:", "  - meta/generated", "generated: true",
           f"author: {AUTHOR}",
           'description: "Nightly vault health report: sync conflicts, sync and backup status, broken links, '
           'frontmatter problems, missing descriptions, empty notes and orphaned attachments."',
           f"attention: {len(attention)}", f"new_issues: {new_count}", f"fixed: {len(fixed)}",
           f"issues: {sum(len(v) for v in sections.values())}", "---", "", "# Vault Health", "",
           f"> Generated {NOW.strftime('%Y-%m-%d %H:%M')} by the `{AUTHOR}` CronJob. Do not edit; it's rewritten nightly.",
           "> 🆕 marks items that weren't in the previous report. Fix things in the notes themselves; "
           "they drop off this list on the next run.", "", "## Summary", "",
           "| Check | Count | New |", "|---|---|---|"]
    for title, items in [("Needs attention", attention), ("Fixed automatically", fixed), *sections.items()]:
        new = "" if title == "Fixed automatically" else sum(1 for i in items if prev and i not in prev)
        out.append(f"| {title} | {len(items)} | {new} |")
    out += ["", "## Needs attention", ""]
    out += [f"- {mark(i)}" for i in attention] or ["Nothing needs attention."]
    out += ["", "## Fixed automatically", ""]
    out += [f"- {i}" for i in fixed] or ["Nothing was fixed this run."]
    out += ["", "## Sync", "", "| Device | State | Detail |", "|---|---|---|", *sync_rows,
            "", "## Backups", "", "| ReplicationSource | Last success | Result |", "|---|---|---|", *backup_rows]
    for title, items in sections.items():
        out += ["", f"## {title}", ""]
        items = sorted(items, key=lambda i: (not (prev and i not in prev), i.lower()))
        out += [f"- {mark(i)}" for i in items[:SECTION_CAP]] or ["None."]
        if len(items) > SECTION_CAP:
            out.append(f"\n…and {len(items) - SECTION_CAP} more.")
    content = "\n".join(out).rstrip() + "\n"

    print(f"{OUT_REL}: {vl.write_if_changed(VAULT, OUT_REL, content)}")
    print(f"attention={len(attention)} fixed={len(fixed)} new={new_count} "
          + " ".join(f"{k.split()[0].lower()}={len(v)}" for k, v in sections.items()))
    for i in attention:
        print(f"ATTENTION: {i}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
