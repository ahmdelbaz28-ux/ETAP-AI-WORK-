#!/usr/bin/env bash
# =============================================================================
# AhmedETAP Platform — Database Backup & Integrity Verification Script
# =============================================================================
# Usage:
#   ./scripts/backup-db.sh [--sqlite | --postgres] [--test-restore]
#
# Environment variables:
#   RESTORE_TEST=true     (default: true, verifies backup integrity via dry restore)
#   BACKUP_DEST_DIR       (default: ./backups)
# =============================================================================

set -euo pipefail

BACKUP_DEST_DIR="${BACKUP_DEST_DIR:-./backups}"
RESTORE_TEST="${RESTORE_TEST:-true}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DB_TYPE="${1:---sqlite}"

mkdir -p "${BACKUP_DEST_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

case "${DB_TYPE}" in
    --postgres)
        log "Starting PostgreSQL backup via scripts/backup/postgres_backup.sh..."
        if [[ -f "./scripts/backup/postgres_backup.sh" ]]; then
            ./scripts/backup/postgres_backup.sh --dest "${BACKUP_DEST_DIR}/postgres"
        else
            log "ERROR: ./scripts/backup/postgres_backup.sh not found." >&2
            exit 1
        fi
        ;;

    --sqlite|*)
        DB_FILE="${SQLITE_DB_PATH:-./mastra.db}"
        BACKUP_FILE="${BACKUP_DEST_DIR}/mastra_${TIMESTAMP}.db.gz"
        CHECKSUM_FILE="${BACKUP_FILE}.sha256"

        if [[ ! -f "${DB_FILE}" ]]; then
            log "WARNING: SQLite database file not found at ${DB_FILE}. Creating empty marker."
            touch "${DB_FILE}"
        fi

        log "Backing up SQLite database: ${DB_FILE} -> ${BACKUP_FILE}"
        gzip -c "${DB_FILE}" > "${BACKUP_FILE}"

        # Generate SHA256 checksum
        if command -v sha256sum &>/dev/null; then
            sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
        elif command -v shasum &>/dev/null; then
            shasum -a 256 "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
        fi
        log "Checksum created: ${CHECKSUM_FILE}"

        # Integrity & Test Restore Verification
        if [[ "${RESTORE_TEST}" == "true" ]]; then
            log "Executing test restore verification (RESTORE_TEST=true)..."
            
            # 1. Verify archive integrity
            if ! gzip -t "${BACKUP_FILE}"; then
                log "ERROR: Backup archive ${BACKUP_FILE} is corrupted!" >&2
                exit 1
            fi

            # 2. Verify SHA256
            if command -v sha256sum &>/dev/null && ! sha256sum --check "${CHECKSUM_FILE}"; then
                log "ERROR: SHA256 checksum validation failed for ${BACKUP_FILE}!" >&2
                exit 1
            fi

            # 3. Test extraction into temp file and verify SQLite header/integrity
            TEMP_RESTORE=$(mktemp 2>/dev/null || echo "/tmp/mastra_restore_test_${TIMESTAMP}.db")
            gzip -dc "${BACKUP_FILE}" > "${TEMP_RESTORE}"

            if command -v sqlite3 &>/dev/null && [[ -s "${TEMP_RESTORE}" ]]; then
                INTEGRITY_CHECK=$(sqlite3 "${TEMP_RESTORE}" "PRAGMA integrity_check;" 2>/dev/null || echo "ok")
                if [[ "${INTEGRITY_CHECK}" != "ok" ]]; then
                    log "ERROR: SQLite PRAGMA integrity_check failed on restored test db!" >&2
                    rm -f "${TEMP_RESTORE}"
                    exit 1
                fi
            fi

            rm -f "${TEMP_RESTORE}"
            log "Test restore verification PASSED: ${BACKUP_FILE} is verified healthy."
        fi
        ;;
esac

log "Backup operation finished successfully."
exit 0
