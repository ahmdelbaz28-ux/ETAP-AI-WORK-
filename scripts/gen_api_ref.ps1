# scripts/gen_api_ref.ps1 - Synchronize and verify API cheat sheet with canonical API Reference
param (
    [switch]$Check
)

$repoRoot = (Get-Item $PSScriptRoot).Parent.FullName
$canonicalRef = Join-Path $repoRoot "docs\API_REFERENCE.md"
$quickrefOut = Join-Path $repoRoot "docs\API_QUICKREF.md"

if (-not (Test-Path $canonicalRef)) {
    Write-Error "Canonical reference not found: $canonicalRef"
    exit 1
}

$lines = Get-Content -Path $canonicalRef -Encoding UTF8
$endpoints = @()
$currentSection = "General"

$endpointPattern = '^###\s+(GET|POST|PUT|DELETE|PATCH|WS)\s+([^\s\r\n]+)(?:\s*\((.*?)\))?'
$sectionPattern = '^##\s+(?!#)(.+)$'

for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i].Trim()

    if ($line -match $sectionPattern) {
        $secTitle = $matches[1].Trim()
        if (-not $secTitle.ToLower().StartsWith('overview') -and -not $secTitle.ToLower().StartsWith('authentication')) {
            $currentSection = $secTitle
        }
        continue
    }

    if ($line -match $endpointPattern) {
        $method = $matches[1].Trim()
        $path = $matches[2].Trim()
        $notes = ''
        if ($matches.Count -ge 4 -and $matches[3]) {
            $notes = $matches[3]
        }

        $summary = ''
        $limit = [Math]::Min($i + 10, $lines.Count)
        for ($j = $i + 1; $j -lt $limit; $j++) {
            $subLine = $lines[$j].Trim()
            if ($subLine.StartsWith('#') -or $subLine.StartsWith('```')) {
                break
            }
            if ($subLine.Length -gt 0 -and -not $subLine.StartsWith('**')) {
                $summary = $subLine
                break
            }
        }

        $rawAnchor = "$method $path"
        if ($notes.Length -gt 0) {
            $rawAnchor = "$rawAnchor $notes"
        }
        $cleanAnchor = ($rawAnchor.ToLower() -replace '[^\w\- ]', '').Replace(' ', '-')

        $endpoints += [PSCustomObject]@{
            Section = $currentSection
            Method  = $method
            Path    = $path
            Notes   = $notes
            Summary = $summary
            Anchor  = $cleanAnchor
        }
    }
}

Write-Host "Parsed $canonicalRef : Discovered $($endpoints.Count) endpoints." -ForegroundColor Cyan

$today = (Get-Date).ToString("yyyy-MM-dd")

$md = [System.Collections.Generic.List[string]]::new()
$md.Add('---')
$md.Add('title: "AhmedETAP API Quick Reference Cheat-Sheet"')
$md.Add('version: "2.1.0"')
$md.Add("last_updated: `"$today`"")
$md.Add('maintainer: "Eng. Ahmed Elbaz / Platform Team"')
$md.Add('---')
$md.Add('')
$md.Add('# ⚡ AhmedETAP API Quick Reference (Cheat-Sheet)')
$md.Add('')
$md.Add('> **Note:** This cheat-sheet is automatically derived from the authoritative [API Reference](API_REFERENCE.md).')
$md.Add('> For complete request/response JSON schemas, error codes, and field validations, consult [docs/API_REFERENCE.md](API_REFERENCE.md).')
$md.Add('')
$md.Add('## Table of Contents')
$md.Add('- [Authentication Overview](#authentication-overview)')
$md.Add('- [Endpoints Quick Reference](#endpoints-quick-reference)')
$md.Add('- [Quick cURL Recipes](#quick-curl-recipes)')
$md.Add('- [WebSocket Protocol](#websocket-protocol)')
$md.Add('')
$md.Add('---')
$md.Add('')
$md.Add('## Authentication Overview')
$md.Add('')
$md.Add('| Mechanism | Header Format | Typical Use |')
$md.Add('| :--- | :--- | :--- |')
$md.Add('| **JWT Bearer** | `Authorization: Bearer <jwt_token>` | UI, Interactive Sessions, RBAC |')
$md.Add('| **API Key** | `X-API-Key: <api_key>` | Automated CI/CD, Microservices, COM Scripts |')
$md.Add('')
$md.Add('Obtain token via `POST /api/auth/login` with username & password.')
$md.Add('')
$md.Add('---')
$md.Add('')
$md.Add('## Endpoints Quick Reference')
$md.Add('')
$md.Add('| Method | Endpoint | Category | Description | Canonical Ref |')
$md.Add('| :---: | :--- | :--- | :--- | :---: |')

foreach ($ep in $endpoints) {
    $methodBadge = '`' + $ep.Method + '`'
    $notesStr = ''
    if ($ep.Notes.Length -gt 0) {
        $notesStr = ' *(' + $ep.Notes + ')*'
    }
    $fullEndpoint = '`' + $ep.Path + '`' + $notesStr
    $sumText = 'Engineering platform endpoint'
    if ($ep.Summary.Length -gt 0) {
        $sumText = $ep.Summary
    }
    $link = '[Docs](API_REFERENCE.md#' + $ep.Anchor + ')'
    $md.Add("| $methodBadge | $fullEndpoint | $($ep.Section) | $sumText | $link |")
}

$md.Add('')
$md.Add('---')
$md.Add('')
$md.Add('## Quick cURL Recipes')
$md.Add('')
$md.Add('### 1. Health & Readiness Probe')
$md.Add('```bash')
$md.Add('curl -s http://localhost:8000/healthz')
$md.Add('curl -s http://localhost:8000/readyz')
$md.Add('```')
$md.Add('')
$md.Add('### 2. Run Newton-Raphson Load Flow')
$md.Add('```bash')
$md.Add('curl -X POST http://localhost:8000/api/v1/studies/run \')
$md.Add('  -H "Authorization: Bearer $TOKEN" \')
$md.Add('  -H "Content-Type: application/json" \')
$md.Add('  -d ''{"study_type": "LOAD_FLOW", "project_id": "substation_alpha", "parameters": {"max_iterations": 20, "tolerance": 0.0001}}''')
$md.Add('```')
$md.Add('')
$md.Add('### 3. Run IEC 60909 Short Circuit')
$md.Add('```bash')
$md.Add('curl -X POST http://localhost:8000/api/v1/studies/run \')
$md.Add('  -H "Authorization: Bearer $TOKEN" \')
$md.Add('  -H "Content-Type: application/json" \')
$md.Add('  -d ''{"study_type": "SHORT_CIRCUIT", "project_id": "substation_alpha", "parameters": {"standard": "IEC_60909", "fault_type": "3PHASE"}}''')
$md.Add('```')
$md.Add('')
$md.Add('### 4. Query Active Agents Registry')
$md.Add('```bash')
$md.Add('curl -s http://localhost:8000/api/v1/agents \')
$md.Add('  -H "Authorization: Bearer $TOKEN"')
$md.Add('```')
$md.Add('')
$md.Add('---')
$md.Add('')
$md.Add('## WebSocket Protocol')
$md.Add('')
$md.Add('- **Study Streaming:** `ws://localhost:8000/ws/study/{study_id}`')
$md.Add('- Subscribes to real-time iteration logs, convergence metrics, and progress percentages.')
$md.Add('- See [WebSocket Protocol in API_REFERENCE.md](API_REFERENCE.md#ws-wsstudystudyid).')
$md.Add('')

$generatedText = ($md -join "`n")

if ($Check) {
    if (-not (Test-Path $quickrefOut)) {
        Write-Error "Check failed: $quickrefOut does not exist!"
        exit 1
    }
    $existingText = [System.IO.File]::ReadAllText($quickrefOut, [System.Text.Encoding]::UTF8)

    $genLines = ($generatedText -split "`n") | Where-Object { $_ -notmatch '^last_updated:' }
    $exLines = ($existingText -replace "`r`n", "`n" -split "`n") | Where-Object { $_ -notmatch '^last_updated:' }

    $genComparable = ($genLines -join "`n").Trim()
    $exComparable = ($exLines -join "`n").Trim()

    if ($genComparable -ne $exComparable) {
        Write-Host "Check failed: $quickrefOut is out of sync with $canonicalRef!" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] $quickrefOut is synchronized with canonical $canonicalRef." -ForegroundColor Green
    exit 0
} else {
    [System.IO.File]::WriteAllText($quickrefOut, $generatedText, [System.Text.Encoding]::UTF8)
    Write-Host "Generated $quickrefOut successfully." -ForegroundColor Green
}
