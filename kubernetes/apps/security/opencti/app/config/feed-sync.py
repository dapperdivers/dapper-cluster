"""File security-relevant Miniflux articles in OpenCTI as reports.

Runs from the opencti-feed-sync CronJob. Standard library only.

Each run looks at the entries published in the last LOOKBACK_DAYS and at the
most recently starred entries, keeps the ones that fit the TMS lens (freight
fraud and cargo theft, telematics, the watched logistics-technology vendors,
integrator themes such as supply-chain and token abuse) and creates one report
per article. It keeps no state: a report's identity comes from its title and
date, so a second run over the same article updates the same report.

Environment:
  OPENCTI_URL, OPENCTI_TOKEN      platform base URL and API token
  MINIFLUX_URL, MINIFLUX_API_KEY  reader base URL and API key
  LOOKBACK_DAYS                   how far back to read (default 3)
  LOGISTICS_CATEGORY              Miniflux category that is always considered
  DRY_RUN                         "true" prints what would be filed
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

OPENCTI_URL = os.environ["OPENCTI_URL"].rstrip("/")
OPENCTI_TOKEN = os.environ["OPENCTI_TOKEN"]
MINIFLUX_URL = os.environ["MINIFLUX_URL"].rstrip("/")
MINIFLUX_API_KEY = os.environ["MINIFLUX_API_KEY"]
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "3"))
LOGISTICS_CATEGORY = os.environ.get("LOGISTICS_CATEGORY", "Logistics security")
DRY_RUN = os.environ.get("DRY_RUN", "").lower() == "true"

SECURITY_CATEGORIES = {"Security firehose", "Security", LOGISTICS_CATEGORY}
WATCH_LABEL = "theme:integration-partner"
SOURCE_LABEL = "src:miniflux"
STARRED_LABEL = "src:my-upload"
AUTHOR = "Miniflux (personal feeds)"

# Watched organisation name (as created in OpenCTI) -> patterns that identify
# it in an article. Generic words (Motive, Highway, WEX) need context.
VENDORS = {
    "FourKites": [r"\bFourKites\b"],
    "Descartes MacroPoint": [r"\bMacroPoint\b", r"\bDescartes Systems\b"],
    "OpenTrack": [r"\bOpenTrack\b"],
    "project44": [r"\bproject44\b"],
    "Railinc": [r"\bRailinc\b"],
    "Transporeon": [r"\bTransporeon\b"],
    "Geotab": [r"\bGeotab\b"],
    "ISAAC Instruments": [r"\bISAAC Instruments\b"],
    "Motive Technologies": [
        r"\bKeepTruckin\b",
        r"\bMotive Technologies\b",
        r"\bMotive(?:'s)? (?:ELD|fleet|dashcam|AI dashcam|telematics)",
    ],
    "Platform Science": [r"\bPlatform Science\b"],
    "Samsara": [r"\bSamsara\b"],
    "ORBCOMM": [r"\bORBCOMM\b", r"\bOrbcomm\b"],
    "Spireon": [r"\bSpireon\b"],
    "DAT Freight & Analytics": [r"\bDAT Freight\b", r"\bDAT One\b", r"\bDAT load board\b", r"\bDAT Solutions\b"],
    "Truckstop": [r"\bTruckstop\b"],
    "Trucker Tools": [r"\bTrucker Tools\b"],
    "SMC3": [r"\bSMC3\b"],
    "Comdata": [r"\bComdata\b"],
    "EFS (WEX)": [
        r"\bWEX Inc\b",
        r"\bWEX\b(?= (?:fleet|fuel|card|said|confirmed|disclosed))",
        r"\bElectronic Funds Source\b",
    ],
    "TriumphPay": [r"\bTriumphPay\b", r"\bTriumph Financial\b"],
    "Transflo": [r"\bTransflo\b"],
    "Navix": [r"\bNavix\b"],
    "Highway (highway.com)": [r"\bHighway(?:'s)? (?:carrier identity|app|platform|said)\b", r"\bhighway\.com\b"],
    "RMIS": [r"\bRMIS\b"],
    "MyCarrierPortal": [r"\bMyCarrierPortal\b", r"\bMyCarrierPackets\b"],
    "Trimble PC*MILER": [r"\bPC\*?MILER\b", r"\bTrimble\b"],
    "Rand McNally": [r"\bRand McNally\b"],
    "Breakthrough Fuel": [r"\bBreakthrough Fuel\b"],
    "Slack": [r"\bSlack\b"],
}
VENDOR_RX = {name: [re.compile(p) for p in pats] for name, pats in VENDORS.items()}

FREIGHT_RX = {
    label: re.compile(pattern, re.I)
    for label, pattern in {
        "theme:cargo-theft": r"cargo (?:theft|thieves|crime)|stolen (?:freight|cargo|load)s?|freight theft",
        "theme:freight-fraud": r"freight fraud|double[- ]broker|fictitious pick-?up|carrier identity theft"
        r"|fraudulent carrier|load board fraud|MC number",
        "theme:telematics": r"telematics|electronic logging device|\bELDs?\b|J1939"
        r"|fleet management (?:system|software)|dashcam",
        "theme:regulation": r"\bFMCSA\b|\bNMFTA\b",
    }.items()
}
INTEGRATOR_RX = {
    label: re.compile(pattern, re.I)
    for label, pattern in {
        "theme:supply-chain": r"supply[- ]chain (?:attack|compromise)|software supply chain"
        r"|malicious (?:npm|pypi|package)|compromised (?:package|dependency)",
        "theme:token-theft": r"(?:oauth|access|api|session) tokens? (?:theft|stolen|abuse|hijack)"
        r"|stolen (?:oauth|access|api|session) tokens?|token theft",
        "theme:saas-compromise": r"third[- ]party (?:breach|vendor breach|compromise)"
        r"|SaaS (?:breach|compromise|supply chain)|integration (?:breach|compromise)",
        "theme:api-abuse": r"API (?:abuse|key leak|keys? (?:leaked|exposed|stolen))|exposed API keys?"
        r"|BOLA|broken object level",
        "theme:account-takeover": r"account takeover|credential stuffing",
    }.items()
}
TRUCKING = re.compile(
    r"\b(?:trucking|truckers?|motor carriers?|freight brokers?|3PL|logistics (?:firm|company|provider|giant)"
    r"|shipping (?:firm|company|giant)|supply chain software|transportation management|TMS)\b",
    re.I,
)
CYBER = re.compile(r"ransomware|breach|hack|cyber|phish|malware|extort|data leak|intrusion|compromis", re.I)
# An article must say something about security, fraud or theft to be filed.
RELEVANT = re.compile(
    r"ransomware|breach|hack|cyber|phish|malware|extort|data leak|intrusion|compromis|fraud|theft|stolen|thieves"
    r"|scam|spoof|identity|vulnerab|exploit|supply[- ]chain attack|account takeover|credential|token|API key",
    re.I,
)
TAGS = re.compile(r"<[^>]+>")


def plain(markup):
    return re.sub(r"\s+", " ", html.unescape(TAGS.sub(" ", markup or ""))).strip()


def http_json(url, headers, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=90) as response:
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


def classify(entry):
    """Return what to file for this entry, or None when it does not fit."""
    title = (entry.get("title") or "").strip()
    body = plain(entry.get("content"))
    text = f"{title} . {body}"
    category = ((entry.get("feed") or {}).get("category") or {}).get("title", "")
    labels, vendors, reasons = set(), [], []

    for name, patterns in VENDOR_RX.items():
        if not any(p.search(text) for p in patterns):
            continue
        # "Slack" is everywhere: only count it when the headline is about a Slack security event.
        if name == "Slack" and not (re.search(r"\bSlack\b", title) and CYBER.search(title)):
            continue
        vendors.append(name)
    if vendors:
        reasons.append("vendor")
        labels.add(WATCH_LABEL)

    transport = False
    for label, pattern in FREIGHT_RX.items():
        if pattern.search(text):
            labels.add(label)
            transport = True
    if TRUCKING.search(title) and CYBER.search(text):
        transport = True
    if transport:
        reasons.append("freight")

    if category in SECURITY_CATEGORIES:
        for label, pattern in INTEGRATOR_RX.items():
            if pattern.search(title):  # headline only, to keep this precise
                labels.add(label)
                if "integrator" not in reasons:
                    reasons.append("integrator")

    if category == LOGISTICS_CATEGORY:
        reasons.append("logistics-category")
        transport = True
    # A starred article counts on its own only when it comes from a security
    # category; the owner also stars things that have nothing to do with this.
    if entry.get("starred") and (reasons or category in SECURITY_CATEGORIES):
        reasons.append("starred")

    topical = any(r in reasons for r in ("vendor", "freight", "integrator"))
    if not reasons:
        return None
    if not (RELEVANT.search(title) or (topical and RELEVANT.search(body[:400]))):
        return None
    return {
        "title": title[:240],
        "url": entry["url"],
        "published": entry["published_at"],
        "feed": (entry.get("feed") or {}).get("title", "") or "Miniflux",
        "starred": bool(entry.get("starred")),
        "labels": sorted(labels),
        "vendors": vendors,
        "transport": transport,
        "reasons": reasons,
        "summary": body[:700] + ("…" if len(body) > 700 else ""),
    }


def recent_entries():
    since = int(time.time()) - LOOKBACK_DAYS * 86400
    seen, offset = {}, 0
    while True:
        page = miniflux("entries", published_after=since, limit=500, offset=offset, order="published_at", direction="desc")
        for entry in page["entries"]:
            seen[entry["id"]] = entry
        offset += 500
        if offset >= page["total"] or not page["entries"]:
            break
    # Starring is the owner's "keep this" signal and can happen long after publication.
    for entry in miniflux("entries", starred="true", limit=200, order="changed_at", direction="desc")["entries"]:
        seen[entry["id"]] = entry
    return list(seen.values())


def lookup():
    labels = {
        e["node"]["value"]: e["node"]["id"]
        for e in opencti("{labels(first:500){edges{node{id value}}}}")["labels"]["edges"]
    }
    for value in (SOURCE_LABEL, STARRED_LABEL, WATCH_LABEL):
        if value not in labels:
            labels[value] = opencti(
                "mutation($i:LabelAddInput!){labelAdd(input:$i){id}}", {"i": {"value": value, "color": "#555555"}}
            )["labelAdd"]["id"]
    sectors = {
        e["node"]["name"]: e["node"]["id"]
        for e in opencti("{sectors(first:500){edges{node{id name}}}}")["sectors"]["edges"]
    }
    watched = opencti(
        "query($f:FilterGroup){organizations(first:500,filters:$f){edges{node{id name}}}}",
        {
            "f": {
                "mode": "and",
                "filterGroups": [],
                "filters": [{"key": ["objectLabel"], "values": [labels[WATCH_LABEL]], "operator": "eq", "mode": "or"}],
            }
        },
    )["organizations"]["edges"]
    orgs = {e["node"]["name"]: e["node"]["id"] for e in watched}
    author = opencti(
        "mutation($i:OrganizationAddInput!){organizationAdd(input:$i){id}}",
        {"i": {"name": AUTHOR, "description": "Articles selected from the owner's RSS reader."}},
    )["organizationAdd"]["id"]
    return labels, sectors, orgs, author


def file_report(item, labels, sectors, orgs, author):
    objects = [orgs[v] for v in item["vendors"] if v in orgs]
    if item["transport"]:
        objects += [sectors[s] for s in ("Transport", "Road transport") if s in sectors]
    label_ids = [labels[SOURCE_LABEL]] + [labels[x] for x in item["labels"] if x in labels]
    if item["starred"]:
        label_ids.append(labels[STARRED_LABEL])
    reference = opencti(
        "mutation($i:ExternalReferenceAddInput!){externalReferenceAdd(input:$i){id}}",
        {"i": {"source_name": item["feed"][:100], "url": item["url"]}},
    )["externalReferenceAdd"]["id"]
    opencti(
        "mutation($i:ReportAddInput!){reportAdd(input:$i){id}}",
        {
            "i": {
                "name": item["title"],
                "published": item["published"],
                "report_types": ["threat-report"],
                "description": f"{item['summary']}\n\nSource: {item['feed']}",
                "createdBy": author,
                "objectLabel": label_ids,
                "objects": objects,
                "externalReferences": [reference],
                "confidence": 50,
            }
        },
    )


def main():
    entries = recent_entries()
    items = [i for i in (classify(e) for e in entries) if i]
    reasons = collections.Counter(r for i in items for r in i["reasons"])
    print(f"read {len(entries)} entries from the last {LOOKBACK_DAYS} days and the starred list; {len(items)} fit {dict(reasons)}")
    if DRY_RUN:
        for item in items:
            print(f"  {item['published'][:10]} | {item['title'][:100]} | {','.join(item['vendors'])}")
        return 0
    if not items:
        return 0
    labels, sectors, orgs, author = lookup()
    filed, failed = 0, 0
    for item in items:
        try:
            file_report(item, labels, sectors, orgs, author)
            filed += 1
        except Exception as error:  # one bad article must not stop the rest
            failed += 1
            print(f"  could not file '{item['title'][:80]}': {error}", file=sys.stderr)
    print(f"filed {filed} reports, {failed} failed")
    # Fail the Job only when nothing at all could be filed.
    return 1 if failed and not filed else 0


if __name__ == "__main__":
    sys.exit(main())
