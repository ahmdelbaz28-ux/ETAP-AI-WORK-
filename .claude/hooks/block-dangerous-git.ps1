# PowerShell equivalent of block-dangerous-git.sh
# Blocks dangerous git commands like push, reset --hard, clean, branch -D, checkout ., restore .

param(
    [Parameter(ValueFromPipeline = $true)]
    [string]$Input
)

# Parse the input JSON to extract the command
$toolInput = $Input | ConvertFrom-Json
$command = $toolInput.tool_input.command

# Define dangerous patterns
$dangerousPatterns = @(
    "git push",
    "git reset --hard",
    "git clean -fd",
    "git clean -f",
    "git branch -D",
    "git checkout \.",
    "git restore \.",
    "push --force",
    "reset --hard"
)

# Check if command matches any dangerous pattern
foreach ($pattern in $dangerousPatterns) {
    if ($command -match $pattern) {
        Write-Error "BLOCKED: '$command' matches dangerous pattern '$pattern'. The user has prevented you from doing this."
        exit 2
    }
}

exit 0