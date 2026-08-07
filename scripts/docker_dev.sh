#!/usr/bin/env bash
# =============================================================================
# ETAP AI Engineering Platform - Development Environment
# =============================================================================
# Starts the development environment with hot reload and debug support.
#
# Usage:
#   ./scripts/docker_dev.sh                  # Start dev environment
#   ./scripts/docker_dev.sh --build          # Rebuild images before starting
#   ./scripts/docker_dev.sh --no-worker      # Skip Windows worker
#   ./scripts/docker_dev.sh --logs           # Follow logs after starting
#   ./scripts/docker_dev.sh stop             # Stop dev environment
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

ACTION="${1:-start}"
STACK_NAME="etap-dev"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
BUILD="false"
FOLLOW_LOGS="false"
NO_WORKER="false"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    start)
      ACTION="start"
      shift
      ;;
    stop|down)
      ACTION="stop"
      shift
      ;;
    restart)
      ACTION="restart"
      shift
      ;;
    --build)
      BUILD="true"
      shift
      ;;
    --logs)
      FOLLOW_LOGS="true"
      shift
      ;;
    --no-worker)
      NO_WORKER="true"
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [start|stop|restart] [--build] [--logs] [--no-worker]"
      exit 0
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Ensure .env file exists
# ---------------------------------------------------------------------------
if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
  echo "Creating .env from .env.example..."
  cp "${PROJECT_DIR}/.env.example" "${PROJECT_DIR}/.env"
  echo "  ✓ .env created. Edit it with your API keys before proceeding."
fi

# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || { echo "Error: docker is not installed" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
case "${ACTION}" in
  start)
    echo "=========================================="
    echo " ETAP AI Platform - Dev Environment"
    echo "=========================================="

    COMPOSE_ARGS=(
      --project-name "${STACK_NAME}"
      --env-file "${PROJECT_DIR}/.env"
      -f "${PROJECT_DIR}/docker-compose.yml"
      -f "${PROJECT_DIR}/docker-compose.override.yml"
    )

    # If not using worker, skip its profile
    if [[ "${NO_WORKER}" = "true" ]]; then
      EXTRA_ARGS+=(--profile development)
    else
      EXTRA_ARGS+=(--profile "development,windows")
    fi

    if [[ "${BUILD}" = "true" ]]; then
      echo "[1/3] Building images..."
      docker compose "${COMPOSE_ARGS[@]}" build
    fi

    echo "[2/3] Starting services..."
    docker compose "${COMPOSE_ARGS[@]}" \
      "${EXTRA_ARGS[@]}" \
      up -d --remove-orphans

    echo "[3/3] Services started."
    echo ""
    echo "  Main API:   http://localhost:${APP_PORT:-3000}"
    echo "  Health:     http://localhost:${APP_PORT:-3000}/health"
    echo "  Redis CLI:  docker exec -it etap-redis redis-cli"
    echo ""

    if [[ "${FOLLOW_LOGS}" = "true" ]]; then
      echo "Tailing logs (Ctrl+C to stop)..."
      docker compose "${COMPOSE_ARGS[@]}" logs -f
    fi
    ;;

  stop)
    echo "Stopping dev environment..."
    docker compose \
      --project-name "${STACK_NAME}" \
      --env-file "${PROJECT_DIR}/.env" \
      -f "${PROJECT_DIR}/docker-compose.yml" \
      -f "${PROJECT_DIR}/docker-compose.override.yml" \
      down --remove-orphans
    echo "  ✓ Dev environment stopped"
    ;;

  restart)
    echo "Restarting dev environment..."
    "${SCRIPT_DIR}/docker_dev.sh" stop
    "${SCRIPT_DIR}/docker_dev.sh" start
    ;;

  *)
    echo "Unknown action: ${ACTION}"
    echo "Usage: $0 [start|stop|restart] [--build] [--logs] [--no-worker]"
    exit 1
    ;;
esac
