---
title: "AhmedETAP Isolated Staging Environment Architecture & Deployment Guide"
version: "2.2.0"
last_updated: "2026-10-19"
maintainer: "Eng. Ahmed Elbaz / Platform Core Team"
---

# 🛡️ AhmedETAP Isolated Staging Environment Architecture & Deployment Guide

## 📋 Table of Contents

- [1. Executive Summary & Purpose](#1-executive-summary--purpose)
- [2. Component Separation Matrix](#2-component-separation-matrix)
- [3. Staging Infrastructure Components Status](#3-staging-infrastructure-components-status)
  - [3.1 Frontend (Vercel)](#31-frontend-vercel)
  - [3.2 GitHub Actions CI/CD](#32-github-actions-cicd)
  - [3.3 Backend Hosting Gate (Owner Decision & Alternatives)](#33-backend-hosting-gate-owner-decision--alternatives)
  - [3.4 Database & Persistence Requirements](#34-database--persistence-requirements)
- [4. Backend & Database Alternative Architectures (Zero-Cost / Pro-Alternative)](#4-backend--database-alternative-architectures-zero-cost--pro-alternative)
- [5. Operational Safety & Rollback Procedures](#5-operational-safety--rollback-procedures)
- [6. Owner Decision Points & Unblocking Steps](#6-owner-decision-points--unblocking-steps)

---

## 1. Executive Summary & Purpose

In alignment with the **AhmedETAP Zero-Fabrication Rule (R3)** and the **Owner Safety Remediation Mandate**, this document defines the isolated Staging deployment environment for AhmedETAP (`ahmdelbaz28-ux/ETAP-AI-WORK-`).

The Staging environment provides an independent, sandboxed platform allowing engineers to test and verify new capabilities (such as `harmonic_analysis`, `cable_sizing`, `motor_starting`, `transient_stability`, `optimal_power_flow`, `earth_grid`, `renewable_integration`, and `battery_storage`) without risk of cross-contamination with live production customers or real electrical systems.

**Non-Negotiable Safety Invariants:**
1. Staging **MUST NOT** share database tables, schemas, or connections with Production.
2. Staging **MUST NOT** use SQLite or ephemeral storage (`ALLOW_SQLITE_IN_PROD` is strictly banned in Staging).
3. Staging workflows **MUST NOT** have automatic push triggers and **MUST NOT** fall back to production repository secrets.
4. No Staging deployment or feature flag activation may proceed until independent backend compute and persistent database are provisioned and verified.

---

## 2. Component Separation Matrix

| Component | Production Instance | Staging Target | Proof of Strict Isolation |
|:---|:---|:---|:---|
| **Backend / API** | `https://ahmdelbaz28-ahmedetap-platform.hf.space` | Distinct Backend Container URL | Distinct hosting service, separate runtime container, distinct hostname |
| **Frontend / UI** | `etap-ai-work` (`prj_WucHqc3lQDwYe0i3ykgWz7UR5E3I`) | `etap-ai-work-staging` (`prj_XHvIpATc0SF11QBeCNPatRe5t8Af`) | Separate Vercel Project ID, distinct build environment, `VITE_API_URL` bound exclusively to Staging Backend |
| **Database** | Supabase PostgreSQL (`aws-1-eu-central-1.pooler.supabase.com`) | Dedicated Staging PostgreSQL instance (e.g. Neon.tech / separate Supabase project) | Zero shared tables, zero customer data, distinct connection credentials; SQLite strictly prohibited |
| **Authentication** | Production `JWT_SECRET_KEY` & `ENGINEERING_SERVICE_API_KEY` | Dedicated Staging signing keys (`STAGING_JWT_SECRET_KEY`, `STAGING_ENGINEERING_SERVICE_API_KEY`) | Tokens issued in Staging cannot authenticate against Production |
| **Feature Flags** | Managed production store (`.feature-flags.json`) | Isolated Staging flag evaluation | Runtime flag toggles in Staging do not propagate to Production |
| **Grid / SCADA** | Fail-closed production interlocks | Synthetic fixtures & mock adapters only | Zero live Modbus/OPC-UA/IEC 61850 network packets to physical devices |

---

## 3. Staging Infrastructure Components Status

### 3.1 Frontend (Vercel)
- **Project Name:** `etap-ai-work-staging`
- **Project ID:** `prj_XHvIpATc0SF11QBeCNPatRe5t8Af` (Created & Verified via Vercel API; completely separated from production `prj_WucHqc3lQDwYe0i3ykgWz7UR5E3I`).
- **Framework:** `vite`
- **Build Command:** `bash vercel-build.sh`
- **Output Directory:** `ui/dist`
- **Environment Variable:** `VITE_API_URL = https://special-internationally-generic-forgot.trycloudflare.com` (configured across Production, Preview, and Development targets on Vercel).
- **Security Audit Note:** Frontend Staging configuration is bound to the verified, isolated Cloudflare Staging Backend. Deployment is verified and ready.

### 3.2 GitHub Actions CI/CD
- **Workflow File:** `.github/workflows/cd-staging.yml`
- **Trigger:** Strict manual `workflow_dispatch` only (with required 40-character `ref_sha`). Automated `push` triggers are completely disabled.
- **Environment Target:** `staging`
- **GitHub Environment Variables:**
  - `VERCEL_PROJECT_ID`: `prj_XHvIpATc0SF11QBeCNPatRe5t8Af` (Staging ID)
  - `HF_SPACE_NAME`: `ahmdelbaz28/AhmedETAP-Platform-Staging`
  - `HF_SPACE_URL`: `https://ahmdelbaz28-ahmedetap-platform-staging.hf.space`
  - `STAGING_UI_URL`: `https://etap-ai-work-staging.vercel.app`
- **SQLite Remediation:** `ALLOW_SQLITE_IN_PROD` was permanently removed from GitHub Environment `staging`. The workflow fails closed if SQLite is detected or if `ALLOW_SQLITE_IN_PROD` is present.
- **Fail-Closed Safety Guards:**
  - Hard failure if repository is not `ahmdelbaz28-ux/ETAP-AI-WORK-`.
  - Hard failure if `VERCEL_PROJECT_ID` matches production (`prj_WucHqc3lQDwYe0i3ykgWz7UR5E3I`).
  - Hard failure if target HF Space matches production (`ahmdelbaz28/AhmedETAP-Platform`).
  - Hard failure if `STAGING_DATABASE_URL` is empty, points to SQLite, or matches the production Supabase database.
  - Hard failure if target backend hosting space does not exist (pre-flight HTTP check).
  - Hard failure on health probe timeout (smoke test fails closed with exit code 1).

### 3.3 Backend Staging Deployment (Cloudflare Tunnel)
- **Architecture:** Cloudflare Secure Tunnel exposing dedicated AhmedETAP Staging FastAPI backend.
- **Active Endpoint:** `https://special-internationally-generic-forgot.trycloudflare.com`
- **Status:** **VERIFIED & OPERATIONAL (HTTP 200 on `/healthz`)**
- **Verified Study Execution:** Live IEEE 1584 Arc Flash study executed via `POST /api/v1/studies/run` with status `completed` (Incident energy: 0.6175 cal/cm², arc boundary: 234.1 mm).
- **Security:** Pure HTTPS with automatic SSL via Cloudflare edge; zero open inbound ports on host machine.

### 3.4 Dedicated Staging PostgreSQL Database (Supabase)
- **Project Name:** `AhmedETAP-Platform-Staging`
- **Project Ref:** `guunodspzhcxpmdwwyjv` (Dedicated, separate project in organization `AHMED ETAP`).
- **Host / Pooler:** `aws-1-eu-central-1.pooler.supabase.com:5432` (Frankfurt / `eu-central-1`).
- **Engine:** PostgreSQL 17.11 (Active & Healthy).
- **Isolation:** 100% independent database; zero shared tables, zero production credentials. Ephemeral SQLite permanently banned (`ALLOW_SQLITE_IN_PROD=false`).
- **Schema Status:** All 20 ORM tables created; Alembic stamped at head revision `016_snapshot_components`.
- **Health Check:** `check_db_health()` verified `{"status": "healthy", "backend": "postgresql", "fallback_active": False}`.

---

## 4. Backend & Database Alternative Architectures (Zero-Cost / Pro-Alternative)

Because the owner declined the Hugging Face PRO subscription, the staging backend and database can be deployed using one of the following fully viable, production-grade architectures:

### Option A: Free Serverless PostgreSQL + Free Container Hosting (Recommended Cloud $0 Solution)
- **Database:** **Neon.tech Serverless PostgreSQL** (Free Tier):
  - 0.5 GB permanent storage, automated branching, SSL-enabled, full PostgreSQL 16 compatibility.
  - Completely independent from production Supabase.
  - Zero ongoing cost.
- **Backend Compute:** **Koyeb** or **Render.com** (Free / Low Tier):
  - Deploys Docker container directly from GitHub or container registry.
  - Koyeb Free Tier provides 1 web service running Docker on `nano` instance with free HTTPS domain.
  - Connects to Neon PostgreSQL via `DATABASE_URL`.
- **Frontend Integration:**
  - Update `VITE_API_URL` in Vercel `etap-ai-work-staging` to point to the Koyeb/Render URL.

### Option B: Local Workstation / Dedicated Server Container with Cloudflare Zero Trust Tunnel ($0 Self-Hosted Solution)
- **Database & Compute:** Local Docker Compose on Engineering Workstation (EWS) or private Linux VM:
  - Container 1: `postgres:16-alpine` (persistent Docker volume).
  - Container 2: `ahmedetap-backend` (running `Dockerfile` via Uvicorn).
- **Public Tunnel:** **Cloudflare Tunnel (cloudflared)**:
  - Free, zero open inbound firewall ports.
  - Exposes `https://staging-api.ahmedetap.org` (or Cloudflare provided subdomain) routing securely to the local container.
- **Advantages:**
  - Uncapped CPU and RAM for heavy ETAP simulations (Load Flow, Transient Stability, OPF).
  - 100% control, zero cloud bills, persistent local PostgreSQL.

### Option C: Repurpose an Existing Docker Space on Hugging Face (If Available)
- If an existing, pre-approved Hugging Face Space under `ahmdelbaz28` is inactive and already authorized as a Docker space, it could be repurposed as the Staging Space without additional subscription fees.
- Requires explicit verification of existing space permissions from the owner.

---

## 5. Operational Safety & Rollback Procedures

1. **Staging Rollback Trigger:**
   If a Staging deployment experiences health probe failures, numerical errors, or unexpected crashes:
   - Trigger `.github/workflows/cd-staging.yml` via `workflow_dispatch` with the previous known green commit SHA.
   - Or redeploy the previous deployment via the Vercel dashboard for `etap-ai-work-staging`.
2. **Feature Flag Isolation:**
   - All 8 candidate capabilities remain strictly `enabled: False` in the staging configuration.
   - Any future runtime flag toggle must be performed through the Staging API administration interface and will affect only the Staging container.
3. **No Cross-Contamination:**
   - Under no circumstances will staging credentials, tokens, or endpoints be merged into `main` or deployed to `production`.

---

## 6. Owner Decision Points & Unblocking Steps

To transition Staging from `BLOCKED` to `READY`:

1. **Select Hosting & Database Architecture:**
   - Approve **Option A** (Neon PostgreSQL + Koyeb/Render Docker) or **Option B** (Local Workstation Docker + Cloudflare Tunnel).
2. **Provision Independent PostgreSQL Database:**
   - Create a free project at [Neon.tech](https://neon.tech) or [Supabase](https://supabase.com).
   - Retrieve connection string (`postgresql://user:pass@host/dbname?sslmode=require`).
3. **Configure GitHub `staging` Environment Secrets:**
   - Add `STAGING_DATABASE_URL` (the independent PostgreSQL connection string).
   - Add `STAGING_VERCEL_TOKEN` (the Vercel deployment token).
   - Add `STAGING_JWT_SECRET_KEY` and `STAGING_ENGINEERING_SERVICE_API_KEY` (staging-only auth keys).
   - Update `vars.HF_SPACE_URL` or set backend URL variable to match the chosen backend host.
