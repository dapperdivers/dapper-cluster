---
name: debug-k8s
description: Troubleshoot Kubernetes pods, services, networking, storage, and resource issues across the dapper-cluster
tools: Bash, Read, Grep, Glob
---

# Kubernetes Debugging

Troubleshoot issues on the dapper-cluster. Takes an optional argument for the target resource (e.g., `/debug-k8s litellm` or `/debug-k8s kube-system`).

## Instructions

### 1. Scope the Problem

If a specific app/namespace was given, focus there. Otherwise start broad:

```bash
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl get pods -A | grep -Ev "Running|Completed"
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl get events -A --sort-by='.lastTimestamp' --field-selector type!=Normal | tail -20
```

### 2. Node Health

```bash
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl get nodes -o wide
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl top nodes
```

### 3. Pod Diagnostics

For failing pods:

```bash
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl describe pod <pod> -n <namespace>
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl logs <pod> -n <namespace> --tail=50
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl logs <pod> -n <namespace> --previous --tail=50
```

### 4. Service/Network Issues

```bash
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl get svc,ep -n <namespace>
```

### 5. Storage Issues

```bash
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl get pv,pvc -n <namespace>
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl describe pvc <pvc> -n <namespace>
```

### 6. Flux/GitOps Issues

If the pod issue originates from a bad deployment:

```bash
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl get hr -n <namespace> <app-name>
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl get kustomizations.kustomize.toolkit.fluxcd.io -n flux-system <app-name>
```

### 7. Cross-Reference with Git

Check the app's manifests for misconfigurations:
- `kubernetes/apps/<namespace>/<app>/ks.yaml` - Flux Kustomization
- `kubernetes/apps/<namespace>/<app>/app/helmrelease.yaml` - HelmRelease
- `kubernetes/apps/<namespace>/<app>/app/externalsecret.yaml` - Secrets

## Cluster Context

- **OS**: Talos Linux (immutable, no SSH - use `talosctl` for node-level debugging)
- **CNI**: Cilium with L2 announcements
- **Storage**: Rook-Ceph (ceph-rbd for RWO, cephfs for RWX), VolSync for backups
- **Ingress**: NGINX (internal class), Envoy Gateway
- **Databases**: CloudNative-PG (postgres), Dragonfly (redis)
- **Secrets**: External Secrets Operator with Infisical backend

## Report

Provide:
- **Issue**: What's broken
- **Root Cause**: Why
- **Evidence**: Relevant logs/events
- **Fix**: What to change (or what was changed)
