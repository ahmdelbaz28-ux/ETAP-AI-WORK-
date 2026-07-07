#!/usr/bin/env bash
# =============================================================================
# rotate-credentials.sh — Helper for the 2026-07-08 security incident
# =============================================================================
# Opens the credential-rotation page for every service that was exposed in
# plain chat on 2026-07-08. Run this script, rotate each credential, then
# update the Vercel env vars with the new values (see
# SECURITY_INCIDENT_2026-07-08.md for the env var key list).
#
# Usage:
#   bash scripts/rotate-credentials.sh        # macOS / Linux (xdg-open)
#   bash scripts/rotatecredentials.sh wsl     # Windows Subsystem for Linux
# =============================================================================
set -euo pipefail

MODE="${1:-auto}"

open_url() {
  local url="$1"
  case "$MODE" in
    wsl)
      cmd.exe /c start "" "$url" 2>/dev/null || true
      ;;
    mac|darwin)
      open "$url" 2>/dev/null || true
      ;;
    auto|linux|*)
      if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" 2>/dev/null || true
      elif command -v sensible-browser >/dev/null 2>&1; then
        sensible-browser "$url" 2>/dev/null || true
      else
        echo "  (could not auto-open: $url)"
      fi
      ;;
  esac
  echo "  ✓ $url"
  sleep 0.5
}

echo "================================================================"
echo " Opening credential rotation pages for the 2026-07-08 incident"
echo " Mode: $MODE"
echo "================================================================"
echo
echo "[1/7] GitHub PAT"
open_url "https://github.com/settings/tokens"

echo
echo "[2/7] Vercel token"
open_url "https://vercel.com/account/tokens"

echo
echo "[3/7] HuggingFace token"
open_url "https://huggingface.co/settings/tokens"

echo
echo "[4/7] Supabase project API keys"
echo "  (Project: ovjttnsvwrmbvwecxbsq)"
open_url "https://supabase.com/dashboard/project/ovjttnsvwrmbvwecxbsq/settings/api"

echo
echo "[5/7] Langfuse API keys"
open_url "https://cloud.langfuse.com/settings"

echo
echo "[6/7] LangWatch API keys"
open_url "https://app.langwatch.ai/settings/api-keys"

echo
echo "[7/7] Smithery API keys"
open_url "https://smithery.ai/console/api-keys"

echo
echo "================================================================"
echo " Next steps:"
echo "   1. Generate a fresh token/key on each service"
echo "   2. Revoke the OLD token/key on each service"
echo "   3. Update Vercel env vars with the new values:"
echo "      https://vercel.com/ahmdelbaz28-ux/etap-ai-work/settings/environment-variables"
echo "   4. Re-deploy the Vercel project to pick up the new values"
echo "   5. (If backend uses the keys) Update HF Space secrets at:"
echo "      https://huggingface.co/spaces/ahmdelbaz28/AhmedETAP-Platform/settings"
echo "================================================================"
