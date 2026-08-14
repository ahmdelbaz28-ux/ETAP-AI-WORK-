# Security Requirements — AhmedETAP Platform

Derived from a STRIDE-based threat analysis of the codebase (API layer, agent runtime, backend/infra).
Generated with the `security-requirement-extraction` skill (Template 1: Security Requirement Model).

**Version:** 1.0
**Scope:** api/ · backend/ · core/ · services/ · agents/ · security/ · acp_runtime/ · facp_distributed/ · docker-compose.yml
**Method:** STRIDE threat model → requirement extraction (traceability + acceptance criteria + test cases + compliance mapping)
**Status of each finding:** verified by code reading; CRITICAL findings additionally verified by live execution.

---

## 1. Threat Model (STRIDE Register)

| ID | STRIDE | Severity | Threat | Evidence |
|----|--------|----------|--------|----------|
| T-01 | Tampering / Elevation | **CRITICAL** | Python sandbox escape → RCE. `import numpy.f2py as nf; nf.__dict__['os']` exposes `os.system`. Pre-scan (`security/secure_executor.py:91-153`) blocks `os.` and `__builtins__` but not `__dict__` subscripting; the module freeze runs only in the parent and is discarded. **Verified live.** | `security/secure_executor.py:65-77,383-390,447-452` |
| T-02 | Spoofing / Tampering / Info Disclosure | **CRITICAL** | Hardcoded secrets in `docker-compose.yml`: JWT secret `test-secret-32-bytes-long-aaaa-bbbb` (passes the ≥32-byte gate at `api/dependencies.py:36-42`), API key `etap_dev_api_key_1234567890`, Redis/Postgres passwords, and the sample Fernet key from public docs. Any deployment from compose ships with attacker-known credentials. **Verified.** | `docker-compose.yml:12-21` |
| T-03 | Information Disclosure / Elevation | **CRITICAL** | Cross-tenant RLS isolation broken. `before_cursor_execute` marks each pooled DBAPI connection in a process-wide `WeakSet` after the first `SET app.current_tenant_id` and never re-sets it (and never resets to empty). Connection reuse across requests/tenants executes tenant B's queries under tenant A's RLS variable. **Verified — no reset exists.** | `backend/request_context.py:290-301` |
| T-04 | Elevation of Privilege | HIGH | Life-safety admin endpoints (`/admin/cua/kill-switch/*`, `/admin/cua/rollback`, `/admin/cua/audit-log`, `/api/v1/audit/verify`) gated only by the single shared API key — no role/admin separation. | `api/routes.py:906,1003,1027,1074,1100` |
| T-05 | Spoofing / Info Disclosure | HIGH | ACP runtime unauthenticated by default (`auth_validator=None` unless `ACP_AUTH_SECRET` set) and the HMAC bearer token rides in `trace_id`, which is written verbatim into logs/spans/audit files. | `acp_runtime/acp/cli.py:211-226`, `acp_runtime/router/router.py:192-195`, `acp_runtime/observability/*` |
| T-06 | Elevation / Spoofing | HIGH | `ENGINEERING_SERVICE_AUTH_DISABLED` / `AUTH_DISABLED` grants **anonymous ADMIN** (`role=_Role.ADMIN`) per-request with no environment guard; the ETAP app has no startup fail-safe equivalent to `api/routes.py:123-146`. | `backend/security_middleware.py:397-403` |
| T-07 | Tampering / Elevation | HIGH | PowerShell executor newline statement-injection bypass: `Get-Service\r\nnet user attacker P@ssw0rd /add` — newlines are flattened by normalization before scanning, cmdlet regex only matches `Verb-Noun`, and the command is written verbatim to the `.ps1`. | `security/secure_powershell_executor.py:173-246,304`, `security/security_framework.py:595-634` |
| T-08 | Information Disclosure | HIGH | Raw exception strings echoed to clients (`detail=f"System spec error: {ve}"`, `errors.append(str(e))`) leak file paths and engine internals; FastAPI `debug=(_ENV == "development")` defaults to dev when `ENVIRONMENT` is unset. | `services/study_service.py:434,475`, `api/routes.py:84-93` |
| T-09 | Information Disclosure (IDOR) | HIGH | `GET /api/v1/studies/task_status/{task_id}` returns full study results for any task ID to any key holder — no ownership/tenant scoping; fallback IDs are predictable (`task_{int(time.time())}`). | `api/routes.py:460-493` |
| T-10 | Information Disclosure | HIGH | JWT access tokens passed in WebSocket query strings (`ws://.../ws/scada?token=<jwt>`) — captured by proxy/access logs, browser history, Referer. | `api/websocket.py:367-398` |
| T-11 | Spoofing / Integrity | HIGH | `/ws/notifications` handler omits token-blacklist, user-existence, and `is_active` checks (unlike its twin) and echoes raw client data back over the socket. | `backend/app.py:767-797` |
| T-12 | Authentication bypass | HIGH | `verify_api_key` open-by-default: `if not expected_key: return` — the whole surface is open when `HF_API_KEY` is unset; valid access JWTs skip the key check with no blacklist validation here. | `api/shared_handlers.py:362-406` |
| T-13 | Denial of Service | MEDIUM | Body-size limit bypassed via chunked `Transfer-Encoding` (no `content-length` → unbounded buffering). | `api/routes.py:191-204` |
| T-14 | Denial of Service | MEDIUM | Rate limiter fails open: any Redis error returns `True` (allow), and identity falls back to `request.client.host` unless trusted proxies configured. | `api/routes.py:295-297,351` |
| T-15 | Spoofing | MEDIUM | No Origin validation on WebSocket handshakes → cross-site WebSocket hijacking / DNS-rebinding. | `api/websocket.py:353-398` |
| T-16 | Elevation of Privilege | MEDIUM | Parent process `pickle.load`s child result files in `facp_distributed` isolation boundary; exec path built via f-string. | `facp_distributed/security/isolation.py:58-122` |
| T-17 | Spoofing | MEDIUM | CSRF origin check defaults to a Host-derived same-origin comparison (DNS-rebinding-sensitive) when `CSRF_ALLOWED_ORIGINS` unset. | `api/auth.py:554-610` |
| T-18 | Denial of Service | MEDIUM | Sync CPU-bound native studies (`_run_native_study`) execute directly on the event loop; blocks health checks/WS/auth under a few concurrent studies. | `api/studies.py:628,703` |
| T-19 | Tampering | MEDIUM | Report generation writes to user-supplied `output_path` from task parameters without `validate_file_path`. | `agents/orchestrator.py:1327,1477` |
| T-20 | Information Disclosure | MEDIUM | LLM provider key (`x-active-key`) accepted in plaintext headers and whitelisted in CORS `allow_headers`; no TLS-only enforcement. | `api/routes.py:318-321,617-640` |
| T-21 | Tampering | LOW | CSV formula injection in audit-log export: `details`/`user` written with no sanitization of leading `= + - @`. | `api/audit_logs.py:659-676` |
| T-22 | Information Disclosure | LOW | Reflective error details echoing user input back in messages. | `api/audit_logs.py:546,556,784` |
| T-23 | Elevation (traversal) | LOW | `etap_project_path` unvalidated at the service layer (currently mitigated downstream by `etap_com.py` containment checks). | `services/study_service.py:409-421` |
| T-24 | Info Disclosure (defense-in-depth) | LOW | No CSP / no default HSTS on the engineering API; only `X-Content-Type-Options`/`X-Frame-Options`/`Referrer-Policy`. | `api/routes.py:649-665` |
| T-25 | Authentication | LOW | `backend/config.py` reads `JWT_SECRET_KEY` with empty default and only warns on validation failure. | `backend/config.py:91,112-113` |

### Verified-clean areas
- No SQL injection (only bound parameters); no `eval`/`exec`/unsafe `yaml.load` in service code.
- No `allow_origins=["*"]` with credentials; CORS fails restrictive in both apps.
- Constant-time key comparison (`hmac.compare_digest`) everywhere.
- `TRUSTED_PROXY_HOPS` defaults to 0 (X-Forwarded-For not trusted by default).
- No hardcoded secrets in production Python code (grep hits are test fixtures only).
- nginx: TLS 1.2/1.3 only, `server_tokens off`, rate limiting.

---

## 2. Security Requirements

Priorities: CRITICAL = 1, HIGH = 2, MEDIUM = 3, LOW = 4.
Requirement types: F = Functional, NF = Non-functional, C = Constraint.

### 2.1 Sandbox & Code Execution (Domain: input_validation)

**SR-001 — Sandbox must prevent module-`__dict__` escapes (F, CRITICAL)**
As a security-conscious system, I need to prevent sandboxed Python code from reaching the OS object model, so that generated study code can never execute arbitrary commands.

- **Threat refs:** T-01
- **Rationale:** `import numpy.f2py as nf; nf.__dict__['os']` was verified live to yield `os.system` (exit 0, marker file written) — the sandbox is bypassable.
- **Acceptance criteria:**
  - [ ] Pre-scan and `FORBIDDEN_ATTRS` block `__dict__` attribute reads and subscripting of module objects (`mod['name']`)
  - [ ] Module attribute freezing executes inside the sandboxed subprocess, not only in the parent
  - [ ] Escape payloads via numpy/scipy/math module `__dict__` are rejected with a "sandbox escape" error
  - [ ] A regression test asserts `numpy.f2py.__dict__['os']` cannot execute
- **Test cases:**
  1. Test: `import numpy.f2py as nf; nf.__dict__['os'].system('cmd')` is rejected
  2. Test: `scipy.__dict__['sys']`-style payloads are rejected
  3. Test: freeze bypass — child process cannot import an unfrozen `os`
  4. Test: sandboxed code cannot write outside the temp workdir
- **Compliance refs:** OWASP ASVS V5 (Input Validation); NIST CSF PR.AC / PR.PT

**SR-002 — PowerShell executor must reject multi-statement input (F, CRITICAL)**
As a security-conscious system, I need to treat newline-separated commands as distinct statements, so that `Get-Service\r\nnet user attacker P@ssw0rd /add` cannot slip past the dangerous-pattern scan.

- **Threat refs:** T-07
- **Rationale:** normalization `" ".join(command.split())` erases newlines before scanning; the first-token allowlist and `Verb-Noun` regex never see the injected statement.
- **Acceptance criteria:**
  - [ ] Input is split into statements (newline/`;`/`|`) *before* normalization
  - [ ] Each statement's first token is validated against the allowlist
  - [ ] Bare executables without a whitelisted cmdlet match (`net`, `whoami`, `curl`, …) are rejected
  - [ ] Regression tests for `\r\n`, `\n`, and `;`-joined injection
- **Test cases:**
  1. Test: `Get-Service\r\nnet user attacker P@ssw0rd /add` is rejected
  2. Test: `whoami` alone is rejected
  3. Test: multi-cmdlet pipe `Get-Process | Stop-Process` is rejected
- **Compliance refs:** OWASP ASVS V5; NIST CSF PR.AC-1

### 2.2 Authentication (Domain: authentication)

**SR-003 — Admin/life-safety endpoints require role-based auth (F, CRITICAL)**
As a system administrator, I need admin CUA and audit endpoints protected by `role=admin` JWTs, so that a leaked shared API key cannot flip kill switches or read the tamper-evident audit chain.

- **Threat refs:** T-04
- **Acceptance criteria:**
  - [ ] `/admin/cua/*` and `/api/v1/audit/verify` require `Depends(require_role("admin"))`
  - [ ] A valid API key alone returns 403 on admin endpoints
  - [ ] Role change endpoints are admin-only and logged
- **Test cases:**
  1. Test: viewer JWT + API key → 403 on kill-switch
  2. Test: admin JWT → 200 on kill-switch
  3. Test: API key only → 403
- **Compliance refs:** OWASP ASVS V2.1/V4; NIST CSF PR.AC-4; ISO 27001 A.9.2

**SR-004 — WebSocket auth token must not travel in the query string (C, HIGH)**
As a security-conscious system, I need to transmit WebSocket credentials via a first-party header, so that bearer tokens are not captured in access logs, proxy logs, or browser history.

- **Threat refs:** T-10
- **Acceptance criteria:**
  - [ ] SCADA/notification WS handshakes read tokens from `Authorization` or a `Sec-WebSocket-Protocol` subprotocol, never `query_params`
  - [ ] Requests presenting `?token=` are rejected
  - [ ] No WS endpoint logs the token
- **Test cases:**
  1. Test: WS handshake with `?token=<jwt>` is rejected
  2. Test: WS handshake with `Authorization: Bearer <jwt>` succeeds
  3. Test: access logs contain no token substring
- **Compliance refs:** OWASP ASVS V3; NIST CSF PR.DS-2

**SR-005 — WebSocket handshakes validate Origin (F, HIGH)**
As a security-conscious system, I need to reject cross-origin WebSocket handshakes, so that a malicious webpage cannot drive a logged-in socket (CSWSH/DNS-rebinding).

- **Threat refs:** T-15, T-11
- **Acceptance criteria:**
  - [ ] All WS endpoints validate `Origin` against the configured allowlist before upgrade
  - [ ] Missing/mismatched Origin → close code 1008
  - [ ] `/ws/notifications` runs the identical auth pipeline (blacklist + user exists + `is_active`) as the SCADA handler
  - [ ] Server never echoes raw client payloads back (pong payload is fixed)
- **Test cases:**
  1. Test: WS with forged Origin is rejected
  2. Test: `/ws/notifications` with revoked-token JWT is rejected
  3. Test: `/ws/notifications` pong returns a constant payload
- **Compliance refs:** OWASP ASVS V3.1/V12; NIST CSF PR.AC-5

**SR-006 — Auth-disable switches fail closed in production (C, HIGH)**
As a security-conscious system, I need `ENGINEERING_SERVICE_AUTH_DISABLED` / `AUTH_DISABLED` to be inert in production, so that a misconfigured environment can never grant anonymous admin access.

- **Threat refs:** T-06, T-12
- **Acceptance criteria:**
  - [ ] Both apps refuse to start in production/staging when auth is disabled (mirror `api/routes.py:123-146` guard in `backend/app.py`)
  - [ ] No code path assigns `_Role.ADMIN` to an unauthenticated request
  - [ ] `verify_api_key` fails closed when the expected key is unset (no `if not expected_key: return`)
- **Test cases:**
  1. Test: `AUTH_DISABLED=true` + `ENVIRONMENT=production` → startup failure
  2. Test: anonymous request with `ENGINEERING_SERVICE_AUTH_DISABLED=true` in prod → 401
  3. Test: unset `HF_API_KEY` → 401, not open
- **Compliance refs:** OWASP ASVS V2.1; NIST CSF PR.AC-1

**SR-007 — ACP runtime requires transport authentication by default (F, HIGH)**
As a security-conscious system, I need ACP transports (WebSocket/UDS) to require an HMAC secret in any real deployment, so that arbitrary processes cannot drive the router.

- **Threat refs:** T-05
- **Acceptance criteria:**
  - [ ] Startup refuses to bind transport when `ACP_AUTH_SECRET` is unset in non-dev environments
  - [ ] WS transport validates `Origin` before upgrade
  - [ ] The auth token is never logged in `trace_id`, span JSONL, or audit NDJSON (redact or separate fields)
- **Test cases:**
  1. Test: transport with no secret configured → startup error (prod)
  2. Test: token-bearing `trace_id` is redacted in all sinks
  3. Test: WS with foreign Origin is rejected
- **Compliance refs:** NIST CSF PR.AC; ISO 27001 A.9.1

### 2.3 Authorization & Tenant Isolation (Domain: authorization)

**SR-008 — RLS session variable must be reset per request (F, CRITICAL)**
As a data owner, I need every pooled DB connection to run under the correct tenant's RLS variable, so that tenant B can never observe tenant A's rows through connection reuse.

- **Threat refs:** T-03
- **Acceptance criteria:**
  - [ ] `before_cursor_execute` re-sets `app.current_tenant_id` on every request (no process-wide "already set" skip)
  - [ ] The RLS variable is reset (`SET app.current_tenant_id = ''`) when a request ends / on connection checkout
  - [ ] A pooled-connection regression test asserts tenant B sees zero tenant-A rows after tenant A reuses the same connection
  - [ ] Application-layer tenant filtering remains active as defense-in-depth
- **Test cases:**
  1. Test: sequential tenant-A → tenant-B requests on the same pooled connection leak nothing
  2. Test: anonymous request after tenant request sees no rows
  3. Test: `current_setting('app.current_tenant_id')` is empty between requests
- **Compliance refs:** ISO 27001 A.9.1/A.10; NIST CSF PR.AC-4

**SR-009 — Study task results are ownership-scoped (F, HIGH)**
As a data owner, I need to fetch task results only for my own studies, so that other users/tenants cannot harvest study output via predictable task IDs.

- **Threat refs:** T-09
- **Acceptance criteria:**
  - [ ] Task IDs are unpredictable (UUID, not `task_{int(time.time())}`)
  - [ ] `task_status/{task_id}` verifies the requester's identity/tenant owns the task
  - [ ] Cross-tenant/cross-user task lookups return 404
- **Test cases:**
  1. Test: user B fetching user A's task ID → 404
  2. Test: forged/unpredictable IDs cannot be enumerated
  3. Test: task ID format contains no timestamp
- **Compliance refs:** OWASP ASVS V4.1 (IDOR); NIST CSF PR.AC-4

### 2.4 Data Protection & Secrets (Domain: cryptography / data_protection)

**SR-010 — No hardcoded or sample secrets in deployment configs (C, CRITICAL)**
As a security-conscious system, I need all secrets injected at deploy time, so that a public repository cannot contain working JWT/API/Fernet keys.

- **Threat refs:** T-02
- **Acceptance criteria:**
  - [ ] `docker-compose.yml` uses `${VAR:?must be set}` (no `:-default`) for all secrets
  - [ ] Startup rejects known-insecure values (`test-secret*`, `etap_dev_api_key*`, Fernet sample key) even when they meet length checks
  - [ ] Secrets come from a secret manager / CI-injected env in production
- **Test cases:**
  1. Test: compose with unset `JWT_SECRET_KEY` fails to start the service
  2. Test: startup refuses `test-secret-32-bytes-long-aaaa-bbbb` as `JWT_SECRET_KEY`
  3. Test: scan fails on `etap_dev_api_key_1234567890` in compose
- **Compliance refs:** NIST CSF PR.DS-1; ISO 27001 A.8.10/A.9.4

**SR-011 — Config-layer secret validation must hard-fail (C, LOW)**
As a security-conscious system, I need `backend/config.py` to validate `JWT_SECRET_KEY` and raise on missing/short keys, so that no code path can sign or verify tokens with an empty secret.

- **Threat refs:** T-25
- **Acceptance criteria:**
  - [ ] `Config` raises at construction in production when `JWT_SECRET_KEY` is empty or <32 bytes
  - [ ] No `os.getenv("JWT_SECRET_KEY", "")` default remains for token operations
- **Test cases:**
  1. Test: `Config()` with empty secret in prod env raises
  2. Test: all token operations read from the validated source
- **Compliance refs:** NIST CSF PR.DS-1

**SR-012 — Sensitive provider keys require TLS and are not CORS-exposed (C, MEDIUM)**
As a security-conscious system, I need `x-active-key` removed from CORS `allow_headers` and API traffic forced over TLS, so that provider credentials cannot be read by third-party pages or captured in cleartext.

- **Threat refs:** T-20
- **Acceptance criteria:**
  - [ ] `x-active-key` / `x-active-url` removed from `allow_headers`
  - [ ] HSTS enforced by default on the engineering API
  - [ ] Cleartext HTTP rejected in production
- **Test cases:**
  1. Test: preflight for `x-active-key` is not allowed
  2. Test: response carries HSTS header in prod
  3. Test: HTTP request in prod is redirected/rejected
- **Compliance refs:** OWASP ASVS V9 (TLS); NIST CSF PR.DS-2

### 2.5 Audit Logging (Domain: audit_logging)

**SR-013 — Audit export is formula-injection safe (F, LOW)**
As a security analyst, I need exported CSV cells neutralized, so that opening an audit export in a spreadsheet cannot execute formulas.

- **Threat refs:** T-21
- **Acceptance criteria:**
  - [ ] Values starting with `= + - @` are prefixed (e.g., `'`)
  - [ ] Applies to `details` and `user` fields in the audit export
- **Test cases:**
  1. Test: `=HYPERLINK(...)` export value is escaped
  2. Test: `@cmd` export value is escaped
- **Compliance refs:** OWASP ASVS V5.4; NIST CSF PR.DS-1

**SR-014 — Security events are logged with full attribution (F, HIGH)**
As a security analyst, I need admin actions, privilege changes, and auth events logged with user identity and non-repudiation, so that incidents can be investigated.

- **Threat refs:** T-04, T-11, T-05
- **Acceptance criteria:**
  - [ ] Kill-switch activate/deactivate, rollback, role changes, and logins are audit-logged with user/tenant/timestamp
  - [ ] Audit entries are tamper-evident (chained hash) — preserved
  - [ ] No raw tokens/passwords written to any log sink (ACP `trace_id` redaction per SR-007)
- **Test cases:**
  1. Test: admin action produces an audit entry with actor identity
  2. Test: logs contain no JWT/password/api-key substrings
  3. Test: tampered chain is detected by `/api/v1/audit/verify`
- **Compliance refs:** OWASP ASVS V7; NIST CSF DE.CM-6/PR.PT-1; ISO 27001 A.12.4

### 2.6 Error Handling (Domain: error_handling)

**SR-015 — No internal state in error responses (F, HIGH)**
As a security-conscious system, I need to sanitize exception messages before returning them, so that file paths and engine internals are never disclosed to clients.

- **Threat refs:** T-08, T-22
- **Acceptance criteria:**
  - [ ] `study_service` maps exceptions to generic details and logs the full trace server-side
  - [ ] FastAPI `debug` defaults to `False` unless `ENVIRONMENT=development` is explicit
  - [ ] Reflective details (`{value!r}`) are removed from audit-log errors
- **Test cases:**
  1. Test: invalid study payload returns generic 400 without file paths
  2. Test: unset `ENVIRONMENT` runs with `debug=False`
  3. Test: error responses never echo input back verbatim
- **Compliance refs:** OWASP ASVS V7.4; NIST CSF PR.DS-1

### 2.7 Availability & DoS (Domain: availability)

**SR-016 — Request body limits cover chunked encoding (F, MEDIUM)**
As a security-conscious system, I need to enforce body size on chunked requests, so that clients cannot bypass the 50 MB cap and exhaust memory.

- **Threat refs:** T-13
- **Acceptance criteria:**
  - [ ] Middleware caps body streaming for `Transfer-Encoding: chunked` (Content-Length absent) at the same limit
  - [ ] Overflowing requests receive 413
- **Test cases:**
  1. Test: chunked POST > 50 MB → 413
  2. Test: chunked POST ≤ 50 MB passes
- **Compliance refs:** NIST CSF PR.AC-1; OWASP ASVS V11

**SR-017 — Rate limiting fails closed (F, MEDIUM)**
As a security-conscious system, I need throttling to stay effective during a Redis outage, so that attackers cannot disable brute-force protection by exhausting Redis.

- **Threat refs:** T-14
- **Acceptance criteria:**
  - [ ] Redis failure in the rate limiter denies conservatively or uses a bounded local fallback — never `return True`
  - [ ] Sensitive endpoints carry per-IP and per-user buckets behind proxies
  - [ ] Trusted-proxy configuration is validated at startup
- **Test cases:**
  1. Test: rate limiter with Redis down still blocks a burst of login attempts
  2. Test: 429 returned when both Redis and local limit exhausted
- **Compliance refs:** NIST CSF PR.DS-4; OWASP ASVS V11

**SR-018 — CPU-bound studies do not block the event loop (NF, MEDIUM)**
As a system administrator, I need native study computations off the async event loop, so that health checks and authentication remain responsive under load.

- **Threat refs:** T-18
- **Acceptance criteria:**
  - [ ] `_run_native_study` executes via `to_thread`/executor (parity with the ETAP path)
  - [ ] Health endpoint latency stays <100 ms under concurrent studies
- **Test cases:**
  1. Test: two concurrent large load-flow runs do not stall `/health`
  2. Test: event loop blocked time during study is ~0
- **Compliance refs:** NIST CSF PR.DS-4

### 2.8 File Integrity & Safe Serialization (Domain: input_validation / data_protection)

**SR-019 — Report output paths are allowlisted (F, MEDIUM)**
As a security-conscious system, I need report generation paths validated, so that task parameters cannot write outside the reports directory.

- **Threat refs:** T-19
- **Acceptance criteria:**
  - [ ] `output_path` passes `validate_file_path` / an allowlist before any write
  - [ ] Attempts outside the reports directory are rejected
- **Test cases:**
  1. Test: `output_path=../../etc` is rejected
  2. Test: `output_path=/tmp/..` is rejected
  3. Test: legitimate `./reports` path succeeds
- **Compliance refs:** OWASP ASVS V12.3; NIST CSF PR.AC-3

**SR-020 — Serialization boundary uses a safe format (F, MEDIUM)**
As a security-conscious system, I need the isolation boundary to never `pickle.load` untrusted data in the parent, so that a tampered result file cannot execute code in the API process.

- **Threat refs:** T-16
- **Acceptance criteria:**
  - [ ] Parent-side reads use a restricted unpickler or a safe format (JSON/schema-validated)
  - [ ] `exec_dir` path is validated before f-string interpolation
- **Test cases:**
  1. Test: crafted `result.pkl` with `__reduce__` payload is rejected
  2. Test: sandbox path traversal in `exec_script` is blocked
- **Compliance refs:** OWASP ASVS V5.5; NIST CSF PR.DS-1

### 2.9 Defense-in-depth (Domain: network_security)

**SR-021 — ETAP project paths validated at the service boundary (F, LOW)**
- **Threat refs:** T-23
- **Acceptance criteria:** [ ] `etap_project_path` validated (extension, allowlisted dir, no traversal) in `study_service` before reaching the provider
- **Test cases:** 1. Test: `../../etc` project path rejected 2. Test: non-`.edb` path rejected
- **Compliance refs:** OWASP ASVS V12.3

**SR-022 — Security headers enforced on the engineering API (NF, LOW)**
- **Threat refs:** T-24
- **Acceptance criteria:** [ ] CSP header set on engineering API 2. [ ] HSTS with `max-age` enabled by default in production
- **Test cases:** 1. Test: `/health` carries CSP in prod 2. Test: HTTPS response carries HSTS
- **Compliance refs:** OWASP ASVS V14.4; NIST CSF PR.DS-2

---

## 3. Threat-to-Requirement Traceability Matrix

| Threat | Requirements |
|--------|--------------|
| T-01 Sandbox escape (RCE) | SR-001 |
| T-02 Hardcoded secrets | SR-010 |
| T-03 RLS tenant leak | SR-008 |
| T-04 Admin endpoints by API key only | SR-003, SR-014 |
| T-05 ACP unauth + token in logs | SR-007, SR-014 |
| T-06 Auth-disable grants ADMIN | SR-006 |
| T-07 PowerShell newline injection | SR-002 |
| T-08 Raw exceptions / debug=True | SR-015 |
| T-09 Task result IDOR | SR-009 |
| T-10 JWT in WS query string | SR-004 |
| T-11 WS notifications weak + echo | SR-005, SR-014 |
| T-12 verify_api_key open | SR-006 |
| T-13 Chunked body bypass | SR-016 |
| T-14 Rate limiter fails open | SR-017 |
| T-15 WS no Origin check | SR-005 |
| T-16 Pickle parent-side | SR-020 |
| T-17 CSRF DNS-rebinding default | SR-005 (Origin checks) |
| T-18 Sync study blocks loop | SR-018 |
| T-19 Report path traversal | SR-019 |
| T-20 x-active-key plaintext | SR-012 |
| T-21 CSV formula injection | SR-013 |
| T-22 Reflective errors | SR-015 |
| T-23 ETAP path unvalidated | SR-021 |
| T-24 Missing CSP/HSTS | SR-022 |
| T-25 Empty JWT secret default | SR-011 |

## 4. Compliance Mapping (high-level)

| Framework | Covered requirements |
|-----------|----------------------|
| OWASP ASVS | SR-001 (V5), SR-002 (V5), SR-003 (V2/V4), SR-004 (V3), SR-005 (V3/V12), SR-009 (V4.1), SR-012 (V9), SR-013 (V5.4), SR-015 (V7), SR-016 (V11), SR-017 (V11), SR-019 (V12.3), SR-020 (V5.5), SR-021 (V12.3), SR-022 (V14.4) |
| NIST CSF | PR.AC (SR-002, SR-003, SR-005, SR-006, SR-007, SR-016, SR-019), PR.DS (SR-010, SR-011, SR-012, SR-013, SR-015, SR-017, SR-018, SR-020, SR-022), PR.PT (SR-001, SR-014), DE.CM (SR-014) |
| ISO 27001 | A.8.10/A.9.4 (SR-010), A.9.1 (SR-007), A.9.2 (SR-003), A.12.4 (SR-014), A.9.1/A.10 (SR-008) |

## 5. Recommended Remediation Order

1. **CRITICAL — now:** remove hardcoded secrets from `docker-compose.yml` (SR-010); fix sandbox `__dict__` escape (SR-001); fix RLS connection reuse (SR-008).
2. **HIGH — next sprint:** role-gate admin CUA endpoints (SR-003), fail-closed auth switches (SR-006), WS auth/origin/notifications (SR-004/SR-005), PowerShell statement validation (SR-002), ACP auth + log redaction (SR-007), sanitize error responses (SR-015), scope task results (SR-009).
3. **MEDIUM/LOW — backlog:** chunked body limits (SR-016), fail-closed rate limiting (SR-017), event-loop offload (SR-018), report path validation (SR-019), safe serialization (SR-020), CSV formula sanitization (SR-013), TLS/HSTS + headers (SR-012/SR-022), config secret hard-fail (SR-011).
