"""File articles from a Miniflux reader in OpenCTI as reports.

Runs from the opencti-feed-sync CronJob. Standard library only.

Nothing about what the owner follows is written here. Three things decide what
gets filed, and all three are read at run time:

  FEED_PROFILE   JSON from a Secret: a description of what is relevant, the
                 reader categories to look at, cheap pre-filter patterns and
                 the sectors a report may be linked to (see PROFILE_KEYS).
  watchlist      The organisations in OpenCTI that carry WATCH_LABEL, matched
                 by name and alias.
  themes         The OpenCTI labels that start with THEME_PREFIX.

Each run reads the entries published in the last LOOKBACK_DAYS and the most
recently starred ones, keeps the candidates the pre-filter lets through, and
asks a kagent agent (TRIAGE_AGENT_URL) which of them fit the profile and how to
file them. Every answer is checked against the lists the request gave: an
unknown label, organisation or sector is dropped, and so is an article the
agent did not mark relevant.

No state is kept. A report's identity comes from its title and date, so a
second run over the same article updates the same report. A batch the agent
could not answer is skipped and comes round again on the next run; on a usage
limit the run stops asking.

Environment:
  OPENCTI_URL, OPENCTI_TOKEN      platform base URL and API token
  MINIFLUX_URL, MINIFLUX_API_KEY  reader base URL and API key
  FEED_PROFILE                    the JSON described above
  TRIAGE_AGENT_URL                A2A URL of the triage agent
  LOOKBACK_DAYS                   how far back to read (default 3)
  BATCH_SIZE, MAX_BATCHES         articles per agent call, calls per run
  DRY_RUN                         "true" prints decisions and files nothing
"""

import collections
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid

OPENCTI_URL = os.environ["OPENCTI_URL"].rstrip("/")
OPENCTI_TOKEN = os.environ["OPENCTI_TOKEN"]
MINIFLUX_URL = os.environ["MINIFLUX_URL"].rstrip("/")
MINIFLUX_API_KEY = os.environ["MINIFLUX_API_KEY"]
AGENT_URL = os.environ.get("TRIAGE_AGENT_URL", "")
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "3"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "10"))
MAX_BATCHES = int(os.environ.get("MAX_BATCHES", "12"))
DRY_RUN = os.environ.get("DRY_RUN", "").lower() == "true"

PROFILE_KEYS = {
    "profile": str,  # what is relevant, in plain words; the agent judges against this
    "always_categories": list,  # reader categories whose every entry is a candidate
    "candidate_categories": list,  # categories where pre-filter matches and starred entries count
    "prefilter": list,  # regular expressions; a match in title or text makes a candidate
    "sectors": list,  # OpenCTI sector names a report may be linked to
}
WATCH_LABEL = os.environ.get("WATCH_LABEL", "watchlist")
THEME_PREFIX = os.environ.get("THEME_PREFIX", "theme:")
SOURCE_LABEL = "src:miniflux"
STARRED_LABEL = "src:my-upload"
AUTHOR = "Miniflux (personal feeds)"
EXCERPT = 900
TAGS = re.compile(r"<[^>]+>")

PROMPT = """Decide which of these articles belong in a threat-intelligence platform, judged only
against the profile below, and how to file the ones that do. Answer with one JSON object
and nothing else:

{{"articles": [{{"id": 0, "relevant": false, "reason": "", "summary": "", "labels": [],
  "organisations": [], "sectors": []}}]}}

One item per article, with the article's id.
- relevant: true only when the article reports or analyses a security, fraud or theft
  event, technique or trend that the profile says matters. Product news, opinion without
  an event, marketing, events and reviews are false. When unsure, false.
- reason: up to 15 words on why.
- summary: for a relevant article, 1-3 sentences on what happened, to whom and how, using
  only what the text says. Empty string otherwise.
- labels: zero or more, copied exactly from the allowed labels.
- organisations: watched organisations the article is actually about (affected, named as
  the route in, or the source of an advisory), copied exactly from the watched list. A
  passing mention or a word that only looks like the name does not count.
- sectors: zero or more, copied exactly from the allowed sectors, for the sectors affected.

Profile:
{profile}

Allowed labels: {labels}
Watched organisations: {organisations}
Allowed sectors: {sectors}

Articles:
{articles}
"""


class AgentLimitError(RuntimeError):
    """The agent's model provider refused for usage or rate limits."""


def plain(markup):
    return re.sub(r"\s+", " ", html.unescape(TAGS.sub(" ", markup or ""))).strip()


def http_json(url, headers, payload=None, timeout=90):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def miniflux(path, **query):
    url = f"{MINIFLUX_URL}/v1/{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    return http_json(url, {"X-Auth-Token": MINIFLUX_API_KEY})


def opencti(query, variables=None):
    body = http_json(
        f"{OPENCTI_URL}/graphql",
        {"Content-Type": "application/json", "Authorization": f"Bearer {OPENCTI_TOKEN}"},
        {"query": query, "variables": variables or {}},
    )
    if body.get("errors"):
        raise RuntimeError(body["errors"][0].get("message", "GraphQL error")[:300])
    return body["data"]


def agent_reply(text, timeout=900):
    """One blocking A2A message to the kagent agent; returns its final answer as text."""
    body = {
        "jsonrpc": "2.0",
        "id": uuid.uuid4().hex,
        "method": "SendMessage",
        "params": {"message": {"messageId": uuid.uuid4().hex, "role": "ROLE_USER", "parts": [{"text": text}]}},
    }
    data = http_json(AGENT_URL, {"Content-Type": "application/json", "A2A-Version": "1.0"}, body, timeout)
    if "error" in data:
        raise RuntimeError(f"agent error: {str(data['error'])[:300]}")
    task = data.get("result", {}).get("task", {})
    usage = (task.get("metadata") or {}).get("https://kagent.dev/extensions/usage/v1")
    if isinstance(usage, dict):
        print(f"  agent tokens in={usage.get('inputTokens')} out={usage.get('outputTokens')}", file=sys.stderr)
    status = task.get("status", {})
    if status.get("state") != "TASK_STATE_COMPLETED":
        message = " ".join(p.get("text", "") for p in (status.get("message") or {}).get("parts") or [])
        if re.search(r"rate.?limit|usage limit|\b429\b|overloaded|limit reached", message, re.I):
            raise AgentLimitError(message.strip()[:300])
        raise RuntimeError(f"agent finished in state {status.get('state')}: {message.strip()[:300]}")
    # Each model step is its own artifact; the answer is the last one that holds text.
    for artifact in reversed(task.get("artifacts") or []):
        parts = [p for p in artifact.get("parts") or [] if isinstance(p, dict)]
        answer = "".join(
            p.get("text") or "" for p in parts if not (p.get("metadata") or {}).get("kagent.dev/a2a/thought")
        ).strip()
        if answer:
            return answer
    return ""


def json_from_text(text):
    """The last complete JSON object in a model's answer (it may wrap it in prose or a fence)."""
    decoder, found, i = json.JSONDecoder(), None, 0
    while (i := text.find("{", i)) != -1:
        try:
            obj, end = decoder.raw_decode(text, i)
        except ValueError:
            i += 1
            continue
        if isinstance(obj, dict):
            found = obj
        i = end
    if found is None:
        raise ValueError("no JSON object in answer")
    return found


def load_profile():
    profile = json.loads(os.environ["FEED_PROFILE"])
    for key, kind in PROFILE_KEYS.items():
        if not isinstance(profile.get(key), kind):
            raise SystemExit(f"FEED_PROFILE: '{key}' must be a {kind.__name__}")
    profile["prefilter_rx"] = [re.compile(p, re.I) for p in profile["prefilter"]]
    return profile


def lookup():
    """Labels, sectors, the watchlist and the author identity, from the platform."""
    labels = {
        e["node"]["value"]: e["node"]["id"]
        for e in opencti("{labels(first:500){edges{node{id value}}}}")["labels"]["edges"]
    }
    for value in (SOURCE_LABEL, STARRED_LABEL):
        if value not in labels and not DRY_RUN:
            labels[value] = opencti(
                "mutation($i:LabelAddInput!){labelAdd(input:$i){id}}", {"i": {"value": value, "color": "#555555"}}
            )["labelAdd"]["id"]
    sectors = {
        e["node"]["name"]: e["node"]["id"]
        for e in opencti("{sectors(first:500){edges{node{id name}}}}")["sectors"]["edges"]
    }
    watched = {}
    if WATCH_LABEL in labels:
        edges = opencti(
            "query($f:FilterGroup){organizations(first:500,filters:$f){edges{node{id name x_opencti_aliases}}}}",
            {
                "f": {
                    "mode": "and",
                    "filterGroups": [],
                    "filters": [
                        {"key": ["objectLabel"], "values": [labels[WATCH_LABEL]], "operator": "eq", "mode": "or"}
                    ],
                }
            },
        )["organizations"]["edges"]
        for edge in edges:
            node = edge["node"]
            # "Name (qualifier)" is how an ambiguous name is stored; match on the bare name.
            names = [re.sub(r"\s*\(.*\)$", "", node["name"])] + list(node.get("x_opencti_aliases") or [])
            names = [n for n in names if len(n) >= 3]
            if names:
                watched[node["name"]] = {
                    "id": node["id"],
                    "rx": re.compile("|".join(rf"(?<!\w){re.escape(n)}(?!\w)" for n in names)),
                }
    author = None
    if not DRY_RUN:
        author = opencti(
            "mutation($i:OrganizationAddInput!){organizationAdd(input:$i){id}}",
            {"i": {"name": AUTHOR, "description": "Articles selected from the owner's RSS reader."}},
        )["organizationAdd"]["id"]
    return labels, sectors, watched, author


def recent_entries():
    since = int(time.time()) - LOOKBACK_DAYS * 86400
    seen, offset = {}, 0
    while True:
        page = miniflux(
            "entries", published_after=since, limit=500, offset=offset, order="published_at", direction="desc"
        )
        for entry in page["entries"]:
            seen[entry["id"]] = entry
        offset += 500
        if offset >= page["total"] or not page["entries"]:
            break
    # Starring is the owner's "keep this" signal and can happen long after publication.
    for entry in miniflux("entries", starred="true", limit=200, order="changed_at", direction="desc")["entries"]:
        seen[entry["id"]] = entry
    return list(seen.values())


def candidate(entry, profile, watched):
    """The entry as a triage candidate, or None when the cheap checks rule it out."""
    title = (entry.get("title") or "").strip()
    body = plain(entry.get("content"))
    text = f"{title} . {body}"
    category = ((entry.get("feed") or {}).get("category") or {}).get("title", "")
    hits = [name for name, w in watched.items() if w["rx"].search(text)]
    why = []
    if category in profile["always_categories"]:
        why.append("category")
    if hits:
        why.append("watchlist")
    in_scope = category in profile["candidate_categories"] or category in profile["always_categories"]
    if in_scope and any(rx.search(text) for rx in profile["prefilter_rx"]):
        why.append("prefilter")
    if entry.get("starred") and in_scope:
        why.append("starred")
    if not why:
        return None
    return {
        "id": entry["id"],
        "title": title[:240],
        "url": entry["url"],
        "published": entry["published_at"],
        "feed": (entry.get("feed") or {}).get("title", "") or "Miniflux",
        "starred": bool(entry.get("starred")),
        "excerpt": body[:EXCERPT],
        "why": why,
    }


def triage(batch, profile, theme_labels, watched):
    """Ask the agent about one batch; return {entry id: checked decision} for the relevant ones."""
    articles = "\n\n".join(f"[id {c['id']}] {c['title']}\nFeed: {c['feed']}\n{c['excerpt']}" for c in batch)
    answer = json_from_text(
        agent_reply(
            PROMPT.format(
                profile=profile["profile"],
                labels=", ".join(theme_labels) or "(none)",
                organisations=", ".join(sorted(watched)) or "(none)",
                sectors=", ".join(profile["sectors"]) or "(none)",
                articles=articles,
            )
        )
    )
    known = {c["id"] for c in batch}
    decisions = {}
    for item in answer.get("articles") or []:
        if not isinstance(item, dict) or item.get("id") not in known or item.get("relevant") is not True:
            continue
        decisions[item["id"]] = {
            "summary": str(item.get("summary") or "")[:1200],
            "labels": [x for x in item.get("labels") or [] if x in theme_labels],
            "organisations": [x for x in item.get("organisations") or [] if x in watched],
            "sectors": [x for x in item.get("sectors") or [] if x in profile["sectors"]],
        }
    return decisions


def file_report(item, decision, labels, sectors, watched, author):
    objects = [watched[name]["id"] for name in decision["organisations"]]
    objects += [sectors[name] for name in decision["sectors"] if name in sectors]
    label_ids = [labels[SOURCE_LABEL]] + [labels[x] for x in decision["labels"]]
    if item["starred"]:
        label_ids.append(labels[STARRED_LABEL])
    reference = opencti(
        "mutation($i:ExternalReferenceAddInput!){externalReferenceAdd(input:$i){id}}",
        {"i": {"source_name": item["feed"][:100], "url": item["url"]}},
    )["externalReferenceAdd"]["id"]
    description = decision["summary"] or item["excerpt"]
    opencti(
        "mutation($i:ReportAddInput!){reportAdd(input:$i){id}}",
        {
            "i": {
                "name": item["title"],
                "published": item["published"],
                "report_types": ["threat-report"],
                "description": f"{description}\n\nSource: {item['feed']}",
                "createdBy": author,
                "objectLabel": sorted(set(label_ids)),
                "objects": objects,
                "externalReferences": [reference],
                "confidence": 60,
            }
        },
    )


def main():
    if not AGENT_URL:
        raise SystemExit("TRIAGE_AGENT_URL is not set")
    profile = load_profile()
    labels, sectors, watched, author = lookup()
    theme_labels = sorted(v for v in labels if v.startswith(THEME_PREFIX))
    entries = recent_entries()
    candidates = [c for c in (candidate(e, profile, watched) for e in entries) if c]
    # Starred and watchlist candidates first, so a run that stops early still covers them.
    candidates.sort(key=lambda c: (not c["starred"], "watchlist" not in c["why"]))
    why = collections.Counter(w for c in candidates for w in c["why"])
    print(f"read {len(entries)} entries; {len(candidates)} candidates {dict(why)}")

    filed = failed = skipped = asked = 0
    batches = [candidates[i : i + BATCH_SIZE] for i in range(0, len(candidates), BATCH_SIZE)]
    for number, batch in enumerate(batches):
        if number >= MAX_BATCHES:
            skipped += sum(len(b) for b in batches[number:])
            break
        try:
            decisions = triage(batch, profile, theme_labels, watched)
        except AgentLimitError as error:
            print(f"usage limit, stopping: {error}", file=sys.stderr)
            skipped += sum(len(b) for b in batches[number:])
            break
        except Exception as error:  # this batch comes round again on the next run
            print(f"batch {number + 1}: no usable answer ({error})", file=sys.stderr)
            skipped += len(batch)
            continue
        asked += len(batch)
        for item in batch:
            decision = decisions.get(item["id"])
            if not decision:
                continue
            if DRY_RUN:
                print(
                    f"  KEEP {item['published'][:10]} | {item['title'][:90]} | {decision['labels']} "
                    f"| {decision['organisations']} | {decision['sectors']}"
                )
                filed += 1
                continue
            try:
                file_report(item, decision, labels, sectors, watched, author)
                filed += 1
            except Exception as error:  # one bad article must not stop the rest
                failed += 1
                print(f"  could not file '{item['title'][:80]}': {error}", file=sys.stderr)
    print(f"asked about {asked}, {'would file' if DRY_RUN else 'filed'} {filed}, failed {failed}, not asked {skipped}")
    # Fail the Job only when the agent answered nothing at all.
    return 1 if candidates and not asked else 0


if __name__ == "__main__":
    sys.exit(main())
