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
| `nodes/<role>/<hostname>.yaml` | Per-node patch: install disk/image, labels, hostname and network documents |
| `render.sh <hostname>`         | Prints the full machine config for a node                                  |
| `nodes.sh [ip\|hostname]`      | Lists nodes as `<hostname> <ip> <role> <install-image>`                    |
| `clusterconfig/talosconfig`    | Admin client config (gitignored)                                           |

The directory a node file sits in (`controlplane/` or `worker/`) is its role.

## Rendering

`render.sh` builds a node's config in layers. Later layers strategically merge into earlier ones,
and lists are appended:

1. `talosctl gen config` for the role, from the decrypted secrets bundle
2. `patches/controller/*.yaml` (control-plane nodes only)
3. `patches/global/*.yaml`
4. `nodes/<role>/<hostname>.yaml`

Role patches come before global ones so list order matches what talhelper produced. Files apply
in name order, hence the numeric prefixes. `${TALOS_VERSION}` and `${KUBERNETES_VERSION}` are
substituted from `versions.yaml`, which is how the install images pick up the Talos version.

`configContract` in `versions.yaml` is passed to `talosctl gen config --talos-version`. It stays at
`v1.13` until the patches are converted to the Talos 1.14 multi-document format; with a `v1.14`
contract the base config emits the new documents and the v1alpha1 patches conflict with them.

## Tasks

```sh
task talos:diff-node IP=10.100.0.50     # dry run: what would change on one node
task talos:diff-cluster                 # dry run against every node
task talos:apply-node IP=10.100.0.50    # shows the diff, asks, then applies
task talos:render-config IP=10.100.0.50 # print the config (contains secrets)
```

Always run a diff before applying. When the repo and the nodes agree, every node reports
`No changes.`

## Adding a node

1. Create `nodes/<role>/<hostname>.yaml` (copy a sibling and change the MACs, addresses and disk).
   `nodes.sh` finds a node by the first address on link `ethSel0`.
2. `task talos:add-node IP=<ip>` while the node is in maintenance mode.

## Schematics

Install images point at Image Factory schematics by ID. Workers and control planes share
`5cc10e6e…` (qemu-guest-agent, nfsrahead); `talos-node-gpu-1` uses `1f6caf93…` (adds the NVIDIA LTS
kernel module and container toolkit). To change extensions, POST a new schematic to
`https://factory.talos.dev/schematics` and update the ID in the node files.
