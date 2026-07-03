# =============================================================================
# Wire ENGINEERING_SERVICE_URL into the Cloudflare Worker (PowerShell)
# =============================================================================
# Usage:
#   .\scripts\set-engineering-service-url.ps1 -Url https://my-eng-svc.example.com [-ApiKey xxx]
#
# Interactive (prompts):
#   .\scripts\set-engineering-service-url.ps1
# =============================================================================
[CmdletBinding()]
param(
  [string]$Url,
  [string]$ApiKey,
  [string]$WorkerName = 'ahmed-etap',
  [string]$StagingName = 'ahmed-etap-staging'
)

$ErrorActionPreference = 'Stop'

if (-not $Url) {
  $Url = Read-Host 'Engineering Service public URL (e.g. https://eng-svc.example.com)'
}
if (-not $Url) { throw 'URL is required' }
$Url = $Url.TrimEnd('/')

if (-not $ApiKey) {
  $secure = Read-Host 'Optional ENGINEERING_SERVICE_API_KEY (Enter to skip)' -AsSecureString
  if ($secure) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  }
}

Write-Host '==========================================' -ForegroundColor Cyan
Write-Host ' Wiring Engineering Service into Worker' -ForegroundColor Cyan
Write-Host '==========================================' -ForegroundColor Cyan
Write-Host "URL:         $Url"
if ($ApiKey) { Write-Host 'API key:     ***set***' } else { Write-Host 'API key:     <not set>' }
Write-Host "Production:  $WorkerName"
Write-Host "Staging:     $StagingName"
Write-Host '==========================================' -ForegroundColor Cyan

function Set-WranglerSecret {
  param([string]$Name, [string]$Value, [string]$Target)
  Write-Host ""  # NOSONAR — S8677: Write-Host in Show verb function; intentional
  Write-Host "Setting $Name on $Target..."  # NOSONAR — S8677: Write-Host in Show verb function; intentional
  $Value | npx wrangler secret put $Name --name $Target
  if ($LASTEXITCODE -ne 0) { throw "wrangler secret put failed for $Name on $Target" }
}

Set-WranglerSecret -Name 'ENGINEERING_SERVICE_URL' -Value $Url -Target $WorkerName
if ($ApiKey) {
  Set-WranglerSecret -Name 'ENGINEERING_SERVICE_API_KEY' -Value $ApiKey -Target $WorkerName
}

Write-Host ""
Write-Host "Setting ENGINEERING_SERVICE_URL on staging Worker (best-effort)..."
try {
  Set-WranglerSecret -Name 'ENGINEERING_SERVICE_URL' -Value $Url -Target $StagingName
  if ($ApiKey) { Set-WranglerSecret -Name 'ENGINEERING_SERVICE_API_KEY' -Value $ApiKey -Target $StagingName }
} catch {
  Write-Warning "Staging Worker not reachable — skipped ($($_.Exception.Message))"
}

Write-Host ""
Write-Host "Verifying Worker /health..." -ForegroundColor Cyan
$verifyUrl = "https://$WorkerName.ahmdelbaz28.workers.dev/health"
Write-Host "  GET $verifyUrl"
try {
  $resp = Invoke-RestMethod -Uri $verifyUrl -Method Get -TimeoutSec 15
  $es = $resp.engineeringService
  Write-Host "  engineeringService.configured = $($es.configured)"
  Write-Host "  engineeringService.healthy    = $($es.healthy)"
  Write-Host "  engineeringService.latencyMs  = $($es.latencyMs)"
  if ($es.error) { Write-Host "  engineeringService.error      = $($es.error)" }
  if ($es.healthy) {
    Write-Host ""
    Write-Host "DONE — Worker reports engineeringService.healthy=true" -ForegroundColor Green
  } else {
    Write-Warning "Worker /health did NOT report engineeringService.healthy=true. See error above."
    exit 1
  }
} catch {
  Write-Warning "Could not reach Worker /health: $($_.Exception.Message)"
  exit 2
}
