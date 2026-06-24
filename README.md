---
title: AhmedETAP
emoji: "⚡"
colorFrom: yellow
colorTo: red
sdk: docker
pinned: false
license: mit
app_port: 7860
---

<div align="center">

# ⚡ AhmedETAP

### Enterprise-Grade Autonomous Engineering Intelligence Platform

*Power System Analysis · AI Agent Orchestration · ETAP Integration · GIS Enrichment*

[![Version](https://img.shields.io/badge/version-1.0.0-blue?style=for-the-badge&logo=semantic-release)](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/releases)
[![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge&logo=open-source-initiative)](LICENSE)
[![CI/CD](https://img.shields.io/github/actions/workflow/status/ahmdelbaz28-ux/ETAP-AI-WORK-/ci-cd.yml?style=for-the-badge&label=CI%2FCD&logo=github-actions)](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/actions)
[![Python](https://img.shields.io/badge/python-3.12-blue?style=for-the-badge&logo=python)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react)](https://react.dev)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker)](Dockerfile)

[![Live Demo](https://img.shields.io/badge/🤗%20Live%20Demo-Hugging%20Face-yellow?style=flat-square&logo=huggingface)](https://huggingface.co/spaces/ahmdelbaz28/AHMEDETAP)
[![Tests](https://img.shields.io/badge/tests-989%20passing-brightgreen?style=flat-square&logo=pytest)](tests/)
[![Index](https://img.shields.io/badge/project%20index-auto--updated-blueviolet?style=flat-square)](PROJECT_INDEX.md)

</div>

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Key Capabilities](#-key-capabilities)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [API Reference](#-api-reference)
- [Project Structure](#-project-structure)
- [Configuration](#-configuration)
- [Testing](#-testing)
- [Deployment](#-deployment)
- [Contributing](#-contributing)
- [Security](#-security)
- [Documentation Portal](#-documentation-portal)
- [License](#-license)

---

## 🔭 Overview

**AhmedETAP** is a production-ready, AI-powered platform for electrical power system engineering. It combines a multi-agent AI orchestration layer with rigorous numerical power system solvers, enabling engineers to run complex studies — load flow, fault analysis, arc flash, harmonic analysis, optimal power flow — through a conversational interface, REST API, or React web dashboard.

The platform is built to enterprise standards with full security hardening (ABAC, MFA, RASP, SIEM), observability (Prometheus + Grafana), and automated CI/CD to Hugging Face Spaces and Docker registries.

| Dimension | Detail |
|:---|:---|
| **Backend** | Python 3.12 · FastAPI · Celery · Redis · SQLite/PostgreSQL |
| **Frontend** | React 19 · Vite 6 · TypeScript · Tailwind CSS 4 |
| **AI Stack** | Multi-agent orchestration · RAG · GNN · ETAP Expert agent |
| **Infrastructure** | Docker · Helm · Terraform · GitHub Actions |
| **Standards** | IEEE 1584 · IEC 60909 · IEEE 519 · NFPA 70E |

---

## 🚀 Key Capabilities

### 🔌 Power System Analysis Engines
| Study Type | Standard | Engine |
|:---|:---|:---|
| Load Flow (Newton-Raphson) | IEEE | `load_flow/load_flow.py` |
| Short Circuit (Symmetrical & Asymmetrical) | IEC 60909 | `fault_analysis/iec60909_engine.py` |
| Arc Flash Hazard Analysis | IEEE 1584-2018 | `fault_analysis/ieee1584_database.py` |
| Harmonic Analysis & THD/TDD | IEEE 519 | `fault_analysis/harmonic_analysis.py` |
| Optimal Power Flow (DC & AC) | IEEE | `load_flow/optimal_power_flow.py` |
| Protection Coordination | IEEE | `coordination/` |

### 🤖 AI Agent System
- **Chief Orchestrator Agent** — decomposes requests, coordinates specialist agents
- **ETAP Expert Agent** — conversational power system Q&A with RAG over IEEE/IEC documents
- **ETAP GUI Agent** — step-by-step GUI workflow guidance
- **Load Flow Agent** — autonomous load flow study execution
- **Short Circuit Agent** — fault analysis and reporting
- **Harmonic Analysis Agent** — IEEE 519 compliance checks
- **OPF Agent** — optimal dispatch and generation scheduling
- **Protection Agent** — relay coordination and grading
- **Validation Agent** — results verification against engineering standards
- **Report Agent** — PDF / DOCX / XLSX report generation

### 🔐 Enterprise Security
- ABAC (Attribute-Based Access Control) with policy engine
- Multi-Factor Authentication (TOTP + WebAuthn/FIDO2)
- RASP (Runtime Application Self-Protection)
- SIEM event forwarding
- JWT + API Key authentication
- Secrets Manager (Vault-compatible + local)

### 📊 Observability & Operations
- Prometheus metrics endpoint (`/prometheus/metrics`)
- Grafana dashboard templates
- Structured audit logging
- Redis caching layer
- Celery async task workers
- Digital Twin live status

---

## 🏛️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERFACES                         │
│  React Web UI  │  REST API  │  CLI  │  MCP Protocol         │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / WebSocket
┌──────────────────────────▼──────────────────────────────────┐
│                  FASTAPI GATEWAY (api/)                      │
│  Auth · Rate Limiting · ABAC · RASP · Request Validation    │
└──────┬──────────┬──────────┬──────────┬───────────┬─────────┘
       │          │          │          │           │
┌──────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐
│ Studies  │ │  RAG   │ │  ML   │ │ SCADA  │ │Security│
│  API     │ │  API   │ │  API  │ │  API   │ │  API   │
└──────┬───┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
       │          │          │          │           │
┌──────▼──────────▼──────────▼──────────▼───────────▼────────┐
│                 ORCHESTRATION LAYER (agents/)                │
│         Chief Orchestrator Agent                            │
│   ┌──────────┬──────────┬──────────┬──────────┬──────────┐ │
│   │Load Flow │  Short   │Harmonic  │   OPF    │Protection│ │
│   │  Agent   │ Circuit  │  Agent   │  Agent   │  Agent   │ │
│   └──────────┴──────────┴──────────┴──────────┴──────────┘ │
│         Validation Agent  ·  Report Agent                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              COMPUTATION LAYER                               │
│  load_flow/  │  fault_analysis/  │  engine/  │  ml/         │
│  solver.py   │  iec60909_engine  │  network  │  predictive  │
│  opf.py      │  ieee1584_db      │  solvers  │  gnn.py      │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              DATA & PERSISTENCE LAYER                        │
│  SQLite / PostgreSQL  │  Redis Cache  │  Vector DB (RAG)    │
│  Celery + Workers     │  SCADA Models │  Engineering Docs   │
└─────────────────────────────────────────────────────────────┘
```

**Full architecture document:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## ⚡ Quick Start

### Prerequisites

| Tool | Version |
|:---|:---|
| Python | 3.12+ |
| Node.js | 20+ |
| Docker | 24+ |
| Redis | 7+ |

### Option 1 — Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
cd ETAP-AI-WORK-

# Copy environment template
cp .env.example .env
# Edit .env with your secrets

# Start all services
docker compose up -d

# Services will be available at:
#   API:       http://localhost:8000
#   Frontend:  http://localhost:3000
#   Metrics:   http://localhost:8000/prometheus/metrics
```

### Option 2 — Local Development

```bash
# ── Backend ──────────────────────────────────────────────
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

pip install -r requirements.txt

# Start the API server
python engineering_service.py

# Start Celery worker (in a separate terminal)
celery -A worker.celery_app worker --loglevel=info

# ── Frontend ─────────────────────────────────────────────
cd ui
npm install
npm run dev
# → http://localhost:5173
```

### Option 3 — Hugging Face Demo

No setup required. Access the live demo instantly:

👉 **[huggingface.co/spaces/ahmdelbaz28/AHMEDETAP](https://huggingface.co/spaces/ahmdelbaz28/AHMEDETAP)**

---

## 🌐 API Reference

**Base URL:** `http://localhost:8000`  
**API Version:** `v1` (prefix: `/api/v1/`)

### Authentication

All protected endpoints require a JWT bearer token:
```
Authorization: Bearer <token>
```

Obtain a token via `POST /api/v1/auth/login`.

### Core Endpoints

| Method | Endpoint | Description | Auth |
|:---|:---|:---|:---:|
| `GET` | `/health` | Liveness check | ❌ |
| `GET` | `/ready` | Readiness check | ❌ |
| `GET` | `/metrics` | Application metrics | ❌ |
| `GET` | `/prometheus/metrics` | Prometheus scrape endpoint | ❌ |
| `POST` | `/api/v1/studies/run` | Execute a power system study | ✅ |
| `POST` | `/api/v1/system/validate` | Validate system topology | ✅ |
| `POST` | `/api/v1/rag/query` | RAG knowledge base query | ✅ |
| `GET` | `/api/v1/agents/info` | List all available agents | ✅ |
| `GET` | `/api/v1/scada/live` | Live SCADA telemetry | ✅ |
| `GET` | `/api/v1/digital-twin/status` | Digital Twin status | ✅ |
| `POST` | `/api/v1/predict/load` | ML load forecasting | ✅ |
| `POST` | `/api/v1/predict/fault` | ML fault prediction | ✅ |
| `POST` | `/api/v1/predict/anomaly` | Anomaly detection | ✅ |
| `POST` | `/api/v1/auth/mfa/totp/setup` | Enable TOTP MFA | ✅ |
| `POST` | `/api/v1/auth/mfa/totp/verify` | Verify TOTP code | ✅ |
| `POST` | `/api/v1/auth/abac/check` | ABAC permission check | ✅ |
| `GET` | `/api/v1/security/rasp/stats` | RASP runtime stats | ✅ |
| `POST` | `/api/v1/security/siem/event` | Submit SIEM event | ✅ |
| `GET` | `/api/v1/benchmark` | Performance benchmark | ✅ |
| `POST` | `/etap-expert/chat` | ETAP Expert AI chat | ✅ |
| `POST` | `/etap-gui/chat` | ETAP GUI Agent chat | ✅ |
| `POST` | `/gnn/predict` | Graph Neural Network prediction | ✅ |

**Full API Reference:** [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)

### Example — Run a Load Flow Study

```bash
curl -X POST http://localhost:8000/api/v1/studies/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "study_type": "load_flow",
    "system": {
      "buses": [
        {"id": "B1", "base_kv": 11.0, "bus_type": "slack"},
        {"id": "B2", "base_kv": 11.0, "bus_type": "load"}
      ],
      "lines": [
        {"from_bus": "B1", "to_bus": "B2", "r_pu": 0.01, "x_pu": 0.05, "b_pu": 0.0}
      ],
      "loads": [
        {"bus": "B2", "p_mw": 10.0, "q_mvar": 3.0}
      ]
    }
  }'
```

### Example — ETAP Expert Chat

```bash
curl -X POST http://localhost:8000/etap-expert/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the difference between a 3-phase and line-to-ground fault in IEC 60909?",
    "session_id": "sess-001"
  }'
```

---

## 📁 Project Structure

```
etap-ai-work/
│
├── 📄 engineering_service.py    # Application entry point
├── 📄 indexer.py                # Codebase auto-indexer
├── 📄 PROJECT_INDEX.json        # Machine-readable project index (auto-generated)
├── 📄 PROJECT_INDEX.md          # Human-readable project index (auto-generated)
│
├── 📂 api/                      # FastAPI route handlers
│   ├── routes.py                # Main router (studies, health, metrics)
│   ├── agents.py                # AI agent endpoints
│   ├── ai_ml.py                 # ML prediction endpoints
│   ├── scada.py                 # SCADA live data
│   ├── digital_twin.py          # Digital twin status
│   ├── mfa.py                   # MFA endpoints
│   ├── validation.py            # System validation
│   ├── health.py                # Health & readiness probes
│   └── dependencies.py          # Auth dependencies / user context
│
├── 📂 agents/                   # AI agent implementations
│   ├── orchestrator.py          # Chief Orchestrator Agent
│   ├── load_flow_agent.py       # Load Flow specialist
│   ├── short_circuit_agent.py   # Short Circuit specialist
│   ├── harmonic_agent.py        # Harmonic Analysis specialist
│   ├── opf_agent.py             # OPF specialist
│   ├── protection_agent.py      # Protection Coordination specialist
│   ├── validation_agent.py      # Results validator
│   ├── report_agent.py          # Report generator
│   ├── etap_agent.py            # ETAP integration agent
│   └── rag_agent.py             # RAG knowledge retrieval agent
│
├── 📂 load_flow/                # Power system load flow solvers
│   ├── load_flow.py             # Newton-Raphson solver
│   ├── optimal_power_flow.py    # DC/AC OPF engine
│   └── solver.py                # Sparse matrix solver utilities
│
├── 📂 fault_analysis/           # Fault and arc flash engines
│   ├── iec60909_engine.py       # IEC 60909 short circuit engine
│   ├── ieee1584_database.py     # IEEE 1584-2018 arc flash engine
│   └── harmonic_analysis.py    # Harmonic + IEEE 519 compliance
│
├── 📂 security/                 # Enterprise security framework
│   ├── security_framework.py   # Auth, AuthZ, sessions
│   ├── abac.py                  # Attribute-Based Access Control
│   ├── mfa.py                   # TOTP + WebAuthn/FIDO2
│   ├── rasp.py                  # Runtime Application Self-Protection
│   ├── siem.py                  # SIEM event forwarding
│   └── secrets_manager.py      # Secrets & API key management
│
├── 📂 ml/                       # Machine learning models
│   └── predictive.py            # Load forecasting, fault prediction, anomaly detection, GNN
│
├── 📂 services/                 # Business logic services
│   ├── study_service.py         # Study orchestration logic
│   └── cache_service.py         # Redis cache abstraction
│
├── 📂 worker/                   # Async task workers
│   ├── celery_app.py            # Celery app configuration
│   └── tasks.py                 # Async study execution tasks
│
├── 📂 core/                     # Application core & bootstrap
├── 📂 engine/                   # Network computation engine
├── 📂 digital_twin/             # Digital twin model
├── 📂 reporting/                # Report generation (PDF/DOCX/XLSX)
├── 📂 coordination/             # Protection coordination
├── 📂 scada_model/              # SCADA data models
├── 📂 etap_integration/         # ETAP software integration layer
│
├── 📂 ui/                       # React 19 + Vite 6 frontend
│   └── src/
│       ├── pages/               # Application pages (50 UI files)
│       ├── components/          # Reusable UI components
│       ├── hooks/               # React custom hooks
│       ├── store/               # State management
│       └── utils/               # Frontend utilities
│
├── 📂 tests/                    # Test suite
│   ├── conftest.py              # Shared fixtures
│   └── test_*.py                # 58 test files · 989 tests
│
├── 📂 docs/                     # Full documentation portal
│   ├── ARCHITECTURE.md          # System architecture deep-dive
│   ├── API_REFERENCE.md         # Complete API documentation
│   ├── OPERATIONS_RUNBOOK.md    # Production operations guide
│   ├── TROUBLESHOOTING_GUIDE.md # Debugging and diagnostics
│   ├── COMPLIANCE.md            # Standards compliance reference
│   ├── SECURITY_OPERATIONS_MANUAL.md
│   └── AR/                      # Arabic documentation
│
├── 📂 .github/
│   ├── workflows/
│   │   ├── ci-cd.yml            # Main CI/CD pipeline
│   │   ├── auto-index.yml       # Auto-update project index
│   │   ├── security.yml         # Security scanning
│   │   └── sync-hf-space.yml    # Hugging Face Space deployment
│   └── ISSUE_TEMPLATE/
│
├── 📂 helm/                     # Kubernetes Helm chart
├── 📂 terraform/                # Infrastructure as Code
├── 📄 docker-compose.yml        # Multi-service orchestration
├── 📄 Dockerfile                # Main application image
├── 📄 Dockerfile.engineering-service
├── 📄 pyproject.toml            # Python project configuration
└── 📄 requirements.txt          # Python dependencies
```

---

## ⚙️ Configuration

All configuration is managed via environment variables. Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

### Core Variables

```env
# Application
ENVIRONMENT=production           # development | staging | production
PORT=8000
HOST=0.0.0.0
SECRET_KEY=<random-256-bit-hex>

# Database
DATABASE_URL=sqlite+aiosqlite:///./etap.db
# For production: postgresql+asyncpg://user:pass@host/db

# Redis Cache
REDIS_URL=redis://localhost:6379/0

# ETAP Integration
USE_ETAP=false                   # true to enable ETAP software bridge
ETAP_HOST=localhost
ETAP_PORT=5000

# Security
JWT_SECRET_KEY=<random-secret>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Observability
LANGWATCH_API_KEY=<optional>
PROMETHEUS_ENABLED=true
```

**Full configuration reference:** [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md)

---

## 🧪 Testing

The project maintains a **989-test** suite across **58 test files**:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=. --cov-report=html --cov-report=term-missing

# Run specific categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m regression    # Regression tests only

# Run a specific module
pytest tests/test_load_flow.py -v

# Performance validation
pytest -m performance --benchmark-only
```

### Test Coverage by Category

| Category | Files | Tests | Status |
|:---|---:|---:|:---:|
| Unit Tests | 32 | ~520 | ✅ Pass |
| Integration Tests | 14 | ~280 | ✅ Pass |
| Regression Tests | 8 | ~120 | ✅ Pass |
| Performance Tests | 4 | ~69 | ✅ Pass |
| **Total** | **58** | **989** | **✅ Pass** |

---

## 🚢 Deployment

### Docker Compose (Staging/Production)

```bash
# Build all images
docker compose build

# Start services in detached mode
docker compose up -d

# View logs
docker compose logs -f engineering-service

# Scale workers
docker compose up -d --scale celery-worker=4
```

### Kubernetes (Helm)

```bash
# Add chart dependencies
helm dependency update helm/etap-ai/

# Install to cluster
helm upgrade --install etap-ai helm/etap-ai/ \
  --namespace etap \
  --create-namespace \
  --values helm/etap-ai/values.yaml \
  --set image.tag=1.0.0
```

### Hugging Face Spaces

Deployment is automated via GitHub Actions on every push to `main`:
- **Workflow:** [`.github/workflows/sync-hf-space.yml`](.github/workflows/sync-hf-space.yml)
- **Space URL:** [huggingface.co/spaces/ahmdelbaz28/AHMEDETAP](https://huggingface.co/spaces/ahmdelbaz28/AHMEDETAP)

### CI/CD Pipeline

```
Push to main
     │
     ├─► Lint (ruff) + Type Check (mypy)
     ├─► Unit Tests (pytest)
     ├─► Security Scan (bandit + trivy)
     ├─► Build Docker Image
     ├─► Push to Registry
     ├─► Deploy to Staging
     ├─► Integration Tests
     ├─► Deploy to Production
     ├─► Sync to Hugging Face Space
     └─► Auto-update PROJECT_INDEX
```

**Full deployment guide:** [`docs/CI_CD_INTEGRATION.md`](docs/CI_CD_INTEGRATION.md)

---

## 🤝 Contributing

We welcome contributions! Please read our contribution guidelines before submitting:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feat/your-feature`
3. **Write tests** for any new functionality
4. **Run** the full test suite: `pytest`
5. **Lint** your code: `ruff check . && ruff format .`
6. **Submit** a Pull Request using the provided template

**Issues:** Please use the [GitHub Issue Templates](.github/ISSUE_TEMPLATE/) for bug reports and feature requests.

**Code of Conduct:** We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

---

## 🔒 Security

Security is a first-class concern in AhmedETAP:

- **Vulnerability Reporting:** See [`SECURITY.md`](SECURITY.md) for responsible disclosure guidelines
- **Security Architecture:** See [`.github/SECURITY.md`](.github/SECURITY.md) for the full security model
- **Automated Scanning:** Bandit, Trivy, and Dependabot run on every PR
- **ABAC Policies:** Fine-grained access control for all API operations
- **MFA:** TOTP and WebAuthn/FIDO2 support for all user accounts
- **RASP:** Runtime protection against SQL injection, path traversal, and other attacks

---

## 📚 Documentation Portal

| Document | Description |
|:---|:---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Full system architecture (42 KB) |
| [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) | Complete API docs with examples (33 KB) |
| [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md) | Production operations guide (45 KB) |
| [`docs/TROUBLESHOOTING_GUIDE.md`](docs/TROUBLESHOOTING_GUIDE.md) | Debugging & diagnostics (58 KB) |
| [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) | IEEE/IEC/NFPA standards reference (17 KB) |
| [`docs/SECURITY_OPERATIONS_MANUAL.md`](docs/SECURITY_OPERATIONS_MANUAL.md) | Security operations (11 KB) |
| [`docs/DISASTER_RECOVERY_PLAN.md`](docs/DISASTER_RECOVERY_PLAN.md) | DR & BCP procedures (8 KB) |
| [`docs/SLA_SLO_DOCUMENT.md`](docs/SLA_SLO_DOCUMENT.md) | SLA/SLO definitions (10 KB) |
| [`docs/AR/README.md`](docs/AR/README.md) | Arabic documentation / التوثيق بالعربية |
| [`PROJECT_INDEX.md`](PROJECT_INDEX.md) | Full auto-generated codebase index (116 KB) |
| [`PROJECT_INDEX.json`](PROJECT_INDEX.json) | Machine-readable index (516 KB) |

---

## 📈 Project Statistics

| Metric | Value |
|:---|:---|
| Python Packages | 25 |
| Python Files | 201 |
| Python Classes | 572 |
| Python Functions | 312 |
| API Endpoints | 51 |
| UI Files (TSX/TS) | 50 |
| Test Files | 58 |
| Total Tests | **989** |
| Documentation Files | 65+ |

*Statistics auto-updated by [`indexer.py`](indexer.py) on every push.*

---

## 📜 License

This project is licensed under the **MIT License** — see the [`LICENSE`](LICENSE) file for details.

---

<div align="center">

**Built with ❤️ for Power System Engineers**

*AhmedETAP — Where AI Meets Electrical Engineering Excellence*

[![GitHub](https://img.shields.io/badge/GitHub-ahmdelbaz28--ux-black?style=flat-square&logo=github)](https://github.com/ahmdelbaz28-ux)
[![Hugging Face](https://img.shields.io/badge/🤗-ahmdelbaz28-yellow?style=flat-square)](https://huggingface.co/ahmdelbaz28)

</div>