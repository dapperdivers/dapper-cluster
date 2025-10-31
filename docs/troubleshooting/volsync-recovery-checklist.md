# VolSync Recovery Checklist

**Last Updated:** 2025-10-31 03:00 UTC

## 🚨 QUICK FIX

**If seeing CSI "operation already exists" errors:**
```bash
kubectl delete pod -n rook-ceph -l app=csi-rbdplugin-provisioner
```
See [recovery doc](./2025-10-31-volsync-recovery.md#-quick-fix---tldr) for details.

---

## Status Overview

- **✅ Completed:** 73/79 VolSync PVCs Bound (92.4%)
- **⏳ In Progress:** 6 PVCs Pending
  - 2 plex PVCs (intentionally deferred)
  - 4 destination restore PVCs (currently provisioning)
- **✅ Flux Reconciliation:** All 28 deleted ReplicationSources successfully recreated
- **✅ CSI Operation Locks:** CLEARED via provisioner restart (was 30+ errors/2min)
- **⏳ Blocked Apps:** esphome, bazarr, searxng waiting for VolSync restores to complete

---

## Phase 1: Critical Infrastructure ✅ COMPLETED

### 1.1 Clear Stuck Resources
- [x] Suspend 33 ReplicationSources across 4 namespaces
- [x] Delete 33+ stuck VolumeSnapshots
- [x] Delete 33+ stuck PVCs with CSI operation locks
- [x] Delete 33+ stuck VolSync jobs
- [x] Unpause ReplicationSources to allow recreation

### 1.2 Clean Up Orphaned Resources
- [x] Delete 7 stale VolumeAttachments (13-28h old)
- [x] Fix sonarr pod stuck for 13 hours
- [x] Delete 3 stuck destination jobs (esphome, bazarr, searxng)

### 1.3 Restart CSI Provisioner (CRITICAL FIX)
- [x] Restart CSI provisioner pods to clear in-memory operation locks
- [x] Verify 0 operation lock errors after restart
- [x] Confirm pending PVCs start provisioning

### 1.4 Verify Recovery
- [x] Confirm 73/79 PVCs are Bound (92.4% recovery)
- [x] Verify snapshot controller is unblocked
- [x] Confirm CSI operation lock errors cleared

---

## Phase 2: Deferred Items ⏳ PENDING

### 2.1 Plex VolSync (User Decision Required)
**Status:** ⏳ Waiting for user approval
**Impact:** 2 pending PVCs, 2 running jobs

**Current State:**
```bash
# Pending PVCs
media/volsync-plex-src          Pending  41m
media/volsync-plex-r2-src       Pending  41m

# Running Jobs
media/volsync-src-plex          0/1      51m
media/volsync-src-plex-r2       0/1      51m
```

**Steps to Fix:**
- [ ] Suspend plex ReplicationSources
  ```bash
  kubectl patch replicationsource -n media plex --type merge -p '{"spec":{"paused":true}}'
  kubectl patch replicationsource -n media plex-r2 --type merge -p '{"spec":{"paused":true}}'
  ```

- [ ] Delete stuck resources
  ```bash
  kubectl delete volumesnapshot -n media volsync-plex-src volsync-plex-r2-src
  kubectl delete pvc -n media volsync-plex-src volsync-plex-r2-src
  kubectl delete job -n media volsync-src-plex volsync-src-plex-r2
  ```

- [ ] Unpause to recreate
  ```bash
  kubectl patch replicationsource -n media plex --type merge -p '{"spec":{"paused":false}}'
  kubectl patch replicationsource -n media plex-r2 --type merge -p '{"spec":{"paused":false}}'
  ```

- [ ] Verify PVCs provision successfully
- [ ] Wait for next scheduled sync (check ReplicationSource schedule)

---

## Phase 3: Missing ReplicationSources ✅ FLUX RECREATED

### 3.1 Previously Deleted Sources (28 ReplicationSources) - **STATUS: RECREATED**

**Update 2025-10-31 02:42 UTC:** Flux successfully reconciled and recreated all 28 ReplicationSources.
All sources now exist, waiting for scheduled sync times to run first backups.

#### Home Automation (4 apps, 8 sources)
- [x] **esphome** - ✅ ReplicationSource recreated by Flux
  - ⚠️ App PVC Pending (40m) - waiting for VolSync restore
  - ⚠️ Pod Pending (149m) - waiting for PVC
  - ⚠️ Snapshot failing: "PVC esphome is not yet bound to a PV"
  - Status: Blocked by ReplicationDestination restore

- [x] **esphome-r2** - ✅ ReplicationSource recreated

- [x] **node-red** - ✅ ReplicationSource recreated by Flux
  - ⚠️ Snapshot created but not ReadyToUse (38m old)
  - Status: Waiting for first sync

- [x] **node-red-r2** - ✅ ReplicationSource recreated

#### Media (14 apps, 14 sources)
- [x] **bazarr** - ✅ ReplicationSource recreated
  - 🔴 App Pod Pending for 28 hours
  - ⚠️ Snapshot failing: PVC not bound
  - Status: App deployment blocked

- [x] **bazarr-r2** - ✅ ReplicationSource recreated

- [x] **bazarr-uhd** - ✅ ReplicationSource recreated
  - ⚠️ Snapshot not ReadyToUse (38m old)

- [x] **bazarr-uhd-r2** - ✅ ReplicationSource recreated

- [x] **kometa** - ✅ ReplicationSource recreated
  - ⚠️ Snapshot not ReadyToUse (37m old)

- [x] **kometa-r2** - ✅ ReplicationSource recreated

- [x] **prowlarr** - ✅ ReplicationSource recreated
  - ✅ Snapshot ReadyToUse from 2h ago
  - Status: Healthy, waiting for next sync

- [x] **prowlarr-r2** - ✅ ReplicationSource recreated

- [x] **sonarr-uhd** - ✅ ReplicationSource recreated
  - ✅ Snapshot ReadyToUse from 2h ago
  - Status: Healthy, waiting for next sync

- [x] **sonarr-uhd-r2** - ✅ ReplicationSource recreated

- [x] **tautulli** - ✅ ReplicationSource recreated
  - ⚠️ Snapshot not ReadyToUse (38m old)

- [x] **tautulli-r2** - ✅ ReplicationSource recreated

- [x] **tdarr** - ✅ ReplicationSource recreated
  - ⚠️ Snapshot not ReadyToUse (37m old)

- [x] **tdarr-r2** - ✅ ReplicationSource recreated

#### Observability (1 app, 2 sources)
- [x] **gatus** - ✅ ReplicationSource recreated
  - ⚠️ Snapshot not ReadyToUse (39m old)

- [x] **gatus-r2** - ✅ ReplicationSource recreated

#### Security (1 app, 2 sources)
- [x] **vaultwarden** - ✅ ReplicationSource recreated
  - ⚠️ **CRITICAL** - App status unknown
  - ⚠️ Snapshot not ReadyToUse
  - TODO: Verify app health and alternate backups

- [x] **vaultwarden-r2** - ✅ ReplicationSource recreated

#### Selfhosted (3 apps, 6 sources)
- [x] **obsidian-couchdb** - ✅ ReplicationSource recreated
  - ⚠️ Snapshot not ReadyToUse

- [x] **obsidian-couchdb-r2** - ✅ ReplicationSource recreated

- [x] **searxng** - ✅ ReplicationSource recreated
  - ⚠️ Snapshot not ReadyToUse
  - Previous multi-attach issue resolved (VolumeAttachment deleted)

- [x] **searxng-r2** - ✅ ReplicationSource recreated

- [x] **unifi** - ✅ ReplicationSource recreated
  - ⚠️ **IMPORTANT** - App status unknown
  - ⚠️ Snapshot not ReadyToUse
  - TODO: Verify app health and manual backups

- [x] **unifi-r2** - ✅ ReplicationSource recreated

### 3.2 Verification Commands

For each app above, run:
```bash
# 1. Check if app is running
kubectl get pod -n <namespace> -l app.kubernetes.io/name=<app-name>

# 2. Check if data PVC exists
kubectl get pvc -n <namespace> <app-name>

# 3. Check if ReplicationSource exists in git
ls kubernetes/apps/<namespace>/<app-name>/

# 4. If needs recreation, check git history
git log --oneline -- kubernetes/apps/<namespace>/<app-name>/
```

---

## Phase 4: Monitor Running Jobs ⏳ IN PROGRESS

### 4.1 Currently Running Jobs (5 total)

#### Plex Backup Jobs (User decision pending)
- [ ] **media/volsync-src-plex** - Running 51m (waiting for PVC)
- [ ] **media/volsync-src-plex-r2** - Running 51m (waiting for PVC)

#### Destination (Restore) Jobs
- [ ] **home-automation/volsync-dst-esphome-dst** - Running 11m
  - Status: May be blocked by stale VolumeAttachment (already deleted)
  - Action: Monitor for completion or multi-attach errors
  - Verify: `kubectl describe pod -n home-automation -l job-name=volsync-dst-esphome-dst`

- [ ] **media/volsync-dst-bazarr-dst** - Running 11m
  - Status: May be blocked (VolumeAttachment deleted)
  - Action: Monitor for completion
  - Verify: `kubectl describe pod -n media -l job-name=volsync-dst-bazarr-dst`

- [ ] **selfhosted/volsync-dst-searxng-dst** - Running 11m
  - Status: May be blocked (VolumeAttachment deleted)
  - Action: Monitor for completion
  - Verify: `kubectl describe pod -n selfhosted -l job-name=volsync-dst-searxng-dst`

### 4.2 Next Scheduled Sync Window

Check when next backups are scheduled to run:
```bash
# Check sync schedule for recovered apps
kubectl get replicationsource -n ai ollama -o jsonpath='{.spec.trigger.schedule}'
kubectl get replicationsource -n home-automation home-assistant -o jsonpath='{.spec.trigger.schedule}'
kubectl get replicationsource -n media huntarr -o jsonpath='{.spec.trigger.schedule}'
kubectl get replicationsource -n selfhosted actual -o jsonpath='{.spec.trigger.schedule}'

# Check next sync time
kubectl get replicationsource -A -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,NEXT:.status.nextSyncTime | grep -v "<none>"
```

- [ ] Wait for next sync window (typically hourly for src, daily for r2)
- [ ] Monitor for job creation
- [ ] Verify jobs complete successfully
- [ ] Check for any new errors in CSI logs

---

## Phase 5: Validation & Monitoring 📊 TODO

### 5.1 Immediate Health Checks (Next 1 Hour)

- [ ] No new CSI operation lock errors
  ```bash
  kubectl logs -n rook-ceph -l app=csi-rbdplugin-provisioner --tail=100 | grep "already exists"
  ```

- [ ] No new multi-attach errors
  ```bash
  kubectl get events -A --sort-by='.lastTimestamp' | grep -i "multi-attach" | tail -10
  ```

- [ ] All destination jobs complete or fail clearly
  ```bash
  kubectl get jobs -A | grep volsync-dst | grep -v Completed
  ```

- [ ] Plex decision made and resolved

### 5.2 Next Sync Window Validation (2-24 Hours)

- [ ] Verify successful backup runs for recovered apps
  ```bash
  # Check completion
  kubectl get jobs -A | grep volsync-src | grep -v Completed

  # Check last sync status
  kubectl get replicationsource -n ai ollama -o jsonpath='{.status.latestMoverStatus.result}'
  ```

- [ ] No PVCs stuck in Pending
  ```bash
  kubectl get pvc -A | grep volsync | grep Pending
  ```

- [ ] No new operation lock errors
- [ ] All snapshots reach ReadyToUse state
  ```bash
  kubectl get volumesnapshot -A | grep volsync | grep -v "true"
  ```

### 5.3 Long-term Monitoring (1 Week)

- [ ] Daily verification of backup job completion rates
- [ ] Monitor for any recurring CSI errors
- [ ] Verify R2 destination syncs complete (daily schedule)
- [ ] Check Rook operator logs for unusual activity
  ```bash
  kubectl logs -n rook-ceph -l app=rook-ceph-operator --tail=100
  ```

---

## Phase 6: Documentation & Prevention 📝 TODO

### 6.1 Update Monitoring

- [ ] Add Prometheus alert for VolumeAttachments older than 1 hour
- [ ] Add alert for VolumeSnapshots stuck in non-ready state
- [ ] Add alert for VolSync job duration exceeding expected time
- [ ] Add alert for CSI "operation already exists" errors

### 6.2 Create Runbooks

- [ ] Document VolumeAttachment cleanup procedure
- [ ] Document CSI operation lock resolution
- [ ] Document VolSync recovery procedure
- [ ] Add to on-call playbook

### 6.3 Git Repository Updates

- [ ] Commit recovery documentation
- [ ] Update cluster README with lessons learned
- [ ] Document any missing ReplicationSources that need recreation
- [ ] Create template for future VolSync troubleshooting

---

## Quick Reference Commands

### Check Overall Health
```bash
# PVC status
kubectl get pvc -A | grep volsync | grep -v Bound | wc -l

# Job status
kubectl get jobs -A | grep volsync | grep -v Completed | wc -l

# Snapshot status
kubectl get volumesnapshot -A | grep volsync | grep -v "true" | wc -l

# VolumeAttachment age
kubectl get volumeattachment -o json | jq -r '.items[] | select(.metadata.creationTimestamp < (now - 3600 | strftime("%Y-%m-%dT%H:%M:%SZ"))) | .metadata.name'
```

### Recovery Commands (If Needed Again)
```bash
# Suspend ReplicationSource
kubectl patch replicationsource -n <ns> <name> --type merge -p '{"spec":{"paused":true}}'

# Delete stuck resources
kubectl delete volumesnapshot -n <ns> <snapshot-name>
kubectl delete pvc -n <ns> <pvc-name>
kubectl delete job -n <ns> <job-name>

# Unpause
kubectl patch replicationsource -n <ns> <name> --type merge -p '{"spec":{"paused":false}}'

# Delete stale VolumeAttachment
kubectl get volumeattachment | grep <pv-name>
kubectl delete volumeattachment <attachment-name>
```

---

## Notes

**Critical Items:**
- vaultwarden (password manager) - verify alternate backups exist
- unifi (network config) - verify alternate backups exist

**Destination Jobs:**
- These are restore operations, not backups
- Can be safely deleted if stuck
- Will recreate on next restore request

**R2 Destinations:**
- Typically sync daily (vs hourly for primary)
- Lower priority than primary backups
- Check schedule: `kubectl get replicationsource <name>-r2 -o jsonpath='{.spec.trigger.schedule}'`

---

**Last Status Check:** 2025-10-31 02:35 UTC
**Next Review:** After next sync window (check schedules above)
