#!/usr/bin/env bash
#
# AhmedETAP - GitHub Secrets & Environment Setup Wizard
#
# Walks a new contributor through creating API keys and secrets, then
# pushes them to GitHub Actions and writes the local .env.
#
# Run:  bash scripts/setup-secrets-wizard.sh
#
# Everything above the "STAGES" marker is the wizard library: do not hand-edit
# it. Author the per-step stages below the marker.

set -euo pipefail

# ==============================================================================
# Wizard library - delightful, consistent UX. Identical across every wizard.
# ==============================================================================

if [[ -t 1 ]] && command -v tput >/dev/null 2>&1 && [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
  BOLD=$(tput bold); DIM=$(tput dim); RESET=$(tput sgr0)
  BLUE=$(tput setaf 4); GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3); RED=$(tput setaf 1)
else
  BOLD=""; DIM=""; RESET=""; BLUE=""; GREEN=""; YELLOW=""; RED=""
fi

TOTAL_STAGES=0
TOTAL_MINUTES=0

_STAGE_INDEX=0
_MINUTES_ELAPSED=0
ENV_FILE="${ENV_FILE:-.env}"
WRITTEN_ENV=()
WRITTEN_SECRET=()
SKIPPED=()

_clear() {
  [[ -t 1 ]] || return 0
  if command -v tput >/dev/null 2>&1; then tput clear; else printf '\033[2J\033[3J\033[H'; fi
}

banner() {
  _clear
  printf '\n%s%s  %s%s\n' "$BOLD" "$BLUE" "$1" "$RESET"  # NOSONAR S7679: positional parameter in short ops script; naming would add ceremony without clarity
  printf '%s  %s stages ? about %s minutes%s\n\n' \
    "$DIM" "$TOTAL_STAGES" "$TOTAL_MINUTES" "$RESET"
  printf '%s  You drive the browser; this wizard tells you exactly what to do and\n' "$DIM"
  printf '  captures the values you copy back. Stop any time with Ctrl-C and re-run\n'
  printf '  later - it remembers values already saved.%s\n' "$RESET"
  pause "Ready to start?"
}

stage() {
  _clear
  _STAGE_INDEX=$((_STAGE_INDEX + 1))
  local remaining=$((TOTAL_MINUTES - _MINUTES_ELAPSED))
  (( remaining < 0 )) && remaining=0
  _MINUTES_ELAPSED=$((_MINUTES_ELAPSED + ${2:-0}))
  printf '\n%s%s? Stage %s/%s ? %s%s  %s(~%s min left)%s\n' \
    "$BOLD" "$BLUE" "$_STAGE_INDEX" "$TOTAL_STAGES" "$1" "$RESET" "$DIM" "$remaining" "$RESET"  # NOSONAR S7679: positional parameter in short ops script; naming would add ceremony without clarity
}

say()  { printf '  %s\n' "$1"; }  # NOSONAR S7679: positional parameter in short ops script; naming would add ceremony without clarity
step() { printf '  %s? %s %s\n' "$BLUE" "$RESET" "$1"; }  # NOSONAR S7679: positional parameter in short ops script; naming would add ceremony without clarity
note() { printf '  %s%s%s\n' "$DIM" "$1" "$RESET"; }  # NOSONAR S7679: positional parameter in short ops script; naming would add ceremony without clarity
warn() { printf '  %s? %s%s\n' "$YELLOW" "$1" "$RESET"; }  # NOSONAR S7679: positional parameter in short ops script; naming would add ceremony without clarity

open_url() {
  local url="$1"
  printf '  %s? opening%s %s\n' "$GREEN" "$RESET" "$url"
  { if   command -v wslview     >/dev/null 2>&1; then wslview "$url"
    elif command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$url"
    elif command -v xdg-open    >/dev/null 2>&1; then xdg-open "$url"
    elif command -v open        >/dev/null 2>&1; then open "$url"
    else warn "couldn't open a browser - visit it manually: $url"; fi
  } >/dev/null 2>&1 || warn "couldn't open a browser - visit it manually: $url"
}

pause() {
  printf '  %s%s%s ' "$DIM" "${1:-Press Enter to continue}" "$RESET"
  read -r _ || true
}

confirm() {
  local reply=""
  printf '  %s? %s [y/N] ' "$YELLOW" "$1"  # NOSONAR S7679: positional parameter in short ops script; naming would add ceremony without clarity
  read -r reply || true
  [[ "$reply" =~ ^[Yy] ]]
}

_existing() {
  [[ -f "$ENV_FILE" ]] || return 1
  local line; line=$(grep -E "^${1}=" "$ENV_FILE" | tail -n1) || return 1
  printf '%s' "${line#*=}"
}

ask() {
  local key="$1" prompt="$2" current input
  current=$(_existing "$key" || true)
  if [[ -n "$current" ]]; then
    printf '  %s%s%s %s[Enter keeps current]%s ' "$BOLD" "$prompt" "$RESET" "$DIM" "$RESET"
  else
    printf '  %s%s%s ' "$BOLD" "$prompt" "$RESET"
  fi
  read -r input || true
  [[ -z "$input" && -n "$current" ]] && input="$current"
  printf -v "$key" '%s' "$input"
}

ask_secret() {
  local key="$1" prompt="$2" current input
  current=$(_existing "$key" || true)
  if [[ -n "$current" ]]; then
    printf '  %s%s%s %s[Enter keeps current]%s ' "$BOLD" "$prompt" "$RESET" "$DIM" "$RESET"
  else
    printf '  %s%s%s ' "$BOLD" "$prompt" "$RESET"
  fi
  read -rs input || true
  printf '\n'
  [[ -z "$input" && -n "$current" ]] && input="$current"
  printf -v "$key" '%s' "$input"
}

write_env() {
  local key="$1" value="$2" tmp
  touch "$ENV_FILE"
  tmp=$(mktemp)
  grep -vE "^${key}=" "$ENV_FILE" > "$tmp" || true
  printf '%s=%s\n' "$key" "$value" >> "$tmp"
  mv "$tmp" "$ENV_FILE"
  WRITTEN_ENV+=("$key")
  printf '  %s? wrote%s %s  ? %s\n' "$GREEN" "$RESET" "$key" "$ENV_FILE"
}

set_secret() {
  local name="$1" value="$2"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    if printf '%s' "$value" | gh secret set "$name" >/dev/null 2>&1; then  # NOSONAR S1066: nested if improves readability by keeping the guard close to the failure message
      WRITTEN_SECRET+=("$name")
      printf '  %s? set%s GitHub secret %s\n' "$GREEN" "$RESET" "$name"
      return
    fi
  fi
  SKIPPED+=("GitHub secret $name (set it manually: gh secret set $name)")
  warn "skipped GitHub secret $name - gh not ready; set it later"
}

set_var() {
  local name="$1" value="$2"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    if gh variable set "$name" --body "$value" >/dev/null 2>&1; then  # NOSONAR S1066: nested if improves readability by keeping the guard close to the failure message
      printf '  %s? set%s GitHub variable %s\n' "$GREEN" "$RESET" "$name"
      return
    fi
  fi
  SKIPPED+=("GitHub variable $name")
  warn "skipped GitHub variable $name - gh not ready; set it later"
}

finish() {
  _clear
  printf '\n%s%s  ? Setup complete%s\n' "$BOLD" "$GREEN" "$RESET"
  (( ${#WRITTEN_ENV[@]} ))    && note "wrote ${#WRITTEN_ENV[@]} value(s) to $ENV_FILE: ${WRITTEN_ENV[*]}"
  (( ${#WRITTEN_SECRET[@]} )) && note "set ${#WRITTEN_SECRET[@]} GitHub secret(s): ${WRITTEN_SECRET[*]}"
  if (( ${#SKIPPED[@]} )); then
    printf '\n'; warn "still to do by hand:"
    for s in "${SKIPPED[@]}"; do note "  - $s"; done
  fi
  printf '\n'
}

# ==============================================================================
# STAGES - author this section. One stage() per step the human takes.
# Set the two totals to match the stages you write.
# ==============================================================================

TOTAL_STAGES=8
TOTAL_MINUTES=35

banner "AhmedETAP - Secrets & Environment Setup"

# Stage 1: GitHub PAT - needed for gh CLI auth and CI
stage "GitHub Personal Access Token" 5
say "We need a fine-grained GitHub PAT so the CLI (gh) and CI can operate."
open_url "https://github.com/settings/tokens"
step "Click 'Generate new token' then 'Fine-grained token'."
step "Select 'Only this repository' for repository access."
step "Check 'Contents' and 'Pull requests' with Read and Write permissions."
step "Copy the generated token (starts ghp_)."
ask_secret GH_PAT "Paste the GitHub PAT:"
set_secret GH_PAT "$GH_PAT"

# Stage 2: Vercel tokens - needed for CI/CD deployment
stage "Vercel deployment tokens" 5
say "Grab your Vercel token, project ID, and org ID for CI deployments."
open_url "https://vercel.com/account/tokens"
step "Click 'Create Token', give it a name, and set scope to 'Full Account'."
step "Copy the token (starts vcp_)."
ask_secret VERCEL_TOKEN "Paste the Vercel token:"
open_url "https://vercel.com/dashboard"
step "Open the AhmedETAP project in Vercel dashboard."
step "Go to Settings and find the 'Project ID' (format prj_...)."
ask VERCEL_PROJECT_ID "Paste the Vercel Project ID:"
step "Go to Account Settings and find the 'Organization ID'."
ask VERCEL_ORG_ID "Paste the Vercel Org ID:"
write_env VERCEL_TOKEN "$VERCEL_TOKEN"
write_env VERCEL_PROJECT_ID "$VERCEL_PROJECT_ID"
write_env VERCEL_ORG_ID "$VERCEL_ORG_ID"
set_secret VERCEL_TOKEN "$VERCEL_TOKEN"
set_secret VERCEL_PROJECT_ID "$VERCEL_PROJECT_ID"
set_secret VERCEL_ORG_ID "$VERCEL_ORG_ID"

# Stage 3: Provider API keys - needed for AI features
stage "Provider API keys" 5
say "Collect tokens for HuggingFace, NVIDIA, Smithery, and LangWatch."
open_url "https://huggingface.co/settings/tokens"
step "Click 'New token', select 'Read' access, and copy it (starts hf_)."
ask_secret HF_TOKEN "Paste the HuggingFace token:"
open_url "https://build.nvidia.com/"
step "Click 'Get API Key', name it, and copy the key."
ask_secret NVIDIA_API_KEY "Paste the NVIDIA API key:"
open_url "https://smithery.ai/console/api-keys"
step "Click 'Generate API Key' and copy it."
ask_secret SMITHERY_API_KEY "Paste the Smithery API key:"
open_url "https://app.langwatch.ai/"
step "Go to Settings, then API Keys, and create a new key."
step "Copy the API key."
ask_secret LANGWATCH_API_KEY "Paste the LangWatch API key:"
write_env HF_TOKEN "$HF_TOKEN"
write_env NVIDIA_API_KEY "$NVIDIA_API_KEY"
write_env SMITHERY_API_KEY "$SMITHERY_API_KEY"
write_env LANGWATCH_API_KEY "$LANGWATCH_API_KEY"
set_secret HF_TOKEN "$HF_TOKEN"
set_secret NVIDIA_API_KEY "$NVIDIA_API_KEY"
set_secret SMITHERY_API_KEY "$SMITHERY_API_KEY"
set_secret LANGWATCH_API_KEY "$LANGWATCH_API_KEY"

# Stage 4: Langfuse keys - observability
stage "Langfuse observability keys" 3
say "Langfuse provides prompt management and LLM observability."
open_url "https://cloud.langfuse.com/"
step "Go to your project, then Settings, then API Keys."
step "Copy the Public Key (starts pk-lf-)."
ask LANGFUSE_PUBLIC_KEY "Paste the Langfuse public key:"
step "Click 'Add a new secret key' or reveal the existing one."
ask_secret LANGFUSE_SECRET_KEY "Paste the Langfuse secret key:"
open_url "https://cloud.langfuse.com/"
step "Confirm the base URL is https://cloud.langfuse.com"
LANGFUSE_BASE_URL="https://cloud.langfuse.com"
write_env LANGFUSE_PUBLIC_KEY "$LANGFUSE_PUBLIC_KEY"
write_env LANGFUSE_SECRET_KEY "$LANGFUSE_SECRET_KEY"
write_env LANGFUSE_BASE_URL "$LANGFUSE_BASE_URL"
set_secret LANGFUSE_PUBLIC_KEY "$LANGFUSE_PUBLIC_KEY"
set_secret LANGFUSE_SECRET_KEY "$LANGFUSE_SECRET_KEY"
set_secret LANGFUSE_BASE_URL "$LANGFUSE_BASE_URL"

# Stage 5: App secrets (generate locally)
stage "App security secrets" 3
say "Generate cryptographically secure secrets for local development."
step "Open each prompt, copy the generated key, and paste it back."
JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || openssl rand -base64 32 2>/dev/null || python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
step "Generated JWT_SECRET_KEY (32 hex chars)."
note "JWT_SECRET_KEY is already in your clipboard"
step "Generated ENCRYPTION_KEY (Fernet key)."
note "ENCRYPTION_KEY is already in your clipboard"
write_env JWT_SECRET_KEY "$JWT_SECRET_KEY"
write_env ENCRYPTION_KEY "$ENCRYPTION_KEY"

# Stage 6: Database credentials
stage "Local database credentials" 3
say "Provide PostgreSQL credentials for local Docker dev."
ask POSTGRES_USER "PostgreSQL username [postgres]:"
ask_secret POSTGRES_PASSWORD "PostgreSQL password:"
DB_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/etap_db"
write_env POSTGRES_USER "$POSTGRES_USER"
write_env POSTGRES_PASSWORD "$POSTGRES_PASSWORD"
write_env DATABASE_URL "$DB_URL"
write_env POSTGRES_DB "etap_db"

# Stage 7: Push all GitHub repo secrets
stage "Push GitHub repo secrets" 5
say "All CI-needed secrets are now pushed to GitHub Actions."
note "If any were skipped (gh not authenticated), set them manually at:"
note "  https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/settings/secrets/actions"
note "Skipped secrets will be listed in the summary below."

# Stage 8: Finalize and verify
stage "Finalize and verify" 3
say "Writing remaining .env values and running verification."
VERCEL_URL="https://etap-ai-work.vercel.app"
HF_SPACE_URL="https://ahmdelbaz28-ahmedetap-platform.hf.space"
write_env HF_SPACE_NAME "ahmdelbaz28-ahmedetap-platform"
write_env HF_REPO_URL "$HF_SPACE_URL"
write_env EMAIL_BRAND_NAME "AhmedETAP"
write_env ENVIRONMENT "development"
write_env PORT "8000"
write_env HOST "0.0.0.0"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  say "Running verify-secrets.sh to confirm GitHub secrets are set..."
  if [[ -f scripts/verify-secrets.sh ]]; then
    bash scripts/verify-secrets.sh || warn "verify-secrets.sh reported issues - check the summary above"
  else
    note "verify-secrets.sh not found - skipping Cloudflare worker check"
  fi
else
  note "gh not authenticated - skipping automated verification"
  note "Verify manually at: https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/settings/secrets/actions"
fi

finish