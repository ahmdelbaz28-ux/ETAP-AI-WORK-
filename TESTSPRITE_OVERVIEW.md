# AhmedETAP — TestSprite Overview

> Use this document to help TestSprite understand the project before running tests.

## Project Identity

- **Name:** AhmedETAP
- **Type:** Full-stack enterprise AI platform (monorepo)
- **Version:** 1.0.0
- **Author:** Eng Ahmed Elbaz (ahmdelbaz28@gmail.com)
- **Repository:** https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-
- **Live Demo:** https://huggingface.co/spaces/ahmdelbaz28/etap-ai-platform

## Architecture Overview

```
Client Layer (React 19 UI + Electron) → API Layer (FastAPI + Mastra) → 
Engineering Engine (Python solvers) → Integration Layer (ETAP COM, GIS, SCADA)
```

## Tech Stack

| Layer | Technology | Key Files/Dirs |
|-------|-----------|----------------|
| **Backend API** | Python 3.12+, FastAPI | `engineering_service.py` |
| **Frontend** | React 19, TypeScript 5.7, Tailwind CSS 4 | `ui/src/pages/*.tsx` |
| **AI Agents** | Mastra framework, 9 specialized agents | `src/mastra/agents/*.ts`, `agents/*.py` |
| **Engineering** | NumPy, SciPy, custom solvers | `engine/`, `load_flow/`, `fault_analysis/` |
| **Database** | DuckDB, PostgreSQL (optional) | `mastra.duckdb` |
| **Deployment** | Docker, Docker Compose, Hugging Face Spaces | `Dockerfile`, `Dockerfile.hf` |

## Key Modules to Test

### 1. Engineering Solvers (Python — Highest Priority)
| Module | Files | Description |
|--------|-------|-------------|
| Load Flow | `load_flow/load_flow.py`, `network_solver/zbus.py` | Newton-Raphson, Fast Decoupled power flow |
| Short Circuit | `fault_analysis/iec60909_engine.py`, `fault_analysis/fault.py` | IEC 60909 fault analysis |
| Arc Flash | `fault_analysis/arc_flash_calc.py`, `fault_analysis/arc_flash_engine.py` | IEEE 1584-2018 incident energy |
| Harmonics | `fault_analysis/harmonic_analysis.py` | THD/TDD analysis (IEEE 519) |
| Protection | `relays/relay.py`, `coordination/coordination.py` | IEC 60255 relay coordination |
| Optimal Power Flow | `load_flow/optimal_power_flow.py` | AC/DC OPF with economic dispatch |
| Motor Starting | `core_model/motor_model.py` | Motor starting analysis |

### 2. AI Agent Layer (Python + TypeScript)
| Agent | File | Purpose |
|-------|------|---------|
| Arc Flash Agent | `agents/arc_flash_agent.py`, `src/mastra/agents/arcflash-agent.ts` | Arc flash study specialist |
| Load Flow Agent | `src/mastra/agents/loadflow-agent.ts` | Power flow analysis |
| Short Circuit Agent | `src/mastra/agents/shortcircuit-agent.ts` | Fault analysis |
| Protection Agent | `src/mastra/agents/protection-agent.ts` | Relay coordination |
| Motor Starting Agent | `src/mastra/agents/motorstarting-agent.ts` | Motor analysis |
| Weather Agent | `agents/weather_agent.py`, `src/mastra/agents/weather-agent.ts` | Weather data integration |
| Goal Planner | `agents/goal_planner_agent.py`, `src/mastra/agents/goal-planner-agent.ts` | Task orchestration |
| ETAP Engineer | `agents/orchestrator.py`, `src/mastra/agents/etap-engineer-agent.ts` | ETAP COM integration |
| Power System Coordinator | `src/mastra/agents/power-system-coordinator-agent.ts` | Multi-agent coordinator |

### 3. API Layer (Python)
| Endpoint | Route | Description |
|----------|-------|-------------|
| Study Execution | `POST /api/v1/studies/run` | Run any engineering study |
| System Validation | `POST /api/v1/system/validate` | Validate power system model |
| Guard Review | `POST /api/v1/guards/review` | Code quality review |
| RAG Query | `POST /api/v1/rag/query` | Knowledge base search |
| Predictive ML | `POST /api/v1/predict/*` | Load/fault/anomaly prediction |
| SCADA | `GET /api/v1/scada/live` | Live SCADA data |
| Digital Twin | `GET /api/v1/digital-twin/status` | Digital twin sync |
| Security | `POST /api/v1/auth/*` | MFA, ABAC, SIEM |
| Benchmark | `GET /api/v1/benchmark` | Solver benchmarks |

### 4. Frontend (React 19 + TypeScript)
| Page | File | Purpose |
|------|------|---------|
| Dashboard | `ui/src/pages/Dashboard.tsx` | System overview, charts, health |
| AI Assistant | `ui/src/pages/AIAssistant.tsx` | Chat with AI agents |
| Studies | `ui/src/pages/Studies.tsx` | Browse and run studies |
| Study Run | `ui/src/pages/StudyRun.tsx` | Execute a study |
| Asset Management | `ui/src/pages/AssetManagement.tsx` | Power system assets |
| Settings | `ui/src/pages/Settings.tsx` | API keys, providers, config |
| Digital Twin | `ui/src/pages/DigitalTwin.tsx` | Digital twin visualization |
| GIS Integration | `ui/src/pages/GisIntegration.tsx` | GIS data import |
| ETAP Integration | `ui/src/pages/EtapIntegration.tsx` | ETAP connection |
| Reports | `ui/src/pages/Reports.tsx` | Engineering reports |
| Diagnostics | `ui/src/pages/Diagnostics.tsx` | System diagnostics |
| Projects | `ui/src/pages/Projects.tsx` | Project management |
| Administration | `ui/src/pages/Administration.tsx` | User/role management |
| Data Export/Import | `ui/src/pages/DataExport.tsx`, `DataImport.tsx` | Data IO |
| Logs | `ui/src/pages/Logs.tsx` | Audit log viewer |

### 5. Integration Layer
| System | Directory | Purpose |
|--------|-----------|---------|
| ETAP COM | `etap_integration/` | Windows COM automation |
| GIS (ArcGIS, QGIS) | `gis_integration/`, `gis_validation/` | Spatial data enrichment |
| SCADA | `scada_model/` | IEC 61850 data model |
| Digital Twin | `digital_twin/` | State store, event bus |

### 6. Security & Infrastructure
| Module | Directory | Features |
|--------|-----------|----------|
| Auth | `security/`, `src/core/auth.ts` | JWT, RBAC (5 roles), MFA (TOTP) |
| Sandbox | `security/secure_executor.py` | Python sandboxing |
| Guard Skills | `guards/` | Code, test, docs quality gates |
| CI/CD | `.github/workflows/` | 10 GitHub Actions workflows |

## Existing Tests

| Test Suite | Location | Count |
|------------|----------|-------|
| Vitest (API) | `tests/index.test.ts` | 16 tests |
| E2E Workflow | `tests/scenarios/e2e-workflow.test.ts` | 14 tests |
| ETAP Integration | `tests/scenarios/etap-integration.test.ts` | 6 tests |
| Engineering Service | `tests/engineering-service.test.ts` | 8 tests |
| Multi-Agent | `tests/scenarios/multi-agent-workflow.test.ts` | 5 tests |
| Power System Coordinator | `tests/scenarios/power-system-coordinator.test.ts` | 1 test |
| Dashboard UI | `ui/src/pages/__tests__/Dashboard.test.tsx` | 3 tests |
| Stress Test | `tests/stress/stress-test.ts` | Performance |
| Load Test | `tests/load/load-test.ts` | Load testing |
| Chaos Test | `tests/chaos/chaos-test.ts` | Chaos engineering |
| Python Unit Tests | `tests/unit_tests.py` | Various |
| Python Arc Flash | `tests/test_arc_flash_single_engine.py` | Arc flash |

## Testing Priorities (Recommended Order)

1. **Critical path:** Engineering solvers → API endpoints → AI agents
2. **Integration:** ETAP COM → GIS → SCADA → Digital Twin
3. **Frontend:** Dashboard → Studies → Settings → Asset Management
4. **Security:** Auth → Guard skills → Sandboxing → Rate limiting
5. **Performance:** Stress test → Load test → Benchmark

## Environment Setup for Tests

- **Port:** Engineering API runs on `:8000`, UI on `:5173`
- **Auth:** Set `ENGINEERING_SERVICE_API_KEY` or use `AUTH_DISABLED=true`
- **Database:** DuckDB at `mastra.duckdb` (auto-created)
- **Dependencies:** `pip install -r requirements.txt` (Python), `pnpm install` (Node)
- **Run API:** `python engineering_service.py --port 8000`
- **Run UI:** `cd ui && pnpm dev`

## Project Stats

- **Languages:** Python (250 files), TypeScript (66 files), TSX/React (35 files)
- **Total files:** 584 tracked in git
- **Test files:** 727 test/spec files across Python + TypeScript
- **Existing passing tests:** 43 (Vitest), 0 failures
- **Python syntax validated:** 250 files, 0 errors
