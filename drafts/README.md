# Drafts

Manifests that are **not applied**. Flux only reconciles `kubernetes/`, so nothing in this directory reaches the cluster. They're kept here so they're versioned and reviewable until the work they belong to is ready.

- `roundtable-fleet-restore/`: the personal Round Table fleet converted to the current CRDs, with personas (knights) and their repeatable jobs as Chains, including the jobs migrated from kagent. Plan and status: roundtable-k8s/roundtable#369 (restore) and #214 (retire kagent). Each knight carries commented-out isolation settings (gVisor `runtimeClassName`, egress allowlist) that become live when the matching CRD fields land. Read `roundtable-fleet-restore/README.md` before applying anything.
