---
name: gatus-monitoring
description: Add or tune Gatus uptime monitoring for a dapper-cluster app. Use when an app should appear on the status page, a Gatus check is flapping/false-alarming, or you need a probe path/condition/opt-out. Covers the gatus-sidecar HTTPRoute auto-discovery model.
allowed-tools: Read, Edit, Write, Bash, Grep, Glob
---

# Gatus monitoring (gatus-sidecar)

Gatus runs the home-operations **gatus-sidecar** chart (`kubernetes/apps/observability/gatus`).
A native sidecar **auto-discovers every HTTPRoute** on the `external` and `internal` Gateways and
writes Gatus endpoints — no per-app config files. Discovery flags:
`--auto-httproute --gateway-name external --gateway-name internal`.

## How an app gets monitored: just have an HTTPRoute

If an app has an HTTPRoute on the external or internal gateway, **it is already monitored** — usually
with zero annotations. The base config is inherited from the **Gateway** annotation
`gatus.home-operations.com/endpoint` (in `kubernetes/apps/network/envoy-gateway/gateway/`):

- **external gateway** → `group: external`, real HTTP probe `[STATUS] == 200`, Cloudflare DNS resolver.
- **internal gateway** → `group: guarded`, `guarded: true` → a **DNS-only** check that asserts the host
  does **not** resolve publicly (`conditions: [len([BODY]) == 0]`). This is the "is this internal app
  accidentally exposed?" check, not an up/down check.

Endpoint **name** = the HTTPRoute's name (so `route.app` → `<release-name>`).

## Per-route overrides

Add a YAML fragment to the app's `route.<key>.annotations`. It deep-merges over the Gateway base
(child wins on scalars):

```yaml
route:
  app:
    annotations:
      gatus.home-operations.com/endpoint: |-
        path: /healthz                       # probe a specific path (default: route's first match path, else /)
        conditions: ["[STATUS] == 200"]      # override conditions
        interval: 2m                          # override interval (default 1m)
```

Real examples in-repo: `media/plex` (`path: /web/index.html`), `media/overseerr`
(`path: /api/v1/status`), `observability/kromgo` (`path: /talos_version`).

## Opt OUT a route

For routes that return non-200 by design (webhooks) or you simply don't want monitored:

```yaml
annotations:
  gatus.home-operations.com/enabled: "false"
```

Example: `flux-system/.../webhooks/httproute.yaml` (returns 404; it's instead monitored by hand in the
central config below).

## Endpoints with no HTTPRoute

Things not backed by a route (e.g. the flux-webhook 404 check, connectivity checks) live hand-written
in the central config: `kubernetes/apps/observability/gatus/app/resources/config.yaml`. That file is a
ConfigMap with `kustomize.toolkit.fluxcd.io/substitute: disabled` — `${VARS}` in it are expanded by
**Gatus at runtime** from the pod's env (`SECRET_DOMAIN`, `GATUS_WEB_PORT`, pushover/ntfy tokens), not
by Flux.

## Gotchas

- `guarded` keys on **presence**, not value — `guarded: false` is _still guarded_. Omit the key to
  un-guard.
- `--auto` means adding any HTTPRoute on these gateways is auto-monitored. An external route that
  isn't `200` on its probe path **will false-alarm** until you add a `path:`/`conditions:` override or
  `enabled: "false"`.
- **Probe path = the route's FIRST match rule, not `/`.** Apps whose HTTPRoute leads with a non-`/`
  rule (websocket `/notifications/hub/negotiate`, `/api/...`, etc.) get probed on that path and 404 a
  plain GET → false UNHEALTHY. Symptom: `success=false; errors=0` (it connected, wrong status) while
  `curl https://host/` returns 200. Fix: add `path: /` (or `/alive`, `/healthz`) override. This bit
  vaultwarden (its first rule is the SignalR `/notifications/hub/negotiate`).
- **Never reuse a PVC that previously held the old kiwigrid `*-gatus-ep.config.yaml` dumps** — Gatus
  loads every `*.yaml` in `/config`, so leftover files collide with the sidecar output
  (`duplicate name+group → panic`). The HR has a `purge-legacy-configmaps` init container for this.
- DEPRECATED: the old `flux/components/gatus/{external,guarded}` configMapGenerator components +
  `GATUS_*` postBuild vars. Don't add new uses; they're being removed.

## Verify

```bash
pod=$(kubectl get pod -n observability -l app.kubernetes.io/name=gatus-sidecar \
  --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1:].metadata.name}')
kubectl logs -n observability "$pod" -c gatus --tail=200 | grep "key=external_<app>"   # success=true/false
kubectl logs -n observability "$pod" -c gatus | grep -c "Reading configuration from"   # want 2 (config.yaml + gatus-sidecar.yaml)
```

Offline render check: `flate build hr gatus -p ./kubernetes/flux/cluster`.

## Related

- Memory: `project_gatus_sidecar_migration.md`, `project_ntfy_alerting.md` (alert routing / pushover limit).
- Skill: `externalsecrets` (the gatus pushover/ntfy tokens come via an ExternalSecret).
