# Authentik native-OIDC apps

Reference for the `authentik-auth` skill, Part B. The app self-enforces OIDC
(plain route, no `forward-auth` annotation); these live in the separate
`authentik-oidc` blueprint (`app/blueprints-oidc.yaml`).

App enforces auth itself, so **no `forward-auth` annotation** — just a plain route. OIDC apps live in a
SEPARATE blueprint: `app/blueprints-oidc.yaml` (ConfigMap `authentik-oidc`, 2nd entry in the HR's
`blueprints.configMaps`). Shared config is the `&oidc` anchor; each app overrides only `redirect_uris`.

**Adopting an existing OIDC app** (already working): OMIT `client_id`/`client_secret` from the blueprint
→ adoption preserves the live creds (which match the app's Infisical value), zero risk. That's how
actual/open-webui/proxmox are done. DR caveat: re-enter the secret once on a from-scratch rebuild.

**A brand-new OIDC app** needs the creds set, via `!Env` from the worker env:

1. **Infisical**: create `NEWAPP_OIDC_CLIENT_ID` / `_SECRET` (for the app) and the SAME values as
   `AUTHENTIK_NEWAPP_CLIENT_ID` / `_SECRET` in authentik's scope (`^AUTHENTIK.*` → worker env → `!Env`).
   NOTE: app secrets and the authentik worker use DIFFERENT Infisical stores (`infisical` vs
   `infisical-authentik`), so this is a deliberate duplicate, not a shared key.
2. **App HR**: OIDC env — issuer/discovery `https://sso.${SECRET_DOMAIN}/application/o/newapp/`,
   client_id/secret from its ExternalSecret. (See `selfhosted/actual` for the pattern.)
3. **Blueprint** (`blueprints-oidc.yaml`), adding `client_id: !Env …` / `client_secret: !Env …` to attrs:

```yaml
- model: authentik_providers_oauth2.oauth2provider
  identifiers: { name: newapp }
  id: newapp-oidc
  attrs:
    client_type: confidential
    client_id: !Env AUTHENTIK_NEWAPP_CLIENT_ID
    client_secret: !Env AUTHENTIK_NEWAPP_CLIENT_SECRET
    authorization_flow:
      !Find [authentik_flows.flow, [slug, default-provider-authorization-implicit-consent]]
    redirect_uris:
      [{ matching_mode: strict, url: "https://newapp.${SECRET_DOMAIN}/oauth/callback" }]
    property_mappings:
      - !Find [
          authentik_providers_oauth2.scopemapping,
          [managed, goauthentik.io/providers/oauth2/scope-openid],
        ]
      - !Find [
          authentik_providers_oauth2.scopemapping,
          [managed, goauthentik.io/providers/oauth2/scope-email],
        ]
      - !Find [
          authentik_providers_oauth2.scopemapping,
          [managed, goauthentik.io/providers/oauth2/scope-profile],
        ]
- model: authentik_core.application
  identifiers: { slug: newapp }
  attrs: { name: Newapp, provider: !KeyOf newapp-oidc }
```

**Do NOT** add an OIDC provider to the outpost `providers:` list (that's forward-auth only).
**Migrating an existing OIDC app:** first read its current client_id/secret from the API and put them
in Infisical, so the `!Env` blueprint is a no-op (otherwise it overwrites the creds and breaks login).

---

## Non-web-app OIDC consumers (Proxmox VE, and similar appliances)

Some OIDC clients aren't web apps with an app HelmRelease — they're appliances configured
**outside Git**. Proxmox is the canonical case (set up 2026-06-30; see memory
`project-proxmox-oidc`). The Authentik blueprint side is normal (provider+app in
`blueprints-oidc.yaml`, creds preserved-live by omission); the _consumer_ side is the twist.

**Proxmox VE realm** lives in `/etc/pve/domains.cfg` — cluster-replicated, so configure on ANY
one node via `ssh` + `pveum`. NOT GitOps. PVE 8.x:

```bash
pveum realm add authentik --type openid \
  --issuer-url 'https://sso.${SECRET_DOMAIN}/application/o/proxmox/' \   # TRAILING SLASH — required
  --client-id <id> --client-key <secret> \
  --username-claim preferred_username \
  --groups-claim groups --autocreate 1 --default 0
pveum group add proxmox-admins-authentik           # PVE names synced groups <claim>-<realm>
pveum acl modify / --group proxmox-admins-authentik --role Administrator
```

Authentik group `proxmox-admins` (declare it + membership in `blueprints-oidc.yaml` as an
`authentik_core.group` entry) → PVE syncs it as `proxmox-admins-authentik`.

**Gotchas (all cost real debug time):**

- **Issuer trailing slash (exact match).** PVE string-compares the configured `issuer-url` against
  the discovery doc's `issuer` field. Authentik publishes it **with** a trailing slash
  (`.../application/o/<slug>/`), so the realm `issuer-url` MUST include it. No-slash →
  `Validation error: unexpected issuer URI`. (Discovery _fetch_ works either way; only the equality
  check is strict.) This is general to any strict OIDC consumer, not just PVE.
- **`username-claim` = `preferred_username`.** Authentik does NOT emit a bare `username` claim
  (the `profile` scope gives `preferred_username` + `nickname`). Users land as `<name>@authentik`.
- **Groups need no custom scope mapping.** Authentik's default `profile` scope already returns a
  `groups` claim (list of group names); with `include_claims_in_id_token: true` (the `&oidc` anchor)
  it's in the ID token. Just set `groups-claim groups` on the consumer.
- **PVE group naming `<claim>-<realm>`.** Pre-create `<group>-authentik` + its ACL before first
  login, and keep `groups-autocreate 0` so PVE doesn't spawn a group for every Authentik group the
  user is in.
- **Redirect URI = the browser origin**, i.e. the reverse-proxy host the user visits
  (`https://proxmox.${SECRET_DOMAIN}`), because PVE builds `redirect_uri` from `window.location.origin`.
  List every proxied host that serves the GUI. Strip stale ones.

**Headless validation (no browser):**

```bash
# PVE builds the authorize URL → proves realm config + discovery fetch + issuer match
AUTHURL=$(ssh proxmox-01 "pvesh create /access/openid/auth-url --realm authentik \
  --redirect-url https://proxmox.${SECRET_DOMAIN}" | tr -d '"')
curl -sk -o /dev/null -w '%{http_code}\n' "$AUTHURL"    # 302 into default-authentication-flow = good
# Read live provider creds to feed the consumer:
TOKEN=$(kubectl -n security get secret authentik-secret -o jsonpath='{.data.AUTHENTIK_BOOTSTRAP_TOKEN}' | base64 -d)
curl -sk -H "Authorization: Bearer $TOKEN" "https://sso.${SECRET_DOMAIN}/api/v3/providers/oauth2/?search=Proxmox"
```

**Flaky login during bring-up is usually NOT your config.** Intermittent `upstream request timeout`
(Envoy 15s) and `authentication failure (401)` both trace to Authentik being briefly slow (single
replica) — the 401 is a single-use auth code (~60s) expiring mid-stall. Confirm via the token+userinfo
`200`s in the authentik-server log. See memory `project-authentik-stability`.
