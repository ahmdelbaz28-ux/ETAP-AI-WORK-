# PowerShell script to run the ArcGIS Pro documentation indexing workflow
# and display the workflow configuration

Write-Host "==========================================" -ForegroundColor Green
Write-Host "ArcGIS Pro Documentation Indexing Workflow" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

# Load the workflow configuration
$workflowConfig = Get-Content -Path ".\arcgis_pro_indexing_workflow.json" -Raw | ConvertFrom-Json

Write-Host "`nWorkflow Name: $($workflowConfig.workflow_name)" -ForegroundColor Cyan
Write-Host "Description: $($workflowConfig.description)" -ForegroundColor Cyan
Write-Host "Schedule: $($workflowConfig.schedule)" -ForegroundColor Cyan

Write-Host "`nWorkflow Steps:" -ForegroundColor Yellow
foreach ($step in $workflowConfig.steps) {
    Write-Host "  - $($step.name) [$($step.type)]" -ForegroundColor White
    if ($step.options) {
        foreach ($key in $step.options.PSObject.Properties.Name) {
            $value = $step.options[$key]
            if ($value -is [hashtable] -or $value -is [System.Object[]]) {
                Write-Host "    $key: $($value | ConvertTo-Json -Depth 3)" -ForegroundColor Gray
            } else {
                Write-Host "    $key: $value" -ForegroundColor Gray
            }
        }
    }
}

# Check if Python is available
Write-Host "`nChecking for Python..." -ForegroundColor Magenta
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $pythonCmd) {
    Write-Host "Python not found! Please install Python 3.13+ to run the workflow." -ForegroundColor Red
    exit 1
}

Write-Host "Python found: $($pythonCmd.Path)" -ForegroundColor Green

# Check if required Python packages are installed
Write-Host "`nChecking for required Python packages..." -ForegroundColor Magenta
$requiredPackages = @("requests", "beautifulsoup4", "sentence-transformers", "elasticsearch")

foreach ($package in $requiredPackages) {
    $null = python -c "import $package; print('OK')" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ $package" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $package (not installed)" -ForegroundColor Red
    }
}

# Run the workflow
Write-Host "`nTo run the workflow, execute:" -ForegroundColor Green
Write-Host "  python .\arcgis_pro_indexing_workflow.py" -ForegroundColor White

# Show how to schedule the workflow
Write-Host "`nTo schedule this workflow daily at 3 AM, you could add to crontab (Linux/Mac):" -ForegroundColor Yellow
Write-Host "  0 3 * * * cd /path/to/project && python arcgis_pro_indexing_workflow.py" -ForegroundColor White

Write-Host "`nOn Windows, you could use Task Scheduler with this command:" -ForegroundColor Yellow
Write-Host "  powershell.exe -ExecutionPolicy Bypass -File `"$(Resolve-Path .\run_arcgis_workflow.ps1)`"" -ForegroundColor White

Write-Host "`n==========================================" -ForegroundColor Green
Write-Host "Workflow configuration loaded successfully!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green