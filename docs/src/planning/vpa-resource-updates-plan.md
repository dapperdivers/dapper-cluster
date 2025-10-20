# VPA-Based Resource Limit Updates

## Summary
This document outlines a plan to systematically update resource limits across the cluster based on VPA (Vertical Pod Autoscaler) recommendations from Goldilocks to eliminate CPU throttling alerts.

## Changes Already Made

### 1. Alert Configuration
**File**: `kubernetes/apps/observability/kube-prometheus-stack/app/alertmanagerconfig.yaml`
- Changed default receiver from `pushover` to `"null"`
- Added explicit routes for `severity: warning` and `severity: critical` to pushover
- **Result**: Only critical and warning alerts will trigger pushover notifications (no more info-level spam)

### 2. Promtail Resources
**File**: `kubernetes/apps/observability/promtail/app/helmrelease.yaml`
- CPU Request: 50m → 100m
- CPU Limit: 100m → 250m
- **Rationale**: VPA recommends 101m upper bound, but we added headroom for log bursts

## Priority Workloads for Update

### High Priority (Currently Throttling or at Risk)

#### Observability Namespace

1. **Loki** - Log aggregation
   - Current: cpu: 35m request, 200m limit
   - VPA: cpu: 23m request, 140m limit
   - **Action**: Keep current limits (already adequate)

2. **Grafana** - Visualization
   - Current: No CPU limits
   - VPA: cpu: 63m request, 213m limit
   - **Action**: Add limits - 100m request, 500m limit for burst capacity

3. **Internal Nginx Ingress** (network namespace)
   - Current: cpu: 500m request, no limit
   - VPA: cpu: 63m request, 316m limit
   - **Action**: Add 500m limit (keep generous for traffic spikes)

### Medium Priority (Good to standardize)

#### Observability Namespace

4. **kube-state-metrics**
   - VPA: cpu: 23m request, 77m limit
   - **Action**: Add resources block

5. **Goldilocks Controller**
   - VPA: cpu: 587m request, 2268m limit (!)
   - **Action**: Add generous limits for this workload

6. **Blackbox Exporter**
   - VPA: cpu: 15m request, 37m limit
   - **Action**: Add resources block

#### Network Namespace

7. **External Nginx Ingress**
   - VPA: cpu: 49m request, 165m limit
   - **Action**: Add resources block

8. **Cloudflared**
   - VPA: cpu: 15m request, 214m limit
   - **Action**: Add resources block (note the high burst)

### Low Priority (Already well-configured)

- **Node Exporter**: Current limits are generous (250m limit vs 22m VPA)
- **DCGM Exporter**: Has limits, VPA shows adequate
- **Media workloads**: Most have no CPU limits (intentional for high CPU apps like Plex, Bazarr)

## Implementation Strategy

### Phase 1: Stop the Alerts (DONE ✅)
- [x] Update alertmanagerconfig to filter by severity
- [x] Update promtail CPU limits

### Phase 2: Observability Namespace (Next)
Update these critical monitoring components:
- [ ] Grafana - Add CPU limits
- [ ] kube-state-metrics - Add resources
- [ ] Goldilocks controller - Add resources
- [ ] Blackbox exporter - Add resources

### Phase 3: Network Infrastructure
- [ ] Internal nginx ingress - Add CPU limit
- [ ] External nginx ingress - Add resources
- [ ] Cloudflared - Add resources

### Phase 4: Optional Refinements
- Review VPA recommendations quarterly
- Adjust limits based on actual usage patterns
- Consider enabling VPA auto-mode for non-critical workloads

## How to Use VPA Recommendations

### 1. View All Recommendations
```bash
# Run the helper script
./scripts/vpa-resource-recommendations.sh

# Or visit the dashboard
open https://goldilocks.chelonianlabs.com
```

### 2. Get Specific Workload Recommendations
```bash
kubectl get vpa -n observability goldilocks-grafana -o jsonpath='{.status.recommendation.containerRecommendations[0]}' | jq
```

### 3. Update HelmRelease
Add resources block under `values:`:
```yaml
values:
  resources:
    requests:
      cpu: <vpa_target>
      memory: <vpa_target_memory>
    limits:
      cpu: <vpa_upper_or_2x_for_bursts>
      memory: <vpa_upper_memory>
```

### 4. Apply and Monitor
```bash
# Commit changes
git add kubernetes/apps/observability/grafana/app/helmrelease.yaml
git commit -m "feat(grafana): add CPU limits based on VPA recommendations"
git push

# Force reconciliation (optional)
flux reconcile helmrelease -n observability grafana

# Monitor for throttling
kubectl top pods -n observability --containers
```

## VPA Interpretation Guide

**VPA Recommendation Fields:**
- `target`: Use as your request value
- `lowerBound`: Minimum to function
- `upperBound`: Use as limit (or higher for burst workloads)
- `uncappedTarget`: What VPA thinks is ideal without constraints

**When to Deviate:**
- **Burst workloads** (logs, ingress): Use 2-3x upper bound for limits
- **Background jobs**: Match VPA recommendations closely
- **User-facing apps**: Add 50-100% headroom for traffic spikes
- **Resource-constrained**: Start with target, monitor, then adjust

## Monitoring for Success

After updates, verify alerts have stopped:
```bash
# Check for CPU throttling alerts
kubectl get alerts -A | grep -i throttl

# Check actual CPU usage vs limits
kubectl top pods -A --containers | sort -k4 -h -r | head -20

# Review VPA over time
watch kubectl get vpa -n observability
```

## Tools Created

1. **`scripts/vpa-resource-recommendations.sh`** - Extract VPA recommendations with HelmRelease file locations
2. **This document** - Implementation plan and guidance

## References

- [Goldilocks Dashboard](https://goldilocks.челonianlabs.com)
- [VPA Documentation](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)
- [Kubernetes Best Practices: Resource Requests and Limits](https://cloud.google.com/blog/products/containers-kubernetes/kubernetes-best-practices-resource-requests-and-limits)
