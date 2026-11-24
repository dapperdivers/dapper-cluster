# Talos

Machine configuration for the Talos nodes, built from plain `talosctl` and layered patches. No
generator tool: talhelper was archived upstream in August 2026 and never supported Talos 1.14
(#4781).

Nothing here is applied automatically. Configs are rendered on demand and streamed into `talosctl`;
the rendered output contains cluster secrets and is never written to disk by the tasks.

## Layout

| Path                           | Purpose                                                                    |
| ------------------------------ | -------------------------------------------------------------------------- |
| `versions.yaml`                | Talos / Kubernetes versions (Renovate-tracked) and the config contract     |
| `talsecret.sops.yaml`          | `talosctl gen secrets` bundle, SOPS-encrypted                              |
| `patches/controller/*.yaml`    | Control-plane-only patches                                                 |
| `patches/global/*.yaml`        | Patches for every node                                                     |
| `nodes/<role>/<hostname>.yaml` | Per-node patch: install image/disk, labels, hostname and network documents |
| `render.sh <hostname>`         | Prints the full machine config for a node                                  |
| `nodes.sh [ip\|hostname]`      | Lists nodes as `<hostname> <ip> <role> <install-image>`                    |
| `diff.sh <hostname>`           | Dry run against the node; prints a summary of the change without values    |
| `clusterconfig/talosconfig`    | Admin client config (gitignored)                                           |

The directory a node file sits in (`controlplane/` or `worker/`) is its role.

## Rendering

`render.sh` builds a node's config in layers. Later layers strategically merge into earlier ones,
and lists are appended:

1. `talosctl gen config` for the role, from the decrypted secrets bundle
2. `patches/controller/*.yaml` (control-plane nodes only)
3. `patches/global/*.yaml`
4. `nodes/<role>/<hostname>.yaml`

Files apply in name order, hence the numeric prefixes. `${TALOS_VERSION}` and
`${KUBERNETES_VERSION}` are substituted from `versions.yaml`, which is how the install images pick
up the Talos version.

Patches are Talos 1.14 configuration documents (`kind: KubeAPIServerConfig`, `KubeletConfig`,
`ResolverConfig`, `UnattendedInstallConfig`, …). A patch document merges into the base document of
the same kind (and `name`, where the kind has one): maps merge, lists append, and
`$patch: delete` removes the base document. Only what has no document yet stays in the v1alpha1
`machine:` / `cluster:` form: etcd settings, `machine.certSANs`, and the containerd customization in
`patches/global/20-machine-files.yaml` (see the comment there).

Every secret (CAs, tokens, the service-account signing key, the etcd encryption key) comes from the
secrets bundle through the generated base. Patches never hold secret material.

## Config contract

`configContract` in `versions.yaml` is passed to `talosctl gen config --talos-version`. It decides
which documents the generated base contains **and their defaults**, so raising it is a migration,
not a version bump: diff the new base against the old one first.

The move from `v1.13` to `v1.14` (November 2026) was done without changing node behaviour. Three
things hold the old behaviour in place and are worth knowing about:

- `patches/global/70-pinned-defaults.yaml` removes the documents a v1.14 base adds that the cluster
  never ran with: workload isolation, the secure `/var` mount and the weekly filesystem trim.
- `patches/controller/00-apiserver.yaml` sets `startupProbes: false`, and
  `30-apiserver-oidc.yaml` sets `anonymous.enabled: false`. The v1.14 defaults are probes on and
  anonymous access to the health paths. Change the two together or not at all: the probes are
  anonymous requests, so probes on with anonymous off gets the apiserver killed.
- `render.sh` appends the `identity` provider to `KubeEtcdEncryptionConfig`, which is what Talos
  generated before v1.14.

To rotate the service-account key again, add a `KubeServiceAccountConfig` patch with
`accepted.publicKeys`; the signing key itself stays in the bundle.

## Tasks

```sh
task talos:diff-node IP=10.100.0.50     # dry run: summary of what would change on one node
task talos:diff-cluster                 # the same for every node
task talos:apply-node IP=10.100.0.50    # shows the summary, asks, then applies
task talos:render-config IP=10.100.0.50 # print the config (contains secrets)
```

Always run a diff before applying. When the repo and the nodes agree, every node reports
`no changes`.

The diff tasks print a summary only: whether a reboot is needed, how many lines change, and which
keys and documents are added or removed. Values are never shown, because a machine config diff
contains CA keys and tokens. That makes the tasks safe in CI logs and agent sessions.
`task talos:diff-node IP=… FULL=true` prints talosctl's raw diff for when you need to see the
values yourself.

## Adding a node

1. Create `nodes/<role>/<hostname>.yaml` (copy a sibling and change the MACs, addresses and disk).
   `nodes.sh` finds a node by the first address on link `ethSel0` and reads its install image
   from the `UnattendedInstallConfig` document.
2. `task talos:add-node IP=<ip>` while the node is in maintenance mode.

## Schematics

Install images point at Image Factory schematics by ID. Workers and control planes share
`5cc10e6e…` (qemu-guest-agent, nfsrahead); `talos-node-gpu-1` uses `1f6caf93…` (adds the NVIDIA LTS
kernel module and container toolkit). gVisor nodes (label `workload.cluster.io/agent-sandbox`) use
`36c18967…` (adds `siderolabs/gvisor` for the `gvisor` RuntimeClass, roundtable-k8s/roundtable#212). To change extensions, POST a new schematic to
`https://factory.talos.dev/schematics` and update the ID in the node files.
