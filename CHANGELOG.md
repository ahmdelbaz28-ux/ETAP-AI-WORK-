# Changelog

All notable changes to AhmedETAP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.0] - 2026-06-17

### Added
- PostGIS spatial provider for geospatial data (GIS integration layer)
- GIS ↔ Digital Twin bidirectional synchronization bridge
- ETAP ↔ AhmedETAP synchronization engine (import/export pipeline)
- GIS map visualization (6 layer types: load flow, voltage, fault, arc flash, protection, network)
- Property-based tests (Hypothesis): 22 tests covering skill validation, retry behavior
- Pydantic skill validation models (SkillMetadata, SkillDescription, ExecutionResult, SkillDefinition, SkillResponse[T])
- Tenacity retry decorators (network, skill, bounded, exponential backoff with jitter)
- Pre-commit CI pipeline (6 stages: quality, typecheck, tests, schema validation, security)
- Ruff linting configuration (extended rules: N, UP, C4, isort, line-length=100)
- Prometheus metrics instrumentation (counters, histograms, gauges, decorators)
- OpenTelemetry tracing (TracerProvider, spans, context propagation)
- Factory Boy test fixtures (SkillMetadata, ExecutionResult, ErrorResponse, SkillDescription)
- Analytical Jacobian for Newton-Raphson load flow (replaces finite-difference)
- Sparse LU factorization for fault analysis (replaces dense Zbus inversion)
- `__slots__` optimization on core model classes (Bus, Line, Load, Generator, Transformer, System)
- 31 integration tests for new modules (prometheus, tracing, factories)

### Changed
- Rebranded to "AhmedETAP" by Eng. Ahmed Elbaz

## [1.0.0] - 2026-06-16

### Added
- Load Flow analysis (Newton-Raphson, Fast Decoupled, DC-OPF)
- Short Circuit analysis (IEC 60909)
- Arc Flash analysis (IEEE 1584-2018)
- Harmonic Analysis (IEEE 519-2022)
- Protection Coordination (IEC 60255)
- Optimal Power Flow (AC/DC)
- Motor Starting analysis
- 25 AI agents with task planning and RAG context
- ETAP COM automation integration
- GIS integration (ArcGIS, QGIS)
- SCADA data model (IEC 61850)
- Digital Twin synchronization
- JWT authentication with RBAC (5 roles)
- Python sandboxing with AST validation
- Secrets management (HashiCorp Vault + Fernet)
- MFA support (TOTP + WebAuthn)
- RASP (Runtime Application Self-Protection)
- Smart Help system with context-aware assistance
- Command palette (Ctrl+K)
- Onboarding tour for new users
- Engineering workspace with resizable panels
- Context panel with item details and warnings
- Error recovery assistant
- React 19 frontend with Tailwind CSS 4
- Electron desktop app (Windows, Linux, macOS)
- 548 automated tests
- 13 CI/CD workflows
- Docker deployment support
- Kubernetes Helm charts
- Hugging Face Spaces deployment
- Dark and Light theme support
- Arabic and English internationalization (RTL)
- Comprehensive API documentation (Swagger/OpenAPI)

## [0.9.0] - 2026-05-01

### Added
- Transient stability analysis
- Cable sizing verification
- Earth grid calculation
- Renewable energy integration
- Battery storage analysis
- SCADA agent
- Digital twin agent
- Predictive analytics (LSTM, Random Forest)
- Anomaly detection (Isolation Forest)
- RAG knowledge base

## [0.8.0] - 2026-03-01

### Added
- Initial release of AhmedETAP
- Core computation engine
- FastAPI engineering service
- React frontend
- Docker deployment
