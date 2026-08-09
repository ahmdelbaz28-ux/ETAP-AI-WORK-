#!/bin/bash
# =============================================================================
# ETAP AI Platform — Mastra Database Backup Script
# =============================================================================
# Usage: ./scripts/backup-mastra-db.sh
# Frequency: Hourly (via cron)
# Retention: 7 days (168 copies)
# =============================================================================

set -euo pipefail

BACKUP_DIR="./backups/mastra.db"
TIMESTAMP=$(date +%Y-%m-%d-%H-%M-%S)
DB_FILE="./mastra.db"

mkdir -p "$BACKUP_DIR"

if [[ ! -f "$DB_FILE" ]]; then
    echo "[WARN] Database file not found: $DB_FILE"
    exit 0
fi

echo "[INFO] Backing up $DB_FILE..."
cp "$DB_FILE" "$BACKUP_DIR/mastra.db.$TIMESTAMP.bak"

# Compress backup
gzip -f "$BACKUP_DIR/mastra.db.$TIMESTAMP.bak"

# Retain only last 168 backups (7 days × 24 hours)
ls -t "$BACKUP_DIR"/*.bak.gz 2>/dev/null | tail -n +169 | xargs -r rm -f

echo "[INFO] Backup complete: $BACKUP_DIR/mastra.db.$TIMESTAMP.bak.gz"
echo "[INFO] Total backups: $(ls -1 "$BACKUP_DIR"/*.bak.gz 2>/dev/null | wc -l)"
