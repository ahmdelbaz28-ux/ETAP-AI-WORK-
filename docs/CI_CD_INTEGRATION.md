# CI/CD Integration — Quality Gates

This document explains the four quality gates enforced in the AhmedETAP pipeline and how they map to GitHub Actions workflows and jobs.

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

<<<<<<< HEAD
## Repository Configuration (Required Settings)

These GitHub repository settings MUST be configured before the CI/CD pipeline runs correctly. They are NOT code-level settings — they are configured in the GitHub repo settings UI or via the GitHub API.

### 1. Dependency Graph (`DEPENDENCY_GRAPH_ENABLED=true`)

**Why**: GitHub's dependency graph enables Dependabot alerts, dependency review in PRs, and the Supply Chain security features. Without it, the `dependency-review` job in security.yml cannot detect vulnerable dependency changes in PRs.

**How to enable**:
1. Go to **Repo Settings → Code security and analysis**
2. Set **Dependency graph** to **Enabled**
3. Set **Dependabot alerts** to **Enabled**
4. Set **Dependabot security updates** to **Enabled**
5. Set **Dependabot version updates** to **Enabled** (optional, but recommended)

**Via GitHub API** (requires `gh` CLI with admin access):
```bash
gh api --method PATCH /repos/{owner}/{repo}/code-security-configuration \
  --field dependency_graphs_enabled=true \
  --field dependabot_alerts_enabled=true \
  --field dependabot_security_updates_enabled=true
```

**Verification**: Check that the dependency review action works on a PR that changes requirements.txt or package-lock.json.

### 2. GitHub Repository Variables

These are set in **Repo Settings → Variables** (NOT secrets — they are non-sensitive configuration IDs):

| Variable | Description | Example |
|---|---|---|
| `AZURE_SUBSCRIPTION_ID` | Azure subscription for Terraform | `xxxxxxxx-xxxx-xxxx-xxxx` |
| `AZURE_TENANT_ID` | Azure AD tenant for OIDC auth | `xxxxxxxx-xxxx-xxxx-xxxx` |
| `AZURE_CLIENT_ID` | Azure AD app client ID for OIDC | `xxxxxxxx-xxxx-xxxx-xxxx` |

### 3. GitHub Repository Secrets

Set in **Repo Settings → Secrets and variables → Actions → New secret**:

| Secret | Used by | Description |
|---|---|---|
| `SONAR_TOKEN` | ci-cd.yml → sonarcloud | SonarCloud analysis token |
| `GITHUB_TOKEN` | All workflows | Auto-provided by GitHub (no manual setup needed) |
| `VERCEL_TOKEN` | ci-cd.yml → deploy-vercel | Vercel deployment token |
| `VERCEL_ORG_ID` | ci-cd.yml → deploy-vercel | Vercel org ID |
| `VERCEL_PROJECT_ID` | ci-cd.yml → deploy-vercel | Vercel project ID |
| `HF_TOKEN` | ci-cd.yml → deploy-hf | HuggingFace Space deploy token |
| `LANGWATCH_API_KEY` | ci-cd.yml → python-tests | LangWatch LLM observability |
| `SMITHERY_API_KEY` | ci-cd.yml → python-tests | Smithery MCP API key |

### 4. GitHub Environment Protection Rules

Configure in **Repo Settings → Environments**:

| Environment | Required reviewers | Deployment branch | Wait timer |
|---|---|---|---|
| `dev` | None (auto-approve) | `main` | 0 min |
| `staging` | 1 reviewer (team lead) | `main` | 2 min |
| `production` | 2 reviewers | `main` | 5 min |

---

=======
>>>>>>> origin/fix/scenario-tests-properly
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
