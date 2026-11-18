#!/usr/bin/env python3
"""Night Watch: a nightly cluster triage written to <vault>/NightWatch/<YYYY-MM-DD>.md.

1. Collect (no model): Flux Kustomizations/HelmReleases not Ready, unhealthy or recently
   restarted pods, failed Jobs, stale VolSync backups, Certificates and kagent Agents not
   Ready, firing Alertmanager alerts, and clusters of Warning events, all from the last 24h.
2. Fingerprint each finding and compare with NightWatch/ledger.json, so recurring noise is
   recognised instead of re-reported as new.
3. Triage: each new finding (most severe first), then recurring ones that were never
   diagnosed, up to MAX_TRIAGE a night, goes to the kagent `nightwatch` agent. It looks with
   read-only Kubernetes tools (and web fetch for upstream docs) and returns JSON. A suggested
   fix that proposes a destructive step is withheld from the report.
4. Write the report and the ledger, then ask Syncthing to rescan NightWatch/.

Needs a service account that can read those resources cluster-wide (no Secrets).
Usage: nightwatch.py <vault-dir> [--dry-run]
"""
import datetime as dt
import hashlib
import json
import os
import re
import ssl
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vaultlib as vl  # noqa: E402

VAULT = sys.argv[1] if len(sys.argv) > 1 else "/vault"
OUT_DIR = "NightWatch"
LEDGER = f"{OUT_DIR}/ledger.json"
AGENT_URL = os.environ.get("NIGHTWATCH_AGENT_URL", "")
ALERTMANAGER_URL = os.environ.get("ALERTMANAGER_URL", "")
MAX_TRIAGE = int(os.environ.get("MAX_TRIAGE", "5"))
AUTHOR = "nightwatch"
DAY = 86400
SA = "/var/run/secrets/kubernetes.io/serviceaccount"
API = "https://kubernetes.default.svc"
QUIET_ALERTS = {"Watchdog", "InfoInhibitor"}
BAD_WAIT = {"CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "CreateContainerConfigError",
            "CreateContainerError", "InvalidImageName"}
RANK = {"critical": 0, "warning": 1, "info": 2}
# Events about these kinds are recorded in `default`; they aren't namespaced.
CLUSTER_KINDS = {"Node", "PersistentVolume", "StorageClass", "VolumeAttachment", "Namespace",
                 "ClusterIssuer", "CSINode", "CSIDriver", "ClusterRole", "ClusterRoleBinding"}
NOW = dt.datetime.now(dt.timezone.utc)


# ---------------------------------------------------------------- Kubernetes API (stdlib)
def k8s(path):
    with open(f"{SA}/token") as fh:
        tok = fh.read().strip()
    ctx = ssl.create_default_context(cafile=f"{SA}/ca.crt")
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        return json.loads(resp.read()).get("items", [])


def ts(s):
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def age_s(s):
    t = ts(s)
    return (NOW - t).total_seconds() if t else None


def not_ready(obj):
    conds = (obj.get("status") or {}).get("conditions") or []
    c = next((c for c in conds if c.get("type") == "Ready"), None)
    return (c is not None and c.get("status") != "True"), (c or {}).get("message", "")


def workload(name):
    """Pod name without its ReplicaSet/Job hash, so restarts fingerprint per workload."""
    name = re.sub(r"-[a-z0-9]{8,10}-[a-z0-9]{5}$", "", name)
    return re.sub(r"-[a-z0-9]{5}$", "", name)


def finding(category, severity, ns, name, title, details, key=None):
    """`key` overrides what the fingerprint is built from, for findings whose title carries a
    count that changes nightly (it would otherwise look new every night)."""
    fp = hashlib.sha1((key or f"{category}|{ns}|{name}|{title}").encode()).hexdigest()[:12]
    return {"fp": fp, "category": category, "severity": severity, "namespace": ns, "name": name,
            "title": title, "details": details}


# ---------------------------------------------------------------- collection
def collect():
    out, checked = [], {}

    for kind, path in [("Kustomization", "/apis/kustomize.toolkit.fluxcd.io/v1/kustomizations"),
                       ("HelmRelease", "/apis/helm.toolkit.fluxcd.io/v2/helmreleases")]:
        items = k8s(path)
        checked[f"Flux {kind}s"] = len(items)
        for o in items:
            bad, msg = not_ready(o)
            if bad and not (o.get("spec") or {}).get("suspend"):
                m = o["metadata"]
                out.append(finding("flux", "warning", m["namespace"], m["name"],
                                   f"{kind} not Ready", msg[:500]))

    pods = k8s("/api/v1/pods")
    checked["Pods"] = len(pods)
    restarts = []
    for p in pods:
        m, st = p["metadata"], p.get("status") or {}
        if st.get("phase") == "Succeeded":
            continue
        for c in st.get("containerStatuses") or []:
            wait = (c.get("state") or {}).get("waiting") or {}
            term = (c.get("lastState") or {}).get("terminated") or {}
            w = workload(m["name"])
            if wait.get("reason") in BAD_WAIT:
                out.append(finding("pod", "critical", m["namespace"], w, f"{wait['reason']} ({c['name']})",
                                   f"pod {m['name']}, restarts {c.get('restartCount', 0)}: {wait.get('message', '')[:300]}"))
            elif not c.get("ready") and st.get("phase") == "Running" and (age_s(m.get("creationTimestamp")) or 0) > 900:
                out.append(finding("pod", "warning", m["namespace"], w, f"container not ready ({c['name']})",
                                   f"pod {m['name']} running for {int(age_s(m['creationTimestamp']) // 60)} min but not ready"))
            if term.get("finishedAt") and (age_s(term["finishedAt"]) or DAY + 1) < DAY:
                restarts.append((m["namespace"], w, c["name"], term.get("reason", "?"), c.get("restartCount", 0),
                                 term.get("finishedAt")))
    for ns, w, cname, reason, count, when in restarts:
        if reason == "OOMKilled" or count >= 3:
            out.append(finding("restart", "warning", ns, w, f"restarting: {reason} ({cname})",
                               f"{count} restarts in total, last at {when}"))
    single = [r for r in restarts if not (r[3] == "OOMKilled" or r[4] >= 3)]
    if len(single) >= 3:  # several one-off restarts usually share a cause (node, API server)
        lines = "; ".join(f"{ns}/{w} ({reason} at {when})" for ns, w, _, reason, _, when in single[:15])
        out.append(finding("restart", "info", "", "many", f"{len(single)} containers restarted once",
                           lines, key="restart|many"))

    jobs = k8s("/apis/batch/v1/jobs")
    checked["Jobs"] = len(jobs)
    for j in jobs:
        m, st = j["metadata"], j.get("status") or {}
        if (st.get("failed") or 0) > 0 and not st.get("succeeded") and (age_s(m.get("creationTimestamp")) or DAY + 1) < DAY:
            owner = next((o["name"] for o in m.get("ownerReferences") or [] if o.get("kind") == "CronJob"), m["name"])
            out.append(finding("job", "warning", m["namespace"], owner, "Job failed",
                               f"job {m['name']}: {st.get('failed')} failed pod(s)"))

    for kind, path, stale in [("ReplicationSource", "/apis/volsync.backube/v1alpha1/replicationsources", 26 * 3600)]:
        items = k8s(path)
        checked["VolSync backups"] = len(items)
        for o in items:
            last = (o.get("status") or {}).get("lastSyncTime")
            a = age_s(last) if last else None
            if a is None or a > stale:
                m = o["metadata"]
                out.append(finding("backup", "warning", m["namespace"], m["name"], "backup is stale",
                                   f"last successful sync: {last or 'never'}"))

    for label, path in [("Certificates", "/apis/cert-manager.io/v1/certificates"),
                        ("kagent Agents", "/apis/api.kagent.dev/v1alpha3/agents")]:
        try:
            items = k8s(path)
        except Exception as e:
            print(f"warning: couldn't list {label}: {e}", file=sys.stderr)
            continue
        checked[label] = len(items)
        for o in items:
            bad, msg = not_ready(o)
            if bad:
                m = o["metadata"]
                out.append(finding(label.split()[-1].lower(), "warning", m["namespace"], m["name"],
                                   f"{label[:-1]} not Ready", msg[:500]))

    if ALERTMANAGER_URL:
        try:
            req = urllib.request.Request(ALERTMANAGER_URL.rstrip("/") +
                                         "/api/v2/alerts?active=true&silenced=false&inhibited=false")
            with urllib.request.urlopen(req, timeout=15) as resp:
                alerts = json.loads(resp.read())
            checked["Alertmanager alerts"] = len(alerts)
            for a in alerts:
                lb, an = a.get("labels") or {}, a.get("annotations") or {}
                if lb.get("alertname") in QUIET_ALERTS:
                    continue
                sev = lb.get("severity", "warning")
                sev = sev if sev in RANK else "warning"
                target = lb.get("pod") or lb.get("persistentvolumeclaim") or lb.get("instance") or lb.get("job", "")
                out.append(finding("alert", sev, lb.get("namespace", ""), workload(target) if lb.get("pod") else target,
                                   f"alert {lb.get('alertname')}",
                                   (an.get("summary") or an.get("description") or "")[:400] +
                                   f" (firing since {a.get('startsAt', '?')})"))
        except Exception as e:
            print(f"warning: couldn't read Alertmanager: {e}", file=sys.stderr)

    # Warning events, grouped cluster-wide by (reason, kind): the same cause usually shows up
    # in many namespaces at once (e.g. VolSync movers), and one finding per namespace would
    # spend the nightly triage budget on duplicates.
    events = k8s("/api/v1/events?fieldSelector=type%3DWarning")
    groups = {}
    for e in events:
        when = e.get("lastTimestamp") or e.get("eventTime") or (e.get("metadata") or {}).get("creationTimestamp")
        if (age_s(when) or DAY + 1) > DAY:
            continue
        io = e.get("involvedObject") or {}
        kind = io.get("kind", "?")
        ns = "" if kind in CLUSTER_KINDS else e["metadata"]["namespace"]
        g = groups.setdefault((e.get("reason", "?"), kind),
                              {"count": 0, "objects": set(), "namespaces": set(), "message": e.get("message", "")})
        g["count"] += e.get("count") or 1
        g["objects"].add(f"{ns}/{io.get('name', '?')}" if ns else io.get("name", "?"))
        if ns:
            g["namespaces"].add(ns)
    checked["Warning event groups"] = len(groups)
    for (reason, kind), g in sorted(groups.items(), key=lambda kv: -kv[1]["count"]):
        if g["count"] >= 5:
            objs, nss = sorted(g["objects"]), sorted(g["namespaces"])
            where = ", ".join(nss) if len(nss) <= 3 else f"{len(nss)} namespaces"
            out.append(finding("events", "info", where, reason, f"{g['count']}x {reason} on {kind}",
                               f"{len(objs)} object(s) in {where or 'cluster-scoped objects'}, "
                               f"e.g. {', '.join(objs[:5])}. Sample: {g['message'][:300]}",
                               key=f"events|{reason}|{kind}"))
    return out, checked


# ---------------------------------------------------------------- triage
SEVERITIES = {"critical", "warning", "info", "ok"}
# The agent's prompt forbids destructive steps, but a small local model can still suggest
# one. Anything matching this is kept out of the report rather than trusted.
DESTRUCTIVE = re.compile(
    r"\b(force[- ]?delet\w*|--force|--grace-period[= ]?0|drain|cordon|reboot|power[- ]cycle|"
    r"wipe\w*|reformat\w*|zap\w*|purge\w*|rm\s+-rf?|"
    r"remov\w*\s+(?:the\s+)?finalizers?|finalizers?\s*[:=]\s*\[\]|"
    r"kubectl\s+(?:edit|patch|delete|apply|replace|scale|drain|cordon)|"
    r"delet\w*\s+(?:the\s+|all\s+|any\s+|stuck\s+|old\s+|orphan\w*\s+)*"
    r"(?:pvc|pv|persistent\s*volume\w*|pod|node|namespace|osd|pool|statefulset|"
    r"volume\w*|snapshot\w*|data|repo\w*|backup\w*)s?)(?!\w)", re.I)
WITHHELD = ("Withheld: the agent proposed a destructive step. Check the evidence above and "
            "decide by hand; cluster changes go through Git and Flux.")


def triage(f):
    prompt = ("Investigate this finding from tonight's cluster check.\n\n" + json.dumps(
        {k: f[k] for k in ("category", "severity", "namespace", "name", "title", "details")}, indent=1))
    raw = vl.json_from_text(vl.agent_reply(AGENT_URL, prompt, timeout=420))
    sev = str(raw.get("severity", "")).lower()
    clean = lambda v, n: " ".join(str(v or "").split())[:n]  # noqa: E731
    fix = clean(raw.get("suggested_fix"), 800)
    if DESTRUCTIVE.search(fix):
        print(f"withheld destructive suggestion for {f['title']} {obj(f)}: {fix[:200]}", file=sys.stderr)
        fix = WITHHELD
    return {"severity": sev if sev in SEVERITIES else f["severity"],
            "summary": clean(raw.get("summary"), 400),
            "cause": clean(raw.get("likely_cause"), 600),
            "fix": fix,
            "evidence": [clean(e, 300) for e in (raw.get("evidence") or [])[:5] if str(e).strip()]}


# ---------------------------------------------------------------- report
def cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def obj(f):
    if f["category"] == "events":  # name is the event reason (already in the title)
        return f["namespace"] or "(cluster-scoped)"
    return f"{f['namespace']}/{f['name']}" if f["namespace"] else f["name"]


def detail(f, d, untriaged_note):
    b = [f"### {f['title']}: `{obj(f)}`", "", f"- **Seen:** {cell(f['details'])}"]
    if d:
        b += [f"- **What's wrong:** {d['summary']}", f"- **Likely cause:** {d['cause']}",
              f"- **Suggested fix:** {d['fix']}"]
        if d["evidence"]:
            b += ["- **Evidence:**"] + [f"  - {cell(e)}" for e in d["evidence"]]
    else:
        b.append(f"- *{untriaged_note}*")
    return b + [""]


def report(today, findings, new, recurring, resolved, diag, checked, ledger):
    n_new = len(new)
    worst = min((RANK.get(f["severity"], 2) for f in findings), default=3)
    verdict = ("All clear: nothing new tonight." if not findings else
               f"{n_new} new and {len(recurring)} recurring finding(s); "
               f"most severe: {['critical', 'warning', 'info'][worst] if worst < 3 else 'none'}.")
    desc = f"Night Watch cluster check for {today}: {verdict}"
    fm = ["---", f"created: {today}", "type: briefing", "status: complete", "tags:", "  - nightwatch",
          f"description: {vl.yaml_str(desc)}", "generated: true", f"author: {AUTHOR}", "---", ""]
    b = [f"# Night Watch: {today}", "", f"> {verdict}", "",
         "*Collected by the `nightwatch` job; findings triaged by the local `nightwatch` agent "
         "(read-only Kubernetes tools and web fetch). Suggested fixes are suggestions: cluster "
         "changes go through Git and Flux.*", ""]
    if new:
        b += ["## New", "", "| Severity | What | Object |", "|---|---|---|"]
        for f in new:
            sev = diag.get(f["fp"], {}).get("severity", f["severity"])
            b.append(f"| {sev} | {cell(f['title'])} | `{cell(obj(f))}` |")
        b.append("")
        for f in new:
            b += detail(f, diag.get(f["fp"]),
                        "Not triaged tonight (agent unavailable or over the nightly limit); "
                        "it will be retried on a later night.")
    late = [f for f in recurring if f["fp"] in diag]
    if late:
        b += ["## Triaged tonight (seen before)", ""]
        for f in late:
            b += detail(f, diag[f["fp"]], "")
    if recurring:
        b += ["## Recurring", "", "| Severity | What | Object | First seen | Nights | Diagnosis |",
              "|---|---|---|---|---|---|"]
        for f in recurring:
            e = ledger[f["fp"]]
            dx = e.get("diagnosis") or ("*pending*" if not e.get("triaged") else "")
            b.append(f"| {f['severity']} | {cell(f['title'])} | `{cell(obj(f))}` | {e['first_seen']} "
                     f"| {e['nights']} | {cell(dx)} |")
        b.append("")
    if resolved:
        b += ["## Resolved since last check", ""] + [f"- {cell(e['title'])}: `{cell(e['object'])}`" for e in resolved] + [""]
    b += ["## Checked", ""] + [f"- {k}: {v}" for k, v in checked.items()] + [""]
    return "\n".join(fm + b)


def main():
    if not vl.vault_ready(VAULT):
        return 0
    today = dt.datetime.now(vl.TZ).date().isoformat()
    findings, checked = collect()
    findings.sort(key=lambda f: (RANK.get(f["severity"], 2), f["category"], obj(f)))
    path = os.path.join(VAULT, LEDGER)
    try:
        with open(path, encoding="utf-8") as fh:
            ledger = json.load(fh)
    except (OSError, ValueError):
        ledger = {}
    current = {f["fp"] for f in findings}
    new = [f for f in findings if f["fp"] not in ledger or ledger[f["fp"]].get("status") == "resolved"]
    recurring = [f for f in findings if f not in new]
    resolved = [e for fp, e in ledger.items() if fp not in current and e.get("status") != "resolved"]

    # New findings first, then recurring ones that never got a diagnosis (missed the nightly
    # limit, or the agent failed), so nothing stays untriaged for good.
    retry = [f for f in recurring if not ledger[f["fp"]].get("triaged")]
    diag = {}
    if AGENT_URL:
        for f in (new + retry)[:MAX_TRIAGE]:
            try:
                diag[f["fp"]] = triage(f)
                print(f"triaged {f['title']} {obj(f)}: {diag[f['fp']]['severity']}")
            except Exception as e:
                print(f"triage failed for {f['title']} {obj(f)}: {e}", file=sys.stderr)

    new_fps = {f["fp"] for f in new}
    for f in findings:
        e = ledger.setdefault(f["fp"], {"first_seen": today, "nights": 0})
        if f["fp"] in new_fps:  # first seen, or back after resolving: diagnose afresh
            e.update(triaged=False, diagnosis="")
        if f["fp"] in diag:
            e.update(triaged=True, triaged_on=today, diagnosis=diag[f["fp"]]["summary"])
        e.update(title=f["title"], object=obj(f), category=f["category"], last_seen=today, status="open",
                 nights=e.get("nights", 0) + (1 if e.get("last_seen") != today else 0))
    for e in resolved:
        e["status"] = "resolved"
        e["resolved"] = today

    text = report(today, findings, new, recurring, resolved, diag, checked, ledger)
    out = os.path.join(VAULT, OUT_DIR, f"{today}.md")
    if vl.DRY:
        print(text)
        return 0
    vl.atomic_write(out, text)
    vl.atomic_write(path, json.dumps(ledger, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT_DIR}/{today}.md: {len(new)} new, {len(recurring)} recurring, {len(resolved)} resolved")
    vl.request_rescan(VAULT, [OUT_DIR])
    return 0


if __name__ == "__main__":
    sys.exit(main())
