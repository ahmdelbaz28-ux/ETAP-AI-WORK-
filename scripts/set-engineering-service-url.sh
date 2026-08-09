#!/usr/bin/env bash
# =============================================================================
# Wire ENGINEERING_SERVICE_URL into the Cloudflare Worker (production + staging)
# =============================================================================
# Usage:
#   ./scripts/set-engineering-service-url.sh https://my-eng-svc.example.com [api-key]
#
# Or interactive (will prompt):
#   ./scripts/set-engineering-service-url.sh
#
# The URL must be PUBLICLY reachable from Cloudflare's edge.
# For local dev, see scripts/start-engineering-tunnel.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

URL="${1:-}"
API_KEY="${2:-}"
WORKER_NAME="${WORKER_NAME:-ahmed-etap}"
STAGING_NAME="${STAGING_NAME:-ahmed-etap-staging}"
DIVIDER='=========================================='

if [[ -z "${URL}" ]]; then
  read -rp "Engineering Service public URL (e.g. https://eng-svc.example.com): " URL
fi
if [[ -z "${URL}" ]]; then
  echo "ERROR: URL is required" >&2
  exit 1
fi

# Strip trailing slash
URL="${URL%/}"

if [[ -z "${API_KEY}" ]]; then
  read -rsp "Optional ENGINEERING_SERVICE_API_KEY (press Enter to skip): " API_KEY
  echo
fi

echo "${DIVIDER}"
echo " Wiring Engineering Service into Worker"
echo "${DIVIDER}"
echo "URL:         ${URL}"
echo "API key:     ${API_KEY:+***set***}${API_KEY:-<not set>}"
echo "Production:  ${WORKER_NAME}"
echo "Staging:     ${STAGING_NAME}"
echo "${DIVIDER}"

# Make sure wrangler is available
command -v npx >/dev/null 2>&1 || { echo "ERROR: npx not found" >&2; exit 1; }

echo
echo "[1/4] Setting ENGINEERING_SERVICE_URL on production Worker..."
# Pipe form (works on wrangler 3.x and 4.x). Do NOT mix with trailing `--`.
printf "%s" "${URL}" | npx wrangler secret put ENGINEERING_SERVICE_URL --name "${WORKER_NAME}"

if [[ -n "${API_KEY}" ]]; then
  echo "[2/4] Setting ENGINEERING_SERVICE_API_KEY on production Worker..."
  printf "%s" "${API_KEY}" | npx wrangler secret put ENGINEERING_SERVICE_API_KEY --name "${WORKER_NAME}"
else
  echo "[2/4] Skipping ENGINEERING_SERVICE_API_KEY (none provided)"
fi

echo
echo "[3/4] Setting ENGINEERING_SERVICE_URL on staging Worker (best-effort)..."
if printf "%s" "${URL}" | npx wrangler secret put ENGINEERING_SERVICE_URL --name "${STAGING_NAME}" 2>&1; then
  if [[ -n "${API_KEY}" ]]; then
    printf "%s" "${API_KEY}" | npx wrangler secret put ENGINEERING_SERVICE_API_KEY --name "${STAGING_NAME}" 2>&1 || true
  fi
else
  echo "  WARNING: staging Worker secret not set — Worker name '${STAGING_NAME}' may not exist under this Cloudflare account." >&2
fi

echo
echo "[4/4] Verifying Worker /health reports engineeringService.healthy=true..."
sleep 2
VERIFY_URL="https://${WORKER_NAME}.ahmdelbaz28.workers.dev/health"
echo "  GET ${VERIFY_URL}"
RESP="$(curl -fsS "${VERIFY_URL}" || true)"
if [[ -z "${RESP}" ]]; then
  echo "  ERROR: could not reach Worker /health" >&2
  exit 2
fi

echo "${RESP}" | node -e "
let s=''; process.stdin.on('data',d=>s+=d); process.stdin.on('end',()=>{
  let d; try { d = JSON.parse(s); } catch (e) {
    console.error('  ERROR: Worker /health returned non-JSON:', s.slice(0,200));
    process.exit(2);
  }
  const es = d.engineeringService || {};
  console.log('  engineeringService.configured =', es.configured);
  console.log('  engineeringService.healthy    =', es.healthy);
  console.log('  engineeringService.latencyMs  =', es.latencyMs);
  console.log('  engineeringService.error      =', es.error || '(none)');
  process.exit(es.healthy === true ? 0 : 1);
});
" || {
  echo
  echo "  Worker /health did NOT report engineeringService.healthy=true." >&2
  echo "  Common causes:" >&2
  echo "   1. URL not publicly reachable from Cloudflare" >&2
  echo "   2. URL is HTTP (must be HTTPS for Worker → service calls)" >&2
  echo "   3. Service /health endpoint returns non-200" >&2
  echo "  Verify directly:" >&2
  echo "    curl -fsS ${URL}/health" >&2
  exit 3
}

echo
echo "${DIVIDER}"
echo " DONE — Worker is now wired to Engineering Service"
echo "${DIVIDER}"
