#!/usr/bin/env bash
# =============================================================================
# Node.js/TypeScript Secrets Scanner
# =============================================================================
# Scans a Node.js/TypeScript project for hardcoded secrets, API keys,
# passwords, and security anti-patterns that should not be committed.
#
# Usage:
#   ./scan-secrets.sh [OPTIONS]
#
# Options:
#   -p, --project-dir <path>    Project directory (default: .)
#   -s, --strict                Strict mode: treat warnings as failures
#   -c, --count-only            Output only the count of findings
#   -o, --output <file>         Output report file
#   -v, --verbose               Verbose output
#   -h, --help                  Show help
#
# Exit codes:
#   0 — No secrets found
#   1 — Secrets found (or in strict mode: warnings count as findings)
#   2 — Error
# =============================================================================

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
PROJECT_DIR="."
STRICT=false
COUNT_ONLY=false
OUTPUT_FILE=""
VERBOSE=false

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ── Helpers ──────────────────────────────────────────────────────────────────
log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_pass()    { echo -e "${GREEN}[PASS]${NC}  $*"; }
log_fail()    { echo -e "${RED}[FAIL]${NC}  $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }

# ── Argument Parsing ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--project-dir)  PROJECT_DIR="$2"; shift 2 ;;
    -s|--strict)       STRICT=true; shift ;;
    -c|--count-only)   COUNT_ONLY=true; shift ;;
    -o|--output)       OUTPUT_FILE="$2"; shift 2 ;;
    -v|--verbose)      VERBOSE=true; shift ;;
    -h|--help)         sed -n '2,/^# =====/p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *)                 echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

cd "$PROJECT_DIR" || { echo "Directory not found: $PROJECT_DIR" >&2; exit 2; }

# ── Check Dependencies ───────────────────────────────────────────────────────
if ! command -v grep >/dev/null 2>&1; then
  echo "grep not found in PATH" >&2
  exit 2
fi

# ── File Types to Scan ──────────────────────────────────────────────────────
TS_FILES="--include=*.ts"
JS_FILES="--include=*.js"
JSON_FILES="--include=*.json"
ALL_SOURCE_FILES="--include=*.ts --include=*.js --include=*.json --include=*.yml --include=*.yaml --include=*.env --include=*.env.*"

# ── Pattern Definitions ─────────────────────────────────────────────────────
# Each pattern: "severity|label|grep_pattern"
SECRETS_PATTERNS=(
  "CRITICAL|Hardcoded password|password\\s*[:=]\\s*['\"][^'\"]+['\"]"
  "CRITICAL|AWS Access Key|AKIA[0-9A-Z]{16}"
  "CRITICAL|AWS Secret Key|[A-Za-z0-9/+=]{40}"
  "CRITICAL|OpenAI API Key|sk-[a-zA-Z0-9]{20,}"
  "CRITICAL|Stripe Secret Key|sk_live_[a-zA-Z0-9]{24,}"
  "CRITICAL|Stripe Publishable Key|pk_live_[a-zA-Z0-9]{24,}"
  "CRITICAL|GitHub Token|ghp_[a-zA-Z0-9]{36}"
  "CRITICAL|GitHub OAuth|gho_[a-zA-Z0-9]{36}"
  "CRITICAL|GitHub PAT|github_pat_[a-zA-Z0-9_]{22,}"
  "CRITICAL|Slack Token|xox[baprs]-[a-zA-Z0-9-]+"
  "CRITICAL|JWT Secret hardcoded|jwtSecret\\s*[:=]\\s*['\"][^'\"]+['\"]"
  "CRITICAL|JWT Secret in config|jwt[_-]?secret\\s*[:=]\\s*['\"][^'\"]+['\"]"
  "CRITICAL|Private Key Header|-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----"
  "CRITICAL|Database URL with password|postgresql?://[^:]+:[^@]+@"
  "WARNING|API key pattern|api[_-]?key\\s*[:=]\\s*['\"][^'\"]+['\"]"
  "WARNING|Secret pattern|secret\\s*[:=]\\s*['\"][^'\"]+['\"]"
  "WARNING|Token pattern|token\\s*[:=]\\s*['\"][^'\"]+['\"]"
  "WARNING|Authorization header|Authorization\\s*:\\s*Bearer\\s+[a-zA-Z0-9._-]+"
)

# Anti-patterns (security hygiene for Node.js/TypeScript)
ANTIPATTERN_PATTERNS=(
  "WARNING|console.log in production|console\\.log\\("
  "WARNING|eval() usage|eval\\s*\\("
  "WARNING|Dangerous innerHTML|innerHTML\\s*="
  "WARNING|Wildcard CORS|cors\\s*:\\s*\\*|origin\\s*:\\s*\\*"
  "WARNING|Disable CSRF|csrf\\s*\\(\\)\\.disable"
  "WARNING|HTTP (not HTTPS) URL|http://.*\\.example\\.com"
  "WARNING|process.exit without handler|process\\.exit\\(\\d?\\)"
  "WARNING|TODO/FIXME marker|TODO|FIXME"
  "WARNING|ts-ignore|@ts-ignore"
  "WARNING|any type usage|:\\s*any\\b"
  "WARNING|Insecure random|Math\\.random\\(\\)"
)

# ── Scanning Functions ──────────────────────────────────────────────────────
total_findings=0
critical_findings=0
warning_findings=0
declare -a FINDINGS=()

scan_pattern() {
  local severity="$1" label="$2" pattern="$3" target_dir="$4" file_filter="$5"

  local matches
  matches=$(grep -rn -E "$pattern" "$target_dir" $file_filter 2>/dev/null || true)

  # Filter out node_modules, dist, coverage, skills directories
  matches=$(echo "$matches" | grep -v 'node_modules/' | grep -v 'dist/' | grep -v 'coverage/' | grep -v 'skills/' | grep -v '.d.ts' || true)

  if [[ -n "$matches" ]]; then
    local count
    count=$(echo "$matches" | wc -l | tr -d ' ')
    total_findings=$((total_findings + count))

    if [[ "$severity" == "CRITICAL" ]]; then
      critical_findings=$((critical_findings + count))
    else
      warning_findings=$((warning_findings + count))
    fi

    FINDINGS+=("[$severity] $label: $count finding(s)")

    if [[ "$COUNT_ONLY" != true ]]; then
      echo "$matches" | while IFS= read -r line; do
        echo -e "  ${RED}$line${NC}" >&2
      done
    fi
  fi
}

# ── Main Scan ────────────────────────────────────────────────────────────────
log_info "Scanning for secrets in: $(pwd)"

# Scan source code
if [[ -d "src" ]]; then
  log_info "Scanning src/ directory..."

  for pattern_def in "${SECRETS_PATTERNS[@]}"; do
    IFS='|' read -r severity label pattern <<< "$pattern_def"
    scan_pattern "$severity" "$label" "$pattern" "src/" "$TS_FILES $JS_FILES"
  done

  log_info "Scanning for security anti-patterns..."
  for pattern_def in "${ANTIPATTERN_PATTERNS[@]}"; do
    IFS='|' read -r severity label pattern <<< "$pattern_def"
    scan_pattern "$severity" "$label" "$pattern" "src/" "$TS_FILES $JS_FILES"
  done
fi

# Check for .env files that should not be committed
for env_file in .env .env.local .env.production .env.staging; do
  if [[ -f "$env_file" ]]; then
    log_warn "Found $env_file — ensure it is in .gitignore"
    if [[ -f ".gitignore" ]]; then
      if ! grep -q "^${env_file}$" .gitignore 2>/dev/null; then
        FINDINGS+=("[CRITICAL] $env_file not in .gitignore")
        critical_findings=$((critical_findings + 1))
        total_findings=$((total_findings + 1))
      fi
    fi
  fi
done

# Verify .env.example exists
if [[ ! -f ".env.example" ]]; then
  FINDINGS+=("[WARNING] No .env.example file found — create a template for developers")
  warning_findings=$((warning_findings + 1))
  total_findings=$((total_findings + 1))
fi

# ── Output ──────────────────────────────────────────────────────────────────
if [[ "$COUNT_ONLY" == true ]]; then
  echo "$total_findings"
  exit $((total_findings > 0 ? 1 : 0))
fi

echo ""
echo "=========================================="
echo "  SECRETS SCAN REPORT"
echo "=========================================="
echo "  Critical findings: ${critical_findings}"
echo "  Warning findings:  ${warning_findings}"
echo "  Total findings:    ${total_findings}"
echo "------------------------------------------"

if [[ ${#FINDINGS[@]} -gt 0 ]]; then
  echo "  Breakdown:"
  for finding in "${FINDINGS[@]}"; do
    echo "    $finding"
  done
fi

echo "=========================================="

# Save report
if [[ -n "$OUTPUT_FILE" ]]; then
  {
    echo "SECRETS SCAN REPORT"
    echo "===================="
    echo "Critical: ${critical_findings}"
    echo "Warnings: ${warning_findings}"
    echo "Total:    ${total_findings}"
    echo ""
    for finding in "${FINDINGS[@]}"; do
      echo "  $finding"
    done
  } > "$OUTPUT_FILE"
  log_info "Report saved to: $OUTPUT_FILE"
fi

# ── Exit Code ────────────────────────────────────────────────────────────────
if [[ "$critical_findings" -gt 0 ]]; then
  log_fail "CRITICAL secrets found — fix immediately"
  exit 1
elif [[ "$STRICT" == true && "$warning_findings" -gt 0 ]]; then
  log_fail "Warnings found in strict mode — treat as failures"
  exit 1
elif [[ "$warning_findings" -gt 0 ]]; then
  log_warn "Warnings found — review recommended"
  exit 0
else
  log_pass "No secrets found"
  exit 0
fi
