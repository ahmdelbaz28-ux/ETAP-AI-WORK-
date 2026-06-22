# ==========================================================================
# ETAP AI — Enterprise Infrastructure Bundle Makefile
#
# Usage:
#   make repos        Add required Helm repositories
#   make secrets      Pre-create Redis + Postgres secrets (pass REDIS_PW=, POSTGRES_PW=)
#   make redis        Install Redis Cluster (6 nodes)
#   make postgres     Install Postgres HA via CloudNativePG (3 instances + PITR)
#   make app          Install the ETAP Helm chart (VALUES= override file)
#   make velero       Install Velero + daily/weekly schedules
#   make keda         Install KEDA + ScaledObjects for API + Worker
#   make chaos        Install Chaos Mesh + experiments + weekly game day
#   make verify       Run health checks across all components
#   make uninstall    Remove everything in reverse dependency order
#   make package      Create a tar.gz of this bundle for download
#   make lint         Lint all YAML files (requires yamllint)
#   make dry-run      Render all Helm templates without applying
# ==========================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Configurable paths
NAMESPACE      ?= etap
INFRA_NS       ?= etap-infra
CHART_DIR      ?= 01-helm-chart/etap-ai
VALUES         ?= $(CHART_DIR)/values-production.yaml
RELEASE        ?= etap-ai

# Tools (override if your binaries live elsewhere)
HELM           ?= helm
KUBECTL        ?= kubectl
VELERO         ?= velero

# Colors for pretty output
G := \033[32m
Y := \033[33m
R := \033[31m
N := \033[0m
INFO := echo "$(G)[$(shell date +%H:%M:%S)]$(N)"
WARN := echo "$(Y)[WARN]$(N)"
ERR  := echo "$(R)[ERROR]$(N)"

.PHONY: help repos secrets redis postgres app velero keda chaos verify uninstall package lint dry-run test validate integration-test

help: ## Show this help
        @grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
                awk 'BEGIN {FS = ":.*?## "}; {printf "  $(G)%-15s$(N) %s\n", $$1, $$2}'

repos: ## Add required Helm repositories
        @$(HELM) repo add bitnami      https://charts.bitnami.com/bitnami
        @$(HELM) repo add cnpg         https://cloudnative-pg.io/charts
        @$(HELM) repo add keda         https://kedacore.github.io/charts
        @$(HELM) repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
        @$(HELM) repo add chaos-mesh   https://charts.chaos-mesh.org
        @$(HELM) repo update
        @$(INFO) Helm repositories added

secrets: ## Pre-create Redis secret + ETAP API key (Postgres secret is auto-created by CNPG)
        @test -n "$(REDIS_PW)"     || { $(ERR) REDIS_PW is required; exit 1; }
        @test -n "$(API_KEY)"      || { $(ERR) API_KEY is required; exit 1; }
        @$(KUBECTL) apply -f 00-prerequisites/namespace.yaml
        @$(KUBECTL) -n $(NAMESPACE) create secret generic etap-redis-cluster \
                --from-literal=redis-password="$(REDIS_PW)" --dry-run=client -o yaml | \
                $(KUBECTL) apply -f -
        @$(KUBECTL) -n $(NAMESPACE) create secret generic etap-ai-secrets \
                --from-literal=api-key="$(API_KEY)" --dry-run=client -o yaml | \
                $(KUBECTL) apply -f -
        @$(INFO) Secrets created:
        @echo "  - etap-redis-cluster         (Redis Cluster password)"
        @echo "  - etap-ai-secrets            (ETAP API key)"
        @$(WARN) CloudNativePG will auto-create etap-postgres-app — do NOT create it manually.
        @$(WARN) You still need to create etap-postgres-backup secret with S3 creds:
        @echo "  kubectl -n $(NAMESPACE) create secret generic etap-postgres-backup \\"
        @echo "      --from-literal=AWS_ACCESS_KEY_ID=... \\"
        @echo "      --from-literal=AWS_SECRET_ACCESS_KEY=... \\"
        @echo "      --from-literal=AWS_REGION=us-east-1 \\"
        @echo "      --from-literal=AWS_ENDPOINT=https://s3.amazonaws.com"

redis: ## Install Redis Cluster (6 nodes)
        @$(INFO) Installing Redis Cluster...
        @$(HELM) upgrade --install etap-redis-cluster bitnami/redis-cluster \
                -n $(NAMESPACE) -f 02-redis-cluster/values.yaml
        @$(KUBECTL) -n $(NAMESPACE) rollout status statefulset/etap-redis-cluster --timeout=600s
        @$(INFO) Redis Cluster is ready

postgres: ## Install Postgres HA via CloudNativePG
        @$(INFO) Installing Postgres HA cluster...
        @if ! $(KUBECTL) get crd clusters.postgresql.cnpg.io >/dev/null 2>&1; then \
                $(ERR) CloudNativePG CRD not found. Install the operator first:; \
                echo "  kubectl apply -f https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.22/releases/cnpg-1.22.2.yaml"; \
                exit 1; \
        fi
        @$(KUBECTL) apply -f 03-postgres-ha/cnpg-cluster.yaml
        @$(KUBECTL) -n $(NAMESPACE) wait --for=condition=Ready cluster/etap-postgres --timeout=900s
        @$(INFO) Postgres HA cluster is ready

app: ## Install the ETAP Helm chart
        @$(INFO) Installing ETAP AI via Helm...
        @$(HELM) upgrade --install $(RELEASE) $(CHART_DIR) \
                -n $(NAMESPACE) -f $(VALUES)
        @$(KUBECTL) -n $(NAMESPACE) rollout status deploy/$(RELEASE)-api --timeout=300s
        @$(KUBECTL) -n $(NAMESPACE) rollout status deploy/$(RELEASE)-worker --timeout=300s
        @$(INFO) ETAP AI is live

velero: ## Install Velero + schedules
        @$(INFO) Installing Velero...
        @$(HELM) upgrade --install velero vmware-tanzu/velero \
                -n velero --create-namespace \
                -f 04-velero-backups/values.yaml
        @$(KUBECTL) -n velero wait --for=condition=available deploy/velero --timeout=180s
        @$(KUBECTL) -n velero get backupstoragelocation
        @$(INFO) Velero is ready (apply 04-velero-backups/backup-schedule.yaml if not via Helm values)

keda: ## Install KEDA + ScaledObjects for API + Worker
        @$(INFO) Installing KEDA...
        @$(HELM) upgrade --install keda keda/keda \
                -n $(INFRA_NS) --create-namespace \
                -f 05-keda-autoscaling/values.yaml
        @$(KUBECTL) -n $(INFRA_NS) wait --for=condition=available deploy/keda-operator --timeout=180s
        @$(INFO) Disabling built-in HPAs in the ETAP chart (KEDA will manage them)...
        @$(HELM) upgrade $(RELEASE) $(CHART_DIR) -n $(NAMESPACE) -f $(VALUES) \
                --set api.autoscaling.enabled=false \
                --set worker.autoscaling.enabled=false
        @$(KUBECTL) apply -f 05-keda-autoscaling/api-scaledobject.yaml
        @$(KUBECTL) apply -f 05-keda-autoscaling/worker-scaledobject.yaml
        @$(INFO) KEDA ScaledObjects are live

chaos: ## Install Chaos Mesh + experiments + weekly schedule
        @$(INFO) Installing Chaos Mesh...
        @$(HELM) upgrade --install chaos-mesh chaos-mesh/chaos-mesh \
                -n $(INFRA_NS) \
                -f 06-chaos-mesh/values.yaml
        @$(KUBECTL) -n $(INFRA_NS) wait --for=condition=available deploy/chaos-controller-manager --timeout=180s
        @$(INFO) Applying chaos experiments (individually; review before scheduling)...
        @for f in 06-chaos-mesh/experiments/*.yaml; do \
                echo "  applying $$f..."; \
                $(KUBECTL) apply -f $$f; \
        done
        @$(WARN) Weekly game-day schedule is NOT applied automatically.
        @echo "  After validating each experiment, run:"
        @echo "    kubectl apply -f 06-chaos-mesh/schedules/weekly-chaos-schedule.yaml"

verify: ## Run health checks across all components
        @$(INFO) Verifying ETAP AI stack...
        @echo ""
        @echo "$(G)=== Namespaces ===$(N)"
        @$(KUBECTL) get ns $(NAMESPACE) $(INFRA_NS) velero 2>/dev/null | grep -v NAME || true
        @echo ""
        @echo "$(G)=== Pods in $(NAMESPACE) ===$(N)"
        @$(KUBECTL) -n $(NAMESPACE) get pods -o wide | grep -v -E 'Completed|Terminating' || true
        @echo ""
        @echo "$(G)=== Helm releases ===$(N)"
        @$(HELM) list -A | grep -E 'etap|redis|velero|keda|chaos' || true
        @echo ""
        @echo "$(G)=== HPA + ScaledObjects ===$(N)"
        @$(KUBECTL) -n $(NAMESPACE) get hpa 2>/dev/null || true
        @$(KUBECTL) -n $(NAMESPACE) get scaledobjects 2>/dev/null || true
        @echo ""
        @echo "$(G)=== PDB ===$(N)"
        @$(KUBECTL) -n $(NAMESPACE) get pdb 2>/dev/null || true
        @echo ""
        @echo "$(G)=== Services ===$(N)"
        @$(KUBECTL) -n $(NAMESPACE) get svc 2>/dev/null || true
        @echo ""
        @echo "$(G)=== Recent events ===$(N)"
        @$(KUBECTL) -n $(NAMESPACE) get events --sort-by='.lastTimestamp' | tail -20
        @echo ""
        @echo "$(G)=== API health check ===$(N)"
        @$(KUBECTL) -n $(NAMESPACE) port-forward svc/$(RELEASE)-api 18000:8000 & \
                PORT_PID=$$!; sleep 3; \
                curl -fsS http://localhost:18000/health && echo " OK" || echo " FAIL"; \
                kill $$PORT_PID 2>/dev/null

uninstall: ## Remove everything in reverse dependency order
        @$(WARN) This will delete the entire ETAP stack. S3 backups are preserved.
        @test "$(CONFIRM)" = "yes" || { echo "Re-run with: make uninstall CONFIRM=yes"; exit 1; }
        @$(INFO) Removing chaos experiments...
        @$(KUBECTL) -n $(NAMESPACE) delete podchaos,networkchaos,stresschaos,iochaos,workflow --all 2>/dev/null || true
        @$(INFO) Removing KEDA ScaledObjects...
        @$(KUBECTL) -n $(NAMESPACE) delete scaledobject,triggerauthentication --all 2>/dev/null || true
        @$(INFO) Uninstalling ETAP Helm release...
        @$(HELM) -n $(NAMESPACE) uninstall $(RELEASE) 2>/dev/null || true
        @$(INFO) Uninstalling Velero...
        @$(HELM) -n velero uninstall velero 2>/dev/null || true
        @$(KUBECTL) delete ns velero 2>/dev/null || true
        @$(INFO) Removing Postgres cluster...
        @$(KUBECTL) -n $(NAMESPACE) delete cluster etap-postgres 2>/dev/null || true
        @$(INFO) Uninstalling Redis Cluster...
        @$(HELM) -n $(NAMESPACE) uninstall etap-redis-cluster 2>/dev/null || true
        @$(INFO) Uninstalling KEDA + Chaos Mesh...
        @$(HELM) -n $(INFRA_NS) uninstall keda 2>/dev/null || true
        @$(HELM) -n $(INFRA_NS) uninstall chaos-mesh 2>/dev/null || true
        @$(INFO) Deleting namespaces...
        @$(KUBECTL) delete ns $(NAMESPACE) $(INFRA_NS) 2>/dev/null || true
        @$(INFO) Uninstall complete. S3 backups preserved.

package: ## Create a downloadable tar.gz of this bundle
        @cd .. && tar -czf etap-enterprise-infra.tar.gz etap-enterprise-infra/
        @$(INFO) Created ../etap-enterprise-infra.tar.gz
        @ls -lh ../etap-enterprise-infra.tar.gz

lint: ## Lint all YAML files (requires yamllint) + shellcheck on .sh files
        @command -v yamllint >/dev/null 2>&1 || { $(ERR) yamllint not installed; exit 1; }
        @find . -name '*.yaml' -not -path '*/templates/*' -not -path './.git/*' | \
                xargs yamllint -d "{rules: {line-length: disable, document-start: disable, truthy: disable, indentation: {spaces: 2, indent-sequences: whatever}, comments: disable, comments-indentation: disable, empty-lines: {max: 2}, trailing-spaces: disable, braces: disable}}"
        @command -v shellcheck >/dev/null 2>&1 && \
                find . -name '*.sh' -not -path './.git/*' | xargs shellcheck -x || \
                $(WARN) shellcheck not installed, skipping

test: ## Run helm-unittest test suite (39 tests across 7 suites)
        @$(HELM) unittest 01-helm-chart/etap-ai

validate: ## Run full validation: lint + unittest + kubeconform (locally)
        @./scripts/validate.sh

integration-test: ## Spin up kind cluster, install chart, verify env vars (requires docker)
        @command -v kind >/dev/null 2>&1 || { $(ERR) kind not installed; exit 1; }
        @command -v docker >/dev/null 2>&1 || { $(ERR) docker not installed (kind needs it); exit 1; }
        @echo "$(G)This is what the CI pipeline does on every push. Running locally...$(N)"
        @.github/workflows/scripts/run-integration-test.sh

dry-run: ## Render all Helm templates without applying
        @$(INFO) Rendering ETAP chart templates...
        @$(HELM) template $(RELEASE) $(CHART_DIR) -n $(NAMESPACE) -f $(VALUES) > /tmp/etap-rendered.yaml
        @wc -l /tmp/etap-rendered.yaml
        @$(INFO) Rendered output is at /tmp/etap-rendered.yaml
