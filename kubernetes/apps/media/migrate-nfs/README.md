# NFS to CephFS Migration

## redeploy

Parallel migration job with checksum verification and resume capability.

## Quick Start

```bash
# 1. Edit configuration
vi jobs/migrate-job-parallel.yaml

env:
  SOURCE: "/tower/movies"      # Change this
  DEST: "/destination/movies"    # Change this
  PARALLEL_JOBS: "4"              # 2-8 concurrent dirs

job:
  completions: 26    # 26 for A-Z split, 1 for single run
  parallelism: 1     # Must be 1 (NFS limitation)

# 2. Enable job
vi jobs/kustomization.yaml
# Uncomment: - ./migrate-job-parallel.yaml

# 3. Deploy
kubectl apply -k jobs/

# 4. Monitor in Grafana → Media Storage dashboard
```

## How It Works

**NFS Limitation:** Only 1 pod can mount NFS at a time
**Solution:** Internal parallelism via `xargs -P` in single pod

```
Single pod processes 4 directories concurrently:
├─ rsync: Avatar (2009)      ─┐
├─ rsync: Alien (1979)       ├─ Parallel
├─ rsync: Arrival (2016)     ├─ execution
└─ rsync: Ant-Man (2015)     ─┘
```

**Safety per directory:**
1. Transfer (rsync)
2. **Verify checksums** (`rsync -avnc`)
3. Set ownership/permissions
4. **Delete source ONLY after verification**
5. Mark complete (checkpoint file)

## Configuration

| PARALLEL_JOBS | CPU | Memory | Speed | Use |
|---------------|-----|--------|-------|-----|
| 2 | 1 | 1Gi | Slow | Test |
| **4** | **2** | **2Gi** | **Good** | **Default** |
| 6 | 3 | 3Gi | Fast | High bandwidth |
| 8 | 4 | 4Gi | Max | Maximum speed |

## Monitoring

**Grafana Dashboard:** Media Storage

Shows:
- Storage usage (source ↓, destination ↑)
- Job status (active/completed/failed)
- **Verification failures** (must be 0!)
- Progress by letter
- Migration logs

**Manual checks:**
```bash
# Status
kubectl get pods -n media -l job-name=migrate-job-parallel -w

# Logs for letter A
kubectl logs -n media -l batch.kubernetes.io/job-completion-index=0 -f

# Verify parallelism
kubectl exec -n media <pod> -- ps aux | grep rsync
# Should see PARALLEL_JOBS processes
```

## Alerting

**Prometheus (auto-deployed):**
- Job failed
- Job running >48h
- Storage low
- No active pods

**Grafana (set up in UI):**

**Critical - Verification Failure:**
```logql
count_over_time({namespace="media", app_kubernetes_io_name=~"migrate.*"}
  |= "Verification FAILED" [5m]) > 0
```

**Warning - Job Stuck (30min no progress):**
```logql
absent_over_time(
  count_over_time({namespace="media", app_kubernetes_io_name=~"migrate.*"}
    |= "Processing:" [5m])[30m]
)
```

Create in: Grafana → Alerting → Alert rules

## Troubleshooting

**Verification failed:**
```bash
# Find which directory
kubectl logs -n media <pod> | grep "Verification FAILED"

# Manually verify
kubectl exec -n media <pod> -- \
  rsync -avnc /source/<dir> /destination/<dir>

# Source NOT deleted - safe to fix and retry
```

**Job stuck:**
```bash
# Check if really stuck
kubectl logs -n media <pod> --tail=50

# Restart pod (checkpoint ensures resume)
kubectl delete pod -n media <pod>
```

## Performance

80TB with PARALLEL_JOBS=4:
- 26 letters × ~3TB/letter
- 4 workers × 500MB/s = ~2GB/s
- **~11 hours total**

With PARALLEL_JOBS=8: **~5.5 hours**

## Files

```
migrate-nfs/
├── app/
│   ├── pvc.yaml               # Shared metrics (checkpoints/logs)
│   └── prometheusrule.yaml    # Prometheus alerts
├── jobs/
│   ├── migrate-job-parallel.yaml  # Main job (edit this)
│   ├── README.md                  # Quick reference
│   └── kustomization.yaml
└── scripts/
    └── migrate-configmap.yaml     # Migration script
```

## Safety Features

- ✅ Checksum verification before deletion
- ✅ Checkpoint resume (survives restarts)
- ✅ Shared PVC for state
- ✅ Source never deleted on failure
- ✅ Per-directory error isolation
