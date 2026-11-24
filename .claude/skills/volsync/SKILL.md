---
name: volsync
description: Add VolSync-backed persistent storage to a dapper-cluster app, or fix a new app whose PVC is stuck Pending on first deploy. Covers the volsync repository+operations components, required substitutions, and the backup-directory bootstrap (auto-created by Kyverno; manual fallback).
allowed-tools: Read, Edit, Write, Bash, Grep, Glob
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
      APP: *app # the PVC + restic repo are named after ${APP}
      VOLSYNC_CAPACITY: 1Gi # app data PVC size (default 5Gi)
```

**Backup minutes are spread automatically; don't set a schedule unless you need a specific one.**
All `ceph-rbd` volumes share three SSD OSDs, and 30+ snapshots taken in the same minute stalled
them for 5-8 seconds (BlueStore slow ops, November 2026). The component defaults are `0 * * * *`
(local, hourly) and `30 0 * * *` (R2, daily), and the Kyverno MutatingPolicy
`volsync-schedule-stagger` (`kubernetes/apps/kyverno/kyverno/policies/`) rewrites the minute of
any ReplicationSource still on a default: `sha256(sourcePVC) % 60` for local, that plus 30 for R2.
So the live schedule differs from the template, and that is expected:

```bash
kubectl get replicationsource -A -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,SCHEDULE:.spec.trigger.schedule
```

Set `VOLSYNC_SCHEDULE` / `VOLSYNC_SCHEDULE_REMOTE` only for a different cadence (e.g.
`"5 */6 * * *"`); the policy leaves any non-default schedule alone.

Other optional substitutions (defaults in parens): `VOLSYNC_STORAGECLASS` (ceph-rbd),
`VOLSYNC_SNAPSHOTCLASS` (ceph-rbd-snapshot), `VOLSYNC_COPYMETHOD` (Snapshot),
`VOLSYNC_CACHE_CAPACITY` (10Gi), `VOLSYNC_ACCESSMODES` (ReadWriteOnce),
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

**This is automated now.** The `volsync-${APP}-repo` PV is a static CephFS PV with
`rootPath: /volsync/${APP}`. When Flux creates it, the Kyverno GeneratingPolicy
`volsync-repository-mkdir` (`kubernetes/apps/kyverno/kyverno/policies/`) generates a one-shot Job
`rook-ceph/mkdir-volsync-${APP}` that creates the directory through libcephfs. kubelet then retries
the mount by itself (the backoff can take a minute or two). Nothing needs to happen before merging.

If it didn't fire (Kyverno down, the PV predates the policy, or the directory was deleted later):

```bash
kubectl -n rook-ceph logs job/mkdir-volsync-<app>   # the Job self-deletes 24h after it finishes
task volsync:mkdir APP=<app>    # manual fallback; idempotent, runs libcephfs in rook-ceph-tools
```

(The Proxmox hosts no longer mount CephFS, so don't `mkdir` there.) Once the directory exists, the mover runs:

```
=== Initialize Dir === created restic repository … at /repository
No eligible snapshots found === No data will be restored
```

…the PVC binds, and the pod schedules. Don't name your own Jobs `volsync-*`: the `volsync-mover-cephfs`
MutatingAdmissionPolicy matches that prefix and rejects Jobs without VolSync's `created-by` label.

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

- `task volsync:mkdir APP=<app>` — manual fallback for the repo directory (normally created by Kyverno).
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
