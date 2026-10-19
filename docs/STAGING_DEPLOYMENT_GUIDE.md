---
title: "AhmedETAP Isolated Staging Environment Architecture & Deployment Guide"
version: "2.1.0"
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
  - [3.3 Backend (Hugging Face Spaces)](#33-backend-hugging-face-spaces)
  - [3.4 Database & Persistence](#34-database--persistence)
- [4. Operational Safety & Rollback Procedures](#4-operational-safety--rollback-procedures)
- [5. Owner Action Items](#5-owner-action-items)

---

## 1. Executive Summary & Purpose

In alignment with the **AhmedETAP Zero-Fabrication Rule (R3)** and the **Owner Authorization Mandate**, this document establishes the isolated Staging deployment environment for AhmedETAP (`ahmdelbaz28-ux/ETAP-AI-WORK-`).

The Staging environment provides an independent, sandboxed platform allowing engineers to test and verify new capabilities (such as `harmonic_analysis`, `cable_sizing`, `motor_starting`, `transient_stability`, `optimal_power_flow`, `earth_grid`, `renewable_integration`, and `battery_storage`) without risk of cross-contamination with live production customers or real electrical systems.

---

## 2. Component Separation Matrix

| Component | Production Instance | Staging Target | Proof of Strict Isolation |
|:---|:---|:---|:---|
| **Backend / API** | `https://ahmdelbaz28-ahmedetap-platform.hf.space` | `https://ahmdelbaz28-ahmedetap-platform-staging.hf.space` | Distinct HF Space repository, separate runtime container, distinct subdomain |
| **Frontend / UI** | `etap-ai-work` (`prj_WucHqc3lQDwYe0i3ykgWz7UR5E3I`) | `etap-ai-work-staging` (`prj_XHvIpATc0SF11QBeCNPatRe5t8Af`) | Separate Vercel Project ID, distinct build environment, `VITE_API_URL` bound to Staging |
| **Database** | Supabase PostgreSQL (`aws-1-eu-central-1.pooler.supabase.com`) | Isolated Staging DB (`ALLOW_SQLITE_IN_PROD=true` or separate PG schema) | Zero shared tables, zero customer data, zero production connection string |
| **Authentication** | Production `JWT_SECRET_KEY` & `ENGINEERING_SERVICE_API_KEY` | Dedicated Staging signing keys | Tokens issued in Staging cannot authenticate against Production |
| **Feature Flags** | Managed production store (`.feature-flags.json`) | Isolated Staging flag evaluation | Runtime flag toggles in Staging do not propagate to Production |
| **Grid / SCADA** | Fail-closed production interlocks | Synthetic fixtures & mock adapters only | Zero live Modbus/OPC-UA/IEC 61850 network packets to physical devices |

---

## 3. Staging Infrastructure Components Status

### 3.1 Frontend (Vercel)
- **Project Name:** `etap-ai-work-staging`
- **Project ID:** `prj_XHvIpATc0SF11QBeCNPatRe5t8Af` (Created & Verified via Vercel API)
- **Framework:** `vite`
- **Build Command:** `bash vercel-build.sh`
- **Output Directory:** `ui/dist`
- **Environment Variable:** `VITE_API_URL = https://ahmdelbaz28-ahmedetap-platform-staging.hf.space` (configured across Production, Preview, and Development targets on Vercel).

### 3.2 GitHub Actions CI/CD
- **Workflow File:** `.github/workflows/cd-staging.yml`
- **Trigger:** `workflow_dispatch` (with pinned `ref_sha`) or push to `staging` branch.
- **Environment Target:** `staging`
- **GitHub Environment Variables Set:**
  - `VERCEL_PROJECT_ID`: `prj_XHvIpATc0SF11QBeCNPatRe5t8Af`
  - `HF_SPACE_NAME`: `ahmdelbaz28/AhmedETAP-Platform-Staging`
  - `HF_SPACE_URL`: `https://ahmdelbaz28-ahmedetap-platform-staging.hf.space`
  - `STAGING_UI_URL`: `https://etap-ai-work-staging.vercel.app`
  - `ALLOW_SQLITE_IN_PROD`: `true` (enables isolated ephemeral local DB in staging)
- **Safety Guards:**
  - Hard failure if `VERCEL_PROJECT_ID` matches production (`prj_WucHqc3lQDwYe0i3ykgWz7UR5E3I`).
  - Hard failure if target HF Space matches production (`ahmdelbaz28/AhmedETAP-Platform`).

### 3.3 Backend (Hugging Face Spaces)
- **Target Space Name:** `ahmdelbaz28/AhmedETAP-Platform-Staging`
- **Current Status:** `BLOCKED — 402 PAYMENT REQUIRED`
- **Evidence:** Querying `POST https://huggingface.co/api/repos/create` returned:
  ```json
  {"error":"Static Spaces are free for everyone, but hosting Gradio and Docker Spaces on free cpu-basic requires a PRO subscription. Subscribe at https://huggingface.co/pro"}
  ```
- **Analysis:** Hugging Face updated its terms requiring a PRO subscription ($9/mo) to spawn new Docker-based Spaces. The existing production Space (`ahmdelbaz28/AhmedETAP-Platform`) is running on `cpu-basic`, but creating an additional Docker Space under `ahmdelbaz28` requires subscription activation or manual assignment.

### 3.4 Database & Persistence
- Staging is configured to run with `ALLOW_SQLITE_IN_PROD=true` in `api/config_prod.py`, providing a completely sandboxed local SQLite database `/tmp/data/etap_staging.db`.
- Alternatively, when a dedicated Staging PostgreSQL instance is provisioned, its connection string should be added to the GitHub `staging` environment secret `DATABASE_URL`.

---

## 4. Operational Safety & Rollback Procedures

1. **Staging Rollback Trigger:**
   If a Staging deployment experiences health probe failures, numerical errors, or unexpected crashes:
   - Trigger `.github/workflows/cd-staging.yml` via `workflow_dispatch` with the previous known green commit SHA.
   - Or deploy the previous pre-built deployment via the Vercel dashboard / CLI for `etap-ai-work-staging`.
2. **Feature Flag Isolation:**
   - All 8 candidate capabilities remain strictly `enabled: False` in the staging configuration.
   - Any future runtime flag toggle must be performed through the Staging API administration interface and will affect only the Staging container.

---

## 5. Owner Action Items

To unblock the Backend Hugging Face Space provisioning:
1. **Activate Hugging Face PRO Subscription:**
   - Visit [https://huggingface.co/pro](https://huggingface.co/pro) on user account `ahmdelbaz28`.
   - Complete PRO subscription activation.
   - Or alternatively, create an Organization with billing enabled and transfer/create the space under the organization.
2. **Create the Staging Space:**
   - Navigate to [https://huggingface.co/new-space](https://huggingface.co/new-space)
   - Space Name: `AhmedETAP-Platform-Staging`
   - License: `MIT`
   - SDK: `Docker` (blank Dockerfile)
   - Visibility: `Public` (or `Private`)
3. **Configure GitHub `staging` Secrets:**
   - Add `HF_TOKEN` (with write permissions) and `VERCEL_TOKEN` to GitHub Environment `staging`:
     [https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/settings/environments](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/settings/environments)
