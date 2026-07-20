# 01 — RELEASE KILLERS
## Zero-Defect Production Validation Report

### 🔴 KR-01: LIVE PRODUCTION SECRETS EXPOSED ON DISK
**Severity: CRITICAL** | **Impact: COMPLETE SYSTEM COMPROMISE**

**Root Cause:**
The `.env` file containing 20+ real production credentials is present at the repository root. While listed in `.gitignore`, the file exists on disk at `c:\Users\EWS-01\Desktop\Ahmedetap\.env`.

**Exposed Credentials:**
| Token | Type | Impact |
|-------|------|--------|
| `HF_TOKEN` | Hugging Face API | Full access to HF Spaces, model repos, datasets |
| `GITHUB_TOKEN` | GitHub PAT (classic) | Full repo access, CI/CD, secrets read |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Service Role | Full database access, bypasses RLS |
| `NEO4J_PASSWORD` | Neo4j Database | Graph database access with all topology data |
| `CLOUDFLARE_ORIGIN_SECRET` | CDN Origin Secret | Bypass CDN, direct origin access |
| `VERCEL_TOKEN` (x2) | Vercel Deployment | Full deployment control, env vars access |
| `LANGFUSE_SECRET_KEY` | LLM Observability | Access to all prompt/LLM traces |
| `RESEND_API_KEY` | Email Service | Send emails as the platform |
| `NAVRO_API_TOKEN` | AI Service | Access to external AI service |
| `SONAR_TOKEN` | SonarCloud | Code quality platform access |
| `ENGINEERING_SERVICE_API_KEY` | Internal API | Backend API access without auth |
| `DAYTONA_TOKEN` | VPS Access | Infrastructure access |
| `CODESANDBOX_TOKEN` | Dev Environment | Development environment access |
| `SUPABASE_PAT` | Personal Access Token | Full Supabase account access |

**Production Impact:**
- Any malicious process on the machine can exfiltrate all credentials
- If any of these tokens are committed to git history, they are permanently compromised
- The GitHub PAT (`github_pat_...`) has full repo access — attacker can push malicious code

**Fix Required:**
1. Rotate EVERY exposed credential immediately
2. Remove `.env` from the repository entirely
3. Add `.env` to `.gitignore` (already done, but verify via `git rm --cached .env`)
4. Use environment variables exclusively (HF Space Secrets, GitHub Secrets, etc.)
5. Scan git history for any accidental .env commits using `git filter-branch`

---

### 🔴 KR-02: JWT SECRET KEY FALLS BACK TO WEAK DETERMINISTIC VALUE
**Severity: CRITICAL** | **Impact: FORGED AUTHENTICATION TOKENS**

**Root Cause:**
In `api/dependencies.py` (lines 33-57), if `JWT_SECRET_KEY` is not set in the environment:
```python
_hostname = os.getenv("HOSTNAME", os.getenv("COMPUTERNAME", "unknown"))
_seed = f"etap-dev-{_hostname}"
_jwt_key = _hashlib.sha256(_seed.encode()).hexdigest()
```
The `.env` file contains `JWT_SECRET_KEY=your-jwt-secret-key-minimum-32-characters` which is a PLACEHOLDER, not a real secret. If this placeholder is used literally in production, the JWT key is well-known and publicly documented in the `.env` file.

**Production Impact:**
- Attacker can forge valid JWT tokens for ANY user, including admin
- Can bypass all authentication and authorization
- Token verification uses HS256 with known key → trivial to forge

**Fix Required:**
1. Set a cryptographically secure `JWT_SECRET_KEY` via environment variable (NOT in .env file)
2. Use: `python3 -c "import secrets; print(secrets.token_hex(32))"`
3. Inject via HF Space Secrets, not .env file

---

### 🔴 KR-03: PASSWORD RESET TOKENS LEAKED IN API RESPONSE
**Severity: HIGH** | **Impact: ACCOUNT TAKEOVER**

**Root Cause:**
In `api/auth.py` (lines 987-994):
```python
if os.getenv("AUTH_RETURN_RESET_TOKEN", "true").lower() == "true":
    return {
        "message": "If the email exists, a reset token has been sent",
        "reset_token": reset_token,
    }
```
By default, password reset tokens are returned directly in the API response. The comment says this is "for testability" but this is a critical vulnerability in production.

**Production Impact:**
- Any intermediary (proxy, log aggregator, API gateway) logging response bodies captures reset tokens
- If the frontend logs API responses, tokens are exposed in browser dev tools
- Account takeover is trivial with a valid reset token

**Fix Required:**
1. Set `AUTH_RETURN_RESET_TOKEN=false` in production
2. Reset tokens should NEVER be returned in API responses — only sent via email
3. Update test suite to not depend on this behavior

---

### 🔴 KR-04: DATABASE AUTO-FALLBACK TO SQLITE = SILENT DATA LOSS
**Severity: HIGH** | **Impact: DATA LOSS, INVISIBLE DATA ACROSS REPLICAS**

**Root Cause:**
In `api/database.py` (lines 297-322):
```python
# Fall back to SQLite — make sure /tmp/data exists, then rebind.
_fallback_dir = os.path.dirname(_FALLBACK_SQLITE_URL.replace("sqlite+aiosqlite:///", ""))
```
When PostgreSQL is unreachable, the system silently falls back to SQLite at `/tmp/data/etap_platform_fallback.db`. On HF Space and containerized environments:
- `/tmp` is wiped on every restart → **all data lost**
- Multiple replicas each have their own SQLite → **data created on one replica is invisible to others**
- The fallback is logged but there is NO alerting mechanism

**Production Impact:**
- If Supabase pauses or network partitions, users can register and create data that disappears
- Study results, user accounts, projects lost on next deployment
- Silent degradation — no one may notice until data is gone

**Fix Required:**
1. Remove the automatic SQLite fallback in production — fail hard if PostgreSQL is down
2. Implement proper alerting when database is unreachable
3. Add a health check that reports "degraded" when fallback is active
4. Document the fallback condition prominently

---

### 🔴 KR-05: TOKEN BLACKLISTING SILENTLY FAILS WITHOUT REDIS
**Severity: HIGH** | **Impact: INVALID LOGOUT, TOKEN REUSE**

**Root Cause:**
In `api/auth.py` (lines 129-143):
```python
async def _blacklist_token(jti: str, ttl_seconds: Optional[int] = None) -> None:
    r = _get_redis_client()
    if r is None:
        return  # fallback: silently no-blacklist if REDIS_URL not configured
```
When Redis is not configured (or unreachable), token blacklisting is silently skipped. Logout does NOT invalidate refresh tokens.

**Production Impact:**
- Logged-out users can still use their refresh tokens to get new access tokens
- Session revocation is completely broken without Redis
- If a device is stolen and the user logs out remotely, the stolen device's tokens remain valid

**Fix Required:**
1. Implement in-memory token blacklist fallback (even if not persistent across restarts)
2. Add logging warning when Redis is unavailable
3. Consider adding a `/logout/all` endpoint that rotates the user's password hash version

---

### 🔴 KR-06: RATE LIMITING BYPASS WHEN REDIS IS DOWN
**Severity: MEDIUM** | **Impact: BRUTE FORCE ATTACK VULNERABILITY**

**Root Cause:**
In `api/auth.py` (lines 485-488):
```python
except (OSError, redis_async.RedisError):
    # Redis is configured but unreachable — fall through to
    # in-memory rate limiting so login still works.
    pass
```
When Redis fails, login rate limiting falls back to per-instance in-memory storage. With multiple HF Space replicas, each replica has its own counter, effectively multiplying the allowed attempts.

**Production Impact:**
- With 3 replicas, an attacker gets 15 attempts per 15 minutes instead of 5
- Brute force attacks become significantly easier during Redis outages
- On HF Space with `REDIS_URL=""` (empty), the in-memory fallback is ALWAYS used

**Fix Required:**
1. Ensure Redis is configured and available in production
2. Increase the in-memory fallback window or reduce max attempts when Redis is unavailable
3. Add monitoring/alerting when Redis is unreachable

---

### 🔴 KR-07: API KEY BACKDOOR — FULL ADMIN ACCESS VIA X-API-Key
**Severity: CRITICAL** | **Impact: COMPLETE AUTHENTICATION BYPASS**

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
The `ENGINEERING_SERVICE_API_KEY` (value: `etap-platform-secret-2024`) grants **full admin privileges** when passed as `X-API-Key` header. This is used by dashboard endpoints as an alternative authentication mechanism:
```python
from api._test_mode import get_api_key_auth
current_user = get_api_key_auth(request) or get_current_user(request)
```

**Production Impact:**
- Anyone who knows the API key has full admin access to protected endpoints
- The key is documented in `.env` and is a predictable pattern
- Bypasses ALL JWT authentication and RBAC
- Effectively a hardcoded backdoor in the authentication system

**Fix Required:**
1. Remove `get_api_key_auth()` entirely — it should never grant admin role
2. If API key auth is needed, implement a proper service account system with scoped permissions
3. Never grant admin role via API key