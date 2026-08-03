#!/usr/bin/env bash
# =============================================================================
# Spring Boot Verification Loop — Main Automation Script
# =============================================================================
# Runs the full 6-phase verification pipeline for Spring Boot projects.
# Supports both Maven and Gradle builds.
#
# Usage:
#   ./springboot-verify.sh [OPTIONS]
#
# Options:
#   -b, --build-tool <maven|gradle>   Build tool (default: auto-detect)
#   -p, --project-dir <path>          Project directory (default: .)
#   -s, --skip <phase>                Skip a phase (build,static,test,security,lint,diff)
#   -c, --coverage-threshold <pct>    Coverage threshold (default: 80)
#   -o, --output <file>               Output report file (default: verification-report.txt)
#   -q, --quick                       Quick mode: only build + test + static
#   -v, --verbose                     Verbose output
#   -h, --help                        Show help
#
# Exit codes:
#   0 — All phases passed
#   1 — One or more phases failed
#   2 — Invalid arguments or missing prerequisites
# =============================================================================

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
BUILD_TOOL=""
PROJECT_DIR="."
COVERAGE_THRESHOLD=80
OUTPUT_FILE="verification-report.txt"
QUICK_MODE=false
VERBOSE=false
SKIP_PHASES=()

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ── Helpers ──────────────────────────────────────────────────────────────────
log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_pass()    { echo -e "${GREEN}[PASS]${NC}  $*"; }
log_fail()    { echo -e "${RED}[FAIL]${NC}  $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_verbose() { [[ "${VERBOSE}" == true ]] && echo -e "${BLUE}[DBG]${NC}   $*"; }

die() {
  echo -e "${RED}[FATAL]${NC} $*" >&2
  exit 2
}

# ── Argument Parsing ─────────────────────────────────────────────────────────
show_help() {
  sed -n '2,/^# =====/p' "$0" | sed 's/^# \?//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -b|--build-tool)   BUILD_TOOL="$2"; shift 2 ;;
    -p|--project-dir)  PROJECT_DIR="$2"; shift 2 ;;
    -s|--skip)         SKIP_PHASES+=("$2"); shift 2 ;;
    -c|--coverage-threshold) COVERAGE_THRESHOLD="$2"; shift 2 ;;
    -o|--output)       OUTPUT_FILE="$2"; shift 2 ;;
    -q|--quick)        QUICK_MODE=true; shift ;;
    -v|--verbose)      VERBOSE=true; shift ;;
    -h|--help)         show_help ;;
    *)                 die "Unknown option: $1" ;;
  esac
done

# ── Resolve Project Directory ────────────────────────────────────────────────
cd "$PROJECT_DIR" || die "Project directory not found: $PROJECT_DIR"
log_info "Working directory: $(pwd)"

# ── Auto-detect Build Tool ───────────────────────────────────────────────────
if [[ -z "$BUILD_TOOL" ]]; then
  if [[ -f "pom.xml" ]]; then
    BUILD_TOOL="maven"
  elif [[ -f "build.gradle" || -f "build.gradle.kts" ]]; then
    BUILD_TOOL="gradle"
  else
    die "Cannot detect build tool: no pom.xml or build.gradle found in $(pwd)"
  fi
  log_info "Auto-detected build tool: $BUILD_TOOL"
fi

# Validate build tool
if [[ "$BUILD_TOOL" != "maven" && "$BUILD_TOOL" != "gradle" ]]; then
  die "Invalid build tool: $BUILD_TOOL (must be maven or gradle)"
fi

# ── Check Prerequisites ──────────────────────────────────────────────────────
if [[ "$BUILD_TOOL" == "maven" ]]; then
  command -v mvn >/dev/null 2>&1 || die "Maven (mvn) not found in PATH"
else
  [[ -x "./gradlew" ]] || die "Gradle wrapper (gradlew) not found or not executable"
fi

command -v git >/dev/null 2>&1 || log_warn "Git not found — diff phase will be skipped"

# ── Result Tracking ──────────────────────────────────────────────────────────
declare -A RESULTS
ISSUES=()
OVERALL="READY"

should_skip() {
  local phase="$1"
  for s in "${SKIP_PHASES[@]}"; do
    [[ "$s" == "$phase" ]] && return 0
  done
  return 1
}

record_result() {
  local phase="$1" status="$2" detail="$3"
  RESULTS["$phase"]="$status"
  if [[ "$status" == "FAIL" ]]; then
    OVERALL="NOT READY"
    [[ -n "$detail" ]] && ISSUES+=("$detail")
  fi
}

# ── Phase 1: Build ──────────────────────────────────────────────────────────
phase_build() {
  log_info "Phase 1: Build"
  if should_skip "build"; then
    log_warn "  Skipping build phase"
    RESULTS["build"]="SKIP"
    return
  fi

  local cmd
  if [[ "$BUILD_TOOL" == "maven" ]]; then
    cmd="mvn -T 4 clean verify -DskipTests"
  else
    cmd="./gradlew clean assemble -x test"
  fi

  log_verbose "  Running: $cmd"
  if $cmd >/dev/null 2>&1; then
    log_pass "  Build: PASS"
    record_result "build" "PASS" ""
  else
    log_fail "  Build: FAIL"
    record_result "build" "FAIL" "Build failed — fix compilation errors first"
  fi
}

# ── Phase 2: Static Analysis ────────────────────────────────────────────────
phase_static() {
  log_info "Phase 2: Static Analysis"
  if should_skip "static"; then
    log_warn "  Skipping static analysis phase"
    RESULTS["static"]="SKIP"
    return
  fi

  local cmd
  if [[ "$BUILD_TOOL" == "maven" ]]; then
    cmd="mvn -T 4 spotbugs:check pmd:check checkstyle:check"
  else
    cmd="./gradlew checkstyleMain pmdMain spotbugsMain"
  fi

  log_verbose "  Running: $cmd"
  if $cmd >/dev/null 2>&1; then
    log_pass "  Static Analysis: PASS"
    record_result "static" "PASS" ""
  else
    log_fail "  Static Analysis: FAIL"
    record_result "static" "FAIL" "Static analysis violations found (spotbugs/pmd/checkstyle)"
  fi
}

# ── Phase 3: Tests + Coverage ───────────────────────────────────────────────
phase_tests() {
  log_info "Phase 3: Tests + Coverage"
  if should_skip "test"; then
    log_warn "  Skipping test phase"
    RESULTS["test"]="SKIP"
    return
  fi

  local test_cmd coverage_cmd
  if [[ "$BUILD_TOOL" == "maven" ]]; then
    test_cmd="mvn -T 4 test"
    coverage_cmd="mvn jacoco:report"
  else
    test_cmd="./gradlew test"
    coverage_cmd="./gradlew jacocoTestReport"
  fi

  # Run tests
  log_verbose "  Running: $test_cmd"
  local test_output
  test_output=$($test_cmd 2>&1) || true

  # Parse test results
  local total=0 passed=0 failed=0
  if [[ "$BUILD_TOOL" == "maven" ]]; then
    # Parse Maven Surefire output
    total=$(echo "$test_output" | grep -oP 'Tests run: \K\d+' | tail -1 || echo "0")
    passed=$(echo "$test_output" | grep -oP 'Tests run: \d+.*Failures: \K\d+' | tail -1 || echo "0")
    failed=$(echo "$test_output" | grep -oP 'Failures: \K\d+.*' | head -1 | grep -oP '^\d+' || echo "0")
  else
    # Parse Gradle test output
    total=$(echo "$test_output" | grep -oP '\d+ tests completed' | grep -oP '^\d+' || echo "0")
    failed=$(echo "$test_output" | grep -oP '\d+ tests? failed' | grep -oP '^\d+' || echo "0")
    passed=$((total - failed))
  fi

  log_info "  Tests: ${passed}/${total} passed, ${failed} failed"

  # Run coverage report
  log_verbose "  Running: $coverage_cmd"
  $coverage_cmd >/dev/null 2>&1 || true

  # Check coverage
  local coverage_pct=0
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [[ -f "$script_dir/verify-coverage.py" ]]; then
    coverage_pct=$(python3 "$script_dir/verify-coverage.py" \
      --build-tool "$BUILD_TOOL" \
      --threshold "$COVERAGE_THRESHOLD" \
      --project-dir "$(pwd)" \
      --percentage-only 2>/dev/null || echo "0")
  else
    # Fallback: try to parse JaCoCo CSV directly
    local jacoco_csv
    if [[ "$BUILD_TOOL" == "maven" ]]; then
      jacoco_csv="target/site/jacoco/jacoco.csv"
    else
      jacoco_csv="build/reports/jacoco/test/jacocoTestReport.csv"
    fi
    if [[ -f "$jacoco_csv" ]]; then
      coverage_pct=$(awk -F',' 'NR>1 {instr_missed+=$4; instr_covered+=$5} END {
        if (instr_missed+instr_covered > 0)
          printf "%.0f", (instr_covered / (instr_missed + instr_covered)) * 100
        else print "0"
      }' "$jacoco_csv")
    fi
  fi

  local coverage_status="PASS"
  if [[ "$coverage_pct" -lt "$COVERAGE_THRESHOLD" ]]; then
    coverage_status="FAIL"
    log_fail "  Coverage: ${coverage_pct}% (below threshold ${COVERAGE_THRESHOLD}%)"
  else
    log_pass "  Coverage: ${coverage_pct}% (meets threshold ${COVERAGE_THRESHOLD}%)"
  fi

  if [[ "$failed" -gt 0 ]]; then
    record_result "test" "FAIL" "Tests: ${failed}/${total} failed, coverage: ${coverage_pct}%"
  elif [[ "$coverage_status" == "FAIL" ]]; then
    record_result "test" "FAIL" "Coverage ${coverage_pct}% is below threshold ${COVERAGE_THRESHOLD}%"
  else
    record_result "test" "PASS" ""
    RESULTS["test_detail"]="${passed}/${total} passed, ${coverage_pct}% coverage"
  fi
}

# ── Phase 4: Security Scan ──────────────────────────────────────────────────
phase_security() {
  log_info "Phase 4: Security Scan"
  if should_skip "security"; then
    log_warn "  Skipping security scan phase"
    RESULTS["security"]="SKIP"
    return
  fi

  local cve_findings=0
  local secret_findings=0

  # Dependency CVE scan
  log_verbose "  Running OWASP dependency check"
  local cve_cmd
  if [[ "$BUILD_TOOL" == "maven" ]]; then
    cve_cmd="mvn org.owasp:dependency-check-maven:check"
  else
    cve_cmd="./gradlew dependencyCheckAnalyze"
  fi

  if $cve_cmd >/dev/null 2>&1; then
    log_pass "  OWASP Dependency Check: PASS"
  else
    cve_findings=1
    log_fail "  OWASP Dependency Check: FAIL — CVE findings detected"
  fi

  # Secrets in source code
  log_verbose "  Scanning for hardcoded secrets"
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [[ -f "$script_dir/scan-secrets.sh" ]]; then
    secret_findings=$(bash "$script_dir/scan-secrets.sh" --count-only 2>/dev/null || echo "0")
  else
    # Fallback: basic grep patterns
    secret_findings=$(
      grep -rn 'password\s*=\s*"' src/ --include="*.java" --include="*.yml" --include="*.properties" 2>/dev/null | wc -l
      grep -rn 'sk-\|api_key\|secret' src/ --include="*.java" --include="*.yml" 2>/dev/null | wc -l
    )
  fi

  if [[ "$secret_findings" -gt 0 ]]; then
    log_fail "  Secrets Scan: FAIL — ${secret_findings} potential secret(s) found"
  else
    log_pass "  Secrets Scan: PASS — no secrets detected"
  fi

  # Common security anti-patterns
  local antipattern_findings=0
  local sysout_findings check_expose_findings cors_findings

  sysout_findings=$(grep -rn 'System\.out\.print' src/main/ --include="*.java" 2>/dev/null | wc -l || echo "0")
  check_expose_findings=$(grep -rn 'e\.getMessage()' src/main/ --include="*.java" 2>/dev/null | wc -l || echo "0")
  cors_findings=$(grep -rn 'allowedOrigins.*\*' src/main/ --include="*.java" 2>/dev/null | wc -l || echo "0")
  antipattern_findings=$((sysout_findings + check_expose_findings + cors_findings))

  if [[ "$antipattern_findings" -gt 0 ]]; then
    log_warn "  Security anti-patterns: ${antipattern_findings} finding(s)"
    log_warn "    - System.out.println: ${sysout_findings}"
    log_warn "    - Raw exception exposure: ${check_expose_findings}"
    log_warn "    - Wildcard CORS: ${cors_findings}"
  fi

  local total_findings=$((cve_findings + secret_findings))
  if [[ "$total_findings" -gt 0 ]]; then
    record_result "security" "FAIL" "Security: ${cve_findings} CVE finding(s), ${secret_findings} secret(s) found"
  else
    record_result "security" "PASS" ""
    RESULTS["security_detail"]="CVE findings: ${cve_findings}, secrets: ${secret_findings}"
  fi
}

# ── Phase 5: Lint/Format ────────────────────────────────────────────────────
phase_lint() {
  log_info "Phase 5: Lint/Format"
  if should_skip "lint"; then
    log_warn "  Skipping lint/format phase"
    RESULTS["lint"]="SKIP"
    return
  fi

  local cmd
  if [[ "$BUILD_TOOL" == "maven" ]]; then
    cmd="mvn spotless:check"
  else
    cmd="./gradlew spotlessCheck"
  fi

  log_verbose "  Running: $cmd"
  if $cmd >/dev/null 2>&1; then
    log_pass "  Lint/Format: PASS"
    record_result "lint" "PASS" ""
  else
    log_fail "  Lint/Format: FAIL — formatting issues detected"
    record_result "lint" "FAIL" "Code formatting issues detected (run spotless:apply to fix)"
  fi
}

# ── Phase 6: Diff Review ────────────────────────────────────────────────────
phase_diff() {
  log_info "Phase 6: Diff Review"
  if should_skip "diff"; then
    log_warn "  Skipping diff review phase"
    RESULTS["diff"]="SKIP"
    return
  fi

  if ! command -v git >/dev/null 2>&1; then
    log_warn "  Git not available — skipping diff review"
    RESULTS["diff"]="SKIP"
    return
  fi

  local files_changed
  files_changed=$(git diff --stat 2>/dev/null | tail -1 || echo "0 files changed")
  log_info "  Files changed: ${files_changed}"

  # Check for common issues in the diff
  local diff_issues=0

  # Check for debug logs left in code
  local debug_logs
  debug_logs=$(git diff --cached --name-only 2>/dev/null | xargs grep -l 'System\.out\.print\|log\.debug' 2>/dev/null | wc -l || echo "0")
  if [[ "$debug_logs" -gt 0 ]]; then
    log_warn "  Debug logs found in ${debug_logs} changed file(s)"
    diff_issues=$((diff_issues + 1))
  fi

  # Check for TODO/FIXME markers
  local todo_markers
  todo_markers=$(git diff --name-only 2>/dev/null | xargs grep -l 'TODO\|FIXME' 2>/dev/null | wc -l || echo "0")
  if [[ "$todo_markers" -gt 0 ]]; then
    log_warn "  TODO/FIXME markers in ${todo_markers} changed file(s)"
  fi

  if [[ "$diff_issues" -gt 0 ]]; then
    record_result "diff" "FAIL" "Diff review: ${diff_issues} issue(s) found"
  else
    record_result "diff" "PASS" ""
    RESULTS["diff_detail"]="${files_changed}"
  fi
}

# ── Generate Report ─────────────────────────────────────────────────────────
generate_report() {
  local report_file="$OUTPUT_FILE"
  local timestamp
  timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')

  {
    echo "=========================================="
    echo "  SPRING BOOT VERIFICATION REPORT"
    echo "=========================================="
    echo "Date:       ${timestamp}"
    echo "Project:    $(pwd)"
    echo "Build Tool: ${BUILD_TOOL}"
    echo "Threshold:  ${COVERAGE_THRESHOLD}% coverage"
    echo ""
    echo "------------------------------------------"
    echo "Phase Results"
    echo "------------------------------------------"
    for phase in build static test security lint diff; do
      local status="${RESULTS[$phase]:-SKIP}"
      local detail="${RESULTS[${phase}_detail]:-}"
      case "$status" in
        PASS)  echo -e "  ${phase^}:      \033[0;32mPASS\033[0m ${detail}" ;;
        FAIL)  echo -e "  ${phase^}:      \033[0;31mFAIL\033[0m ${detail}" ;;
        SKIP)  echo -e "  ${phase^}:      \033[1;33mSKIP\033[0m" ;;
      esac
    done
    echo ""
    echo "------------------------------------------"
    echo "Overall:    ${OVERALL}"
    echo "------------------------------------------"

    if [[ ${#ISSUES[@]} -gt 0 ]]; then
      echo ""
      echo "Issues to Fix:"
      local i=1
      for issue in "${ISSUES[@]}"; do
        echo "  ${i}. ${issue}"
        ((i++))
      done
    fi

    echo ""
    echo "=========================================="
  } | tee "$report_file"

  log_info "Report saved to: ${report_file}"
}

# ── Main Execution ──────────────────────────────────────────────────────────
main() {
  echo ""
  echo "=========================================="
  echo "  Spring Boot Verification Loop"
  echo "=========================================="
  echo ""

  phase_build

  # If build fails, stop early
  if [[ "${RESULTS[build]:-SKIP}" == "FAIL" ]]; then
    log_fail "Build failed — stopping pipeline. Fix build errors before continuing."
    generate_report
    exit 1
  fi

  if [[ "$QUICK_MODE" == true ]]; then
    phase_static
    phase_tests
  else
    phase_static
    phase_tests
    phase_security
    phase_lint
    phase_diff
  fi

  echo ""
  generate_report

  if [[ "$OVERALL" == "READY" ]]; then
    log_pass "All phases passed — project is READY for release/PR"
    exit 0
  else
    log_fail "One or more phases failed — project is NOT READY"
    exit 1
  fi
}

main "$@"
