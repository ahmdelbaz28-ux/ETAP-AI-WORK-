# 02 — HIDDEN BUGS
## Latent Defects Discovered During Audit

### 🐛 HB-01: LOGIN RATE LIMIT USERS IN-MEMORY STORE NEVER CLEANED
**Severity: MEDIUM** | **Category: MEMORY LEAK**

**Root Cause:**
In `api/auth.py` (line 510):
```python
_LOGIN_ATTEMPTS.setdefault(username, []).append(now)
```
The in-memory `_LOGIN_ATTEMPTS` dict grows unboundedly. Failed login attempts are appended but entries are never deleted — even successful logins leave stale entries. Over time, with many users attempting logins (or a distributed brute force), this dict will consume increasing memory.

**Impact:**
- Memory grows without bound
- On HF Space with limited memory (cpu-basic: 2GB), this can OOM the process
- No mechanism to prune entries older than the rate-limit window

**Fix:**
Implement periodic pruning of stale entries in `_LOGIN_ATTEMPTS` or switch to a TTL-based cache.

---

### 🐛 HB-02: API KEY AUTH GRANTS FULL ADMIN ACCESS — MASTER BACKDOOR
**Severity: CRITICAL** | **Category: AUTHORIZATION BYPASS**

**Root Cause:**
In `api/_test_mode.py` (lines 81-97):
```python
def get_api_key_auth(request: Request) -> Optional[dict]:
    if is_test_mode(request):
        return {
            "user_id": "service",
            "role": "admin",
            "auth_method": "api_key",
        }
    return None
```
The API key (`etap-platform-secret-2024`) grants **full admin access** to any endpoint that uses `get_api_key_auth()`. This is used by dashboard endpoints as an alternative to JWT authentication.

**Impact:**
- Anyone who knows the API key has full admin privileges
- The key is predictable and documented in `.env`
- Bypasses ALL JWT authentication and authorization
- Effectively a hardcoded backdoor

**Fix:**
- Remove this admin bypass mechanism entirely OR
- Use API key only for service-to-service auth, NEVER grant admin role
- Implement proper service account system with scoped permissions

---

### 🐛 HB-03: API KEY CONFIGURATION LOGS SECRET IN CI/CD OUTPUT
**Severity: HIGH** | **Category: SECURITY / LOG LEAKAGE**

**Root Cause:**
Not directly seen in code, but the `.env` contains `ENGINEERING_SERVICE_API_KEY=etap-platform-secret-2024`. If any CI/CD pipeline or startup script logs the environment, this key is exposed in build logs.

**Impact:**
- CI/CD logs (GitHub Actions, Vercel builds) may capture environment variables
- Engineering Service API key exposed
- External systems can call internal APIs

**Fix:**
Mask the API key in logs using the existing `security/log_redaction.py` module.

---

### 🐛 HB-04: FORGOT-PASSWORD ENDPOINT HAS NO RATE LIMITING PER EMAIL
**Severity: MEDIUM** | **Category: ABUSE / SPAM**

**Root Cause:**
In `api/auth.py` (lines 926-997), the `/forgot-password` endpoint generates a reset token and sends an email. There is no rate limiting per email address — an attacker can bombard a user's email inbox with password reset emails.

**Impact:**
- Email spam attack against users
- Possible SMTP rate limiting from Resend (leading to legitimate emails being blocked)
- User annoyance and potential reputational damage

**Fix:**
Add per-email rate limiting for forgot-password (e.g., 1 request per 60 seconds).

---

### 🐛 HB-05: ENGINEERING SERVICE API KEY IS A PLAINTEXT STRING `etap-platform-secret-2024`
**Severity: HIGH** | **Category: WEAK SECRET**

**Root Cause:**
The `.env` file defines `ENGINEERING_SERVICE_API_KEY=etap-platform-secret-2024`. This is a weak, predictable string with no entropy. If this is used in production, it provides trivial bypass of API authentication.

**Impact:**
- Anyone who knows the pattern "etap-platform-secret-YYYY" can access internal APIs
- The key is visible in the .env file which exists on disk
- If this same pattern is used elsewhere, those systems are also vulnerable

**Fix:**
Generate a cryptographically random API key using `openssl rand -hex 32`, rotate immediately.

---

### 🐛 HB-06: CORS ALLOWS ALL ORIGINS ON HF SPACE
**Severity: MEDIUM** | **Category: MISCONFIGURATION**

**Root Cause:**
In `hf-space/app.py` (lines 195-206):
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://huggingface.co",
        "https://*.hf.space",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
The wildcard `*.hf.space` allows any HF Space (including attacker-controlled ones) to make CORS requests with credentials.

**Impact:**
- Malicious HF Space can make authenticated API calls from victim's browser
- Session hijacking possible if combined with XSS on any HF Space

**Fix:**
Pin exact origins: `"https://ahmdelbaz28-ahmedetap-platform.hf.space"`.

---

### 🐛 HB-07: CSP HEADERS USE `unsafe-inline` AND `unsafe-eval`
**Severity: MEDIUM** | **Category: SECURITY / XSS**

**Root Cause:**
In `hf-space/app.py` (lines 235-242):
```python
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
    ...
)
```
The CSP allows `unsafe-inline` and `unsafe-eval`, which defeats the purpose of CSP for XSS mitigation.

**Impact:**
- Any XSS vulnerability in the app can execute arbitrary JavaScript
- The CSP provides minimal protection against injection attacks

**Fix:**
Implement nonce-based or hash-based CSP for inline scripts. Remove `unsafe-eval` if possible.

---

### 🐛 HB-08: SYNTHETIC SCADA DATA RETURNED IN PRODUCTION MODE
**Severity: LOW** | **Category: DATA ACCURACY**

**Root Cause:**
In `routes.py` (line 655):
```python
"source": "synthetic" if os.environ.get("ENVIRONMENT") != "production" else "zenon",
```
AND in `hf-space/app.py` (line 902):
```python
"source": "hf-space-synthetic",
```
On HF Space, the SCADA endpoint ALWAYS returns synthetic data. The production env check in routes.py may report "zenon" as source even when no real Zenon backend is connected.

**Impact:**
- Users may believe they are viewing real SCADA data when it's synthetic
- False confidence in system state
- Incorrect operational decisions based on fake telemetry

**Fix:**
Always report `"source": "synthetic"` unless the real Zenon backend is actually connected and verified via health check.

---

### 🐛 HB-09: DUAL AUTHENTICATION SYSTEMS — CONFIGURATION RISK
**Severity: HIGH** | **Category: AUTHORIZATION BYPASS**

**Root Cause:**
There are TWO independent authentication systems:
1. `api/auth.py` + `api/dependencies.py` — Used by FastAPI route handlers (JWT + bcrypt)
2. `security/security_framework.py` (AuthenticationManager) — Standalone JWT system with SEPARATE secret key, token format, and user store

These systems have:
- Different JWT payload schemas (`api/auth.py` uses `sub`/`role`/`type`/`jti`, `security_framework.py` uses `user_id`/`username`/`role`)
- Different secret key derivation logic
- Different token expiration handling
- Completely separate user stores (SQLAlchemy vs in-memory dict)

**Impact:**
- A token issued by one system is NOT valid for the other
- Confusion about which auth system protects which endpoint
- If a developer adds a new endpoint using the wrong auth system, auth is bypassed
- The `security/security_framework.py` `AuthenticationManager` stores users in memory → no persistence across restarts

**Fix:**
Either:
1. Remove `security/security_framework.py` AuthenticationManager entirely (it's unused by actual routes)
2. Or refactor to use a single auth system throughout

---

### 🐛 HB-10: DOCKER-COMPOSE EXPOSES GRAFANA WITHOUT AUTH BY DEFAULT
**Severity: MEDIUM** | **Category: MISCONFIGURATION**

**Root Cause:**
In `docker-compose.yml` (lines 90-101):
```yaml
grafana:
    image: grafana/grafana-enterprise
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:?GRAFANA_ADMIN_PASSWORD is required}
```
Grafana is exposed on port 3000 without any network restriction. The admin password is required but:
- There's no documentation of what the default should be
- The .env.example doesn't include GRAFANA_ADMIN_PASSWORD
- If deployed without setting this env var, docker-compose fails with "GRAFANA_ADMIN_PASSWORD is required" error message that LEAKS the env var name

**Fix:**
Add GRAFANA_ADMIN_PASSWORD to .env.example with a strong default + documentation.

---

### 🐛 HB-11: CELERY WORKER DEPENDS ON `engineering-service` SERVICE — CIRCULAR LOGIC
**Severity: LOW** | **Category: STARTUP ORDER**

**Root Cause:**
In `docker-compose.yml` (lines 42-47):
```yaml
depends_on:
    redis:
        condition: service_healthy
    engineering-service:
        condition: service_started
```
Celery worker depends on `engineering-service: service_started`, but `engineering-service` doesn't need to be running for Celery to work. Celery only needs Redis (broker) and the code.

**Impact:**
- Slower startup sequence (waits for engineering-service to start)
- If engineering-service crashes, Celery is also stopped unnecessarily
- Single point of failure for background task processing

**Fix:**
Celery should only depend on Redis, not the API service.

---

### 🐛 HB-12: REDIS PASSWORD LEAKED IN DOCKER HEALTHCHECK
**Severity: HIGH** | **Category: SECRET IN PROCESS LIST**

**Root Cause:**
In `docker-compose.yml` (line 64):
```python
healthcheck:
    test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
```
The Redis password is passed as a command-line argument to `redis-cli -a ${REDIS_PASSWORD}`. This makes the password visible in:
- `docker ps` output (process list)
- Container health check logs
- Process monitoring tools

**Fix:**
Use `redis-cli ping` without password (Redis checks auth automatically for locally-connected clients) or use the `REDISCLI_AUTH` environment variable.