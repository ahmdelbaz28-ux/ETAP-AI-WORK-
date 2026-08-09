#!/usr/bin/env pwsh
# =============================================================================
# AhmedETAP — GitHub Secrets Setup Script (PowerShell)
# Run this ONCE to register all secrets in the GitHub repository.
# Requires: GitHub CLI (gh) installed and authenticated.
# =============================================================================
# Usage:
#   .\scripts\setup_github_secrets.ps1
#   Or with custom values:
#   .\scripts\setup_github_secrets.ps1 -Repo "ahmdelbaz28-ux/ETAP-AI-WORK-"
# =============================================================================

param(
    [string]$Repo = "ahmdelbaz28-ux/ETAP-AI-WORK-"
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  AhmedETAP — GitHub Secrets Configuration" -ForegroundColor Cyan
Write-Host "  Repository: $Repo" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ─── Check GitHub CLI ────────────────────────────────────────────────────────
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "❌ GitHub CLI (gh) not found." -ForegroundColor Red
    Write-Host "   Install from: https://cli.github.com/" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ GitHub CLI found" -ForegroundColor Green

# ─── Authenticate check ───────────────────────────────────────────────────────
$authStatus = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Not authenticated. Running 'gh auth login'..." -ForegroundColor Yellow
    gh auth login --with-token <<< "ghp_YOUR_GITHUB_PAT_HERE"
}

# ─── Define all secrets ───────────────────────────────────────────────────────
$secrets = @{
    # === Hugging Face ===
    "HF_TOKEN"                = "hf_YOUR_HUGGINGFACE_TOKEN_HERE"

    # === LangWatch ===
    "LANGWATCH_API_KEY"       = "sk-lw-YOUR_LANGWATCH_KEY_HERE"

    # === Smithery MCP ===
    "SMITHERY_API_KEY"        = "YOUR_SMITHERY_API_KEY_HERE"

    # === App Security (generate new values for production!) ===
    "JWT_SECRET_KEY"          = "etap-production-jwt-secret-change-this-in-prod"
    "ENCRYPTION_KEY"          = "etap-production-enc-key-change-in-prod"

    # === Engineering Service ===
    "ENGINEERING_SERVICE_API_KEY" = "etap-internal-service-key-change-in-prod"

    # === Database (update for production PostgreSQL) ===
    "DATABASE_URL"            = "sqlite+aiosqlite:///./etap.db"

    # === Redis ===
    "REDIS_URL"               = "redis://localhost:6379/0"
}

Write-Host "📋 Secrets to configure: $($secrets.Count)" -ForegroundColor Cyan
Write-Host ""

$success = 0
$failed  = 0

foreach ($name in $secrets.Keys) {
    $value = $secrets[$name]
    try {
        $value | gh secret set $name --repo $Repo 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ $name" -ForegroundColor Green
            $success++
        } else {
            Write-Host "  ❌ $name (failed)" -ForegroundColor Red
            $failed++
        }
    } catch {
        Write-Host "  ❌ $name — Error: $_" -ForegroundColor Red
        $failed++
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Results: $success succeeded, $failed failed" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Yellow" })
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if ($success -gt 0) {
    Write-Host "🔍 Verify secrets at:" -ForegroundColor Cyan
    Write-Host "   https://github.com/$Repo/settings/secrets/actions" -ForegroundColor Blue
}

Write-Host ""
Write-Host "📋 Next Steps:" -ForegroundColor Cyan
Write-Host "   1. Update JWT_SECRET_KEY to a real random value for production" -ForegroundColor White
Write-Host "   2. Add your OpenAI/LLM keys if you have them" -ForegroundColor White
Write-Host "   3. Trigger CI/CD: git push origin main" -ForegroundColor White
Write-Host "   4. Monitor LangWatch: https://app.langwatch.ai/" -ForegroundColor White
Write-Host "   5. Monitor Smithery:  https://smithery.ai/console/api-keys" -ForegroundColor White
Write-Host ""
