# CI Gate Exceptions & Allowlist Registry

**Version:** 1.0.0  
**Effective Date:** 2026-10-07  
**Enforcement:** `.github/workflows/anti-greenwash.yml`  
**Owner:** Platform Core Team / Eng. Ahmed Elbaz  

---

## 1. Objective & Security Policy

AhmedETAP enforces a strict **Zero-Greenwashing / Fail-Closed** policy across all CI/CD workflows and deployment gates.
Silent error swallowing via `continue-on-error: true`, `|| true`, `|| exit 0`, or `--admin` bypass flags is strictly forbidden in:
- Production Deployment workflows (`cd.yml`, `deploy-*.yml`)
- Release gates (`release-gate.yml`)
- Security & Secret scanners (`secret-scan.yml`, `security.yml`, `security-audit.yml`)
- Core testing & compliance verification pipelines (`integration-tests.yml`, `no-mock-in-prod.yml`, `test.yml`)

Any legitimate, non-greenwashing exception (such as cleanup of test background processes or non-fatal diagnostic log fetching) must be explicitly registered and documented in this registry.

---

## 2. Approved CI Exception Registry

| ID | Workflow File | Pattern / Target | Rationale & Non-Greenwash Proof | Owner | Review Date |
|---|---|---|---|---|---|
| `EXC-001` | `.github/workflows/integration-tests.yml` | `pkill -f "engineering_service.py" 2>/dev/null \|\| true` | Post-test teardown cleanup of background mock servers. Failure to kill already terminated processes is non-fatal to test outcome. | Core Infra | 2027-01-01 |
| `EXC-002` | `.github/workflows/load-test.yml` | `pkill -f "engineering_service.py" 2>/dev/null \|\| true` | Teardown cleanup of local benchmarking daemon after load suite completion. | Performance Team | 2027-01-01 |
| `EXC-003` | `.github/workflows/security.yml` | `sudo rm -rf ... 2>/dev/null \|\| true` | Runner disk-space pre-clean in ephemeral container runner. Non-fatal if directories do not exist. | CI Team | 2027-01-01 |
| `EXC-004` | `.github/workflows/docker-validation.yml` | `docker rmi ... 2>/dev/null \|\| true` | Post-build cleanup of intermediate test container images on self-hosted runners. | DevOps | 2027-01-01 |
| `EXC-005` | `.github/workflows/etap-infra-integration.yml` | `kubectl -n etap logs ... \|\| true` | Diagnostic post-failure log dump gathering for GitHub Action summary. Actual gate assertions follow separately. | Kubernetes Team | 2027-01-01 |
| `EXC-006` | `.github/workflows/no-mock-in-prod.yml` | `grep ... 2>/dev/null \|\| true` | Subshell grep match collector. Captures outputs to `$matches` variable; downstream assertion fails closed if `$matches` is non-empty. | Security Team | 2027-01-01 |
| `EXC-007` | `.github/workflows/npm-audit.yml` | `grep -vE ... \|\| true` | Pipe exception parser for GHSA allowlist extraction. Handled downstream by Node validator. | AppSec Team | 2027-01-01 |

---

## 3. Prohibited Patterns (Hard Fail)

The Meta-Guard scanner automatically rejects any PR introducing:
1. `continue-on-error: true` in gate, test, security, or deploy steps.
2. `|| true` or `|| exit 0` on test commands, curl health probes, lint checks, or build commands.
3. `--admin` flags in GitHub CLI or auto-merge scripts to bypass branch protection rules.
4. `[skip ci]` in release or deployment trigger events.
