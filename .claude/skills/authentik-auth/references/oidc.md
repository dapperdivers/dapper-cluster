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
