# AhmedETAP Troubleshooting Guide

This guide provides operational diagnostics, common failure modes, and verified remediation procedures for the AhmedETAP platform (v2.0 production architecture).

---

## 1. Authentication & Security Issues

### HTTP 401 Unauthorized on Study or Validation Endpoints
- **Affected Endpoints**: `POST /api/v1/studies/re-run`, `POST /api/v1/tool-policy/evaluate`, `POST /api/v1/system/validate`.
- **Root Cause**: These endpoints are fail-closed and strictly require the `X-API-Key` or `Authorization: Bearer` header containing `ENGINEERING_SERVICE_API_KEY`.
- **Resolution**:
  ```bash
  curl -H "X-API-Key: $ENGINEERING_SERVICE_API_KEY" https://ahmdelbaz28-ahmedetap-platform.hf.space/api/v1/system/validate
  ```

### WebSocket Dual-Control Connection Dropped (Close Code 1011 or 4001)
- **Code 1011 (`Internal Error`)**: The server does not have `ENGINEERING_SERVICE_API_KEY` configured in its environment (fail-closed security).
- **Code 4001 (`Unauthorized`)**: The provided dual-control API key token is invalid or does not match the server secret.
- **Resolution**: Ensure `ENGINEERING_SERVICE_API_KEY` is properly defined in the deployment environment and the client sends `?token=<key>` or passes the authorization header upon connecting.

### Insecure JWT Secret Rejection at Startup
- **Symptom**: Application fails to boot with `FATAL: Insecure JWT secret key detected`.
- **Root Cause**: `JWT_SECRET_KEY` is using a known placeholder (such as `.env.example` sample string) or is shorter than 32 characters.
- **Resolution**:
  ```bash
  # Generate a cryptographically secure 256-bit secret:
  openssl rand -hex 32
  ```

---

## 2. Database & Data Layer Issues

### Production PostgreSQL Connection Failure
- **Symptom**: Startup fails with `FATAL: DATABASE_URL must be configured` or connection timeout.
- **Root Cause**: Per FIX-14, ephemeral SQLite is forbidden in production environments. A persistent PostgreSQL instance (e.g. Supabase Postgres) is mandatory.
- **Resolution**:
  1. Verify the `DATABASE_URL` environment variable format:
     `postgresql+asyncpg://user:password@host:port/dbname`
  2. Test network connectivity to port 5432/6543 (pooler).
  3. Ensure SSL mode is enabled (`?ssl=require`).

### Schema Out of Sync / Missing Tables
- **Symptom**: Query error `relation "users" does not exist` or `missing column`.
- **Resolution**: Run Alembic migrations against the database:
  ```bash
  alembic upgrade head
  ```

### Administrator Account Bootstrap
- **Symptom**: New users registered via the API get `role="viewer"` and cannot approve changes.
- **Resolution**: Set `INITIAL_ADMIN_EMAIL` before the user registers, or run the CLI helper:
  ```bash
  python scripts/create_admin.py --username admin --email admin@domain.com --password "SecurePass123!"
  ```

---

## 3. Deployment, CI/CD, and Rollback

### CD Run Fails with "NOT DEPLOYED"
- **Root Cause**: One or more deployment secrets (`HF_TOKEN`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`) are missing or empty in GitHub Repository Secrets.
- **Resolution**: Go to GitHub Repository Settings -> Secrets and Variables -> Actions, and verify all four secrets are defined.

### Deployment Drift-Check Failure
- **Symptom**: `cd.yml` step `Drift-check — every Dockerfile COPY source must be staged` exits with code 1.
- **Root Cause**: A new file or directory was added to a `COPY` instruction in `Dockerfile` without being included in the canonical 25-item production whitelist in `cd.yml`.
- **Resolution**: Add the necessary directory to the `Stage THE 25-item production whitelist` step in `.github/workflows/cd.yml`.

### Executing a Production Rollback
- **Procedure**:
  1. Identify the commit SHA of the last known-good green CI run:
     ```bash
     git log --oneline -n 10
     ```
  2. Navigate to GitHub Actions -> **Production Rollback** (`rollback.yml`).
  3. Click **Run workflow**, enter the 40-character target `git_sha` and incident `reason`.
  4. The workflow triggers `cd.yml` with the pinned SHA and validates `/healthz` post-rollback.

---

## 4. Operational Monitoring & Health

### Health Probe Verification
- **App Healthz**: `GET /healthz` on port 7860/8000.
  Returns HTTP 200 `{"status":"ok", "timestamp": ...}`.
- **Metrics**: `GET /metrics` exports Prometheus metrics including request rates and study latencies.
- **Syslog Forwarder**: Configured via `SIEM_ENABLED=true` and `SIEM_SYSLOG_HOST` / `SIEM_SYSLOG_PORT` (UDP 514 / TCP 514 / TLS 6514 per RFC 5424).
