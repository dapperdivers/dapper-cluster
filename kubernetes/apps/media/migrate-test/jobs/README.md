# Automated Migration Jobs

Individual migration jobs that run rsync automatically instead of interactively.

## Quick Start

1. **Choose which jobs to run** in `jobs/kustomization.yaml`:
   ```yaml
   resources:
     - ./migrate-audiobooks.yaml     # Uncomment to enable
     - ./migrate-pmm-test.yaml       # Uncomment to enable
     # etc.
   ```

2. **Commit and push**:
   ```bash
   git add .
   git commit -m "feat(media): enable migration jobs"
   git push
   ```

4. **Monitor progress**:
   ```bash
   # Watch all migration jobs
   kubectl get jobs -n media -l app.kubernetes.io/name=~migrate

   # Check logs for specific job
   kubectl logs -n media -l app.kubernetes.io/instance=migrate-audiobooks -f

   # View in Grafana
   # https://grafana.${SECRET_DOMAIN}/d/media-storage
   ```

## Available Jobs

| Job | Source | Size | Time Estimate |
|-----|--------|------|---------------|
| `migrate-audiobooks` | `/tower-2/audiobooks` | 16.1GB | ~12 min |
| `migrate-pmm-test` | `/tower-2/pmm-test` | 21.2GB | ~16 min |
| `migrate-pictures` | `/tower-2/pictures` | 24.2GB | ~18 min |
| `migrate-downloads` | `/tower-2/downloads` | 101.9GB | ~1.2 hours |
| `migrate-homework` | `/tower-2/homework` | 120.1GB | ~1.5 hours |

## How It Works

Each job:
- ✅ Runs rsync with optimized flags (`--whole-file`, `--no-inc-recursive`)
- ✅ Deletes source files after successful copy (`--remove-source-files`)
- ✅ Logs to `/metrics/migration.log` (parsed by Grafana)
- ✅ Runs as UID 1000, GID 140, fsGroup 150 (matches other media apps)
- ✅ Auto-retries up to 3 times on failure
- ✅ Keeps completed job for 24 hours (`ttlSecondsAfterFinished: 86400`)

## Re-running a Job

Jobs are immutable. To re-run:

```bash
# Delete the job
kubectl delete job -n media migrate-audiobooks

# Delete the HelmRelease (Flux will recreate it)
kubectl delete helmrelease -n media migrate-audiobooks

# Flux will automatically recreate and run it
```

Or simply comment it out in `kustomization.yaml`, commit, wait for reconcile, then uncomment and commit again.

## Cleanup After Completion

After a job completes, empty source directories remain. To clean them up:

```bash
# Exec into the interactive migration pod
export MPOD=$(kubectl get pods -n media -l app.kubernetes.io/name=migrate-test-dryrun -o name)
kubectl exec -it -n media $MPOD -- /bin/sh

# Inside container:
find /tower-2 -type d -empty -delete
```

## Running Multiple Jobs in Parallel

You can enable multiple jobs at once! They'll run in parallel:

```yaml
resources:
  - ./migrate-audiobooks.yaml
  - ./migrate-pmm-test.yaml
  - ./migrate-pictures.yaml
```

**Recommended**: Run 3-5 jobs in parallel based on:
- Network bandwidth (10Gb link)
- Ceph write capacity
- NFS server load

Monitor with Grafana to ensure performance stays healthy.

## For Massive Folders (Movies/TV)

For the 80TB movies and 59TB tv folders, create dedicated jobs with:
- Longer timeouts
- Higher resource limits
- Consider splitting into subdirectories

See parent README.md for more details.
