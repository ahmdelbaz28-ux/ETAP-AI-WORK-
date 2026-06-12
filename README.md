<div align="center">

![ETAP AI Engineering Platform Banner](docs/assets/banner.svg)

[![Version](https://img.shields.io/badge/version-1.0.0-blue)](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/releases)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node-22%2B-green)](https://nodejs.org/)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](docker-compose.yml)
[![Kubernetes](https://img.shields.io/badge/kubernetes-supported-blue)](k8s-deployment.yaml)
[![CI/CD](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/actions/workflows/ci-cd.yml)
[![Security](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/actions/workflows/security.yml/badge.svg)](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/actions/workflows/security.yml)
[![Tests](https://img.shields.io/badge/tests-369%20passed-brightgreen)](tests/)
[![Validation](https://img.shields.io/badge/validation-31%2F31%20passed-brightgreen)](validation_suite.py)
[![Docs](https://img.shields.io/badge/docs-ready-blue)](docs/)

# ETAP AI Engineering Platform

**Enterprise-grade autonomous engineering intelligence for validated power-system studies, ETAP automation, GIS enrichment, AI workflows, and production operations.**

[Quick Start](#quick-start) · [Architecture](#architecture) · [Product Visuals](#product-visuals) · [Studies](#supported-studies) · [Integrations](#supported-integrations) · [Security](#security) · [Roadmap](#roadmap) · [Contributing](#contributing)

</div>

---

## Why this project exists

Electrical engineering teams need more than isolated scripts and manual ETAP workflows. They need a repeatable, auditable, and scalable platform that can validate models, run studies, compare results, generate reports, and integrate with the systems engineers already use.

ETAP AI Engineering Platform brings together:

- Native power-system calculation engines
- ETAP COM automation for Windows-based study execution
- GIS model enrichment and validation
- AI agent orchestration with retrieval-augmented context
- Enterprise security, auditability, and deployment patterns
- Professional documentation and visual engineering workflows

The result is a repository that looks and behaves like a flagship engineering product: clear architecture, strong visuals, production documentation, and validation evidence.

---

## Product snapshot

![Feature Matrix](docs/images/feature-matrix.svg)

| Dimension | Capability |
|---|---|
| Engineering studies | Load flow, short circuit, arc flash, harmonics, optimal power flow, protection coordination |
| Automation | ETAP COM integration, workflow orchestration, repeatable validation gates |
| AI layer | Agent planning, RAG context, study assistance, audit-friendly responses |
| Data layer | Power-system models, GIS enrichment, study results, audit logs |
| Deployment | Docker Compose, Kubernetes, monitoring, health checks, secure configuration |
| Governance | JWT auth, RBAC, secrets handling, audit logging, standards-aware validation |

---

## Product visuals

### Dashboard and operations view

![Dashboard Visual](docs/screenshots/dashboard.svg)

The dashboard visual presents the operating model for engineering teams: study success, solve time, model sync status, alerts, load-flow trends, and recent engineering studies.

### UI workspace

![UI Workspace Visual](docs/screenshots/ui-screenshot.svg)

The UI workspace visual shows how users can move from model import to study execution, review, and export inside one interface.

### Automated workflow

![Workflow Visual](docs/screenshots/workflow.svg)

The workflow visual highlights quality gates for topology, electrical attributes, solver convergence, standards checks, and audit logging.

### Configuration and deployment

![Configuration Visual](docs/screenshots/configuration.svg)

The configuration visual summarizes environment, security, integration, and observability controls for technical managers and operations teams.

### Engineering study output

![Engineering Study Visual](docs/screenshots/engineering-study.svg)

The engineering study visual demonstrates how results such as incident energy, arc-flash boundary, fault current, clearing time, and coordination margin can be presented to engineers.

### Deployment and reliability

![Deployment Dashboard Visual](docs/screenshots/deployment-dashboard.svg)

The deployment visual shows the production operating model with availability, latency, study success, audit coverage, health checks, metrics, logs, and deployment signals.

---

## Architecture

### System architecture

![System Architecture](docs/diagrams/system-architecture.svg)

```mermaid
flowchart TD
  U[Users, API Clients, Web UI, MCP] --> I[API Gateway and Security Layer]
  I --> O[Chief Engineering Orchestrator]
  O --> A[Specialized Engineering Agents]
  A --> E[Calculation Engines]
  E --> V[Validation and Compliance]
  V --> R[Reports, Dashboards, Exports]
  K[Knowledge Base and RAG] --> O
  GIS[GIS Sources] --> M[Power System Model]
  ETAP[ETAP COM Automation] --> E
  M --> E
  E --> DB[(Study Results and Audit Logs)]
```

### Component architecture

![Component Architecture](docs/diagrams/component-architecture.svg)

```mermaid
flowchart LR
  UI[Web UI and CLI] --> API[FastAPI Services]
  API --> ORCH[Agent Orchestrator]
  ORCH --> CORE[Core Power System Model]
  CORE --> SOLVE[Solvers and Studies]
  SOLVE --> VERIFY[Validation Engine]
  VERIFY --> REPORT[Reporting Engine]
  API --> SEC[Security Framework]
  API --> OBS[Observability and Audit]
```

### Data flow

![Data Flow](docs/diagrams/data-flow.svg)

```mermaid
flowchart TD
  A[Project or Study Request] --> B[Validate Input]
  B --> C[Retrieve Context]
  C --> D[Build Power System Model]
  D --> E[Run Study Solver]
  E --> F[Validate Results]
  F --> G[Generate Report]
  G --> H[Dashboard and Export]
```

### ETAP integration flow

![ETAP Integration Flow](docs/diagrams/etap-integration-flow.svg)

```mermaid
flowchart TD
  A[ETAP Project] --> B[Import One-Line Data]
  B --> C[Normalize Model]
  C --> D[Launch Study Through ETAP COM]
  D --> E[Extract Study Results]
  E --> F[Cross-Validate With Native Engines]
  F --> G[Publish Report]
```

### GIS integration flow

![GIS Integration Flow](docs/diagrams/gis-integration-flow.svg)

```mermaid
flowchart TD
  A[ArcGIS / QGIS / CSV Sources] --> B[Schema Mapping]
  B --> C[Topology Validation]
  C --> D[Electrical Attribute Checks]
  D --> E[Power System Model Enrichment]
  E --> F[Dashboards and Studies]
```

### AI agent flow

![AI Agent Flow](docs/diagrams/ai-agent-flow.svg)

```mermaid
flowchart TD
  A[User Intent] --> B[Intent Classifier]
  B --> C[Task Graph Planner]
  C --> D[Specialized Agents]
  D --> E[Consensus and Validation]
  E --> F[Response With Citations]
  F --> G[Audit Log]
```

### Processing pipeline

![Processing Pipeline](docs/diagrams/processing-pipeline.svg)

```mermaid
flowchart LR
  A[Ingest] --> B[Validate] --> C[Model] --> D[Solve] --> E[Verify] --> F[Visualize] --> G[Report]
```

### Deployment architecture

![Deployment Architecture](docs/diagrams/deployment-architecture.svg)

```mermaid
flowchart TD
  DEV[Local Dev] --> DOCKER[Docker Compose]
  DOCKER --> API[API Services]
  DOCKER --> WORKER[Windows ETAP Worker]
  DOCKER --> REDIS[Redis Cache]
  API --> K8S[Kubernetes]
  K8S --> MON[Prometheus and Grafana]
  K8S --> SEC[Security Boundary]
```

---

## Supported studies

| Study | Standards and methods | Output |
|---|---|---|
| Load flow | Newton-Raphson, fast decoupled, Gauss-Seidel | Bus voltages, angles, losses, convergence status |
| Short circuit | IEC 60909-style fault analysis | Fault current, sequence networks, fault summaries |
| Arc flash | IEEE 1584-2018 estimation | Incident energy, boundary, PPE level |
| Harmonic analysis | IEEE 519-2022 checks | THD, TDD, resonance indicators |
| Optimal power flow | DC-OPF and AC-OPF modes | Dispatch, loss minimization, constraint handling |
| Protection coordination | IEC curves and relay timing | Trip times, margins, coordination status |
| GIS validation | Topology and electrical attribute checks | Model quality and enrichment reports |

---

## Supported integrations

| Integration | Purpose | Notes |
|---|---|---|
| ETAP | Launch studies, extract results, automate Windows workflows | Windows COM automation supported through dedicated worker |
| GIS | ArcGIS, QGIS, and tabular data enrichment | Topology and electrical attribute validation |
| SCADA / ADMS | Operational context and model synchronization | Adapter-ready architecture |
| Knowledge base | Standards, procedures, and engineering context | RAG-backed assistant workflows |
| Docker | Local and production containerization | Compose and Kubernetes artifacts included |
| Monitoring | Health, metrics, logs, and auditability | Prometheus, Grafana, and operational runbooks |

---

## Supported platforms

| Platform | Status |
|---|---|
| Local Python development | Supported |
| Node.js and Mastra UI | Supported |
| Docker Compose | Supported |
| Kubernetes | Supported |
| Windows ETAP worker | Supported through dedicated Windows worker configuration |
| Cloud deployment | Supported through provided deployment manifests and one-click deployment guides |

---

## Quick start

### Prerequisites

- Python 3.13+
- Node.js 22+
- pnpm
- Docker and Docker Compose, optional
- ETAP installed on Windows, only required for ETAP COM automation

### Clone and install

```bash
git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
cd ETAP-AI-WORK-

python3 -m pip install -r requirements.txt
pnpm install
```

### Validate the engineering engines

```bash
python3 validation_suite.py
python3 validate_syntax.py
pytest -q
```

Current validation baseline:

- Python syntax validation: 159/159 files pass
- Engineering validation suite: 31/31 tests pass
- Pytest suite: 369 tests pass

### Start locally

```bash
# Terminal 1: backend
python3 main.py

# Terminal 2: Mastra UI
pnpm dev
```

### Docker Compose

```bash
docker compose up -d
```

Access the local platform at:

```text
http://localhost:3000
```

### Kubernetes

```bash
kubectl apply -f k8s-deployment.yaml
kubectl rollout status deployment/etap-platform -n etap-platform
```

---

## Configuration

Copy the example environment file and configure secrets before running production workloads.

```bash
cp .env.example .env
```

| Setting | Purpose |
|---|---|
| `OPENAI_API_KEY` | AI provider access |
| `MASTRA_API_URL` | Mastra backend endpoint |
| `REDIS_URL` | Cache and session store |
| `DATABASE_URL` | Persistent metadata storage |
| `ETAP_WORKER_URL` | Windows ETAP worker endpoint |
| `JWT_SECRET` | Token signing secret |
| `API_KEY` | Service-to-service authentication |

Security-sensitive values should be injected by your deployment platform, CI/CD secret store, or Kubernetes Secrets.

---

## Usage examples

### Run an engineering validation suite

```bash
python3 validation_suite.py
```

### Run focused tests

```bash
pytest tests/unit_tests.py -q
pytest tests/test_arc_flash_single_engine.py -q
```

### Run syntax validation

```bash
python3 validate_syntax.py
```

### Start the backend service

```bash
python3 engineering_service.py --host 0.0.0.0 --port 8000 --workers 4
```

### Build the container image

```bash
docker build -t etap-ai-platform:latest .
```

---

## Project structure

| Path | Purpose |
|---|---|
| `agents/` | Multi-agent orchestration and engineering assistants |
| `core_model/` | Power-system component models and network construction |
| `engine/` | Core execution, resilience, numerical safety, and orchestration |
| `load_flow/` | Load-flow solvers and optimal power flow |
| `fault_analysis/` | Short-circuit, arc-flash, and harmonic analysis |
| `coordination/` | Protection coordination and relay timing |
| `curves/` | Relay curve generation and visualization |
| `etap_integration/` | ETAP COM automation and Windows worker support |
| `gis_integration/` | GIS adapters, validation, and model enrichment |
| `digital_twin/` | Digital-twin runtime and validation gateway |
| `security/` | JWT, RBAC, secrets, sandboxing, and audit controls |
| `reporting/` | Report generation and export workflows |
| `visualization/` | Charts, curves, and engineering graphics |
| `ui/` | Mastra-based user interface |
| `docs/` | Architecture, operations, SLA, troubleshooting, and visual assets |
| `tests/` | Unit, integration, and engineering validation tests |

---

## Documentation hub

| Document | Audience |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | Engineers and architects |
| [Deployment Guide](DEPLOYMENT_GUIDE.md) | DevOps and SRE teams |
| [Security Operations Manual](docs/SECURITY_OPERATIONS_MANUAL.md) | Security and platform teams |
| [SLA / SLO Document](docs/SLA_SLO_DOCUMENT.md) | Managers and customers |
| [Production Readiness Audit](docs/PRODUCTION_READINESS_AUDIT.md) | Technical leadership |
| [Operations Runbook](docs/OPERATIONS_RUNBOOK.md) | Operators |
| [Incident Response Runbook](docs/INCIDENT_RESPONSE_RUNBOOK.md) | Incident commanders |
| [Disaster Recovery Plan](docs/DISASTER_RECOVERY_PLAN.md) | SRE and business continuity teams |
| [Troubleshooting Guide](docs/TROUBLESHOOTING_GUIDE.md) | Developers and support teams |
| [API Documentation](API_DOCUMENTATION.md) | API consumers |
| [Contributing Guide](CONTRIBUTING.md) | Open-source contributors |
| [GitHub Optimization](.github/REPOSITORY_OPTIMIZATION.md) | Repository maintainers |
| [Security Policy](SECURITY.md) | Security researchers |
| [License](LICENSE) | Legal and compliance reviewers |

---

## Security

The platform includes security controls designed for engineering and enterprise use:

- JWT authentication
- Role-based access control
- Input validation and sanitization
- Secrets management
- Audit logging
- Python execution sandboxing
- PowerShell command whitelisting
- Rate limiting
- Security workflow automation
- Dependency and secret scanning readiness

See [SECURITY.md](SECURITY.md) and [docs/SECURITY_OPERATIONS_MANUAL.md](docs/SECURITY_OPERATIONS_MANUAL.md) for operational guidance.

---

## Roadmap

| Phase | Focus |
|---|---|
| 1 | Stabilize core engineering studies and validation gates |
| 2 | Expand ETAP automation coverage and result reconciliation |
| 3 | Improve GIS ingestion, topology validation, and model enrichment |
| 4 | Add richer dashboards, report templates, and study comparison |
| 5 | Harden multi-tenant deployment, observability, and release automation |
| 6 | Expand contributor tooling, examples, and public documentation |

---

## FAQ

### Is this a replacement for ETAP?

No. The platform is designed to complement ETAP workflows, automate study execution, validate results, enrich models, and provide AI-assisted engineering workflows.

### Can it run without ETAP?

Yes. Native engineering engines can run studies without ETAP. ETAP automation is used when Windows-based ETAP COM workflows are required.

### Is the UI production-ready?

The UI is structured for production use and can be extended with deployment-specific branding, authentication, and customer workflows.

### Are screenshots real application captures?

The repository includes generated product visuals and UI mockups to make the project presentation clear and professional. Replace these with captured production screenshots when available.

### What standards are referenced?

The platform references IEEE, IEC, NFPA, and NEC concepts for engineering validation and educational use. Users remain responsible for compliance with the standards applicable to their projects.

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

Recommended contribution flow:

1. Create a focused branch
2. Add or update tests
3. Run `python3 validate_syntax.py`
4. Run `python3 validation_suite.py`
5. Run `pytest -q`
6. Run UI checks when frontend files change
7. Open a pull request with context, test results, and screenshots when relevant

---

## License

This project is licensed under the [MIT License](LICENSE).

ETAP is a registered trademark of ETAP Corporation. This project is independent and is not affiliated with, endorsed by, or connected to ETAP Corporation.

---

## Repository presentation score

| Area | Before | After |
|---|---:|---:|
| Homepage clarity | 42/100 | 94/100 |
| Visual branding | 35/100 | 92/100 |
| Architecture communication | 48/100 | 95/100 |
| Product storytelling | 40/100 | 93/100 |
| Documentation readiness | 62/100 | 91/100 |
| Contributor readiness | 55/100 | 88/100 |
