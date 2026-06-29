---
name: externalsecrets
description: Write or fix ExternalSecrets in dapper-cluster (Infisical ClusterSecretStore). Use when adding a secret to an app, an ExternalSecret shows SecretSyncedError, or a key isn't resolving. Enforces the find:name regexp pattern and avoids the find:path / remoteRef.key pitfalls.
allowed-tools: Read, Edit, Write, Bash, Grep, Glob
---

# ExternalSecrets (Infisical)

Secrets in this cluster come from **Infisical** via External Secrets Operator. Apps declare an
`ExternalSecret` that targets a Kubernetes `Secret`; the app consumes that Secret via `envFrom` /
`secretRef`. Never commit plaintext secrets.

## The one rule that matters: use `find: name: regexp`

Infisical keys live in **folders** (reorganised into `/Infrastructure/...` paths). The provider
resolves keys by **recursive name search**, so always look keys up by NAME regexp:

```yaml
dataFrom:
  - find:
      name:
        regexp: ^MYAPP_.*
```

### Do NOT use these (they break)

- ❌ `find: path: <KEY>` — `path` is a **folder** filter, not a key matcher. This silently matched
  nothing after the Infisical folder reorg and took out secrets **cluster-wide**. (The "find:path bug".)
- ❌ `data: - remoteRef: { key: <KEY> }` — a direct path-scoped lookup. Fragile for any key that
  lives in a subfolder; prefer `find: name:`.

## Canonical template

Mirror `kubernetes/apps/network/smtp-relay/app/externalsecret.yaml`:

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/external-secrets.io/externalsecret_v1beta1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: myapp
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: infisical # also: infisical-postgres, infisical-chelonian (scoped variants)
  target:
    name: myapp-secret # the k8s Secret the app mounts
    template:
      engineVersion: v2
      data:
        # Rename / shape keys here. RHS refers to the found Infisical keys by name.
        # You can also splice Flux substitutions, e.g. ${SECRET_DOMAIN}.
        MYAPP_TOKEN: "{{ .MYAPP_TOKEN }}"
        MYAPP_PASSWORD: "{{ .MYAPP_ADMIN_PASSWORD }}"
  dataFrom:
    - find:
        name:
          regexp: ^MYAPP_.*
```

Notes:

- With a `template.data` block, the target Secret contains **only** the templated keys; `dataFrom`
  just populates the template variables. Use this to rename (e.g. `MYAPP_ADMIN_PASSWORD` → the
  `MYAPP_PASSWORD` env the container expects).
- The regexp is greedy by prefix — `^NTFY_.*` will also pull a later `NTFY_TOKEN`. Harmless if the
  template only outputs what the app needs.
- The ks.yaml usually needs `dependsOn: external-secrets-stores` (namespace `external-secrets`).

## Prerequisite: the key must exist in Infisical first

ESO can only sync keys that exist in Infisical. Adding a _new_ app's creds is a two-part job:
**Derek adds the keys to Infisical**, then Flux syncs. Until then the ExternalSecret stays
`SecretSyncedError` and the pod won't start (it's waiting on the Secret). This is expected, not a bug.

## Verify

```bash
kubectl get externalsecret -n <ns> <name>          # want: STATUS=SecretSynced, READY=True
kubectl describe externalsecret -n <ns> <name>     # shows the resolved/missing keys on error
task kubernetes:view-secret NS=<ns> SECRET=<target>   # decode the synced Secret, confirm keys present
```

Force a resync after changing keys in Infisical (annotates every ExternalSecret
with `force-sync`): `task kubernetes:sync-secrets`. The `task` helpers set
`KUBECONFIG` automatically when run from the repo root.

`flate` auto-skips in-repo ExternalSecrets with a static target name during offline render, so a green
`flate` does **not** prove the keys exist in Infisical — only that the manifest is valid.

## Related

- Memory: `project_infisical_find_path_bug.md` (the cluster-wide outage this rule prevents).
