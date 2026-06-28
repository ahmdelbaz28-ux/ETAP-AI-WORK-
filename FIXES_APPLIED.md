# ETAP Launch Blockers - Fixes Applied

**Date:** 2026-06-23
**Status:** Critical & High Priority Fixes Complete

---

## 2026-06-28 — Vercel Build Fix + Cross-Platform Auto-Sync

### Root cause of Vercel build warnings
The `npm warn ERESOLVE overriding peer dependency` warning for
`@vitest/mocker@2.1.8 → vite@^5.0.0 vs vite@6.0.5` was caused by
`vitest@2.1.8` not officially supporting `vite@6.x`. While npm was
auto-resolving it, the underlying mismatch made the install step
fragile and could trigger failures on stricter CI environments.

### Fixes applied
1. **`ui/package.json`** — upgraded `vitest` from `2.1.8` → `3.0.9`
   (Vitest 3.x officially supports Vite 6.x → eliminates the peer
   dependency warning entirely).
2. **`package.json` (root)** — upgraded `vitest` + `@vitest/coverage-v8`
   from `2.1.8` → `3.0.9` to keep the monorepo consistent.
3. **`ui/package.json`** — added `build:vercel` script that skips
   `tsc -b` (Vite handles TS transforms; type-checks run in CI).
4. **`ui/vercel.json`** — pinned `installCommand`, `buildCommand`,
   `outputDirectory`, and added security headers.
5. **`ui/.npmrc`** — set `auto-install-peers=true` + `audit=false` for
   faster, more reliable installs.
6. **`.nvmrc`** — pinned Node 22 so Vercel/HF/local all use the same
   runtime.
7. **`.github/workflows/sync-platforms.yml`** — new unified workflow
   that auto-syncs every push to `main` across **Vercel + HuggingFace
   Space + LangWatch + Smithery**, plus a daily drift-detection job
   that opens a PR if the HF Space README diverges from GitHub.
8. **`.github/SECRETS_SETUP.md`** — step-by-step guide to set all
   required GitHub Secrets.

---

## Summary of Changes

### 1. HF Space Build Fixes (A1-A5, A3, A4)

#### Dockerfile.hf - Simplified & Secured
- **Removed:** nginx + supervisord (over-engineered for single FastAPI app)
- **Added:** Non-root user (UID 1000) as required by HF Spaces
- **Changed:** Single-process uvicorn entrypoint on port 7860
- **Fixed:** Database path uses `/tmp/data` (writable location)
- **Fixed:** Python packages installed to `/home/user/.local` (not `/root/.local`)

#### requirements.hf.txt - Created
- Minimal dependencies for HF Space deployment
- Excludes ML/GUI packages that fail on Linux (pyautogui, opencv-python, torch, etc.)
- Includes: fastapi, uvicorn, pydantic, sqlalchemy, redis, cryptography, etc.

### 2. Dockerfile.engineering-service - Fixed Missing COPYs (D1)

Added missing directories:
- `api/`, `core/`, `services/`, `worker/`, `ml/`, `agents/`
- `migrations/`, `digital_twin/`, `scada_model/`, `adms_control/`
- `utils/`, `schemas/`, `guards/`, `copilot/`, `gis_integration/`
- `gis_model/`, `gis_validation/`, `skills/`, `reporting/`, `prompts/`, `config/`

### 3. pyproject.toml - Dependency Cleanup (D9, J2, J6)

**Removed from runtime dependencies:**
- `aioredis>=2.0.0` (abandoned, fails on Python 3.12+)
- `pyautogui>=0.9.53` (requires X11, fails on Linux)
- `opencv-python>=4.5.0` (requires libGL, fails on Linux)
- `hypothesis>=6.92.0` (moved to dev)
- `pre-commit>=3.6.0` (moved to dev)

**Added to win32 optional dependencies:**
- `pyautogui>=0.9.53`
- `opencv-python>=4.5.0`

**Added to dev dependencies:**
- `hypothesis>=6.92.0`
- `pre-commit>=3.6.0`

**Fixed pydantic extra:**
- Changed `pydantic>=2.0.0` to `pydantic[email]>=2.0.0`

### 4. docker-compose.yml - Security & Reliability (D4, D5, D6)

**Replaced hardcoded credentials with required env vars:**
- `POSTGRES_PASSWORD: etap_pass` → `${POSTGRES_PASSWORD:?required}`
- `GF_SECURITY_ADMIN_PASSWORD=admin123` → `${GRAFANA_PASSWORD:?required}`
- Added `ENGINEERING_SERVICE_API_KEY=${ENGINEERING_SERVICE_API_KEY:?required}`
- Added `JWT_SECRET_KEY=${JWT_SECRET_KEY:?required}`

**Fixed DATABASE_URL:**
- Changed from `/data/mastra.db` (invalid) to `sqlite+aiosqlite:////tmp/data/etap_platform.db`

**Added healthchecks:**
- Redis: `redis-cli ping` every 10s
- Postgres: `pg_isready` every 10s

**Updated depends_on:**
- Use `condition: service_healthy` for proper startup ordering

### 5. requirements.txt - Cleaned Up (J3, J8)

**Removed problematic packages:**
- `pyautogui` (requires X11)
- `opencv-python` (requires libGL)
- `flask` (conflicts with FastAPI)
- `pymongo` (unused)
- `geopandas` (requires GDAL)
- `shapely` (requires GEOS)

**Added missing dependencies:**
- `python-multipart>=0.0.6`
- `email-validator>=2.0.0` (explicit)

### 6. requirements-prod.txt - Updated

Added missing dependencies:
- `httpx>=0.25.0`
- `python-multipart>=0.0.6`
- `email-validator>=2.0.0`
- `alembic>=1.13.0`

### 7. core/bootstrap.py - Bug Fixes (C5, C6)

**Fixed logging format (C6):**
- Removed `%(trace_id)s` from format string (caused KeyError)
- Now uses `%(message)s` with trace_id added via filter

**Fixed cache.ping() not awaited (C5):**
- Made `_initialize_cache_with_retry` async
- Properly `await cache.ping()` instead of calling sync
- Added `asyncio.sleep()` for retry delays

### 8. api/__init__.py - Import Optimization (C8)

- Removed eager imports of 10 routers
- Each router is now imported explicitly by `api/routes.py`
- Reduces cold-start time and import cycles

### 9. Sync Workflow - Fixed (B1, B2)

**Updated sync-ahmedetap-space.yml:**
- Added path filters (only sync when relevant files change)
- Added Dockerfile.hf validation step
- Now syncs only required files/directories
- Added `--delete-after` behavior (clean target first)

### 10. Root Dockerfile - Fixed (D3)

- Removed `main.py` reference (doesn't exist in repo)
- Added missing directories: `guards/`, `copilot/`, `prompts/`, `config/`
- Updated version label to `2.1.0`

### 11. hf-space Updates

**Dockerfile:**
- Updated Python version from 3.11 to 3.13
- Added non-root user (UID 1000)
- Added database path environment variable

**requirements.hf.txt:**
- Added missing dependencies for full functionality
- Added: sqlalchemy, alembic, bcrypt, PyJWT, cryptography, etc.

**app.py:**
- Removed redundant `UTC = UTC` self-assignment
- Restricted CORS origins (no more `allow_origins=["*"]`)

### 12. .dockerignore - Enhanced

Added exclusions for:
- Root-level scripts (`fix_*.py`, `test_*.py`, etc.)
- Terraform/Helm/charts
- Grafana/monitoring configs
- Source code for other runtimes (`src/`)
- Root-level config files

### 13. VERSION File - Created

Single source of truth for version number: `2.1.0`

---

## Remaining High Priority Items

### Not Yet Fixed (require manual intervention):

1. **HF Space Secrets** - Must be set in HF Space settings:
   - `JWT_SECRET_KEY` (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
   - `ENGINEERING_SERVICE_API_KEY`
   - `ENVIRONMENT=production`

2. **Token Revocation** - User must revoke leaked tokens:
   - HF token: `hf_GMLi...`
   - GitHub PAT 1: `github_pat_11CCHF4XA0...`
   - GitHub PAT 2: `ghp_48G4QTksCwW3...`

3. **Duplicate StudyCache** (K3)
   - `services/cache_service.py` and `engine/caching.py` both define `StudyCache`
   - Need to consolidate into one

---

## Files Modified

| File | Changes |
|------|---------|
| `Dockerfile.hf` | Simplified, non-root user, uvicorn-only |
| `requirements.hf.txt` | **NEW** - Minimal HF dependencies |
| `Dockerfile.engineering-service` | Added missing COPY directives |
| `pyproject.toml` | Removed problematic deps, version bump |
| `docker-compose.yml` | Security fixes, healthchecks |
| `requirements.txt` | Removed problematic packages, added celery |
| `requirements-prod.txt` | Added missing dependencies, added celery |
| `core/bootstrap.py` | Fixed logging, async cache init |
| `api/__init__.py` | Removed eager imports |
| `.github/workflows/sync-ahmedetap-space.yml` | Fixed sync logic |
| `Dockerfile` | Fixed COPY directives, version |
| `hf-space/Dockerfile` | Non-root user, Python 3.13 |
| `hf-space/requirements.hf.txt` | Added missing dependencies |
| `hf-space/app.py` | Fixed CORS, removed redundant code |
| `.dockerignore` | Enhanced exclusions |
| `VERSION` | **NEW** - Single source of truth |
| `ui/package.json` | Fixed nonexistent npm versions, version bump |
| `package.json` | Fixed nonexistent npm versions, version bump |

---

## Next Steps

1. **Revoke leaked tokens immediately**
2. **Set HF Space secrets** (JWT_SECRET_KEY, ENGINEERING_SERVICE_API_KEY)
3. **Test Docker build locally**: `docker build -f Dockerfile.hf -t etap-hf:test .`
4. **Test docker-compose**: `docker-compose up --build`
5. **Commit and push changes** to trigger HF Space sync
