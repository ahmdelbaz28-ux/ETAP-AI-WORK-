# ETAP AI Platform - PowerShell Quick Start Script
# This script sets up and starts the platform on Windows

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "ETAP AI Engineering Platform - Quick Start" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is installed
try {
    $dockerVersion = docker --version
    Write-Host "✓ Docker found: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker is not installed. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if .env file exists
if (-Not (Test-Path ".env")) {
    Write-Host "ℹ Creating .env file from template..." -ForegroundColor Blue
    Copy-Item ".env.example" ".env"
    Write-Host "✓ .env file created. Please edit it with your configuration." -ForegroundColor Green
}

# Build and start services
Write-Host "ℹ Building Docker images..." -ForegroundColor Blue
docker-compose build

Write-Host "ℹ Starting services..." -ForegroundColor Blue
docker-compose up -d

# Optionally start the Engineering Service (Python FastAPI) under the
# `engineering` profile. Set START_ENGINEERING_SERVICE=1 to opt in non-interactively.
$startEng = $env:START_ENGINEERING_SERVICE -eq '1'
if (-not $startEng) {
    $ans = Read-Host "Start the Engineering Service too? [y/N]"
    $startEng = ($ans -eq 'y' -or $ans -eq 'Y')
}
if ($startEng) {
    Write-Host "ℹ Starting Engineering Service (profile: engineering)..." -ForegroundColor Blue
    docker-compose --profile engineering up -d engineering-service
    Write-Host "ℹ Waiting for Engineering Service /health..." -ForegroundColor Blue
    for ($i = 0; $i -lt 15; $i++) {
        try {
            $r = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) {
                Write-Host "✓ Engineering Service is running and healthy (port 8000)" -ForegroundColor Green
                break
            }
        } catch { Start-Sleep -Seconds 1 }
    }
}

# Wait for services to be ready
Write-Host "ℹ Waiting for services to start..." -ForegroundColor Blue
Start-Sleep -Seconds 15

# Check health
Write-Host "ℹ Checking service health..." -ForegroundColor Blue
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3000/health" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ Platform is running and healthy!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Access the platform at: http://localhost:3000" -ForegroundColor Cyan
        Write-Host "API documentation: http://localhost:3000/docs" -ForegroundColor Cyan
        Write-Host "Engineering Service: http://localhost:8000 (if started)" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Useful commands:" -ForegroundColor Yellow
        Write-Host "  View logs:     docker-compose logs -f" -ForegroundColor White
        Write-Host "  Stop services: docker-compose down" -ForegroundColor White
        Write-Host "  Restart:       docker-compose restart" -ForegroundColor White
        Write-Host ""
        Write-Host "To start the Engineering Service later:" -ForegroundColor Yellow
        Write-Host "  docker compose --profile engineering up -d" -ForegroundColor White
    }
} catch {
    Write-Host "✗ Platform may not be ready yet. Check logs:" -ForegroundColor Red
    Write-Host "  docker-compose logs -f" -ForegroundColor White
}

Write-Host ""
Write-Host "✓ Setup complete!" -ForegroundColor Green
