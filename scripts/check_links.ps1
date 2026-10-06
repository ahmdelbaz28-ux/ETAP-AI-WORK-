# scripts/check_links.ps1 - Validate internal markdown links across documentation
$repoRoot = (Get-Item $PSScriptRoot).Parent.FullName

$rootFiles = Get-ChildItem -Path $repoRoot -Filter *.md -File
$docsFiles = @()
$docsDir = Join-Path $repoRoot "docs"
if (Test-Path $docsDir) {
    $docsFiles = Get-ChildItem -Path $docsDir -Recurse -Filter *.md -File | Where-Object {
        $_.FullName -notmatch '\\site\\' -and $_.FullName -notmatch '\\node_modules\\'
    }
}

$mdFiles = @($rootFiles) + @($docsFiles)
$linkRegex = '(?<!!)\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)'
$codeBlockRegex = '```[\s\S]*?```'

$totalLinks = 0
$externalCount = 0
$anchorCount = 0
$verifiedCount = 0
$brokenList = @()

Write-Host "Scanning $($mdFiles.Count) documentation files for link integrity..." -ForegroundColor Cyan

foreach ($file in $mdFiles) {
    $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    if (-not $content) { continue }

    $cleanContent = [regex]::Replace($content, $codeBlockRegex, '')

    $matches = [regex]::Matches($cleanContent, $linkRegex)
    foreach ($m in $matches) {
        $totalLinks++
        $text = $m.Groups[1].Value.Trim()
        $target = $m.Groups[2].Value.Trim()

        if ($target.StartsWith("http://") -or $target.StartsWith("https://") -or $target.StartsWith("mailto:")) {
            $externalCount++
            continue
        }

        if ($target.StartsWith("#")) {
            $anchorCount++
            continue
        }

        $cleanTarget = ($target -split '\?')[0]
        $cleanTarget = ($cleanTarget -split '#')[0]
        if (-not $cleanTarget) {
            $anchorCount++
            continue
        }

        $parentDir = $file.DirectoryName
        $found = $false
        try {
            $targetPath = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($parentDir, $cleanTarget))
            if ([System.IO.File]::Exists($targetPath) -or [System.IO.Directory]::Exists($targetPath)) { $found = $true }
        } catch {}

        if (-not $found) {
            try {
                $rootTarget = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($repoRoot, $cleanTarget.TrimStart('/','\')))
                if ([System.IO.File]::Exists($rootTarget) -or [System.IO.Directory]::Exists($rootTarget)) { $found = $true }
            } catch {}
        }

        if (-not $found) {
            try {
                $docsTarget = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($docsDir, $cleanTarget.TrimStart('/','\')))
                if ([System.IO.File]::Exists($docsTarget) -or [System.IO.Directory]::Exists($docsTarget)) { $found = $true }
            } catch {}
        }

        if ($found) {
            $verifiedCount++
        } else {
            $relPath = $file.FullName.Substring($repoRoot.Length + 1)
            $brokenList += [PSCustomObject]@{
                File = $relPath
                Text = $text
                Target = $target
                Resolved = $cleanTarget
            }
        }
    }
}

Write-Host "`nDocumentation Link Integrity Summary:" -ForegroundColor Yellow
Write-Host "   Total Links Analyzed:   $totalLinks"
Write-Host "   External Links:         $externalCount"
Write-Host "   Anchor-Only Links:      $anchorCount"
Write-Host "   Verified Local Links:   $verifiedCount"
Write-Host "   Broken Local Links:     $($brokenList.Count)"

if ($brokenList.Count -gt 0) {
    Write-Host "`nBroken Links Found:" -ForegroundColor Red
    foreach ($item in $brokenList) {
        Write-Host "   - [$($item.File)]: [$($item.Text)]($($item.Target))" -ForegroundColor Red
    }
    exit 1
} else {
    Write-Host "`nZero broken internal documentation links! Link integrity verified." -ForegroundColor Green
    exit 0
}
