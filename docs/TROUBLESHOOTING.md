# AhmedETAP Troubleshooting Guide (v2.0 Production Runbook)

This guide provides operational diagnostics, common failure modes, root causes, and verified remediation procedures for the AhmedETAP platform.

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

## 2. Database, Alembic Migrations & Redis Shared State

### Production PostgreSQL Connection Failure
- **Symptom**: Startup fails with `FATAL: DATABASE_URL must be configured` or connection timeout.
- **Root Cause**: Per FIX-14, ephemeral SQLite is forbidden in production environments. A persistent PostgreSQL instance (e.g. Supabase Postgres) is mandatory.
- **Resolution**:
  1. Verify the `DATABASE_URL` environment variable format:
     `postgresql+asyncpg://user:password@host:port/dbname`
  2. Test network connectivity to port 5432/6543 (pooler).
  3. Ensure SSL mode is enabled (`?ssl=require`).

### Alembic Startup Migration Gate Failure (FIX-27)
- **Symptom**: Application logs `FATAL: Database migration failed at startup (Fail-Closed)` and terminates boot.
- **Root Cause**: Pending migrations exist or a dirty revision was applied to the database schema.
- **Resolution**:
  ```bash
  # Check current revision vs head:
  alembic current
  alembic heads

  # Apply pending migrations:
  alembic upgrade head

  # If a migration got interrupted and needs stamping:
  alembic stamp head
  ```

### Redis Shared State & Distributed Lock Contention (FIX-22)
- **Symptom**: Session data missing on cross-replica requests or `TimeoutError: Could not acquire distributed lock for resource: ...`.
- **Root Cause**:
  1. `REDIS_URL` not configured or unreachable; replicas falling back to in-memory mode.
  2. A task died holding a lock before TTL expired.
- **Resolution**:
  ```bash
  # Test Redis connectivity:
  redis-cli -u "$REDIS_URL" ping
  # Inspect active locks:
  redis-cli -u "$REDIS_URL" keys "etap:lock:*"
  # Inspect sessions:
  redis-cli -u "$REDIS_URL" keys "etap:session:*"
  ```

### Administrator Account Bootstrap
- **Symptom**: New users registered via the API get `role="viewer"` and cannot approve changes.
- **Resolution**: Set `INITIAL_ADMIN_EMAIL` before the user registers, or run the CLI helper:
  ```bash
  python scripts/create_admin.py --username admin --email admin@domain.com --password "SecurePass123!"
  ```

---

## 3. Frontend, CSP & UI Bundle Security

### Content-Security-Policy (CSP) Script or Style Blocking (FIX-29)
- **Symptom**: Browser console logs `Refused to execute inline script because it violates the following Content Security Policy directive...`.
- **Root Cause**: `SecurityHeadersMiddleware` strictly enforces CSP (`script-src 'self' 'unsafe-inline'`, `connect-src 'self' wss: https:`).
- **Resolution**: Do not load scripts from external unvetted CDNs. All API requests must route to same-origin or explicit HTTPS/WSS endpoints.

### UI Bundle Secret Scanning Failure
- **Symptom**: CI fails step `UI Bundle Provider Keys Scan` with `[FAIL] CRITICAL: Found exposed secrets in UI bundle`.
- **Root Cause**: A frontend file in `ui/` or `ui/dist` contains a literal API token (`sk-`, `hf_`, `vcp_`, `sb_`, `github_pat_`).
- **Resolution**: Run `python scripts/check_bundle_secrets.py` locally to locate and purge any exposed keys.

---

## 4. SCADA, Telemetry & Multi-Agent Scenarios

### IEC 61850 Logical Node or Interlock Violation
- **Symptom**: Control action rejected with `InterlockViolation: invalid telemetry timestamp` or `bad signal quality`.
- **Root Cause**: Telemetry data has expired timestamp (>60s old) or signal quality is not GOOD.
- **Resolution**: Verify NTP time synchronization on SCADA gateways and check that device signal quality flags are healthy.

### ETAP COM Windows Integration
- **Symptom**: `ImportError: win32com.client` or `ETAP COM Automation unavailable`.
- **Root Cause**: ETAP COM API is Windows-only (`pywin32`). In Linux/Docker environments, the system automatically uses validated native Python calculation engines (Newton-Raphson, IEC 60909).

---

## 5. Deployment, CI/CD, and Rollback

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

## 6. Operational Monitoring & Health

### Health Probe Verification
- **App Healthz**: `GET /healthz` on port 7860/8000.
  Returns HTTP 200 `{"status":"ok"}`.
- **Readiness Probe**: `GET /readyz`
  Returns HTTP 200 `{"ready": true, "checks": {"db": "ok", "redis": "ok", "schema_version": "011_add_hardening_tables"}}` or 503 on dependency outage.
- **Schema Health**: `GET /api/v1/health/schema`
  Returns HTTP 200 `{"status": "synchronized", "head_revision": "011_add_hardening_tables"}`.
- **Metrics**: `GET /metrics` exports Prometheus metrics including request rates and study latencies.
- **Syslog Forwarder**: Configured via `SIEM_ENABLED=true` and `SIEM_SYSLOG_HOST` / `SIEM_SYSLOG_PORT` (UDP 514 / TCP 514 / TLS 6514 per RFC 5424).