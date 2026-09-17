# AhmedETAP — Staging & Production Deployment Operational Guide

This document defines the operational runbook and deployment standards for deploying AhmedETAP to staging and production environments.

---

## 1. System Architecture & Dual-Runtime Model

AhmedETAP operates on a dual-runtime architecture:
1. **Frontend & Orchestration Gateway**: React / TypeScript Chat-First v3.0 interface with Mastra TypeScript agent workflows.
2. **Authoritative Engineering Backend**: FastAPI application running on Python with validated computational solvers (Newton-Raphson load flow, IEC 60909 short circuit, IEEE 1584 arc flash, IEEE 399 motor starting).
3. **Shared Distributed State**:
   - **PostgreSQL 16**: Relational storage for users, projects, revisions, component libraries, and audit logs.
   - **Redis 7**: Distributed session persistence (`RedisSessionStore`), distributed resource locking (`LockManager`), and asynchronous job queueing (`RedisTaskQueue`).

---

## 2. Pre-Deployment Environment Checklist

All production and staging environments must supply the following environment variables. In staging and production (`ENV=production` or `ENV=staging`), any missing or weak variable triggers a **Fail-Closed** process termination at startup.

| Variable | Description | Security Requirement |
|---|---|---|
| `DATABASE_URL` | PostgreSQL async connection string | Must use `postgresql+asyncpg://`, SSL enabled in prod. |
| `REDIS_URL` | Redis distributed state connection | Must use `rediss://` (TLS) in public production. |
| `JWT_SECRET_KEY` | Key for signing and verifying JWTs | Minimum 32 bytes of cryptographic randomness (`secrets.token_hex(32)`). Known samples permanently banned. |
| `ENGINEERING_SERVICE_API_KEY` | Admin / service-to-service authentication | Cryptographically strong token. Banned samples cause startup crash. |
| `CRON_SECRET` | Secret token for Vercel/external cron jobs | Mandatory Bearer token for triggering `/api/cron/digest`. |
| `CSRF_SECRET` | Secret for signing anti-CSRF tokens | Minimum 32 bytes random string. |
| `DB_POOL_SIZE` | Connection pool size per worker (default: 5) | Sized with workers to prevent pool exhaustion. |
| `DB_MAX_OVERFLOW` | Max overflow connections per worker (default: 10) | Total per worker = pool + overflow (default: 15). |
| `DB_MAX_CONNECTIONS` | Expected database max_connections (default: 100) | Enforced via startup sizing check. |

### 2.1 Database Connection Pool Budgeting Formula
To prevent PostgreSQL connection exhaustion across multi-worker deployments (e.g. 4 Gunicorn workers):
```
Total Connections = Workers × (DB_POOL_SIZE + DB_MAX_OVERFLOW) <= DB_MAX_CONNECTIONS
```
With default settings:
```
4 workers × (5 pool + 10 overflow) = 60 connections <= 100 max_connections
```
If the calculated total exceeds `DB_MAX_CONNECTIONS`, the application logs a warning on startup.

---

## 3. Database Migration Rollout Procedure

AhmedETAP enforces an automatic **Fail-Closed Startup Migration Gate** (`api/database_migrations.py`):
1. Upon container startup during the FastAPI `lifespan`, the service automatically attempts to execute:
   ```bash
   alembic upgrade head
   ```
2. **Distributed Migration Lock**: In multi-worker / multi-replica environments, migration is coordinated via a Redis distributed lock (`LockManager.lock("alembic-migration", ttl_seconds=300, timeout_ms=120000)`).
   > [!WARNING]
   > Running multi-replica deployments without `REDIS_URL` falls back to uncoordinated execution and risks concurrent DDL migration collisions. Multi-replica environments MUST configure `REDIS_URL`.
3. In production or staging, if the migration fails or database schema diverges from `head_revision`, the process exits with a non-zero exit code to prevent dirty writes or split-brain schema state.
4. To inspect schema synchronization status at any time:
   ```bash
   curl -s -H "Authorization: Bearer <ADMIN_TOKEN>" http://localhost:8000/api/v1/health/schema
   ```

---

## 4. Verification & Staging Readiness Gate

Run the staging readiness verification script:
```bash
python scripts/verify_staging_readiness.py --url https://staging.ahmedetap.internal --api-key <KEY>
```
> [!NOTE]
> When using `python scripts/verify_staging_readiness.py --local`, execution is performed within an in-process FastAPI `TestClient`. While suitable for fast CI route verification, it does NOT test real network latency, socket buffer sizes, physical PostgreSQL connection pools, real Redis cluster failovers, or TLS certificates. Full staging drills must execute against a running HTTP/TLS service endpoint.

---

## 5. Feature Flags & Canary Rollout Strategy (Chat-First v3.0)
   **Expected Response:**
   ```json
   {
     "status": "synchronized",
     "head_revision": "011_add_hardening_tables"
   }
   ```

---

## 4. Automated Staging Verification Drill

Before cutting over real traffic, execute the automated readiness drill against the staging URL:

```bash
python scripts/verify_staging_readiness.py --base-url https://staging.ahmedetap.internal --api-key "$ENGINEERING_SERVICE_API_KEY"
```

The script automatically tests and reports all 6 production gates:
- **Gate 1**: Liveness & Readiness probes (`/health`, `/ready`, `/healthz`).
- **Gate 2**: Database migration synchronization at Head (`/api/v1/health/schema`).
- **Gate 3**: Security Headers & CSP (`X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, CSP).
- **Gate 4**: Fail-closed authentication enforcement (rejection of unauthorized calls).
- **Gate 5**: End-to-End Newton-Raphson study calculation with provenance validation (`POST /api/v1/studies/run`).
- **Gate 6**: Feature Flags registry integrity.

---

## 5. Canary Rollout Strategy (Chat-First v3.0)

As documented in `AGENTS.md`, traffic to Chat-First v3.0 is managed via gradual rollout:

### Phase 1: Internal Canary (Admin Only)
- Configuration in `.feature-flags.json`:
  ```json
  "chat_first_ui": {
    "enabled": false,
    "allow_list": ["admin"],
    "rollout_percentage": 0
  }
  ```
- Only administrators access Chat-First; all other engineers use the classic UI.

### Phase 2: Canary 10% (General User Cohort)
- Configuration:
  ```json
  "chat_first_ui": {
    "enabled": false,
    "allow_list": ["admin"],
    "rollout_percentage": 10
  }
  ```
- Deterministic SHA-256 bucketing routes 10% of users to Chat-First.
- Monitor error rates, token latency, and Redis lock contention for 48 hours.

### Phase 3: Full Production (100% Rollout)
- Configuration:
  ```json
  "chat_first_ui": {
    "enabled": true,
    "rollout_percentage": 100
  }
  ```
- The "استخدم الواجهة الكلاسيكية" (`onExitToLegacy`) emergency fallback button remains accessible for operational safety.

---

## 6. Disaster Recovery & Emergency Rollback Runbook

### Scenario A: Rollback Canary to Classic UI
If a critical frontend or streaming regression occurs in Chat-First:
1. Update feature flag via Admin API:
   ```bash
   curl -X PATCH http://localhost:8000/api/v1/feature-flags/chat_first_ui \
     -H "Authorization: Bearer <ADMIN_TOKEN>" \
     -H "X-CSRF-Token: <CSRF_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"enabled": false}'
   ```
2. Instantly drops all non-admin traffic back to the classic UI without container restarts.

### Scenario B: Database Migration Reversal
If a newly deployed migration causes SQL locking or incompatibility:
```bash
alembic downgrade -1
```
Verify schema health:
```bash
curl -s -H "Authorization: Bearer <ADMIN_TOKEN>" http://localhost:8000/api/v1/health/schema
```

### Scenario C: Redis Outage / Restart
If Redis restarts or becomes temporarily unavailable:
1. In development, the platform continues in single-process in-memory mode.
2. In production, `LockManager.acquire()` propagates a `ConnectionError` (or `RuntimeError`), failing closed immediately and aborting critical operations before state corruption occurs. The release mechanism safely no-ops (`release()` catches exceptions cleanly). At the API layer, the global exception handler catches unhandled exceptions and returns a sanitized HTTP 500 error envelope without exposing internal paths (`C:\`, `/home/`, `/app/`), Python tracebacks, or secret credentials (`password`, `secret`, `api_key`).
3. Once Redis is reachable again, clients re-establish connection automatically without process restart.

---

## 7. Observability & Telemetry Thresholds

AhmedETAP exposes Prometheus metrics at `/metrics` and `/prometheus/metrics`. Monitor these thresholds:

| Metric | Normal Target | Alert Threshold | Action |
|---|---|---|---|
| `http_req_duration` (p95) | < 250ms | > 500ms for 3m | Inspect Redis connection pool and database slow query log. |
| `http_req_failed` | < 0.1% | > 1.0% | Check application logs for 5xx unhandled exceptions. |
| `redis_task_queue_size` | < 50 jobs | > 200 jobs | Scale out Celery / background calculation worker replicas. |
| `token_budget_exceeded` | 0 | > 10 / hour | Investigate potential prompt injection or recursive tool loop. |
