# E2E Testing Protocol — AhmedETAP Engineering Platform

> **Last updated:** 2026-07-19
> **Branch:** `secure-work-20260718-145500`
> **Status:** All Python e2e suites PASSING (42/42), TypeScript scenarios gated on pnpm install

---

## 1. E2E Test Suites Overview

| Suite | File(s) | Type | Framework | Tests | Status |
|-------|---------|------|-----------|-------|--------|
| Validation Smoke | `tests/e2e_smoke_test.py` | Python | pytest | 3 | ✅ PASS |
| Security E2E | `tests/test_security_e2e.py` | Python | pytest | 39 | ✅ PASS |
| E2E Workflow (TS) | `tests/scenarios/e2e-workflow.test.ts` | TypeScript | vitest | 14 | ⚠️ Needs pnpm install |
| Live Backend | `scripts/e2e_test.py` | Python | standalone | 8 categories | 🔌 Requires live backend |

---

## 2. Fixes Applied

### 2.1 `check_results.py` — Syntax Error (CRITICAL)
- **File:** `check_results.py`, line 7
- **Error:** `SyntaxError: invalid syntax` — raw string with double quotes inside double-quoted delimiters
- **Root cause:** `re.findall(r"style="[^"]*"", content)` — outer `"` delimiter conflicted with `"` inside regex
- **Fix:** Changed outer delimiter to single quotes: `re.findall(r'style="[^"]*"', content)`
- **Impact:** `test_syntax_validation_cli_passes` now passes (was failing with return code 1)

### 2.2 `tests/e2e_smoke_test.py` — All 3 tests verified
- `test_validation_suite_cli_passes` — calls `scripts/dev/validation_suite.py` ✅
- `test_syntax_validation_cli_passes` — calls `scripts/maintenance/validate_syntax.py` ✅ *(after fix 2.1)*
- `test_docker_compose_file_is_present` — checks `docker-compose.yml` (3807 bytes) ✅

### 2.3 `tests/test_security_e2e.py` — All 39 tests verified
- Runs against FastAPI TestClient with in-memory SQLite
- Covers: API key bypass, JWT lifecycle, RASP (SQLi/XSS/traversal), rate limiting, body size, ABAC, MFA TOTP, SIEM event forwarding
- All pass in 112s on Python 3.8 (CI runs Python 3.12 — slightly faster)

---

## 3. How to Run

### 3.1 Python E2E Tests

```bash
# Smoke tests (no external deps)
pytest tests/e2e_smoke_test.py -v --timeout=30

# Security E2E tests (requires pytest-asyncio)
pytest tests/test_security_e2e.py -v --timeout=30
```

**Requirements:** `pytest`, `pytest-timeout`, `pytest-asyncio`

### 3.2 TypeScript Scenario Tests

```bash
# Install dependencies (first time only — 1534 packages, ~3-5 min)
pnpm install --no-frozen-lockfile

# Run scenario tests
pnpm test:scenarios
```

**Config:** `vitest.scenarios.config.ts` — includes `tests/scenarios/**/*.test.ts`

### 3.3 Live Backend Test

```bash
# Requires engineering_service.py running on localhost:8000
python scripts/e2e_test.py
```

---

## 4. CI/CD Integration

### 4.1 Main Pipeline (`.github/workflows/ci-cd.yml`)

| Job | Tests | Notes |
|-----|-------|-------|
| `lint` (Code Quality) | `pnpm test:scenarios` | Runs scenario tests (auto-skipped if no provider creds) |
| `python-tests` | Full pytest suite | Excludes `tests/scenarios`, `tests/load`, `tests/stress`, `tests/chaos`, `tests/property_based`, `tests/regression` |
| `sonarcloud` | Coverage analysis | Downloads coverage from `python-tests`; fallback generates minimal `coverage.xml` |

### 4.2 Integration Tests (`.github/workflows/integration-tests.yml`)

| Job | Tests | Services |
|-----|-------|----------|
| `database` | `pytest -k "database or db or migration"` | PostgreSQL 15, Redis 7 |
| `api-e2e` | `pytest -k "api or endpoint or e2e"` + curl checks | PostgreSQL 15, Redis 7 |
| `agents` | `pytest -k "agent or orchestrator"` + import check | Redis 7 |

### 4.3 Key CI Configuration Details

- **Rate limit:** `LOGIN_RATE_LIMIT_MAX_ATTEMPTS=5` (env var) — 5 failed attempts trigger 429
- **Rate limit override:** `ENGINEERING_SERVICE_RATE_LIMIT_MAX=10000` (test env) — increases global ceiling
- **Auth disabled:** `ENGINEERING_SERVICE_AUTH_DISABLED=true` (test env) — skip API key checks
- **Cache disabled:** `ENGINEERING_SERVICE_CACHE_DISABLED=true` (test env) — avoid Redis dependency
- **Database:** `sqlite+aiosqlite:///./test.db` (CI) / `sqlite+aiosqlite://` (in-memory for unit tests)
- **Python:** 3.12 (CI) — locally tested on 3.8
- **Node:** 24 (CI) — locally tested on 24.16.0

---

## 5. Architecture Notes

### 5.1 Test Fixture Chain (Python)
```
client → app → db_engine (creates tables) → auth_headers → registered_user
```
The `conftest.py` provides:
- `client` — FastAPI TestClient wired to in-memory SQLite
- `auth_headers` — Bearer token for engineer role
- `viewer_headers` — Bearer token for viewer role
- `admin_headers` — Bearer token for admin role

### 5.2 Test Fixture Chain (TypeScript)
```
beforeEach → MockEtapProvider.createMockEtapScenario() → connect
```
Mocks are fully in-memory (no real ETAP COM or network calls).

---

## 6. Known Limitations

1. **`tests/scenarios/**` excluded from root vitest config** — zod v4 vs zod-to-json-schema v3 incompatibility. Run via `pnpm test:scenarios` exclusively.
2. **`scripts/e2e_test.py` is not a pytest suite** — standalone script requiring live backend. Run manually for production smoke testing.
3. **pnpm install is slow (1534 packages)** — In CI this is cached; locally use `pnpm install --offline` after first install.
4. **Python 3.8 locally vs 3.12 in CI** — Some tests may have minor timing differences due to async event loop behavior.

---

## 7. Test Results Log

| Date | Suite | Results | Runner |
|------|-------|---------|--------|
| 2026-07-19 | `e2e_smoke_test.py` | 3/3 PASS (25.98s) | Python 3.8 / Windows |
| 2026-07-19 | `test_security_e2e.py` | 39/39 PASS (112.54s) | Python 3.8 / Windows |
| 2026-07-19 | `e2e-workflow.test.ts` | Not run (pnpm install timeout) | Node 24 / Windows |

---

## 8. Emergency Checklist

If CI pipeline fails on e2e tests:

1. **Check `check_results.py`** for syntax errors (recurring issue with raw string escaping)
2. **Check `_LOGIN_ATTEMPTS` clearing** in `conftest.py` — if rate limit tests leak across test functions
3. **Check `pnpm-lock.yaml`** for `zod` / `zod-to-json-schema` version conflicts
4. **Check Redis connectivity** — `_check_rate_limit` falls back to in-memory dict, but stats tracking differs
5. **Check event loop** — set `DEBUG_EVENT_LOOP=1` in CI for diagnostics on `RuntimeError: Event loop is closed`
