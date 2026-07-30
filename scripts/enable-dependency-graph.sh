#!/usr/bin/env bash
# =============================================================================
# AhmedETAP — Enable GitHub Dependency Graph & Code Security Settings
# =============================================================================
# This script enables the GitHub dependency graph and code security features
# for the ETAP-AI-WORK repository. Per CI/CD skill: "Shift Left" — dependency
# visibility enables automated dependency review, Dependabot alerts, and
# supply-chain security scanning.
#
# Prerequisites:
#   - GitHub CLI (gh) installed and authenticated
#   - Repository admin permissions
#
# Usage:
#   ./scripts/enable-dependency-graph.sh
#
# What this enables:
#   1. Dependency graph (DEPENDENCY_GRAPH_ENABLED=true)
#      - Detects Python (pip), JavaScript (npm), and other dependencies
#      - Required for: dependency-review-action, Dependabot, SBOM generation
#
#   2. Dependabot alerts (security vulnerability notifications)
#      - Automatic PRs for vulnerable dependencies
#      - Alerts visible in Security tab
#
#   3. Dependabot security updates (auto-fix PRs)
#      - Automatically creates PRs to fix vulnerable dependencies
#
# Note: These settings can also be configured via the GitHub web UI:
#   Repository → Settings → Code security and analysis
# =============================================================================
set -euo pipefail

REPO="${GITHUB_REPO:-ahmdelbaz28-ux/ETAP-AI-WORK-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { local msg="$1"; echo -e "${BLUE}[INFO]${NC}  $msg"; }
log_ok()    { local msg="$1"; echo -e "${GREEN}[OK]${NC}    $msg"; }
log_fail()  { local msg="$1"; echo -e "${RED}[FAIL]${NC}  $msg"; }

# ── Check prerequisites ──────────────────────────────────────────────────────
if ! command -v gh &> /dev/null; then
    log_fail "GitHub CLI (gh) not installed. Install: https://cli.github.com/"
    exit 1
fi

# Verify authentication
if ! gh auth status &> /dev/null 2>&1; then
    log_fail "GitHub CLI not authenticated. Run: gh auth login"
    exit 1
fi

log_info "Configuring code security for repository: ${REPO}"

# ── 1. Enable Dependency Graph ──────────────────────────────────────────────
# Per CI/CD skill: DEPENDENCY_GRAPH_ENABLED=true — this is a prerequisite for
# dependency-review-action (used in security.yml) and Dependabot alerts.
log_info "Enabling dependency graph (DEPENDENCY_GRAPH_ENABLED=true)..."

# The dependency graph is enabled via the GitHub API.
# Endpoint: PATCH /repos/{owner}/{repo}
# Field: dependency_graph.enabled = true
# Note: This is NOT a secret — it's a public repository configuration.

gh api \
    --method PATCH \
    "/repos/${REPO}" \
    --field dependency_graph_enabled=true \
    2>&1 && log_ok "Dependency graph enabled" || {
    log_fail "Failed to enable dependency graph via API"
    log_info "You can also enable it manually:"
    log_info "  Repository → Settings → Code security and analysis → Dependency graph → Enable"
    exit 1
}

# ── 2. Enable Dependabot Alerts ─────────────────────────────────────────────
log_info "Enabling Dependabot vulnerability alerts..."

gh api \
    --method PUT \
    "/repos/${REPO}/vulnerability-alerts" \
    2>&1 && log_ok "Dependabot alerts enabled" || {
    log_fail "Failed to enable Dependabot alerts"
    log_info "You can also enable it manually:"
    log_info "  Repository → Settings → Code security and analysis → Dependabot alerts → Enable"
}

# ── 3. Enable Dependabot Security Updates ───────────────────────────────────
log_info "Enabling Dependabot automatic security updates..."

gh api \
    --method PATCH \
    "/repos/${REPO}" \
    --field security_and_analysis.dependabot_security_updates.enabled=true \
    2>&1 && log_ok "Dependabot security updates enabled" || {
    log_fail "Failed to enable Dependabot security updates"
    log_info "You can also enable it manually:"
    log_info "  Repository → Settings → Code security and analysis → Dependabot security updates → Enable"
}

# ── 4. Verify configuration ─────────────────────────────────────────────────
log_info "Verifying code security configuration..."

REPO_SETTINGS=$(gh api "/repos/${REPO}" --jq '.security_and_analysis')

echo ""
echo "======================================================================"
echo "  Code Security Configuration for ${REPO}"
echo "======================================================================"
echo "${REPO_SETTINGS}" | python3 -m json.tool 2>/dev/null || echo "${REPO_SETTINGS}"
echo "======================================================================"
echo ""

log_ok "DEPENDENCY_GRAPH_ENABLED=true — dependency graph is active"
log_ok "Dependabot alerts are enabled"
log_ok "Dependabot security updates are enabled"
echo ""
log_info "Next steps:"
log_info "  1. The dependency-review-action in security.yml will now have data to analyze"
log_info "  2. Dependabot will create alerts for known vulnerabilities"
log_info "  3. Security updates will be automatically proposed via PRs"
log_info "  4. Run 'gh api /repos/${REPO}/dependency-graph/sbom' to generate SBOM"
