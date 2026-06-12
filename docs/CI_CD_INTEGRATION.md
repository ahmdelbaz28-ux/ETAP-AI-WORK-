# CI/CD Integration — Quality Gates

This document explains the four quality gates enforced in the ETAP AI Engineering Platform pipeline and how they map to GitHub Actions workflows and jobs.

## Gate overview

| Gate | Purpose | Trigger |
|---|---|---|
| **PRE_COMMIT** | Fast feedback on code quality and correctness | Push, pull_request |
| **PRE_BUILD** | Verify integration behavior and build artifacts | Push to main, pull_request |
| **POST_BUILD** | Validate deployable artifacts and scan for vulnerabilities | workflow_run (success) |
| **SCHEDULED** | Nightly full regression and performance baselining | Schedule + workflow_dispatch |

---

## PRE_COMMIT

**Goal**: Catch defects before they reach the build stage.

**Jobs**:
- Lint (Python and TypeScript)
- Unit tests (pytest)
- Syntax validation (AST parsing, import checks)
- Validation suite (IEEE/IEC reference cases)
- Type checking (TypeScript compiler)

**Tools**:
- `python3 validate_syntax.py`
- `python3 validation_suite.py`
- `pytest -q`
- `pnpm lint` (tsc --noEmit)
- `pnpm test` (vitest run)

**Secrets/Vars**: None required.

**Artifacts**:
- pytest JUnit report
- validation suite stdout
- lint logs

---

## PRE_BUILD

**Goal**: Verify that the application integrates correctly and builds successfully.

**Jobs**:
- Integration tests (cross-component workflows, ETAP bridge, GIS enrichment)
- Docker build verification (multi-stage targets)
- docker-compose configuration validation

**Tools**:
- `docker compose config`
- `docker build --target python-builder .`
- `docker build --target ts-builder .`
- `docker build -f Dockerfile.engineering-service .`

**Secrets/Vars**: None required.

**Artifacts**:
- Docker build logs
- docker-compose config dump
- Image provenance digests

---

## POST_BUILD

**Goal**: Validate the built artifact end-to-end and scan for security issues.

**Jobs**:
- E2E smoke tests (CLI invocation, file presence, subprocess checks)
- Security scan (Trivy filesystem scan for CRITICAL and HIGH)
- Visual regression readiness (UI build and baseline generation)

**Tools**:
- `pytest -q tests/e2e_smoke_test.py`
- `python3 validation_suite.py`
- `trivy filesystem --exit-code 1 --severity CRITICAL,HIGH .`

**Secrets/Vars**:
- `TRIVY_TOKEN` (optional, for Trivy Enterprise)
- `GITHUB_TOKEN` (auto-provided)

**Artifacts**:
- Trivy SARIF report (uploaded to GitHub Security tab)
- Smoke test results
- Validation suite report
- UI build output

---

## SCHEDULED

**Goal**: Nightly full regression and performance baseline maintenance.

**Jobs**:
- Full validation suite run
- Complete pytest matrix
- docker-compose configuration validation
- Docker build verification
- Performance baseline capture
- Regression report generation

**Tools**:
- Same as PRE_COMMIT plus PRE_BUILD stages

**Secrets/Vars**:
- Same as above; no additional secrets required

**Artifacts**:
- Full test report (JUnit + console)
- Validation suite report
- Docker build logs
- Performance baseline JSON
- Regression delta report

---

## Secrets and variables reference

| Name | Required | Scope | Purpose |
|---|---|---|---|
| `GITHUB_TOKEN` | Auto | All jobs | API access, artifact upload, SARIF upload |
| `TRIVY_TOKEN` | Optional | POST_BUILD | Trivy Enterprise / database access |
| `SNYK_TOKEN` | Optional | POST_BUILD | Snyk vulnerability scanning |
| `SLACK_WEBHOOK_URL` | Optional | SCHEDULED | Nightly regression notifications |
| `ETAP_ENABLED` | Optional | PRE_BUILD | Enable ETAP COM automation tests (CI default: false) |
| `ENGINEERING_SERVICE_API_KEY` | Optional | POST_BUILD | Engineering service smoke auth |

**Note**: Never print or log secret values. All secrets must be configured as GitHub Actions masked secrets.

---

## Artifact retention

| Artifact | Retention | Uploaded by |
|---|---|---|
| pytest JUnit XML | 30 days | PRE_COMMIT, SCHEDULED |
| Validation suite stdout | 30 days | PRE_COMMIT, SCHEDULED |
| Trivy SARIF | 90 days | POST_BUILD |
| docker-compose config | 30 days | PRE_BUILD, SCHEDULED |
| Performance baseline | 90 days | SCHEDULED |
| Regression report | 90 days | SCHEDULED |

---

## Concurrency and cancellation

- `concurrency` groups prevent overlapping runs on the same branch or workflow.
- `cancel-in-progress: true` ensures newer commits supersede stale runs.
- Scheduled jobs use a dedicated concurrency group to avoid colliding with PR-triggered runs.

---

## Status badges

```markdown
[![Quality Gates](https://github.com/<owner>/<repo>/actions/workflows/quality-gates.yml/badge.svg)](https://github.com/<owner>/<repo>/actions/workflows/quality-gates.yml)
[![Security](https://github.com/<owner>/<repo>/actions/workflows/quality-gates.yml/badge.svg?event=schedule)](https://github.com/<owner>/<repo>/actions/workflows/quality-gates.yml)
```
