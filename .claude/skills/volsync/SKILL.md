---
name: volsync
description: Add VolSync-backed persistent storage to a dapper-cluster app, or fix a new app whose PVC is stuck Pending on first deploy. Covers the volsync repository+operations components, required substitutions, and the create-the-backup-directory-first bootstrap trap.
tools: Read, Edit, Write, Bash, Grep, Glob
---

# VolSync persistence

Most stateful apps back their data with **VolSync** (restic, dual-target: local + R2 offsite) via the
shared components in `kubernetes/flux/components/volsync/`. VolSync also provides **deploy-or-restore**:
on a fresh cluster the app's PVC is auto-restored from backup before first use.

## Wire it up (3 pieces)

**1. `ks.yaml`** — add the components + capacity substitution + the volsync dependency:

```yaml
spec:
  components:
    - ../../../../flux/components/volsync/repository
    - ../../../../flux/components/volsync/operations
  dependsOn:
    - name: volsync
      namespace: storage
    - name: external-secrets-stores
      namespace: external-secrets
  postBuild:
    substitute:
      APP: *app                 # the PVC + restic repo are named after ${APP}
      VOLSYNC_CAPACITY: 1Gi     # app data PVC size (default 5Gi)
```

Optional substitutions (defaults in parens): `VOLSYNC_STORAGECLASS` (ceph-rbd),
`VOLSYNC_SNAPSHOTCLASS` (ceph-rbd-snapshot), `VOLSYNC_COPYMETHOD` (Snapshot),
`VOLSYNC_CACHE_CAPACITY` (10Gi), `VOLSYNC_ACCESSMODES` (ReadWriteOnce), `VOLSYNC_SCHEDULE` (`0 * * * *`),
`VOLSYNC_PUID`/`VOLSYNC_PGID` (1000/150 — the data is chown'd to this; the app pod must run as a
compatible uid/gid).

**2. `helmrelease.yaml`** — mount the PVC the `operations` component creates (named `${APP}`):

```yaml
persistence:
  data:
    existingClaim: ntfy # == ${APP}
    globalMounts:
      - path: /var/lib/ntfy
```

**3. Restic secrets** — the components pull repo creds from Infisical via ExternalSecrets that use the
`find: name: ^${APP}-volsync.*` pattern → Secrets `${APP}-volsync-secret` (local) and
`${APP}-volsync-r2-secret` (R2). Usually nothing to add per-app; see the `externalsecrets` skill.

## ⚠️ The bootstrap trap: NEW app → PVC stuck `Pending`

On a brand-new app the data PVC has a `dataSourceRef` to a bootstrap `ReplicationDestination`
(`${APP}-dst`). That mover restores from the restic repo at the **backup directory** defined by the
`volsync-${APP}-repo` PV (the `repository` component). **If that directory doesn't exist yet on the
backup target, the mover can't initialise the repo → the PVC populator hangs → the app pod sits
`Pending` forever** with:

```
FailedScheduling: pod has unbound immediate PersistentVolumeClaims. not found
RD condition:     Synchronizing=False :: Waiting for manual trigger
```

**Fix: create the backup repo directory first** (on the NAS / R2 target — the path the
`volsync-${APP}-repo` PV points at). Once it exists, the mover runs:

```
=== Initialize Dir === created restic repository … at /repository
No eligible snapshots found === No data will be restored
```

…the PVC binds, and the pod schedules. This is a one-time step per new app (existing apps already have
their directory). The chicken-and-egg is inherent to deploy-or-restore — backup target must exist
before the first restore-or-init.

## Unlock a stale restic repo

If a backup/restore mover is interrupted (node reboot, OOM, eviction), restic leaves a **stale lock**
in the repo. The next `ReplicationSource` backup (or a restore) then fails:

```
unable to create lock in backend: repository is already locked exclusively by …
Fatal: failed to refresh lock … / unlock first
```

Clear it with the Taskfile (patches `replicationsources.spec.restic.unlock` with a timestamp, which
makes VolSync run `restic unlock` on the next reconcile):

```bash
task volsync:unlock NS=<namespace> REPO=<app>     # one app (REPO == the ReplicationSource name == ${APP})
task volsync:unlock-all                            # sweep every ReplicationSource cluster-wide
```

Related Taskfile helpers (`.taskfiles/volsync/Taskfile.yaml`):

- `task volsync:list` — show every ReplicationSource and its last backup time.
- `task volsync:snapshot NS=<ns> APP=<app>` — trigger a manual backup and wait for the job.
- `task volsync:run NS=<ns> REPO=<app> -- snapshots` — run an arbitrary restic command (e.g. list snapshots).
- `task volsync:restore NS=<ns> APP=<app> PREVIOUS=<n>` — restore an app from a backup.

A stuck **restore** (the bootstrap trap above) is different from a stuck **backup** (stale lock): the
former needs the backup directory to exist; the latter needs an unlock.

## Verify

```bash
kubectl get pvc -n <ns> <app>                                   # want STATUS=Bound
kubectl get replicationdestination -n <ns> <app>-dst -o jsonpath='{.status.latestMoverStatus.logs}'
kubectl get pod -n <ns> -l app.kubernetes.io/name=<app>         # Pending → unbound PVC (see trap above)
```

If the mover never runs, check the `${app}-volsync*` Secrets synced (ExternalSecret), then that the
backup directory exists.

## Related

- Skill: `externalsecrets` (restic repo creds resolution).
- Component docs: `kubernetes/flux/components/volsync/README.md`, `ARCHITECTURE.md`.
- Memory: `project_infisical_find_path_bug.md` (the find:path bug once broke all volsync restic secrets).
