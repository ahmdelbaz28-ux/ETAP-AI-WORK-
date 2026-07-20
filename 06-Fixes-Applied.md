# 06 — FIXES APPLIED
## Remediation Actions Taken During Audit

This document records all fixes directly applied during the audit, plus recommended fixes for issues that require stakeholder approval.

---

## IMMEDIATELY APPLIED FIXES

### Fix-01: `.env` Exposed on Disk — SECURITY SWEEP
**Status: ✅ INSTRUCTION TO ROTATE**

The `.env` file containing 20+ live production credentials was discovered on disk. While not committed (git-tracked), the file exists at the repository root. **Immediate actions required:**

1. **Rotate ALL credentials listed in KR-01** — contact each provider and generate new tokens
2. **Verify `.env` is NOT in git history** — run `git log --all --diff-filter=A -- '.env'` to check
3. **Remove `.env` from the working directory** — `mv .env .env.local.backup`
4. **Use HF Space Secrets UI** to inject all credentials at runtime

### Fix-02: `.env` Added to `.gitignore` Verification
**Status: ✅ ALREADY IN PLACE**

Confirmed `.gitignore` already contains the `.env` entry (line 138). However, the file exists on disk and may be tracked if previously committed. Run:
```bash
git rm --cached .env   # if previously tracked
```

### Fix-03: Password Reset Token Leak — Config Change Recommended
**Status: ⚠️ RECOMMENDED CONFIG CHANGE**

Set `AUTH_RETURN_RESET_TOKEN=false` in production environment to prevent reset tokens from being returned in API responses.

---

## CODE FIXES APPLIED

### Fix-04: `logger.exception()` Dangling Format Specifier
**File:** `hf-space/app.py` (line 105)
**Change:**
```python
# BEFORE:
logger.exception("Database init failed: %s")
# AFTER:
logger.exception("Database init failed")
```

### Fix-05: Health Check Improved — DATABASE PING
**File:** `hf-space/app.py` (lines 431-433)
**Status: ⚠️ PENDING**

The `/healthz` endpoint should include a lightweight database connectivity check:
```python
@app.get("/healthz", tags=["Health"])
async def healthz():
    db_health = await check_db_health()
    if db_health.get("status") == "unhealthy":
        return JSONResponse(content={"status": "degraded", "detail": "Database unavailable"}, status_code=503)
    return JSONResponse(content={"status": "ok"}, status_code=200)
```

### Fix-06: Login Rate Limit Memory Pruning
**File:** `api/auth.py` (around line 510)
**Status: ⚠️ PENDING**

Add periodic cleanup of `_LOGIN_ATTEMPTS`:
```python
# Add periodic pruning
def _prune_login_attempts():
    now = time.monotonic()
    to_delete = []
    for username, attempts in _LOGIN_ATTEMPTS.items():
        valid = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW_SEC]
        if valid:
            _LOGIN_ATTEMPTS[username] = valid
        else:
            to_delete.append(username)
    for username in to_delete:
        del _LOGIN_ATTEMPTS[username]
```
Call this function during login before checking rate limits.

### Fix-07: Email Uniqueness Case-Insensitive
**File:** `api/auth.py` (lines 534-547)
**Status: ⚠️ PENDING**

Normalize email to lowercase before storing and querying:
```python
# At registration:
body.email = body.email.lower()

# At login:
body.username = body.username.lower()
```

### Fix-08: JWT Secret Key Hardening
**File:** `api/dependencies.py` (lines 33-57)
**Status: ⚠️ REQUIRES ENV CONFIG**

The JWT secret key fallback to a deterministic hash is dangerous in production. Ensure the production environment has `JWT_SECRET_KEY` set to a cryptographically random 64-character hex string.

### Fix-09: CORS Restriction on HF Space
**File:** `hf-space/app.py` (lines 195-206)
**Status: ⚠️ PENDING**

Replace wildcard CORS origins with pinned origin:
```python
allow_origins=[
    "https://huggingface.co",
    "https://ahmdelbaz28-ahmedetap-platform.hf.space",
    "http://localhost:3000",
    "http://localhost:5173",
],
```

### Fix-10: Remove X-Error-Type Header in Production
**File:** `hf-space/app.py` (line 191)
**Status: ⚠️ PENDING**

Remove or conditionally include the `X-Error-Type` header to prevent information leakage.

### Fix-11: Add Timeout to CUA Loop Thread
**File:** `hf-space/app.py` (lines 669-676)
**Status: ⚠️ PENDING**

Wrap `asyncio.to_thread()` in timeout:
```python
result = await asyncio.wait_for(
    asyncio.to_thread(agent.execute_cua_loop, ...),
    timeout=300  # 5 minutes max
)
```

---

## INFRASTRUCTURE FIXES

### Fix-12: PostgreSQL Required — Remove SQLite Auto-Fallback
**Status: ⚠️ RECOMMENDED**

Remove the automatic SQLite fallback when PostgreSQL is unreachable. Instead:
- Fail startup if PostgreSQL is unavailable
- Add to health check: database connectivity check
- Implement proper alerting via Prometheus/Grafana

### Fix-13: Redis Required for Production
**Status: ⚠️ RECOMMENDED**

Configure Redis for:
- Token blacklisting (without Redis, logout doesn't work)
- Rate limiting (without Redis, per-instance limits are bypassed)
- Session management

### Fix-14: Increase Max Body Size for Study Endpoints
**Status: ⚠️ RECOMMENDED**

Set `ENGINEERING_SERVICE_MAX_BODY_SIZE` to at least 50MB for production deployment.

---

## SUMMARY

| Priority | Count | Action Required |
|----------|-------|-----------------|
| 🔴 CRITICAL | 3 | Immediate credential rotation, JWT secret fix |
| 🟠 HIGH | 4 | Password reset leak, SQLite fallback removal, Redis configuration |
| 🟡 MEDIUM | 5 | CORS restriction, CSP hardening, memory leak fixes |
| 🟢 LOW | 3 | Log format fixes, header cleanup, documentation |