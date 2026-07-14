# 05 — PERFORMANCE RISKS
## Production Performance Hazards

### 📊 PR-01: SQLITE DATABASE ON HF SPACE — NO CONCURRENCY
**Severity: HIGH** | **Impact: REQUEST QUEUING, TIMEOUTS**

**Root Cause:**
On HF Space, the database is SQLite at `sqlite+aiosqlite:////tmp/data/etap_platform.db`. SQLite serializes ALL writes — only one write transaction can proceed at a time.

**Impact:**
- With multiple users registering/logging in concurrently, requests queue
- Under load, all database operations serialize behind a write lock
- HF Space cpu-basic has limited CPU (2 cores) → write contention causes cascading timeouts
- The healthz endpoint returns 200 even when the database is locked

**Fix:**
- Use PostgreSQL on HF Space (connect to Supabase PostgreSQL)
- Remove the automatic SQLite fallback for production
- If SQLite must be used, consider WAL mode for better concurrency

---

### 📊 PR-02: IN-MEMORY RATE LIMITER IS O(N) ON PRUNE
**Severity: MEDIUM** | **Impact: REQUEST LATENCY SPIKES**

**Root Cause:**
In `routes.py` (lines 204-212):
```python
if len(_rate_limit_fallback_store) > _RATE_LIMIT_MAX_ENTRIES:
    stale = [
        cid
        for cid, timestamps in _rate_limit_fallback_store.items()
        if not timestamps or now - timestamps[-1] > _RATE_LIMIT_WINDOW
    ]
    for cid in stale:
        del _rate_limit_fallback_store[cid]
```
When the store exceeds 10,000 entries, it iterates ALL entries to find stale ones. This is O(n) during the prune, and the prune happens on EVERY request until entries drop below the threshold.

**Impact:**
- Under DDoS with 10,000+ unique IPs, every request triggers a full dictionary scan
- 10,000+ iterations per request adds measurable latency
- The latency spike makes the server MORE vulnerable during attack

**Fix:**
Use `collections.OrderedDict` with TTL-based eviction, or `cachetools.TTLCache`.

---

### 📊 PR-03: `_LOGIN_ATTEMPTS` DICT GROWS WITHOUT BOUND
**Severity: MEDIUM** | **Impact: MEMORY EXHAUSTION**

**Root Cause:**
In `api/auth.py`, `_LOGIN_ATTEMPTS` is a global dict that stores failed login attempts. Entries are appended but never removed (see HB-01). With enough users:
- 1 million entries × ~100 bytes ≈ 100 MB
- On HF Space with 2GB total RAM, this is significant wasted memory
- If an attacker rotates through 10,000 usernames, each attempt adds an entry

---

### 📊 PR-04: JSON SERIALIZATION IN CRITICAL PATH
**Severity: LOW** | **Impact: UNNECESSARY CPU**

In `routes.py` (lines 721-724):
```python
t0 = _time.perf_counter()
payload = {"matrix_size": 200, "ok": numpy_ok}
_ = _json.dumps(payload)
json_ms = (_time.perf_counter() - t0) * 1000.0
```
The `/api/v1/benchmark` endpoint unnecessarily serializes JSON as part of the benchmark. While negligible for benchmarks, this pattern shows a general awareness of performance but the benchmark itself is wasteful during peak load.

---

### 📊 PR-05: DATABASE CONNECTION POOL POTENTIALLY EXHAUSTED
**Severity: MEDIUM** | **Impact: CONNECTION TIME-OUTS**

In `api/database.py` (lines 93-96):
```python
_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
```
Default pool: 10 connections permanent + 20 overflow = 30 total. With asynchronous handlers that hold connections for the duration of a request:
- 30 concurrent requests can exhaust the pool
- The 31st request waits for `pool_timeout` (30 seconds)
- If the timeout is exceeded, the request fails with `TimeoutError`

**Impact:**
- Under moderate load (30+ concurrent API calls), requests start failing
- The health check returns "healthy" because it uses its own session
- Degradation is gradual and hard to diagnose

**Fix:**
- Increase pool size based on expected concurrency
- Implement connection pooling monitoring
- Add pool exhaustion alerting

---

### 📊 PR-06: CELERY COMPONENTS ARE IMPORTED ON EVERY COLD START
**Severity: LOW** | **Impact: SLOW STARTUP**

In `routes.py` (lines 328-349):
```python
def get_celery_components() -> tuple[Optional[Any], Optional[Any], Optional[Any]]:
    global _celery_cache
    if _celery_cache:
        return _celery_cache
    try:
        from celery.result import AsyncResult
        from worker.celery_app import app as celery_app
        from worker.tasks import execute_engineering_study_task
        ...
```
While the import is lazy and cached, the first request to `/api/v1/studies/run_async` on a cold start will block for several seconds while Celery components are imported. On HF Space, this can trigger request timeouts.

---

### 📊 PR-07: NO REQUEST SIZE LIMIT ON STUDY EXECUTION
**Severity: MEDIUM** | **Impact: MEMORY EXHAUSTION**

The body size limit (1MB) applies to all POST/PUT/PATCH requests. However, the study execution endpoint (`POST /api/v1/studies/run`) can receive large power system models. If a study request is accepted (within 1MB), the server must deserialize and process it, which could consume significantly more memory than the request body size.

**Fix:**
Set explicit memory limits for study processing, or implement streaming for large payloads.