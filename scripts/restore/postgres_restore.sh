#!/usr/bin/env bash
# ============================================================
# AhmedETAP — PostgreSQL Restore Script
# ============================================================
# Restores a database backup created by scripts/backup/postgres_backup.sh
#
# Usage:
#   ./scripts/restore/postgres_restore.sh <backup_file> [--dry-run]
#
# Examples:
#   ./scripts/restore/postgres_restore.sh /backups/etap_20260718_120000.sql.gz
#   ./scripts/restore/postgres_restore.sh /backups/etap_20260718_120000.sql.gz --dry-run
#
# Requirements:
#   - pg_restore or psql (PostgreSQL client tools)
#   - DATABASE_URL or PGHOST/PGPORT/PGUSER/PGDATABASE env vars
#   - The backup file must be a .sql.gz or .sql file
#
# Security:
#   - Prompts for confirmation before overwriting production data
#   - --dry-run shows what would be restored without executing
#   - Creates a pre-restore backup before overwriting
# ============================================================

set -euo pipefail

# --- Configuration ---
BACKUP_FILE="${1:-}"
DRY_RUN=false
if [[ "${2:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

if [[ -z "$BACKUP_FILE" ]]; then
    echo "Usage: $0 <backup_file> [--dry-run]"
    echo ""
    echo "Available backups:"
    if [[ -d /backups ]]; then
        ls -lh /backups/*.sql.gz 2>/dev/null || echo "  (no .sql.gz files in /backups)"
    fi
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# --- Database connection ---
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-etap_db}"

# Override with DATABASE_URL if set
if [[ -n "${DATABASE_URL:-}" ]]; then
    PGURL="$DATABASE_URL"
    PGUSER=$(echo "$PGURL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
    PGHOST=$(echo "$PGURL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
    PGPORT=$(echo "$PGURL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
    PGDATABASE=$(echo "$PGURL" | sed -n 's|.*/\([^?]*\).*|\1|p')
fi

echo "=========================================="
echo "  AhmedETAP Database Restore"
echo "=========================================="
echo "  Backup file: $BACKUP_FILE"
echo "  Database:    $PGDATABASE"
echo "  Host:        $PGHOST:$PGPORT"
echo "  User:        $PGUSER"
echo "  Dry run:     $DRY_RUN"
echo "=========================================="
echo ""

# --- Verify backup integrity ---
echo "[1/5] Verifying backup integrity..."
if [[ "$BACKUP_FILE" == *.gz ]]; then
    if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
        echo "ERROR: Backup file is corrupted (gzip integrity check failed)"
        exit 1
    fi
    BACKUP_SIZE=$(gzip -l "$BACKUP_FILE" | tail -1 | awk '{print $2}')
    echo "  OK: Backup integrity verified (uncompressed size: $(numfmt --to=iec $BACKUP_SIZE 2>/dev/null || echo ${BACKUP_SIZE}B))"
    DECOMPRESSOR="gunzip -c"
else
    BACKUP_SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE" 2>/dev/null || echo "0")
    echo "  OK: Backup is plain SQL (size: $(numfmt --to=iec $BACKUP_SIZE 2>/dev/null || echo ${BACKUP_SIZE}B))"
    DECOMPRESSOR="cat"
fi

# --- Check for SHA256 checksum ---
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
if [[ -f "$CHECKSUM_FILE" ]]; then
    echo "[2/5] Verifying checksum..."
    EXPECTED=$(cat "$CHECKSUM_FILE" | awk '{print $1}')
    ACTUAL=$(sha256sum "$BACKUP_FILE" | awk '{print $1}')
    if [[ "$EXPECTED" != "$ACTUAL" ]]; then
        echo "ERROR: Checksum mismatch! Expected: $EXPECTED, Got: $ACTUAL"
        exit 1
    fi
    echo "  OK: Checksum verified"
else
    echo "[2/5] No checksum file found — skipping verification"
fi

# --- Pre-restore backup ---
if [[ "$DRY_RUN" == false ]]; then
    echo "[3/5] Creating pre-restore backup..."
    PRE_RESTORE_BACKUP="/tmp/pre_restore_$(date +%Y%m%d_%H%M%S).sql.gz"
    if PGPASSWORD="${PGPASSWORD:-}" pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" 2>/dev/null | gzip > "$PRE_RESTORE_BACKUP"; then
        echo "  OK: Pre-restore backup: $PRE_RESTORE_BACKUP"
    else
        echo "  WARN: Could not create pre-restore backup (database may be empty)"
    fi
else
    echo "[3/5] [DRY RUN] Would create pre-restore backup"
fi

# --- Confirmation ---
if [[ "$DRY_RUN" == false ]]; then
    echo ""
    echo "WARNING: This will OVERWRITE the current database '$PGDATABASE'"
    echo "    All existing data will be replaced with the backup contents."
    echo ""
    read -p "Type 'RESTORE' to confirm: " CONFIRM
    if [[ "$CONFIRM" != "RESTORE" ]]; then
        echo "Restore cancelled."
        exit 0
    fi
fi

# --- Restore ---
echo "[4/5] Restoring database..."
if [[ "$DRY_RUN" == true ]]; then
    echo "  [DRY RUN] Would execute: $DECOMPRESSOR $BACKUP_FILE | psql ..."
    echo "  [DRY RUN] First 20 lines of backup:"
    $DECOMPRESSOR "$BACKUP_FILE" | head -20
    echo "  ..."
    echo "  [DRY RUN] Restore would complete here"
else
    if $DECOMPRESSOR "$BACKUP_FILE" | PGPASSWORD="${PGPASSWORD:-}" psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -v ON_ERROR_STOP=1 2>&1; then
        echo "  OK: Restore completed successfully"
    else
        echo "  FAIL: Restore failed — check errors above"
        echo "  Pre-restore backup: ${PRE_RESTORE_BACKUP:-none}"
        exit 1
    fi
fi

# --- Verify ---
echo "[5/5] Verifying restore..."
if [[ "$DRY_RUN" == false ]]; then
    TABLE_COUNT=$(PGPASSWORD="${PGPASSWORD:-}" psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null | tr -d ' ' || echo "0")
    echo "  OK: Database has $TABLE_COUNT tables in public schema"
    if [[ "$TABLE_COUNT" -gt 0 ]]; then
        echo "  OK: Restore verification passed"
    else
        echo "  WARN: No tables found — restore may have failed silently"
    fi
else
    echo "  [DRY RUN] Would verify table count"
fi

echo ""
echo "=========================================="
echo "  Restore complete!"
echo "=========================================="
if [[ "$DRY_RUN" == false && -f "${PRE_RESTORE_BACKUP:-}" ]]; then
    echo "  Pre-restore backup: $PRE_RESTORE_BACKUP"
    echo "  (Keep this until you verify the restored data is correct)"
fi
echo ""
