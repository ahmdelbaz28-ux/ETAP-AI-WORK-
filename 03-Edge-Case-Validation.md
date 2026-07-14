# 03 — EDGE CASE VALIDATION
## Boundary Conditions and Extreme Scenarios

### ⚠️ EC-01: EMPTY DATABASE — FIRST-TIME STARTUP
**Status: AT RISK**

The `init_db()` function creates all tables at startup. However, if the database connection fails during `init_db()`, the fallback to SQLite creates tables in a transient location. On HF Space:
- First request to `/api/v1/auth/register` triggers table creation (see `hf-space/app.py` lines 101-105)
- If PostgreSQL is unreachable, data goes to `/tmp/data/etap_platform_fallback.db`
- **Data is lost on restart**

**Attack Scenario:**
If an attacker can cause a database outage (e.g., by exhausting Supabase connections), any data created during the outage is silently lost when the system restarts.

---

### ⚠️ EC-02: VERY LARGE STUDY REQUEST PAYLOAD
**Status: AT RISK**

In `routes.py` (line 148):
```python
_MAX_BODY_SIZE = int(os.environ.get("ENGINEERING_SERVICE_MAX_BODY_SIZE", "1_048_576"))
```
The default max body size is **1MB** (1,048,576 bytes). Power system studies with large network models will easily exceed this limit.

**Impact:**
- Any study with realistic power system data (>1MB) returns 413 Payload Too Large
- No way for the client to know the limit until hitting it
- The error response is a JSONResponse with `{"detail": "Request body too large"}`

**Recommendation:**
Increase the default to at least 50MB for study endpoints, or make it configurable with a higher default. Properly communicate the limit via response headers or documentation.

---

### ⚠️ EC-03: JWT WITH 0-CHARACTER USER ID
**Status: NOT HANDLED**

In `api/auth.py` (line 441):
```python
def _create_access_token(user_id: str, role: str) -> str:
```
There is no validation of `user_id` length. If a user somehow registers with an empty string username (the validation pattern `^[a-zA-Z0-9_-]+$` allows min 1 char, but min_length=3), the JWT will contain `sub=""`.

In `api/dependencies.py` (line 170-177):
```python
user_id: Optional[str] = payload.get("sub")
token_type: Optional[str] = payload.get("type")
if user_id is None or token_type != "access":
    raise HTTPException(...)
```
This checks for `None` but NOT for empty string `""`. An empty `sub` would bypass this check, and the DB query `select(User).where(User.id == "")` might return unexpected results.

---

### ⚠️ EC-04: EMAIL CASE SENSITIVITY BUG
**Status: CONFIRMED BUG**

In `api/auth.py` (lines 534-547):
```python
existing = await db.execute(select(User).where(User.email == body.email))
```
Emails are stored and queried as-is, without normalization to lowercase. This means:
- `User@Example.com` and `user@example.com` are considered **different emails**
- A user can register with mixed-case email, then authenticate with different case (login matches either username or email)
- **Email uniqueness is case-sensitive**, which violates RFC 5321 (local-part IS case-sensitive but mailbox names are NOT case-sensitive in practice; domain part is always case-insensitive)

**Attack Scenario:**
An attacker registers `ADMIN@example.com` while the real admin has `admin@example.com`. Since PostgreSQL string comparison is case-sensitive by default for `VARCHAR` with no explicit collation, both accounts can exist.

---

### ⚠️ EC-05: PASSWORD RESET TOKEN WITH SPECIAL CHARACTERS IN URL
**Status: FRAGILE**

In `api/auth.py` (lines 958-961):
```python
reset_link = (
    f"{_os.getenv('EMAIL_APP_URL', 'http://localhost:3000')}"
    f"/reset-password?token={reset_token}"
)
```
The reset token is inserted into a URL without URL-encoding. If the token contains characters like `&`, `?`, `#`, `+` (which `uuid.uuid4()` does NOT produce, but future changes might), the URL would break.

**Risk:** Low currently (uuid4 hex chars only), but fragile for future changes.

---

### ⚠️ EC-06: RATE LIMITER FALLBACK LOST ON PROCESS RESTART
**Status: CONFIRMED**

In `routes.py` (lines 177-179):
```python
_rate_limit_fallback_store: dict[str, list[float]] = {}
```
This is an in-memory Python dict. On any process restart (deployment, crash, scaling event):
- All rate limit counters are reset to zero
- An attacker who was being throttled gets a fresh window
- This is expected behavior for per-instance rate limiting, but exacerbates the Redis availability risk documented in KR-06

---

### ⚠️ EC-07: CLIENT_ID REVEALED IN VERIFIED RESPONSE HEADER
**Status: INFORMATION LEAK**

`.vercel/project.json` contains:
```json
{
  "projectId": "prj_WucHqc3lQDwYe0i3ykgWz7UR5E3I",
  "orgId": "team_eeEYqzXI8zkrTo62cUOTMVmS"
}
```
This file is tracked in git, exposing the Vercel project and organization IDs. While not high severity alone, these IDs can be used for targeted attacks against Vercel deployments.

---

### ⚠️ EC-08: EMAIL WEBHOOKS WITHOUT HMAC VERIFICATION
**Status: UNVERIFIED**

The `EMAIL_WEBHOOK_SECRET` is set to `your-webhook-hmac-secret` (placeholder) in `.env`. If the email webhook endpoint (`api/email_webhooks.py`) doesn't verify incoming webhook signatures, an attacker could:
- Send fake webhook events to the platform
- Trigger fake email delivery/complaint/bounce events
- Potentially cause downstream processing errors

**Fix:**
Verify the email webhook payload signature using the configured secret before processing.

---

### ⚠️ EC-09: CONCURRENT REGISTRATION — RACE CONDITION
**Status: THEORETICAL RISK**

In `api/auth.py` (lines 534-555):
```python
# Check username uniqueness
existing = await db.execute(select(User).where(User.username == body.username))
if existing.scalar_one_or_none() is not None:
    raise HTTPException(...)

# Check email uniqueness
existing = await db.execute(select(User).where(User.email == body.email))
if existing.scalar_one_or_none() is not None:
    raise HTTPException(...)

user = User(...)
db.add(user)
await db.flush()
```
Between the uniqueness check and the flush, another request could register the same username/email. PostgreSQL's unique constraints will catch the duplicate at commit time, but the exception will surface as a 500 Internal Server Error instead of a proper 409 Conflict.

**Fix:**
Add proper exception handling for integrity errors, or use `INSERT ... ON CONFLICT` / `SAVEPOINT` patterns.