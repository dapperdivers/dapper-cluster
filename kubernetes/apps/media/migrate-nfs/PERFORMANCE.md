# Migration Performance Optimization

## rsync Performance Flags

### Currently Used (Safe Defaults)

- `--archive` - Preserve all file attributes
- `--checksum` - Verify files using checksums (slower but ensures integrity)
- `--stats` - Show transfer statistics
- `--dry-run` - Test mode (remove for production)

### Optional Performance Improvements

Add these flags for better performance in production:

#### `--no-inc-recursive`
**What it does**: Builds complete file list before starting transfer
**When to use**: Large datasets with many small files
**Impact**: Reduces seek operations on source filesystem
**Trade-off**: Higher memory usage, longer startup time

```yaml
args:
  - --no-inc-recursive  # Build full file list upfront
```

#### `--whole-file`
**What it does**: Transfers entire files instead of using delta algorithm
**When to use**: Fast network between source and destination
**Impact**: Faster transfers when bandwidth > disk I/O
**Trade-off**: Uses more network bandwidth

```yaml
args:
  - --whole-file  # Skip delta algorithm
```

#### `--compress` / `-z`
**What it does**: Compress data during transfer
**When to use**: Slow network, fast CPUs
**Impact**: Reduces network bandwidth
**Trade-off**: Increases CPU usage

```yaml
args:
  - --compress  # Compress during transfer
```

## Storage-Specific Optimizations

### CephFS (Destination)

**Available Metrics** (from Rook-Ceph):
- `ceph_pool_wr` - Write operations/sec
- `ceph_pool_wr_bytes` - Write throughput
- `cephfs_metadata_pool_*` - Metadata operations

**Optimization**: CephFS handles small file writes well, no special flags needed.

### NFS (Source)

**Type**: Static NFS mount (no CSI driver metrics)
**Optimization**: `--no-inc-recursive` reduces NFS GETATTR calls

**Mount options** (already configured):
```yaml
- soft                    # Don't hang on NFS issues
- rsize=4194304           # 4MB read buffer
- wsize=4194304           # 4MB write buffer
```

## Recommended Production Configuration

For 200TB migration with good network:

```yaml
args:
  - --archive
  - --human-readable
  - --checksum              # Keep for safety
  - --remove-source-files
  - --stats
  - --log-file=/metrics/migration.log
  - --no-inc-recursive      # Reduce seeks
  - --whole-file            # Fast network optimization
  - /source/
  - /destination/movies/
```

## Monitoring Performance

### Grafana Dashboard

The **Media Storage** dashboard shows:
- **CephFS Write Activity**: Real-time write ops/sec
- **Migration Statistics**: rsync transfer rates from logs
- **Storage Growth**: Watch CephFS usage increase

### Metrics to Watch

1. **ceph_pool_wr** - Should see sustained writes during migration
2. **kubelet_volume_stats_used_bytes** - Source should decrease, destination increase
3. **Loki logs** - Filter for "bytes/sec" to see rsync speeds

## Performance Expectations

With current configuration:
- **Per Job**: 50-100 MB/s (depends on file sizes)
- **Concurrent Jobs**: 3-5 jobs = 200-300 MB/s aggregate
- **Large Files**: Faster (less overhead)
- **Small Files**: Slower (more metadata operations)

## Testing

### Measure Actual Performance

```bash
# Watch dashboard: https://grafana.${SECRET_DOMAIN}/d/media-storage

# Check job logs for speed
kubectl logs -n media -l app.kubernetes.io/name=migrate-nfs-dryrun | grep "bytes/sec"

# Monitor Ceph write ops
kubectl exec -n rook-ceph deploy/rook-ceph-tools -- ceph osd pool stats cephfs-data
```

### Tune Based on Results

- **Low throughput (<50 MB/s)**: Try `--whole-file`
- **High CPU usage**: Remove `--compress` if added
- **NFS slow**: Add `--no-inc-recursive`
- **Ceph slow**: Check cluster health, might be rebalancing

## File List Pre-generation (Advanced)

For maximum performance, generate file lists ahead of time:

```bash
# Generate file list
find /source -type f > /tmp/files.txt

# Use with rsync
rsync --files-from=/tmp/files.txt --archive /source/ /destination/
```

This eliminates filesystem traversal during migration but requires:
- Mounting file list into pod
- Updating job args to use `--files-from`

## References

- rsync man page: `man rsync`
- Ceph performance: [Rook Ceph Docs](https://rook.io/docs/rook/latest/)
- Dashboard: `kubernetes/apps/observability/grafana/app/dashboards/media-storage.json`
