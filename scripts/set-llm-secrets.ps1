# =============================================================================
# ETAP AI Platform — LLM API Secret Setup (PowerShell)
# =============================================================================
# Sets LLM provider and observability API keys as encrypted Cloudflare Worker secrets.
#
# Usage:
#   .\scripts\set-llm-secrets.ps1
#
# Prerequisites:
#   1. You have a Cloudflare account
#   2. You have installed wrangler: npm install -g wrangler
#   3. You have run: npx wrangler login
#   4. You have the API keys ready (see .env.example for provider links)
#
# Environment:
#   $env:WRANGLER_WORKER_NAME  - Override the Worker name (default: auto-detected)
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

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectDir = Resolve-Path (Join-Path $ScriptDir "..")

Set-Location $ProjectDir

function Write-Header {
    Write-Host ""  # NOSONAR — S8677: Write-Host in Show verb function; intentional
    Write-Host "╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan  # NOSONAR — S8677: Write-Host in Show verb function; intentional
    Write-Host "║           ETAP AI Platform — API Secret Setup                               ║" -ForegroundColor Cyan  # NOSONAR — S8677: Write-Host in Show verb function; intentional
    Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan  # NOSONAR — S8677: Write-Host in Show verb function; intentional
    Write-Host ""  # NOSONAR — S8677: Write-Host in Show verb function; intentional
}

function Write-Success { param([string]$Message) Write-Host "✅ $Message" -ForegroundColor Green }  # NOSONAR — S8677: Write-Host in Show verb function; intentional
function Write-ErrorMsg { param([string]$Message) Write-Host "❌ $Message" -ForegroundColor Red }  # NOSONAR — S8677: Write-Host in Show verb function; intentional
function Write-Warn { param([string]$Message) Write-Host "⚠️ $Message" -ForegroundColor Yellow }  # NOSONAR — S8677: Write-Host in Show verb function; intentional
function Write-Info { param([string]$Message) Write-Host "ℹ️ $Message" -ForegroundColor Blue }  # NOSONAR — S8677: Write-Host in Show verb function; intentional

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

# Check if npx and wrangler are available
function Test-Wrangler {
    try {
        $null = Get-Command npx -ErrorAction Stop
    } catch {
        Write-ErrorMsg "npx is not installed. Install Node.js first: https://nodejs.org/"
        exit 1
    }

    try {
        $null = npx wrangler --version 2>$null
    } catch {
        Write-ErrorMsg "wrangler is not installed. Install it: npm install -g wrangler"
        exit 1
    }

    Write-Success "wrangler is available"
}

# Check if user is logged in to Cloudflare
function Test-CloudflareLogin {
    Write-Info "Checking Cloudflare authentication..."

    try {
        $whoami = npx wrangler whoami 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $whoami) { throw "Not authenticated" }
    } catch {
        Write-ErrorMsg "You are not logged in to Cloudflare."
        Write-Host ""  # NOSONAR — S8677: Write-Host in Show verb function; intentional
        Write-Info "Run: npx wrangler login"
        Write-Host ""  # NOSONAR — S8677: Write-Host in Show verb function; intentional
        Write-Info "This will open a browser window to authenticate with Cloudflare."
        Write-Info "After logging in, run this script again."
        exit 1
    }

    Write-Success "Authenticated with Cloudflare"
}

# Prompt for a secret (hidden input)
function Prompt-Secret {
    param([string]$Name, [string]$Description)
    Write-Host ""  # NOSONAR — S8677: Write-Host in Show verb function; intentional
    Write-Info "$Name"
    Write-Host "   $Description"  # NOSONAR — S8677: Write-Host in Show verb function; intentional
    Write-Host ""  # NOSONAR — S8677: Write-Host in Show verb function; intentional
    $secure = Read-Host "   Enter $Name (or press Enter to skip)" -AsSecureString
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    return $plain
}

# Set a single secret via wrangler
function Set-WorkerSecret {
    param([string]$Name, [string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        Write-Warn "Skipping $Name — no value provided"
        return
    }

    Write-Info "Setting $Name on Worker '$WorkerName'..."
    try {
        $Value | npx wrangler secret put "$Name" --name "$WorkerName" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "$Name set successfully"
        } else {
            Write-ErrorMsg "Failed to set $Name — check wrangler output above for details"
        }
    } catch {
        Write-ErrorMsg "Failed to set $Name`: $_"
    }
}

# Main
Write-Header
Test-Wrangler
Test-CloudflareLogin

Write-Host ""
Write-Host "───────────────────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Info "You will be prompted for 5 API keys (4 LLM + 1 observability)."
Write-Info "If you don't have a key yet, press Enter to skip and set it later."
Write-Info "These keys are stored as encrypted Cloudflare Worker secrets."
Write-Info "For local development, set them in your .env file separately."
Write-Info "See .env.example for links to obtain each key."
Write-Host "───────────────────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Info "Target Worker: $WorkerName"
Write-Host ""

$OpenAIKey = Prompt-Secret -Name "OPENAI_API_KEY" -Description "Primary LLM provider (GPT-4 / GPT-4o). Get one at: https://platform.openai.com/api-keys"
$QwenKey   = Prompt-Secret -Name "QWEN_API_KEY"   -Description "Fallback LLM provider (Alibaba Qwen). Get one at: https://dashscope.console.aliyun.com/"
$GLMKey    = Prompt-Secret -Name "GLM_API_KEY"    -Description "Fallback LLM provider (Zhipu GLM-4). Get one at: https://open.bigmodel.cn/"

$NvidiaKey = Prompt-Secret -Name "NVIDIA_API_KEY" -Description "Fourth LLM provider (NVIDIA NIM). Get one at: https://build.nvidia.com/"

$LangWatchKey = Prompt-Secret -Name "LANGWATCH_API_KEY" -Description "Agent observability & prompt management. Get one at: https://app.langwatch.ai/"

Write-Host ""
Write-Host "───────────────────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Info "Setting secrets on Cloudflare Workers..."
Write-Host "───────────────────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

Set-WorkerSecret -Name "OPENAI_API_KEY"     -Value $OpenAIKey
Set-WorkerSecret -Name "QWEN_API_KEY"       -Value $QwenKey
Set-WorkerSecret -Name "GLM_API_KEY"        -Value $GLMKey
Set-WorkerSecret -Name "NVIDIA_API_KEY"     -Value $NvidiaKey
Set-WorkerSecret -Name "LANGWATCH_API_KEY"  -Value $LangWatchKey

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Success "API secret setup complete!"
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Info "Next steps:"
Write-Host "   1. Verify secrets are set:   .\scripts\verify-secrets.ps1"
Write-Host "   2. Deploy the worker:         npx wrangler deploy"
Write-Host "   3. Test a provider:           curl -H 'x-api-key: YOUR_KEY'"
Write-Host "                                 https://ahmed-etap.ahmdelbaz28.workers.dev/api/v1/providers"
Write-Host ""
