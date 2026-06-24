---
name: authentik-auth
description: Add or change Authentik SSO for a dapper-cluster app (forward-auth proxy or native OIDC), managed declaratively via Envoy Gateway annotations + Authentik blueprints. Use when an app needs login protection, you're adding a new gated app, or fixing/auditing the forward-auth or OIDC wiring.
tools: Read, Edit, Write, Bash, Grep, Glob
---

# Authentik auth (forward-auth + OIDC)

Two auth models. Pick by whether the **app** can do OIDC itself:

| | **Forward-auth (proxy provider)** | **Native OIDC** |
|---|---|---|
| Enforcer | Envoy `SecurityPolicy` → Authentik outpost (app is dumb) | the app (it's an OAuth client) |
| Route annotation | `authentik.home.arpa/forward-auth: "true"` | **none** (plain route) |
| Authentik object | proxy provider + app, assigned to embedded outpost | OAuth2 provider + app |
| Secrets in app | none | client_id + client_secret |
| Examples | all *arr, firefly (header variant) | actual, open-webui, proxmox |

Everything is GitOps. Route gating = an HTTPRoute annotation (Kyverno generates the rest). Authentik
side = a blueprint in `kubernetes/apps/security/authentik/app/blueprints.yaml` (one ConfigMap key
`forward-auth.yaml`, delivered to the worker via the chart's `blueprints.configMaps`).

---

## A. Add a forward-auth app (the common case)

### 1. Gate the route — one annotation
On the app's `route.<key>.annotations` (app-template) or the standalone HTTPRoute:
```yaml
route:
  app:
    annotations:
      authentik.home.arpa/forward-auth: "true"
    hostnames: ["newapp.${SECRET_DOMAIN}"]
    parentRefs: [{ name: internal, namespace: network }]   # internal | external
```
Kyverno (`kyverno/policies/httproute-authentik-forward-auth.yaml`) auto-generates the `SecurityPolicy`
(ext-auth → outpost) **and** a per-namespace `ReferenceGrant` (works in any namespace, no edits). Done.

### 2. Define the Authentik provider + app — in `blueprints.yaml`, key `forward-auth.yaml`
Add a block under `entries:` (everything else is inherited from the `&proxy` anchor):
```yaml
  # newapp
  - model: authentik_providers_proxy.proxyprovider
    identifiers: { name: Provider for Newapp }
    id: newapp-provider
    attrs: { <<: *proxy, external_host: "https://newapp.${SECRET_DOMAIN}" }
  - model: authentik_core.application
    identifiers: { slug: newapp }
    attrs: { name: Newapp, group: media_internal, provider: !KeyOf newapp-provider,
             meta_icon: "https://cdn.jsdelivr.net/gh/selfhst/icons/svg/newapp.svg",
             meta_launch_url: "https://newapp.${SECRET_DOMAIN}" }
```
- `id:` must be unique; `!KeyOf <id>` binds the app to its provider.
- Add `skip_path_regex: "^/api([/?].*)?$"` to the provider `attrs` **only** if the app needs an
  unauthenticated API bypass (clients hitting `/api`). Omit it to require auth on everything.
- `group` = portal bucket (e.g. `media_internal`, `home`). `meta_icon` uses
  `cdn.jsdelivr.net/gh/selfhst/icons/` (bare `selfh.st` URLs 404).
- `identifiers` matching an existing object **adopts it in place** (no duplicate); a new slug creates it.

### 3. Assign it to the outpost — one line
In the same file, the `authentik_outposts.outpost` entry has a `providers:` list. Add:
```yaml
        - !KeyOf newapp-provider
```
This is what actually makes the outpost gate the host. **Skipping it = the app shows a 500/“provider
not found” on login.** (The outpost entry also disables the k8s Ingress — leave that alone.)

### 4. Validate, push, apply
```bash
kustomize build kubernetes/apps/security/authentik/app/ >/dev/null && echo OK
git add kubernetes/apps/security/authentik/app/blueprints.yaml && git commit && git push
flux reconcile source git flux-system && flux reconcile kustomization authentik -n security
```

### 5. Make Authentik discover it (the mount lags ~60–90s)
The ConfigMap mount updates, then Authentik discovers on a schedule. To force it:
```bash
pod=$(kubectl get pods -n security -l app.kubernetes.io/instance=authentik,app.kubernetes.io/component=worker \
  --field-selector status.phase=Running -o name | head -1)
kubectl exec -n security "$pod" -c worker -- ak shell -c \
  "from authentik.blueprints.v1.tasks import blueprints_discovery; blueprints_discovery.send()"
```
**Do not spam discovery/apply** — concurrent outpost updates can hit a Postgres deadlock (see Gotchas).

### 6. Verify
```bash
TOKEN=$(kubectl get secret authentik-secret -n security -o jsonpath='{.data.AUTHENTIK_BOOTSTRAP_TOKEN}' | base64 -d)
API=https://sso.${SECRET_DOMAIN}/api/v3   # substitute the real domain
auth=(-H "Authorization: Bearer $TOKEN" -H "Accept: application/json")
curl -sS "${auth[@]}" "$API/managed/blueprints/?search=forward-auth-apps" | jq '.results[0].status'  # successful
curl -sI https://newapp.${SECRET_DOMAIN}      # 302 -> sso... (gated). /api -> app's own 401 if bypassed
```

---

## B. Add a native-OIDC app

App enforces auth itself, so **no `forward-auth` annotation** — just a plain route.

1. **Infisical**: create `NEWAPP_OIDC_CLIENT_ID` / `_SECRET` (for the app) and the SAME values as
   `AUTHENTIK_NEWAPP_CLIENT_ID` / `_SECRET` (the `^AUTHENTIK.*` keys land in the worker env → blueprint `!Env`).
2. **App HR**: OIDC env — issuer/discovery `https://sso.${SECRET_DOMAIN}/application/o/newapp/`,
   client_id/secret from its ExternalSecret. (See `selfhosted/actual` for the pattern.)
3. **Blueprint** (`forward-auth.yaml` or a new key):
```yaml
  - model: authentik_providers_oauth2.oauth2provider
    identifiers: { name: newapp }
    id: newapp-oidc
    attrs:
      client_type: confidential
      client_id: !Env AUTHENTIK_NEWAPP_CLIENT_ID
      client_secret: !Env AUTHENTIK_NEWAPP_CLIENT_SECRET
      authorization_flow: !Find [authentik_flows.flow, [slug, default-provider-authorization-implicit-consent]]
      redirect_uris: [{ matching_mode: strict, url: "https://newapp.${SECRET_DOMAIN}/oauth/callback" }]
      property_mappings:
        - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-openid]]
        - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-email]]
        - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-profile]]
  - model: authentik_core.application
    identifiers: { slug: newapp }
    attrs: { name: Newapp, provider: !KeyOf newapp-oidc }
```
**Do NOT** add an OIDC provider to the outpost `providers:` list (that's forward-auth only).
**Migrating an existing OIDC app:** first read its current client_id/secret from the API and put them
in Infisical, so the `!Env` blueprint is a no-op (otherwise it overwrites the creds and breaks login).

---

## Gotchas

- **Outpost-update deadlock (transient):** changing the outpost `providers:` list triggers an Authentik
  permission rebuild that can hit `DeadlockDetected` under concurrency → blueprint `status=error`. Just
  re-apply once on a quiet window — it succeeds: `POST $API/managed/blueprints/<pk>/apply/`. Don't fire
  multiple discoveries at once.
- **Forgot the `!KeyOf` line:** provider/app exist but the outpost won't gate the host. Add it.
- **Icons & app config are live-only** unless in a blueprint; manage via the blueprint, not the UI.
- **`hass`/`vault`** have leftover proxy providers not on the outpost (they use OIDC/native) — don't add
  them to forward-auth.
- The blueprint **adopts by `identifiers`** and never deletes objects you remove from the file — to
  retire an app, remove its entries AND `DELETE` the live provider+app via the API (apps first).
- `blueprints.yaml` was bootstrapped once from live state by a throwaway script; it is **hand-maintained
  now** (no codegen in the Flux flow).
