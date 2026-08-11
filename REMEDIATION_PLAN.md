# AhmedETAP Remediation Plan — Audit Prompt 2026-08-10

**Repo:** `C:\Users\Repair SC\Desktop\etap` (ETAP-AI-WORK-, cloned at HEAD `8c920b00f`)
**Mode:** Plan (approved for exploration only). All findings below were re-verified against live code on 2026-08-10.
**Constraint:** Verify-before-edit / verify-after-edit. One finding = one focused edit. No blind changes, no `as any`/`type: ignore`/`# type: ignore`, no new secrets, no weakening auth. Commit ONLY if user explicitly authorizes; otherwise leave uncommitted.

---

## 0. Pre-verified "DO NOT TOUCH" (already fixed in HEAD) → SKIP
| ID | Check result |
|---|---|
| S-CRIT-1 | `docker-compose.yml` uses `${VAR:?}` for ENGINEERING_SERVICE_API_KEY, JWT_SECRET_KEY, FERNET_ENCRYPTION_KEY, FIREAI_SESSION_SECRET, POSTGRES_PASSWORD, REDIS_PASSWORD → **SKIP** |
| S-CRIT-4 | `security/secure_executor.py` → subprocess-based exec + MRO escape pre-scan + module freeze (commit 030cad1b9) → **SKIP** |
| S-HIGH-6 | `backend/request_context.py` → `_reset_tenant_on_checkin` registered on `reset_rollback` (line 334) → **SKIP** |
| frontend/.env.example | `frontend/` does not exist → **SKIP** (never create) |

## 1. Verified status matrix (live code, HEAD 8c920b00f)
| ID | Location (verified) | Status | Evidence |
|---|---|---|---|
| A1 | `api/shared_handlers.py:362-364` | **OPEN** | `if not expected_key: return` → fail-open |
| A2 | `backend/security_middleware.py:396-403` | **OPEN** | AUTH_DISABLED → role=ADMIN regardless of ENVIRONMENT |
| A3 | `api/routes.py` audit_verify(930), kill-switch(998/1028/1054), rollback(1076) | **OPEN** | Only `_require_api_key(request)`; no require_role |
| A4 | `api/routes.py:449/492`; `src/routes/studies.ts:46/64/106` | **OPEN** | TS `taskId=traceId`, no ownerApiKeyId, no ownership check; Python no key-id on task |
| A5 | `api/websocket.py:396-431`, `api/routes.py:547` | **OPEN** | No Origin check; token query-only; wrapper calls endpoint w/o token (always 4001); `cua_confirmation_ws.py:478-485` already has Origin check |
| A6 | `api/routes.py:649` (+ verify `backend/app.py:~547`) | **PARTIAL** | `x-active-key` only remains in CORS allow_headers; no server read path |
| B1 | `worker/tasks.py:124-132` | **OPEN** | Second ETAPProvider + execute_command block runs duplicate command |
| B2 | `api/websocket.py:382` | **OPEN** | `if _is_token_blacklisted(jti)` missing `await` |
| B3 | `api/websocket.py:167-190` | **OPEN** | New `ETAPScadaBridge()` per call; bare `except Exception: pass` |
| B4 | `worker/tasks.py:152-219` | **OPEN** | Placeholder numpy inversion loop ("Simulate a heavy calculation") |
| B5 | `services/study_service.py:213-227` | **OPEN** | New ThreadPoolExecutor + asyncio.run per call |
| B6 | `services/api_key_store.py:177-205`; `api/settings.py` | **OPEN** | Random Fernet key on restart; sync sqlite3 inside async handlers |
| B7 | `services/otp_store.py:174-235` | **OPEN** | Docstring claims Redis; all paths use `_mem_store` only. `email_send_log.py` DOES persist to Redis (honest) |
| B8 | `services/cache_service.py:201-204` | **OPEN** | Unreachable duplicate in-memory fallback |
| B9 | `api/routes.py:773+792, 782+784-786` | **OPEN** | Duplicate include_router: feature_flags, autodesk_connectors |
| C1 | `alembic/` vs `migrations/versions/` | **OPEN** | alembic.ini → `migrations` (live); `006_add_scada_gis_email` + `006_add_tenant_id_and_rls` = 2 heads |
| C2 | `api/database.py:384-386` | **OPEN** | `Base.metadata.create_all` still in init_db |
| C3 | `scripts/backup/postgres_backup.sh` | **OPEN** | Exists, referenced by nothing (grep across yml/tf) |
| D1 | `src/core/engineeringService.ts:127-136` | **OPEN** | 4xx thrown inside loop is caught by retry catch (141-153) |
| D2 | `src/mastra/lib/model-config.ts:21-26,78-88`; `tools/provider-settings-tool.ts` | **OPEN** | ProviderConfig.apiKey raw; returned to tool result |
| D3 | `tsconfig.json:8` | **OPEN** | `noImplicitAny: false` |
| D4 | `src/mastra/lib/model-config.ts:65` | **PARTIAL** | Only 1 cast left (`as unknown as LanguageModel`); "22 sites" claim stale |
| D5 | root `index.html`/`login.html`, `todo-app/`, `cloud/FRONTEND` | **PARTIAL** | todo-app + cloud/FRONTEND exist (move → separate repo, NO delete); login.html ≠ index.html (different SHA) → cannot auto-delete |
| D6 | `src/core/circuitBreaker.ts:85-96` | **OPEN** | No halfOpenInProgress flag (thundering herd) |
| D7 | `src/core/tokenStats.ts:76,93` | **OPEN** | `_calls` unbounded |
| D8 | `src/mastra/prompts.ts:45-188` | **OPEN** | Hand-rolled YAML parser; js-yaml NOT in package.json |
| E1 | root `Dockerfile` 1-162 vs 164-310 | **PARTIAL** | Two build pipelines concatenated; verify HF uses other Dockerfile before removal |
| E2 | `terraform/backend.tf:24-49` | **OPEN** | azurerm block unclosed + extra `backend "local"` block |
| E3 | `deploy/k8s/*.yaml` (all 9) | **OPEN** | ALL files (incl. namespace/deployments) still `fireai`; prompt's "already-correct 3" claim is stale |
| E4 | `deploy/observability/alertmanager.yml` | **PARTIAL** | Still `${VAR:default}` (lines 18-21,57-75); `monitoring/alertmanager.yml` already fixed → consolidate to ONE |
| E5 | `.github/workflows/deploy.yml` | **OPEN** | echo-placeholders for staging/prod/smoke/monitor |
| E6 | root `.gitignore` | **OPEN** | No `*.tfstate*`, `*.tfplan`, `crash.*`, `.terraform.tfstate.lock.info` |
| E7 | `nginx.conf` | **OPEN** | Brace count {=25 }=24; orphaned block after line 79 server |
| E8 | `docker-compose.copilot.yml` | **OPEN** | No deploy.resources / cap_drop / security_opt / read_only; line 221-222 duplicate GF_SECURITY_ADMIN_USER |
| WF-hygiene | multiple | **OPEN** | see §5 |

## 2. Execution Plan — WP-A (Authentication & Authorization, HIGHEST)
**A1** `api/shared_handlers.py::verify_api_key` — after `expected_key = os.environ.get(env_var, "")`, if empty AND `ENVIRONMENT`/`ENV` in {production, prod}: `raise HTTPException(401, "API key not configured")`. Keep current open behavior only for non-prod. *(verify callers first: routes.py middleware / hf-space usage)*
**A2** `backend/security_middleware.py::ApiKeyMiddleware.__call__` — compute `env = (_os.getenv("ENVIRONMENT") or _os.getenv("FIREAI_ENV") or "").lower()`; only honor `ENGINEERING_SERVICE_AUTH_DISABLED`/`FIREAI_AUTH_DISABLED` when env NOT in {production, prod, staging}; otherwise fall through to normal auth (lines 396-403 become conditional).
**A3** `api/routes.py` — add `require_role("admin")`-style guard ON TOP of `_require_api_key` for: `audit_verify`(~930), `cua_kill_switch_status`(998), `cua_kill_switch_activate`(1028), `cua_kill_switch_deactivate`(1054), `cua_rollback`(1076). Mirror the file's existing admin pattern (RBAC via `api/rbac.py:require_permission` or `request.state.fireai_role`/`backend.rbac.Role`) → 403 on non-admin. Re-run `tests/test_p0_backend_auth_patch.py` + `tests/test_audit_phase7_round5_fixes.py`.
**A4** (TS primary, Python defensive)
- `src/routes/studies.ts`: add `ownerApiKeyId?: string` to `TaskRecord`; in `handleStudyRun` set `ownerApiKeyId = apiKeyId` and `const taskId = crypto.randomUUID()` (replace `traceId` at line 64); in `handleStudyStatus` after `getTask` → `404/403` if `task.ownerApiKeyId && task.ownerApiKeyId !== apiKeyId`.
- `api/routes.py`: `run_study_async` embeds `api_key_id` (= sha256 of presented `x-api-key` header) in celery kwargs; `get_task_status` recomputes and returns 404/403 on mismatch.
**A5** `api/websocket.py` + `api/routes.py`
- (a) Origin allowlist in `scada_websocket_endpoint` from `ENGINEERING_SERVICE_CORS_ORIGINS` (mirror `cua_confirmation_ws.py:478-485`); close 1008 when set and Origin missing/mismatched.
- (b) Prefer `Sec-WebSocket-Protocol` subprotocol token (`websocket.headers.get("sec-websocket-protocol")`); keep query `token` as legacy fallback.
- (c) `routes.py:547`: `await scada_websocket_endpoint(websocket, token=api_key or "")` — single auth source (wrapper already validated the key).
**A6** `api/routes.py:649` (and `backend/app.py` CORS allow list if it lists it): remove `"x-active-key"` from allow_headers. No server read path exists; removal closes the remnant.

## 3. Execution Plan — WP-B (Python Runtime) & WP-C (DB)
**B1** `worker/tasks.py:124-132` — delete entire 2nd block (2nd "Starting ETAP integration" log, `from etap_integration.etap_provider import ETAPProvider`, `provider = ETAPProvider()`, `result = provider.execute_command(...)`, 2nd "Completed" log). Keep single `get_etap_provider()` path + SUCCESS/FAILURE update_state.
**B2** `api/websocket.py:382` — `if _is_token_blacklisted(jti):` → `if await _is_token_blacklisted(jti):`. Inspect `_validate_ws_token`/`authenticate_ws_request` sync/async and align (make the enclosing helper async if its callers accommodate; no event-loop hacks).
**B3** `api/websocket.py::SCADALiveFeed` — instantiate `ETAPScadaBridge()` once (lazily, stored on feed instance); in `_generate_scada_data` guard with cheap `is_connected()`; log failure on first occurrence + on state change only (module flag / last-state), never per-second; keep synthetic fallback `is_simulated: True`.
**B4** `worker/tasks.py:152-219` — either wire real computation through `execute_study_logic` OR `raise NotImplementedError("<clear message>")`; delete placeholder numpy inversion loop; preserve update_state contract.
**B5** `services/study_service.py:213-227` — module-level single `ThreadPoolExecutor(max_workers=…)` + reuse (no per-call pool creation). Verify no deadlock (run a study after change).
**B6** `services/api_key_store.py` — `_init_cipher`: if `API_KEY_ENCRYPTION_KEY` missing, persist a generated key to `_DATA_DIR/.keyring` (0o600) as documented fallback and warn loudly (stable across restarts). `api/settings.py`: route sync `api_key_store.*` calls through `asyncio.to_thread` (no event-loop block).
**B7** `services/otp_store.py` — pick ONE honestly: wire `_get_redis()` into `issue_otp`/`verify_otp`/`invalidate_otp` + startup warning when Redis missing, OR keep in-memory and fix docstring + warn at import. `email_send_log.py` is already honest (Redis best-effort).
**B8** `services/cache_service.py:201-204` — delete unreachable duplicate fallback; add `_MAX_MEMORY_ENTRIES` cap with eviction (oldest/expired) on set.
**B9** `api/routes.py` — delete 2nd `include_router(feature_flags_router)` (line 792) and 2nd `include_router(autodesk_connectors_router)` (lines 784-786).
**C1** Alembic — delete dead `alembic/` dir (keep `alembic.ini`, `script_location=migrations`); set `006_add_tenant_id_and_rls.down_revision = "006_add_scada_gis_email"` → exactly ONE head. Verify: `alembic heads` (one) + `alembic upgrade head --sql`.
**C2** `api/database.py::init_db` — remove `Base.metadata.create_all` (line 385); connectivity-only init + startup check reading `alembic_version` that fails loudly on in-prod head mismatch.
**C3** Add `.github/workflows/db-backup.yml`: daily cron + workflow_dispatch → runs `scripts/backup/postgres_backup.sh` with real S3 creds via GitHub Secrets; monthly restore-drill job using `scripts/restore/postgres_restore.sh`.

## 4. Execution Plan — WP-D (TypeScript / Frontend)
**D1** `src/core/engineeringService.ts` — restructure so 4xx throws are NOT caught by the retry `catch`. Introduce a sentinel (e.g. `class ClientError extends Error {}`) thrown for `res.status >= 400 && res.status < 500` AFTER `clearTimeout`; the `catch` only handles transport/5xx (`recordProviderFailure` stays for 5xx/network only, not 4xx).
**D2** `src/mastra/lib/model-config.ts` — add `ProviderPublicConfig = { name, baseURL, model, apiKeyMasked, hasKey }`; `getProviderStatus()` returns masked sets (`'***' + key.slice(-4)`), never raw. `src/mastra/tools/provider-settings-tool.ts` returns public shape only. Verify no consumer needs the raw key.
**D3** `tsconfig.json` — delete line 8 (`"noImplicitAny": false`); run `npx tsc --noEmit`; fix EVERY resulting error with real types (no `as any`). Do last within WP-D to limit blast radius.
**D4** `src/mastra/lib/model-config.ts:65` — pin `@ai-sdk/openai` to a version whose `LanguageModelV1` satisfies Mastra's `MastraLanguageModelV2`, then remove `as unknown as LanguageModel`. Confirm no other cast remains (`grep "as " src/mastra --include=*.ts`). (Note: only 1 cast site remains today, not 22.)
**D5** NO deletion without confirmation. Add `docs/REPO_SEPARATION_RECOMMENDATIONS.md` noting `todo-app/`, `cloud/FRONTEND*` belong in separate repos. `login.html` ≠ `index.html` (different SHA-256) → do NOT auto-delete; flag to user.
**D6** `src/core/circuitBreaker.ts` — add `halfOpenInProgress` to `BreakerState`; in `isCircuitOpen`, when cooldown elapsed → set half-open + flag so only ONE probe passes; subsequent callers see flag and stay blocked. Clear on `recordProviderSuccess/Failure`.
**D7** `src/core/tokenStats.ts` — add `MAX_RECORDS` (e.g. 1000); in `recordTokenUsage` after `_calls.push(...)`, `if (_calls.length > MAX_RECORDS) _calls.shift()`.
**D8** `src/mastra/prompts.ts` — add pinned `js-yaml` (+ `@types/js-yaml`) to `package.json`, replace `parseSimpleYaml` (lines 45-188) with `yaml.load(...)`; delete dead if/else branches; keep LangWatch-first → local fallback flow.

## 5. Execution Plan — WP-E (Infra/Deploy) & WP-F (Hygiene)
**E1** root `Dockerfile` — before deleting lines 1-162, check `docker-compose*.yml`/`vercel.json`/HF workflows for `dockerfile:` references. Line 123 comment says use `hf-space/app.py`; HF already ships `Dockerfile.hf`. After confirming, strip lines 1-162 (old HF Space pipeline), keep the 164-310 multi-stage build. Validate `docker compose config -q`.
**E2** `terraform/backend.tf` — close the `azurerm` block (`}` after `use_azuread_auth = true`), delete trailing `backend "local"` block (lines 34-49). Then `terraform fmt -check -recursive terraform/ && terraform validate` (and `terraform init -backend-config=environments/<env>/backend.hcl` if terraform present).
**E3** `deploy/k8s/` — rewrite ALL 9 manifests (configmap, ingress, network-policy, pdb, secret, service-api AND namespace, deployment-api, deployment-worker) `fireai` → `etap-ai` with correct env keys (FIREAI_* → ETAP/ENGINEERING_*). *Prompt's "3 already-correct" premise is STALE — all 9 are fireai today.*
**E4** Alertmanager — consolidate to ONE config (keep `monitoring/alertmanager.yml`), delete `deploy/observability/alertmanager.yml`. Remove ALL `${VAR:default}` syntax (still present in deploy/observability lines 18-21, 57-75). Document envsubst/Helm templating at deploy.
**E5** `.github/workflows/deploy.yml` — replace echo-placeholders (staging/prod/smoke/monitor, lines ~98-159) with real steps (build → push → `kubectl set image`/`vercel --prod`) OR delete. Never echo-only success.
**E6** `.gitignore` — add `*.tfstate`, `*.tfstate.*`, `*.tfplan`, `crash.log`, `crash.json`, `.terraform.tfstate.lock.info` (and check `terraform/.gitignore`).
**E7** `nginx.conf` — brace imbalance (25 `{` vs 24 `}`); remove the orphaned block (duplicate "HTTP→HTTPS" server around lines 79-93). Validate via `nginx -t` (if available) or structural brace recount.
**E8** `docker-compose.copilot.yml` (+ base compose) — add `deploy.resources.limits` + `security_opt: [no-new-privileges:true]` + `cap_drop: [ALL]` + `read_only: true` (where images support). Remove duplicate `GF_SECURITY_ADMIN_USER` env (lines 221-222). Validate `docker compose config -q`.

**WP-F hygiene**
1. `scada_etap_consumer.py` — delete or wire to real broker config (no hardcoded `localhost:1883`); recommend deletion after confirming no consumers.
2. `services/cache_service.py::get_study_cache` — drop `async` (no I/O); update callers in `study_service.py` to drop `await`.
3. `api/websocket.py:32` module `active_connections` — remove if dead; `:339` import-time `SCADALiveFeed()` → lazy (folds into **B3**).
4. `worker/celery_app.py:73-75` — remove global `task_soft_time_limit`/`task_time_limit` (hits heartbeat); set per-task limits on study/ETAP tasks only via route kwargs / `time_limit`/`soft_time_limit`.
5. `engineering_service.py` — reload already gated to development; ADD: refuse `host=0.0.0.0` when ENVIRONMENT ∈ {production, prod, staging} unless `HOST` explicitly set.
6. Root dev scripts (`indexer.py`, `_scan_tool.py`, `run_git.py`, `VALIDATE_FIXES.py`, `verify_agents.py`, `fix_agent_structures.py`, `test_agents.py`) — move under `scripts/` or mark dev-only (check git history for duplicate `fix_future_imports.py`/`setup_rules.py`). Keep imports intact.
7. Two FastAPI apps (`backend_app.py`, `api/routes.py:app`, `api/refactored_service.py`) + two orchestrators (`agents/orchestrator.py`, `agents/ahmed_etap_orchestrator.py`) — pick ONE canonical each (`routes.py` app + `orchestrator.py` per AGENTS.md §Agent Architecture); add `# DEPRECATED` banner to the others (no deletion without approval).

## 6. Verification Commands (existing in repo — not assumed)
- **Syntax gate:** `python -m compileall api backend security worker services core agents`
- **Tests:** `pytest tests/ -x -q --tb=short` (pytest in pyproject `[test]` extra)
- **Lint:** `python -m ruff check api backend security worker services core agents --config ruff.toml`
- **Alembic:** `alembic heads` → exactly ONE; `alembic upgrade head --sql` succeeds
- **TypeScript:** `npm run lint` (`tsc --noEmit`); `npm test` (`vitest run`); scenarios `npm run test:scenarios`
- **Infra:** `docker compose config -q` (after E8/E1); `terraform fmt -check -recursive terraform/ && terraform validate` (if terraform present); brace-count/`nginx -t` (E7)
- **Targeted regressions:** `pytest -q tests/test_scada_websocket.py tests/test_p0_backend_auth_patch.py tests/test_audit_phase7_round5_fixes.py tests/test_cache_service.py tests/test_engineering_service.py` + vitest `tests/engineering-service.test.ts`

## 7. Order, Commit Policy & Risks
**Phase order:** re-verify DO-NOT-TOUCH (done) → **1**) WP-A → **2**) WP-B → **3**) WP-C → **4**) WP-D (D3/D4 last) → **5**) WP-E → **6**) WP-F.
- **One finding = one logical commit** ONLY if user explicitly authorizes; otherwise ALL changes remain uncommitted.
- After every package: run the applicable §6 checks; on failure → halt → re-read → correct → re-run. No `as any`/`type: ignore`/`# type: ignore` / broad `except Exception` to silence failures.
- **Deliverable:** per-finding `FIXED / SKIPPED (already fixed) / BLOCKED (<reason>)` + files changed + verification evidence (no fix claimed without evidence).

**Risks / code-drift disclosures:**
1. **E3 scope** exceeds the prompt's premise — all 9 `deploy/k8s` files use `fireai`, not just the 6 "stale" ones.
2. **D4 site count** is 1 (`model-config.ts:65`), not 22 — most casts were already removed.
3. **B2** requires careful sync→async alignment (`_is_token_blacklisted` / `_validate_ws_token`).
4. **C1** deleting `alembic/` is safe (alembic.ini→`migrations`); confirm no `env.py`-in-`alembic` dependency first.
5. **D5 `login.html`** deletion BLOCKED (not byte-identical to `index.html`) — needs user decision.
6. **js-yaml** is a new pinned dependency (explicitly permitted by remediation rule #4).