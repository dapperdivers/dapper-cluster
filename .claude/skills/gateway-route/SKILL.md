---
name: gateway-route
description: Expose a dapper-cluster app on the network via an Envoy Gateway HTTPRoute (internal or external). Use when an app needs a hostname/URL, you're adding a new app that serves HTTP, converting an old nginx Ingress to a route, or debugging why a route returns 404/no-DNS. Covers app-template route blocks, standalone HTTPRoutes, apex hosts, multi-controller apps, and validation. For login protection on top of routing, use the authentik-auth skill.
allowed-tools: Read, Edit, Write, Bash, Grep, Glob
---

# Expose an app via Envoy Gateway

The cluster routes all HTTP through **two Envoy Gateways** in the `network` namespace
(nginx is gone). You attach an app by adding an HTTPRoute that references one of them.

| Gateway  | `parentRef name` | VIP           | Reach                        | DNS                                 |
| -------- | ---------------- | ------------- | ---------------------------- | ----------------------------------- |
| internal | `internal`       | `10.100.0.20` | LAN only                     | k8s-gateway (`10.100.0.21`)         |
| external | `external`       | `10.100.0.22` | public via Cloudflare tunnel | external-dns → `*.cfargotunnel.com` |

**internal vs external is chosen purely by the `parentRef` name.** A route on the
`external` Gateway is published publicly automatically — the Gateway carries the tunnel
target, so you do **not** add a per-route `external-dns` target annotation (the
`gateway-httproute` source ignores it; older app manifests still carry inert ones).

Each Gateway has a wildcard HTTPS listener per domain (`*.${SECRET_DOMAIN}`,
`*.${SECRET_DOMAIN_MEDIA}`, `_PERSONAL`, `_DIVING`, `_WIFE`); the external Gateway also has
bare-apex listeners. **Do not set `sectionName`** — the Gateway auto-selects the listener by
matching the route's hostname. Pick the domain via the hostname, not the listener.

## A. app-template apps (the common case)

Add a `route:` block to the HelmRelease values (sibling of `persistence:`). Single
controller, single Service → omit `rules` and it defaults to the primary Service:

```yaml
route:
  app:
    hostnames: ["myapp.${SECRET_DOMAIN}"] # internal
    parentRefs:
      - name: internal # internal | external
        namespace: network
```

### Multi-controller / multi-Service apps — explicit rules required

If the app has more than one controller or Service, app-template can't auto-pick the
backend ("automatic Service detection not possible"). Give **each** route entry an explicit
rule with the controller `identifier` and named `port`:

```yaml
route:
  app:
    hostnames: ["hass.${SECRET_DOMAIN}"]
    parentRefs: [{ name: external, namespace: network }]
    rules:
      - backendRefs: [{ identifier: app, port: http }]
  code-server:
    hostnames: ["hass-code.${SECRET_DOMAIN}"]
    parentRefs: [{ name: internal, namespace: network }]
    rules:
      - backendRefs: [{ identifier: app, port: code-server }]
```

### Apex / bare-domain hosts

A wildcard listener (`*.domain`) does **not** match the bare apex (`domain`). The external
Gateway has apex listeners, so just list every hostname in one entry on the `external`
Gateway — no `sectionName` needed:

```yaml
route:
  app:
    hostnames:
      - "{{ .Release.Name }}.${SECRET_DOMAIN_PERSONAL}"
      - "www.${SECRET_DOMAIN_PERSONAL}"
      - "${SECRET_DOMAIN_PERSONAL}" # apex
    parentRefs: [{ name: external, namespace: network }]
```

## B. Non-app-template charts → standalone HTTPRoute

Charts without app-template (grafana, kube-prometheus-stack, emqx, goldilocks…) get a
hand-written `httproute.yaml` next to the app, added to its `kustomization.yaml`. Point
`backendRefs` at the chart's Service + port:

```yaml
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: goldilocks
  namespace: observability
spec:
  parentRefs:
    - name: internal
      namespace: network
  hostnames: ["goldilocks.${SECRET_DOMAIN}"]
  rules:
    - backendRefs:
        - name: goldilocks-dashboard
          port: 80
```

For self-signed HTTPS upstreams (e.g. unifi, proxmox), use an EnvoyProxy `Backend` +
`tls.insecureSkipVerify: true` and reference it with
`backendRefs: [{ group: gateway.envoyproxy.io, kind: Backend, name: <x> }]`.

## Validate before trusting it

`render` with the **pinned chart version** (named ports resolve to numbers only on ≥5.0.1):

```bash
helm template . --version 5.0.1 --show-only templates/... | grep -A20 HTTPRoute
flate test all          # or: task yaml:validate-all
```

After Flux applies, hit the Gateway VIP directly (bypasses DNS) — internal `.20`, external `.22`:

```bash
curl -sk --resolve myapp.${SECRET_DOMAIN}:443:10.100.0.20 https://myapp.${SECRET_DOMAIN} -o /dev/null -w '%{http_code}\n'
```

Any non-000 code (200/302/401/403) means the route reached the app. Then confirm
`kubectl get httproute -n <ns> <name>` shows `Accepted=True` and `ResolvedRefs=True`.

## Gotchas

- **Cross-check the app is actually live.** A `route:` edit on a dormant app (commented out
  of the namespace `kustomization.yaml`) is inert. Authoritative list:
  `grep '^\s*-\s*\./.+/ks.yaml' kubernetes/apps/<ns>/kustomization.yaml | grep -v '#'`.
- **app-template 5.0.1** resolves named ports → numbers; render/validate with `--version 5.0.1`
  (4.x passes named ports through as strings and `ResolvedRefs` fails).
- Renovate commits to `main` constantly — `git rebase origin/main` before pushing.
- Internal DNS resolves a host to whichever Gateway its route attaches to; if a name doesn't
  resolve on the LAN, the route is probably on `external` (or not Accepted yet).

## Related

- Skill: `authentik-auth` — add login protection (one annotation on the route block).
- Skill: `gatus-monitoring` — the status page auto-discovers HTTPRoutes.
- Skill: `find-app` — scaffolds the rest of a new app's directory.
- Files: `kubernetes/apps/network/envoy-gateway/{app,gateway}/`.
