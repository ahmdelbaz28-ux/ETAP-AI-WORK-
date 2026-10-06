# scripts/check_metadata.ps1 - Audit metadata frontmatter and TOC on major documentation files
$repoRoot = (Get-Item $PSScriptRoot).Parent.FullName

$majorFiles = @(
    "README.md",
    "README.ar.md",
    "QUICKSTART.md",
    "QUICKSTART.ar.md",
    "CONTRIBUTING.md",
    "CONTRIBUTING.ar.md",
    "ROADMAP.md",
    "SUPPORT.md",
    "SUPPORT.ar.md",
    "AGENTS.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    "docs/API_REFERENCE.md",
    "docs/API_QUICKREF.md",
    "docs/API_DOCUMENTATION.md",
    "docs/GLOSSARY.md",
    "docs/DOCUMENTATION_STANDARDS.md",
    "docs/STATUS.md",
    "docs/ARCHITECTURE.md",
    "docs/OPERATIONS_RUNBOOK.md",
    "docs/TROUBLESHOOTING_GUIDE.md",
    "docs/SECURITY_OPERATIONS_MANUAL.md",
    "docs/ENTERPRISE_CERTIFICATION_REPORT.md",
    "docs/STANDARDS_COMPLIANCE_MATRIX.md",
    "docs/TRUST_CHARTER.md",
    "docs/VALIDATION_REPORT.md",
    "docs/TUTORIALS/README.md",
    "docs/TUTORIALS/01_load_flow_short_circuit_protection.md",
    "docs/TUTORIALS/02_motor_starting_voltage_drop.md",
    "docs/TUTORIALS/03_arc_flash_hazard_evaluation.md"
)

$frontmatterRegex = '(?s)^---\s*\r?\n(.*?)\r?\n---\s*\r?\n'
$totalErrors = 0
$totalChecked = 0

Write-Host "Auditing $($majorFiles.Count) major documentation files for metadata & style standards..." -ForegroundColor Cyan

foreach ($rel in $majorFiles) {
    $fullPath = Join-Path $repoRoot ($rel.Replace('/', '\'))
    $totalChecked++

    if (-not (Test-Path $fullPath)) {
        Write-Host "   Missing file: $rel" -ForegroundColor Red
        $totalErrors++
        continue
    }

    $content = Get-Content -Path $fullPath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    $fileErrors = @()

    # Frontmatter check
    if ($content -match $frontmatterRegex) {
        $yamlText = $matches[1]
        $fields = @{}
        foreach ($line in ($yamlText -split '\r?\n')) {
            if ($line -match '^\s*([^#:][^:]*)\s*:\s*(.*)$') {
                $k = $matches[1].Trim()
                $v = $matches[2].Trim().Trim('"', "'")
                $fields[$k] = $v
            }
        }

        foreach ($req in @("title", "version", "last_updated", "maintainer")) {
            if (-not $fields.ContainsKey($req) -or [string]::IsNullOrWhiteSpace($fields[$req])) {
                $fileErrors += "Frontmatter missing required field '$req'"
            }
        }
        if ($fields.ContainsKey("last_updated") -and ($fields["last_updated"] -notmatch '^\d{4}-\d{2}-\d{2}$')) {
            $fileErrors += "Invalid date format for last_updated: '$($fields['last_updated'])' (expected YYYY-MM-DD)"
        }
    } else {
        $fileErrors += "Missing YAML frontmatter block (--- ... ---)"
    }

    # Word count and Table of Contents check
    $words = ($content -split '\s+').Count
    if ($words -gt 800) {
        $hasToc = ($content -match '(?i)Table of Contents') -or ($content -match 'المحتويات') -or ($content -match '\[Table of Contents\]')
        if (-not $hasToc) {
            $fileErrors += "Document has $words words (>800 words) but is missing a Table of Contents"
        }
    }

    if ($fileErrors.Count -gt 0) {
        Write-Host "   X [$rel]:" -ForegroundColor Red
        foreach ($err in $fileErrors) {
            Write-Host "     - $err" -ForegroundColor Red
            $totalErrors++
        }
    } else {
        Write-Host "   OK [$rel]" -ForegroundColor Green
    }
}

Write-Host "`nSummary: Checked $totalChecked files, found $totalErrors issue(s)." -ForegroundColor Yellow
if ($totalErrors -gt 0) {
    exit 1
} else {
    Write-Host "All major documentation files comply with metadata and structure standards!" -ForegroundColor Green
    exit 0
}
