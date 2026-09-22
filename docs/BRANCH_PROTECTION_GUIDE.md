# AhmedETAP — Production Branch Protection & Environment Governance Guide

This guide provides authoritative instructions for repository administrators to configure GitHub Branch Protection rules and consolidate deployment environments.

---

## 1. Branch Protection Configuration (`main`)

Navigate to:
**Repository Settings** → **Branches** → **Branch protection rules** → **Add rule** (or edit rule for `main`).

### Branch name pattern:
`main`

### 1.1 Protect matching branches
* [x] **Require a pull request before merging**
  - Required approvals: **1**
  - [x] **Dismiss stale pull request approvals when new commits are pushed**
  - [x] **Require review from Code Owners**

### 1.2 Authoritative Quality & Security Gates
* [x] **Require status checks to pass before merging**
  - [x] **Require branches to be up to date before merging**
  - **Mandatory Status Checks to select:**
    1. `Authoritative Release Gate` (from `.github/workflows/release-gate.yml`)
    2. `CI Success` (from `.github/workflows/ci.yml`)
    3. `Authoritative TypeScript Quality Gate` (from `.github/workflows/ui-quality.yml`)
    4. `Docker Validation Summary` (from `.github/workflows/docker-validation.yml`)
    5. `Trivy Security Scan` (from `.github/workflows/security.yml`)

### 1.3 Governance & Linear History
* [x] **Do not allow bypassing the above settings** (`enforce_admins: true`)
  - Ensures administrative accounts cannot accidentally push directly or bypass gates.
* [x] **Require linear history**
  - Enforces squash merges or rebase merges to maintain a clean git log.
* [x] **Require conversation resolution before merging**

---

## 2. Production Environment Consolidation

GitHub API reveals multiple fragmented deployment environments:
- `copilot`
- `dev`
- `Preview`
- `prod`
- `Production`
- `production-hf`
- `production-vercel`
- `staging`

### Action Required:
1. Navigate to: **Settings** → **Environments**.
2. Retain only:
   - `production` (Canonical unified production environment used by `cd.yml`)
   - `github-pages` (Documentation build)
3. Delete or archive legacy environments (`copilot`, `dev`, `Preview`, `prod`, `Production`, `production-hf`, `production-vercel`, `staging`).
4. On `production`:
   - Under **Deployment branches**, configure **Selected branches** -> `main` only.
   - Configure **Environment secrets**: `HF_TOKEN`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `SLACK_WEBHOOK_URL`.
