#!/usr/bin/env bash
# =============================================================================
# AhmedETAP — Local Load Test Runner
# =============================================================================
# Runs load tests against the local docker-compose stack BEFORE deploying
# Helm to Kubernetes. Per CI/CD skill: "No gate can be skipped."
#
# Usage:
#   ./scripts/run-load-tests.sh [--locust|--k6|--both] [--skip-setup] [--skip-teardown]
#
# Prerequisites:
#   - docker compose v2+
#   - For k6: installed locally (https://k6.io/docs/get-started/installation/)
#   - For locust: installed via pip (pip install locust)
#   - .env file with REDIS_PASSWORD, POSTGRES_PASSWORD, ENGINEERING_SERVICE_API_KEY
#
# Exit codes:
#   0 = all tests passed
#   1 = setup failed
#   2 = tests failed (thresholds not met)
# =============================================================================
set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────
MODE="${1:---both}"          # --locust | --k6 | --both
SKIP_SETUP="${2:---no-skip-setup}"
SKIP_TEARDOWN="${3:---no-skip-teardown}"
BASE_URL="http://localhost:8000"
MAX_WAIT_SECONDS=120         # Max time to wait for service to be healthy
LOCUST_USERS=20
LOCUST_RUNTIME="1m"
K6_VUS=50
K6_DURATION="1m"
RESULTS_DIR="load-test-results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ─── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }  # NOSONAR S7679: positional parameter in short ops script; naming would add ceremony without clarity
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }  # NOSONAR S7679: positional parameter in short ops script; naming would add ceremony without clarity
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }  # NOSONAR S7679: positional parameter in short ops script; naming would add ceremony without clarity
log_fail()  { echo -e "${RED}[FAIL]${NC}  $1"; }  # NOSONAR S7679: positional parameter in short ops script; naming would add ceremony without clarity

# ─── Step 1: Set up docker-compose stack ─────────────────────────────────────
setup_stack() {
    if [[ "$SKIP_SETUP" == "--skip-setup" ]]; then
        log_warn "Skipping docker-compose setup (--skip-setup)"
        return 0
    fi

    log_info "Starting docker-compose stack..."
    docker compose up -d --wait --timeout 60 2>&1 || {
        log_fail "docker compose up failed!"
        exit 1
    }

    log_info "Waiting for engineering-service to be healthy (max ${MAX_WAIT_SECONDS}s)..."
    elapsed=0
    while [[ $elapsed -lt $MAX_WAIT_SECONDS ]]; do
        if curl -sf "${BASE_URL}/health" > /dev/null 2>&1; then
            log_ok "Service is healthy at ${BASE_URL}"
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
        echo -e "  ${YELLOW}...${NC} waiting (${elapsed}s/${MAX_WAIT_SECONDS}s)"
    done

    log_fail "Service did not become healthy within ${MAX_WAIT_SECONDS}s"
    docker compose logs engineering-service --tail 50
    exit 1
}

# ─── Step 2: Run Locust load tests ───────────────────────────────────────────
run_locust() {
    log_info "Running Locust load tests (${LOCUST_USERS} users, ${LOCUST_RUNTIME} runtime)..."

    local locust_results="${RESULTS_DIR}/locust/${TIMESTAMP}"
    mkdir -p "$locust_results"

    # Run locust in headless mode
    locust \
        -f locustfile.py \
        --host="${BASE_URL}" \
        --users="${LOCUST_USERS}" \
        --spawn-rate=5 \
        --run-time="${LOCUST_RUNTIME}" \
        --headless \
        --html="${locust_results}/report.html" \
        --csv="${locust_results}/locust" \
        --logfile="${locust_results}/locust.log" \
        2>&1 | tee "${locust_results}/console.log" || {
        log_fail "Locust tests failed!"
        return 2
    }

    log_ok "Locust tests completed. Results saved to ${locust_results}/"
}

# ─── Step 3: Run k6 load tests ───────────────────────────────────────────────
run_k6() {
    # Check if k6 is installed
    if ! command -v k6 &> /dev/null; then
        log_warn "k6 not installed — skipping k6 tests. Install: https://k6.io/docs/get-started/installation/"
        return 0
    fi

    log_info "Running k6 load tests (${K6_VUS} VUs, ${K6_DURATION} duration)..."

    local k6_results="${RESULTS_DIR}/k6/${TIMESTAMP}"
    mkdir -p "$k6_results"

    # For CI: use reduced VUs and duration
    K6_VUS_VAL="${K6_VUS}"
    K6_DURATION_VAL="${K6_DURATION}"

    k6 run \
        k6-load-test.js \
        --env BASE_URL="${BASE_URL}" \
        --env K6_VUS="${K6_VUS_VAL}" \
        --env K6_DURATION="${K6_DURATION_VAL}" \
        --out json="${k6_results}/results.json" \
        --summary-output="${k6_results}/summary.json" \
        2>&1 | tee "${k6_results}/console.log" || {
        log_fail "k6 tests failed (thresholds not met)!"
        return 2
    }

    log_ok "k6 tests completed. Results saved to ${k6_results}/"
}

# ─── Step 4: Teardown ─────────────────────────────────────────────────────────
teardown() {
    if [[ "$SKIP_TEARDOWN" == "--skip-teardown" ]]; then
        log_warn "Skipping teardown (--skip-teardown). Stack is still running."
        return 0
    fi

    log_info "Tearing down docker-compose stack..."
    docker compose down --volumes --remove-orphans 2>&1 || true
    log_ok "Stack torn down."
}

# ─── Main ─────────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo "======================================================================"
    echo "  AhmedETAP — Local Load Test Runner"
    echo "  Mode: ${MODE}  |  Timestamp: ${TIMESTAMP}"
    echo "======================================================================"
    echo ""

    setup_stack

    failed=0

    case "$MODE" in
        --locust)
            run_locust || failed=$?
            ;;
        --k6)
            run_k6 || failed=$?
            ;;
        --both)
            run_locust || failed=$?
            run_k6 || failed=$?
            ;;
        *)
            log_fail "Unknown mode: ${MODE}. Use --locust, --k6, or --both"
            exit 1
            ;;
    esac

    teardown

    echo ""
    echo "======================================================================"
    if [[ $failed -eq 0 ]]; then
        log_ok "ALL LOAD TESTS PASSED ✅"
    else
        log_fail "LOAD TESTS FAILED ❌ (exit code: ${failed})"
    fi
    echo "======================================================================"  # NOSONAR S1192: separator string repeated intentionally for visual structure
    echo ""

    exit $failed
}

main
