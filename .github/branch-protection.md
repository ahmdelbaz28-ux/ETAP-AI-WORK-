# Branch Protection & Production Quality Gates

This document defines the authoritative branch protection policies and required status checks for the AhmedETAP platform. These settings must be configured in GitHub Repository Settings (`Settings` → `Branches` → `Branch protection rules` for `main`).

---

## 1. Authoritative Branch Protection Rules for `main`

### A. Pull Request Reviews
- **Require a pull request before merging:** Enabled
- **Required approvals:** `1` minimum
- **Dismiss stale pull request approvals when new commits are pushed:** Enabled
- **Require review from Code Owners:** Enabled (governed by `.github/CODEOWNERS`)
- **Require conversation resolution before merging:** Enabled

### B. Required Status Checks (Fail-Closed)
- **Require status checks to pass before merging:** Enabled
- **Require branches to be up to date before merging:** Enabled (`strict: true`)
- **Canonical Required Check:**
  - **`Authoritative Release Gate`** (Job: `authoritative-gate` in [`.github/workflows/release-gate.yml`](./workflows/release-gate.yml))

#### Underlying Gate Coverage Enforced by Release Gate:
The `Authoritative Release Gate` runs with `cancel-in-progress: false` and polls GitHub Check Runs to verify all canonical gates have completed with `success`:
1. `CI Success` (aggregates linting, typechecking, pytest unit & scenario suites, UI build, bundle size)
2. `gitleaks` (authoritative pre-commit & CI credential leak detection with SARIF reporting)
3. `npm audit (high)` (root & UI zero high/critical vulnerability enforcement)
4. `Trivy Security Scan` (container vulnerability scanning with SARIF reporting)
5. `Docker Validation Summary` (container build verification)
6. `UI Quality Summary` (Playwright E2E tests, Vite production build, strict bundle limits)

### C. Branch Rules & Deletion Protection
- **Allow force pushes:** **Disabled** (Strictly forbidden for all users including administrators)
- **Allow deletions:** **Disabled** (Branch cannot be deleted)
- **Include administrators:** Enabled (Enforces status checks and gate compliance even for repo admins)

### D. Automated Merging (Dependabot)
- Auto-merge is strictly restricted to squash merges via `gh pr merge --auto --squash`.
- Bypassing checks via `gh pr merge --admin` is strictly prohibited and removed.
- Dependabot PRs must satisfy the full check suite with zero skipped or failed required checks before merge execution.

---

## 2. CODEOWNERS Specification

Located in [`.github/CODEOWNERS`](./CODEOWNERS):
```text
*                       @ahmdelbaz28-ux
.github/workflows/      @ahmdelbaz28-ux
src/mastra/             @ahmdelbaz28-ux
agents/                 @ahmdelbaz28-ux
hf-space/               @ahmdelbaz28-ux
```
