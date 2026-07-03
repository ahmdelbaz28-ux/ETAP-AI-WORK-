#!/usr/bin/env bash
# =============================================================================
# ETAP AI Engineering Platform - Docker Deploy Script
# =============================================================================
# Deploys the platform to production using Docker Compose.
#
# Usage:
#   ./scripts/docker_deploy.sh                    # Deploy with default .env
#   ./scripts/docker_deploy.sh --env .env.prod    # Use production env file
#   ./scripts/docker_deploy.sh --profile full     # Deploy with full profile
#   ./scripts/docker_deploy.sh --rollback         # Rollback to previous version
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Defaults
ENV_FILE="${PROJECT_DIR}/.env"
PROFILES="production"
ROLLBACK="false"
STACK_NAME="etap-platform"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_FILE="$2"
      shift 2
      ;;
    --profile)
      PROFILES="$2"
      shift 2
      ;;
    --rollback)
      ROLLBACK="true"
      shift
      ;;
    --stack-name)
      STACK_NAME="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--env .env.prod] [--profile production] [--rollback] [--stack-name etap-platform]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || { echo "Error: docker is not installed"; exit 1; }

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Error: Environment file not found: ${ENV_FILE}" >&2
  echo "Create it from .env.example: cp .env.example ${ENV_FILE}" >&2
  exit 1
fi

echo "=========================================="
echo " ETAP AI Platform - Deploy"
echo "=========================================="
echo "Stack:          ${STACK_NAME}"
echo "Profiles:       ${PROFILES}"
echo "Environment:    ${ENV_FILE}"
echo "Rollback:       ${ROLLBACK}"
echo "=========================================="

# ---------------------------------------------------------------------------
# Pull latest images
# ---------------------------------------------------------------------------
echo ""
echo "[1/4] Pulling latest images..."
docker compose \
  --project-name "${STACK_NAME}" \
  --env-file "${ENV_FILE}" \
  -f "${PROJECT_DIR}/docker-compose.yml" \
  pull

echo "[2/4] Running pre-deploy checks..."
docker compose \
  --project-name "${STACK_NAME}" \
  --env-file "${ENV_FILE}" \
  -f "${PROJECT_DIR}/docker-compose.yml" \
  config > /dev/null
echo "  ✓ Configuration is valid"

# ---------------------------------------------------------------------------
# Backup current state
# ---------------------------------------------------------------------------
BACKUP_DIR="${PROJECT_DIR}/backups/$(date +%Y%m%d_%H%M%S)"
echo "[3/4] Creating backup snapshot at ${BACKUP_DIR}..."
mkdir -p "${BACKUP_DIR}"

# Export current .env as backup
cp "${ENV_FILE}" "${BACKUP_DIR}/env.backup"

# Copy docker-compose config
cp "${PROJECT_DIR}/docker-compose.yml" "${BACKUP_DIR}/docker-compose.yml.backup"

# Backup volumes (if running)
if docker compose --project-name "${STACK_NAME}" ps >/dev/null 2>&1; then
  docker compose \
    --project-name "${STACK_NAME}" \
    --env-file "${ENV_FILE}" \
    -f "${PROJECT_DIR}/docker-compose.yml" \
    exec -T redis redis-cli -a "${REDIS_PASSWORD:-}" SAVE || true
fi

echo "  ✓ Backup created"

# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------
if [[ "${ROLLBACK}" = "true" ]]; then
  echo ""
  echo "[4/4] Performing rollback to previous version..."
  # Restore previous docker-compose
  PREVIOUS=$(ls -t "${PROJECT_DIR}/backups/" | head -2 | tail -1)
  if [[ -n "${PREVIOUS}" ]]; then
    cp "${PROJECT_DIR}/backups/${PREVIOUS}/docker-compose.yml.backup" "${PROJECT_DIR}/docker-compose.yml"
    echo "  Restored compose config from ${PREVIOUS}"
  fi

  docker compose \
    --project-name "${STACK_NAME}" \
    --env-file "${ENV_FILE}" \
    -f "${PROJECT_DIR}/docker-compose.yml" \
    up --pull always -d
else
  echo ""
  echo "[4/4] Deploying services..."

  docker compose \
    --project-name "${STACK_NAME}" \
    --env-file "${ENV_FILE}" \
    -f "${PROJECT_DIR}/docker-compose.yml" \
    --profile "${PROFILES}" \
    up --pull always -d --remove-orphans
fi

# ---------------------------------------------------------------------------
# Post-deploy verification
# ---------------------------------------------------------------------------
echo ""
echo "=========================================="
echo " Post-Deploy Verification"
echo "=========================================="

# Wait for services to be healthy
echo "Waiting for services to become healthy..."
sleep 10

for service in $(docker compose \
  --project-name "${STACK_NAME}" \
  --env-file "${ENV_FILE}" \
  -f "${PROJECT_DIR}/docker-compose.yml" \
  config --services 2>/dev/null); do

  status=$(docker compose \
    --project-name "${STACK_NAME}" \
    --env-file "${ENV_FILE}" \
    -f "${PROJECT_DIR}/docker-compose.yml" \
    ps "${service}" --format json 2>/dev/null | \
    python3 -c "import sys,json; data=json.load(sys.stdin); print(data.get('Health',''))" 2>/dev/null || echo "unknown")

  echo "  ${service}: ${status}"
done

echo ""
echo "=========================================="
echo " Deploy Complete"
echo "=========================================="
echo "Run 'docker compose logs -f' to tail logs."
echo "=========================================="
