#!/usr/bin/env bash
# =============================================================================
# ETAP AI Platform — LLM API Secret Setup (Bash)
# =============================================================================
# Sets LLM provider and observability API keys as encrypted Cloudflare Worker secrets.
#
# Usage:
#   ./scripts/set-llm-secrets.sh
#
# Prerequisites:
#   1. You have a Cloudflare account
#   2. You have installed wrangler: npm install -g wrangler
#   3. You have run: npx wrangler login
#   4. You have the API keys ready (see .env.example for provider links)
#
# Environment:
#   WRANGLER_WORKER_NAME  - Override the Worker name (default: auto-detected)
#
# Secrets set:
#   OPENAI_API_KEY     — OpenAI GPT-4 / GPT-4o
#   QWEN_API_KEY       — Alibaba Qwen (fallback)
#   GLM_API_KEY        — Zhipu GLM-4 (fallback)
#   NVIDIA_API_KEY    — NVIDIA NIM (Llama, Mistral, etc.)
#   LANGWATCH_API_KEY  — Agent observability & prompt management
#
# Note: These are Cloudflare Worker secrets (encrypted at rest).
#       They are NOT written to the local .env file.
#       For local development, set them in .env separately.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
  echo ""
  echo "╔══════════════════════════════════════════════════════════════════════════════╗"
  echo "║           ETAP AI Platform — API Secret Setup                               ║"
  echo "╚══════════════════════════════════════════════════════════════════════════════╝"
  echo ""
}

print_success() { echo -e "${GREEN}✅${NC} $1"; }  # NOSONAR — S7679: function params assigned to locals; readability
print_error()   { echo -e "${RED}❌${NC} $1"; }  # NOSONAR — S7679: function params assigned to locals; readability
print_warn()    { echo -e "${YELLOW}⚠️${NC} $1"; }  # NOSONAR — S7679: function params assigned to locals; readability
print_info()    { echo -e "${BLUE}ℹ️${NC} $1"; }  # NOSONAR — S7679: function params assigned to locals; readability

# ---------------------------------------------------------------------------
# Worker name: env var > wrangler.jsonc > fallback
# ---------------------------------------------------------------------------
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

# Check if wrangler is available
check_wrangler() {
  if ! command -v npx &> /dev/null; then
    print_error "npx is not installed. Install Node.js first: https://nodejs.org/"
    exit 1
  fi

  if ! npx wrangler --version &> /dev/null; then
    print_error "wrangler is not installed. Install it: npm install -g wrangler"
    exit 1
  fi

  print_success "wrangler is available"
}

# Check if user is logged in to Cloudflare
check_login() {
  print_info "Checking Cloudflare authentication..."

  if ! npx wrangler whoami &> /dev/null; then
    print_error "You are not logged in to Cloudflare."
    echo ""
    print_info "Run: npx wrangler login"
    echo ""
    print_info "This will open a browser window to authenticate with Cloudflare."
    print_info "After logging in, run this script again."
    exit 1
  fi

  print_success "Authenticated with Cloudflare"
  local account
  account=$(npx wrangler whoami 2>/dev/null | grep -E "Account|Email" | head -2 || true)
  print_info "Account info:"
  echo "${account}" | sed 's/^/   /'
}

# Prompt for a secret (hidden input)
prompt_secret() {
  local name="$1"
  local description="$2"
  local value=""

  echo ""
  print_info "${name}"
  echo "   ${description}"
  echo ""
  read -rsp "   Enter ${name} (or press Enter to skip): " value
  echo ""
  echo "${value}"
}

# Set a single secret via wrangler — shows errors on failure
set_secret() {
  local name="$1"
  local value="$2"

  if [[ -z "${value}" ]]; then
    print_warn "Skipping ${name} — no value provided"
    return 0
  fi

  print_info "Setting ${name} on Worker '${WORKER_NAME}'..."
  local err_output
  err_output=$(echo "${value}" | npx wrangler secret put "${name}" --name "${WORKER_NAME}" 2>&1 >/dev/null) || {
    print_error "Failed to set ${name}: ${err_output}"
    return 1
  }
  print_success "${name} set successfully"
}

# Main
main() {
  print_header
  check_wrangler
  check_login

  echo ""
  echo "───────────────────────────────────────────────────────────────────────────────"
  print_info "You will be prompted for 5 API keys (4 LLM + 1 observability)."
  print_info "If you don't have a key yet, press Enter to skip and set it later."
  print_info "These keys are stored as encrypted Cloudflare Worker secrets."
  print_info "For local development, set them in your .env file separately."
  print_info "Links to obtain keys are in .env.example"
  echo "───────────────────────────────────────────────────────────────────────────────"
  print_info "Target Worker: ${WORKER_NAME}"
  echo ""

  local openai_key
  openai_key=$(prompt_secret "OPENAI_API_KEY" "Primary LLM provider (GPT-4 / GPT-4o). Get one at: https://platform.openai.com/api-keys")

  local qwen_key
  qwen_key=$(prompt_secret "QWEN_API_KEY" "Fallback LLM provider (Alibaba Qwen). Get one at: https://dashscope.console.aliyun.com/")

  local glm_key
  glm_key=$(prompt_secret "GLM_API_KEY" "Fallback LLM provider (Zhipu GLM-4). Get one at: https://open.bigmodel.cn/")

  local nvidia_key
  nvidia_key=$(prompt_secret "NVIDIA_API_KEY" "Fourth LLM provider (NVIDIA NIM). Get one at: https://build.nvidia.com/")

  local langwatch_key
  langwatch_key=$(prompt_secret "LANGWATCH_API_KEY" "Agent observability & prompt management. Get one at: https://app.langwatch.ai/")

  echo ""
  echo "───────────────────────────────────────────────────────────────────────────────"
  print_info "Setting secrets on Cloudflare Workers..."
  echo "───────────────────────────────────────────────────────────────────────────────"

  set_secret "OPENAI_API_KEY" "${openai_key}"
  set_secret "QWEN_API_KEY" "${qwen_key}"
  set_secret "GLM_API_KEY" "${glm_key}"
  set_secret "NVIDIA_API_KEY" "${nvidia_key}"
  set_secret "LANGWATCH_API_KEY" "${langwatch_key}"

  echo ""
  echo "═══════════════════════════════════════════════════════════════════════════════"
  print_success "API secret setup complete!"
  echo "═══════════════════════════════════════════════════════════════════════════════"
  echo ""
  print_info "Next steps:"
  echo "   1. Verify secrets are set:   ./scripts/verify-secrets.sh"
  echo "   2. Deploy the worker:         npx wrangler deploy"
  echo "   3. Test a provider:           curl -H 'x-api-key: YOUR_KEY' \\"
  echo "                                  https://ahmed-etap.ahmdelbaz28.workers.dev/api/v1/providers"
  echo ""
}

main "$@"
