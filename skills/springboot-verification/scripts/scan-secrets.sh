#!/usr/bin/env bash
# =============================================================================
# Spring Boot Secrets Scanner
# =============================================================================
# Scans a Spring Boot project source code for hardcoded secrets, API keys,
# passwords, and other sensitive information that should not be committed.
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

# ── Pattern Definitions ─────────────────────────────────────────────────────
# Each pattern: "severity|label|grep_pattern"
# severity: CRITICAL or WARNING
SECRETS_PATTERNS=(
  "CRITICAL|Hardcoded password|password\\s*=\\s*\"[^\"]+\""
  "CRITICAL|Hardcoded password in properties|password\\s*=\\s*[^\\s]+"
  "CRITICAL|AWS Secret Key|AKIA[0-9A-Z]{16}"
  "CRITICAL|AWS Secret Access Key|[A-Za-z0-9/+=]{40}"
  "CRITICAL|OpenAI API Key|sk-[a-zA-Z0-9]{20,}"
  "CRITICAL|Stripe Secret Key|sk_live_[a-zA-Z0-9]{24,}"
  "CRITICAL|Stripe Publishable Key|pk_live_[a-zA-Z0-9]{24,}"
  "CRITICAL|GitHub Token|ghp_[a-zA-Z0-9]{36}"
  "CRITICAL|GitHub OAuth|gho_[a-zA-Z0-9]{36}"
  "CRITICAL|Slack Token|xox[baprs]-[a-zA-Z0-9-]+"
  "CRITICAL|JWT Secret|jwt\\.secret\\s*=\\s*\"[^\"]+\""
  "CRITICAL|Private Key Header|-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----"
  "WARNING|API key pattern|api[_-]?key\\s*=\\s*\"[^\"]+\""
  "WARNING|Secret pattern|secret\\s*=\\s*\"[^\"]+\""
  "WARNING|Token pattern|token\\s*=\\s*\"[^\"]+\""
  "WARNING|Database URL with credentials|jdbc:.*:.*:.*@"
  "WARNING|Authorization header|Authorization\\s*:\\s*Bearer\\s+[a-zA-Z0-9._-]+"
)

# Anti-patterns (security hygiene)
ANTIPATTERN_PATTERNS=(
  "WARNING|System.out.println|System\\.out\\.print"
  "WARNING|Raw exception exposure|e\\.getMessage\\(\\)"
  "WARNING|Wildcard CORS|allowedOrigins.*\\*"
  "WARNING|Disable CSRF|csrf\\(\\)\\.disable"
  "WARNING|Disable frame options|frameOptions\\(\\)\\.disable"
  "WARNING|Permit all|permitAll\\(\\)"
  "WARNING|Insecure HTTP|http://.*\\.example\\.com"
  "WARNING|Debug logging enabled|logging\\.level\\.root=DEBUG"
  "WARNING|H2 console enabled|spring\\.h2\\.console\\.enabled=true"
  "WARNING|Actuator exposed|management\\.endpoints\\.web\\.exposure\\.include=\\*"
)

# ── File Types to Scan ──────────────────────────────────────────────────────
JAVA_FILES="--include=*.java"
YML_FILES="--include=*.yml --include=*.yaml"
PROPERTIES_FILES="--include=*.properties"
XML_FILES="--include=*.xml"
ALL_SOURCE_FILES="--include=*.java --include=*.yml --include=*.yaml --include=*.properties --include=*.xml --include=*.json"

# ── Scanning Functions ──────────────────────────────────────────────────────
total_findings=0
critical_findings=0
warning_findings=0
declare -a FINDINGS

scan_pattern() {
  local severity="$1" label="$2" pattern="$3" target_dir="$4" file_filter="$5"

  local matches
  matches=$(grep -rn -E "$pattern" "$target_dir" $file_filter 2>/dev/null || true)

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
    scan_pattern "$severity" "$label" "$pattern" "src/" "$ALL_SOURCE_FILES"
  done

  log_info "Scanning for security anti-patterns..."
  for pattern_def in "${ANTIPATTERN_PATTERNS[@]}"; do
    IFS='|' read -r severity label pattern <<< "$pattern_def"
    scan_pattern "$severity" "$label" "$pattern" "src/main/" "$JAVA_FILES $YML_FILES $PROPERTIES_FILES"
  done
fi

# Scan configuration files
for config_file in application.properties application.yml application.yaml; do
  if [[ -f "src/main/resources/$config_file" ]]; then
    log_info "Scanning $config_file..."
    for pattern_def in "${SECRETS_PATTERNS[@]}"; do
      IFS='|' read -r severity label pattern <<< "$pattern_def"
      scan_pattern "$severity" "$label" "$pattern" "src/main/resources/$config_file" ""
    done
  fi
done

# Check for .env files
for env_file in .env .env.local .env.production .env.staging; do
  if [[ -f "$env_file" ]]; then
    log_warn "Found $env_file — ensure it is in .gitignore"
    # Check if .env is in .gitignore
    if [[ -f ".gitignore" ]]; then
      if ! grep -q "$env_file" .gitignore 2>/dev/null; then
        FINDINGS+=("[CRITICAL] $env_file not in .gitignore")
        critical_findings=$((critical_findings + 1))
        total_findings=$((total_findings + 1))
      fi
    fi
  fi
done

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
