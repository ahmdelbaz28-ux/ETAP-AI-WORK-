# =============================================================================
# ETAP AI Platform — Verify LLM Secrets (PowerShell)
# =============================================================================
# Checks that LLM API keys are set as Cloudflare Worker secrets.
#
# Usage:
#   .\scripts\verify-secrets.ps1
#
# Environment:
#   $env:WRANGLER_WORKER_NAME  - Override the Worker name (default: auto-detected)
# =============================================================================

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectDir = Resolve-Path (Join-Path $ScriptDir "..")

Set-Location $ProjectDir

# Detect Worker name: env var > wrangler.jsonc > fallback
function Get-WorkerName {
    if ($env:WRANGLER_WORKER_NAME) { return $env:WRANGLER_WORKER_NAME }
    $wranglerPath = Join-Path $ProjectDir "wrangler.jsonc"
    if (Test-Path $wranglerPath) {
        $content = Get-Content $wranglerPath -Raw
        if ($content -match '"name"\s*:\s*"([^"]+)"') { return $matches[1] }
    }
    return "ahmed-etap"
}

$WorkerName = Get-WorkerName

$Secrets = @("OPENAI_API_KEY", "QWEN_API_KEY", "GLM_API_KEY", "NVIDIA_API_KEY", "LANGWATCH_API_KEY")
$Missing = @()
$Found = @()

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           ETAP AI Platform — Secret Verification                            ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check wrangler
try {
    $null = npx wrangler --version 2>$null
} catch {
    Write-Host "❌ wrangler not available. Run: npm install -g wrangler" -ForegroundColor Red
    exit 1
}

# Check login
try {
    npx wrangler whoami 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Not logged in" }
} catch {
    Write-Host "❌ Not logged in. Run: npx wrangler login" -ForegroundColor Red
    exit 1
}

Write-Host "Worker: ${WorkerName}" -ForegroundColor Gray
Write-Host ""
Write-Host "Checking API key secrets on Cloudflare..." -ForegroundColor Gray
Write-Host ""

# Fetch secret list once
$secretList = npx wrangler secret list --name "${WorkerName}" 2>$null | Out-String

foreach ($secret in $Secrets) {
    if ($secretList -match """${secret}""") {
        Write-Host "✅ ${secret} — set" -ForegroundColor Green
        $Found += $secret
    } else {
        Write-Host "❌ ${secret} — not set" -ForegroundColor Red
        $Missing += $secret
    }
}

Write-Host ""

if ($Missing.Count -eq 0) {
    Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "All $($Secrets.Count) secrets are set." -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next: Deploy the worker with:" -ForegroundColor Gray
    Write-Host "  npx wrangler deploy" -ForegroundColor White
    exit 0
} else {
    Write-Host "───────────────────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
    Write-Host "$($Missing.Count) of $($Secrets.Count) secrets are missing." -ForegroundColor Yellow
    Write-Host "───────────────────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "Missing secrets:" -ForegroundColor Gray
    foreach ($m in $Missing) { Write-Host "  - ${m}" -ForegroundColor White }
    Write-Host ""
    Write-Host "Set missing secrets with:" -ForegroundColor Gray
    Write-Host "  .\scripts\set-llm-secrets.ps1" -ForegroundColor White
    exit 1
}
