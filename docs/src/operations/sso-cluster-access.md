# SSO Cluster Access (kubectl via Authentik OIDC)

Daily `kubectl` access authenticates against **Authentik** (OIDC). Group membership
in Authentik maps to cluster RBAC. This is layered _on top of_ the existing x509
admin kubeconfig, which remains the untouchable **break-glass** path.

## How it fits together

| Path                  | Depends on Authentik? | Use                                 |
| --------------------- | --------------------- | ----------------------------------- |
| OIDC (`kubelogin`)    | Yes                   | Daily, per-user, revocable, audited |
| x509 admin kubeconfig | **No**                | Break-glass                         |
| `talosctl kubeconfig` | **No**                | Break-glass of last resort          |

The kube-apiserver runs multiple authenticators at once — OIDC is _additive_. The
apiserver validates the x509 admin cert entirely locally against the cluster CA, so
it works even if Authentik is completely down. The OIDC flags use the legacy
`--oidc-*` form, which fetches JWKS lazily: an unreachable Authentik degrades only
OIDC token validation, it never blocks apiserver startup.

- **Provider**: Authentik `Kubernetes OIDC`, public/PKCE client, `client_id: kubectl`.
- **Issuer**: `https://sso.chelonianlabs.com/application/o/kubectl/` (trailing slash required).
- **apiserver flags**: `kubernetes/bootstrap/talos/patches/controller/cluster.yaml`.
- **RBAC**: `kubernetes/apps/kube-system/oidc-rbac/` binds
  `oidc:kubernetes-admins` → `cluster-admin` and `oidc:kubernetes-viewers` → `view`.

## Access tiers

| Authentik group      | Cluster role       |
| -------------------- | ------------------ |
| `kubernetes-admins`  | `cluster-admin`    |
| `kubernetes-viewers` | `view` (read-only) |

Grant access by adding a user to the group in Authentik; revoke by removing them.

## Client setup (one-time)

Install the exec credential plugin:

```bash
kubectl krew install oidc-login   # provides `kubectl oidc-login` / kubelogin
```

Add an OIDC user and context to `~/.kube/config` (leave the existing admin context
untouched):

```yaml
users:
  - name: oidc
    user:
      exec:
        apiVersion: client.authentication.k8s.io/v1beta1
        command: kubectl
        args:
          - oidc-login
          - get-token
          - --oidc-issuer-url=https://sso.chelonianlabs.com/application/o/kubectl/
          - --oidc-client-id=kubectl
          - --oidc-use-pkce
          - --oidc-extra-scope=profile
          - --oidc-extra-scope=email
          - --oidc-extra-scope=offline_access
```

Then add a context that pairs this user with the existing cluster, e.g.:

```bash
kubectl config set-context dapper-oidc --cluster=<existing-cluster> --user=oidc
```

`--oidc-use-pkce` means no client secret is needed; `offline_access` gives a refresh
token so you are not re-prompted every hour.

Verify:

```bash
kubectl --context dapper-oidc auth whoami          # -> oidc:<you> + oidc:kubernetes-admins
kubectl --context dapper-oidc auth can-i '*' '*'   # -> yes (admins)
```

## Break-glass (when Authentik is down or misbehaving)

Neither path below touches Authentik:

1. **x509 admin kubeconfig** — switch back to the original admin context:
   ```bash
   kubectl config use-context <admin-context>
   ```
2. **Regenerate from Talos** — the Talos mTLS PKI is fully independent of Authentik:
   ```bash
   talosctl kubeconfig ./break-glass-kubeconfig
   export KUBECONFIG=./break-glass-kubeconfig
   ```

Keep a copy of `talosconfig` / the admin kubeconfig backed up **off-cluster**. That
backup is what makes the circular-dependency concern (Authentik runs _on_ the cluster
you need it to reach) a non-issue.
