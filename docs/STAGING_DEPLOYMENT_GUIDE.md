---
title: "AhmedETAP Isolated Staging Environment Architecture & Deployment Guide"
version: "2.3.0"
last_updated: "2026-10-20"
maintainer: "Eng. Ahmed Elbaz / Platform Core Team"
---

# 🛡️ AhmedETAP Isolated Staging Environment Architecture & Deployment Guide

## 📋 Table of Contents

- [1. Executive Summary & Purpose](#1-executive-summary--purpose)
- [2. Component Separation Matrix](#2-component-separation-matrix)
- [3. Staging Infrastructure Components Status](#3-staging-infrastructure-components-status)
  - [3.1 Frontend (Vercel)](#31-frontend-vercel)
  - [3.2 Dedicated Staging PostgreSQL Database (Supabase)](#32-dedicated-staging-postgresql-database-supabase)
  - [3.3 GitHub Actions CI/CD](#33-github-actions-cicd)
  - [3.4 Backend Runtime & Ingress (Ephemeral vs. Persistent Hosting)](#34-backend-runtime--ingress-ephemeral-vs-persistent-hosting)
- [4. Engineering Capability Verification & Feature Flag Isolation](#4-engineering-capability-verification--feature-flag-isolation)
- [5. Operational Safety & Rollback Procedures](#5-operational-safety--rollback-procedures)
- [6. Owner Decision Points & Persistent Hosting Options](#6-owner-decision-points--persistent-hosting-options)

---

## 1. Executive Summary & Purpose

In alignment with the **AhmedETAP Zero-Fabrication Rule (R3)** and the **Owner Safety Remediation Mandate**, this document defines the verified Staging deployment architecture for AhmedETAP (`ahmdelbaz28-ux/ETAP-AI-WORK-`).

The Staging environment provides an isolated, sandboxed platform allowing engineers to test and verify new capabilities (such as `harmonic_analysis`, `cable_sizing`, `motor_starting`, `transient_stability`, `optimal_power_flow`, `earth_grid`, `renewable_integration`, and `battery_storage`) without cross-contamination with live production customers or physical electrical systems.

**Non-Negotiable Safety Invariants:**
1. Staging **MUST NOT** share database tables, schemas, or credentials with Production (`kuqwgxzkscqqftcrcuqe`).
2. Staging **MUST NOT** use SQLite or ephemeral storage (`ALLOW_SQLITE_IN_PROD` is strictly banned in Staging).
3. Staging workflows **MUST NOT** have automatic push triggers and **MUST NOT** fall back to production repository secrets.
4. Production feature flag defaults in `api/feature_flags.py` **MUST REMAIN** fail-closed (`enabled: False, rollout_percentage: 0`).
5. Quick Tunnels (`trycloudflare.com`) are recognized as temporary, ephemeral smoke-test utilities and are **NOT** persistent production-grade hosting.

---

## 2. Component Separation Matrix

| Component | Production Instance | Staging Target | Proof of Strict Isolation | Status |
|:---|:---|:---|:---|:---|
| **Frontend / UI** | `etap-ai-work` (`prj_WucHqc3lQDwYe0i3ykgWz7UR5E3I`) | `etap-ai-work-staging` (`prj_XHvIpATc0SF11QBeCNPatRe5t8Af`) | Separate Vercel Project ID, distinct build environment, `VITE_API_URL` bound exclusively to Staging Backend | **OPERATIONAL (HTTP 200)** |
| **Database** | Supabase PostgreSQL (`kuqwgxzkscqqftcrcuqe`) | Dedicated Supabase Project `guunodspzhcxpmdwwyjv` | Distinct project ref, isolated credentials, enforced by `api/staging_guard.py`; SQLite strictly banned | **OPERATIONAL (PostgreSQL 17)** |
| **Backend API** | `https://ahmdelbaz28-ahmedetap-platform.hf.space` | Isolated Staging Service | Independent container process, dedicated ports and credentials | **SMOKE-TESTED (Temporary Tunnel)** |
| **Authentication** | Production `JWT_SECRET_KEY` & `ENGINEERING_SERVICE_API_KEY` | Dedicated Staging signing keys (`STAGING_JWT_SECRET_KEY`, `STAGING_ENGINEERING_SERVICE_API_KEY`) | Tokens issued in Staging cannot authenticate against Production | **CONFIGURED** |
| **Feature Flags** | Code defaults (`DEFAULT_FEATURE_FLAGS`) | In-memory / untracked local `.feature-flags.json` | Flags activated in Staging do not modify code defaults; production remains fail-closed | **ISOLATED** |
| **Grid / SCADA** | Fail-closed production interlocks | Synthetic fixtures & mock adapters only | Zero live Modbus/OPC-UA/IEC 61850 network packets to physical devices | **VERIFIED** |

---

## 3. Staging Infrastructure Components Status

### 3.1 Frontend (Vercel)
- **Project Name:** `etap-ai-work-staging`
- **Project ID:** `prj_XHvIpATc0SF11QBeCNPatRe5t8Af` (Created & Verified via Vercel API; completely separated from production `prj_WucHqc3lQDwYe0i3ykgWz7UR5E3I`).
- **Framework:** `vite`
- **Build Command:** `bash vercel-build.sh`
- **Output Directory:** `ui/dist`
- **Live URL:** `https://etap-ai-work-staging.vercel.app` (Verified HTTP 200).
- **Anti-Production Guard:** `ui/src/lib/api-base-url.ts` contains explicit guards preventing fallback to production Hugging Face Spaces on Staging hosts.

### 3.2 Dedicated Staging PostgreSQL Database (Supabase)
- **Project Name:** `AhmedETAP-Platform-Staging`
- **Project Ref:** `guunodspzhcxpmdwwyjv` (Dedicated, separate project in organization `AHMED ETAP`).
- **Host / Pooler:** `aws-1-eu-central-1.pooler.supabase.com:5432` (Frankfurt / `eu-central-1`).
- **Engine:** PostgreSQL 17.11 (Active & Healthy).
- **Isolation Verification:** Enforced by `api/staging_guard.py` (which validates project ref `guunodspzhcxpmdwwyjv` and rejects `kuqwgxzkscqqftcrcuqe`). Tested with 15/15 unit tests in `tests/test_staging_db_guards.py`.
- **Schema Status:** All 21 ORM tables verified; Alembic stamped at head revision `016_snapshot_components`.
- **SQLite Ban:** Enforced fail-closed via `api/config_prod.py` (`ALLOW_SQLITE_IN_PROD` forbidden in Staging).

### 3.3 GitHub Actions CI/CD
- **Workflow File:** `.github/workflows/cd-staging.yml`
- **Trigger:** Strict manual `workflow_dispatch` only (with required 40-character `ref_sha`). Automated `push` triggers are completely disabled.
- **Environment Target:** `staging`
- **Fail-Closed Safety Guards:**
  - Validates commit SHA length and repository name.
  - Verifies target `VERCEL_PROJECT_ID` is `prj_XHvIpATc0SF11QBeCNPatRe5t8Af`.
  - Executes `python3 -m api.staging_guard` against `STAGING_DATABASE_URL` prior to build.
  - Performs comprehensive health and smoke checks on backend endpoints (`/healthz`, `/readyz`, `/version`, `/api/v1/studies/run`, `/api/v1/chat/stream`).

### 3.4 Backend Runtime & Ingress (Ephemeral vs. Persistent Hosting)
- **Current Runtime Status:** The isolated Staging backend runs `hf-space/app.py` bound to dedicated Staging Supabase PostgreSQL 17.
- **Ingress Mechanism (Temporary):** Cloudflare Quick Tunnels (`trycloudflare.com`) provide temporary ingress for automated validation and smoke testing.
- **Limitation:** Quick tunnels expire after 12-24 hours or when the tunnel process stops. They do not constitute permanent cloud hosting.
- **Status Gate:** **PERSISTENT BACKEND HOSTING IS BLOCKED** pending Owner infrastructure selection (see Section 6).

---

## 4. Engineering Capability Verification & Feature Flag Isolation

All eight candidate engineering capabilities have been verified with deterministic solvers and independent IEEE/IEC standard benchmarks:

| Capability | Standard | Acceptance & Simulation Tests | Benchmark Status | Staging Runtime Flag |
|:---|:---|:---|:---|:---|
| `harmonic_analysis` | IEEE 519-2022 | 6/6 passed (`test_harmonic_analysis_acceptance.py`) | Verified (3 IEEE 519 benchmarks) | `enabled: true` |
| `cable_sizing` | IEC 60364-5-52 | 7/7 passed (`test_cable_sizing_acceptance.py`) | Verified (4 Prysmian/IEC benchmarks) | `enabled: true` |
| `motor_starting` | IEEE 399-1997 | 12/12 passed (acceptance + dynamic simulation) | Verified (DOL, Star-Delta, Soft-Starter) | `enabled: true` |
| `transient_stability` | IEEE 399 | 7/7 passed (`test_transient_stability_acceptance.py`) | Verified (SMIB & Multi-machine RK4) | `enabled: true` |
| `optimal_power_flow` | IEEE 3002 | 9/9 passed (`test_opf_correctness.py`, `test_pso_opf.py`) | Verified (DC-OPF PTDF & AC-OPF PSO) | `enabled: true` |
| `earth_grid` | IEEE 80-2013 | 7/7 passed (`test_earth_grid_acceptance.py`) | Verified (Sverak/Schwarz potentials) | `enabled: true` |
| `renewable_integration` | IEEE 1547-2018 | 7/7 passed (`test_renewable_integration_acceptance.py`) | Verified (PVWatts & Hosting Capacity) | `enabled: true` |
| `battery_storage` | IEC 62933 | 7/7 passed (`test_battery_storage_acceptance.py`) | Verified (4 IEC 62933 benchmarks) | `enabled: true` |

**Total Capability Test Suite:** 62 passed tests in `pytest`.
**Production Isolation:** In `api/feature_flags.py`, `DEFAULT_FEATURE_FLAGS` sets all 8 capabilities to `enabled: False, rollout_percentage: 0`. Flags are toggled exclusively in Staging runtime without modifying repository defaults.

---

## 5. Operational Safety & Rollback Procedures

1. **Staging Rollback Trigger:**
   If a Staging deployment experiences health probe failures, numerical errors, or unexpected crashes:
   - Trigger `.github/workflows/cd-staging.yml` via `workflow_dispatch` with the previous known green commit SHA.
   - Or roll back to the previous deployment via the Vercel dashboard for `etap-ai-work-staging`.
2. **Feature Flag Isolation:**
   - All 8 candidate capabilities remain strictly `enabled: False` in repository defaults.
   - Staging flag activation is isolated from production.
3. **No Cross-Contamination:**
   - Under no circumstances will staging credentials, tokens, or endpoints be merged into `main` or deployed to `production`.

---

## 6. Owner Decision Points & Persistent Hosting Options

To transition persistent Staging backend hosting from `BLOCKED` to `OPERATIONAL`, the owner must select one of the following permanent hosting architectures:

### Option 1: Persistent Container Service (Render.com / Koyeb)
- Deploys Docker container (`Dockerfile`) directly from GitHub branch `infra/staging-environment-bootstrap`.
- Configures static environment variables (`DATABASE_URL`, `JWT_SECRET_KEY`, `DEPLOY_SHA`).
- Provides a stable, permanent HTTPS domain (e.g., `https://etap-staging-api.onrender.com`).

### Option 2: Named Cloudflare Zero Trust Tunnel (Permanent Self-Hosted)
- Installs `cloudflared` service with a persistent tunnel token (`CLOUDFLARE_TUNNEL_TOKEN`).
- Routes a custom subdomain (e.g., `https://staging-api.ahmedetap.org`) directly to the backend container.
- Zero open inbound ports, completely free, but requires continuous workstation/server availability.

### Option 3: Dedicated Hugging Face Docker Space (Paid Pro)
- Upgrades `ahmdelbaz28/AhmedETAP-Platform-Staging` to a persistent Docker Space.
- Requires owner approval of Hugging Face subscription billing.
