# Hugging Face Space Secrets Audit & Operational Hygiene

**Version:** 2.1.0  
**Last Updated:** 2026-10-07  
**Maintainer:** Eng. Ahmed Elbaz / Platform Core Team  
**Enforcement:** `hf-space/app.py` (`_startup_auth_fail_closed_check()`) & `.github/workflows/cd.yml`  

---

## 1. Executive Summary

This document provides the authoritative inventory and security configuration for all secrets, credentials, and environmental tokens utilized across the **AhmedETAP Hugging Face Space** (`ahmdelbaz28/AhmedETAP-Platform`) and associated CI/CD deployment pipelines.

In accordance with **Fail-Closed Security Guard (FIX-15)** and **Alembic Startup Gate (FIX-27)**, all production instances strictly enforce validation on startup:
- Missing mandatory secrets abort application boot immediately with `RuntimeError`.
- Weak or placeholder credentials (`placeholder`, `your-secret-here`, `test-dummy-key-changeme`) are strictly rejected.
- SQLite is forbidden in production unless explicitly allowed in single-container tests via `ALLOW_SQLITE_IN_PROD=true`.

---

## 2. Secrets Audit Matrix

| Secret Identifier | Subsystem / Purpose | Production Requirement | Default / Dev Fallback | Rotation Cycle |
|---|---|---|---|---|
| `ENGINEERING_SERVICE_API_KEY` | Master API gateway authentication for external clients & Mastra agents | **Mandatory** (or `HF_API_KEY`) | Dev allows unauthenticated with warning | 90 days |
| `HF_API_KEY` | Hugging Face space API authentication alias | **Mandatory** (if no `ENGINEERING_SERVICE_API_KEY`) | None | 90 days |
| `DATABASE_URL` | Persistent PostgreSQL connection string (`postgresql+asyncpg://...`) | **Mandatory** (PostgreSQL required) | Local SQLite development database | 180 days |
| `JWT_SECRET_KEY` | HMAC-SHA256 signing secret for user session tokens (Access/Refresh) | **Mandatory** | Ephemeral dev key (warns on startup) | 90 days |
| `REDIS_URL` | Distributed state, rate limiting, Alembic migration locks (`rediss://...`) | **Mandatory for multi-replica** | In-memory fallback (pinned to 1 replica) | 180 days |
| `HF_TOKEN` | Fine-grained Hugging Face write token for Git Space sync & metadata queries | **Mandatory in CI/CD** | None (CI only) | 90 days |
| `VERCEL_TOKEN` | Token for deploying prebuilt React frontend to Vercel production | **Mandatory in CI/CD** | None (CI only) | 90 days |
| `SONAR_TOKEN` | SonarCloud security and code quality gate token | **Mandatory in CI/CD** | Advisory in dev | 180 days |
| `LANGFUSE_PUBLIC_KEY` | Public key for Langfuse LLM telemetry & prompt caching | Optional (Advisory) | In-memory trace logging | 365 days |
| `LANGFUSE_SECRET_KEY` | Secret key for Langfuse LLM telemetry & prompt caching | Optional (Advisory) | In-memory trace logging | 365 days |
| `LANGFUSE_BASE_URL` | Custom endpoint for Langfuse instance (default: cloud.langfuse.com) | Optional | Default cloud endpoint | N/A |
| `SLACK_WEBHOOK_URL` | Incoming webhook for deployment failure alerts & health digests | Optional (Advisory) | Logging to stdout | 180 days |
| `RESEND_API_KEY` | Resend transactional email API key (OTP, Magic Links, Welcome emails) | Optional (Advisory) | Logged to stdout if unconfigured | 180 days |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 storage key for persistent CAD/CIM export files | Optional | Local file export fallback | 180 days |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 storage secret | Optional | Local file export fallback | 180 days |
| `R2_BUCKET_NAME` | Target R2 bucket name | Optional | Local directory | N/A |
| `R2_ENDPOINT_URL` | Cloudflare S3-compatible endpoint | Optional | Local storage | N/A |

---

## 3. Credential Rotation & Incident Remediation

### 3.1 Historical Leak Remediation Verification (D1)
- **Incident Scope:** Historical documentation (`docs/archive/ETAP_Radical_Remediation_Plan_v2.0.md`) referenced an exposed GitHub Personal Access Token (`github_pat_11CCHF...`).
- **Remediation Execution:**
  1. The leaked PAT token was revoked and deleted immediately from GitHub Developer Settings.
  2. Active secret scanning was integrated into `.github/workflows/secret-scan.yml` with native `gitleaks:v8.28.0` and custom regex detection in `core/error_tracking.py`.
  3. No live secrets or tokens are stored in the git tree. All references in `core/error_tracking.py` serve strictly as redacting scanner rules.

### 3.2 Rotation Procedure
When rotating any production secret:
1. **Database Credentials:** Update password in upstream managed database (Supabase / Neon), then update `DATABASE_URL` in HF Space Settings -> Variables and secrets.
2. **JWT Secret:** Generate a cryptographically secure 256-bit token (`openssl rand -hex 32`) and update `JWT_SECRET_KEY`. Existing sessions will expire safely upon access token expiry.
3. **API Keys:** Update `ENGINEERING_SERVICE_API_KEY` and propagate to Mastra Node runtime `.env` and client integration profiles.
4. **CI/CD Tokens (`HF_TOKEN`, `VERCEL_TOKEN`):** Rotate directly in GitHub Repository Secrets (`Settings -> Secrets and variables -> Actions`).

---

## 4. Operational Hygiene & Verification Checklist

- [x] **No Placeholder Tokens:** Verified that all secrets in HF Space production contain genuine, high-entropy keys with zero default placeholder strings.
- [x] **Fail-Closed Gate Active:** Verified that `_startup_auth_fail_closed_check()` in `hf-space/app.py` actively halts boot if mandatory secrets are missing.
- [x] **Post-Deployment Smoke Verification:** Automated smoke test `scripts/post_deploy_smoke.py` validates JWT authentication and study execution against live endpoints.
