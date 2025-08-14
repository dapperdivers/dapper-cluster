# Pattern Violation Fix Tasks - Next Steps

This document contains the remaining tasks to fix pattern violations in the dapper-cluster repository.

## ✅ **Completed Tasks**

### Task 1: Fix helm-release.yaml Naming Violations ✅
- [x] Renamed `/kubernetes/apps/observability/peanut/app/helm-release.yaml` → `helmrelease.yaml`
- [x] Updated `/kubernetes/apps/observability/peanut/app/kustomization.yaml` reference
- [x] Renamed `/kubernetes/apps/observability/exporters/dcgm-exporter/app/helm-release.yaml` → `helmrelease.yaml`
- [x] Updated `/kubernetes/apps/observability/exporters/dcgm-exporter/app/kustomization.yaml` reference
- [x] Renamed `/kubernetes/apps/kube-system/nut-upsd/app/helm-release.yaml` → `helmrelease.yaml`
- [x] Updated `/kubernetes/apps/kube-system/nut-upsd/app/kustomization.yaml` reference
- [x] Renamed `/kubernetes/apps/kube-system/node-feature-discovery/app/helm-release.yaml` → `helmrelease.yaml`
- [x] Updated `/kubernetes/apps/kube-system/node-feature-discovery/app/kustomization.yaml` reference

### Task 2: Fix Directory Naming Violations ✅
- [x] Renamed `/kubernetes/apps/kube-system/gpu_plugins/` → `gpu-plugins`
- [x] Updated `/kubernetes/apps/kube-system/kustomization.yaml` references
- [x] Updated `/kubernetes/apps/kube-system/gpu-plugins/nvidia-device-plugin/ks.yaml` path
- [x] Updated `/kubernetes/apps/kube-system/gpu-plugins/intel-device-plugin/ks.yaml` paths (both app and gpu)

### Task 3: Clean Up Empty Directories ✅
- [x] Removed `/kubernetes/apps/storage/csi-driver-iscsi/` (empty directory)
- [x] Removed `/kubernetes/apps/media/nzbget/app/resources/` (empty directory)

---

## 🚀 **Remaining Tasks to Complete**

### Task 4: Add Timeout Fields to HelmRelease Configurations
**Priority: High** - Missing timeouts can cause operational issues

#### Complex applications (add `timeout: 15m`):
- [ ] `/kubernetes/apps/observability/kube-prometheus-stack/app/helmrelease.yaml`
- [ ] `/kubernetes/apps/observability/grafana/app/helmrelease.yaml`
- [ ] `/kubernetes/apps/observability/loki/app/helmrelease.yaml`
- [ ] `/kubernetes/apps/cert-manager/cert-manager/app/helmrelease.yaml`
- [ ] `/kubernetes/apps/kube-system/cilium/app/helmrelease.yaml`
- [ ] `/kubernetes/apps/flux-system/flux-operator/app/helmrelease.yaml`
- [ ] `/kubernetes/apps/flux-system/flux-operator/instance/helmrelease.yaml`

#### Standard applications (add `timeout: 5m`):
- [ ] All remaining ~85+ HelmRelease files missing timeout field
- [ ] Consider creating a script to batch add timeout fields

**Implementation approach:**
```yaml
spec:
  interval: 30m
  retryInterval: 1m
  timeout: 5m  # or 15m for complex apps
```

### Task 5: Standardize Schema References
**Priority: Medium**

#### Files using bjw-s-labs (change to bjw-s):
- [ ] `/kubernetes/apps/system-upgrade/system-upgrade-controller/app/helmrelease.yaml`
- [ ] Search for other files using `bjw-s-labs` and standardize to `bjw-s`

**Change from:**
```yaml
schema: https://raw.githubusercontent.com/bjw-s-labs/helm-charts/main/charts/other/app-template/schemas/helmrelease-helm-v2.schema.json
```

**Change to:**
```yaml
schema: https://raw.githubusercontent.com/bjw-s/helm-charts/main/charts/other/app-template/schemas/helmrelease-helm-v2.schema.json
```

### Task 6: Network Namespace Structure Decision
**Priority: Medium** - Requires architectural decision

#### Current structure:
```
network/
├── external/
│   ├── cloudflared/
│   ├── external-dns/
│   └── ingress-nginx/
├── internal/
│   ├── home-reverse-proxy/
│   ├── ingress-nginx/
│   └── k8s-gateway/
├── multus/
└── smtp-relay/
```

#### Decision Options:

**Option A: Restructure to standard pattern**
- [ ] Move `network/external/cloudflared` → `network/cloudflared`
- [ ] Move `network/external/external-dns` → `network/external-dns`
- [ ] Move `network/external/ingress-nginx` → `network/ingress-nginx-external`
- [ ] Move `network/internal/ingress-nginx` → `network/ingress-nginx-internal`
- [ ] Move `network/internal/k8s-gateway` → `network/k8s-gateway`
- [ ] Move `network/internal/home-reverse-proxy` → `network/home-reverse-proxy`
- [ ] Update all kustomization.yaml files with new paths
- [ ] Update `/kubernetes/apps/network/kustomization.yaml`
- [ ] Update any cross-references in ks.yaml files

**Option B: Document as accepted deviation**
- [ ] Update `systemPatterns.md` to document network namespace as exception
- [ ] Add rationale for external/internal organization

### Task 7: Security Review
**Priority: High** - Security implications

#### Privileged containers to review:
- [ ] `/kubernetes/apps/observability/exporters/dcgm-exporter/app/helmrelease.yaml`
  - Currently has: `privileged: true`, `allowPrivilegeEscalation: true`, `SYS_ADMIN` capability
  - Action: Verify if necessary for NVIDIA GPU monitoring, document justification
- [ ] Search for other containers with excessive privileges:
  ```bash
  find kubernetes/ -name "*.yaml" -exec grep -l "privileged.*true\|SYS_ADMIN\|allowPrivilegeEscalation.*true" {} \;
  ```
- [ ] Review security contexts across all applications
- [ ] Document security exceptions in systemPatterns.md

### Task 8: Additional Consistency Improvements
**Priority: Low** - Nice to have

#### Chart reference patterns:
- [ ] Decide on standard: `chartRef` with `OCIRepository` vs `chart.spec` with explicit versions
- [ ] Current mix:
  - `chartRef` pattern: Used by bjw-s app-template charts
  - `chart.spec` pattern: Used by traditional Helm repositories
- [ ] Standardize all HelmRelease files to chosen pattern

#### Missing resources review:
- [ ] Review applications using `existingClaim` for PVCs
- [ ] Ensure all necessary PVC definitions exist or are managed appropriately
- [ ] Examples to check:
  - `plex`, `home-assistant`, `overseerr`, `tautulli`, `posterizarr`, `gatus`

---

## 📋 **Implementation Scripts**

### Script to add timeouts to HelmRelease files:
```bash
#!/bin/bash
# Add timeout field to HelmRelease files missing it

find kubernetes/ -name "helmrelease.yaml" -exec grep -L "timeout:" {} \; | while read file; do
  echo "Processing $file"
  # Insert timeout after retryInterval if it exists, otherwise after interval
  if grep -q "retryInterval:" "$file"; then
    sed -i '/retryInterval:/a\  timeout: 5m' "$file"
  elif grep -q "interval:" "$file"; then
    sed -i '/interval:/a\  timeout: 5m' "$file"
  fi
done
```

### Script to find schema inconsistencies:
```bash
#!/bin/bash
# Find bjw-s-labs references
grep -r "bjw-s-labs" kubernetes/ --include="*.yaml"
```

---

## 📊 **Progress Tracking**

- ✅ **Task 1**: Helm release naming (4/4 files fixed)
- ✅ **Task 2**: Directory naming (1/1 directory fixed)  
- ✅ **Task 3**: Empty directories (2/2 directories cleaned)
- ⏳ **Task 4**: Timeout fields (0/~90 files)
- ⏳ **Task 5**: Schema references (0/~10 files) 
- ⏳ **Task 6**: Network structure (decision pending)
- ⏳ **Task 7**: Security review (0/1+ containers)
- ⏳ **Task 8**: Additional improvements (ongoing)

**Next recommended task**: Task 4 (timeout fields) - highest operational impact