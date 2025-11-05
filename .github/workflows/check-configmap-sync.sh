#!/bin/bash
# Check if migrate.sh has been updated but configmap hasn't been synced

MIGRATE_NFS_DIR="kubernetes/apps/media/migrate-nfs/app"

if git diff --cached --name-only | grep -q "$MIGRATE_NFS_DIR/scripts/migrate.sh"; then
    echo "✓ scripts/migrate.sh changed, checking if configmap is synced..."

    # Check if configmap was also staged
    if ! git diff --cached --name-only | grep -q "$MIGRATE_NFS_DIR/migrate-configmap.yaml"; then
        echo ""
        echo "❌ ERROR: scripts/migrate.sh changed but migrate-configmap.yaml not updated"
        echo ""
        echo "Run this command to sync:"
        echo "  cd $MIGRATE_NFS_DIR/scripts && ./sync-configmap.sh"
        echo ""
        exit 1
    fi

    echo "✓ Both files staged - proceeding with commit"
fi
