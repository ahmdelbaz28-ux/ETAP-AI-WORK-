#!/usr/bin/env bash
# =============================================================================
# AhmedETAP — Interactive Infrastructure & Secrets Setup Wizard ⚡
# =============================================================================
# Walks engineers and administrators through manual credential provisioning,
# cloud database integration, and local .env generation with zero friction.
# =============================================================================

set -euo pipefail

# Visual tokens & colors
BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
CYAN="\033[36m"
RED="\033[31m"
RESET="\033[0m"

TOTAL_STAGES=6
ENV_FILE=".env"

header() {
    clear || true
    echo -e "${CYAN}${BOLD}"
    echo "============================================================"
    echo "       ⚡ AhmedETAP Platform — Setup Wizard ⚡"
    echo "============================================================"
    echo -e "${RESET}"
}

stage() {
    local num="$1"
    local title="$2"
    echo -e "${YELLOW}${BOLD}[Stage ${num}/${TOTAL_STAGES}] ${title}${RESET}"
    echo "------------------------------------------------------------"
}

step() {
    echo -e "${CYAN}➜${RESET} $1"
}

open_url() {
    local url="$1"
    echo -e "${GREEN}Opening:${RESET} ${url}"
    if command -v xdg-open &>/dev/null; then
        xdg-open "$url" &>/dev/null || true
    elif command -v open &>/dev/null; then
        open "$url" &>/dev/null || true
    elif command -v start &>/dev/null; then
        start "$url" &>/dev/null || true
    fi
}

write_env() {
    local key="$1"
    local val="$2"
    if [ ! -f "$ENV_FILE" ]; then
        touch "$ENV_FILE"
    fi
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        # Replace existing key
        sed -i.bak "s|^${key}=.*|${key}=${val}|" "$ENV_FILE" && rm -f "${ENV_FILE}.bak"
    else
        echo "${key}=${val}" >> "$ENV_FILE"
    fi
}

# --- Stage 1: GitHub & Repository Token ---
header
stage 1 "GitHub Access & Automation Token"
step "Visit your GitHub Tokens settings page."
open_url "https://github.com/settings/tokens"
echo ""
read -r -p "Enter GITHUB_TOKEN (press Enter to skip if already set): " gh_tok
if [ -n "$gh_tok" ]; then
    write_env "GITHUB_TOKEN" "$gh_tok"
    write_env "GH_PAT" "$gh_tok"
    echo -e "${GREEN}✓ GitHub token saved to .env${RESET}"
fi
echo ""
read -n 1 -s -r -p "Press any key to proceed to Stage 2..."

# --- Stage 2: Hugging Face Space ---
header
stage 2 "Hugging Face Space API Token"
step "Visit your Hugging Face Access Tokens page."
open_url "https://huggingface.co/settings/tokens"
echo ""
read -r -p "Enter HF_TOKEN (press Enter to skip): " hf_tok
if [ -n "$hf_tok" ]; then
    write_env "HF_TOKEN" "$hf_tok"
    write_env "HF_SPACE_NAME" "ahmdelbaz28/AhmedETAP-Platform"
    echo -e "${GREEN}✓ HuggingFace token saved to .env${RESET}"
fi
echo ""
read -n 1 -s -r -p "Press any key to proceed to Stage 3..."

# --- Stage 3: Langfuse Observability ---
header
stage 3 "Langfuse LLM Observability & Prompts"
step "Open Langfuse Cloud dashboard."
open_url "https://cloud.langfuse.com"
echo ""
read -r -p "Enter LANGFUSE_PUBLIC_KEY (pk-lf-...): " lf_pub
read -r -p "Enter LANGFUSE_SECRET_KEY (sk-lf-...): " lf_sec
if [ -n "$lf_pub" ] && [ -n "$lf_sec" ]; then
    write_env "LANGFUSE_PUBLIC_KEY" "$lf_pub"
    write_env "LANGFUSE_SECRET_KEY" "$lf_sec"
    write_env "LANGFUSE_BASE_URL" "https://cloud.langfuse.com"
    echo -e "${GREEN}✓ Langfuse keys saved to .env${RESET}"
fi
echo ""
read -n 1 -s -r -p "Press any key to proceed to Stage 4..."

# --- Stage 4: Neo4j Aura Graph Database ---
header
stage 4 "Neo4j Aura Enterprise Graph Database"
step "Open Neo4j Aura console."
open_url "https://console.neo4j.io"
echo ""
read -r -p "Enter Neo4j Connection URI (neo4j+s://...): " neo_uri
read -r -p "Enter Neo4j Username: " neo_user
read -r -p "Enter Neo4j Password: " neo_pass
if [ -n "$neo_uri" ] && [ -n "$neo_pass" ]; then
    write_env "NEO4J_URI" "$neo_uri"
    write_env "NEO4J_USER" "$neo_user"
    write_env "NEO4J_PASSWORD" "$neo_pass"
    echo -e "${GREEN}✓ Neo4j Aura credentials saved to .env${RESET}"
fi
echo ""
read -n 1 -s -r -p "Press any key to proceed to Stage 5..."

# --- Stage 5: Supabase Managed Database ---
header
stage 5 "Supabase PostgreSQL Database"
step "Open Supabase project dashboard."
open_url "https://supabase.com/dashboard"
echo ""
read -r -p "Enter SUPABASE_URL: " sb_url
read -r -p "Enter SUPABASE_ANON_KEY: " sb_anon
read -r -p "Enter SUPABASE_SERVICE_ROLE_KEY: " sb_sec
if [ -n "$sb_url" ] && [ -n "$sb_sec" ]; then
    write_env "SUPABASE_URL" "$sb_url"
    write_env "SUPABASE_ANON_KEY" "$sb_anon"
    write_env "SUPABASE_SERVICE_ROLE_KEY" "$sb_sec"
    echo -e "${GREEN}✓ Supabase keys saved to .env${RESET}"
fi
echo ""
read -n 1 -s -r -p "Press any key to proceed to Stage 6..."

# --- Stage 6: Final Verification ---
header
stage 6 "Live Service Verification"
step "Executing automated service verification suite..."
echo ""
if command -v python &>/dev/null; then
    python scripts/verify_services.py
elif command -v python3 &>/dev/null; then
    python3 scripts/verify_services.py
fi

echo ""
echo -e "${GREEN}${BOLD}============================================================${RESET}"
echo -e "${GREEN}${BOLD}🎉 Setup Wizard Completed Successfully!${RESET}"
echo -e "${GREEN}${BOLD}============================================================${RESET}"
echo -e "Your local configuration in ${CYAN}.env${RESET} is verified and ready."
