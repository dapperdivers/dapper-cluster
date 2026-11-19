#!/usr/bin/env python3
"""Keep a restorable copy of the Miniflux configuration in the vault (stdlib only).

The feed reader's database holds a few hundred subscriptions plus settings that took a
long time to tune. This job copies all of it into the vault, where Syncthing and the
vault backups carry it, and writes a note about the health of the feeds.

Modes
-----
miniflux-export.py <vault> [--dry-run] [--force]
    The nightly run. Reads Miniflux with GET requests only and writes, under EXPORT_DIR
    (default System/Miniflux):
      feeds.opml            the OPML export, without its creation timestamp so it is
                            byte-identical from one night to the next when nothing changed
      miniflux-config.json  what OPML does not carry: user settings (reading preferences,
                            block/keep filter rules), category flags, and for each feed
                            (keyed by feed URL) its title, category and every option that
                            differs from the Miniflux default
    and Agents/Generated/Feed Health.md: totals, feeds with parsing errors, enabled feeds
    that went quiet, and the busiest feeds of the last week.
    Feed usernames, passwords, cookies and proxy URLs are never exported: the JSON only
    lists which of them were set ("credentials": ["password"]), to be re-entered by hand.
    Files are rewritten only when their content changed. If Miniflux suddenly has fewer
    than half the feeds of the last export (a rebuilt, empty instance), the run refuses to
    overwrite the good export and fails; --force overrides that.
    Prints counts only: feed titles and URLs never go to the job log.

miniflux-export.py --restore-plan <vault>
    Read-only. Compares the two exported files with the live Miniflux and prints what a
    restore would change: feeds and categories that are missing, and settings, category
    flags and feed options that differ. Prints feed titles and URLs, so run it from a
    terminal, not from the CronJob.

miniflux-export.py --restore <vault> --yes
    Applies that plan: creates missing categories, imports the missing feeds from
    feeds.opml (only the missing ones are sent), then sets category flags, feed options and
    user settings from miniflux-config.json. Refuses to run without --yes. It only creates
    and updates: nothing is ever deleted, and feeds or categories that exist in Miniflux
    but not in the export are left alone.

Restoring onto a fresh Miniflux
-------------------------------
 1. Log in to the new instance and create an API key (Settings -> API Keys).
 2. From any machine that has the vault (it syncs to every device) and can reach Miniflux,
    for example through `kubectl port-forward -n selfhosted svc/miniflux 8080:8080`:
        export MINIFLUX_URL=http://127.0.0.1:8080 MINIFLUX_API_KEY=<the new key>
        python3 miniflux-export.py --restore-plan <vault>      # look at what it would do
        python3 miniflux-export.py --restore <vault> --yes
        python3 miniflux-export.py --restore-plan <vault>      # should now report no differences
 3. Re-enter by hand whatever the last plan still lists: feed credentials (never exported)
    and any option the API did not accept.
 4. Put the new API key in the secret the vault jobs read, so the nightly export resumes.
    Until the restore is done the nightly run fails on purpose rather than overwrite the
    export with an empty one.

Needs MINIFLUX_URL and MINIFLUX_API_KEY; the nightly mode does nothing without them.
"""
import collections
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# The jobs run `python3 -I`, which leaves the script's own folder off sys.path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vaultlib as vl  # noqa: E402

AUTHOR = "miniflux-export"
MINIFLUX_URL = os.environ.get("MINIFLUX_URL", "").rstrip("/")
API_KEY = os.environ.get("MINIFLUX_API_KEY", "")
EXPORT_DIR = os.environ.get("EXPORT_DIR", "System/Miniflux")
OPML_REL = os.path.join(EXPORT_DIR, "feeds.opml")
CONFIG_REL = os.path.join(EXPORT_DIR, "miniflux-config.json")
HEALTH_REL = os.path.join(vl.GENERATED_DIR, "Feed Health.md")
STALE_DAYS = int(os.environ.get("FEED_STALE_DAYS", "90"))
VOLUME_DAYS = 7
PAGE = 250           # entries per request for the weekly volume count (they carry full text)
MAX_PAGES = 60       # stop counting after 15000 entries in a week
PAUSE = 0.05         # seconds between per-feed requests

# Per-feed options and the value a new Miniflux feed has. Only options that differ are
# exported, and a restore sets back only the ones that differ.
FEED_DEFAULTS = {
    "disabled": False,
    "crawler": False,
    "hide_globally": False,
    "scraper_rules": "",
    "rewrite_rules": "",
    "urlrewrite_rules": "",
    "blocklist_rules": "",
    "keeplist_rules": "",
    "block_filter_entry_rules": "",
    "keep_filter_entry_rules": "",
    "user_agent": "",
    "ignore_http_cache": False,
    "ignore_entry_updates": False,
    "allow_self_signed_certificates": False,
    "fetch_via_proxy": False,
    "no_media_player": False,
    "disable_http2": False,
    "apprise_service_urls": "",
    "webhook_url": "",
    "ntfy_enabled": False,
    "ntfy_priority": 3,
    "ntfy_topic": "",
    "pushover_enabled": False,
    "pushover_priority": 0,
}
# Never exported: only the names of the ones that are set.
FEED_SECRETS = ("username", "password", "cookie", "proxy_url")
# Feed fields that are state, identity or already in the OPML: nothing to export.
FEED_IGNORED = {
    "id", "user_id", "feed_url", "site_url", "title", "description", "category", "icon",
    "checked_at", "next_check_at", "etag_header", "last_modified_header", "language",
    "parsing_error_count", "parsing_error_message",
}
# /v1/me keys that identify the account or its logins rather than configure the reader.
USER_SKIP = re.compile(r"(^id$|_id$|username|password|login|admin|token|secret|session|api_key)")

_writes_allowed = False  # only --restore --yes turns this on


def api(path, method="GET", body=None, raw=False, content_type="application/json", timeout=60):
    if method != "GET" and not _writes_allowed:
        raise RuntimeError(f"refusing {method} {path}: this mode is read-only")
    data = None
    headers = {"X-Auth-Token": API_KEY}
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        headers["Content-Type"] = content_type
    req = urllib.request.Request(MINIFLUX_URL + "/v1/" + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read()
    if raw:
        return payload
    return json.loads(payload) if payload.strip() else None


# ---------------------------------------------------------------- export: pure helpers

def normalise_opml(text):
    """Drop the export timestamp, the only part that changes when the feeds did not."""
    text = re.sub(r"[ \t]*<dateCreated>[^<]*</dateCreated>[ \t]*\r?\n?", "", text)
    return text.rstrip("\n") + "\n"


def opml_feed_urls(text):
    return [o.get("xmlUrl") for o in ET.fromstring(text.encode()).iter("outline") if o.get("xmlUrl")]


def filter_opml(text, keep_urls):
    """The same OPML holding only the feeds in keep_urls (empty categories dropped)."""
    for prefix, uri in re.findall(r'xmlns:(\w+)="([^"]+)"', text):
        ET.register_namespace(prefix, uri)
    root = ET.fromstring(text.encode())
    keep = set(keep_urls)

    def prune(node):
        for child in list(node):
            if child.tag != "outline":
                continue
            if child.get("xmlUrl"):
                if child.get("xmlUrl") not in keep:
                    node.remove(child)
            else:
                prune(child)
                if not any(c.tag == "outline" for c in child):
                    node.remove(child)

    body = root.find("body")
    if body is not None:
        prune(body)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def user_settings(me):
    return {k: v for k, v in sorted(me.items())
            if not USER_SKIP.search(k) and isinstance(v, (str, int, float, bool))}


def feed_config(feed):
    """Title, category, the options that differ from the defaults, and which secrets are set.
    For example {"title": "Example Blog", "category": "Tech", "crawler": true}."""
    out = {"title": feed.get("title", ""), "category": (feed.get("category") or {}).get("title", "")}
    for key, default in FEED_DEFAULTS.items():
        if key in feed and feed[key] != default:
            out[key] = feed[key]
    creds = [k for k in FEED_SECRETS if feed.get(k)]
    if creds:
        out["credentials"] = creds
    return out


def build_config(me, categories, feeds, version=""):
    return {
        "format": 1,
        "miniflux_version": version,
        "user": user_settings(me),
        "categories": sorted(({"title": c["title"], "hide_globally": bool(c.get("hide_globally"))}
                              for c in categories), key=lambda c: c["title"]),
        "feeds": {f["feed_url"]: feed_config(f) for f in sorted(feeds, key=lambda f: f["feed_url"])},
    }


def unknown_feed_fields(feeds):
    known = set(FEED_DEFAULTS) | set(FEED_SECRETS) | FEED_IGNORED
    return sorted({k for f in feeds for k in f} - known)


def dump_config(cfg):
    return json.dumps(cfg, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------- restore: pure helpers

def diff_config(saved, opml_urls, live):
    """What a restore would change. `saved` and `live` are build_config() results; opml_urls
    are the feed URLs in the saved OPML (the only feeds that can be imported)."""
    live_cats = {c["title"]: c for c in live["categories"]}
    plan = {
        "missing_feeds": [u for u in sorted(set(opml_urls)) if u not in live["feeds"]],
        "not_in_opml": [u for u in sorted(saved["feeds"]) if u not in live["feeds"] and u not in set(opml_urls)],
        "missing_categories": [c["title"] for c in saved["categories"] if c["title"] not in live_cats],
        "category_flags": {},   # title -> wanted hide_globally
        "feed_options": {},     # feed url -> {option: [have, want]}
        "credentials": {},      # feed url -> [names to re-enter by hand]
        "user": {},             # setting -> [have, want]
        "extra_feeds": len([u for u in live["feeds"] if u not in saved["feeds"]]),
    }
    for c in saved["categories"]:
        have = live_cats.get(c["title"])
        if have is not None and bool(have.get("hide_globally")) != bool(c.get("hide_globally")):
            plan["category_flags"][c["title"]] = bool(c.get("hide_globally"))
    for url, want in saved["feeds"].items():
        have = live["feeds"].get(url)
        if have is None:
            continue
        changes = {}
        for key in ["title", "category"] + list(FEED_DEFAULTS):
            default = FEED_DEFAULTS.get(key, "")
            w, h = want.get(key, default), have.get(key, default)
            if w != h:
                changes[key] = [h, w]
        if changes:
            plan["feed_options"][url] = changes
        lost = [c for c in want.get("credentials", []) if c not in have.get("credentials", [])]
        if lost:
            plan["credentials"][url] = lost
    for key, want in saved["user"].items():
        if key in live["user"] and live["user"][key] != want:
            plan["user"][key] = [live["user"][key], want]
    return plan


def plan_size(plan):
    """Number of things a restore would create or change (credentials are manual: not counted)."""
    return (len(plan["missing_feeds"]) + len(plan["missing_categories"]) + len(plan["category_flags"])
            + sum(len(v) for v in plan["feed_options"].values()) + len(plan["user"]))


def short(v, n=60):
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[:n - 1] + "…"


def print_plan(plan, saved):
    def name(url):
        return f"{saved['feeds'].get(url, {}).get('title', '?')} <{url}>"

    if plan["missing_categories"]:
        print(f"Categories to create ({len(plan['missing_categories'])}):")
        for t in plan["missing_categories"]:
            print(f"  + {t}")
    if plan["missing_feeds"]:
        print(f"Feeds to import from the OPML ({len(plan['missing_feeds'])}):")
        for u in plan["missing_feeds"]:
            print(f"  + {name(u)}")
    if plan["not_in_opml"]:
        print(f"Feeds in the JSON but not in the OPML, cannot be imported ({len(plan['not_in_opml'])}):")
        for u in plan["not_in_opml"]:
            print(f"  ! {name(u)}")
    if plan["category_flags"]:
        print(f"Category flags to set ({len(plan['category_flags'])}):")
        for t, want in plan["category_flags"].items():
            print(f"  ~ {t}: hide_globally -> {short(want)}")
    if plan["feed_options"]:
        print(f"Feeds with options to set ({len(plan['feed_options'])}):")
        for u, changes in plan["feed_options"].items():
            print(f"  ~ {name(u)}")
            for k, (have, want) in changes.items():
                print(f"      {k}: {short(have)} -> {short(want)}")
    if plan["user"]:
        print(f"User settings to set ({len(plan['user'])}):")
        for k, (have, want) in plan["user"].items():
            print(f"  ~ {k}: {short(have)} -> {short(want)}")
    if plan["credentials"]:
        print(f"Feed credentials to re-enter by hand, never exported ({len(plan['credentials'])}):")
        for u, names in plan["credentials"].items():
            print(f"  ! {name(u)}: {', '.join(names)}")
    if plan["extra_feeds"]:
        print(f"{plan['extra_feeds']} feed(s) in Miniflux are not in the export; they are left alone.")
    n = plan_size(plan)
    print(f"restore plan: {n} difference(s)" if n else "restore plan: no differences")
    return n


def feed_update_body(changes, category_ids):
    """PUT /v1/feeds/{id} body for one feed's changes; None when its category is unknown."""
    body = {}
    for key, (_, want) in changes.items():
        if key == "category":
            if want not in category_ids:
                return None
            body["category_id"] = category_ids[want]
        else:
            body[key] = want
    return body


# ---------------------------------------------------------------- live state

def fetch_live():
    me, cats, feeds = api("me"), api("categories"), api("feeds")
    try:
        version = api("version").get("version", "")
    except Exception:
        version = ""
    return me, cats, feeds, version


def parse_time(s):
    s = re.sub(r"\.\d+", "", (s or "").replace("Z", "+00:00"))
    try:
        t = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def weekly_volume(now):
    """Entries published per feed over the last VOLUME_DAYS days, in a few paged requests."""
    after = int((now - dt.timedelta(days=VOLUME_DAYS)).timestamp())
    counts, seen, capped = collections.Counter(), 0, False
    for page in range(MAX_PAGES):
        data = api(f"entries?published_after={after}&order=published_at&direction=desc"
                   f"&limit={PAGE}&offset={page * PAGE}", timeout=120)
        entries = data.get("entries") or []
        for e in entries:
            counts[e["feed_id"]] += 1
        seen += len(entries)
        if not entries or seen >= data.get("total", 0):
            break
    else:
        capped = True
    return counts, capped


def newest_entries(feeds, volume):
    """Newest entry time per enabled feed that published nothing this week: one small request
    each. A feed with entries this week is fresh and needs no request. Value None = no entries."""
    newest, failed = {}, 0
    for f in feeds:
        if f.get("disabled") or volume.get(f["id"]):
            continue
        try:
            data = api(f"feeds/{f['id']}/entries?limit=1&order=published_at&direction=desc")
            entries = data.get("entries") or []
            newest[f["id"]] = parse_time(entries[0].get("published_at")) if entries else None
        except Exception:
            failed += 1
        time.sleep(PAUSE)
    return newest, failed


# ---------------------------------------------------------------- health note

def cell(s, n=200):
    s = " ".join(str(s).split()).replace("|", "\\|").replace("[[", "[ [")
    return s if len(s) <= n else s[:n - 1] + "…"


def render_health(today, feeds, categories, unread, volume, newest, now, capped=False, unchecked=0):
    by_id = {f["id"]: f for f in feeds}
    enabled = [f for f in feeds if not f.get("disabled")]

    def cat(f):
        return (f.get("category") or {}).get("title", "")

    errors = sorted((f for f in feeds if f.get("parsing_error_count")),
                    key=lambda f: (-f["parsing_error_count"], f["title"].lower()))
    cutoff = now - dt.timedelta(days=STALE_DAYS)
    stale = sorted(((newest[f["id"]], f) for f in enabled if newest.get(f["id"]) and newest[f["id"]] < cutoff),
                   key=lambda p: (p[0], p[1]["title"].lower()))
    empty = sorted((f for f in enabled if f["id"] in newest and newest[f["id"]] is None),
                   key=lambda f: f["title"].lower())
    top = sorted(((n, by_id[i]) for i, n in volume.items() if i in by_id),
                 key=lambda p: (-p[0], p[1]["title"].lower()))[:10]

    out = [
        "---",
        "type: index\nstatus: active\ntags:\n  - meta/generated",
        f"generated: true\nauthor: {AUTHOR}",
        "description: " + vl.yaml_str("Health of the Miniflux feeds: totals, feeds with parsing errors, feeds that "
                                      "went quiet and the busiest feeds of the week. Regenerated nightly by a cluster CronJob."),
        "---",
        "# Feed Health\n",
        f"> Generated {today.isoformat()} by the `{AUTHOR}` CronJob from the Miniflux API. Do not edit; changes are overwritten.",
        f"> The full configuration is exported beside it in `{EXPORT_DIR}/`.\n",
        "## Totals\n",
        f"- Feeds: {len(feeds)} ({len(enabled)} enabled, {len(feeds) - len(enabled)} disabled)",
        f"- Categories: {len(categories)}",
        f"- Unread entries: {unread}",
        f"- Entries published in the last {VOLUME_DAYS} days: {sum(volume.values())}{'+ (count capped)' if capped else ''}",
        "",
        f"## Parsing errors ({len(errors)})\n",
    ]
    if errors:
        out += ["| Feed | Category | Errors | Message |", "| --- | --- | --- | --- |"]
        out += [f"| {cell(f['title'])} | {cell(cat(f))} | {f['parsing_error_count']} | {cell(f.get('parsing_error_message', ''))} |"
                for f in errors]
    else:
        out.append("- (none)")
    out += ["", f"## Quiet feeds: newest entry older than {STALE_DAYS} days ({len(stale)})\n"]
    if stale:
        out += ["| Feed | Category | Newest entry |", "| --- | --- | --- |"]
        out += [f"| {cell(f['title'])} | {cell(cat(f))} | {t.astimezone(vl.TZ).date().isoformat()} |" for t, f in stale]
    else:
        out.append("- (none)")
    out += ["", f"## Enabled feeds with no entries ({len(empty)})\n"]
    out += [f"- {cell(f['title'])} ({cell(cat(f))})" for f in empty] or ["- (none)"]
    if unchecked:
        out += ["", f"*{unchecked} feed(s) could not be checked this run.*"]
    out += ["", f"## Busiest feeds, last {VOLUME_DAYS} days\n"]
    if top:
        out += ["| Feed | Category | Entries |", "| --- | --- | --- |"]
        out += [f"| {cell(f['title'])} | {cell(cat(f))} | {n} |" for n, f in top]
    else:
        out.append("- (none)")
    out += [
        "",
        "## How to restore\n",
        f"`{OPML_REL}` (subscriptions) and `{CONFIG_REL}` (settings, category flags, per-feed options) "
        "are a full copy of the Miniflux configuration. To rebuild: create an API key on the new instance, "
        "then run `miniflux-export.py --restore-plan <vault>` to see what would change and "
        "`miniflux-export.py --restore <vault> --yes` to apply it. The script and the full procedure "
        "are in the cluster repo under `kubernetes/apps/selfhosted/obsidian-vault/app/resources/`. "
        "Feed usernames, passwords and cookies are not exported and must be re-entered by hand.",
    ]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- modes

def read_file(vault, rel):
    try:
        with open(os.path.join(vault, rel), encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def write_file_if_changed(vault, rel, content):
    if read_file(vault, rel) == content:
        return "unchanged"
    if vl.DRY:
        return "would write"
    vl.atomic_write(os.path.join(vault, rel), content)
    return "written"


def export(vault):
    if not MINIFLUX_URL or not API_KEY:
        print("miniflux-export: MINIFLUX_URL / MINIFLUX_API_KEY not set; nothing to do")
        return 0
    if not vl.vault_ready(vault):
        return 0
    me, cats, feeds, version = fetch_live()
    opml = normalise_opml(api("export", raw=True).decode("utf-8"))
    cfg = build_config(me, cats, feeds, version)

    old = read_file(vault, CONFIG_REL)
    try:
        had = len(json.loads(old)["feeds"]) if old else 0
    except (ValueError, KeyError, TypeError):
        had = 0
    if had >= 10 and len(feeds) * 2 < had and "--force" not in sys.argv:
        print(f"miniflux-export: Miniflux has {len(feeds)} feeds but the last export has {had}; refusing to "
              "overwrite it (rebuilt instance? see --restore-plan). Use --force if the drop is intended.",
              file=sys.stderr)
        return 1
    extra = unknown_feed_fields(feeds)
    if extra:  # field names only: a newer Miniflux has options this script does not export yet
        print(f"warning: feed fields not exported (unknown to this script): {', '.join(extra)}", file=sys.stderr)

    now = dt.datetime.now(dt.timezone.utc)
    volume, capped = weekly_volume(now)
    newest, unchecked = newest_entries(feeds, volume)
    counters = api("feeds/counters") or {}
    unread = sum((counters.get("unreads") or {}).values())
    note = render_health(dt.datetime.now(vl.TZ).date(), feeds, cats, unread, volume, newest, now, capped, unchecked)

    results = {
        "feeds.opml": write_file_if_changed(vault, OPML_REL, opml),
        "miniflux-config.json": write_file_if_changed(vault, CONFIG_REL, dump_config(cfg)),
        "Feed Health.md": vl.write_if_changed(vault, HEALTH_REL, note),
    }
    if "written" in results.values():
        vl.request_rescan(vault, (EXPORT_DIR, vl.GENERATED_DIR))
    cutoff = now - dt.timedelta(days=STALE_DAYS)
    quiet = sum(1 for t in newest.values() if t is None or t < cutoff)
    errors = sum(1 for f in feeds if f.get("parsing_error_count"))
    print(f"miniflux-export: exported {len(feeds)} feeds, {len(cats)} categories; {errors} feeds with errors, "
          f"{quiet} quiet or empty" + (f", {unchecked} not checked" if unchecked else "")
          + "; " + ", ".join(f"{k} {v}" for k, v in results.items()))
    return 0


def load_export(vault):
    opml, raw = read_file(vault, OPML_REL), read_file(vault, CONFIG_REL)
    if opml is None or raw is None:
        sys.exit(f"miniflux-export: {OPML_REL} and {CONFIG_REL} must both exist in {vault}")
    saved = json.loads(raw)
    if saved.get("format") != 1:
        sys.exit(f"miniflux-export: unknown export format {saved.get('format')!r}")
    return opml, saved


def current_plan(saved, opml):
    me, cats, feeds, version = fetch_live()
    plan = diff_config(saved, opml_feed_urls(opml), build_config(me, cats, feeds, version))
    return plan, me, cats, feeds


def restore_plan(vault):
    opml, saved = load_export(vault)
    plan, *_ = current_plan(saved, opml)
    print_plan(plan, saved)
    return 0


def restore(vault):
    global _writes_allowed
    if "--yes" not in sys.argv:
        print("miniflux-export: --restore changes the live Miniflux. Look at --restore-plan first, "
              "then run it again with --yes.", file=sys.stderr)
        return 2
    opml, saved = load_export(vault)
    plan, me, cats, feeds = current_plan(saved, opml)
    if not plan_size(plan):
        print_plan(plan, saved)
        return 0
    _writes_allowed = True
    failed = 0

    def attempt(what, fn):
        nonlocal failed
        try:
            fn()
            return True
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:200]
            print(f"  failed: {what}: HTTP {e.code} {detail}", file=sys.stderr)
        except Exception as e:
            print(f"  failed: {what}: {e}", file=sys.stderr)
        failed += 1
        return False

    wanted_flags = {c["title"]: bool(c.get("hide_globally")) for c in saved["categories"]}
    for title in plan["missing_categories"]:
        attempt(f"create category {title}", lambda t=title: api(
            "categories", "POST", {"title": t, "hide_globally": wanted_flags.get(t, False)}))
    print(f"created {len(plan['missing_categories'])} categories")

    if plan["missing_feeds"]:
        body = filter_opml(opml, plan["missing_feeds"]).encode("utf-8")
        attempt("OPML import", lambda: api("import", "POST", body, content_type="application/xml", timeout=600))
        print(f"sent {len(plan['missing_feeds'])} feeds to the OPML import")

    # Everything below works on what exists now, ids included.
    plan, me, cats, feeds = current_plan(saved, opml)
    cat_ids = {c["title"]: c["id"] for c in cats}
    feed_ids = {f["feed_url"]: f["id"] for f in feeds}

    for title, want in plan["category_flags"].items():
        attempt(f"category {title}", lambda t=title, w=want: api(
            f"categories/{cat_ids[t]}", "PUT", {"title": t, "hide_globally": w}))
    for url, changes in plan["feed_options"].items():
        body = feed_update_body(changes, cat_ids)
        if body is None:
            print(f"  failed: feed {url}: its category does not exist", file=sys.stderr)
            failed += 1
            continue
        attempt(f"feed {url}", lambda u=url, b=body: api(f"feeds/{feed_ids[u]}", "PUT", b))
        time.sleep(PAUSE)
    if plan["user"]:
        body = {k: want for k, (_, want) in plan["user"].items()}
        attempt("user settings", lambda: api(f"users/{me['id']}", "PUT", body))
    print(f"updated {len(plan['category_flags'])} category flags, {len(plan['feed_options'])} feeds, "
          f"{len(plan['user'])} user settings")

    _writes_allowed = False
    plan, *_ = current_plan(saved, opml)
    print("\nAfter the restore (anything still listed did not take and needs doing by hand):")
    left = print_plan(plan, saved)
    return 1 if failed or left else 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    vault = args[0] if args else "/vault"
    if "--restore" in sys.argv or "--restore-plan" in sys.argv:
        if not MINIFLUX_URL or not API_KEY:
            sys.exit("miniflux-export: set MINIFLUX_URL and MINIFLUX_API_KEY")
        return restore(vault) if "--restore" in sys.argv else restore_plan(vault)
    return export(vault)


if __name__ == "__main__":
    sys.exit(main())
