#!/bin/bash
# Sync migrate.sh into migrate-configmap.yaml
# Run this before committing changes to migrate.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Syncing scripts/migrate.sh to migrate-configmap.yaml..."

# Create the metadata header with Flux annotation
cat > ../migrate-configmap.yaml << 'EOF'
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: migrate-movies-parallel-script
  namespace: media
  annotations:
    kustomize.toolkit.fluxcd.io/substitute: disabled
EOF

# Generate full configmap and extract only the data section (from "data:" until "kind:")
kubectl create configmap migrate-movies-parallel-script \
  --from-file=migrate.sh \
  --namespace=media \
  --dry-run=client \
  -o yaml | sed -n '/^data:/,/^kind:/p' | sed '$d' >> ../migrate-configmap.yaml

echo "✓ ConfigMap synced successfully"
