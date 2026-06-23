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

<p align="center">
  <a href="https://github.com/ahmdelbaz28-ux/AhmedETAP">
    <img src="docs/assets/banner.svg" alt="AhmedETAP Banner" width="100%">
  </a>
</p>

<h1 align="center">AhmedETAP</h1>

<p align="center">
  <strong>Enterprise-Grade Autonomous Engineering Intelligence Platform</strong>
  <br>
  <em>Power System Analysis · AI Agent Orchestration · ETAP Integration · GIS Enrichment</em>
</p>

<p align="center">
  <a href="https://github.com/ahmdelbaz28-ux/AhmedETAP/releases">
    <img src="https://img.shields.io/badge/version-1.0.0-blue?style=for-the-badge" alt="Version">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
  </a>
  <a href="https://github.com/ahmdelbaz28-ux/AhmedETAP/actions/workflows/ci-cd.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/ahmdelbaz28-ux/AhmedETAP/ci-cd.yml?style=for-the-badge&label=CI/CD" alt="CI/CD">
  </a>
</p>

<p align="center">
  <a href="https://huggingface.co/spaces/ahmdelbaz28/etap-ai-platform">
    <img src="https://img.shields.io/badge/%F0%9F%A4%97%20Live%20Demo-Hugging%20Face-yellow?style=flat-square" alt="Hugging Face">
  </a>
</p>

---

## Table of Contents
// This is the omitted part
| Engineering validation | 31/31 | Pass |
| Syntax validation | 173/173 | Pass |

---

## Testing Framework

<details>
<summary><strong>Comprehensive Test Suite</strong></summary>

| Category | Coverage | Status |
|----------|----------|---------|
| Unit Tests | 85%+ | Pass |
| Integration Tests | 90%+ | Pass |
| Regression Tests | 100% | Pass |
| Performance Tests | Baseline | Pass |
| Security Tests | Continuous | Pass |

### Running Tests

```bash
# Run all tests
pytest

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m regression    # Regression tests only

# Run with coverage
pytest --cov=. --cov-report=html

# Run tests with specific network configurations
pytest tests/fixtures/  # Test networks: 3-bus, IEEE 14-bus, etc.
```

### Test Network Configurations

- **3-Bus System**: Simple network for basic functionality testing
- **IEEE 14-Bus**: Standard test case for load flow validation
- **Custom Networks**: User-defined systems for edge case testing

### Test Structure
```
tests/
├── conftest.py          # Test configuration and fixtures
├── test_study_service.py # Core study execution tests
├── test_cache_service.py # Cache functionality tests
├── integration/         # API and service integration tests
│   └── test_api_endpoints.py
└── regression/          # Calculation accuracy regression tests
    └── test_calculations_regression.py
```

</details>

---

## Monitoring & Observability

<details>
<summary><strong>Production-Grade Monitoring Stack</strong></summary>

| Component | Status | Purpose |
|-----------|--------|---------|
| Prometheus | ✅ Active | Metrics collection |
| Grafana | ✅ Active | Dashboard visualization |
| Alertmanager | ✅ Configured | Alert routing and notifications |
| OpenTelemetry | ✅ Enabled | Distributed tracing |
| Jaeger | ✅ Available | Trace visualization |

### Key Metrics Tracked

- **Service Health**: Uptime, response times, error rates
- **Study Execution**: Success rates, duration, resource usage
- **Cache Performance**: Hit rates, miss rates, eviction stats
- **API Performance**: Request rates, latency percentiles
- **Resource Utilization**: CPU, memory, disk I/O

### Alerting Configuration

Alertmanager is configured with multiple notification channels:
- **Slack**: Real-time operational alerts
- **Email**: Critical system notifications
- **PagerDuty**: Escalation for severe issues

### Pre-built Dashboards

Grafana dashboards available in `monitoring/grafana_dashboards/`:
- Engineering Service Overview
- API Performance Metrics
- Study Execution Analytics
- Resource Utilization Trends

</details>

---

## Security

<details>
<summary><strong>Security Architecture</strong></summary>

| Layer | Implementation |
|-------|---------------|
| **Authentication** | JWT + bcrypt (14 rounds) + account lockout |
| **Authorization** | RBAC with 5 roles, 25+ permissions |
| **Sandboxing** | Python AST validation, restricted globals |
| **Secrets** | HashiCorp Vault + Fernet encrypted fallback |
| **Rate Limiting** | Token-bucket with LRU eviction |
| **Audit Logging** | JSON-structured with rotation |
| **RASP** | SQLi, XSS, Cmdi, SSRF detection |
| **MFA** | TOTP (RFC 6238) + WebAuthn |
| **Dependency Scanning** | CodeQL + Trivy + TruffleHog |

</details>

### Reporting Vulnerabilities

See [SECURITY.md](SECURITY.md) for responsible disclosure instructions.

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quick Contribution Guide

```bash
# 1. Fork and clone
git clone https://github.com/<your-username>/AhmedETAP.git

# 2. Create branch
git checkout -b feat/my-feature

# 3. Make changes and validate
pytest -q

# 4. Commit and push
git commit -m "feat: add my feature"
git push origin feat/my-feature

# 5. Open a Pull Request
```

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | Core computation engine, load flow, short circuit |
| Phase 2 | ✅ Complete | AI agent orchestration, security framework |
| Phase 3 | ✅ Complete | ETAP COM integration, GIS, SCADA |
| Phase 4 | ✅ Complete | Transient stability, cable sizing, earth grid |
| Phase 5 | ✅ Complete | ML/AI predictive analytics, anomaly detection |
| Phase 6 | ✅ Complete | Kubernetes deployment, monitoring, observability |
| Phase 7 | 🔄 In Progress | Desktop Electron app, UI enhancements |
| Phase 8 | 📋 Planned | Cloud deployment (AWS/Azure), multi-tenant |

See [ROADMAP.md](ROADMAP.md) for detailed planning.

---

## Production Entrypoints

| Category | File | Command / Purpose |
|----------|------|------------------|
| **Production API** | `engineering_service.py` | `python engineering_service.py --host 0.0.0.0 --port 8000` — Main FastAPI engineering service |
| **Production Worker** | (Celery) | `celery -A worker.celery_app worker` — Background task worker (requires celery config) |
| **Database Migration** | `alembic upgrade head` | `alembic upgrade head` — Apply pending database migrations |
| **Dev / Testing** | `scripts/dev/main.py` | Demonstration 3-bus power system example |
| **Dev / Testing** | `scripts/dev/validation_suite.py` | Engineering validation against IEEE test systems |
| **Dev / Testing** | `scripts/dev/validation_campaign.py` | Full verification and validation campaign |
| **Dev / Testing** | `run_complete_setup.py` | Automated setup and test script (CI use) |
| **Dev / Testing** | `scripts/validate_syntax.py` | Python syntax validation across all files |
| **Dev / Testing** | `scripts/security_scan.py` | Hardcoded secrets scanner |
| **Security** | `scripts/set-llm-secrets.sh` | Set LLM API keys as Cloudflare Worker secrets |
| **Security** | `scripts/verify-secrets.sh` | Verify all required secrets are configured |

---

## FAQ

<details>
<summary><strong>What makes AhmedETAP different from traditional ETAP?</strong></summary>

AhmedETAP is open-source with AI agent orchestration, a modern web/desktop UI, Docker support, and 548+ automated tests. Traditional ETAP is proprietary, desktop-only, and lacks AI capabilities.

</details>

<details>
<summary><strong>Can I use AhmedETAP without ETAP installed?</strong></summary>

Yes. The native Python solvers work independently. ETAP COM integration is optional for cross-validation studies.

</details>

<details>
<summary><strong>What standards are supported?</strong></summary>

IEEE 3002.7, IEC 60909, IEEE 1584-2018, IEEE 519-2022, IEC 60255, IEEE 399, IEEE 80, IEC 60364, NFPA 70E.

</details>

<details>
<summary><strong>Is there a cloud-hosted version?</strong></summary>

The live demo runs on Hugging Face Spaces. Self-hosted deployment via Docker or Kubernetes is recommended for production.

</details>

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Backend not responding | `python engineering_service.py --port 8000` |
| UI build fails | `cd ui && pnpm install && pnpm build` |
| Database errors | Check PostgreSQL connection in `.env` |
| ETAP COM unavailable | Windows-only; use native solvers on Linux/macOS |
| Redis connection refused | `docker compose up redis` or check `REDIS_URL` |

See [docs/TROUBLESHOOTING_GUIDE.md](docs/TROUBLESHOOTING_GUIDE.md) for comprehensive diagnostics.

---

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

```
MIT License — Copyright (c) 2026 Eng. Ahmed Elbaz
```

---

## Author

<p align="center">
  <a href="https://github.com/ahmdelbaz28-ux">
    <img src="https://github.com/ahmdelbaz28-ux.png" width="100" style="border-radius:50%">
  </a>
  <br>
  <strong>Eng. Ahmed Elbaz</strong>
  <br>
  <em>Electrical Power Engineer & AI Systems Architect</em>
  <br>
  <a href="mailto:ahmdelbaz28@gmail.com">ahmdelbaz28@gmail.com</a> ·
  <a href="https://github.com/ahmdelbaz28-ux">GitHub</a> ·
  <a href="https://huggingface.co/spaces/ahmdelbaz28/etap-ai-platform">Live Demo</a>
</p>

---

<p align="center">
  <sub>Built with precision for the power systems engineering community.</sub>
</p