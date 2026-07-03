#!/usr/bin/env bash
# =============================================================================
# Expose the local Engineering Service to the public Internet via a
# Cloudflare quick-tunnel (no account / no DNS required).
# =============================================================================
# Usage:
#   ./scripts/start-engineering-tunnel.sh           # tries :8000
#   PORT=8080 ./scripts/start-engineering-tunnel.sh
#
# After it starts, the printed https://*.trycloudflare.com URL is the
# ENGINEERING_SERVICE_URL you pass to set-engineering-service-url.sh.
# =============================================================================
set -euo pipefail

PORT="${PORT:-8000}"

command -v docker >/dev/null 2>&1 || { echo "ERROR: docker is not installed"; exit 1; }
command -v cloudflared >/dev/null 2>&1 || {
  echo "cloudflared not found. Install:"
  echo "  Windows: winget install Cloudflare.cloudflared"
  echo "  macOS:   brew install cloudflared"
  echo "  Linux:   https://pkg.cloudflare.com/"
  exit 1
}

CONTAINER_NAME="etap-eng-svc"
IMAGE="etap-engineering-service:latest"

# Build image if missing
if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
  echo "Image ${IMAGE} not found — building (this may take a few minutes)..."
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  (cd "${SCRIPT_DIR}/.." && docker build -f Dockerfile.engineering-service -t "${IMAGE}" .) || {
    echo "ERROR: docker build failed" >&2; exit 1;
  }
fi

# Start container if not running
if ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
  echo "Starting ${CONTAINER_NAME} container on port ${PORT}..."
  docker run -d --name "${CONTAINER_NAME}" -p "${PORT}:8000" \
    -e ENGINEERING_SERVICE_API_KEY="${ENGINEERING_SERVICE_API_KEY:-}" \
    "${IMAGE}"
  echo "  Container started."
else
  echo "  Container ${CONTAINER_NAME} already exists."
  if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
    echo "  Starting it..."
    docker start "${CONTAINER_NAME}"
  fi
fi

# Wait for /health to return 200
echo "Waiting for /health to return 200..."
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/health" || echo 000)
  if [[ "${code}" = "200" ]]; then echo "  Ready after ${i}s"; break; fi
  sleep 1
done

# Clean up container on exit
trap 'echo "Stopping ${CONTAINER_NAME}..."; docker stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true' EXIT INT TERM

echo
echo "Starting cloudflared quick tunnel → http://localhost:${PORT}"
echo "When the URL appears, pass it to set-engineering-service-url.sh"
echo "Press Ctrl+C to stop."
echo
cloudflared tunnel --no-autoupdate --url "http://localhost:${PORT}"
