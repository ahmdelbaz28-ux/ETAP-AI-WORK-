# scripts/verify_assets.ps1 - Verify all image references in Documentation Markdown files
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
$imageRegex = '!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)'
$codeBlockRegex = '```[\s\S]*?```'

$totalImages = 0
$externalCount = 0
$verifiedCount = 0
$brokenList = @()

Write-Host "Scanning $($mdFiles.Count) documentation Markdown files for media assets..." -ForegroundColor Cyan

foreach ($file in $mdFiles) {
    $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    if (-not $content) { continue }

    # Strip code blocks
    $contentClean = [regex]::Replace($content, $codeBlockRegex, '')

    $matches = [regex]::Matches($contentClean, $imageRegex)
    foreach ($m in $matches) {
        $totalImages++
        $alt = $m.Groups[1].Value
        $target = $m.Groups[2].Value.Trim()

        if ($target.StartsWith("http://") -or $target.StartsWith("https://")) {
            $externalCount++
            continue
        }

        if ($target -eq "...") { continue }

        # Clean query/hash
        $cleanTarget = ($target -split '\?')[0]
        $cleanTarget = ($cleanTarget -split '#')[0]
        if (-not $cleanTarget) { continue }

        $parentDir = $file.DirectoryName
        $targetPath = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($parentDir, $cleanTarget))
        $rootTarget = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($repoRoot, $cleanTarget.TrimStart('/','\')))
        $docsTarget = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($docsDir, $cleanTarget.TrimStart('/','\')))

        if ([System.IO.File]::Exists($targetPath) -or [System.IO.File]::Exists($rootTarget) -or [System.IO.File]::Exists($docsTarget)) {
            $verifiedCount++
        } else {
            $relPath = $file.FullName.Substring($repoRoot.Length + 1)
            $brokenList += [PSCustomObject]@{
                File = $relPath
                Alt = $alt
                Target = $target
                Resolved = $targetPath
            }
        }
    }
}

Write-Host "`nDocumentation Media Asset Verification Summary:" -ForegroundColor Yellow
Write-Host "   Total Image References: $totalImages"
Write-Host "   External URLs / Badges:  $externalCount"
Write-Host "   Verified Local Files:   $verifiedCount"
Write-Host "   Broken / Missing Local: $($brokenList.Count)"

if ($brokenList.Count -gt 0) {
    Write-Host "`nMissing/Broken Assets Found:" -ForegroundColor Red
    foreach ($item in $brokenList) {
        Write-Host "   - [$($item.File)]: ![$($item.Alt)]($($item.Target))" -ForegroundColor Red
    }
    exit 1
} else {
    Write-Host "`nAll documentation media assets and image references are valid and verified!" -ForegroundColor Green
    exit 0
}
