# VolSync Recovery Checklist

A generic checklist for recovering VolSync backups/restores when PVCs are stuck `Pending` or CSI reports operation locks. For the full step-by-step CSI operation-lock fix, see [VolSync CSI Operation Locks](../playbooks/volsync-csi-operation-locks.md).

## 🚨 Quick fix

If you see CSI `operation already exists` errors:

```bash
kubectl rollout restart deployment -n rook-ceph csi-rbdplugin-provisioner
```

This clears in-memory CSI operation locks; pending PVCs should start provisioning within a few minutes.

## Health checks

```bash
# PVCs not yet bound
kubectl get pvc -A | grep volsync | grep -v Bound

# Jobs not completed
kubectl get jobs -A | grep volsync | grep -v Completed

# Snapshots not ready
kubectl get volumesnapshot -A | grep volsync | grep -v "true"

# Stale VolumeAttachments (older than 1h)
kubectl get volumeattachment -o json | jq -r '.items[] | select(.metadata.creationTimestamp < (now - 3600 | strftime("%Y-%m-%dT%H:%M:%SZ"))) | .metadata.name'

# CSI operation-lock errors
kubectl logs -n rook-ceph -l app=csi-rbdplugin-provisioner --tail=100 | grep "already exists"
```

## Recovery commands

Reset a single stuck ReplicationSource (suspend → delete stuck resources → resume):

```bash
# Suspend
kubectl patch replicationsource -n <ns> <name> --type merge -p '{"spec":{"paused":true}}'

# Delete stuck resources
kubectl delete volumesnapshot -n <ns> <snapshot-name>
kubectl delete pvc -n <ns> <pvc-name>
kubectl delete job -n <ns> <job-name>

# Resume
kubectl patch replicationsource -n <ns> <name> --type merge -p '{"spec":{"paused":false}}'
```

Clear a stale VolumeAttachment (cause of multi-attach errors):

```bash
kubectl get volumeattachment | grep <pv-name>
kubectl delete volumeattachment <attachment-name>
```

## Notes

- **Destination (restore) jobs** are restore operations, not backups. They can be safely deleted if stuck and will recreate on the next restore request.
- **`-r2` destinations** typically sync daily (vs hourly for primary), so they are lower priority during recovery. Check the schedule with `kubectl get replicationsource <name>-r2 -o jsonpath='{.spec.trigger.schedule}'`.
- **Critical apps** (e.g. `vaultwarden`, `unifi`) — verify the app is healthy and an alternate backup exists before assuming recovery is complete.
- After a mass cleanup, let Flux recreate ReplicationSources rather than recreating them by hand (`flux reconcile source git flux-system`).
