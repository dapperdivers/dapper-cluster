# Monitoring Stack Gap Analysis - October 17, 2025

## Executive Summary
Comprehensive review of Grafana, Prometheus, and Loki monitoring stack revealed the core components are **functional** with 97.6% operational status. Critical issues identified require both Kubernetes configuration changes and external Ceph infrastructure remediation.

---

## Component Status

### ✅ Grafana (Healthy)
- **Status**: Running (2/2 containers)
- **Memory**: 441Mi
- **URL**: grafana.chelonianlabs.com
- **Datasources**: Properly configured
  - Prometheus: `http://prometheus-operated.observability.svc.cluster.local:9090`
  - Loki: `http://loki-headless.observability.svc.cluster.local:3100`
  - Alertmanager: `http://alertmanager-operated.observability.svc.cluster.local:9093`
- **Dashboards**: 35+ configured and loading
- **Issues**: None

### ✅ Prometheus (Healthy with Minor Issues)
- **Status**: Running HA mode (2 replicas)
- **Memory**: 2.1GB per pod
- **Scrape Success**: 161/165 targets healthy (97.6%)
- **Storage**: 5.8GB/100GB used (6%)
- **Retention**: 14 days
- **Monitoring Coverage**:
  - 38 ServiceMonitors
  - 7 PodMonitors
  - 44 PrometheusRules
- **Issues**:
  - 4 targets down (2.4% failure rate)
  - Duplicate timestamp warnings from kube-state-metrics

### ⚠️ Loki (Functional but Dropping Logs)
- **Status**: Running (2/2 containers)
- **Memory**: 340Mi
- **Storage**: 1.6GB/30GB used (5%)
- **Retention**: 14 days
- **Log Collection**: Successfully collecting from 17 namespaces
- **Issues**:
  - **CRITICAL**: Max entry size limit (256KB) exceeded
  - Plex logs (553KB entries) being rejected
  - Error: `Max entry size '262144' bytes exceeded`

### ✅ Promtail (Healthy)
- **Status**: DaemonSet running on all 11 nodes
- **Memory**: 70-140Mi per pod
- **Target**: `http://loki-headless.observability.svc.cluster.local:3100/loki/api/v1/push`
- **Issues**: None (successfully shipping logs despite Loki rejections)

### ⚠️ Alertmanager (Healthy but Active Alerts)
- **Status**: Running (2/2 containers)
- **Memory**: 37Mi
- **Active Alerts**: 19 alerts firing
- **Issues**: See Active Alerts section below

---

## Critical Issues

### 1. Loki Log Entry Size Limit
**Severity**: High
**Impact**: Logs from high-volume applications being dropped

**Details**:
- Default max entry size: 262,144 bytes (256KB)
- Plex application producing 553KB log entries
- Logs silently dropped without alerting

**Fix Applied**:
- ✅ Updated `/kubernetes/apps/observability/loki/app/helmrelease.yaml`
- Added `limits_config.max_line_size: 1048576` (1MB)
- **Action Required**: Commit and push to trigger Flux reconciliation

**Verification**:
```bash
# After deployment, verify no more errors:
kubectl logs -n observability -l app.kubernetes.io/name=promtail --tail=100 | grep "exceeded"
```

---

### 2. External Ceph Cluster Health Warnings
**Severity**: High
**Impact**: PVC provisioning failures, pod scheduling blocked

**Details**:
External Ceph cluster (running on Proxmox hosts) showing `HEALTH_WARN`:

1. **PG_AVAILABILITY** (Critical):
   - 128 placement groups inactive
   - 128 placement groups incomplete
   - **This is blocking new PVC creation**

2. **MDS_SLOW_METADATA_IO**:
   - 1 MDS (metadata server) reporting slow I/O
   - Impacts CephFS performance

3. **MDS_TRIM**:
   - 1 MDS behind on trimming
   - Can impact metadata operations

**Ceph Cluster Info**:
- FSID: `782dd297-215e-4c35-b7cf-659c20e6909e`
- Version: 18.2.7-0 (Reef)
- Monitors: proxmox-02 (10.150.0.2), proxmox-03 (10.150.0.3), Proxmox-04 (10.150.0.4)
- Capacity: 195TB available / 244TB total (80% used)

**Action Required**:
These are **infrastructure-level issues** that must be resolved on the Proxmox/Ceph cluster directly:

```bash
# SSH to Proxmox host and run:
ceph health detail
ceph pg dump | grep -E "inactive|incomplete"
ceph osd tree
ceph fs status cephfs

# Likely fixes (depending on root cause):
# - Check OSD status and bring up any down OSDs
# - Verify network connectivity between OSDs
# - Check disk space on OSD nodes
# - Review Ceph logs for specific PG issues
```

**Kubernetes Impact**:
- ❌ Gatus pod stuck in Pending (PVC provisioning failure)
- ❌ VolSync destination pods failing
- ❌ Any new workloads requiring CephFS storage blocked

---

## Prometheus Scrape Target Failures

**Down Targets** (4 total):

1. **athena.manor:9221** - Unnamed exporter (likely SNMP)
2. **circe.manor:9221** - Unnamed exporter (likely SNMP)
3. **nut-upsd.kube-system.svc.cluster.local:3493** - NUT UPS exporter
4. **zigbee-controller-garage.manor** - Zigbee controller

**Analysis**: All down targets are edge devices or external services. Core Kubernetes monitoring intact.

**Recommended Actions**:
- Verify network connectivity to .manor hostnames
- Check if SNMP exporters are running
- Investigate NUT UPS service in kube-system namespace
- Verify zigbee-controller service status

---

## Active Alerts (19 Total)

### High Priority:
1. **TargetDown** - Related to 4 targets listed above
2. **KubePodNotReady** - Related to Ceph PVC provisioning issues (gatus, volsync)
3. **KubeDeploymentRolloutStuck** - Likely gatus deployment
4. **KubePersistentVolumeFillingUp** - Check which PVs

### Medium Priority:
5. **CPUThrottlingHigh** - Investigate which pods/namespaces
6. **KubeJobFailed** - 2 failed jobs identified:
   - `kometa-29344680` (media namespace)
   - `plex-off-deck-29344620` (media namespace)
7. **VolSyncVolumeOutOfSync** - Expected with current Ceph issues

### Informational:
8. **Watchdog** - Always firing (heartbeat)
9. **PrometheusDuplicateTimestamps** - kube-state-metrics timing issue (low impact)

---

## Recommendations

### Immediate Actions (Required before further work):
1. ✅ **Loki configuration updated** - Ready for commit
2. ⚠️ **Fix Ceph PG issues** - Must be done on Proxmox hosts
3. ⚠️ **Verify Ceph health** - Run `ceph health detail` on Proxmox

### Post-Ceph Fix:
4. Delete stuck pods to retry provisioning:
   ```bash
   kubectl delete pod -n observability gatus-6fcfb64bc8-zz996
   kubectl delete pod -n observability volsync-dst-gatus-dst-8wvtx
   ```

5. Investigate and fix down Prometheus targets:
   - Check SNMP exporter configurations
   - Verify NUT UPS service
   - Test network connectivity to .manor devices

6. Review CPU throttling alerts:
   ```bash
   kubectl top pods -A --sort-by=cpu
   # Adjust resource limits as needed
   ```

7. Clean up failed CronJobs in media namespace

### Long-term Improvements:
- Add Loki ingestion metrics dashboard
- Configure log sampling/filtering for high-volume apps
- Set up PVC capacity monitoring alerts
- Review and tune Prometheus scrape intervals
- Consider adding CephFS-specific dashboards

---

## Verification Checklist

After applying fixes:

- [ ] Loki accepting large log entries (check Promtail logs)
- [ ] No "exceeded" errors in Promtail logs
- [ ] Ceph cluster shows `HEALTH_OK`
- [ ] Gatus pod Running (2/2)
- [ ] All PVCs Bound
- [ ] Prometheus targets down count <= 2 (excluding optional edge devices)
- [ ] Active alerts reduced to baseline (~5-10 expected)
- [ ] All core namespace pods Running

---

## Infrastructure Context

### Deployment Method:
- **GitOps**: FluxCD
- **Workflow**: Edit repo → User commits → User pushes → Flux reconciles

### Storage:
- **Provider**: External Ceph cluster (Proxmox)
- **Storage Classes**: cephfs-shared (default), cephfs-static
- **Provisioner**: rook-ceph.cephfs.csi.ceph.com

### Monitoring Namespace:
- **Namespace**: observability
- **Components**: Grafana, Prometheus (HA), Loki, Promtail, Alertmanager
- **Additional**: VPA, Goldilocks, Gatus, Kromgo, various exporters

---

## Next Steps

1. **User Action**: Review and commit Loki configuration changes
2. **User Action**: Fix Ceph PG availability issues on Proxmox
3. **After Ceph Fix**: Proceed with pod cleanup and target investigations
4. **Monitor**: Watch for new alerts or recurring issues

---

**Generated**: 2025-10-17
**Analysis Duration**: ~30 minutes
**Status**: Awaiting user commit and Ceph infrastructure remediation
