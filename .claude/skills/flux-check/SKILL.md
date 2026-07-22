---
name: flux-check
description: Troubleshoot Flux CD on the dapper-cluster — a Kustomization or HelmRelease not Ready, changes merged but not applying, dependency/substitution errors, a stuck or wedged release. Use when "flux get all" shows False, a deploy didn't land, or reconciliation errors appear. For pod-level symptoms use debug-k8s instead.
allowed-tools: Read, Edit, Bash, Grep, Glob
---

# FluxCD Troubleshooting

Diagnose and resolve Flux CD reconciliation and deployment issues on the dapper-cluster.

## Instructions

### 1. Assess Current State

Check Flux component status and recent events:

```bash
KUBECONFIG=~/projects/dapper-cluster/kubeconfig flux get all -A | grep -v "Applied\|True"
KUBECONFIG=~/projects/dapper-cluster/kubeconfig flux events --watch=false | tail -30
```

### 2. Identify Failing Resources

Focus on resources that aren't reconciling:

```bash
# Failed Kustomizations
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl get kustomizations.kustomize.toolkit.fluxcd.io -A -o wide | grep -v "True"

# Failed HelmReleases
KUBECONFIG=~/projects/dapper-cluster/kubeconfig kubectl get helmreleases -A -o wide | grep -v "True"

# Source issues
KUBECONFIG=~/projects/dapper-cluster/kubeconfig flux get sources all -A | grep -v "True"
```

### 3. Diagnose Root Causes

For each failing resource:

- Check the resource's status conditions for error messages
- Review controller logs: `flux logs --tail=50 --kind=kustomization --name=<name>`
- Common causes: YAML syntax errors, dependency ordering, authentication failures, resource conflicts

### 4. Cross-Reference with Git

Check the app's manifests for issues:

- ks.yaml at `kubernetes/apps/<namespace>/<app>/ks.yaml`
- HelmRelease at `kubernetes/apps/<namespace>/<app>/app/helmrelease.yaml`
- Namespace kustomization at `kubernetes/apps/<namespace>/kustomization.yaml`

All namespace kustomizations must include `components: [../../flux/components/common]` which provides:

- OCI repos (app-template from bjw-s-labs)
- SOPS decryption
- Cluster substitutions (`${SECRET_DOMAIN}`, `${TIME_ZONE}`, etc.)
- Flux alerts

### 5. Implement Solutions

Apply targeted fixes by editing the relevant YAML files.

### 6. Verify Resolution

```bash
# Quickest: the repo task pulls Git + reconciles flux-system (sets KUBECONFIG for you)
task reconcile

# Reconcile a specific Kustomization
KUBECONFIG=~/projects/dapper-cluster/kubeconfig flux reconcile kustomization <name> -n flux-system
```

For a HelmRelease stuck in a bad state, `task kubernetes:restart-helmrelease HR=<name> NS=<ns>`
uninstalls and reconciles it cleanly.

## Key Reminders

- sourceRef in ks.yaml is `name: flux-system, namespace: flux-system`
- `prune: false` is intentional on: cilium, coredns, flux-operator
- `healthChecks` are intentional on: goldilocks, system-upgrade-controller
- `substituteFrom` is intentional on: system-upgrade-controller-plans, vllm, wazuh, litellm, ollama
- `retries: -1` is intentional on: system-upgrade-controller, barman-cloud
- ks.yaml field order: `targetNamespace -> components -> commonMetadata -> dependsOn -> path -> prune -> sourceRef -> wait -> interval -> retryInterval -> timeout -> postBuild`

## Report

Provide:

- **Status**: What's failing and what's healthy
- **Root Cause**: Why it's failing
- **Fix Applied**: What was changed
- **Verification**: Confirmation it's resolved
