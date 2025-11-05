# Migration Script Setup

This directory contains a Kubernetes job for migrating movie files from NFS to CephFS.

## File Structure

- **`scripts/migrate.sh`** - The actual migration script (edit this file)
- **`scripts/sync-configmap.sh`** - Helper script to sync .sh → .yaml
- **`migrate-configmap.yaml`** - Auto-generated ConfigMap (do not edit directly)
- **`migrate-job-parallel.yaml`** - Kubernetes Job definition
- **`kustomization.yaml`** - Kustomize configuration

## Workflow

### Updating the Migration Script

1. Edit `scripts/migrate.sh` with your changes
2. Run the sync script:
   ```bash
   cd scripts && ./sync-configmap.sh
   ```
3. Commit both files:
   ```bash
   git add scripts/migrate.sh migrate-configmap.yaml
   git commit -m "fix(migration): your change description"
   ```

### Why Two Files?

- **`migrate.sh`**: Clean shell script with proper syntax highlighting
- **`migrate-configmap.yaml`**: Generated YAML that Flux/Kustomize can use
- The annotation `kustomize.toolkit.fluxcd.io/substitute: disabled` prevents Flux from mangling bash variables like `${VAR}`

## Key Features

- ✅ File count verification before deletion
- ✅ Parallel processing (4 workers per pod)
- ✅ Resume capability via checkpoints
- ✅ DRY_RUN mode for testing
- ✅ Handles filenames with special characters (quotes, spaces, etc.)
- ✅ Optimized rsync (no compression, delta transfer)

## Configuration

Set these environment variables in `migrate-job-parallel.yaml`:

- `DRY_RUN`: `true` or `false` (default: `false`)
- `SOURCE`: Source path (default: `/tower-2/movies`)
- `DEST`: Destination path (default: `/destination/movies`)
- `PARALLEL_JOBS`: Worker count (default: `4`)

## Monitoring

Check logs for letter-based progress:
```bash
kubectl logs -n media -l app.kubernetes.io/name=migrate-job-parallel -c app -f
```

Check migration metrics:
```bash
kubectl exec -n media deploy/some-pod -- ls -lh /metrics/
```
