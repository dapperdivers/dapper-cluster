# YAML Standardization Utilities

This directory contains utilities for standardizing YAML files in your Kubernetes GitOps repository.

## Features

- Standardize YAML files by ordering keys according to Kubernetes conventions
- Preserve comments and document structure
- Handle multi-document YAML files
- Support for excluding certain paths
- Dry-run mode to preview changes
- Validation to ensure standardized YAML still works

## Available Commands

| Command                                      | Description                                            |
| -------------------------------------------- | ------------------------------------------------------ |
| `task yaml:standardize -- path/to/file.yaml` | Standardize a single YAML file                         |
| `task yaml:standardize-all -- [options]`     | Standardize all YAML files in the kubernetes directory |
| `task yaml:diff -- path/to/file.yaml`        | Show diff between original and standardized file       |
| `task yaml:diff-all -- [options]`            | Show diffs for all files                               |
| `task yaml:validate -- path/to/file.yaml`    | Validate a YAML file                                   |
| `task yaml:validate-all -- [options]`        | Validate all YAML files                                |
| `task yaml:verify -- path/to/file.yaml`      | Standardize a file and verify it still works           |
| `task yaml:verify-all -- [options]`          | Standardize all files and verify they still work       |
| `task yaml:install-deps`                     | Install required dependencies                          |

## Options

- `--exclude <pattern>`: Exclude files matching pattern (can be used multiple times)
- `--dry-run`: Show what would be changed without actually making changes

## Examples

```bash
# Show what would be standardized without making changes
task yaml:standardize-all -- --dry-run

# Exclude certain directories
task yaml:standardize-all -- --exclude bootstrap

# Standardize a specific file
task yaml:standardize -- kubernetes/apps/cert-manager/cert-manager/ks.yaml

# Show diff for a file
task yaml:diff -- kubernetes/apps/cert-manager/cert-manager/ks.yaml

# Verify changes won't break anything
task yaml:verify -- kubernetes/apps/cert-manager/cert-manager/ks.yaml
```

## Standardization Rules

The YAML standardizer follows these conventions:

1. Top-level Kubernetes resource keys are ordered as:
   - apiVersion
   - kind
   - metadata
   - spec
   - status

2. Metadata fields are ordered as:
   - name
   - namespace
   - labels
   - annotations

3. Special handling for common resource types:
   - HelmRelease
   - Kustomization
   - And others...

4. Any keys not explicitly ordered are sorted alphabetically

These conventions make YAML files more consistent and easier to read and compare.
