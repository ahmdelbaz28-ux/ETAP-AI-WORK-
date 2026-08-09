#!/usr/bin/env bash
# =============================================================================
# ETAP AI Platform — Verify LLM Secrets (Bash)
# =============================================================================
# Checks that LLM API keys are set as Cloudflare Worker secrets.
#
# Usage:
#   ./scripts/verify-secrets.sh
#
# Environment:
#   WRANGLER_WORKER_NAME  - Override the Worker name (default: auto-detected)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Worker name: env var > wrangler.jsonc > fallback
detect_worker_name() {
  if [[ -n "${WRANGLER_WORKER_NAME:-}" ]]; then
    echo "${WRANGLER_WORKER_NAME}"
    return
  fi
  local detected
  detected=$(grep -oP '"name"\s*:\s*"\K[^"]+' "${PROJECT_DIR}/wrangler.jsonc" 2>/dev/null | head -1)
  if [[ -n "${detected}" ]]; then
    echo "${detected}"
    return
  fi
  echo "ahmed-etap"
}

WORKER_NAME=$(detect_worker_name)

SECRETS=("OPENAI_API_KEY" "QWEN_API_KEY" "GLM_API_KEY" "NVIDIA_API_KEY" "LANGWATCH_API_KEY")
MISSING=()
FOUND=()

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║           ETAP AI Platform — Secret Verification                            ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check wrangler
if ! npx wrangler --version &> /dev/null; then
    echo "❌ wrangler not available. Run: npm install -g wrangler"
    exit 1
fi

# Check login
if ! npx wrangler whoami &> /dev/null; then
    echo "❌ Not logged in. Run: npx wrangler login"
    exit 1
fi

echo "Worker: ${WORKER_NAME}"
echo ""
echo "Checking API key secrets on Cloudflare..."
echo ""

# Fetch secret list once, then check each secret name
SECRET_LIST=$(npx wrangler secret list --name "${WORKER_NAME}" 2>/dev/null || echo "")

for secret in "${SECRETS[@]}"; do
    # Use a simple grep for the secret name — robust against format changes
    if echo "${SECRET_LIST}" | grep -q "\"${secret}\""; then
        echo -e "${GREEN}✅${NC} ${secret} — set"
        FOUND+=("${secret}")
    else
        echo -e "${RED}❌${NC} ${secret} — not set"
        MISSING+=("${secret}")
    fi
done

echo ""

if [[ ${#MISSING[@]} -eq 0 ]]; then
    echo "═══════════════════════════════════════════════════════════════════════════════"
    echo -e "${GREEN}All ${#SECRETS[@]} secrets are set.${NC}"
    echo "═══════════════════════════════════════════════════════════════════════════════"
    echo ""
    echo "Next: Deploy the worker with:"
    echo "  npx wrangler deploy"
    exit 0
else
    echo "───────────────────────────────────────────────────────────────────────────────"
    echo -e "${YELLOW}${#MISSING[@]} of ${#SECRETS[@]} secrets are missing.${NC}"
    echo "───────────────────────────────────────────────────────────────────────────────"
    echo ""
    echo "Missing secrets:"
    for m in "${MISSING[@]}"; do echo "  - ${m}"; done
    echo ""
    echo "Set missing secrets with:"
    echo "  ./scripts/set-llm-secrets.sh"
    exit 1
fi
