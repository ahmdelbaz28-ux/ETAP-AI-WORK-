# CI/CD Security Governance & Workflow Policies

This document establishes repository-level security requirements and invariant rules governing all GitHub Actions workflows in the AhmedETAP project.

---

## 1. Repository-Level Workflow Permissions
- **Default Policy**: All workflows execute under **Read-Only** permissions by default:
  ```yaml
  permissions:
    contents: read
  ```
- **Job-Level Least Privilege**: Any job requiring elevated permissions must explicitly declare only the minimal required scope (e.g. `security-events: write` for SARIF uploads, `statuses: write` for authoritative gate status, `packages: write` for container registries).
- **Automated Enforcement**: Enforced continuously via `scripts/check_workflows_meta.py` across all 50 workflow files. Any job lacking an explicit permissions block fails the `Meta CI` build gate.

---

## 2. Fail-Closed Quality Gate Rules
1. **No Silent Failure**: No gate, check, scan, or audit step may swallow errors via `|| true`, `|| echo`, or `continue-on-error` (except non-blocking auxiliary SARIF uploads).
2. **State Machine + Post-Loop Assertions**: Any retry or polling loop for health checks or external services must use a state-tracking variable (e.g., `HEALTHY=0`) and a mandatory exit assertion:
   ```bash
   if [ "$HEALTHY" -ne 1 ]; then
     echo "::error::Health check failed after maximum attempts"
     exit 1
   fi
   ```
3. **Forensic Identity Verification**: Post-deployment smoke tests must assert that the deployed `/version` endpoint returns the exact target commit SHA (`WANT_SHA`), with `exit 1` on any mismatch.
4. **Single Source of Truth**: Package overrides and tool versions must have a single authoritative definition (`pnpm.overrides` under pnpm 9).

---

## 3. Secret & Credential Scanning
- **Authoritative Scanner**: `Gitleaks` (`.github/workflows/secret-scan.yml`) scans the complete repository on all pull requests and pushes to `main`.
- **Pre-Push Gate**: `scripts/verify_secure_push.py` validates that all security, lockfile, and branch invariants pass before allowing any branch push.
- **Credential Rotation**: Managed per `docs/security/rotation-log.md`.
