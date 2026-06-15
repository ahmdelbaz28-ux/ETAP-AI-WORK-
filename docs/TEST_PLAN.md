# Quality Assurance Test Plan

## TEST_SCOPE

This test plan covers the ETAP AI Engineering Platform quality gates for the following domains:

- **Python engineering engines**: core power-system models, load-flow solvers, short-circuit analysis, arc-flash calculations, protection coordination, and validation suites.
- **ETAP integration**: ETAP COM automation workflows, Windows worker connectivity, study execution, and result reconciliation.
- **GIS integration**: topology validation, electrical attribute enrichment, spatial data ingestion, and cross-validation against power-system models.
- **Mastra UI**: TypeScript/Mastra frontend build, type checking, lint validation, and Smoke-test readiness.
- **Docker/Kubernetes**: container build verification, docker-compose configuration validation, Kubernetes manifest sanity, image target layer checks.
- **Security**: secret scanning, filesystem vulnerability assessment, dependency audit, JWT/RBAC validation, and audit-log completeness.
- **Nightly regression**: full validation suite execution, performance baseline tracking, cross-environment consistency, and gated release readiness.

Out of scope for this plan: manual ETAP GUI interaction, customer-specific data migrations, and third-party vendor certifications.

## TEST_TYPES

| Test Type | Purpose | Automation Level | Trigger |
|---|---|---|---|
| Syntax validation | Python AST parsing, import resolution, circular dependency detection | Fully automated | PRE_COMMIT |
| Unit tests | Component-level correctness for models, solvers, and utilities | Fully automated | PRE_COMMIT |
| Type checking | TypeScript type safety for Mastra UI | Fully automated | PRE_COMMIT |
| Lint | Code style and static analysis for Python and TypeScript | Fully automated | PRE_COMMIT |
| Validation suite | IEEE/IEC reference-case validation (load flow, short circuit, arc flash, coordination) | Fully automated | PRE_COMMIT, SCHEDULED |
| Integration tests | Cross-component workflows, API contracts, ETAP bridge, GIS enrichment | Fully automated | PRE_BUILD |
| Build verification | Docker multi-stage targets, compose config, engineering-service image | Fully automated | PRE_BUILD, SCHEDULED |
| E2E smoke tests | End-to-end startup, CLI invocation, and dependency presence | Fully automated | POST_BUILD |
| Security scan | Container filesystem vulnerability scan, CRITICAL/HIGH findings | Fully automated | POST_BUILD |
| Visual regression readiness | UI build and baseline artifact generation | Semi-automated | POST_BUILD |
| Nightly regression | Full test matrix, performance baseline, cross-branch comparison | Fully automated | SCHEDULED |

## TEST_ENVIRONMENT

### Runtime versions

- Python 3.13
- Node.js 22
- pnpm 9+
- Docker 24+ and Docker Compose v2+
- kubectl 1.28+ (for Kubernetes validation)

### Infrastructure

- Linux runner (ubuntu-latest)
- Docker-in-Docker enabled for build and security scan stages
- Network-isolated sandbox for security scanning
- Artifact retention: 30 days for test reports, 90 days for SARIF and baseline reports

### Configuration

- Environment variables injected via CI/CD secrets store
- No production secrets in test fixtures
- Synthetic datasets used for all regression tests
- Test concurrency groups prevent resource contention for scheduled jobs

## TEST_SCHEDULE

| Gate | Frequency | Trigger |
|---|---|---|
| PRE_COMMIT | Every push / PR | `push`, `pull_request` |
| PRE_BUILD | Every push to main / PR merge | `push` to `main`, `pull_request` |
| POST_BUILD | Every successful build on main | `workflow_run` on success of build/deploy |
| SCHEDULED | Nightly at 02:00 UTC | `schedule: cron('0 2 * * *')` plus `workflow_dispatch` |

### Performance baselines

- Validation suite runtime: baseline captured on each successful SCHEDULED run
- Pytest suite runtime: baseline tracked with 10% tolerance band
- Docker build time: baseline per target (python-builder, ts-builder, engineering-service)
- Security scan: zero CRITICAL findings allowed; HIGH findings tracked with 24h SLA

## RISK_ANALYSIS

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Flaky validation suite due to numerical tolerance | Medium | High | Lock solver tolerances; rerun on failure with increased iterations |
| Docker build cache corruption | Low | Medium | Use `--no-cache` on scheduled builds; cache-from for PR builds |
| Secret leakage in logs | Low | Critical | Mask all secrets; never print token values; use GitHub masked secrets |
| Nightly job resource exhaustion | Medium | Medium | Concurrency groups; sensible timeouts; artifact cleanup policies |
| Third-party dependency outage (PyPI, npm, Docker Hub) | Low | High | Retry logic; fallback mirrors where configured |
| ETAP COM bridge unavailable in CI | High | Low | Gate ETAP-specific tests behind `ETAP_ENABLED` flag; skip in CI |
| Visual regression false positives | Medium | Low | Baseline update workflow with manual approval |

## ENTRY_EXIT_CRITERIA

### Entry criteria

- Repository source is accessible to the CI runner
- All required secrets and environment variables are configured
- Docker daemon is available for build and security stages
- Python 3.13, Node.js 22, and pnpm are installed
- No active deployment freeze blocking pipeline execution

### Exit criteria

- All automated gates report success or documented accepted risks
- Test artifacts are uploaded and retained per schedule
- Security scan shows no new CRITICAL findings; new HIGH findings have open tracking tickets
- Performance baselines are updated within tolerance bands
- Regression report is published to the repository artifacts and Slack/email channel (if configured)

## DEFECT_MANAGEMENT

### Severity levels

- **P0 - Critical**: Security breach, data loss, platform downtime, incorrect engineering result with safety impact
- **P1 - High**: Broken CI/CD gate, failed validation suite, blocked release, missing artifact
- **P2 - Medium**: Flaky test, lint failure, type error, slow build exceeding baseline by >20%
- **P3 - Low**: Documentation drift, cosmetic UI issue, minor performance regression

### Workflow

1. Defect detected by automated gate or human review
2. Auto-label applied by workflow based on failure type
3. Issue created with standardized template (severity, gate, reproduction, logs)
4. P0/P1 defects block merging until resolved or risk-accepted by on-call engineer
5. P2/P3 defects tracked in sprint backlog
6. Fix validated by re-running affected gate and updating baseline if needed

## REPORTING

### Automated reports

- **Test summary**: pytest JUnit XML and console summary uploaded as artifacts
- **Validation suite report**: captured stdout from `validation_suite.py` uploaded as text artifact
- **Security scan report**: Trivy SARIF uploaded to GitHub Security tab; summary in workflow summary
- **Docker build report**: buildx provenance and target digest logged as artifact
- **Nightly regression report**: aggregated artifact with pass/fail counts, timing deltas, and baseline comparison

### Dashboards

- GitHub Actions workflow run history
- GitHub Security / Code Scanning dashboard for SARIF findings
- Prometheus metrics exposed from platform containers (study success rate, solve time, API latency)
- Grafana dashboards for operational visibility (referenced in deployment architecture)

### Communication

- PR checks block merge on failure
- Nightly regression summary posted to repository Discussions or designated Slack channel
- Security HIGH/CRITICAL findings trigger immediate notification to security on-call
