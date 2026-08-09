# =============================================================================
# ETAP AI Platform — Mastra Database Backup Script (Windows)
# =============================================================================
# Usage: .\scripts\backup-mastra-db.ps1
# Frequency: Hourly (via Task Scheduler)
# Retention: 7 days (168 copies)
# =============================================================================

$ErrorActionPreference = "Stop"

$BackupDir = "./backups/mastra.db"
$Timestamp = Get-Date -Format "yyyy-MM-dd-HH-mm-ss"
$DbFile = "./mastra.db"

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

if (-not (Test-Path $DbFile)) {
    Write-Host "[WARN] Database file not found: $DbFile"
    exit 0
}

Write-Host "[INFO] Backing up $DbFile..."
$BackupFile = "$BackupDir\mastra.db.$Timestamp.bak"
Copy-Item $DbFile $BackupFile

# Compress backup
Compress-Archive -Path $BackupFile -DestinationPath "$BackupFile.zip" -Force
Remove-Item $BackupFile

# Retain only last 168 backups (7 days × 24 hours)
$Backups = Get-ChildItem "$BackupDir\*.bak.zip" | Sort-Object LastWriteTime -Descending
if ($Backups.Count -gt 168) {
    $Backups | Select-Object -Skip 168 | Remove-Item -Force
}

Write-Host "[INFO] Backup complete: $BackupFile.zip"
Write-Host "[INFO] Total backups: $(($Backups | Measure-Object).Count)"
