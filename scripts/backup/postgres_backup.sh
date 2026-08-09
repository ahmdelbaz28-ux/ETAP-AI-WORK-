#!/usr/bin/env bash
# =============================================================================
# AhmedETAP Platform — PostgreSQL Backup Script
# =============================================================================
#
# PURPOSE:
#   Create a compressed, timestamped dump of the PostgreSQL database and
#   upload it to the configured backup destination (local path or S3).
#
# USAGE:
#   ./scripts/backup/postgres_backup.sh [OPTIONS]
#
# OPTIONS:
#   -h, --help          Show this help message
#   -d, --dry-run       Print commands without executing
#   -v, --verbose       Enable verbose output
#   --dest DIR          Override local backup destination (default: /backup/postgres)
#   --retention DAYS    Days to retain local backups (default: 30)
#
# ENVIRONMENT VARIABLES (required unless --dry-run):
#   POSTGRES_HOST       PostgreSQL host (default: localhost)
#   POSTGRES_PORT       PostgreSQL port (default: 5432)
#   POSTGRES_DB         Database name (default: etap_db)
#   POSTGRES_USER       Database user (default: etap_user)
#   PGPASSWORD          Database password (set this — do NOT put in .env)
#
# OPTIONAL S3 UPLOAD:
#   S3_BACKUP_BUCKET    s3://bucket-name/path — if set, uploads backup to S3
#   AWS_ACCESS_KEY_ID   AWS credentials
#   AWS_SECRET_ACCESS_KEY
#   AWS_DEFAULT_REGION  (default: us-east-1)
#
# CRONTAB EXAMPLE (every 15 minutes — achieves RPO ≤ 15 min):
#   */15 * * * * /app/scripts/backup/postgres_backup.sh >> /var/log/etap-backup.log 2>&1
#
# SUCCESS CRITERIA:
#   RTO ≤ 30 minutes, RPO ≤ 15 minutes
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

PG_HOST="${POSTGRES_HOST:-localhost}"
PG_PORT="${POSTGRES_PORT:-5432}"
PG_DB="${POSTGRES_DB:-etap_db}"
PG_USER="${POSTGRES_USER:-etap_user}"

BACKUP_DIR="${BACKUP_DEST:-/backup/postgres}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
S3_BUCKET="${S3_BACKUP_BUCKET:-}"

DRY_RUN=false
VERBOSE=false

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/etap_db_${TIMESTAMP}.sql.gz"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
METADATA_FILE="${BACKUP_DIR}/etap_db_${TIMESTAMP}.meta.json"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            grep "^#" "$0" | sed 's/^# \?//'
            exit 0
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --dest)
            BACKUP_DIR="$2"
            BACKUP_FILE="${BACKUP_DIR}/etap_db_${TIMESTAMP}.sql.gz"
            CHECKSUM_FILE="${BACKUP_FILE}.sha256"
            METADATA_FILE="${BACKUP_DIR}/etap_db_${TIMESTAMP}.meta.json"
            shift 2
            ;;
        --retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

run() {
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "[DRY-RUN] $*"
    else
        "$@"
    fi
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

log "=== AhmedETAP PostgreSQL Backup ==="
log "Host: ${PG_HOST}:${PG_PORT}  DB: ${PG_DB}  User: ${PG_USER}"

if [[ "$DRY_RUN" == "false" ]]; then
    if ! command -v pg_dump &>/dev/null; then
        log "ERROR: pg_dump not found. Install postgresql-client." >&2
        exit 1
    fi

    if [[ -z "${PGPASSWORD:-}" ]]; then
        log "ERROR: PGPASSWORD environment variable is not set." >&2
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# Create backup directory
# ---------------------------------------------------------------------------

run mkdir -p "${BACKUP_DIR}"

# ---------------------------------------------------------------------------
# Database dump
# ---------------------------------------------------------------------------

log "Starting dump → ${BACKUP_FILE}"
START_TIME=$(date +%s)

if [[ "$DRY_RUN" == "false" ]]; then
    pg_dump \
        --host="${PG_HOST}" \
        --port="${PG_PORT}" \
        --username="${PG_USER}" \
        --dbname="${PG_DB}" \
        --format=plain \
        --no-owner \
        --no-privileges \
        --verbose \
        2>/tmp/pg_dump_stderr.log \
    | gzip --best > "${BACKUP_FILE}"

    DUMP_EXIT_CODE=${PIPESTATUS[0]}
    if [[ "$DUMP_EXIT_CODE" -ne 0 ]]; then
        log "ERROR: pg_dump failed (exit code ${DUMP_EXIT_CODE}):" >&2
        cat /tmp/pg_dump_stderr.log >&2
        rm -f "${BACKUP_FILE}"
        exit "$DUMP_EXIT_CODE"
    fi
else
    log "[DRY-RUN] pg_dump --host=${PG_HOST} --port=${PG_PORT} --username=${PG_USER} --dbname=${PG_DB} | gzip > ${BACKUP_FILE}"
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
log "Dump complete in ${ELAPSED}s"

# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------

if [[ "$DRY_RUN" == "false" ]]; then
    sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
    BACKUP_SIZE=$(stat -c%s "${BACKUP_FILE}" 2>/dev/null || stat -f%z "${BACKUP_FILE}")
    log "Checksum: $(cat "${CHECKSUM_FILE}")"
    log "Size: ${BACKUP_SIZE} bytes"
else
    BACKUP_SIZE=0
fi

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

if [[ "$DRY_RUN" == "false" ]]; then
    cat > "${METADATA_FILE}" <<JSON
{
  "backup_timestamp": "${TIMESTAMP}",
  "database_host": "${PG_HOST}",
  "database_port": ${PG_PORT},
  "database_name": "${PG_DB}",
  "database_user": "${PG_USER}",
  "backup_file": "${BACKUP_FILE}",
  "backup_size_bytes": ${BACKUP_SIZE},
  "duration_seconds": ${ELAPSED},
  "checksum_file": "${CHECKSUM_FILE}",
  "rpo_target_minutes": 15,
  "rto_target_minutes": 30,
  "platform_version": "2.1.0"
}
JSON
    log "Metadata written: ${METADATA_FILE}"
fi

# ---------------------------------------------------------------------------
# S3 upload (optional)
# ---------------------------------------------------------------------------

if [[ -n "${S3_BUCKET}" ]]; then
    log "Uploading to S3: ${S3_BUCKET}/"
    if [[ "$DRY_RUN" == "false" ]]; then
        if ! command -v aws &>/dev/null; then
            log "WARNING: aws CLI not found — skipping S3 upload" >&2
        else
            aws s3 cp "${BACKUP_FILE}" "${S3_BUCKET}/etap_db_${TIMESTAMP}.sql.gz" \
                --storage-class STANDARD_IA \
                --no-progress

            aws s3 cp "${CHECKSUM_FILE}" "${S3_BUCKET}/etap_db_${TIMESTAMP}.sql.gz.sha256" \
                --no-progress

            aws s3 cp "${METADATA_FILE}" "${S3_BUCKET}/etap_db_${TIMESTAMP}.meta.json" \
                --no-progress

            log "S3 upload complete"
        fi
    else
        log "[DRY-RUN] aws s3 cp ${BACKUP_FILE} ${S3_BUCKET}/etap_db_${TIMESTAMP}.sql.gz"
    fi
fi

# ---------------------------------------------------------------------------
# Retention — delete old local backups
# ---------------------------------------------------------------------------

log "Cleaning up backups older than ${RETENTION_DAYS} days"
if [[ "$DRY_RUN" == "false" ]]; then
    find "${BACKUP_DIR}" \
        -name "etap_db_*.sql.gz" \
        -mtime "+${RETENTION_DAYS}" \
        -delete \
        -print | while read -r f; do
            log "Deleted old backup: $f"
        done
    # Also clean up metadata and checksums
    find "${BACKUP_DIR}" \
        -name "etap_db_*.sha256" \
        -mtime "+${RETENTION_DAYS}" \
        -delete
    find "${BACKUP_DIR}" \
        -name "etap_db_*.meta.json" \
        -mtime "+${RETENTION_DAYS}" \
        -delete
else
    log "[DRY-RUN] find ${BACKUP_DIR} -name 'etap_db_*.sql.gz' -mtime +${RETENTION_DAYS} -delete"
fi

log "=== Backup complete: ${BACKUP_FILE} ==="
exit 0
