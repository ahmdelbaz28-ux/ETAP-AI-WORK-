# 04 — RUNTIME RISKS
## Production Runtime Hazards

### 🔥 RR-01: UVICORN RELOAD ENABLED IN PRODUCTION-LIKE ENVIRONMENTS
**Severity: MEDIUM** | **Category: RESOURCE LEAK / SECURITY**

**Root Cause:**
In `engineering_service.py` (line 76):
```python
reload=os.environ.get("ENVIRONMENT", "development").lower() == "development",
```
When `ENVIRONMENT=development`, uvicorn runs with auto-reload enabled. If someone accidentally sets `ENVIRONMENT=development` in production:
- File watchers consume additional CPU/memory
- Every code change triggers an automatic restart
- The reloader spawns a child process that may not inherit security context correctly

**Risk:** Low (requires misconfiguration), but worth noting.

---

### 🔥 RR-02: EXCEPTION HANDLER LEAKS EXCEPTION TYPE VIA HEADER
**Severity: LOW** | **Category: INFORMATION DISCLOSURE**

In `hf-space/app.py` (line 191):
```python
headers={"X-Error-Type": type(exc).__name__},
```
The global exception handler returns the exception class name in a response header. While the body message is sanitized, the header leaks information about the internal error type (e.g., `IntegrityError`, `OperationalError`, `ValueError`).

**Impact:**
- Attackers can fingerprint the database type (SQLite vs PostgreSQL) via `IntegrityError` vs `OperationalError`
- Information gathering for targeted attacks

**Fix:**
Remove the `X-Error-Type` header in production.

---

### 🔥 RR-03: HEALTH CHECK DOESN'T VERIFY DATABASE CONNECTIVITY
**Severity: MEDIUM** | **Category: FALSE POSITIVE HEALTH**

In `hf-space/app.py` (lines 431-433):
```python
@app.get("/healthz", tags=["Health"])
async def healthz():
    return JSONResponse(content={"status": "ok"}, status_code=200)
```
The `/healthz` endpoint always returns `200 OK` without checking:
- Database connectivity
- Redis availability
- External service reachability

Compare with `api/health.py` (imported at line 447 via `build_health_response`) which DOES check the database. But `/healthz` is the standard Kubernetes/HF Space health check endpoint and it reports "ok" even when the database is completely down.

**Impact:**
- Load balancer keeps routing traffic to a broken instance
- HF Space reports the app as "running" when it's degraded
- Auto-scaling/auto-healing systems won't trigger

**Fix:**
Make `/healthz` perform a lightweight database ping check (similar to `check_db_health()` in `api/database.py`).

---

### 🔥 RR-04: LIFESPAN DATABASE INIT EXCEPTION IS SILENTLY LOGGED
**Severity: LOW** | **Category: SILENT FAILURE**

In `hf-space/app.py` (lines 102-105):
```python
try:
    from api.database import init_db
    await init_db()
except Exception:
    logger.exception("Database init failed: %s")
```
The format string `"Database init failed: %s"` uses `%s` but no exception variable is being formatted into it. The actual exception IS logged via `logger.exception()` (which includes the traceback), but the message `"Database init failed: %s"` has a dangling format specifier.

**Fix:**
Change to `logger.exception("Database init failed")`.

---

### 🔥 RR-05: CUA EXECUTION RUNS IN `asyncio.to_thread()` — NO TIMEOUT
**Severity: MEDIUM** | **Category: HANGING REQUEST**

In `hf-space/app.py` (lines 669-676):
```python
result = await asyncio.to_thread(
    agent.execute_cua_loop,
    question=question,
    max_steps=max_steps,
    require_confirmation=require_confirmation,
    audit_dir=audit_dir,
    start_url=start_url,
)
```
The CUA loop runs in a thread without any timeout. If the Playwright browser hangs or the Gemini Vision API hangs:
- The thread is never released
- The HTTP request hangs until the client times out
- Accumulated hanging threads exhaust the thread pool
- The entire server becomes unresponsive

**Fix:**
Wrap in `asyncio.wait_for()` with a reasonable timeout (e.g., 300 seconds for CUA loop).

---

### 🔥 RR-06: RATE LIMITER WRONG DATA TYPE FOR `str` VS `int` TOKEN EXPIRY
**Severity: LOW** | **Category: TYPE MISMATCH**

In `api/auth.py` (line 741):
```python
if isinstance(exp, (int, float)):
    now_epoch = datetime.now(tz=UTC).timestamp()
    ttl_seconds = int(exp - now_epoch)
```
`exp` from JWT payload is always `int` (epoch seconds). But if the JWT was decoded with `options={"verify_exp": False}` (as done during logout), the `exp` field is already validated as an integer. The isinstance check is technically correct but redundant.

---

### 🔥 RR-07: SQLITE THREAD SAFETY CONFIGURATION
**Severity: MEDIUM** | **Category: DATABASE CORRUPTION**

In `api/database.py` (line 131):
```python
connect_args={"check_same_thread": False},
```
SQLite is configured with `check_same_thread=False`, allowing multiple threads to use the same connection. SQLite is NOT thread-safe for writes — concurrent writes can cause `database is locked` errors or data corruption.

**Risk:** Low with async app (single-threaded event loop), but if Celery workers or background threads also use the SQLite database, corruption is possible.

---

### 🔥 RR-08: `SMITHERY_API_KEY` LOGGED AT STARTUP
**Severity: LOW** | **Category: SECRET IN LOGS**

In `routes.py` (line 90):
```python
logger.info("smithery_api_key_available", extra={"trace_id": "startup"})
```
While this doesn't log the actual key value, it does log that a Smithery API key is configured. Combined with other information, this can aid an attacker in understanding the infrastructure.

---

### 🔥 RR-09: NO RATE LIMITING ON FILE UPLOAD / DATA IMPORT
**Severity: MEDIUM** | **Category: DOS**

The `data_import` router is mounted but the data_import.py file wasn't examined. File upload endpoints without rate limiting can be abused for:
- Disk space exhaustion
- Connection pool exhaustion
- Processing queue backpressure

**Risk:** Unknown without examining `api/data_import.py`.

---

### 🔥 RR-10: PYTHONPATH SET TO `/app` ENABLES IMPORT HIJACKING
**Severity: LOW** | **Category: DEPENDENCY CONFUSION**

In `Dockerfile` (line 94):
```dockerfile
ENV PYTHONPATH=/app
```
With `/app` on `PYTHONPATH`, if any dependency installs a package with the same name as an internal module, the dependency could be imported instead. This is a common attack vector for dependency confusion.