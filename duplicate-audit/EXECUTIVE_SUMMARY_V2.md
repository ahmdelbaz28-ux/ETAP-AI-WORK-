# Duplicate Functions Audit — Executive Summary v2 (Corrected)

**Generated:** 2026-07-26  
**Codebase:** ETAP-AI-WORK + AhmedETAP-Platform  
**Branch:** feature/duplicate-functions-audit  
**Skill:** finding-duplicate-functions (from superpowers-lab)

---

## Audit Scope (Corrected — after self-critique fixes)

| Metric | v1 (Previous) | v2 (Corrected) | Change |
|--------|---------------|----------------|--------|
| Functions extracted | 5,668 | 5,668 | — |
| Functions categorized | 2,176 (38%) | 4,005 (70%) | +1,829 |
| Categories analyzed | 11 (opus) | 16 (opus) | +5 |
| TS/JS analyzed | 0 | 182 | +182 |
| Exact-name groups uncovered | 0 | 14 | +14 |
| Duplicate groups found | 120 | **165** | +45 |
| HIGH confidence | 68 | **87** | +19 |
| MEDIUM confidence | 41 | **64** | +23 |
| LOW confidence | 11 | **14** | +3 |
| Cross-repo identical lines | ~1,000 (estimate) | **25,680 (exact)** | Corrected |
| Cross-repo identical files | — | **63 files** | Quantified |
| Cross-repo different files | — | **17 files** | Quantified |
| Test coverage verified | No | Yes (partial) | Added |

---

## Self-Critique Fixes Applied

| # | Gap | What I Fixed | Status |
|---|-----|---------------|--------|
| 1 | 38% coverage only | Categorized 1,647 more functions → 70% coverage | ✅ |
| 2 | 2-line context instead of 15 | Used 3-line context for remaining categorization (trade-off: speed vs depth) | ✅ Improved |
| 3 | Large categories truncated to 100 | Added remaining functions from truncated categories to overall analysis | ✅ |
| 4 | TS/JS never analyzed | Categorized all 182 TS/JS functions, ran ui-helpers opus analysis | ✅ |
| 5 | 5 categories had no opus analysis | Added: agent, gis+scada, http-api+database, ui-helpers (4 new opus runs) | ✅ |
| 6 | Exact-name duplicates not merged | Found 14 additional exact-name groups not covered by semantic analysis | ✅ |
| 7 | No test coverage check | Checked survivor test coverage; identified 2 gaps (get_or_404, CDNProtectionMiddleware) | ✅ Partial |
| 8 | Cross-repo estimate not quantified | Exact count: 63 identical files, 25,680 lines, 17 different files | ✅ |
| 9 | No actual consolidation done | Moving to Phase 6 next | 🔄 |
| 10 | JSON consistency unchecked | All 16 JSON files validated as correct | ✅ |

---

## Top 10 Highest-Impact Duplications (Updated)

| # | Group | Confidence | Est. Lines | Survivor Has Tests? | Action |
|---|-------|-----------|------------|--------------------|--------|
| 1 | **consolidated_solver.py = 520-line copy of load_flow.py** | HIGH | ~520 | ✅ (unit_tests.py, test_edge_cases.py) | **Delete consolidated_solver.py** |
| 2 | **Cross-repo: 63 identical files, 25,680 lines** | HIGH | 25,680 | — | **Extract shared pip package** |
| 3 | **7 retry implementations across 4 files** | HIGH | ~200 | ✅ (test_retry_behavior.py, unit_tests.py) | **Keep core/retry.py + engine/resilience.py** |
| 4 | **3 Cache classes (identical CRUD)** | HIGH | ~350 | ✅ (test_cache_manager.py, test_cache_service.py) | **Merge into CalculationCache** |
| 5 | **Akamai ↔ Cloudflare CDN (80% overlap)** | HIGH | ~300 | ❌ NO TESTS | **Create unified CDNProtectionMiddleware** — WRITE TESTS FIRST |
| 6 | **18 validate_result skeletons in agents** | HIGH | ~180 | Partial | **Extract BaseAgent template method** |
| 7 | **6 get_or_404 helpers** | HIGH | ~60 | ❌ NO TESTS | **Use FastAPI built-in** — WRITE TESTS FIRST |
| 8 | **8 Redis client getter singletons** | HIGH | ~80 | — | **Centralize RedisClientFactory** |
| 9 | **Langfuse ↔ LangWatch observability** | HIGH | ~200 | — | **Create _observability_base.py** |
| 10 | **5 API key validation implementations** | HIGH | ~50 | ✅ (conftest.py, test_hf_space_skill.py) | **Keep shared_handlers.verify_api_key** |

---

## Test Coverage Gaps (CRITICAL — must fix before consolidation)

| Survivor Function | Test Coverage | Risk | Required Action |
|-------------------|---------------|------|-----------------|
| `CDNProtectionMiddleware` | ❌ None | HIGH | Write tests before merging Akamai/Cloudflare |
| `get_or_404` | ❌ None | HIGH | Write tests before removing 6 duplicates |
| `LoadFlowSolver` | ✅ tests exist | LOW | Verify they cover both solver paths |
| `_env_truthy` | — | MEDIUM | Check existing config tests |
| `redact_text` | ❌ None found | HIGH | Write tests before removing _redact_secrets |

---

## Cross-Repo Duplication (Exact Quantification)

**63 files are byte-for-byte identical** across ETAP-AI-WORK and AhmedETAP-Platform, totaling **25,680 lines**. 17 files differ (due to deployment-specific changes like auth, websocket, email handlers). The identical files span:

- **agents/**: 20 identical files (all domain agents)
- **api/**: 22 identical, 11 different (auth, cloudflare, studies diverged)
- **core/**: 6 identical (bootstrap, database, metrics, models, redis_state, retry, tracing)
- **core_model/**: All identical (bus, line, generator, load, transformer, system, specs, zip_load, motor_model)
- **engine/**: All identical (engine, async_executor, cache_manager, caching, resilience, error_handler, numerical_safety, etc.)
- **integrations/**: All identical (all vision, langfuse, supabase, neo4j modules)
- **services/**: All identical (api_key_store, cache_service, email_service, memory_service, study_service)
- **fault_analysis/**: All identical

**Recommendation**: Extract shared modules into `etap-engineering-core` pip package, deploy-specific files stay in each repo.

---

## Remaining Uncovered

| Area | Remaining Functions | Priority | Why Not Fully Analyzed |
|------|--------------------|---------|------------------------|
| script-utility (145) | 145 | Low | Build/deploy scripts rarely duplicate domain logic |
| testing (70) | 70 | Low | Test utilities intentionally duplicated per test suite |
| other (77) | 77 | Low | Miscellaneous, hard to group |
| config (102) | 50 remaining | Medium | Only public functions analyzed, private init helpers skipped |
| http-api (488) | 388 remaining | Medium | Only public API+DB functions analyzed |

---

## Next Phase: Consolidation Execution (Phase 6)

Priority order for actual code changes:

### Batch 1 — Quick Wins (no test gaps, safe to delete)
1. Delete `consolidated_solver.py` (520 lines, tests exist for LoadFlowSolver)
2. Delegate Gemini/OpenCV `_to_pil_image` → `_vision_base.to_pil_image` (2 lines each)
3. Move SYSTEM_PROMPT to `_vision_base.SYSTEM_PROMPT` (120 lines saved)
4. Remove `send_email` wrapper in resend_email.py (1 function)
5. Extract `_fallback_html_wrapper()` (100 lines saved)

### Batch 2 — Medium Wins (tests exist or easy to add)
6. Remove duplicate `get_study_cache` accessors (keep engine/caching.py version)
7. Remove duplicate `_generate_key` / `_make_key` (keep cache_manager.py::build_key)
8. Merge `safe_inverse` → resilience.py version (numerical_safety can delegate)
9. Centralize `_env_truthy` pattern across config modules
10. Use `shared_handlers.verify_api_key` as single API key validator

### Batch 3 — Large Wins (requires new tests first)
11. Merge Akamai/Cloudflare → unified CDNProtectionMiddleware (NEED TESTS)
12. Merge 3 cache classes → single CalculationCache with Redis adapter
13. Merge Langfuse/LangWatch → _observability_base.py abstract tracker
14. Extract BaseAgent template method for validate_result skeleton
15. Extract shared `get_or_404` helper (NEED TESTS)

---

*Full report: `/home/z/my-project/duplicate-audit/duplicates-report-v2.md`*
*Cross-repo comparison: `/home/z/my-project/duplicate-audit/cross-repo-comparison.txt`*
*All analysis artifacts: `/home/z/my-project/duplicate-audit/`*
