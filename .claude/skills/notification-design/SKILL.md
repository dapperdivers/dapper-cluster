---
name: notification-design
description: EEMUA 191 design gate for alarms and notifications. Run this BEFORE creating or modifying ANY alert/notification anywhere in the ecosystem — a PrometheusRule, a Gatus alert, a Home Assistant / Node-RED automation that notifies, an Inovelli LED-bar notification, an app webhook (Pushover/ntfy), a Flux alert. Walks the rationalization questions that decide whether the alert should exist, what severity it gets, and which channel (page / push / TTS / LED bar / dashboard) delivers it. Also use when fighting alert fatigue, floods, or auditing existing alerts.
allowed-tools: Read, Edit, Write, Bash, Grep, Glob
---

# Notification design gate (EEMUA 191)

EEMUA Publication 191 (with ISA-18.2 / IEC 62682) is the industrial alarm-management standard.
Its core insight scales to a homelab: **a notification is a demand on a human's attention, and
attention is a fixed budget.** Here the "operator console" is Derek's phone, there is ONE
operator, and he is asleep a third of the day.

**This skill is a gate, not a reference.** Whenever an alert/notification is about to be born —
regardless of which system delivers it — walk the steps below IN ORDER. Most proposed alerts
should die at Step 1 or get demoted at Step 2. That is the skill working, not a failure.

> **The prime directive: an alarm requires an operator ACTION. If there is no action, it is not
> an alarm** — it's an event. Events go to dashboards/logs (Grafana, VictoriaLogs, HA logbook),
> not to a phone.

## Step 1 — Rationalize: does this deserve to exist?

Answer all five in writing (they become the alert's annotations/message):

1. **Cause** — what happened?
2. **Consequence** — what breaks if nobody acts?
3. **Response** — what does the person seeing it actually DO?
4. **Time to respond** — how long before the consequence lands?
5. **Audience** — WHO can act on it? This decides which console it's even allowed on:
   - **Derek-only** (anything cluster/infra: etcd, VolSync, certs, Flux…) → phone channels
     (ntfy/Pushover) ONLY. Never the LEDs or TTS.
   - **Household** (Derek + Sara: trash, dryer, doors, doorbell, alarm, leaks) → LED/TTS
     eligible, and often the LED is the BETTER channel — Sara can't see Derek's phone.

Kill criteria — if any of these hit, do NOT create the notification (on this channel):

- **No response exists** ("just good to know") → dashboard it — or, for home state worth a
  glance, **demote to an Inovelli LED slot** (see channel ladder below). Ambient light costs
  ~zero attention; a push costs an interruption.
- **It self-heals** (pod restart, retry, HPA, reconnect) → the system doing its job is an event.
  Alert only if it's _still_ broken after self-healing had time to work.
- **The response is automatable** → automate it; alert only on automation failure.
- **An existing alert already covers the consequence** (check stock kube-prometheus-stack rules
  and `kubectl get prometheusrules -A`) → don't create a twin.
- **It's a symptom of another alert** (node down → everything on it) → add an inhibition rule
  instead of a new alert.

## Step 2 — Prioritize: consequence × urgency, then pick the channel to match

**Priority = consequence severity × time available to respond.** Not how important the component
feels, not how proud we are of the app.

**Channel intrusiveness ladder** — pick the LOWEST rung that still gets the response in time.
Every rung you climb spends more of the attention budget:

| Rung | Channel                                     | Costs the human               | Use for                                                             |
| ---- | ------------------------------------------- | ----------------------------- | ------------------------------------------------------------------- |
| 0    | Dashboard / logs                            | nothing until they look       | events, history, debugging                                          |
| 1    | **Inovelli LED slot** (per-LED, persistent) | a glance at any switch        | standing home state: trash out?, door open, dryer done, alarm armed |
| 2    | **Inovelli full-bar effect** (transient)    | ambient attention in the room | local, now-ish events: doorbell, timer expiry, escalations          |
| 3    | ntfy push                                   | an interruption, follows you  | act today-ish, or away-from-home relevance                          |
| 4    | TTS announce / Pushover page (bypasses DND) | wakes / stops everyone        | act NOW: safety, security, data loss                                |

Two channels can pair (alarm armed = LED slot + arming push), but each channel must
independently pass the gate — "also send a push" is a decision, not a default.

**Consoles have audiences (EEMUA: route alarms to the operator who can respond).** Rungs 0 and
3–4 are Derek's console. Rungs 1–2 (LEDs) and TTS are the HOUSEHOLD console — Sara sees them
too. A notification on a shared surface must be actionable by whoever is looking at it: "trash
night" passes; "etcd flapping" is pure noise to Sara and erodes the trust that makes the trash
light work. Infra never lights the panel. Rare, deliberate exceptions only where the household
response is real (e.g. "internet down" = "it's known, don't power-cycle the router") — chosen
case by case, never defaulted.

| severity   | Delivery (cluster)                         | Test                                                                                               | EEMUA share |
| ---------- | ------------------------------------------ | -------------------------------------------------------------------------------------------------- | ----------- |
| `critical` | Pushover page + ntfy urgent (bypasses DND) | **"Would I want to be woken at 3am for this?"** Data loss, safety, security, power, whole-cluster. | ~5%         |
| `warning`  | ntfy high                                  | Act today-ish: degraded, trending toward full, backup missed.                                      | ~15%        |
| `info`     | ntfy low / mostly null-routed              | No action. Prefer no notification at all.                                                          | ~80%        |

EEMUA's target distribution is ~**80% low / 15% medium / 5% high**. The repo's custom rules
currently sit near 50/50 critical/warning — **bias DOWN**. Media-stack anything is almost never
critical (Plex down at 3am costs nothing; make it a warning handled at breakfast). Legitimately
critical: UPS/power, storage/data-loss risk (VolSync, CNPG, Ceph health), security (cert expiry
imminent, Authentik down), Flux fully broken.

Smart-home ladder, same logic: critical = water leak, smoke/CO, freezer warm, garage open late
(bypass DND / TTS announce); high = door unlocked at bedtime, washer done, important battery
low; motion/lights/presence = events, no push.

## Step 3 — Debounce: design out the noise before it ships

- **PrometheusRule:** `for:` on everything user-facing — ≥ 2× scrape interval AND ≥ the time the
  condition self-heals in practice (pod restart ≈ 5m). Prefer `predict_linear` ("disk full in
  4h") over static thresholds; if static, pick a value the metric doesn't flap around.
- **Gatus:** the defaults `failure-threshold: 5` / `success-threshold: 3` (in
  `kubernetes/apps/observability/gatus/app/resources/config.yaml`) are the debounce — don't
  lower them per-endpoint without a reason.
- **Home Assistant:** `for:` on triggers, condition guards for state-based suppression (don't
  announce "door open" while actively unloading groceries).
- **Direct webhooks (\*arr, sabnzbd, custom scripts):** events silent/low priority
  (sabnzbd uses Pushover -2 — correct), action-required high (\*arr bumps to 1 only for
  ManualInteractionRequired — correct). Never page priority for something with no response.

## Step 4 — Route: use the existing pipeline, don't invent a channel

Prefer **PrometheusRule → Alertmanager** over bespoke webhooks: central grouping, inhibition,
silencing, and history beat N pipelines. The existing plumbing:

- Routing: `kubernetes/apps/observability/kube-prometheus-stack/app/alertmanagerconfig.yaml` —
  default receiver ntfy; `severity=critical` → Pushover (`continue: true`) → ntfy. Groups by
  `[alertname, job]`, groupWait 1m, groupInterval 10m, repeat 12h. Critical inhibits
  same-alertname+namespace warnings. Unactionable stock alerts go to the `null` receiver
  (`InfoInhibitor`, `Watchdog`, `CPUThrottlingHigh`, …) — extend that list rather than tolerate noise.
- ntfy topics/priorities: `kubernetes/apps/observability/alertmanager-ntfy/app/resources/config.yml`
  — media namespace → topic `plex`, else `alertmanager`; critical=urgent, warning=high, info=low.
- Placement: the app's own `.../app/prometheusrule.yaml`, listed in its `kustomization.yaml`.
- HA (out-of-band): route notify → ntfy topics for parity; critical may use ntfy urgent or Pushover.
- Temporary suppression = **silence-operator** `Silence` CRs
  (`kubernetes/apps/observability/silence-operator/silences/silences.yaml`), always with a
  comment saying why. Shelving is triage, not a fix — a months-old silence means the alert
  should be rewritten or deleted.

### Inovelli LED platform (rungs 1–2) — the house annunciator panel

Full design + hardware grammar live in the second brain:
`~/second-brain/Projects/HomeLab/Inovelli LED Notification Platform.md` (30 VZM31-SN switches,
slot assignments, zone map, MQTT payloads). Read it before wiring anything. Design rules:

- **The panel is the household's, not the homelab's.** LED notifications must pass the Step 1
  audience test for Sara, not just Derek. No cluster/infra status on the switches — the panel's
  entire value is that every light on it means something a household member should do.
- **All LED writes go through the Node-RED `led-notify` dispatcher** (Phase 1 shipped). Producers
  emit the normalized message (`id`, `action: set|clear`, `slot`/full-bar, `zone`, `color`,
  `effect`, `level`, `priority`) — never publish to `zigbee2mqtt/<switch>/set` directly. The
  dispatcher owns zone fan-out, priority preemption, Night-mode dimming, and state re-assert.
- **Per-LED slot = standing status; full-bar = transient event.** Don't put a transient on a
  slot or a standing state on the full bar. Slots are the EEMUA "annunciator": same LED means
  the same thing on every switch in the house — check the slot table before claiming one, and
  update the note when you do.
- **Honor the color language** (red security, orange physical-action-needed, green complete,
  blue people, yellow reminder, purple fun). EEMUA is emphatic about consistent presentation:
  a color that means different things in different rooms is worse than no light.
- **Clear discipline is the standing-alarm rule made physical.** Everything sent with
  `duration: 255` needs a named owner and a defined clear condition; an LED that stays on after
  the condition cleared trains the household to ignore the panel — same failure mode as a
  stale Alertmanager alert. Prefer auto-expiring durations for transients.
- **Zones are state-based suppression**: bedtime-relevant only upstairs, guest wing quiet unless
  guest mode, Night mode caps brightness. A new notification must declare its zone, not default
  to house-wide.

## Step 5 — Write the message: cause → consequence → response on a lock screen

```yaml
annotations:
  summary: "UPS on battery — {{ $value }} min runtime left" # cause, glanceable
  description: >- # consequence + response
    Mains power lost. Cluster shuts down cleanly at 5 min runtime.
    Check breaker/utility; shed load if outage will be long.
```

The alertmanager-ntfy bridge already adds severity emoji, namespace tags, click-through, and
action buttons (Prometheus / Grafana alert history / pre-filled silence) — don't duplicate them.
Keep wording consistent per class of problem so pattern recognition works half-asleep.

## Step 6 — Watch it for a week

First-week flapping = tune NOW, not later. Attention budgets (EEMUA rates, one-operator scale):

- **Pushover pages: ~0/week** steady state. Even 1/day desensitizes; the channel dies when it matters.
- **ntfy high: a handful/day**, grouped.
- **Any alert firing >5×/week is a "bad actor"** — EEMUA: the top 10 bad actors typically cause
  \>50% of total load; fixing them is the highest-leverage alerting work there is.
- **Standing alerts are debt** — firing-for-days trains flood-blindness. Fix or shelve (visibly).
  The LED equivalent: the nightly orphan watchdog should never be the thing that clears your
  notification — if it is, your clear condition is broken.
- A page that turned out non-actionable is a **defect**: demote or fix it the same day. Same for
  an LED slot nobody glances at anymore — demote to dashboard or delete.

## The pipeline is itself a system to alarm on

EEMUA devotes a whole chapter to alarm-system health: a dead notification path fails SILENT —
no alerts looks exactly like all-healthy. Design rules:

- **Channel-failure alerts must cross channels.** An "ntfy send failing" alert routed to ntfy
  tells nobody anything. Send-failure alerts for channel A go to channel B (and vice versa).
- **Dead man's switch.** The stock `Watchdog` alert exists to be an always-firing heartbeat
  consumed by something OUTSIDE the cluster (healthchecks.io or similar) that pages when the
  heartbeat STOPS. Null-routing it means end-to-end pipeline death goes unnoticed.
- **Volume is a channel-health input, not just an annoyance.** ntfy rate-limits per visitor;
  a noisy day → 429s → Alertmanager retries (up to ~20×) → MORE requests → sustained saturation
  where real alerts get dropped after retry exhaustion. Floods don't just distract the human,
  they break the pipe. Watch `alertmanager_notifications_failed_total`.
- **Test the paging path on a schedule.** A monthly deliberate test page (and LED test pattern)
  is the fire drill — the worst time to learn Pushover credentials expired is during an outage.

## Auditing the existing posture

```bash
# severity distribution of custom rules (want warning-heavy, critical-scarce)
grep -rh "severity:" kubernetes/apps/*/*/app/*prometheusrule*.yaml kubernetes/apps/*/*/*/prometheusrule.yaml 2>/dev/null | sort | uniq -c

# what's firing right now
kubectl -n observability exec alertmanager-kube-prometheus-stack-0 -- amtool alert query --alertmanager.url=http://localhost:9093
# bad actors over time: Grafana alert-history dashboard (linked from every ntfy notification)
```

## Related

- Docs pipeline overview: `docs/src/apps/observability.md` (Mermaid flow)
- LED platform design (slots, zones, dispatcher, MQTT grammar):
  `~/second-brain/Projects/HomeLab/Inovelli LED Notification Platform.md`
- Skills: `gatus-monitoring` (uptime checks), `externalsecrets` (pushover/ntfy tokens)
- Source: EEMUA Publication 191 (4th ed., 2024) — https://www.eemua.org/products/publications/digital/eemua-publication-191 ; aligned with ISA-18.2 / IEC 62682
