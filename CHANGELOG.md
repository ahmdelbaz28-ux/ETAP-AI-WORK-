# Changelog

All notable changes to AhmedETAP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

<<<<<<< HEAD
## [Unreleased]

### UI/Backend coverage — pass-2 (branch `fix/ui-backend-coverage-pass-2`)

This pass closes 4 of the 4 tasks left undone by pass-1 (TASK-8, 9, 11, 13, 14)
and adds backend infrastructure for two of them.

- **TASK-8 — AI/ML Playground page** (`ui/src/pages/AIPlayground.tsx`, route
  `/admin/ai-playground`). Tabs for all 5 endpoints in `api/ai_ml.py`:
  `predict/load`, `predict/fault`, `predict/anomaly`, `gnn/predict`, `rag/query`.
  JSON editor with required-key validation, result viewer, rate-limit indicator,
  recent-runs history. Playwright smoke tests in `ui/tests/ai-playground.spec.ts`.
- **TASK-9 — Feature Flags router + admin panel**. `api/feature_flags.py`
  converted from pure module to FastAPI router at `/api/v1/feature-flags` with
  `GET /`, `GET /{key}`, `PATCH /{key}` (admin-only). Toggles persist to
  `.feature-flags.json` so they survive restarts. New "Feature Flags" section
  in `Administration.tsx` with per-flag toggle, dev-override banner, loading
  and error states. Backend tests: `tests/test_feature_flags.py` (16 tests,
  all passing).
- **TASK-11 — Settings.tsx config-drift fix**. Removed the hardcoded
  `MCP_SERVERS` constant; the `MCPSettingsPanel` now fetches from a new
  `GET /api/v1/agents/mcp-servers` endpoint (added in `api/agents.py`) that
  reads `.mcp.json` and redacts all env values server-side. The constant is
  retained as `MCP_SERVERS_FALLBACK` and only shown when the backend is
  unreachable or `.mcp.json` is absent, with a visible banner explaining the
  fallback. Loading / error / degraded states all handled.
- **TASK-12 — Tests**. Added `tests/test_feature_flags.py` (16 backend tests)
  and `ui/tests/ai-playground.spec.ts` (5 Playwright smoke tests). All new
  tests pass.
- **TASK-13 — Security scan**. Ran `bandit -r api/ -ll` (0 HIGH, 0 CRITICAL,
  2 MEDIUM, 41 LOW — no new HIGH/CRITICAL introduced by pass-2) and
  `pnpm audit --audit-level=high` (3 HIGH in `undici`, all pre-existing and
  transitive via `@langwatch/scenario`). Report saved to
  `download/security-scan-2026-08-04.txt`.
- **TASK-14 — Documentation**. Added §12 "Pass-2 Update" to
  `UI_COVERAGE_REPORT.md` with re-counted endpoint inventory (150 HTTP + 4 WS =
  154 total, across 30 router files) and updated coverage score (77.9%, up
  from 68.3%).

#### Deviations from pass-1 (accepted, not reverted)

- **TASK-5** was implemented as a new `AgentsControlPanel.tsx` page rather
  than extending `CuaMonitor.tsx`. Accepted because the page already ships
  with tests and covers all 14 `agents.py` endpoints.
- **TASK-7** was implemented as a separate `Mfa.tsx` page rather than a tab
  in `Settings.tsx`. Accepted for the same reason.
- **TASK-10** was implemented as a separate `MagicLinks.tsx` page rather
  than a tab in `Login.tsx`. Accepted for the same reason.
- **`EmailOtp.tsx`** was added in pass-1 but is not in the original task
  list. Retained because it has tests and may be useful; documented as a
  pass-1 addition.

#### Residual gaps (follow-up pass-3 needed)

- `api/pe_stamp.py`, `api/dual_control.py`, `api/risk_scoring.py`,
  `api/error_debugger.py` still have zero UI consumers.
- `cua_confirmation_ws` WebSocket still has no UI consumer.
- `pnpm audit` 3 HIGH in `undici` need an override bump to `>=6.27.0`.

### Security — Python dependencies (pip)
- **LangChain 0.3.x → 1.x major upgrade** to resolve Dependabot alerts on
  `langchain-core`, `langchain-openai`, and `langsmith`. The 0.3.x line is
  end-of-life and ships vulnerable transitive dependencies (httpx, pydantic,
  requests). All langchain packages are now pinned to the maintained 1.x line:
  - `langchain-core>=1.0.0,<2` (resolves to 1.5.3 in uv.lock)
  - `langchain-openai>=1.0.0,<2` (resolves to 1.4.1)
  - `langchain-qdrant>=1.0.0,<2` (resolves to 1.1.0)
  - `langchain-community>=0.4.0,<0.5` (resolves to 0.4.2)
  - `langchain-experimental>=0.4.0,<0.5` (resolves to 0.4.2)
  - `langchain-neo4j>=0.10.0,<0.11` (resolves to 0.10.0)
  - `langsmith>=0.10.0,<0.11` (resolves to 0.10.15)
- **cryptography bumped 48.0.1 → 49.0.0+** (resolves to 50.0.0 in uv.lock) —
  fixes CVE-2026-26007 (subgroup attack on SECT curves) and the vulnerable
  bundled OpenSSL CVEs. (Dependabot suggested 46.0.5 but no such release
  exists on PyPI; we go straight to the latest stable line.)
- **PyJWT bumped 2.9.0 → 2.13.0** — fixes CVE-2026-32597 (accepts unknown
  `crit` header extensions) and CVE-2026-48526 (public-key JWK accepted as
  HMAC secret enables forged HS256 tokens).
- **starlette bumped 0.40.x → 1.3.1** + **fastapi bumped 0.115.4 → 0.135.0**
  (fastapi 0.133+ is the first release that drops the `starlette<1.0.0`
  upper bound). Fixes 6 CVEs that affect the 0.40.x starlette line:
  - Range header O(n²) DoS in FileResponse              (HIGH)
  - SSRF + NTLM credential theft via UNC paths on Win   (HIGH)
  - request.form() limit bypass DoS                      (HIGH)
  - Multipart large-file parsing DoS                     (MED)
  - Host header poisoning bypasses path security         (MED)
  - Arbitrary HTTP method dispatch via getattr           (MED)
- **nltk bumped 3.9.4 → 3.10.0** — fixes URL-Encoded Path Traversal in
  `nltk.data.load()` and 4 other CVEs (ReDoS, SSRF, path traversal).
- **Pygments bumped 2.18.0 → 2.20.0** — fixes ReDoS via GUID-matching regex.
- **setuptools bumped ≥68 → ≥83.0.0** (in `pyproject.toml` build-system) —
  fixes MANIFEST.in exclusion bypass via Unicode NFC/NFD normalization.
- **chromadb**: documented that the critical pre-auth code injection CVE
  (affects ≤1.5.9) has no upstream fix yet; mitigation is to never expose
  port 8000 to the public internet.

### Security — Node dependencies (npm)
- **pnpm-workspace.yaml**: added `overrides` block (pnpm 11+ reads overrides
  from `pnpm-workspace.yaml`, NOT from `package.json` `pnpm.overrides` field).
  This drops npm-side Dependabot alerts from 72 → 2 (the remaining 2 have
  no upstream fix available — see notes below).
- **protobufjs bumped 8.0.1 → ^8.6.6** — fixes the CRITICAL Arbitrary Code
  Execution CVE plus 24 high/medium alerts. The previous `overrides` block
  in `package.json` was pinning protobufjs to **exactly the vulnerable
  version** (8.0.1); this was the single most impactful fix in this release.
- **langsmith (npm) bumped 0.3.87 → ^0.8.0** — pulled in transitively by
  `langwatch`. Fixes 8 alerts (SSRF, prototype pollution, redaction bypass).
- **axios bumped → ^1.18.0** — fixes 10 alerts (prototype pollution,
  proxy inheritance, body limit bypass, maxBodyLength bypass).
- **brace-expansion bumped → ^5.0.8** — fixes 8 DoS alerts.
- **hono bumped → ^4.12.27** — fixes 8 alerts (CORS reflection, XSS,
  path traversal, body limit bypass).
- **js-yaml bumped → ^4.3.0** — fixes 3 quadratic CPU consumption alerts.
- **fast-uri bumped → ^3.1.4** — fixes 2 host-confusion alerts.
- **linkify-it bumped → ^5.0.2**, **liquidjs → ^10.27.1**,
  **postcss → ^8.5.18**, **shell-quote → ^1.9.0**, **tar → ^7.5.21**,
  **uuid → ^11.1.1**, **body-parser → ^2.3.0** — fix 1 alert each.
- **@opentelemetry/{exporter-prometheus, sdk-node, propagator-jaeger,
  core}** bumped — fix 8 OpenTelemetry alerts combined.
- **@hono/node-server bumped → ^2.0.5** — fixes 2 path-traversal alerts.
- **Remaining unfixable (documented in pnpm-workspace.yaml):**
  - `react-router` (HIGH, GHSA-qwww-vcr4-c8h2) — patched version 8.3.0 has
    not been published to npm. Mitigation: this app does not use RSC mode,
    so the vulnerable code path is unreachable.
  - `@ai-sdk/provider-utils` (LOW, GHSA-866g-f22w-33x8) — `@mastra/core`
    uses package aliases (`@ai-sdk/provider-utils-v5`/`-v6`) that resolve
    to old 3.x/4.x versions which pnpm overrides do not rewrite. Mitigation:
    DoS only via streaming LLM responses; track @mastra/core upstream.

### Changed
- `services/memory_service.py`: migrated from the deprecated LangChain 0.x
  API surface to the 1.x API:
  - `BaseChatModel.predict(text)` → `BaseChatModel.invoke(text).content`
  - `Chain.run(query)` → `Chain.invoke({"query": query})["result"]`
  - The internal `DummyLLM` fallback now exposes both `.invoke()` (1.x)
    and `.predict()` (legacy) for backward compatibility.
- `uv.lock`: regenerated against the new constraints (langchain 1.5.3,
  langsmith 0.10.15, cryptography 50.0.0, fastapi 0.141.1, starlette 1.3.1,
  nltk 3.10.1, pygments 2.20.0, pyjwt 2.13.0, setuptools 83.0.0).
- `pnpm-lock.yaml`: regenerated against the new overrides (protobufjs 8.6.6,
  langsmith 0.8.x, axios 1.18+, hono 4.12.27+, etc.).
- `package.json`: removed the legacy `"pnpm": { "overrides": {...} }` block
  (pnpm 11+ ignores it; overrides moved to `pnpm-workspace.yaml`). Kept the
  top-level `"overrides": {...}` block (read by npm).

### Verification
- `pip install --dry-run` against the new constraints resolves cleanly to
  the intended 1.x / 49.x / 1.3.x / 0.135.x / 3.10.x / 2.20.x / 83.x versions.
- `pnpm audit` reports 2 remaining vulnerabilities (down from 72), both
  with documented upstream-blocker reasons and mitigations.
- `uv lock --upgrade-package …` succeeded against the new constraints.
- AST scan confirms no remaining `.predict()` / `.run()` callsites on
  LLM/chain objects in `services/memory_service.py`.

=======
>>>>>>> origin/fix/scenario-tests-properly
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
<<<<<<< HEAD
- 25 AI agents with task planning and RAG context
=======
- 23 AI agents with task planning and RAG context
>>>>>>> origin/fix/scenario-tests-properly
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
