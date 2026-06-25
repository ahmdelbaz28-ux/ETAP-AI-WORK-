# ETAP AI Engineering Platform - Makefile
# Usage: make <target>

.PHONY: help install test run build docker-up docker-down clean docs lint format validate deploy-k8s

# Cross-platform support
ifeq ($(OS),Windows_NT)
    PYTHON := .venv312/Scripts/python
    PIP    := .venv312/Scripts/pip
    ACTIVATE := .venv312/Scripts/activate
else
    PYTHON := .venv/bin/python
    PIP    := .venv/bin/pip
    ACTIVATE := .venv/bin/activate
endif

# Default target
help: ## Show this help message
        @echo "ETAP AI Engineering Platform - Available Commands"
        @echo "=================================================="
        @echo ""
        @grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation
install: ## Install all dependencies
        @echo "Installing Python dependencies (Python 3.12)..."
        $(PIP) install -r requirements.txt
        @echo "Installing Node.js dependencies..."
        pnpm install
        @echo "Installation complete!"
        @echo "Activate the venv:  source $(ACTIVATE)"

test: ## Run all tests
        @echo "Running validation suite..."
        $(PYTHON) validation_suite.py
        @echo ""
        @echo "Running unit tests..."
        $(PYTHON) -m pytest tests/unit_tests.py -v --cov=. --cov-report=html
        @echo ""
        @echo "Tests complete! Check htmlcov/index.html for coverage report"

run: ## Start the platform in development mode
        @echo "Starting ETAP AI Platform..."
        @echo "Open two terminals:"
        @echo "  Terminal 1: $(PYTHON) engineering_service.py"
        @echo "  Terminal 2: pnpm dev"

run-backend: ## Start Python backend only
        $(PYTHON) engineering_service.py

run-frontend: ## Start Mastra frontend only
        pnpm dev

# Docker
build: ## Build Docker image
        docker build -t etap-ai-platform:latest .

docker-up: ## Start services with Docker Compose
        docker-compose up -d
        @echo "Services started! Access at http://localhost:3000"

docker-down: ## Stop Docker services
        docker-compose down

docker-logs: ## View Docker logs
        docker-compose logs -f

docker-restart: ## Restart Docker services
        docker-compose restart

# Development
lint: ## Run linters
        @echo "Linting Python code (ruff)..."
        $(PYTHON) -m ruff check . --config ruff.toml
        @echo "Linting TypeScript code..."
        pnpm lint

format: ## Format code
        @echo "Formatting Python code (ruff)..."
        $(PYTHON) -m ruff format . --config ruff.toml
        @echo "Formatting TypeScript code..."
        pnpm format

validate: ## Run validation suite
        $(PYTHON) validation_suite.py

clean: ## Clean build artifacts and cache
        @echo "Cleaning Python artifacts..."
        find . -type d -name __pycache__ -exec rm -rf {} +
        find . -type f -name "*.pyc" -delete
        find . -type f -name "*.pyo" -delete
        find . -type d -name "*.egg-info" -exec rm -rf {} +
        rm -rf build/ dist/ .pytest_cache/ .coverage htmlcov/
        @echo "Cleaning Node.js artifacts..."
        rm -rf node_modules/
        @echo "Clean complete!"

# Documentation
docs: ## Generate documentation
        @echo "Generating API documentation..."
        pnpm docs
        @echo "Documentation generated!"

# Deployment
deploy-docker: ## Deploy using Docker
        @echo "Building and deploying with Docker..."
        make build
        docker-compose up -d
        @echo "Deployment complete! Check: docker-compose ps"

deploy-k8s: ## Deploy to Kubernetes
        @echo "Deploying to Kubernetes..."
        kubectl apply -f k8s-deployment.yaml
        @echo "Waiting for deployment..."
        kubectl rollout status deployment/etap-platform -n etap-platform
        @echo "Kubernetes deployment complete!"

deploy-local: ## Quick local deployment
        @echo "Quick start..."
        chmod +x quickstart.sh
        ./quickstart.sh

# Monitoring
health: ## Check platform health
        curl -f http://localhost:3000/health || echo "Platform not responding"

logs: ## View application logs
        tail -f logs/app.log

status: ## Show service status
        @echo "=== Docker Services ==="
        docker-compose ps
        @echo ""
        @echo "=== Health Check ==="
        make health

# Database
db-backup: ## Backup database
        @echo "Backing up database..."
        cp mastra.db mastra.db.backup.$$(date +%Y%m%d_%H%M%S)
        @echo "Backup complete!"

db-restore: ## Restore database from backup
        @echo "Available backups:"
        @ls -lt mastra.db.backup.* | head -5
        @read -p "Enter backup file to restore: " backup; \
        cp $$backup mastra.db
        @echo "Restore complete!"

# CI/CD
# Security
security-audit: ## Run all security scans locally
        @echo "=== Security Audit (Python 3.12) ==="
        @echo ""
        @echo "— npm audit —"
        pnpm audit --audit-level=high 2>&1 || echo "⚠  npm audit warnings above"
        @echo ""
        @echo "— pip-audit —"
        $(PIP) install pip-audit -q 2>&1 || true
        $(PYTHON) -m pip_audit 2>&1 || echo "⚠  pip-audit warnings above"
        @echo ""
        @echo "— Trivy (filesystem) —"
        @command -v trivy >/dev/null 2>&1 && trivy fs --severity CRITICAL,HIGH . || echo "trivy not installed — install from https://trivy.dev"
        @echo ""
        @echo "— TruffleHog (secrets) —"
        @command -v trufflehog >/dev/null 2>&1 && trufflehog filesystem --no-verification . || echo "trufflehog not installed — install from https://github.com/trufflesecurity/trufflehog"
        @echo ""
        @echo "Security audit done!"

security-ci: ## Install CI security tools locally (for testing GitHub Actions locally)
        @echo "Installing CI security tools in .venv312..."
        $(PIP) install pip-audit
        @echo "Done. Run 'make security-audit' to execute scans."

ci-test: ## Run CI tests
        @echo "Running CI pipeline..."
        make lint
        make test
        make validate
        @echo "CI pipeline complete!"

ci-build: ## Build for CI
        @echo "Building for CI..."
        make build
        docker-compose -f docker-compose.yml config
        @echo "CI build complete!"

# Utilities
env-setup: ## Setup environment file
        @if [ ! -f .env ]; then \
                echo "Creating .env from template..."; \
                cp .env.example .env; \
                echo "Please edit .env with your configuration"; \
        else \
                echo ".env already exists"; \
        fi

check-deps: ## Check if all dependencies are installed
        @echo "Checking Python dependencies (Python 3.12)..."
        @$(PYTHON) -c "import numpy; import scipy; import pandas; print('✓ Python deps OK')" || echo "✗ Python deps missing"
        @echo "Checking Node.js dependencies..."
        @pnpm list | head -5
        @echo "Dependency check complete!"

version: ## Show version information
        @echo "ETAP AI Engineering Platform v2.1.0"
        @echo "Python: $$($(PYTHON) --version)"
        @echo "Node: $$(node --version)"
        @echo "Docker: $$(docker --version 2>/dev/null || echo 'Not installed')"
        @echo "Kubectl: $$(kubectl version --client --short 2>/dev/null || echo 'Not installed')"
