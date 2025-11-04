# Media Migration Job

Interactive migration job for moving data from NFS (Unraid) to CephFS.

## Quick Start

```bash
# 1. Deploy
git add kubernetes/apps/media/migrate-test/
git commit -m "feat(media): deploy migration job"
git push

# 2. Wait for pod to start
kubectl get pods -n media -l app.kubernetes.io/name=migrate-test-dryrun

# 3. Exec into container
export MPOD=$(kubectl get pods -n media -l app.kubernetes.io/name=migrate-test-dryrun -o name)
kubectl exec -it -n media $MPOD -- /bin/sh

# 4. Inside container - explore and migrate!
ls -lh /tower/
ls -lh /tower-2/
du -sh /tower/*
rsync -av --dry-run --stats /tower/movies/ /destination/movies/
```

## How It Works

The job deploys a container with:
- **Source NFS #1**: `/tower/` → tower.manor:/mnt/user/Media (media-tower-pvc)
- **Source NFS #2**: `/tower-2/` → tower-2.manor:/mnt/user/Media (media-tower-2-pvc)
- **Destination CephFS**: `/destination/` → CephFS /truenas/Media (media-cephfs-pvc)
- **Container**: `instrumentisto/rsync-ssh:latest` with rsync, sh, common tools (Alpine-based)
- **Mode**: Sleeps for 1 hour, allowing interactive `kubectl exec` sessions

**Note**: Each PVC mounts the **full** `/mnt/user/Media` directory from NFS servers, and the full `/truenas/Media` from CephFS.

**Important Notes**:
- **Jobs are immutable**: To update the configuration, you must delete the existing Job first: `kubectl delete job -n media migrate-test-dryrun`
- **Flux health checks disabled**: The Kustomization has `wait: false` because the Job runs for 1 hour. Flux won't wait for completion.

### Mount Structure

```
Container filesystem:
/tower/                # tower.manor:/mnt/user/Media
  ├── movies/
  ├── tv/
  ├── music/
  └── ...

/tower-2/              # tower-2.manor:/mnt/user/Media
  ├── movies/
  ├── tv/
  └── ...

/destination/          # CephFS /truenas/Media
  ├── movies/          # Migrated content goes here
  ├── tv/
  └── ...
```

## Interactive Migration

Once exec'd into the container, you have full control:

```bash
# Explore what's available
ls -lh /tower/
ls -lh /tower-2/
du -sh /tower/*
du -sh /tower-2/*

# Test with dry-run (shows what would happen, safe)
rsync -av --dry-run --stats /tower/movies/ /destination/movies/

# Copy files (keeps source intact)
rsync -av --stats /tower/movies/ /destination/movies/

# Move files (deletes source after successful copy)
rsync -avc --remove-source-files --stats /tower/movies/ /destination/movies/

# Check progress
du -sh /destination/movies/
```

## Recommended Commands

### Testing: Dry-run (safe, shows what would happen)
```bash
rsync -a --stats --dry-run /source/folder/ /destination/folder/
```

### Production: Optimized copy (keeps source)
```bash
# Fast network + NFS optimization
rsync -a --stats --whole-file --no-inc-recursive /source/folder/ /destination/folder/
```

### Production: Optimized move (deletes source)
```bash
# ⚠️ Deletes source files after successful copy!
rsync -a --stats --whole-file --no-inc-recursive --remove-source-files /source/folder/ /destination/folder/
```

### With progress monitoring
```bash
# Add --progress to see per-file transfer speed
rsync -a --stats --whole-file --no-inc-recursive --progress /source/folder/ /destination/folder/
```

### Why these flags?
- `--whole-file` - Your fast internal network (10Gb?) makes delta algorithm unnecessary
- `--no-inc-recursive` - Reduces seeks on NFS, builds full file list upfront
- **NO `--checksum`** - Too slow for 200TB; rsync's default (size+timestamp) is fine for one-time migration
- **NO `--verbose`** - Creates massive logs with millions of files; use `--progress` instead

### Resume interrupted transfer
```bash
# Just re-run the same command - rsync will skip existing files
rsync -av --stats /source/folder/ /destination/folder/
```

## Essential Flags

| Flag | Purpose | Use Case |
|------|---------|----------|
| `-a` | Archive mode (preserves permissions, timestamps, etc.) | **Always use** |
| `--stats` | Show transfer statistics | **Always use** - Grafana parses this |
| `--whole-file` | Skip delta algorithm (faster on fast networks) | **Recommended for your 10Gb network** |
| `--no-inc-recursive` | Build full file list first (reduces NFS seeks) | **Recommended for NFS source** |
| `--info=progress2` | Periodic progress updates (every 1-2 seconds) | **Recommended for monitoring** - log-friendly |
| `--remove-source-files` | Delete source after successful copy | Production moves only |
| `--dry-run` | Show what would happen without making changes | Testing only |
| `-h` or `--human-readable` | Human-readable sizes (KB, MB, GB) | Makes stats readable |
| `--progress` | Per-file progress with carriage returns | ⚠️ Don't use - spams logs, bad for Grafana |
| `-v` | Verbose output (prints every filename) | ⚠️ Don't use - millions of log lines |
| `-c` or `--checksum` | Compare checksums instead of size+time | ⚠️ VERY SLOW - adds days for 200TB |

## Monitoring Multiple Jobs

The Grafana dashboard is designed for monitoring parallel jobs:

**Dashboard URL**: `https://grafana.${SECRET_DOMAIN}/d/media-storage`

**What it shows**:
- Active/completed/failed job counts
- CephFS write activity (ops/sec)
- Storage growth on destination
- Final rsync statistics from logs (sent/received/speedup)

**For running jobs**:
```bash
# Watch all migration jobs
kubectl logs -n media -l app.kubernetes.io/name=~migrate -f

# Check specific job
kubectl logs -n media $MPOD -f

# Storage growth (real-time)
watch kubectl exec -n media $MPOD -- df -h | grep destination
```

**Progress monitoring**:
- Use `--info=progress2` in rsync (shows periodic updates, not per-file spam)
- **Don't use `--progress`** - creates massive log spam and doesn't help Grafana
- Watch destination storage in Grafana (updates every 15s)
- Final stats appear in Grafana when job completes

## Typical Workflow

### 1. Test with small folder
```bash
# Exec in
kubectl exec -it -n media $MPOD -- /bin/sh

# Find small folder
du -sh /source/* | sort -h | head

# Dry-run
rsync -av --dry-run /source/test-folder/ /destination/test-folder/

# Copy (keeps source)
rsync -av --stats /source/test-folder/ /destination/test-folder/

# Verify
ls /destination/test-folder/
```

### 2. Migrate large directory
```bash
# Check size
du -sh /source/movies

# Optimized transfer
rsync -av --whole-file --stats /source/movies/ /destination/movies/

# Monitor from another terminal
kubectl logs -n media $MPOD -f | grep "bytes/sec"
```

### 3. Production move (delete source)
```bash
# Test first!
rsync -avc --remove-source-files --dry-run /source/folder/ /destination/folder/

# Run for real
rsync -avc --remove-source-files --stats /source/folder/ /destination/folder/

# Source should be empty
ls /source/folder/
rmdir /source/folder/
```

## Automated Mode

To run rsync automatically instead of interactively, edit `app/helmrelease.yaml`:

```yaml
# Comment out the sleep command:
# command:
#   - /bin/sh
# args:
#   - -c
#   - "sleep 3600"

# Uncomment the rsync command:
command:
  - rsync
args:
  - --archive
  - --verbose
  - --checksum
  - --remove-source-files
  - --stats
  - --log-file=/metrics/migration.log
  - /source/YOUR_FOLDER/
  - /destination/YOUR_FOLDER/
```

## Troubleshooting

**Pod won't start**
```bash
kubectl describe pod -n media $MPOD
kubectl get events -n media --sort-by='.lastTimestamp'
```

**Can't see files**
```bash
kubectl exec -n media $MPOD -- ls -la /source/
kubectl get pvc -n media media-tower-pvc
```

**Permission denied**
```bash
# Job runs as UID/GID 568
kubectl exec -n media $MPOD -- id
kubectl exec -n media $MPOD -- ls -ln /source/
```

**Pod exited too fast**
```bash
# The pod sleeps for 1 hour, then exits
# Check when it started:
kubectl get pod -n media $MPOD -o jsonpath='{.status.startTime}'

# If it exited, trigger a new job by redeploying
flux reconcile helmrelease -n media migrate-test-dryrun
```

## Storage Details

**NFS Sources** (both mount the full `/mnt/user/Media` directory):
- **`media-tower-pvc`** → `/tower/` - 100Ti NFS from tower.manor:/mnt/user/Media
- **`media-tower-2-pvc`** → `/tower-2/` - 100Ti NFS from tower-2.manor:/mnt/user/Media

**CephFS Destination** (mounts the full `/truenas/Media` directory):
- **`media-cephfs-pvc`** → `/destination/` - 100Ti CephFS at /truenas/Media

**Permissions**:
- Runs as UID 1000, GID 140, fsGroup 150 (matches other media apps)
- Read/write access to all mounts

## Running Multiple Jobs in Parallel

For large migrations, run multiple jobs simultaneously:

```bash
# Create multiple job variants
cd kubernetes/apps/media/

# Job 1: Movies
cp -r migrate-test/ migrate-movies/
# Edit: change name to "migrate-movies", set source/destination to /source/movies/

# Job 2: TV Shows
cp -r migrate-test/ migrate-tv/
# Edit: change name to "migrate-tv", set source/destination to /source/tv/

# Job 3: Music
cp -r migrate-test/ migrate-music/
# Edit: change name to "migrate-music", set source/destination to /source/music/

# Add all to kubernetes/apps/media/kustomization.yaml:
#   resources:
#     - ./migrate-movies/ks.yaml
#     - ./migrate-tv/ks.yaml
#     - ./migrate-music/ks.yaml

# Commit and deploy
git add .
git commit -m "feat(media): add parallel migration jobs"
git push

# Monitor all jobs in Grafana
# Dashboard shows: Active (3), Completed (0), Failed (0)
# Watch storage grow on destination PVC
# See individual job stats when they complete
```

**Recommended parallelism**: 3-5 jobs based on:
- Network bandwidth (don't saturate your 10Gb link)
- Ceph cluster capacity (watch write ops)
- NFS server load (tower.manor can handle multiple clients)

Monitor with:
- Grafana: https://grafana.${SECRET_DOMAIN}/d/media-storage
- `kubectl get jobs -n media -l app.kubernetes.io/instance=migrate`
- Ceph write ops: Should see sustained activity without errors

## Performance Tuning

See [PERFORMANCE.md](./PERFORMANCE.md) for:
- Detailed rsync optimization flags
- CephFS and NFS tuning
- Expected performance (50-100 MB/s per job)
- Monitoring with Prometheus/Grafana

## Links

- Performance Guide: [PERFORMANCE.md](./PERFORMANCE.md)
- Grafana Dashboard: `https://grafana.${SECRET_DOMAIN}/d/media-storage`
- HelmRelease: [app/helmrelease.yaml](./app/helmrelease.yaml)
