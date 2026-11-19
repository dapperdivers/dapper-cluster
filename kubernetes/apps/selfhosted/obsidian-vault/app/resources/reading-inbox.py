#!/usr/bin/env python3
"""Turn starred Miniflux articles into vault notes (stdlib only).

Starring an article in the feed reader (key `f`) is the owner's "keep this" signal. This
job lists the starred entries and writes one note per new one under READING_DIR, with the
link, the feed and the article text, so it can be read, filed and linked like any note.
It only reads from Miniflux (GET requests): nothing is unstarred or marked read.

A ledger of entry ids already written lives beside the notes, so a note that was filed
elsewhere or deleted is not written again. Does nothing unless MINIFLUX_URL and
MINIFLUX_API_KEY are set.

Usage: reading-inbox.py <vault-dir> [--dry-run]
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser

import vaultlib as vl

VAULT = sys.argv[1] if len(sys.argv) > 1 else "/vault"
MINIFLUX_URL = os.environ.get("MINIFLUX_URL", "").rstrip("/")
API_KEY = os.environ.get("MINIFLUX_API_KEY", "")
READING_DIR = os.environ.get("READING_DIR", "Inbox/Reading")
LEDGER = os.path.join(READING_DIR, "ledger.json")
MAX_PER_RUN = int(os.environ.get("READING_PER_RUN", "20"))
MAX_CHARS = int(os.environ.get("READING_MAX_CHARS", "40000"))
SHORT = 1500  # below this the feed only carried a teaser: fetch the page instead

BLOCK = {"p", "div", "section", "article", "blockquote", "ul", "ol", "table", "tr", "figure", "pre"}
SKIP = {"script", "style", "noscript", "svg", "iframe", "form", "button", "nav"}


def api(path, timeout=45):
    req = urllib.request.Request(MINIFLUX_URL + "/v1/" + path, headers={"X-Auth-Token": API_KEY})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


class Text(HTMLParser):
    """HTML to plain Markdown-ish text: headings, paragraphs, list items and links only."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.href, self.pre = [], 0, None, 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        elif self.skip:
            return
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.out.append("\n\n" + "#" * min(int(tag[1]) + 1, 6) + " ")
        elif tag == "li":
            self.out.append("\n- ")
        elif tag == "br":
            self.out.append("\n")
        elif tag == "pre":
            self.pre += 1
            self.out.append("\n\n```\n")
        elif tag in BLOCK:
            self.out.append("\n\n")
        elif tag == "a":
            self.href = dict(attrs).get("href")
            if self.href:
                self.out.append("[")

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        elif self.skip:
            return
        elif tag == "pre" and self.pre:
            self.pre -= 1
            self.out.append("\n```\n\n")
        elif tag == "a" and self.href:
            self.out.append(f"]({self.href})")
            self.href = None
        elif tag in BLOCK or tag.startswith("h"):
            self.out.append("\n\n")

    def handle_data(self, data):
        if self.skip:
            return
        self.out.append(data if self.pre else re.sub(r"\s+", " ", data))


def to_text(content):
    p = Text()
    try:
        p.feed(content or "")
        p.close()
    except Exception:  # malformed markup: fall back to stripping tags
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", content or ""))).strip()
    text = "".join(p.out)
    text = re.sub(r"\[\s*\]\([^)]*\)", "", text)  # links that wrapped only an image
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def safe_name(title):
    name = re.sub(r'[\\/:*?"<>|#^\[\]]', " ", title or "Untitled")
    name = " ".join(name.split())[:90].rstrip(" .")
    return name or "Untitled"


def note_for(entry, text, truncated):
    feed = entry.get("feed") or {}
    cat = (feed.get("category") or {}).get("title", "")
    published = (entry.get("published_at") or "")[:10]
    now = dt.datetime.now(vl.TZ).replace(microsecond=0).isoformat()
    title = " ".join((entry.get("title") or "Untitled").split())
    tag = re.sub(r"[^a-z0-9]+", "-", cat.lower()).strip("-")
    tags = ["reading"] + ([f"reading/{tag}"] if tag else [])
    fm = [
        "---",
        f"created: {now}",
        "type: article",
        "source: miniflux",
        "status: inbox",
        f"url: {vl.yaml_str(entry.get('url', ''))}",
        f"feed: {vl.yaml_str(feed.get('title', ''))}",
        f"category: {vl.yaml_str(cat)}",
        f"published: {published}",
        f"miniflux_id: {entry['id']}",
        f"tags: [{', '.join(tags)}]",
        f"description: {vl.yaml_str('Article starred in Miniflux: ' + title + ' (' + feed.get('title', '') + ').')}",
        "---",
        "",
        f"# {title}",
        "",
        f"> [Original]({entry.get('url', '')}) · {feed.get('title', '')}"
        + (f" · {published}" if published else "")
        + (f" · {entry['author']}" if entry.get("author") else ""),
        "",
        "## My notes",
        "",
        "",
        "## Article",
        "",
        text or "*(The feed carried no text for this article; open the original.)*",
    ]
    if truncated:
        fm += ["", f"*(Cut at {MAX_CHARS} characters; the rest is at the original link.)*"]
    return "\n".join(fm) + "\n"


def main():
    if not MINIFLUX_URL or not API_KEY:
        print("reading-inbox: MINIFLUX_URL / MINIFLUX_API_KEY not set; nothing to do")
        return 0
    if not vl.vault_ready(VAULT):
        return 0
    ledger_path = os.path.join(VAULT, LEDGER)
    try:
        with open(ledger_path, encoding="utf-8") as fh:
            ledger = json.load(fh)
    except (FileNotFoundError, ValueError):
        ledger = {}
    entries = api("entries?starred=true&limit=200&order=changed_at&direction=desc").get("entries", [])
    new = [e for e in entries if str(e["id"]) not in ledger][:MAX_PER_RUN]
    if not new:
        print(f"reading-inbox: {len(entries)} starred, nothing new")
        return 0
    written = 0
    for e in reversed(new):  # oldest star first, so the ledger order follows the reading order
        text = to_text(e.get("content"))
        if len(text) < SHORT:
            try:  # read-only: without update_content Miniflux does not save what it fetched
                fetched = to_text(api(f"entries/{e['id']}/fetch-content").get("content"))
                if len(fetched) > len(text):
                    text = fetched
            except Exception as err:
                print(f"warning: could not fetch the page for entry {e['id']}: {err}", file=sys.stderr)
        truncated = len(text) > MAX_CHARS
        if truncated:
            text = text[:MAX_CHARS].rsplit("\n", 1)[0]
        day = dt.datetime.now(vl.TZ).strftime("%Y-%m-%d")
        rel = os.path.join(READING_DIR, f"{day} {safe_name(e.get('title'))}.md")
        if os.path.exists(os.path.join(VAULT, rel)):
            rel = rel[:-3] + f" ({e['id']}).md"
        print(f"{'would write' if vl.DRY else 'writing'}: {rel} ({len(text)} chars)")
        vl.atomic_write(os.path.join(VAULT, rel), note_for(e, text, truncated))
        ledger[str(e["id"])] = rel
        written += 1
    vl.atomic_write(ledger_path, json.dumps(ledger, indent=1, sort_keys=True) + "\n")
    if written:
        vl.request_rescan(VAULT, (READING_DIR,))
    print(f"reading-inbox: {written} new note(s) from {len(entries)} starred")
    return 0


if __name__ == "__main__":
    sys.exit(main())
