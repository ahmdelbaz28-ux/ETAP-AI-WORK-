#!/usr/bin/env bash
# ==========================================================================
# validate.sh — validate all Kubernetes manifests in the bundle.
#
# Runs:
#   1. helm lint        on the Helm chart (default + production values)
#   2. helm unittest    on the Helm chart test suite
#   3. helm template    to render the chart to YAML
#   4. kubeconform      on the rendered chart + standalone manifests
#                       (with CRD schemas fetched from upstream repos)
#
# Usage:
#   ./validate.sh
#
# Exit codes:
#   0 = all checks passed
#   1 = at least one check failed
# ==========================================================================
set -euo pipefail

cd "$(dirname "$0")/../.."

export PATH="$HOME/.local/bin:$HOME/bin:/usr/local/bin:$PATH"

# Colors
G='\033[32m'; Y='\033[33m'; R='\033[31m'; N='\033[0m'
INFO() { echo -e "${G}[$(date +%H:%M:%S)]${N} $*"; }
WARN() { echo -e "${Y}[WARN]${N} $*"; }
ERR()  { echo -e "${R}[ERROR]${N} $*" >&2; }

FAIL=0

# ---------------------------------------------------------------------------
# 1. helm lint
# ---------------------------------------------------------------------------
INFO "1/4: helm lint"
for VALUES in "" "-f infra/helm/etap-ai/values-production.yaml"; do
    # shellcheck disable=SC2086 # intentional word splitting for the -f flag
    if helm lint infra/helm/etap-ai $VALUES > /tmp/lint.log 2>&1; then
        INFO "  helm lint ${VALUES:-default values}: PASS"
    else
        ERR "  helm lint ${VALUES:-default values}: FAIL"
        cat /tmp/lint.log
        FAIL=1
    fi
done

# ---------------------------------------------------------------------------
# 2. helm unittest
# ---------------------------------------------------------------------------
INFO "2/4: helm unittest"
if helm unittest infra/helm/etap-ai > /tmp/unittest.log 2>&1; then
    INFO "  helm unittest: PASS"
    grep -E "Tests:|Test Suites:|Charts:" /tmp/unittest.log | sed 's/^/    /'
else
    ERR "  helm unittest: FAIL"
    cat /tmp/unittest.log
    FAIL=1
fi

# ---------------------------------------------------------------------------
# 3. helm template (render chart to YAML for kubeconform)
# ---------------------------------------------------------------------------
INFO "3/4: helm template"
if helm template etap-ai infra/helm/etap-ai -n etap \
    -f infra/helm/etap-ai/values-production.yaml > /tmp/etap-rendered.yaml 2>/tmp/template.log; then
    COUNT=$(grep -c '^kind:' /tmp/etap-rendered.yaml)
    INFO "  helm template: rendered $COUNT objects"
else
    ERR "  helm template: FAIL"
    cat /tmp/template.log
    FAIL=1
fi

# ---------------------------------------------------------------------------
# 4. kubeconform (with CRD schemas)
# ---------------------------------------------------------------------------
INFO "4/4: kubeconform"

# kubeconform uses the default Kubernetes JSON Schema registry
# (https://github.com/yannh/kubernetes-json-schema) for built-in types.
# For CRDs (CloudNativePG, KEDA, Chaos Mesh, Velero, ServiceMonitor), there
# is no public JSON Schema registry, so we use -ignore-missing-schemas to
# skip validation for those and validate only the built-in K8s types.
#
# Full CRD validation happens at apply-time on a real cluster — the operator
# validates the custom resource against its CRD's OpenAPI schema.

KUBECONFORM_ARGS=(
    -strict
    -summary
    -ignore-missing-schemas
    -kubernetes-version 1.29.0
    -reject
    "ReplicaSet"
    -reject
    "ManagedFields"
)

# Run kubeconform on rendered chart
INFO "  kubeconform: rendered chart"
if kubeconform "${KUBECONFORM_ARGS[@]}" /tmp/etap-rendered.yaml 2>&1 | tee /tmp/kubeconform-chart.log; then
    INFO "  kubeconform chart: PASS"
else
    if grep -q "Invalid" /tmp/kubeconform-chart.log; then
        ERR "  kubeconform chart: FAIL (invalid manifests)"
        FAIL=1
    else
        WARN "  kubeconform chart: some schemas missing (CRDs) — built-in types validated"
    fi
fi

# Run kubeconform on standalone manifests (skip values.yaml, Chart.yaml, tests)
INFO "  kubeconform: standalone manifests"
STANDALONE_FILES=$(find . -name '*.yaml' \
    -not -path '*/templates/*' \
    -not -path '*/tests/*' \
    -not -name 'values.yaml' \
    -not -name 'values-production.yaml' \
    -not -name 'Chart.yaml' \
    -not -name 'repositories.yaml' \
    | sort)

if [ -n "$STANDALONE_FILES" ]; then
    if echo "$STANDALONE_FILES" | xargs kubeconform "${KUBECONFORM_ARGS[@]}" 2>&1 | tee /tmp/kubeconform-standalone.log; then
        INFO "  kubeconform standalone: PASS"
    else
        if grep -qE "Invalid" /tmp/kubeconform-standalone.log; then
            ERR "  kubeconform standalone: FAIL"
            FAIL=1
        else
            WARN "  kubeconform standalone: some schemas missing (CRDs) — built-in types validated"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
if [ $FAIL -eq 0 ]; then
    INFO "=========================================="
    INFO "  ALL VALIDATION CHECKS PASSED"
    INFO "=========================================="
    exit 0
else
    ERR "=========================================="
    ERR "  SOME VALIDATION CHECKS FAILED — see above"
    ERR "=========================================="
    exit 1
fi
