# Duplicate Functions Audit — Executive Summary

**Generated:** 2026-07-26  
**Codebase:** ETAP-AI-WORK + AhmedETAP-Platform  
**Branch:** feature/duplicate-functions-audit  
**Skill:** finding-duplicate-functions (from superpowers-lab)

---

## Audit Scope

| Metric | Value |
|--------|-------|
| Python functions extracted | 5,486 |
| TypeScript/JS functions extracted | 182 |
| Functions categorized | 2,176 (focused on high-risk zones) |
| Categories analyzed | 28 |
| Exact-name duplicates | 142 names across 478 occurrences |
| Semantic duplicate groups found | **120** |
| HIGH confidence groups | 68 |
| MEDIUM confidence groups | 41 |
| LOW confidence groups | 11 |

---

## Top 10 Highest-Impact Duplications

| # | Duplicate Group | Confidence | Estimated Lines | Recommended Action |
|---|----------------|-----------|-----------------|--------------------|
| 1 | **LoadFlowSolver class** — 520-line class duplicated in `consolidated_solver.py` and `load_flow.py` (character-for-character identical) | HIGH | ~520 | **Delete `consolidated_solver.py` entirely** |
| 2 | **7 Retry implementations** across 4 files — hand-rolled, decorator, tenacity, class-based, context manager | HIGH | ~200 | **Keep `core/retry.py` (tenacity) + `engine/resilience.py:RetryHandler`** |
| 3 | **3 Cache classes** (CacheService, StudyCache, CalculationCache) — same CRUD pattern, different backends | HIGH | ~350 | **Merge into single `CalculationCache` with Redis adapter** |
| 4 | **Akamai ↔ Cloudflare CDN protection** — 80% structural overlap, identical middleware, IP extraction, secret verification | HIGH | ~300 | **Create unified `CDNProtectionMiddleware` with provider configs** |
| 5 | **Langfuse ↔ LangWatch observability** — 18 functions near-identical across both tracker backends | HIGH | ~200 | **Create `_observability_base.py` abstract tracker** |
| 6 | **Vision module `_to_pil_image`** — Gemini & OpenCV have stale inline copies despite `_vision_base` being created to eliminate them | HIGH | ~25 | **Delegate to `_vision_base.to_pil_image`** |
| 7 | **5 API key validation implementations** — all compare `X-API-Key` to env secret | HIGH | ~50 | **Keep `shared_handlers.verify_api_key` as single source** |
| 8 | **Cross-repo duplication** — AhmedETAP-Platform has byte-for-byte copies of ETAP-AI-WORK core files | HIGH | 1000+ | **Extract shared `etap-engineering-core` pip package** |
| 9 | **11 Email fallback HTML generators** — identical HTML wrapper boilerplate | HIGH | ~100 | **Extract `_fallback_html_wrapper(title, body_html, color)`** |
| 10 | **14 Stats/statistics/get_stats methods** — each module reimplements operational stats snapshot | HIGH | ~150 | **Consolidate through `core/metrics.py` unified API** |

---

## Category Breakdown of Duplicate Groups

| Category | HIGH Groups | MEDIUM Groups | LOW Groups | Total |
|----------|------------|---------------|------------|-------|
| async-utils | 3 | 2 | 0 | 5 |
| caching | 9 | 2 | 2 | 13 |
| security | 6 | 3 | 2 | 11 |
| integration | 4 | 6 | 2 | 12 |
| data-transform | 3 | 1 | 2 | 6 |
| numerical | 4 | 2 | 1 | 7 |
| validation | 6 | 5 | 5 | 16 |
| vision+email | 6 | 2 | 1 | 9 |
| string+error+crypto | 5 | 3 | 3 | 11 |
| logging+config+event | 5 | 3 | 0 | 13 |
| electrical-eng+digital-twin | 5 | 4 | 1 | 10 |
| **TOTAL** | **68** | **41** | **11** | **120** |

---

## Estimated Impact

- **Total lines of code that could be eliminated**: ~800-1,200 (within ETAP-AI-WORK alone)
- **Cross-repo duplication (ETAP ↔ HF)**: ~1,000+ lines of identical files
- **Quick wins (can be done in <1 hour each)**:
  1. Delete `consolidated_solver.py` (520 lines)
  2. Delegate Gemini/OpenCV `_to_pil_image` to `_vision_base` (2 function changes)
  3. Move SYSTEM_PROMPT to `_vision_base.SYSTEM_PROMPT` (120 lines saved)
  4. Extract `_fallback_html_wrapper` (100 lines saved)
  5. Remove `send_email` wrapper in resend_email.py (1-line removal)

---

## Methodology

This audit followed the **finding-duplicate-functions** skill from [superpowers-lab](https://github.com/obra/superpowers-lab):

1. **Phase 1 — Extract**: Created Python extraction script (skill only covered TS/JS), ran against both repos. Found 5,668 total function definitions.
2. **Phase 2 — Categorize**: Dispatched 7 haiku subagents in parallel to categorize 2,176 functions into 29 domain categories.
3. **Phase 3 — Split**: Used `prepare-category-analysis.sh` to create per-category JSON files.
4. **Phase 4 — Detect**: Dispatched 11 opus subagents in parallel for semantic duplicate detection across 11 category groups.
5. **Phase 5 — Report**: Used `generate-report.sh` to produce prioritized markdown report grouped by confidence level.
6. **Phase 6 — Review**: This executive summary for human review and consolidation decisions.

---

## Next Steps

For each HIGH confidence duplicate:
1. Verify the recommended survivor has test coverage
2. Update all callers to use the survivor function
3. Delete the duplicate implementations
4. Run full test suite to verify no regressions
5. Commit changes following the secure push protocol (feature branch → PR)

For MEDIUM confidence duplicates:
- Read full implementations before deciding
- Some may intentionally differ in edge case handling
- Flag for human review if uncertain

---

*Full detailed report: `/home/z/my-project/duplicate-audit/duplicates-report.md`*  
*All analysis artifacts: `/home/z/my-project/duplicate-audit/`*
