# Codebase Map — AhmedETAP

## Repository Root Structure

```
AhmedETAP/
├── 📁 acp_runtime/          # ACP runtime (Agent Communication Protocol)
├── 📁 adms_control/         # ADMS control module
├── 📁 agents/               # 🤖 19 AI agent modules
│   ├── orchestrator.py      # Chief Engineering Orchestrator
│   ├── prompt_loader.py     # 3-tier prompt management
│   ├── stability_agent.py   # Transient stability
│   ├── cable_sizing_agent.py
│   ├── earth_grid_agent.py
│   ├── renewable_agent.py
│   ├── battery_storage_agent.py
│   ├── scada_agent.py
│   ├── weather_agent.py
│   ├── anomaly_agent.py
│   ├── predictive_agent.py
│   ├── goal_planner_agent.py
│   ├── code_guard_agent.py
│   ├── arc_flash_agent.py
│   ├── coordination_agent.py
│   ├── digital_twin_agent.py
│   ├── motor_starting_agent.py
│   └── __init__.py
├── 📁 api/                  # 🔌 FastAPI routers
│   ├── auth.py              # JWT authentication
│   ├── projects.py          # Project CRUD
│   ├── database.py          # Async SQLAlchemy
│   ├── dependencies.py      # FastAPI dependencies
│   ├── coverage_report.py
│   ├── error_debugger.py
│   ├── refactored_service.py
│   └── security_audit.py
├── 📁 backend/              # Backend utilities
│   └── request_context.py
├── 📁 benchmarks/           # Performance benchmarks
├── 📁 charts/               # Kubernetes Helm charts
│   └── etap-ai/
├── 📁 config/               # Configuration files
│   ├── grafana-datasources/
│   └── promtail.yml
├── 📁 coordination/         # ⚡ Protection coordination
│   └── coordination.py
├── 📁 core/                 # Core database module
│   ├── database.py
│   └── models.py
├── 📁 core_model/           # ⚡ Power system models
│   ├── system.py            # System class
│   ├── bus.py               # Bus model
│   ├── line.py              # Transmission line
│   ├── generator.py         # Generator model
│   ├── load.py              # Load model
│   ├── transformer.py       # Transformer model
│   ├── motor_model.py       # Motor model
│   └── zip_load.py          # ZIP load model
├── 📁 curves/               # Relay curves
│   └── curves.py
├── 📁 data/                 # Data files
├── 📁 digital_twin/         # 🔗 Digital twin
│   ├── digital_twin_core.py
│   ├── event_bus.py
│   ├── handlers.py
│   ├── state_store.py
│   └── validation_gateway.py
├── 📁 docs/                 # 📚 Documentation
│   ├── ARCHITECTURE.md
│   ├── assets/
│   ├── diagrams/
│   ├── screenshots/
│   └── internal/
├── 📁 engine/               # ⚡ Computation engine
│   ├── engine.py            # PowerSystemEngine
│   ├── gpu_solver.py        # GPU acceleration
│   ├── sparse_solver.py     # Sparse matrices
│   ├── caching.py           # Redis cache
│   ├── cache_manager.py
│   ├── async_executor.py
│   ├── data_optimizer.py
│   ├── error_handler.py
│   ├── interfaces.py        # Engine protocols
│   ├── numerical_safety.py
│   ├── resilience.py
│   └── scalability.py
├── 📁 etap_integration/     # 🔗 ETAP COM automation
│   ├── etap_com.py
│   ├── etap_compatibility.py
│   ├── etap_error_recovery.py
│   ├── etap_provider.py
│   ├── etap_worker_service.py
│   └── scada_client.py
├── 📁 fault_analysis/       # ⚡ Fault analysis
│   ├── fault.py             # Short circuit (IEC 60909)
│   ├── arc_flash_engine.py  # Arc flash (IEEE 1584)
│   ├── arc_flash_calc.py
│   ├── harmonic_analysis.py # Harmonics (IEEE 519)
│   ├── iec60909_engine.py
│   └── ieee1584_database.py
├── 📁 gis_integration/      # 🔗 GIS integration
│   ├── base.py
│   ├── models.py
│   ├── transformer.py
│   ├── utils.py
│   ├── exceptions.py
│   └── providers/
├── 📁 gis_model/            # GIS data model
├── 📁 gis_validation/       # GIS validation
├── 📁 gis_validation_electrical/
├── 📁 gis_validation_real/
├── 📁 guards/               # 🛡️ Code quality guards
│   ├── base.py
│   ├── code_guard.py
│   ├── test_guard.py
│   ├── docs_guard.py
│   └── ai_failure_modes.py
├── 📁 knowledge/            # 📚 Knowledge base
│   └── rag_engine.py
├── 📁 load_flow/            # ⚡ Load flow solvers
│   ├── load_flow.py
│   ├── load_flow.py  # Canonical Newton-Raphson solver (consolidated)
│   ├── optimal_power_flow.py
│   └── solver.py
├── 📁 migrations/           # Database migrations
│   └── versions/
├── 📁 ml/                   # 🤖 Machine learning
│   └── predictive.py
├── 📁 network_solver/       # Network matrix solver
│   ├── zbus.py
│   └── per_unit.py
├── 📁 prompts/              # 🤖 Agent prompts (YAML)
│   ├── load_flow_agent.prompt.yaml
│   ├── short_circuit_agent.prompt.yaml
│   ├── arcflash_agent.prompt.yaml
│   └── ... (24 prompt files)
├── 📁 relays/               # ⚡ Relay models
│   └── relay.py
├── 📁 reporting/            # 📊 Report generation
│   └── advanced_reports.py
├── 📁 scada_model/          # 🔗 SCADA data model
│   ├── scada_model.py
│   └── state_estimation.py
├── 📁 scripts/              # Utility scripts
├── 📁 security/             # 🛡️ Security framework
│   ├── security_framework.py
│   ├── secrets_manager.py
│   ├── secure_executor.py
│   ├── secure_powershell_executor.py
│   ├── rasp.py
│   ├── mfa.py
│   ├── abac.py
│   └── siem.py
├── 📁 src/                  # Mastra AI agents (TypeScript)
│   ├── core/
│   └── mastra/
├── 📁 tests/                # 🧪 Test suites
│   ├── scenarios/
│   ├── chaos/
│   ├── load/
│   ├── stress/
│   └── *.py, *.ts
├── 📁 ui/                   # 🖥️ React frontend
│   ├── electron/
│   └── src/
├── 📁 visualization/        # 📊 Chart generation
│   └── visualization.py
├── 🔧 engineering_service.py  # Main FastAPI app
├── 🔧 main.py                 # Demo script
├── 🔧 validate_syntax.py      # Syntax validation
├── 🔧 validation_suite.py     # Validation suite
├── 🔧 validation_campaign.py  # Validation campaign
├── 📦 Dockerfile
├── 📦 Dockerfile.engineering-service
├── 📦 Dockerfile.hf
├── 📦 docker-compose.yml
├── 📦 requirements.txt
├── 📦 package.json
└── 📦 Makefile
```

## File Importance Levels

| Level | Description | Example |
|-------|-------------|---------|
| 🔴 Critical | Core entry points, must not break | `engineering_service.py`, `engine/engine.py` |
| 🟠 High | Primary functionality | `api/auth.py`, `agents/orchestrator.py`, `App.tsx` |
| 🟡 Medium | Supporting modules | `load_flow/load_flow.py`, `pages/Dashboard.tsx` |
| 🟢 Low | Utilities, helpers | `visualization/visualization.py`, `utils/helpers.ts` |
| ⚪ Optional | Extras, configs | `benchmarks/`, `scripts/`, `.mcp.json` |
