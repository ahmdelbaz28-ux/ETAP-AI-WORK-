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

<h1>⚡ AhmedETAP Platform</h1>
<h3>Enterprise AI-Powered Power Systems Engineering Intelligence</h3>

<p>
  An autonomous engineering-intelligence platform that fuses <strong>24 specialist AI agents</strong>
  with rigorous IEC / IEEE computational engines — taking engineers from a natural-language
  question to a validated, standards-compliant, auditable engineering report in seconds.
</p>

<br/>

[![Version](https://img.shields.io/badge/version-2.1.0-gold?style=for-the-badge&logo=semantic-release&logoColor=white)](#)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge&logo=open-source-initiative&logoColor=white)](LICENSE)

<br/>

[![UI](https://img.shields.io/badge/UI-Vercel-000000?style=flat-square&logo=vercel&logoColor=white)](https://etap-ai-work.vercel.app)
[![API](https://img.shields.io/badge/API-HF%20Space-FFD21E?style=flat-square&logo=huggingface&logoColor=black)](https://ahmdelbaz28-ahmedetap-platform.hf.space/health)
[![DB](https://img.shields.io/badge/Postgres-Neon-00e599?style=flat-square&logo=postgresql&logoColor=white)](https://neon.tech)
[![CI/CD](https://img.shields.io/github/actions/workflow/status/ahmdelbaz28-ux/ETAP-AI-WORK-/ci.yml?branch=main&style=flat-square&label=CI&logo=github-actions&logoColor=white)](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/actions)
[![Security](https://img.shields.io/badge/Semgrep-passing-brightgreen?style=flat-square&logo=semgrep&logoColor=white)](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/actions)
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2Fahmdelbaz28-ux%2FETAP-AI-WORK-.svg?type=shield)](https://app.fossa.com/projects/git%2Bgithub.com%2Fahmdelbaz28-ux%2FETAP-AI-WORK-?ref=badge_shield)
[![LLM Obs](https://img.shields.io/badge/LLM%20Obs-Langfuse-7C3AED?style=flat-square&logo=langfuse&logoColor=white)](https://cloud.langfuse.com)
[![Standards](https://img.shields.io/badge/Standards-IEEE%20%7C%20IEC-0052cc?style=flat-square&logo=ieee&logoColor=white)](#-engineering-standards)

<br/>

**[🚀 Live UI — Vercel](https://etap-ai-work.vercel.app)** &nbsp;•&nbsp;
**[🧠 Live API — HF Space](https://ahmdelbaz28-ahmedetap-platform.hf.space/docs)** &nbsp;•&nbsp;
**[📚 Documentation](docs/)** &nbsp;•&nbsp;
**[🔧 API Reference](docs/API_REFERENCE.md)** &nbsp;•&nbsp;
**[📋 Project Index](PROJECT_INDEX.md)** &nbsp;•&nbsp;
**[📝 Changelog](CHANGELOG.md)**

</div>

---

## 📋 Table of Contents

- [Platform Overview](#-platform-overview)
- [Architecture](#-architecture)
- [AI Agent Inventory](#-ai-agent-inventory)
- [Engineering Standards](#-engineering-standards)
- [Quick Start](#-quick-start)
- [Deployment](#-deployment)
- [Security Posture](#-security-posture)
- [Testing & CI](#-testing--ci)
- [Monitoring & Observability](#-monitoring--observability)
- [Repository Layout](#-repository-layout)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🏭 Platform Overview

**AhmedETAP** is a production-grade, autonomous engineering-intelligence platform that wraps ETAP-style power-systems analysis in a conversational, agent-driven interface. It combines:

- A **FastAPI backend** running 24 specialist AI agents with native IEEE/IEC computational engines
- A **React 19 + Vite 6** single-page application served from a global edge CDN
- A **dual-runtime agent orchestration** layer: Python for computation, TypeScript (Mastra) for LLM orchestration
- **Enterprise-grade observability**: Langfuse prompt versioning, LangWatch evaluations, Prometheus/Grafana metrics

| Tier | Hosting | Stack | Role |
|:---|:---|:---|:---|
| **Frontend SPA** | Vercel Edge CDN | React 19 · Vite 6 · TypeScript 5.7 | Static UI, instant global delivery |
| **Backend API** | Hugging Face Space (Docker) | FastAPI 0.115 · Python 3.13 · uvicorn | AI agents, engineering engines, auth |
| **Database** | Neon PostgreSQL | Serverless Managed Postgres | Durable project & study persistence |
| **LLM Observability** | Langfuse Cloud | Prompt versioning · LLM traces | Unlimited prompts, 50k obs/month |
| **LLM Evaluation** | LangWatch | Scenario evals · drift detection | Continuous agent quality monitoring |
| **MCP Tooling** | Smithery | Model Context Protocol registry | Secure external tool discovery |
| **Security Scanning** | Semgrep · Snyk · Trivy · GitGuardian | SAST · SCA · secret scanning | Continuous security gate |

---

## 🏗️ Architecture

```
 ┌──────────────────────────────┐         ┌────────────────────────────────────────┐
 │  Vercel Edge CDN             │         │  Hugging Face Space (Docker SDK)       │
 │  ────────────────────────    │  HTTPS  │  ─────────────────────────────────     │
 │  React 19 + Vite 6 SPA       │ ──────► │  FastAPI 0.115 + uvicorn               │
 │  TypeScript 5.7              │  JSON   │  24 AI agents (Python + TypeScript)    │
 │  Zustand + React Query 5     │  WS     │  40+ REST endpoints (/api/v1/*)        │
 │  React Router 7              │         │  IEEE/IEC computational engines        │
 │  i18next (Arabic / English)  │         │  JWT auth · RBAC · bcrypt              │
 └──────────────────────────────┘         │  Mastra agent runtime (TypeScript)     │
                                          └────────────────┬───────────────────────┘
                                                           │
              ┌────────────────────────────────────────────┴───────────────────────┐
              │                                                                    │
              ▼                                                                    ▼
 ┌─────────────────────────┐                              ┌─────────────────────────────┐
 │  Neon PostgreSQL         │                              │  Langfuse Cloud             │
 │  ─────────────────────   │                              │  ─────────────────────────  │
 │  Project persistence     │                              │  Prompt versioning          │
 │  Study revisions (OCC)   │                              │  LLM traces + safety alerts │
 │  Export history          │                              │  Rollback & A/B testing     │
 │  Solver parameters       │                              └────────────┬────────────────┘
 └─────────────────────────┘                                            │
                                                                        ▼
                                                          ┌─────────────────────────────┐
                                                          │  LangWatch                  │
                                                          │  ─────────────────────────  │
                                                          │  Scenario evaluations       │
                                                          │  Agent drift detection      │
                                                          └─────────────────────────────┘
```

### Computation Engine Architecture

The platform uses **two distinct computation layers**:

| Layer | Engine | Platforms | Purpose |
|:---|:---|:---|:---|
| **Native Python Solvers** | `engine/`, `load_flow/`, `fault_analysis/`, `coordination/` | All (HF Space, Linux, Windows) | Newton-Raphson load flow, IEC 60909 fault, IEEE 1584-2018 arc flash, IEEE 519 harmonics, transient stability |
| **ETAP COM Automation** | `etap_integration/etap_com.py` | Windows only (pywin32 + licensed ETAP) | Certified ETAP 2021/22 COM API for native `.edb` project studies |

> **Note:** On HF Space and all Linux deployments, COM automation falls back to `NullEtapProvider`. All engineering computations use the native Python solvers. Configure `ETAP_WORKER_URL` to point to a remote Windows ETAP worker for COM-dependent studies.

---

## 🤖 AI Agent Inventory

24 specialist agents, each governed by Langfuse prompt-versioning and safety alerts:

| Domain | Agents |
|:---|:---|
| **Power System Analysis** | Load Flow (IEEE 3002.7) · Short Circuit (IEC 60909) · Arc Flash (IEEE 1584) · Protection Coordination (IEC 60255) · Motor Starting (IEEE 399) · Harmonic Analysis (IEEE 519) · Transient Stability |
| **ETAP Automation** | ETAP Engineer Agent · ETAP GUI (Computer-Use via Gemini Vision) · ETAP Expert Skill (4,400+ line knowledge base) · Generative Design Agent |
| **Infrastructure & GIS** | QGIS/ArcGIS Connector · SCADA Agent (IEC 61850) · Digital Twin · Renewable Energy (IEEE 1547) · BESS Storage (IEC 62933) |
| **Engineering Ops** | Cable Sizing (IEC 60364) · Earth Grid (IEEE 80) · Optimal Power Flow · Anomaly Detection · Predictive Analytics |
| **Orchestration & Safety** | Power System Coordinator (router) · Goal Planner · Report Generation · Code Guard (prompt-injection defence) · Validation Agent |

Full prompt files and agent specifications: [`AGENTS.md`](AGENTS.md) · [`agents/`](agents/) · [`prompts/`](prompts/)

---

## 📐 Engineering Standards

| Standard | Scope | Implementation |
|:---|:---|:---|
| **IEEE 3002.7** | Load flow | Newton-Raphson solver in `load_flow/load_flow.py` |
| **IEC 60909** | Short circuit / fault currents | Symmetrical-components solver in `fault_analysis/fault.py` |
| **IEEE 1584-2018** | Arc flash incident energy & PPE | Empirical engine in `fault_analysis/arc_flash.py` |
| **IEEE 519-2022** | Harmonic distortion limits | FFT-based analysis in `fault_analysis/harmonic_analysis.py` |
| **IEC 60255** | Protection relay coordination | TCC selectivity engine in `coordination/coordination.py` |
| **IEEE 399** | Motor starting & industrial power | Motor starting solver in `motor_starting/` |
| **IEEE 80** | Grounding / earth grid safety | Touch/step voltage calculator in `agents/earth_grid_agent.py` |
| **IEC 60364** | Cable sizing & ampacity | Derating calculator in `agents/cable_sizing_agent.py` |
| **IEEE 1547** | Distributed energy resources (DER) | PV/wind integration in `agents/renewable_agent.py` |
| **IEC 61850** | SCADA data model | GOOSE/MMS mapping in `agents/scada_agent.py` |
| **IEC 62933** | Battery energy storage | BESS dispatch optimizer in `agents/battery_storage_agent.py` |
| **NFPA 70E** | Electrical safety / PPE categories | Arc flash boundary calculation |
| **IEC 62443 / NERC CIP** | Industrial cybersecurity | RFC 5424 SIEM syslog forwarder in `integrations/siem_syslog.py` |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.13** — see `.python-version`
- **Node.js 22** — see `.nvmrc`
- **pnpm 9+** — workspace package manager
- **Docker** (optional, for full-stack local dev)

### Interactive Setup Wizard

```bash
# Configure all credentials and generate .env in under 2 minutes
bash scripts/setup_wizard.sh

# Or verify existing service connections directly
python scripts/verify_services.py
```

### Run the UI Locally

```bash
cd ui
npm install --no-audit --no-fund
npm run dev          # → http://localhost:5173 (proxies /api to :8000)
```

### Run the Backend Locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # fill in real values
uvicorn api.main:app --reload --port 8000
```

The UI dev server proxies `/api`, `/health`, `/docs`, and `/openapi.json` to `http://localhost:8000` automatically (see `ui/vite.config.ts`).

### Run the Full Stack with Docker

```bash
docker-compose up -d   # Postgres + Redis + Backend + UI + Prometheus + Grafana
```

See [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md) for production hardening.

---

## 📦 Deployment

### Frontend → Vercel

Configured in [`vercel.json`](vercel.json):

1. Install: `npm --prefix ui install --no-audit --no-fund`
2. Build: `bash vercel-build.sh` (safety wrapper with pre-flight checks)
3. Serve: `ui/dist/` as static assets with immutable cache headers
4. SPA rewrites for client-side routing
5. Security headers (CSP, HSTS, X-Frame-Options) applied everywhere

```bash
vercel --prod   # Promote to production
```

### Backend → Hugging Face Space

The HF Space uses Docker SDK (`app_port: 7860`). [`Dockerfile.hf`](Dockerfile.hf) builds the FastAPI image. Secrets are injected via the HF Space secrets panel.

Required secrets: `OPENAI_API_KEY` · `DATABASE_URL` · `SUPABASE_URL` · `SUPABASE_SERVICE_ROLE_KEY` · `LANGFUSE_PUBLIC_KEY` · `LANGFUSE_SECRET_KEY` · `LANGWATCH_API_KEY` · `SECRET_KEY`

### Database Migrations

```bash
alembic upgrade head     # Apply all pending migrations
alembic history          # View migration history
```

Current head: migration `012` — adds `project_solver_parameters`, `study_versions`, `export_history` tables.

### Kubernetes (Optional)

Helm charts in [`helm/`](helm/) · Raw manifests in [`k8s/`](k8s/) · Azure IaC in [`terraform/`](terraform/)

---

## 🔒 Security Posture

| Layer | Implementation |
|:---|:---|
| **Authentication** | JWT (HS256) + bcrypt 14 rounds + account lockout after 5 attempts |
| **Authorization** | RBAC with 5 roles and 25+ fine-grained permissions on every API route |
| **LLM Guardrails** | Prompt-injection defence (Code Guard agent) · model allow-list · 50k-char input cap |
| **Rate Limiting** | Token-bucket with LRU eviction per client IP |
| **Secret Management** | Vercel env vars (frontend) · HF Space secrets (backend) · never committed |
| **Audit Logging** | JSON-structured with rotation · RFC 5424 SIEM syslog forwarder |
| **Dual Control** | Maker-Checker enforcement on critical engineering actions (HTTP 403 on violation) |
| **Dependency Scanning** | Semgrep SAST · Snyk SCA · Trivy container · GitGuardian secret detection · pip-audit |
| **MFA** | TOTP (RFC 6238) + WebAuthn passkeys |

See [`SECURITY.md`](SECURITY.md) for responsible disclosure instructions.

---

## 🧪 Testing & CI

### Test Suite

| Category | Framework | Status |
|:---|:---|:---|
| Python unit tests | `pytest` | ✅ 85%+ coverage |
| Python integration tests | `pytest-asyncio` + real Postgres + Redis | ✅ 90%+ coverage |
| SCADA & scenario tests | `pytest` + custom fixtures | ✅ 100% regression |
| UI unit tests | `vitest` | ✅ Component-level |
| UI E2E tests | `playwright` | ✅ Critical user flows |
| Agent scenario evals | `vitest --config vitest.scenarios.config.ts` | ✅ LLM output quality |
| Property-based tests | `hypothesis` | ✅ Edge cases |
| Load tests | `k6` + `locust` | ✅ API throughput |

### Running Tests

```bash
# Backend
pytest                              # All Python tests
pytest -m unit                     # Unit tests only
pytest -m integration              # Integration tests only
pytest --cov=. --cov-report=html   # With HTML coverage report

# Frontend
cd ui && npm test                   # Vitest unit tests
cd ui && npm run test:e2e           # Playwright E2E tests

# Smoke test against production
PRODUCTION_URL=https://ahmdelbaz28-ahmedetap-platform.hf.space python scripts/smoke_test.py
```

### CI Workflows (GitHub Actions)

| Workflow | Checks |
|:---|:---|
| `ci.yml` | Unit · Integration · SCADA tests · Build · Bundle size |
| `security-scans.yml` | Trivy · pip-audit · Custom security checks · Runtime security |
| `python-compatibility.yml` | Import sanity on Python 3.12 and 3.13 |
| `code-quality.yml` | YAML validation · Ruff · Type checking |
| `docker-build.yml` | Multi-platform Docker image builds |
| `ui-quality.yml` | Vitest · Production build test |
| `semgrep.yml` | SAST security scan (OSS rules) |

---

## 📊 Monitoring & Observability

| Component | Purpose |
|:---|:---|
| **Prometheus** | Study latency, agent success rates, API throughput |
| **Grafana** | Dashboards in `monitoring/grafana_dashboards/` |
| **Alertmanager** | SCADA outages, re-run latency >30s, export failures >5%, revision deadlocks |
| **Langfuse** | LLM trace recording, prompt versioning, safety alerts |
| **LangWatch** | Scenario-based agent quality evaluation and drift detection |
| **OpenTelemetry** | Distributed tracing across Python + TypeScript runtimes |

```bash
docker-compose -f docker-compose.monitoring.yml up -d
# Grafana → http://localhost:3000  |  Prometheus → http://localhost:9090
```

---

## 📁 Repository Layout

```
.
├── ui/                         # React 19 + Vite 6 SPA (Vercel deploy target)
│   ├── src/                    #   Application source (components, pages, hooks)
│   ├── tests/                  #   Playwright E2E + Vitest unit tests
│   └── vite.config.ts          #   Vite config + dev-server proxy to :8000
├── api/                        # FastAPI routers (40+ endpoints under /api/v1/)
├── agents/                     # Python specialist AI agent implementations
├── src/mastra/                 # TypeScript agent runtime (Mastra framework)
│   ├── agents/                 #   LLM agent definitions + tool bindings
│   └── workflows/              #   Multi-step agent orchestration workflows
├── prompts/                    # Agent prompt YAML files (versioned via Langfuse)
├── core/                       # Shared core (auth, redis_state, logging, config)
├── load_flow/                  # Newton-Raphson IEEE 3002.7 solver
├── fault_analysis/             # IEC 60909 fault + IEEE 1584 arc flash + harmonics
├── coordination/               # IEC 60255 protection coordination engine
├── motor_starting/             # IEEE 399 motor starting analysis
├── engine/                     # Main computation engine dispatcher
├── security/                   # LLM guardrails, audit logging, SIEM integration
├── integrations/               # ETAP COM, ArcGIS, Zenon, Gemini Vision connectors
├── ai_context_engine/          # RAG over 35 ETAP manuals + Zenon guides
├── migrations/                 # Alembic database migrations (head: 012)
├── tests/                      # pytest suites (unit · integration · scenario)
├── monitoring/                 # Prometheus rules + Grafana dashboards
├── docs/                       # MkDocs documentation site
│   └── mkdocs.yml              #   Build: mkdocs build -f docs/mkdocs.yml
├── helm/                       # Kubernetes Helm charts
├── terraform/                  # Azure infrastructure as code (Terraform)
├── docker-compose.yml          # Full-stack local dev (all services)
├── Dockerfile.hf               # HF Space backend image
├── Dockerfile.engineering-service  # Engineering service Docker image
├── vercel.json                 # Vercel project config
├── vercel-build.sh             # Safety wrapper around the Vite build
├── engineering_service.py      # Production FastAPI entrypoint
├── pyproject.toml              # Python package metadata + tool configs
├── ruff.toml                   # Ruff linter configuration
├── requirements.txt            # Python production dependencies
├── requirements-dev.txt        # Dev/test dependencies (pinned with upper bounds)
├── requirements-ml.txt         # ML/AI dependencies (Pillow 12.3+, mlflow, xgboost)
├── .env.example                # Full environment variable reference (376 lines)
└── AGENTS.md                   # Complete AI agent specification and architecture
```

---

## 🗺️ Roadmap

| Phase | Status | Description |
|:---|:---|:---|
| **Phase 1** | ✅ Complete | Core computation engines: load flow, short circuit, arc flash |
| **Phase 2** | ✅ Complete | AI agent orchestration, security framework, JWT auth |
| **Phase 3** | ✅ Complete | ETAP COM integration, GIS, SCADA (IEC 61850) |
| **Phase 4** | ✅ Complete | Transient stability, cable sizing, earth grid, renewables, BESS |
| **Phase 5** | ✅ Complete | ML/AI predictive analytics, anomaly detection, OPF |
| **Phase 6** | ✅ Complete | Kubernetes/Helm deployment, Prometheus/Grafana observability |
| **Phase 7** | ✅ Complete | Chat-first UI v3.0, generative design agent, production hardening |
| **Phase 8** | 🔄 In Progress | Multi-tenant SaaS, Azure Terraform IaC, Electron desktop app |
| **Phase 9** | 📋 Planned | Federated learning, digital twin real-time sync, ADMS integration |

See [`ROADMAP.md`](ROADMAP.md) for detailed planning.

---

## 🤝 Contributing

1. **Fork** the repo and create a feature branch: `git checkout -b feat/your-feature`
2. **Install** pre-commit hooks: `pre-commit install`
3. **Test** — all CI checks must pass: `pytest && cd ui && npm test`
4. **Commit** using Conventional Commits: `feat(agents): add new study type`
5. **Open a PR** — squash-merge to `main` → Vercel auto-deploys a preview → promote to prod

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full workflow and code review standards.

---

## ❓ FAQ

<details>
<summary><strong>Can I use AhmedETAP without a licensed ETAP installation?</strong></summary>

Yes. The native Python solvers (Newton-Raphson, IEC 60909, IEEE 1584, etc.) work completely independently on any platform. ETAP COM automation is an optional enhancement for Windows deployments with a licensed ETAP 2021+ installation.
</details>

<details>
<summary><strong>What engineering standards are implemented?</strong></summary>

IEEE 3002.7, IEC 60909, IEEE 1584-2018, IEEE 519-2022, IEC 60255, IEEE 399, IEEE 80, IEC 60364, IEEE 1547, IEC 61850, IEC 62933, NFPA 70E, IEC 62443/NERC CIP. See the Engineering Standards table for implementation details.
</details>

<details>
<summary><strong>How is production data secured?</strong></summary>

All secrets are managed via Vercel env vars and HF Space secrets — never committed to git. GitGuardian and Semgrep scan every push. Database connections use TLS. JWT tokens expire after 1 hour. RBAC enforces least-privilege on every API endpoint.
</details>

---

## 🆘 Support & Troubleshooting

| Issue | Solution |
|:---|:---|
| Backend not responding | `python engineering_service.py --port 8000` |
| UI build fails | `cd ui && npm install && npm run build` |
| Database migration errors | `alembic upgrade head` — check `DATABASE_URL` in `.env` |
| ETAP COM unavailable | Expected on Linux/macOS — native Python solvers are the fallback |
| Redis connection refused | `docker compose up redis` or verify `REDIS_URL` |
| SCADA bridge HTTP 503 | Live SCADA connection failed — verify `SCADA_*` env vars |

- **Issues:** [GitHub Issues](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/issues)
- **Security disclosures:** See [`SECURITY.md`](SECURITY.md) — do NOT open a public issue for vulnerabilities
- **Diagnostics:** [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) · [`OPS_RUNBOOK.md`](OPS_RUNBOOK.md)

---

## 📜 License

MIT — see [`LICENSE`](LICENSE) for details.

```
MIT License — Copyright © 2026 Eng. Ahmed Elbaz
```

[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2Fahmdelbaz28-ux%2FETAP-AI-WORK-.svg?type=large)](https://app.fossa.com/projects/git%2Bgithub.com%2Fahmdelbaz28-ux%2FETAP-AI-WORK-?ref=badge_large)

---

<div align="center">

<p>
  <a href="https://github.com/ahmdelbaz28-ux">
    <img src="https://github.com/ahmdelbaz28-ux.png" width="80" style="border-radius:50%" alt="Eng. Ahmed Elbaz">
  </a>
  <br/>
  <strong>Eng. Ahmed Elbaz</strong><br/>
  <em>Electrical Power Engineer &amp; AI Systems Architect</em><br/>
  <a href="mailto:ahmdelbaz28@gmail.com">ahmdelbaz28@gmail.com</a> ·
  <a href="https://github.com/ahmdelbaz28-ux">GitHub</a> ·
  <a href="https://ahmdelbaz28-ahmedetap-platform.hf.space">Live Demo</a>
</p>

<sub>Built with precision for the global power-systems engineering community. ⚡</sub>

</div>
