# Security Remediation Log — 2026-07-21

## Branch
`fix/security-critical-2026-07-21` (based on `main` @ `a6d196a9`)

## Fixes applied in this batch

### CRITICAL
- **C1**: Removed hardcoded live RESEND_API_KEY from `tests/test_new_features.py`.
  Replaced with `os.environ.setdefault()` reading from env. The previous
  value (`re_FpxUQQs1_...`) was committed to a public repository and is
  being rotated.
- **C2**: Fixed `NameError` in `api/studies.py:run_study()` — `warnings`/
  `errors`/`data` containers are now initialised BEFORE the `try:` block
  that may append to them. Previous code raised on every PE-stamp-required
  study (arc_flash, protection_coordination, etc.).
- **C4**: `api/_test_mode.py:is_test_mode()` now hard-returns `False` in
  production/staging. A leaked `ENGINEERING_SERVICE_API_KEY` no longer
  grants admin access on the email dashboard / OTP / magic-link flows.
  Comparison is now timing-safe (`hmac.compare_digest`).
- **C5**: `api/csrf.py:_get_secret()` no longer falls back to the publicly
  known placeholder `_SENTINEL_DEFAULT` in production. It raises
  `RuntimeError` instead. In development it generates a per-process random
  key (logged).
- **C6**: `api/database.py:init_db()` no longer silently falls back to
  `/tmp/data/etap_platform_fallback.db`. If Postgres is unreachable, the
  failure is re-raised so the `/healthz` endpoint reports unhealthy.
  `_ALLOW_SQLITE_FALLBACK` env var is now hard-`False` (no env override).

### HIGH
- **H3**: `api/auth.py` registration + forgot-password + update-me now
  compare emails case-insensitively (`func.lower(User.email) == ...`) and
  store emails lowercased. Prevents duplicate accounts via `User@x.com` vs
  `user@x.com`.
- **H4**: Removed `'unsafe-eval'` from CSP in `akamai/property.json` and
  `hf-space/app.py`. The HF Space now ships a strict CSP for all routes
  except `/docs`, `/redoc`, `/openapi.json` (where Swagger UI requires
  `'unsafe-inline'` for script-src, which is still safer than eval).
- **H5**: Removed `X-Error-Type` response header and `type` field from
  the global exception handler in `hf-space/app.py`. No more internal
  exception class names leaked to clients.
- **H7**: `api/studies.py` no longer hardcodes `redis://localhost:6379`
  — now reads from `REDIS_URL` env var.
- **H8**: Removed the hardcoded `/home/z/my-project/etap-local-clone`
  path from `tests/test_new_features.py`. Now resolves the project root
  from `__file__`.

### MEDIUM
- **M2**: Synced `vitest` and `typescript` versions between root
  `package.json` and `ui/package.json` (both at `3.2.6` and `5.7.2`
  respectively).
- **M9**: `EMAIL_DASHBOARD_DEV_OPEN=true` is now hard-rejected in
  production/staging. The dashboard no longer opens without auth even if
  the env var leaks.

## Issues documented but NOT fixed in this batch

These require multi-day refactors and are tracked separately:

- **C3**: Rotate every credential the user pasted in chat. The AI
  assistant cannot perform rotations — the account owner must do this
  from each service's dashboard. See `SECURITY_INCIDENT_2026-07-08.md`.
- **H1**: 1,738 `NOSONAR` suppressions. A multi-week cleanup sprint is
  required; individual removals must be reviewed case-by-case (some are
  legitimate engineering notation in IEEE/IEC formulas).
- **H2**: 92 `fix/*` and 17 `sonarcloud/*` branches need bulk delete
  after PRs are merged. Requires maintainer action.
- **H6**: `hf-space/app.py` (1,499 lines) duplicates `api/routes.py`.
  Consolidating requires ~3 days of careful migration.
- **H9**: 785 `.md` files at root — needs an organisational decision on
  which docs to keep.
- **M10**: Apply `langfuse_llm` guardrails to all agents. Currently
  agents use `gemini_vision`/`openai_vision` SDKs directly. The
  `langfuse_llm.openai` / `langfuse_llm.anthropic` wrappers exist but
  are only imported in tests. A migration plan is needed.

## Pre-push verification checklist

- [x] All modified Python files compile (`python3 -m py_compile`)
- [x] No hardcoded secrets in diff (`scripts/security_scan.py` + grep)
- [x] `.env` is gitignored
- [x] Commit messages do not contain tokens
- [x] Branch is a feature branch, NOT main
- [ ] pytest suite passes (run locally before push)
- [ ] ruff lint passes
- [ ] tsc on ui/ passes
- [ ] GitHub Actions secret-scan workflow passes

## Post-push verification (after PR is opened)

- [ ] CI workflows pass on the PR
- [ ] Code review by maintainer before merge
- [ ] Squash-merge into main (do not preserve the fix branch)
- [ ] Delete the fix branch after merge
