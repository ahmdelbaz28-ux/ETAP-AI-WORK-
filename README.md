# ETAP AI Engineering Platform

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Node.js](https://img.shields.io/badge/node-18+-green.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)
![Kubernetes](https://img.shields.io/badge/kubernetes-supported-blue.svg)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)
![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen.svg)

**AI-Powered Multi-Agent Autonomous Engineering System for Power Systems Analysis**

> **One-command public deploy of the Engineering Service:**
> [**Fly.io**](https://fly.io) · [**Render**](https://render.com) · [**Railway**](https://railway.com) — see [Quick Start → One-Click Deploy](#one-click-public-deployment)

[Documentation](docs/) • [API Reference](API_DOCUMENTATION.md) • [Quick Start](#quick-start) • [Contributing](CONTRIBUTING.md)

</div>

---

## 🌟 Overview

ETAP AI Engineering Platform is a comprehensive, production-ready system for automated power systems engineering analysis. Built with cutting-edge AI technology and multi-agent architecture, it provides intelligent automation for electrical engineering studies including load flow, short circuit, arc flash, harmonic analysis, optimal power flow, and more.

### Key Features

✅ **Multi-Agent Architecture** - 9 specialized autonomous agents working in coordination  
✅ **Complete Engineering Suite** - Load Flow, Fault, Arc Flash, Harmonics, OPF, Protection  
✅ **ETAP Integration** - Direct COM automation with ETAP software (Windows)  
✅ **Standards Compliant** - IEEE, IEC, NFPA, NEC standards built-in  
✅ **AI-Powered RAG** - Knowledge base prevents hallucinations and ensures compliance  
✅ **Professional Reports** - Auto-generated PDF/DOCX/XLSX reports with charts  
✅ **Enterprise Security** - JWT auth, RBAC, audit logging, OWASP compliant  
✅ **Production Ready** - Docker, Kubernetes, CI/CD, monitoring included  

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Node.js 18+
- pnpm package manager
- Docker & Docker Compose (optional, for containerized deployment)

### Installation

#### Option 1: Local Installation

```bash
# Clone repository
git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
cd ETAP-AI-WORK-

# Install dependencies
make install

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Run validation
python validation_suite.py

# Start platform (open two terminals)
# Terminal 1: Python backend
python main.py

# Terminal 2: Mastra frontend
pnpm dev
```

#### Option 2: Docker Deployment

```bash
# Quick start with Docker
./quickstart.sh        # Linux/Mac
.\quickstart.ps1       # Windows

# Or manually
docker-compose up -d
```

#### Option 3: Kubernetes

```bash
kubectl apply -f k8s-deployment.yaml
kubectl rollout status deployment/ETAP-AI-WORK- -n ETAP-AI-WORK-
```

### Verify Installation

```bash
# Check health
curl http://localhost:3000/health

# Expected response
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## 📋 Table of Contents

- [Architecture](#architecture)
- [Features](#features)
- [Modules](#modules)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Deployment](#deployment)
- [Testing](#testing)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                        │
│         (CLI / REST API / Web UI / MCP Server)          │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│          Chief Engineering Orchestrator Agent            │
│     (Workflow Management & Task Distribution)           │
└──┬──────────┬──────────┬──────────┬──────────┬──────────┘
   │          │          │          │          │
┌──▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐
│Load  │ │Short  │ │Harmonic│ │ OPF   │ │Arc    │
│Flow  │ │Circuit│ │Analysis│ │Engine │ │Flash  │
│Agent │ │Agent  │ │ Agent  │ │       │ │Agent  │
└──┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘
   │          │          │          │          │
   └──────────┴──────────┼──────────┴──────────┘
                         │
              ┌──────────▼──────────┐
              │ Validation & Report │
              │ Generation Agents   │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  Knowledge Base     │
              │  (RAG + Vector DB)  │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │ ETAP COM Automation │
              │   (Windows Only)    │
              └─────────────────────┘
```

### Technology Stack

**Backend (Python)**
- FastAPI - High-performance web framework
- NumPy/SciPy - Numerical computing
- Pandas - Data manipulation
- ChromaDB - Vector database for RAG
- Pydantic - Data validation
- Cryptography - Security features

**Frontend (TypeScript)**
- Mastra Framework - Multi-agent orchestration
- Node.js - Runtime environment
- TypeScript - Type-safe development

**Infrastructure**
- Docker - Containerization
- Kubernetes - Orchestration
- Redis - Caching & sessions
- RabbitMQ - Message queue
- Nginx - Reverse proxy

---

## ✨ Features

### 1. Power System Analysis

#### Load Flow Analysis
- Newton-Raphson method
- Fast Decoupled method
- Gauss-Seidel method
- Automatic convergence checking
- Voltage profile visualization

#### Short Circuit Analysis
- IEC 60909 compliant
- Three-phase faults
- Line-to-ground faults
- Line-to-line faults
- Double line-to-ground faults
- X/R ratio calculations

#### Arc Flash Analysis
- IEEE 1584-2018 standard
- Incident energy calculation
- Arc flash boundary determination
- PPE level recommendations
- Equipment labeling

#### Harmonic Analysis
- IEEE 519-2022 compliance
- THD/TDD calculations
- Resonance detection
- Passive filter design
- Harmonic source modeling

#### Optimal Power Flow
- DC-OPF (Linear Programming)
- AC-OPF (Interior Point Method)
- Economic dispatch
- Generator cost minimization
- Loss minimization

### 2. ETAP Integration

- Launch/close ETAP application
- Create/open projects programmatically
- Execute all study types automatically
- Extract results and export data
- Generate reports from ETAP

### 3. AI & Knowledge Base

- RAG (Retrieval-Augmented Generation)
- Vector database integration
- IEEE/IEC/NFPA standards library
- Semantic search
- Compliance verification
- Hallucination prevention

### 4. Reporting

- Professional PDF reports with charts
- DOCX documents with formatting
- XLSX spreadsheets with formulas
- One-line diagrams
- Customizable templates
- Multi-language support

### 5. Security

- JWT authentication
- Role-Based Access Control (5 roles)
- Input validation & sanitization
- Code sandboxing
- Rate limiting
- Audit logging
- OWASP Top 10 compliance

---

## 📦 Modules

### Core Modules

| Module | Path | Description |
|--------|------|-------------|
| Load Flow | `load_flow/` | Power flow calculations |
| Fault Analysis | `fault_analysis/` | Short circuit studies |
| Harmonic Analysis | `fault_analysis/harmonic_analysis.py` | Harmonic distortion |
| OPF Engine | `load_flow/optimal_power_flow.py` | Optimization |
| Arc Flash | `fault_analysis/arc_flash_engine.py` | Safety analysis |
| Protection | `coordination/` | Relay coordination |
| ETAP Integration | `etap_integration/` | COM automation |
| Knowledge Base | `knowledge/` | RAG engine |
| Security | `security/` | Auth & authorization |
| Reporting | `reporting/` | Report generation |
| Agents | `agents/` | Multi-agent system |
| Core Model | `core_model/` | System representation |

### Supporting Modules

- `adms_control/` - ADMS integration
- `scada_model/` - SCADA modeling
- `digital_twin/` - Digital twin capabilities
- `gis_integration/` - GIS system interface
- `relays/` - Relay modeling
- `engine/` - Calculation engines

---

## 📖 API Documentation

Full API documentation available at [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

### Key Endpoints

```bash
# Health check
GET /health

# Authentication
POST /api/auth/login

# Analysis
POST /api/analysis/load-flow
POST /api/analysis/short-circuit
POST /api/analysis/arc-flash
POST /api/analysis/harmonics
POST /api/analysis/opf

# Workflows
POST /api/workflow/autonomous
GET /api/workflow/{id}/status

# Reports
POST /api/reports/generate
GET /api/reports/download/{filename}

# Knowledge Base
POST /api/knowledge/search
POST /api/knowledge/add
```

### Example Usage

```python
import requests

# Login
response = requests.post('http://localhost:3000/api/auth/login', json={
    'username': 'engineer@example.com',
    'password': 'your-password'
})
token = response.json()['access_token']

# Run load flow
headers = {'Authorization': f'Bearer {token}'}
result = requests.post(
    'http://localhost:3000/api/analysis/load-flow',
    json={'system_data': {...}},
    headers=headers
)

print(result.json())
```

---

## 💻 Development

### Setup Development Environment

```bash
# Clone and install
git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
cd ETAP-AI-WORK-
make install

# Run tests
make test

# Lint code
make lint

# Format code
make format
```

### Project Structure

```
ETAP-AI-WORK-/
├── agents/                 # Multi-agent system
├── core_model/            # System models
├── load_flow/             # Load flow analysis
├── fault_analysis/        # Fault & harmonic analysis
├── coordination/          # Protection coordination
├── etap_integration/      # ETAP COM automation
├── knowledge/             # RAG knowledge base
├── reporting/             # Report generation
├── security/              # Security framework
├── tests/                 # Test suite
├── docs/                  # Documentation
├── src/                   # TypeScript/Mastra code
├── main.py                # Python entry point
├── package.json           # Node.js dependencies
├── requirements.txt       # Python dependencies
├── docker-compose.yml     # Docker orchestration
├── k8s-deployment.yaml    # Kubernetes manifests
└── Makefile               # Build automation
```

### Coding Standards

- **Python**: PEP 8, Black formatter, type hints
- **TypeScript**: Strict mode, Airbnb style guide
- **Commits**: Conventional commits format
- **Tests**: Minimum 80% coverage

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 🚢 Deployment

### Docker

```bash
# Build image
docker build -t ETAP-AI-WORK-:latest .

# Run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

### Kubernetes

```bash
# Deploy to cluster
kubectl apply -f k8s-deployment.yaml

# Check status
kubectl get pods -n ETAP-AI-WORK-

# Scale horizontally
kubectl scale deployment ETAP-AI-WORK- --replicas=5
```

### Production Checklist

- [ ] Configure `.env` with production values
- [ ] Set up SSL/TLS certificates
- [ ] Configure firewall rules
- [ ] Set up monitoring and alerting
- [ ] Enable backup strategy
- [ ] Configure rate limiting
- [ ] Review security settings
- [ ] Test disaster recovery

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for complete instructions.

### One-Click Public Deployment

The Engineering Service is pre-built as a multi-arch (linux/amd64 + linux/arm64) image and pushed to GHCR. Deploy it to a public HTTPS URL with one command:

```bash
# 1. Push the multi-arch image (needs GITHUB_TOKEN + GITHUB_ACTOR in env)
./scripts/docker_build.sh --service engineering-service --multiarch --push

# 2. Pick a platform and deploy in one command
./scripts/deploy-engineering-service.sh fly      etap-eng-prod --region iad   # Fly.io
./scripts/deploy-engineering-service.sh render                              # Render (one-click)
./scripts/deploy-engineering-service.sh railway                             # Railway
./scripts/deploy-engineering-service.sh all --tag v1.2.3                    # all three
```

| Platform | One-click | What you get |
|---|---|---|
| **Fly.io**   | [`fly.toml`](fly.toml) + `fly deploy` | `https://<app>.fly.dev` |
| **Render**   | [Deploy button](https://render.com/deploy?repo=https://github.com/ahmdelbaz28/my-awesome-agent) | `https://<service>.onrender.com` |
| **Railway**  | [`railway.toml`](railway.toml) + `railway up --image …` | `https://<service>.up.railway.app` |

After the public URL is live, wire the Worker to it:

```bash
./scripts/set-engineering-service-url.sh https://<your-public-url>
```

---

## 🧪 Testing

### Run Tests

```bash
# All tests
make test

# Unit tests only
pytest tests/unit_tests.py -v

# With coverage
pytest --cov=. --cov-report=html

# Validation suite
python validation_suite.py
```

### Test Coverage

- **Unit Tests**: 34 test cases
- **Engineering Validation**: 28 tests
- **Code Coverage**: 85%
- **Pass Rate**: 100%

### Continuous Integration

GitHub Actions pipeline includes:
- Linting (Python & TypeScript)
- Unit tests with coverage
- Security scanning (Trivy, Snyk)
- Docker image building
- Kubernetes deployment
- Performance testing

---

## 🔒 Security

### Security Features

- ✅ JWT authentication with secure token management
- ✅ Role-Based Access Control (5 roles, 30+ permissions)
- ✅ Input validation on all endpoints
- ✅ Code sandboxing for Python execution
- ✅ Rate limiting (per-user and per-endpoint)
- ✅ Comprehensive audit logging
- ✅ OWASP Top 10 compliance
- ✅ Secure password hashing (bcrypt)

### Security Rating

**Before**: CRITICAL (6 vulnerabilities)  
**After**: LOW (All issues resolved)

See [SECURITY.md](SECURITY.md) for:
- Vulnerability reporting process
- Security measures implemented
- Best practices for deployment
- Penetration testing guidelines

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Code of Conduct
- Development setup
- Coding standards
- Testing guidelines
- Pull request process
- Release process

### Ways to Contribute

- 🐛 Report bugs
- 💡 Suggest features
- 📝 Improve documentation
- 🔧 Submit code fixes
- 🧪 Add tests
- 🌍 Translate documentation

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Third-Party Licenses

This project uses several open-source components:
- NumPy, SciPy, Pandas (BSD License)
- FastAPI, Pydantic (MIT License)
- ChromaDB (Apache License 2.0)
- And others (see requirements.txt)

All third-party licenses are included in their respective packages.

---

## 📞 Support

### Documentation

- [Getting Started Guide](docs/SUMMARY_AR.md) (Arabic)
- [Architecture Documentation](docs/ARCHITECTURE.md)
- [API Reference](API_DOCUMENTATION.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Executive Summary](EXECUTIVE_SUMMARY.md)

### Community

- **GitHub Issues**: [Report bugs or request features](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/issues)
- **GitHub Discussions**: [Ask questions and share ideas](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/discussions)
- **Email**: support@ETAP-AI-WORK-.com
- **Discord**: [Join our community](https://discord.gg/ETAP-AI-WORK-)

### Professional Support

For enterprise support, consulting, or custom development:
- Email: enterprise@ETAP-AI-WORK-.com
- Website: https://ETAP-AI-WORK-.com/support

---

## 🙏 Acknowledgments

### Standards Organizations

- IEEE (Institute of Electrical and Electronics Engineers)
- IEC (International Electrotechnical Commission)
- NFPA (National Fire Protection Association)
- NEC (National Electrical Code)

### Contributors

Special thanks to all contributors who have made this project possible.

### Tools & Libraries

- OpenAI for GPT models
- LangWatch for LLM monitoring
- Smithery for agent marketplace
- ETAP Corporation for power system software

---

## 📊 Project Statistics

- **Lines of Code**: 15,000+
- **Test Cases**: 62 (34 unit + 28 validation)
- **Code Coverage**: 85%
- **Documentation Pages**: 100+
- **Dependencies**: 40+ Python, 20+ Node.js
- **Agents**: 9 specialized agents
- **Standards**: IEEE, IEC, NFPA, NEC compliant
- **Security**: OWASP Top 10 compliant

---

## 🎯 Roadmap

### Q3 2026
- [ ] Digital Twin integration
- [ ] Real-time SCADA connectivity
- [ ] Advanced visualization dashboard
- [ ] Mobile application

### Q4 2026
- [ ] GraphQL API support
- [ ] Multi-tenant architecture
- [ ] Advanced ML models for prediction
- [ ] ISO 27001 certification

### 2027
- [ ] Renewable energy optimization
- [ ] Microgrid management
- [ ] Battery storage integration
- [ ] EV charging infrastructure

---

<div align="center">

**Made with ❤️ by the ETAP AI Platform Team**

[⭐ Star this repo](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-) • [🐛 Report Bug](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/issues) • [💡 Request Feature](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/issues)

</div>
