# PRD: Kubernetes-Based Unraid to Ceph Data Migration System

## Executive Summary
Design and implement a Kubernetes-native data migration system to transfer up to 200TB of media files from Unraid NFS storage to CephFS using a move-and-verify approach. The system leverages Kubernetes Jobs with rsync for reliable, monitored transfers organized by directory structure.

**Key Architectural Decision**: Migration will use existing Kubernetes node connectivity to Ceph public network (10.150.0.0/24), leveraging the cluster's established dual-network architecture. Unraid VMs on Proxmox already have network access via the hypervisor's bridge configuration.

**Storage Strategy**: Initial migration will use the existing `cephfs-shared` storage class (replicated). When the EC 4+2 pool is created in the future, the migration jobs can be easily reconfigured to use the new pool by simply updating the PVC reference. This allows migration to proceed immediately without waiting for pool creation.

## Project Goals

### Primary Objectives
- Migrate up to 200TB of media data from Unraid NFS (tower.manor + tower-2.manor) to CephFS
- Achieve zero data loss through verify-before-delete approach
- Provide real-time monitoring and progress tracking via existing Prometheus/Grafana stack
- Enable pause/resume capabilities for maintenance windows
- Automatically clean up source NFS data after successful verification
- Decommission legacy Unraid NFS servers upon completion

### Secondary Objectives
- Create reusable migration framework for future data movements
- Establish performance baselines for large-scale transfers
- Document migration patterns for team knowledge base
- Build confidence in Ceph storage through successful migration

## Functional Requirements

### 1. Migration Orchestration
- **FR-1.1**: System SHALL use Kubernetes Jobs for migration execution (one Job per directory)
- **FR-1.2**: System SHALL organize migrations by source directory structure
- **FR-1.3**: Operator SHALL control concurrent job count manually via kubectl/Flux

### 2. Data Transfer (Move Semantics)
- **FR-2.1**: System SHALL mount Unraid NFS servers (tower.manor, tower-2.manor) read-write within containers
- **FR-2.2**: System SHALL mount destination CephFS storage via Rook CSI using `cephfs-shared` storage class
- **FR-2.3**: System SHALL be easily reconfigurable to use different storage backend (e.g., EC pool) via PVC change
- **FR-2.4**: System SHALL preserve file permissions, timestamps, and attributes during copy
- **FR-2.5**: System SHALL verify each file's integrity after transfer (checksum comparison)
- **FR-2.6**: System SHALL delete source file ONLY after successful verification
- **FR-2.7**: System SHALL use rsync as the transfer mechanism with appropriate flags
- **FR-2.8**: System SHALL handle verification failures by retaining source and logging error

### 3. Monitoring & Observability
- **FR-3.1**: System SHALL expose migration progress metrics to Prometheus
- **FR-3.2**: System SHALL log all operations with appropriate detail levels
- **FR-3.3**: System SHALL integrate with existing Grafana dashboards
- **FR-3.4**: System SHALL track: bytes transferred, files moved, files remaining, errors

### 4. Control Interface
- **FR-4.1**: System SHALL allow pausing via Kubernetes Job suspension
- **FR-4.2**: System SHALL support dry-run mode for validation (rsync --dry-run flag)

### 5. Network Strategy
- **FR-5.1**: Migration traffic SHALL leverage existing Kubernetes node dual-network configuration (VLAN 100 primary + VLAN 150 Ceph public)
- **FR-5.2**: Unraid NFS servers SHALL remain accessible via existing network (tower.manor, tower-2.manor)
- **FR-5.3**: System SHALL use standard pod networking without special network configuration
- **FR-5.4**: Ceph traffic will use established CSI driver paths over VLAN 150 (10.150.0.0/24)

## Non-Functional Requirements

### Performance
- **NFR-1.1**: System SHOULD achieve minimum 200MB/s aggregate transfer rate (not critical)
- **NFR-1.2**: Individual jobs SHOULD sustain 50-100MB/s per stream
- **NFR-1.3**: System SHALL handle files from 1KB to 100GB+ efficiently
- **NFR-1.4**: Memory usage SHALL not exceed 4GB per migration pod

### Reliability
- **NFR-2.1**: System SHALL handle network interruptions gracefully via rsync retry logic
- **NFR-2.2**: System SHALL recover from pod failures via Kubernetes Job restart
- **NFR-2.3**: System SHALL ensure source deletion ONLY after destination verification passes
- **NFR-2.4**: System SHALL maintain detailed logs for failure investigation

### Scalability
- **NFR-3.1**: System SHALL scale to handle 10+ parallel job executions
- **NFR-3.2**: System SHALL efficiently handle directories with millions of files
- **NFR-3.3**: System SHALL support horizontal scaling across Kubernetes nodes

### Security
- **NFR-4.1**: System SHALL use Kubernetes Secrets for NFS credentials
- **NFR-4.2**: System SHALL implement least-privilege access patterns
- **NFR-4.3**: System SHALL use ServiceAccounts with minimal RBAC permissions

## System Architecture

### Network Strategy

**Leverage Existing Infrastructure**: Use established Kubernetes dual-network architecture without additional configuration.

#### Current Infrastructure:
- **Ceph Public Network**: 10.150.0.0/24 (VLAN 150)
  - All Kubernetes nodes already dual-homed with this network
  - Rook CSI drivers already use this path for storage
  - 2x 10Gb bonded links per Proxmox host
  - MTU 9000 (jumbo frames enabled)

- **Ceph Cluster Network**: 10.200.0.0/24 (VLAN 200)
  - OSD-to-OSD replication only
  - 40Gb dedicated links per host
  - Not used by migration (internal Ceph only)

- **Kubernetes Primary Network**: 10.100.0.0/24 (VLAN 100)
  - Pod and service networking via Cilium CNI
  - Standard Kubernetes API access

- **Unraid Servers** (VMs on Proxmox):
  - tower.manor: 100Ti NFS at /mnt/user/Media
  - tower-2.manor: 100Ti NFS at /mnt/user/Media
  - Already accessible via standard networking

#### Why This Works:
- **No network reconfiguration needed**: Unraid VMs already accessible from K8s pods
- **Ceph connectivity established**: CSI drivers use VLAN 150 automatically
- **Standard pod networking**: No hostNetwork or special network policies required
- **Proven infrastructure**: Leverages existing 10Gb storage network paths

#### Network Flow:
```
Kubernetes Pod Network          Ceph Public Network
    (10.100.0.0/24)              (10.150.0.0/24)

    ┌─────────────┐              ┌─────────────┐
    │ Migration   │   NFS mount  │   Unraid    │
    │    Pod      │─────────────►│ (tower.*)   │
    └──────┬──────┘              └─────────────┘
           │
           │ rsync data
           │ (via CSI driver)
           │
    ┌──────▼──────────────────────────────┐
    │        Rook CSI Driver              │
    │   (uses VLAN 150 automatically)     │
    └──────┬──────────────────────────────┘
           │
           │ CephFS mount
           │ (10.150.0.0/24)
           │
    ┌──────▼──────┐
    │    Ceph     │
    │  Monitors   │
    │ 10.150.0.2  │
    │ 10.150.0.3  │
    │ 10.150.0.4  │
    └─────────────┘
```

**Key Benefits**:
- Zero configuration changes required
- Uses battle-tested network paths
- Kubernetes CSI drivers already optimized
- No risk from network changes

**Monitoring Considerations**:
- Monitor Ceph public network (VLAN 150) utilization during migration
- Watch for saturation on 2x 10Gb bonded links
- Adjust concurrent jobs if network congestion detected
- Existing Prometheus metrics cover all relevant network stats

### Component Overview
1. **Job ConfigMap** - Defines all directory migration jobs
2. **Kubernetes Jobs** - Execute rsync transfers (one Job per directory)
3. **Worker Pods** - Containers running rsync with mounted storage
4. **Monitoring Exporter** - Sidecar or init container exposing metrics
5. **Grafana Dashboards** - Visualization of progress and health

### Migration Job Flow
```
1. Create Job from ConfigMap definition
   ↓
2. Pod starts, mounts NFS (source) and CephFS (destination)
   ↓
3. Rsync copies files to destination
   ↓
4. Verify each transferred file (checksum)
   ↓
5. Delete source file only if verification succeeds
   ↓
6. Repeat for all files in directory
   ↓
7. Job completes successfully or fails with logs
   ↓
8. Metrics exported for monitoring
```

### Infrastructure Topology
```
┌──────────────────────────────────────────────┐
│         Kubernetes Cluster                   │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │   Migration Jobs (1-10 concurrent)     │ │
│  │                                        │ │
│  │  Job 1: /movies/action  → Complete     │ │
│  │  Job 2: /movies/comedy  → Running      │ │
│  │  Job 3: /tv/drama       → Pending      │ │
│  │  ...                                   │ │
│  │                                        │ │
│  │  ┌──────────┬──────────────┐          │ │
│  │  │   NFS    │   CephFS     │          │ │
│  │  │  Mount   │   Mount      │          │ │
│  │  │  (r/w)   │   (write)    │          │ │
│  │  └──────────┴──────────────┘          │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  Monitoring Stack (Existing)           │ │
│  │  - Prometheus (metrics collection)     │ │
│  │  - Grafana (visualization)             │ │
│  └────────────────────────────────────────┘ │
└──────────────┬──────────────┬───────────────┘
              │              │
     ┌────────▼─────┐    ┌─────▼──────┐
     │   Unraid   │    │   Ceph    │
     │  NFS (RW)  │    │   EC4+2   │
     │  ~165TB    │    │  ~165TB   │
     └────────────┘    └───────────┘
```

## Implementation Approach

### Phase 1: Infrastructure Setup (Week 1)
**Goal**: Prepare Kubernetes migration infrastructure

Activities:
- Create namespace for migration jobs (`data-migration`)
- Configure RBAC and ServiceAccounts
- Verify NFS accessibility from K8s pods (tower.manor, tower-2.manor)
- Create dynamic PVC using `cephfs-shared` storage class for destination
- Build rsync container image with verification scripts
- Push container image to ghcr.io/dapperdivers/
- Set up Grafana dashboard for job monitoring (add to observability namespace)
- Create PrometheusRule for migration alerts
- Test single Job execution with small directory

**Deliverables**:
- Namespace `data-migration` created
- Working Job template using HelmRelease pattern (follows existing Flux patterns)
- PVC created on `cephfs-shared` (can be easily changed to EC pool later)
- Verified connectivity (Pod → tower.manor NFS → CephFS)
- Monitoring dashboard in Grafana
- Rsync container image at ghcr.io/dapperdivers/rsync-migrator:latest
- PodMonitor configured for metrics collection

**Success Criteria**:
- Can successfully mount tower.manor NFS from pod
- Can successfully mount CephFS destination via Rook CSI (`cephfs-shared`)
- Test file transfer (1GB) completes successfully with verification
- Source file deleted after successful verification
- Metrics visible in Prometheus
- Grafana dashboard shows job progress

### Phase 2: Test Migration (Week 1)
**Goal**: Validate move-and-verify workflow with real data

Activities:
- Select 1TB test dataset (representative directory)
- Execute test migration Job
- Validate data integrity on destination
- Confirm source deletion after verification
- Tune rsync parameters for optimal performance
- Establish baseline metrics (throughput, time per GB)
- Test Job failure and retry scenarios

**Deliverables**:
- Successful test migration
- Performance baseline metrics
- Verified move-and-verify workflow
- Documented rsync parameters

**Success Criteria**:
- 100% of test data migrated successfully
- All source files deleted after verification
- No data corruption detected
- Job completes without manual intervention

### Phase 3: Job Planning (Week 1)
**Goal**: Define all migration jobs by directory

Activities:
- Inventory Unraid directory structure
- Estimate size and file count per directory
- Prioritize directories (critical content first)
- Create ConfigMap with all job definitions
- Calculate expected duration per job
- Define job execution schedule (which directories to run in parallel)

**Deliverables**:
- Complete directory inventory
- ConfigMap with all job definitions
- Migration execution plan
- Estimated timeline

### Phase 4: Bulk Migration (Weeks 2-4+)
**Goal**: Execute all migration jobs with monitoring

Activities:
- Deploy initial batch of Jobs (3-5 concurrent based on test results)
- Monitor job progress via Grafana
- Adjust concurrency based on system load and performance
- Handle any job failures (investigate, fix, retry)
- Track daily progress (GB migrated, directories remaining)
- Maintain communication with stakeholders (daily updates)

**Operations**:
- Start next batch of Jobs as previous ones complete
- Pause jobs during maintenance windows if needed
- Scale concurrent jobs up/down based on network/storage load
- Investigate and resolve any stalled jobs

**Deliverables**:
- All 165TB migrated to Ceph
- All source directories cleaned up
- Daily progress reports
- Issue log and resolutions

### Phase 5: Verification & Cutover (Week 4+)
**Goal**: Validate migration completeness and switch to Ceph

Activities:
- Verify all Jobs completed successfully
- Spot-check random files for playback/integrity
- Compare total size and file counts (source vs destination)
- Update media server configurations to point to Ceph
- Test media playback from Ceph
- Monitor for any issues post-cutover
- Document lessons learned
- Decommission tower.manor and tower-2.manor VMs

**Deliverables**:
- Migration completion report
- Updated media server configurations
- Validated Ceph as primary storage
- Post-migration documentation
- Unraid servers decommissioned

**Success Criteria**:
- All Jobs show "Complete" status
- Source directories empty (except any failed files)
- Media playback works from Ceph
- No user complaints about missing content
- Legacy Unraid servers powered down

---

### Phase 6 (Future): EC Pool Migration (Optional)
**Goal**: Migrate from replicated to erasure-coded storage for efficiency

**When**: After EC 4+2 pool creation and validation

Activities:
- Create EC 4+2 profile and pool on external Ceph cluster
- Create new StorageClass `ceph-bulk` in Kubernetes
- Create new PVC on EC pool
- Use same migration Jobs to move data from `cephfs-shared` to `ceph-bulk`
- Update application mounts to use new EC pool PVC
- Delete old replicated PVC after verification

**Benefits**:
- ~33% reduction in raw storage usage (EC 4+2 vs 3-replica)
- Same data protection level
- Significant cost savings on storage capacity

**Deliverables**:
- EC pool operational
- Data migrated to erasure-coded storage
- Old replicated PVC deleted
- ~67TB raw storage reclaimed (200TB / 3 replicas vs 200TB * 1.5 EC overhead)

## Job Definition Structure

### ConfigMap Example
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: migration-jobs
  namespace: data-migration
data:
  jobs.yaml: |
    jobs:
      - name: movies-action
        source: /mnt/unraid/movies/action
        destination: /mnt/ceph/movies/action
        priority: high
        estimatedSize: 2.5TB

      - name: movies-comedy
        source: /mnt/unraid/movies/comedy
        destination: /mnt/ceph/movies/comedy
        priority: high
        estimatedSize: 1.8TB

      - name: tv-drama
        source: /mnt/unraid/tv/drama
        destination: /mnt/ceph/tv/drama
        priority: medium
        estimatedSize: 3.2TB

      # ... more jobs ...
```

### Kubernetes Job Template
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: migrate-{{ JOB_NAME }}
  namespace: data-migration
  labels:
    app: data-migration
    job-name: {{ JOB_NAME }}
spec:
  backoffLimit: 3
  template:
    metadata:
      labels:
        app: data-migration
        job-name: {{ JOB_NAME }}
    spec:
      restartPolicy: OnFailure
      containers:
      - name: rsync-migrate
        image: your-registry/rsync-migrator:latest
        resources:
          requests:
            memory: "2Gi"
            cpu: "2"
          limits:
            memory: "4Gi"
            cpu: "4"
        env:
        - name: SOURCE_PATH
          value: "{{ SOURCE_PATH }}"
        - name: DEST_PATH
          value: "{{ DEST_PATH }}"
        - name: JOB_NAME
          value: "{{ JOB_NAME }}"
        volumeMounts:
        - name: unraid-nfs
          mountPath: /mnt/unraid
        - name: ceph-storage
          mountPath: /mnt/ceph
        command:
        - /scripts/migrate-and-verify.sh
      volumes:
      - name: unraid-nfs
        nfs:
          server: tower.manor  # Unraid NFS server hostname
          path: /mnt/user/Media
          readOnly: false  # Need write access for deletion
      - name: ceph-storage
        persistentVolumeClaim:
          claimName: media-migration-pvc  # Dynamic PVC on cephfs-shared
```

**Network Configuration Notes**:
- `nfs.server` uses existing DNS hostname (tower.manor or tower-2.manor)
- Standard pod networking - no special configuration required
- Ceph access handled automatically by Rook CSI driver via VLAN 150
- No `hostNetwork: true` needed - CSI driver manages routing

**Storage Configuration Notes**:
- PVC `media-migration-pvc` uses `cephfs-shared` storage class initially
- To migrate to EC pool later: create new PVC on `ceph-bulk`, update Job template claimName
- All Jobs are stateless - can easily point to different PVC without code changes

## Migration Script Logic

The `migrate-and-verify.sh` script in each pod:

```bash
#!/bin/bash
set -euo pipefail

SOURCE="${SOURCE_PATH}"
DEST="${DEST_PATH}"
JOB="${JOB_NAME}"

echo "Starting migration job: ${JOB}"
echo "Source: ${SOURCE}"
echo "Destination: ${DEST}"

# Create destination directory
mkdir -p "${DEST}"

# Find all files in source
find "${SOURCE}" -type f | while read -r file; do
    # Calculate relative path
    rel_path="${file#$SOURCE/}"
    dest_file="${DEST}/${rel_path}"

    # Create destination directory structure
    dest_dir=$(dirname "${dest_file}")
    mkdir -p "${dest_dir}"

    # Copy file using rsync
    if rsync -av --progress "${file}" "${dest_file}"; then

        # Verify file integrity (checksum comparison)
        src_checksum=$(sha256sum "${file}" | awk '{print $1}')
        dest_checksum=$(sha256sum "${dest_file}" | awk '{print $1}')

        if [ "${src_checksum}" == "${dest_checksum}" ]; then
            # Checksums match - safe to delete source
            rm "${file}"
            echo "✓ Migrated and verified: ${rel_path}"

            # Export metrics
            echo "migration_files_transferred_total{job=\"${JOB}\"} 1" >> /metrics/metrics.prom
        else
            echo "✗ Checksum mismatch for: ${rel_path}"
            echo "  Source:      ${src_checksum}"
            echo "  Destination: ${dest_checksum}"
            echo "migration_errors_total{job=\"${JOB}\",type=\"checksum_mismatch\"} 1" >> /metrics/metrics.prom
            # Do NOT delete source on checksum failure
        fi
    else
        echo "✗ Transfer failed for: ${rel_path}"
        echo "migration_errors_total{job=\"${JOB}\",type=\"transfer_failed\"} 1" >> /metrics/metrics.prom
        # Do NOT delete source on transfer failure
    fi
done

echo "Migration job complete: ${JOB}"
```

## Monitoring & Metrics

### Key Metrics to Track
- **Job Status**: Completed, Running, Failed, Pending
- **Transfer Progress**: GB transferred, files moved, files remaining
- **Transfer Rate**: MB/s per job, aggregate MB/s
- **Error Rate**: Failed transfers, checksum mismatches
- **Estimated Completion**: Based on current rate and remaining data
- **Resource Usage**: CPU, memory, network per job

### Grafana Dashboard Panels
1. **Migration Overview**
   - Total progress (% complete)
   - Aggregate transfer rate
   - Jobs by status (pie chart)
   - Estimated time to completion

2. **Job Details**
   - Individual job progress (table)
   - Job duration histogram
   - Success/failure rate by job

3. **Network Health**
   - Ceph public network throughput
   - Ceph public network utilization (%)
   - Migration pod bandwidth usage
   - Network saturation alerts

4. **Storage Health**
   - Ceph pool capacity
   - Ceph write IOPS
   - Unraid read performance
   - Ceph OSD latency

5. **System Health**
   - Pod resource usage (CPU/memory)
   - Error count over time
   - Job queue depth

6. **Alerts**
   - Job failed (Critical)
   - Job stalled >4 hours (Warning)
   - Checksum mismatch detected (Critical)
   - Ceph network utilization >80% (Warning)
   - Ceph pool capacity <10% free (Critical)

## Success Criteria

### Quantitative Metrics
- 100% of data successfully migrated (165TB)
- Zero data corruption (all checksums pass)
- Source directories empty after successful migration
- Average transfer rate ≥200MB/s (aspirational)

### Qualitative Metrics
- No user-reported service disruptions
- Successful media playback from Ceph
- Documentation complete and approved
- All Jobs show "Complete" status

## Risk Management

### Risk 1: Ceph Public Network Saturation
- **Impact**: High - Could affect all Ceph-dependent production workloads
- **Likelihood**: Medium - Depends on current network utilization
- **Mitigation**:
  - Monitor Ceph network utilization before and during migration
  - Reduce concurrent jobs if saturation detected
  - Schedule migrations during off-peak hours
  - Set bandwidth limits on migration pods if necessary
- **Monitoring**: Ceph network metrics, pod bandwidth usage

### Risk 2: Source Storage Failure
- **Impact**: Critical - Could lose data mid-migration
- **Likelihood**: Low - But risk increases over 165TB migration period
- **Mitigation**:
  - Priority-based migration (critical content first)
  - Regular Unraid health checks
  - Move-and-verify ensures successful transfers are safe
- **Monitoring**: Unraid SMART stats, disk health, array status

### Risk 3: Destination Pool Capacity
- **Impact**: High - Migration could stall
- **Likelihood**: Medium - 165TB is substantial
- **Mitigation**:
  - Verify adequate capacity before starting (165TB + overhead)
  - Monitor capacity throughout migration
  - Enable compression if needed
  - Plan for EC 4+2 overhead (1.5x raw capacity)
- **Monitoring**: `ceph df` statistics, pool utilization alerts

### Risk 4: Checksum Verification Failures
- **Impact**: Medium - Some files may not migrate
- **Likelihood**: Low - Usually indicates source disk issues
- **Mitigation**:
  - Investigate root cause immediately
  - Check source disk health
  - Retry transfer after fixing underlying issue
  - Keep detailed log of failed files
- **Monitoring**: Error metrics, failed file log

### Risk 5: Job Failures
- **Impact**: Low - Kubernetes will retry automatically
- **Likelihood**: Medium - Expected with long-running migrations
- **Mitigation**:
  - Backoff limit on Jobs (3 retries)
  - Investigate persistent failures
  - Manual intervention for stuck jobs
- **Monitoring**: Job status, pod restart counts, pod logs

## Dependencies

### External Dependencies
- Unraid system availability and read/write access
- Network infrastructure stability (10Gbps)
- Ceph cluster health and available capacity

### Internal Dependencies
- Kubernetes cluster resources (CPU, memory, network)
- Rook operator functionality
- Prometheus/Grafana monitoring stack
- Container registry for migration images

## Constraints

### Technical Constraints
- Maximum 10Gbps network throughput
- Ceph EC 4+2 write performance characteristics
- Kubernetes node resources
- Unraid read/write performance

### Operational Constraints
- No hard deadline (flexible timeline)
- Zero downtime requirement for user access
- Must maintain data integrity throughout
- Source deletion must be conditional on verification

## Technology Stack

- **Container Runtime**: containerd
- **Orchestration**: Kubernetes 1.28+
- **GitOps**: Flux for deployment management
- **Storage Interface**: Rook Ceph CSI (destination), NFS (source)
- **Transfer Tool**: rsync (with custom verification script)
- **Monitoring**: Prometheus + Grafana (existing)
- **Logging**: Kubernetes native (kubectl logs)
- **Deployment**: HelmReleases with ConfigMaps for scripts

### Flux Integration

Since the cluster uses Flux for GitOps:

1. **Scripts as ConfigMaps**: Migration scripts stored in Git, mounted as ConfigMaps
2. **Jobs as HelmReleases**: Job definitions managed via Helm charts in Git
3. **Progressive Deployment**: Can deploy jobs in batches via Flux
4. **Configuration Management**: All job definitions version-controlled

Example directory structure:
```
infrastructure/
├── migration/
│   ├── helmrelease.yaml        # Main HelmRelease
│   ├── scripts/
│   │   └── migrate-verify.sh   # Mounted as ConfigMap
│   ├── jobs/
│   │   └── job-definitions.yaml # ConfigMap with job list
│   └── values.yaml             # Helm values (network config, etc.)
```

## Infrastructure Configuration (ANSWERED)

This section documents the infrastructure details needed for implementation.

### 1. Network Configuration ✓
- **Ceph public network subnet**: `10.150.0.0/24` (VLAN 150)
- **Bandwidth**: 2x 10Gb bonded links per Proxmox host (20Gb aggregate)
- **Ceph cluster network**: `10.200.0.0/24` (VLAN 200, 40Gb dedicated)
- **Kubernetes primary network**: `10.100.0.0/24` (VLAN 100)
- **MTU**: 9000 (jumbo frames on storage networks)
- **Ceph Monitors**: 10.150.0.2, 10.150.0.3, 10.150.0.4
- **Network action required**: NONE - existing dual-network architecture sufficient

### 2. Unraid Configuration ✓
- **Servers**:
  - `tower.manor` - 100Ti capacity, NFS at `/mnt/user/Media`
  - `tower-2.manor` - 100Ti capacity, NFS at `/mnt/user/Media`
- **NFS version**: 4.1 (current configuration)
- **Authentication**: No special auth required (standard NFS)
- **Mount options**: Existing mount options from media PVs can be reused (soft, tcp, vers=4.1)
- **Status**: Both servers marked for decommissioning after migration

### 3. Ceph Configuration ✓
- **Storage Class (migration)**: `cephfs-shared` (replicated, default) - **USING THIS**
- **Storage Class (future)**: `ceph-bulk` (EC 4+2) - Can migrate to this later if created
- **Decision**: Use `cephfs-shared` immediately, migrate to EC pool in Phase 6 if desired
- **Current pools**: `cephfs_data`, `k8s-backups`, `rook-pvc-pool`
- **Rook CSI**: Fully operational (external cluster mode)
- **Capacity**: Must check `ceph df` on Proxmox to ensure 200TB+ available
- **Static PV pattern**: Existing at `/truenas/*` paths (can use similar pattern if needed)

### 4. Directory Structure & Planning (TO BE DETERMINED)
- **Action required**: Inventory tower.manor and tower-2.manor directory structures
- **Suggested approach**:
  ```bash
  ssh tower.manor "du -sh /mnt/user/Media/*"
  ssh tower-2.manor "du -sh /mnt/user/Media/*"
  ```
- **Prioritization**: TBD based on inventory
- **Expected structure**: `/movies`, `/tv`, `/music`, etc.

### 5. Flux/GitOps Configuration ✓
- **Git repository**: `/home/derek/projects/dapper-cluster`
- **Namespace**: `data-migration`
- **HelmRepository**: Use existing `bjw-s` app-template (OCI at ghcr.io)
- **Git branch**: `main` (standard approach)
- **Pattern**: Follow existing apps structure at `kubernetes/apps/data-migration/`
- **Components**: Use `flux/components/common` for shared resources

### 6. Monitoring & Observability ✓
- **Prometheus**: `http://prometheus-operated.observability.svc.cluster.local:9090`
- **Grafana**: In `observability` namespace, accessible via ingress
- **Alerting**: Pushover (already configured in AlertManager)
- **Dashboard provisioning**: Via HelmRelease values (gnetId or file-based)
- **Metrics pattern**: Create PodMonitor in job namespace
- **PrometheusRule**: Create in `kubernetes/apps/data-migration/app/prometheusrule.yaml`

### 7. Container Registry ✓
- **Registry**: `ghcr.io/dapperdivers/`
- **Authentication**: GitHub token (public images require no pull secrets)
- **Image naming**: `ghcr.io/dapperdivers/rsync-migrator:YYYY-MM-DD-{sha}`
- **Build**: GitHub Actions workflow in archon-images repo pattern
- **Scanning**: Trivy enabled, cosign signing recommended
- **CI/CD**: Follow existing pattern from `/home/derek/projects/archon-images/.github/workflows/`

### 8. Outstanding Questions

**Critical (must answer before starting)**:
1. ~~Should we create EC 4+2 pool first, or use `cephfs-shared` temporarily?~~ ✓ **DECIDED: Use cephfs-shared now**
2. What is actual data size on tower.manor and tower-2.manor? (run `du -sh /mnt/user/Media/*`)
3. Directory structure inventory - what are the top-level directories?
4. Which server to migrate first? (tower.manor or tower-2.manor)
5. **Verify Ceph capacity**: Run `ceph df` to confirm 200TB+ available space

**Nice to have**:
1. Desired migration schedule (business hours, off-hours, 24/7)?
2. Maximum acceptable concurrent jobs? (start with 3-5, adjust based on monitoring)
3. Desired retention of source data post-verification? (immediate delete vs 7-day grace period)
4. Future EC pool migration desired? (would save ~67TB raw storage)

---

*Version: 4.0 - Infrastructure-Aligned Revision*
*Status: Ready for Review - Requires Decision on EC Pool*
*Owner: Storage Team*
*Last Updated: 2025-01-18*

*Key Changes v4.0 (Infrastructure Alignment)*:
- **CORRECTED**: Network configuration - uses existing dual-network architecture, no changes needed
- **CORRECTED**: Ceph public network is 10.150.0.0/24 (not 10.50.0.0/24)
- **CORRECTED**: Data size is up to 200TB (not 165TB)
- **ADDED**: Phase 0 for EC 4+2 pool creation (currently doesn't exist)
- **ADDED**: Specific infrastructure details from actual cluster configuration
- **UPDATED**: Monitoring integration with existing Prometheus/Grafana stack
- **UPDATED**: Container registry to ghcr.io/dapperdivers/
- **UPDATED**: Flux GitOps structure to match existing patterns
- **CLARIFIED**: Unraid servers are tower.manor and tower-2.manor (100Ti each)
- **CLARIFIED**: Network flow - no special configuration needed

*Critical Decisions Made*:
1. ✓ **Use existing `cephfs-shared` storage class for initial migration**
2. ✓ **EC 4+2 pool migration deferred to optional Phase 6**
3. ✓ **Network strategy confirmed - use existing dual-network architecture**

*Critical Actions Required*:
1. **Check Ceph capacity**: Verify 200TB+ available with `ceph df`
2. **Inventory data**: Run `du -sh` on both tower servers to get actual sizes
3. **Approve PRD v4.0** with infrastructure corrections
4. **Begin Phase 1: Infrastructure Setup**

*Optional Future Work*:
- Phase 6: Migrate to EC 4+2 pool for ~33% storage efficiency gain
