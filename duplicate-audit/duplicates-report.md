# Duplicate Functions Report

Generated: 2026-07-25 20:01

## Summary

| Confidence | Count | Action |
|------------|-------|--------|
| HIGH | 68 | Consolidate immediately |
| MEDIUM | 41 | Investigate further |
| LOW | 11 | Review if time permits |

---

## HIGH Confidence Duplicates

These functions are definitely duplicates. Consolidate them.

### Retry a failing operation with exponential backoff delay

**Category:** async-utils

**Functions:**
- `retry_with_backoff` in `ETAP-AI-WORK/integrations/_vision_base.py:97` - Direct function (not decorator) that takes make_request/parse_response callables; hand-rolled exponential backoff using time.sleep; returns error dict on exhaustion rather than raising
- `retry_with_backoff` in `ETAP-AI-WORK/integrations/resilience.py:58` - Decorator factory with max_delay cap and on_retry callback; hand-rolled exponential backoff; raises on exhaustion; specifically designed for CUA Loop transient failures
- `decorator` in `ETAP-AI-WORK/integrations/resilience.py:80` - Inner decorator function of integrations/resilience.retry_with_backoff; part of the same retry mechanism
- `network_retry` in `ETAP-AI-WORK/core/retry.py:36` - Tenacity-based decorator for network/IO operations; exponential backoff + jitter; retries on ConnectionError/TimeoutError/OSError
- `skill_retry` in `ETAP-AI-WORK/core/retry.py:70` - Tenacity-based decorator for skill/module loading; shorter backoff (0.5x multiplier); retries on ImportError/ModuleNotFoundError
- `bounded_retry` in `ETAP-AI-WORK/core/retry.py:101` - Tenacity-based general-purpose decorator; stops on either attempt limit or elapsed time limit; configurable exception types
- `execute` in `ETAP-AI-WORK/engine/resilience.py:111` - RetryHandler class method; most feature-rich implementation with configurable exponential_base, jitter, retryable_exceptions; tracks total_calls and total_retries
- `async_execute` in `ETAP-AI-WORK/engine/resilience.py:177` - RetryHandler async method; mirrors execute() for async callables; uses asyncio.sleep instead of time.sleep
- `with_retry` in `ETAP-AI-WORK/engine/resilience.py:236` - Decorator factory wrapping RetryHandler.execute; provides decorator API for the class-based retry
- `decorator` in `ETAP-AI-WORK/engine/resilience.py:281` - Inner decorator of with_retry; wraps function calls with RetryHandler and optional circuit breaker integration
- `async_retry` in `ETAP-AI-WORK/engine/async_executor.py:569` - Simple _RetryContext manager; fixed delay (no exponential backoff); no configurable exception filtering; no jitter

**Differences:** Seven distinct retry implementations across 4 files. (1) integrations/_vision_base.py:retry_with_backoff is a direct function, not a decorator, returns error dicts instead of raising. (2) integrations/resilience.py:retry_with_backoff is a decorator factory with max_delay cap and on_retry callback. (3) core/retry.py uses the tenacity library for network_retry/skill_retry/bounded_retry with proper jitter, configurable exception types, and time limits. (4) engine/resilience.py:RetryHandler is the most complete class-based approach with exponential_base, jitter, tracking stats, and both sync/async variants. (5) engine/async_executor.py:async_retry is the simplest — fixed delay, no exponential backoff, no exception filtering.

**Recommendation:** Keep `core/retry.py (tenacity-based decorators) + engine/resilience.py:RetryHandler (for programmatic/class-based usage)` - The tenacity-based core/retry.py decorators (network_retry, skill_retry, bounded_retry) are the most robust and well-tested approach for decorator-style usage. The engine/resilience.py RetryHandler is the best class-based approach when programmatic retry control is needed (e.g., circuit breaker integration). The hand-rolled implementations in integrations/_vision_base.py and integrations/resilience.py should be migrated to use bounded_retry or RetryHandler. The simple async_retry context manager in async_executor.py should be replaced with a proper exponential backoff retry.

---

### Enforce a timeout/deadline on an operation, raising if it exceeds the limit

**Category:** async-utils

**Functions:**
- `async_timeout` in `ETAP-AI-WORK/engine/async_executor.py:565` - Returns _TimeoutContext sync context manager; uses time.monotonic() to track deadline; checks expiration only on __exit__, does NOT actively cancel running work
- `__enter__` in `ETAP-AI-WORK/engine/async_executor.py:515` - Entry for _TimeoutContext; sets deadline via time.monotonic()
- `__exit__` in `ETAP-AI-WORK/engine/async_executor.py:518` - Exit for _TimeoutContext; raises TimeoutError if deadline exceeded at exit time
- `remaining` in `ETAP-AI-WORK/engine/async_executor.py:526` - Property returning remaining seconds before _TimeoutContext deadline
- `expired` in `ETAP-AI-WORK/engine/async_executor.py:530` - Property checking if _TimeoutContext deadline has passed
- `_timeout` in `ETAP-AI-WORK/engine/async_executor.py:700` - Contextmanager decorator using a watchdog thread to enforce timeout; actively interrupts by raising TimeoutError from a separate thread
- `_watchdog` in `ETAP-AI-WORK/engine/async_executor.py:706` - Watchdog thread helper for _timeout; waits then sets TimeoutError if operation still running
- `enforce_deadline_ms` in `ETAP-AI-WORK/acp_runtime/acp/runtime/deadline.py:22` - Async function that wraps a coroutine with anyio.move_on_after; properly cancels the coroutine on timeout; raises DeadlineExceeded (custom exception); uses milliseconds
- `deadline_scope` in `ETAP-AI-WORK/acp_runtime/acp/runtime/deadline.py:62` - Async context manager yielding an anyio.CancelScope with deadline; lower-level primitive for manual scope management; uses milliseconds
- `cancellable` in `ETAP-AI-WORK/acp_runtime/acp/runtime/cancel.py:20` - Async context manager yielding a cancel scope with optional deadline_ms; wraps anyio.move_on_after or anyio.CancelScope; allows external cancellation

**Differences:** Three distinct timeout approaches: (1) _TimeoutContext is a simple sync context manager that only checks expiration on exit — it does NOT cancel running work, making it unreliable for long-running operations. (2) _timeout/_watchdog uses a separate thread to actively enforce timeout but is threading-based and does not integrate with async cancellation. (3) acp_runtime uses anyio.move_on_after for proper async cancellation — it actually cancels the running coroutine and raises DeadlineExceeded. The acp_runtime approach is the most correct for async code, while _TimeoutContext is a passive check and _timeout is a threading hack.

**Recommendation:** Keep `acp_runtime/acp/runtime/deadline.py:enforce_deadline_ms + deadline_scope` - The anyio-based deadline enforcement is the most correct approach — it properly cancels running coroutines on timeout. The _TimeoutContext is unreliable (passive check only), and _timeout uses threading which is fragile and does not integrate with async. For sync code, Python's built-in asyncio.wait_for or signal.alarm should be preferred. The _TimeoutContext and _timeout implementations should be deprecated in favor of the acp_runtime deadline primitives.

---

### Return/create the StudyCache singleton instance

**Category:** caching

**Functions:**
- `get_study_cache` in `ETAP-AI-WORK/services/cache_service.py:209` - Get or create the shared StudyCache singleton — service-layer accessor
- `get_study_cache` in `ETAP-AI-WORK/core/bootstrap.py:433` - Return the global study cache singleton instance — bootstrap-layer accessor
- `get_study_cache` in `ETAP-AI-WORK/engine/caching.py:498` - Returns or creates a StudyCache instance configured with Redis URL — engine-layer factory

**Differences:** All three return the same StudyCache singleton but from different architectural layers. cache_service.py and bootstrap.py are thin accessors that likely delegate to caching.py::get_study_cache as the actual factory. The bootstrap version may initialize the singleton earlier in the app lifecycle.

**Recommendation:** Keep `ETAP-AI-WORK/engine/caching.py::get_study_cache` - The engine-layer factory is the canonical creator. Remove the redundant accessor wrappers in cache_service.py and bootstrap.py; import the singleton directly from caching.py where needed.

---

### Generate a deterministic cache key from domain parameters

**Category:** caching

**Functions:**
- `_generate_key` in `ETAP-AI-WORK/services/cache_service.py:77` - Generate cache key from study type and parameters — StudyCache domain
- `_make_key` in `ETAP-AI-WORK/engine/caching.py:213` - Create deterministic cache key from study type and parameters — StudyCache domain
- `build_key` in `ETAP-AI-WORK/engine/cache_manager.py:289` - Construct deterministic cache key from component, method, and params hash — CalculationCache domain

**Differences:** The first two (_generate_key and _make_key) are near-identical — both hash study type + parameters into a cache key string. build_key differs by using component + method + params hash as inputs (CalculationCache domain) and is more elaborate (289-341 lines vs ~11 lines). All serve the same purpose of turning domain inputs into a stable, hash-based cache key.

**Recommendation:** Keep `ETAP-AI-WORK/engine/cache_manager.py::build_key` - build_key is the most general and feature-rich implementation. Extract it into a shared utility (e.g., engine/cache_utils.py::build_cache_key) that accepts configurable input fields, then replace _generate_key and _make_key with calls to it.

---

### Retrieve a cached value by key from a cache backend

**Category:** caching

**Functions:**
- `get` in `ETAP-AI-WORK/services/cache_service.py:96` - Retrieve cached value by key — Redis primary, in-memory fallback
- `get` in `ETAP-AI-WORK/engine/cache_manager.py:99` - Retrieve cached value by key with LRU promotion — CalculationCache, in-memory only
- `get` in `ETAP-AI-WORK/engine/caching.py:262` - Get cached study result by study type and parameters — StudyCache, Redis + fallback
- `get` in `ETAP-AI-WORK/engine/caching.py:69` - Low-level: get value from in-memory dict by key — internal building block for StudyCache

**Differences:** Four get() implementations across three modules. cache_service.py::get and caching.py::get (line 262) both use Redis with in-memory fallback — likely near-identical logic. cache_manager.py::get is in-memory only with LRU promotion. caching.py::get (line 69) is a low-level in-memory dict lookup. The core intent (retrieve cached value by key) is identical; implementations differ in backend choice and feature sophistication.

**Recommendation:** Keep `ETAP-AI-WORK/engine/cache_manager.py::get` - cache_manager.py::CalculationCache is the most feature-complete (LRU, tags, size eviction). Consolidate all caching into a single CacheManager class that supports both study and calculation domains. The Redis fallback logic from caching.py can be integrated as a backend adapter. Remove cache_service.py::get entirely (it duplicates caching.py).

---

### Store a value in cache with TTL

**Category:** caching

**Functions:**
- `set` in `ETAP-AI-WORK/services/cache_service.py:144` - Store value with TTL — Redis primary, in-memory fallback
- `set` in `ETAP-AI-WORK/engine/cache_manager.py:123` - Store value with TTL, tags, and size-based eviction — CalculationCache
- `set` in `ETAP-AI-WORK/engine/caching.py:304` - Cache study result with study type, parameters, and TTL — StudyCache, Redis + fallback
- `set` in `ETAP-AI-WORK/engine/caching.py:83` - Low-level: set key with optional TTL in in-memory dict — internal building block

**Differences:** Four set() implementations mirroring the get() pattern. cache_service.py::set and caching.py::set (line 304) are near-identical (Redis + fallback). cache_manager.py::set adds tags and size-based eviction. caching.py::set (line 83) is the low-level in-memory store. All store a key-value pair with optional TTL.

**Recommendation:** Keep `ETAP-AI-WORK/engine/cache_manager.py::set` - Same as get() — consolidate all cache storage into the feature-rich CalculationCache/CacheManager in cache_manager.py. Add Redis backend support and domain-specific key builders. Remove the duplicate implementations in cache_service.py and the high-level set in caching.py.

---

### Remove a single cache entry by key

**Category:** caching

**Functions:**
- `invalidate` in `ETAP-AI-WORK/engine/cache_manager.py:157` - Remove specific cache entry by key — CalculationCache
- `invalidate` in `ETAP-AI-WORK/engine/caching.py:341` - Invalidate specific cached study result — StudyCache
- `delete` in `ETAP-AI-WORK/engine/caching.py:92` - Delete key from in-memory cache — low-level StudyCache internal
- `delete` in `ETAP-AI-WORK/services/otp_store.py:99` - Delete OTP record from in-memory cache — OTP-specific domain

**Differences:** All remove a single entry by key. cache_manager.py::invalidate includes size accounting. caching.py::invalidate (line 341) invalidates study-specific entries (Redis + in-memory). caching.py::delete (line 92) is low-level in-memory removal. otp_store.py::delete is OTP-domain specific. The OTP variant has different semantics (verification workflow) and should stay separate.

**Recommendation:** Keep `ETAP-AI-WORK/engine/cache_manager.py::invalidate` - Consolidate cache_service.py and StudyCache invalidation into CacheManager::invalidate. Keep otp_store.py::delete separate — OTP deletion is part of a verification lifecycle, not general cache eviction. The low-level caching.py::delete becomes internal to the consolidated cache.

---

### Clear all entries from a cache

**Category:** caching

**Functions:**
- `clear` in `ETAP-AI-WORK/services/cache_service.py:187` - Clear all entries from memory and best-effort from Redis
- `clear` in `ETAP-AI-WORK/engine/cache_manager.py:181` - Clear all cache entries and reset statistics — CalculationCache
- `flushdb` in `ETAP-AI-WORK/engine/caching.py:132` - Clear all entries from in-memory cache — low-level StudyCache internal
- `clear` in `ETAP-AI-WORK/engine/caching.py:453` - Clear all cached entries in the study cache — high-level StudyCache

**Differences:** cache_service.py::clear targets both Redis and in-memory. cache_manager.py::clear also resets statistics counters. caching.py::flushdb is the low-level in-memory-only clear. caching.py::clear (line 453) is the high-level StudyCache clear (likely wraps flushdb + Redis FLUSHDB). All achieve the same result: an empty cache.

**Recommendation:** Keep `ETAP-AI-WORK/engine/cache_manager.py::clear` - The CalculationCache clear is the most thorough (includes stats reset). Consolidate all cache-clearing into one method that handles both backends (Redis + in-memory) and resets stats. Remove redundant flushdb and cache_service.py::clear.

---

### Report cache performance statistics (hit rate, eviction count, size)

**Category:** caching

**Functions:**
- `get_stats` in `ETAP-AI-WORK/engine/cache_manager.py:193` - Return cache statistics: hit rate, size, and entry count — CalculationCache
- `get_stats` in `ETAP-AI-WORK/engine/caching.py:411` - Return cache hit/miss/eviction statistics and current storage info — StudyCache

**Differences:** Both return dicts with hit/miss counts, hit rate, eviction count, and current size/entry count. Implementation likely very similar — both track hits/misses on get() calls and evictions on removal. Minor differences in exact field names and structure of the returned dict.

**Recommendation:** Keep `ETAP-AI-WORK/engine/cache_manager.py::get_stats` - Merge into a unified get_stats on the consolidated CacheManager. Standardize the output dict schema so all callers get the same fields. The StudyCache stats tracking can be absorbed into the CalculationCache's stats counters.

---

### List cache keys filtered by a glob pattern

**Category:** caching

**Functions:**
- `get_cache_keys` in `ETAP-AI-WORK/engine/cache_manager.py:211` - Return cache keys optionally filtered by a glob pattern — CalculationCache
- `keys` in `ETAP-AI-WORK/engine/caching.py:109` - Return keys matching a glob pattern from the in-memory cache — StudyCache low-level

**Differences:** Both accept a glob pattern and return matching keys. caching.py::keys is a low-level in-memory-only operation (fnmatch filtering). cache_manager.py::get_cache_keys operates on the CalculationCache dict with similar filtering. Identical purpose, nearly identical implementation.

**Recommendation:** Keep `ETAP-AI-WORK/engine/cache_manager.py::get_cache_keys` - Rename to a standard method (e.g., keys()) on the consolidated CacheManager. The glob filtering logic is trivial and should not be duplicated.

---

### Check whether a cache entry exists for a given key (and is not expired)

**Category:** caching

**Functions:**
- `exists` in `ETAP-AI-WORK/engine/cache_manager.py:220` - Check whether a cache entry exists for a given key — CalculationCache
- `exists` in `ETAP-AI-WORK/engine/caching.py:97` - Check if a key exists and is not expired in the in-memory cache — StudyCache low-level

**Differences:** Both return a boolean indicating whether a key is present and valid (not expired). caching.py::exists is a low-level in-memory check. cache_manager.py::exists checks the CalculationCache dict. Identical purpose.

**Recommendation:** Keep `ETAP-AI-WORK/engine/cache_manager.py::exists` - Standard exists() method on the consolidated CacheManager. The expiration check logic is trivial and should not exist in two places.

---

### Provide a complete cache CRUD layer (get/set/invalidate/clear/stats) — architectural duplicate across three modules

**Category:** caching

**Functions:**
- `[class: CacheService]` in `ETAP-AI-WORK/services/cache_service.py:70` - Full cache service: redis_client, cache, _generate_key, _cleanup_key_if_expired, get, set, clear, ping, get_study_cache — Redis + in-memory fallback
- `[class: CalculationCache]` in `ETAP-AI-WORK/engine/cache_manager.py:99` - Full cache manager: get, set, invalidate, invalidate_by_tag, clear, get_stats, get_cache_keys, exists, eviction, build_key, should_cache, get_cache_ttl, pre_warm, memory reporting — in-memory with LRU/LFU, tags, size limits
- `[class: StudyCache]` in `ETAP-AI-WORK/engine/caching.py:69` - Full cache: low-level get/set/delete/exists/keys/dbsize/flushdb + high-level get/set/invalidate/invalidate_study_type/get_stats/clear — Redis + in-memory fallback

**Differences:** Three independent cache implementations providing the same core CRUD operations (get, set, invalidate/delete, clear, stats). CacheService (services/) and StudyCache (engine/caching.py) both use Redis with in-memory fallback and target study results — near-identical architectures. CalculationCache (engine/cache_manager.py) is more feature-rich (LRU/LFU eviction, tags, size limits, decorators) but in-memory only. The fundamental pattern (key-value store with TTL and stats) is duplicated across all three.

**Recommendation:** Keep `ETAP-AI-WORK/engine/cache_manager.py::CalculationCache` - CalculationCache is the most feature-complete implementation. Absorb StudyCache's Redis backend support as an adapter, add study-domain key building, and eliminate CacheService entirely. The consolidated CacheManager should support both study and calculation domains via configurable key builders and tags. This eliminates three classes doing the same thing with different feature levels.

---

### Parse vision API responses into a standard format dict with error handling

**Category:** data-transform

**Functions:**
- `_parse_response` in `ETAP-AI-WORK/integrations/anthropic_vision.py:318` - Extracts text from Anthropic content blocks, strips markdown fences, parses JSON, adds source='anthropic', identical error dict structure
- `_parse_response` in `ETAP-AI-WORK/integrations/openai_vision.py:369` - Extracts text from OpenAI choices[0].message.content, strips markdown fences, parses JSON, adds source='openai', identical error dict structure
- `_parse_response` in `AhmedETAP-Platform/integrations/anthropic_vision.py:318` - Exact copy of ETAP-AI-WORK version
- `_parse_response` in `AhmedETAP-Platform/integrations/openai_vision.py:369` - Exact copy of ETAP-AI-WORK version

**Differences:** Anthropic version extracts from response.content[] blocks; OpenAI version extracts from response.choices[0].message.content. Both strip markdown code fences identically, both add a source tag, both return identical error dict shapes. Gemini uses completely different response structure (SDK objects vs raw dicts) and is NOT a duplicate of these two.

**Recommendation:** Keep `ETAP-AI-WORK/integrations/_vision_base.py (shared helper)` - Anthropic and OpenAI _parse_response share identical logic: strip-markdown-fences → json.loads → add-source-tag → error-dict. Extract a shared _parse_json_from_text(text, source) helper into _vision_base.py (which already consolidates vision duplicates). Each client would call this helper after its own response-specific extraction step, keeping per-provider extraction separate but sharing the JSON parsing/fence-stripping/error-handling pipeline.

---

### Ensure data is JSON-serializable by replacing NaN/inf and converting non-native types

**Category:** data-transform

**Functions:**
- `_to_jsonable` in `ETAP-AI-WORK/core/bootstrap.py:79` - Comprehensive: handles numpy types (ndarray, integer, floating, bool_, complex), Python complex, NaN/inf → None, recurses dicts/lists/tuples/sets, fallback str coercion
- `_clean_nan` in `ETAP-AI-WORK/api/ai_ml.py:39` - Simpler subset: only handles float NaN/inf → None, recurses dicts/lists/tuples, no numpy or complex support
- `_to_jsonable` in `AhmedETAP-Platform/core/bootstrap.py:79` - Exact copy of ETAP-AI-WORK version
- `_clean_nan` in `AhmedETAP-Platform/api/ai_ml.py:39` - Exact copy of ETAP-AI-WORK version

**Differences:** _to_jsonable is a superset of _clean_nan. _clean_nan only sanitizes float NaN/inf → None and recurses containers. _to_jsonable additionally converts numpy types, Python complex numbers, and has a fallback string coercion. Both serve the same purpose (make data JSON-safe) but _to_jsonable is more general.

**Recommendation:** Keep `ETAP-AI-WORK/core/bootstrap.py::_to_jsonable` - _clean_nan is a subset of _to_jsonable. Replace all calls to _clean_nan with _to_jsonable, then delete _clean_nan. Since _to_jsonable is already in core/bootstrap.py (loaded at app startup), it is always available. The ai_ml.py module can import and use it directly instead of defining its own local version.

---

### Exact cross-repo duplication between AhmedETAP-Platform and ETAP-AI-WORK

**Category:** data-transform

**Functions:**
- `to_pil_image / image_to_base64_png / retry_with_backoff` in `ETAP-AI-WORK/integrations/_vision_base.py:34` - Entire file is an identical copy
- `to_pil_image / image_to_base64_png / retry_with_backoff` in `AhmedETAP-Platform/integrations/_vision_base.py:34` - Identical copy of ETAP-AI-WORK version
- `to_dict (Point3D, Geometry, SemanticProperties, Relationship, UniversalElement, Conflict)` in `ETAP-AI-WORK/core/models.py:168` - All to_dict methods identical across repos
- `to_dict (Point3D, Geometry, SemanticProperties, Relationship, UniversalElement, Conflict)` in `AhmedETAP-Platform/core/models.py:168` - Identical copy
- `_make_bus_record / _make_branch_record / _json_bus_record / _json_branch_record` in `ETAP-AI-WORK/api/data_import.py:185` - All record builder functions identical
- `_make_bus_record / _make_branch_record / _json_bus_record / _json_branch_record` in `AhmedETAP-Platform/api/data_import.py:185` - Identical copy
- `embed_documents / embed_query / _embed` in `ETAP-AI-WORK/services/memory_service.py:82` - Near-identical (minor __all__ and qdrant import diff)
- `embed_documents / embed_query / _embed` in `AhmedETAP-Platform/services/memory_service.py:82` - Near-identical (missing __all__ export line)
- `to_dict (ConfirmationRequest)` in `ETAP-AI-WORK/api/cua_confirmation_ws.py:81` - Identical
- `to_dict (ConfirmationRequest)` in `AhmedETAP-Platform/api/cua_confirmation_ws.py:81` - Identical copy
- `to_dict (FunctionInfo, ModuleCoverage, CoverageReport)` in `ETAP-AI-WORK/api/coverage_report.py:75` - Identical
- `to_dict (FunctionInfo, ModuleCoverage, CoverageReport)` in `AhmedETAP-Platform/api/coverage_report.py:75` - Identical copy
- `to_masked_dict` in `ETAP-AI-WORK/services/api_key_store.py:86` - Identical
- `to_masked_dict` in `AhmedETAP-Platform/services/api_key_store.py:86` - Identical copy

**Differences:** All listed files are exact or near-exact copies between AhmedETAP-Platform and ETAP-AI-WORK repos. Verified via diff: zero differences for core/models.py, integrations/_vision_base.py, api/data_import.py, services/api_key_store.py, api/cua_confirmation_ws.py, api/coverage_report.py. Only memory_service.py has minor diffs (missing __all__ and small qdrant import difference).

**Recommendation:** Keep `ETAP-AI-WORK (canonical repo)` - AhmedETAP-Platform appears to be an older/parallel copy. Consolidate shared modules into a common package or pip-installable library that both repos import, eliminating the need to manually synchronize identical files. Short-term: delete the AhmedETAP-Platform copies and have it import from ETAP-AI-WORK as a dependency.

---

### Newton-Raphson load flow solver — entire class duplicated across two files

**Category:** electrical-eng-digital-twin

**Functions:**
- `LoadFlowSolver (entire class)` in `ETAP-AI-WORK/load_flow/consolidated_solver.py:17` - Consolidated solver — 523 lines, identical code to load_flow.py
- `LoadFlowSolver (entire class)` in `ETAP-AI-WORK/load_flow/load_flow.py:15` - Canonical solver — 520 lines, identical code to consolidated_solver.py

**Differences:** Files are character-for-character identical (same __init__, _build_jacobian, _apply_step_limiting, _update_voltages, _check_q_limits, solve method with LM regularization, line-search damping). Both claim to be the 'consolidated' version but neither was deleted. consolidated_solver.py docstring says it consolidates from load_flow_solver_fixed.py; load_flow.py says it is the canonical implementation. This is a leftover from an incomplete merge — the duplicate was never removed.

**Recommendation:** Keep `ETAP-AI-WORK/load_flow/load_flow.py` - Delete consolidated_solver.py entirely — it contains identical code. Keep load_flow.py as the single canonical source. Ensure all import paths reference load_flow.py (e.g., from load_flow.load_flow import LoadFlowSolver).

---

### Arc flash calculation — convenience wrapper duplicates the engine's purpose

**Category:** electrical-eng-digital-twin

**Functions:**
- `calculate_arc_flash` in `ETAP-AI-WORK/fault_analysis/arc_flash_calc.py:36` - Wrapper function that delegates to ArcFlashEngine, returns plain dict
- `_get_engine` in `ETAP-AI-WORK/fault_analysis/arc_flash_calc.py:29` - Singleton pattern for ArcFlashEngine instance
- `calculate` in `ETAP-AI-WORK/fault_analysis/arc_flash_engine.py:461` - Complete arc flash calculation producing ArcFlashResult dataclass
- `calculate_arc_current` in `ETAP-AI-WORK/fault_analysis/arc_flash_engine.py:188` - Sub-step: IEEE 1584 arc current computation
- `calculate_incident_energy` in `ETAP-AI-WORK/fault_analysis/arc_flash_engine.py:247` - Sub-step: incident energy from arc flash event
- `calculate_arc_flash_boundary` in `ETAP-AI-WORK/fault_analysis/arc_flash_engine.py:350` - Sub-step: arc flash boundary distance
- `determine_ppe_level` in `ETAP-AI-WORK/fault_analysis/arc_flash_engine.py:435` - Sub-step: PPE level from incident energy
- `ralph_lee_method` in `ETAP-AI-WORK/fault_analysis/arc_flash_engine.py:549` - Alternative method for voltages below IEEE 1584 range

**Differences:** arc_flash_calc.py is explicitly documented as a 'thin convenience wrapper' around ArcFlashEngine. It normalizes string params to Enums, delegates to engine.calculate(), and converts the ArcFlashResult dataclass to a plain dict. No coefficient duplication exists (the wrapper imports from the engine). However, the wrapper adds a redundant layer — callers could use ArcFlashEngine directly. The _get_engine singleton caches the engine instance unnecessarily since the engine is stateless.

**Recommendation:** Keep `ETAP-AI-WORK/fault_analysis/arc_flash_engine.py` - The wrapper adds no value beyond dict-vs-dataclass conversion and string-to-Enum normalization. Move the string→Enum normalization helper into ArcFlashEngine itself (or a small utility), and let callers use engine.calculate() directly. The CLI __main__ block in arc_flash_calc.py can be moved to a separate CLI entry point script.

---

### Protection coordination checking — agent reimplements logic that exists in CoordinationEngine

**Category:** electrical-eng-digital-twin

**Functions:**
- `verify_coordination` in `ETAP-AI-WORK/agents/coordination_agent.py:187` - Agent-level coordination verification, computes trip times and checks margin >= 0.2s
- `analyze_selectivity` in `ETAP-AI-WORK/agents/coordination_agent.py:324` - Agent-level selectivity analysis across fault current range
- `calculate_relay_operating_time` in `ETAP-AI-WORK/agents/coordination_agent.py:116` - Agent-level relay operating time per IEC 60255 / IEEE C37.112
- `check_coordination` in `ETAP-AI-WORK/coordination/coordination.py:32` - Core engine: check coordination between two relays at a given fault current
- `check_coordination_range` in `ETAP-AI-WORK/coordination/coordination.py:71` - Core engine: check coordination across a range of fault currents
- `suggest_tms_adjustment` in `ETAP-AI-WORK/coordination/coordination.py:88` - Core engine: suggest TMS to achieve coordination margin

**Differences:** The CoordinationAgent reimplements coordination checking logic inline (verify_coordination computes relay times and compares margins) instead of delegating to CoordinationEngine.check_coordination / check_coordination_range. The agent uses IEC 60255 curve equations directly in calculate_relay_operating_time with its own _IEC60255_CURVES dict, while CoordinationEngine relies on OvercurrentRelay.trip_time() from the relays module. The agent works with dict parameters (pickup_current_a, curve_type, time_multiplier) while CoordinationEngine works with OvercurrentRelay objects. Same IEEE 242 / IEC 60255 standard, same 0.2s coordination interval, same fundamental logic.

**Recommendation:** Keep `ETAP-AI-WORK/coordination/coordination.py` - CoordinationAgent should delegate to CoordinationEngine rather than reimplementing coordination logic. The agent should accept task specifications, convert them to OvercurrentRelay objects, and call CoordinationEngine methods. This eliminates duplicate curve equations and margin-checking logic. The agent's value-add is orchestration and reporting, not raw computation.

---

### Complex voltage computation from magnitude and angle

**Category:** electrical-eng-digital-twin

**Functions:**
- `voltage (property getter)` in `ETAP-AI-WORK/core_model/bus.py:59` - Returns magnitude * np.exp(1j * angle) for Bus model
- `voltage (property setter)` in `ETAP-AI-WORK/core_model/bus.py:64` - Decomposes complex value into magnitude and angle
- `voltage (property)` in `ETAP-AI-WORK/digital_twin/state_store.py:48` - Returns magnitude * np.exp(1j * angle) for BusState in DT state layer

**Differences:** Both implement the same mathematical formula: V = Vmag * exp(j * Vangle). Bus.voltage is a @property with both getter and setter on the core model class. BusState.voltage is a @property getter only on the digital twin state dataclass. The setter logic (magnitude = abs(value), angle = np.angle(value)) only exists in Bus. This pattern is repeated identically across two separate class hierarchies — one for the core power system model, one for the DT state representation.

**Recommendation:** Keep `ETAP-AI-WORK/core_model/bus.py:voltage` - The voltage property formula is trivial and idiomatic for power engineering classes. The duplication stems from BusState mirroring Bus fields for DT snapshot storage. Options: (a) extract a shared VoltageMixin/protocol with voltage property, or (b) have BusState inherit from or compose Bus, or (c) keep separate since BusState is a lightweight snapshot dataclass with different serialization needs. Given the simplicity, KEEP_SEPARATE is acceptable, but the pattern should be documented.

---

### get_shunt_admittance method duplicated across Line and Transformer

**Category:** electrical-eng-digital-twin

**Functions:**
- `get_shunt_admittance` in `ETAP-AI-WORK/core_model/line.py:71` - Returns yshunt1/yshunt2/yshunt0 based on sequence parameter
- `get_shunt_admittance` in `ETAP-AI-WORK/core_model/transformer.py:79` - Returns yshunt1/yshunt2/yshunt0 based on sequence parameter — identical structure to Line

**Differences:** Both use identical if/elif/else pattern: if seq==1 return yshunt1, elif seq==2 return yshunt2, elif seq==0 return yshunt0, else ValueError. The only difference is the attribute names happen to match (both store yshunt1/yshunt2/yshunt0). This is pure copy-paste duplication.

**Recommendation:** Keep `Shared SequenceImpedanceMixin extracted from both Line and Transformer` - get_impedance and get_shunt_admittance are identical between Line and Transformer. Create a SequenceImpedanceMixin or base class that both inherit from, eliminating 2× copy-paste of both methods. The mixin can also be extended to Generator/Load if their default-value patterns are parameterized.

---

### Load flow execution — multiple entry points across EE and DT modules

**Category:** electrical-eng-digital-twin

**Functions:**
- `run_load_flow` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:1181` - DT public API: rebuilds Ybus, runs load flow via _base_engine, updates DT state
- `_run_load_flow` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:538` - DT internal: directly instantiates LoadFlowSolver for propagation pipeline
- `LoadFlowSolver.solve` in `ETAP-AI-WORK/load_flow/load_flow.py:351` - Core EE solver: Newton-Raphson iteration with convergence control
- `_run_load_flow` in `ETAP-AI-WORK/etap_integration/etap_com.py:339` - ETAP COM interface: runs load flow via external ETAP application

**Differences:** Two levels of duplication: (1) digital_twin_core.py has TWO load flow entry points — run_load_flow (public, uses _base_engine.run_load_flow()) and _run_load_flow (internal, directly creates LoadFlowSolver). Both ultimately call the same LoadFlowSolver but through different paths within the same class. (2) The ETAP COM _run_load_flow is a genuinely different implementation (calls ETAP via COM automation) that serves the same purpose but for external tool integration. The DT duplication (two methods in same class) is the actionable concern.

**Recommendation:** Keep `digital_twin_core.py:run_load_flow (public API) + LoadFlowSolver (core engine)` - Merge _run_load_flow (line 538) into run_load_flow (line 1181) or make _run_load_flow call run_load_flow. Having two separate load flow paths in the same DigitalTwin class is confusing and risks divergence. The propagation pipeline (handlers.py) should call run_load_flow instead of maintaining its own solver instantiation. ETAP COM _run_load_flow should remain separate — it's a different execution platform.

---

### Return a snapshot/summary of operational statistics from a module

**Category:** logging-config-event

**Functions:**
- `get_stats` in `ETAP-AI-WORK/engine/async_executor.py:336` - Executor stats: submitted/completed/failed counts
- `get_stats` in `ETAP-AI-WORK/engine/async_executor.py:462` - Thread pool manager stats
- `get_stats` in `ETAP-AI-WORK/engine/async_executor.py:505` - Process pool manager stats
- `get_statistics` in `ETAP-AI-WORK/copilot/ai/drawing_engine.py:956` - Drawing engine processing statistics
- `get_statistics` in `ETAP-AI-WORK/copilot/translation/engine.py:673` - Translation engine statistics
- `get_statistics` in `ETAP-AI-WORK/etap_integration/sync_engine.py:586` - Sync statistics with counts and success rates
- `stats` in `ETAP-AI-WORK/acp_runtime/acp/runtime/engine.py:256` - Per-capability call and error count snapshot
- `metrics` in `ETAP-AI-WORK/acp_runtime/acp/health.py:93` - Metrics snapshot dictionary from registry
- `get_system_status` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:1418` - Digital twin system status summary
- `get_statistics` in `ETAP-AI-WORK/digital_twin/event_bus.py:464` - Event bus subscription and publication counts
- `snapshot` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:457` - In-memory registry full metrics snapshot

**Differences:** All return module-specific stats with different field sets (executor vs translation vs sync vs event-bus). Some are plain dicts, others are Prometheus-aware. Naming varies: get_stats, get_statistics, stats, metrics, get_system_status, snapshot.

**Recommendation:** Keep `core/metrics.py as central stats collector with per-module stat namespaces` - 9+ functions with same intent across modules. Standardize to a single get_statistics() interface per module that returns a dict conforming to a common schema, with core/metrics.py providing the aggregation layer.

---

### Return historical records of past operations/events from a module

**Category:** logging-config-event

**Functions:**
- `get_sync_log` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:369` - History of synchronization operations
- `get_propagation_log` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:743` - History of state propagation operations
- `get_processed_events` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:949` - History of processed domain events
- `get_step_log` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:1118` - History of simulation time-step results
- `get_operation_log` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:1414` - History of operations on the digital twin
- `get_sync_log` in `ETAP-AI-WORK/etap_integration/sync_engine.py:570` - Recent sync operation log entries
- `get_translation_log` in `ETAP-AI-WORK/copilot/translation/engine.py:670` - Recent translation log entries
- `get_history` in `ETAP-AI-WORK/copilot/ai/drawing_engine.py:952` - Recent NLP processing history entries
- `get_history` in `ETAP-AI-WORK/digital_twin/event_bus.py:445` - Event history filtered by type
- `entries` in `ETAP-AI-WORK/acp_runtime/acp/observability/structured_logger.py:180` - Buffered log entries snapshot
- `events` in `ETAP-AI-WORK/acp_runtime/acp/runtime/progress.py:85` - Buffered progress events snapshot

**Differences:** digital_twin_core.py has 5 separate log getters for different operation types. Others have one per module. All return list/dict of historical entries but with different schemas per domain. Some accept limit/filters, others don't.

**Recommendation:** Keep `A unified get_history(domain, limit, filter) interface across modules` - 11 functions doing the same thing — returning recent operation history. digital_twin_core.py's 5 separate log getters could be one get_log(category) function. Each module should expose one standardized history retrieval method.

---

### Record a single metric/observation into an internal counter, histogram, or registry

**Category:** logging-config-event

**Functions:**
- `_record_metrics` in `ETAP-AI-WORK/acp_runtime/acp/runtime/engine.py:228` - Record execution metrics to metrics registry
- `_increment_counter` in `ETAP-AI-WORK/core/bootstrap.py:303` - Thread-safe increment of bootstrap metrics counters
- `_add_execution_time` in `ETAP-AI-WORK/core/bootstrap.py:315` - Thread-safe accumulation of execution time into bootstrap metrics
- `observe_memory` in `ETAP-AI-WORK/core/metrics.py:308` - Record RSS memory observation into histogram
- `record_validation_failure` in `ETAP-AI-WORK/core/metrics.py:318` - Increment validation failure counter with reason label
- `observe` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:157` - Record value observation into Prometheus histogram
- `inc` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:88` - Increment counter by amount
- `_log_sync` in `ETAP-AI-WORK/etap_integration/sync_engine.py:555` - Log sync operation (also records to statistics)
- `_log_translation` in `ETAP-AI-WORK/copilot/translation/engine.py:657` - Log translation operation (also records to statistics)
- `_record_event` in `ETAP-AI-WORK/api/email_webhooks.py:261` - Record email webhook event in in-memory log
- `_add_to_history` in `ETAP-AI-WORK/digital_twin/event_bus.py:438` - Add event to history buffer with size limit

**Differences:** Some target Prometheus counters/histograms (core/metrics.py, acp observability), others use plain in-memory dicts/lists (bootstrap, email_webhooks, event_bus). _log_sync and _log_translation dual-purpose: both log and accumulate stats. Domain-specific labels differ.

**Recommendation:** Keep `core/metrics.py as the single metrics recording API` - 11 functions that all increment counters/record observations. Should funnel through a unified metrics recording API. Domain-specific labels can be parameters. The dual-purpose _log_* functions should separate logging from metrics recording.

---

### Format metrics data in Prometheus or OpenMetrics text exposition format

**Category:** logging-config-event

**Functions:**
- `generate_metrics` in `ETAP-AI-WORK/core/metrics.py:303` - Generate Prometheus exposition format metrics as bytes
- `prometheus` in `ETAP-AI-WORK/acp_runtime/acp/health.py:104` - Format metrics in Prometheus text exposition format
- `openmetrics` in `ETAP-AI-WORK/acp_runtime/acp/health.py:115` - Format metrics in OpenMetrics text exposition format
- `to_prometheus` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:385` - Render snapshot in Prometheus text format
- `to_openmetrics` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:397` - Render snapshot in OpenMetrics text format
- `prometheus` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:473` - Render in-memory registry metrics in Prometheus text format

**Differences:** core/metrics.py uses the prometheus_client library's native generate_latest. acp observability has its own to_prometheus/to_openmetrics rendering from its in-memory registry. acp health exposes both formats as HTTP endpoints. All produce the same output format but from different metric sources.

**Recommendation:** Keep `core/metrics.py:generate_metrics as the single Prometheus exposition endpoint` - 6 functions producing the same output format. The acp observability metrics module reimplements Prometheus exposition rendering that core/metrics.py already provides via prometheus_client. Should route through a single exposition endpoint.

---

### Instrument function execution with timing/counting/tracing decorators

**Category:** logging-config-event

**Functions:**
- `trace_operation` in `ETAP-AI-WORK/core/tracing.py:263` - Decorator: OpenTelemetry tracing span on function
- `track_skill_operation` in `ETAP-AI-WORK/core/metrics.py:188` - Decorator: in-flight gauge + result counter
- `track_execution_duration` in `ETAP-AI-WORK/core/metrics.py:240` - Decorator: time function, record in Prometheus histogram
- `count_executions` in `ETAP-AI-WORK/core/metrics.py:255` - Decorator: increment success/error counters on exit
- `start_span` in `ETAP-AI-WORK/acp_runtime/acp/observability/tracer.py:136` - Start a tracing span (non-decorator, manual API)
- `finish_span` in `ETAP-AI-WORK/acp_runtime/acp/observability/tracer.py:148` - Finish a tracing span, record duration and status

**Differences:** core/tracing.py uses OpenTelemetry for distributed tracing. core/metrics.py uses prometheus_client for metrics. acp observability/tracer.py has a manual start_span/finish_span API vs decorator pattern. track_skill_operation combines gauge+counter, track_execution_duration does histogram, count_executions does counters — all overlapping instrumentation concerns.

**Recommendation:** Keep `A single observe() decorator in core/observability.py that combines trace+metrics` - 3 separate decorator families in core/ (tracing, metrics) and a manual span API in acp. All instrument the same thing: function execution. A unified decorator should wrap a function with both an OTEL span AND Prometheus metrics in one call, eliminating the need to stack multiple decorators.

---

### Get or create a singleton service instance

**Category:** logging-config-event

**Functions:**
- `_get_power_system_engine` in `ETAP-AI-WORK/core/bootstrap.py:205` - Return or init global PowerSystemEngine singleton
- `get_async_executor` in `ETAP-AI-WORK/engine/async_executor.py:727` - Factory returning configured AsyncExecutor singleton
- `get_thread_pool_manager` in `ETAP-AI-WORK/engine/async_executor.py:742` - Factory returning ThreadPoolManager singleton
- `get_process_pool_manager` in `ETAP-AI-WORK/engine/async_executor.py:757` - Factory returning ProcessPoolManager singleton
- `get_secrets_manager` in `ETAP-AI-WORK/security/secrets_manager.py:660` - Get or init secrets manager singleton
- `get_siem_forwarder` in `ETAP-AI-WORK/security/siem.py:616` - Get or init SIEM forwarder singleton
- `get_knowledge_base` in `ETAP-AI-WORK/knowledge/rag_engine.py:799` - Get or create knowledge base singleton
- `get_or_create_counter` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:437` - Get or create counter metric in in-memory registry
- `get_or_create_histogram` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:443` - Get or create histogram metric in registry
- `get_or_create_gauge` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:451` - Get or create gauge metric in registry

**Differences:** Each creates a different service type. Some use module-level globals (_get_power_system_engine), others use class-level caching (get_async_executor). The metrics get_or_create_* are factory methods within a registry pattern. All follow lazy-init singleton pattern but with no shared infrastructure.

**Recommendation:** Keep `A shared SingletonRegistry or ServiceLocator in core/bootstrap.py` - 10 singleton factory functions with no shared pattern. Could benefit from a centralized service registry that manages lifecycle and provides type-safe access. However, each service has unique init requirements, so full consolidation may not be practical — investigate a shared pattern first.

---

### Get the ETAP provider/adapter instance for the current environment

**Category:** logging-config-event

**Functions:**
- `_get_etap_provider` in `ETAP-AI-WORK/core/bootstrap.py:214` - Factory with privacy controls
- `factory` in `ETAP-AI-WORK/core/bootstrap.py:217` - Inner closure creating ETAP provider respecting privacy mode
- `_get_etap_provider` in `ETAP-AI-WORK/copilot/api/routes.py:47` - Get ETAP AI provider for copilot services
- `get_etap_provider` in `ETAP-AI-WORK/etap_integration/etap_provider.py:504` - Factory method selecting provider based on environment
- `get_etap_adapter` in `ETAP-AI-WORK/etap_integration/etap_adapter.py:170` - Factory selecting adapter based on environment
- `get_etap_provider` in `ETAP-AI-WORK/etap_integration/etap_adapter.py:182` - Legacy factory for backward compatibility

**Differences:** Three separate _get_etap_provider functions across bootstrap, copilot/routes, and etap_provider modules. etap_adapter has both get_etap_adapter (new) and get_etap_provider (legacy compat). bootstrap adds privacy-mode wrapping. Different provider selection logic but all resolve to the same ETAP interface.

**Recommendation:** Keep `etap_integration/etap_adapter.py:get_etap_adapter as the single canonical factory` - 3 duplicate _get_etap_provider functions and a legacy compat wrapper. The etap_adapter module already has the proper factory. Remove bootstrap._get_etap_provider and copilot/routes._get_etap_provider — both should import from etap_adapter. Remove the legacy get_etap_provider wrapper.

---

### Check whether a service or feature is enabled via environment configuration

**Category:** logging-config-event

**Functions:**
- `is_enabled` in `ETAP-AI-WORK/integrations/resend_email.py:261` - Check if Resend email service is enabled
- `is_akamai_enabled` in `ETAP-AI-WORK/api/akamai_protection.py:104` - Check if Akamai origin verification is configured
- `is_cloudflare_enabled` in `ETAP-AI-WORK/api/cloudflare_protection.py:98` - Check if Cloudflare origin verification is configured
- `is_r2_enabled` in `ETAP-AI-WORK/api/r2_storage.py:117` - Check if R2 storage is configured and ready
- `is_feature_enabled` in `ETAP-AI-WORK/api/feature_flags.py:17` - Check if study type feature is enabled
- `enabled` in `ETAP-AI-WORK/security/rasp.py:162` - Check if RASP protection is enabled for a feature
- `enabled` in `ETAP-AI-WORK/security/rasp.py:167` - Check if RASP engine is globally enabled
- `_is_etap_enabled` in `ETAP-AI-WORK/etap_integration/etap_provider.py:30` - Check if ETAP functionality is enabled via env var
- `_env_truthy` in `ETAP-AI-WORK/integrations/langfuse_integration.py:91` - Check if env variable is truthy (generic helper)
- `_is_supabase_database` in `ETAP-AI-WORK/integrations/supabase_integration.py:483` - Check if DATABASE_URL points to Supabase Postgres

**Differences:** Each checks a different env var or config source. Some are simple env-var checks (is_akamai_enabled, _is_etap_enabled), others involve more logic (is_r2_enabled checks client readiness, _is_supabase_database parses URL). _env_truthy is a generic env-var truthiness helper that others could reuse. RASP has both per-feature and global enabled checks.

**Recommendation:** Keep `core/config.py:is_service_enabled(service_name) as a unified service-enablement checker` - 10 functions all checking if some service is on/off via env vars. _env_truthy already provides the generic mechanism — others should use it instead of each reimplementing env-var parsing. A centralized is_service_enabled() registry would replace the scattered per-module checks.

---

### Read/parse/check environment variables for configuration values

**Category:** logging-config-event

**Functions:**
- `env_int` in `ETAP-AI-WORK/acp_runtime/acp/config.py:23` - Read integer from env var with fallback default
- `env_bool` in `ETAP-AI-WORK/acp_runtime/acp/config.py:34` - Read boolean from env var with fallback default
- `_env_truthy` in `ETAP-AI-WORK/integrations/langfuse_integration.py:91` - Check if env var is truthy
- `_is_production` in `ETAP-AI-WORK/etap_integration/etap_provider.py:39` - Check if env is production/staging via env var
- `_is_etap_enabled` in `ETAP-AI-WORK/etap_integration/etap_provider.py:30` - Check ETAP env var is truthy
- `_is_set` in `ETAP-AI-WORK/acp_runtime/acp/config.py:175` - Check if CLI argument was explicitly set
- `is_feature_enabled` in `ETAP-AI-WORK/api/feature_flags.py:17` - Check study type feature via env config
- `_get_secret` in `ETAP-AI-WORK/api/csrf.py:64` - Return CSRF secret from environment configuration
- `_get_client` in `ETAP-AI-WORK/api/r2_storage.py:82` - Return cached boto3 S3 client configured from env
- `_get_rate_limit_redis` in `ETAP-AI-WORK/api/routes.py:190` - Get Redis connection for rate limiting from env
- `_load_from_env` in `ETAP-AI-WORK/integrations/resend_email.py:248` - Load Resend config from env vars on first use

**Differences:** env_int/env_bool are generic env-var parsers. _env_truthy, _is_etap_enabled, _is_production are ad-hoc truthiness checks that reimplement env_bool. _get_secret, _get_client, _get_rate_limit_redis, _load_from_env are env-driven service factories that also parse env vars internally. Each module reimplements env-var reading instead of using the centralized env_int/env_bool.

**Recommendation:** Keep `acp_runtime/acp/config.py:env_int/env_bool as the shared env-var utility (move to core/config.py)` - 11 functions reading env vars. _env_truthy, _is_etap_enabled, _is_production all duplicate env_bool logic. Should consolidate env-var reading into core/config.py utilities that all modules import, eliminating the scattered per-module env parsing.

---

### Lookup sequence-network impedance by sequence key ('1','2','0') for a component model

**Category:** numerical

**Functions:**
- `get_impedance` in `ETAP-AI-WORK/core_model/line.py:54` - Dispatches on seq='1'→z1, '2'→z2, '0'→z0 with ValueError for unknown seq; uses explicit if/elif
- `get_impedance` in `ETAP-AI-WORK/core_model/transformer.py:62` - Line-for-line identical to line.get_impedance: same if/elif dispatch, same ValueError, same docstring
- `get_impedance` in `ETAP-AI-WORK/core_model/generator.py:69` - Uses dict.get(seq, complex(0,0)) instead of if/elif; simpler but less strict (no ValueError for unknown seq)
- `get_impedance` in `ETAP-AI-WORK/core_model/load.py:57` - Uses dict.get(seq, complex(1e9,0)) — different default (1e9 vs 0) reflecting that a missing load impedance should be very large
- `get_impedance` in `AhmedETAP-Platform/core_model/line.py:54` - Cross-repo identical copy of ETAP-AI-WORK/core_model/line.py get_impedance
- `get_impedance` in `AhmedETAP-Platform/core_model/transformer.py:62` - Cross-repo identical copy of ETAP-AI-WORK/core_model/transformer.py get_impedance
- `get_impedance` in `AhmedETAP-Platform/core_model/generator.py:69` - Cross-repo identical copy of ETAP-AI-WORK/core_model/generator.py get_impedance
- `get_impedance` in `AhmedETAP-Platform/core_model/load.py:57` - Cross-repo identical copy of ETAP-AI-WORK/core_model/load.py get_impedance

**Differences:** line and transformer share identical if/elif dispatch code; generator uses dict.get with default 0; load uses dict.get with default 1e9. Cross-repo copies are byte-for-byte identical.

**Recommendation:** Keep `A shared SequenceImpedanceMixin or base class method` - The if/elif dispatch pattern is repeated identically for line and transformer; generator and load differ only in default value. All four should inherit a common get_impedance that takes a dict and default, eliminating copy-paste. Cross-repo copies should be eliminated via a shared package.

---

### Lookup sequence-network shunt admittance by sequence key ('1','2','0')

**Category:** numerical

**Functions:**
- `get_shunt_admittance` in `ETAP-AI-WORK/core_model/line.py:71` - if/elif dispatch on seq → yshunt1/yshunt2/yshunt0; ValueError for unknown seq
- `get_shunt_admittance` in `ETAP-AI-WORK/core_model/transformer.py:79` - Line-for-line identical to line.get_shunt_admittance
- `get_shunt_admittance` in `AhmedETAP-Platform/core_model/line.py:71` - Cross-repo identical copy
- `get_shunt_admittance` in `AhmedETAP-Platform/core_model/transformer.py:79` - Cross-repo identical copy

**Differences:** line and transformer implementations are character-for-character identical. No other models (generator, load) have this method. Cross-repo copies are identical.

**Recommendation:** Keep `Shared SequenceAdmittanceMixin on both Line and Transformer classes` - Two identical implementations across two classes (and two repos) — trivial to extract into a mixin or base class that dispatches on a dict of shunt values.

---

### Build the Newton-Raphson Jacobian matrix from Ybus, voltage vector, and bus-type indices

**Category:** numerical

**Functions:**
- `_build_jacobian` in `ETAP-AI-WORK/load_flow/load_flow.py:86` - Analytical Jacobian using numpy dense matrices; J1/J2/J3/J4 sub-blocks computed via vectorized numpy operations (GS, BC, GC, BS precomputed)
- `_build_jacobian` in `ETAP-AI-WORK/load_flow/consolidated_solver.py:89` - Character-for-character identical to load_flow.py version — same docstring, same variable names, same formulas. Only difference: line 105 has 'Union[Δ|V, _pq]' typo vs 'Δ|V|_pq' in load_flow.py
- `_build_jacobian` in `ETAP-AI-WORK/engine/gpu_solver.py:306` - Same mathematical formulas but implemented as element-by-element loops for sparse matrix construction; supports CuPy (GPU) and SciPy (CPU) sparse formats; uses lil_matrix or COO data lists for incremental insertion
- `_build_jacobian` in `AhmedETAP-Platform/load_flow/load_flow.py:86` - Cross-repo identical copy of ETAP-AI-WORK version
- `_build_jacobian` in `AhmedETAP-Platform/load_flow/consolidated_solver.py:89` - Cross-repo identical copy of ETAP-AI-WORK version
- `_build_jacobian` in `AhmedETAP-Platform/engine/gpu_solver.py:306` - Cross-repo identical copy of ETAP-AI-WORK version

**Differences:** load_flow.py and consolidated_solver.py are near-identical (intentional duplicate — consolidated_solver was meant to replace load_flow but both survive). gpu_solver uses a fundamentally different implementation strategy (sparse, loop-based, GPU-compatible) but computes the same mathematical result. Cross-repo copies are identical.

**Recommendation:** Keep `ETAP-AI-WORK/load_flow/load_flow.py::_build_jacobian (canonical dense implementation)` - consolidated_solver.py is an unresolved merge — its docstring says 'This is the canonical (consolidated)' but load_flow.py also says 'This is the canonical'. Delete consolidated_solver.py entirely; it adds no value beyond what load_flow.py provides. Keep gpu_solver::_build_jacobian as a separate sparse/GPU variant but consider extracting a shared JacobianFormula helper for the mathematical constants (H, N, M, L formulas).

---

### Full Newton-Raphson load-flow solve loop (iterate: mismatch → Jacobian → correction → update voltage → check convergence)

**Category:** numerical

**Functions:**
- `solve` in `ETAP-AI-WORK/load_flow/load_flow.py:351` - Canonical NR solver with PV→PQ switching, step limiting, line-search damping, Levenberg-Marquardt fallback
- `solve` in `ETAP-AI-WORK/load_flow/consolidated_solver.py:354` - Near-identical to load_flow.py::solve — same iteration loop structure, same fallback strategies, same variable names
- `solve` in `AhmedETAP-Platform/load_flow/load_flow.py:351` - Cross-repo identical copy
- `solve` in `AhmedETAP-Platform/load_flow/consolidated_solver.py:354` - Cross-repo identical copy

**Differences:** load_flow.py::solve and consolidated_solver.py::solve are near-identical in logic and structure. Both include PV→PQ Q-limit switching, step limiting, line-search damping, LM regularization. The consolidated_solver was intended to replace load_flow but both files persist. Cross-repo copies are identical.

**Recommendation:** Keep `ETAP-AI-WORK/load_flow/load_flow.py::LoadFlowSolver` - consolidated_solver.py::LoadFlowSolver is an unresolved merge duplicate — it should be deleted. solver.py already re-exports LoadFlowSolver from load_flow.py for backward compatibility, so consolidated_solver adds nothing.

---

### Compute matrix inverse with fallback to pseudo-inverse on singularity

**Category:** numerical

**Functions:**
- `safe_inverse` in `ETAP-AI-WORK/engine/numerical_safety.py:449` - Uses lstsq(mat, eye) for pseudo-inverse fallback; supports method='pinv' (always via lstsq) or method='inv' (try inv then fallback to lstsq)
- `safe_matrix_inverse` in `ETAP-AI-WORK/engine/resilience.py:781` - Uses np.linalg.inv then np.linalg.pinv for fallback; adds thread-safe metrics counting (_checks_performed, _violations_detected); supports fallback_to_pinv toggle
- `safe_inverse` in `AhmedETAP-Platform/engine/numerical_safety.py:449` - Cross-repo identical copy
- `safe_matrix_inverse` in `AhmedETAP-Platform/engine/resilience.py:781` - Cross-repo identical copy

**Differences:** Both try inv() then fall back on singularity. numerical_safety::safe_inverse uses lstsq for pseudo-inverse computation (mathematically equivalent but slower), while resilience::safe_matrix_inverse uses np.linalg.pinv (standard, faster). resilience adds thread-safety and audit metrics. Cross-repo copies are identical.

**Recommendation:** Keep `engine/resilience.py::safe_matrix_inverse ( richer: thread-safe, metrics, pinv is more standard)` - Two modules in the same package implement the same safe-inverse pattern. resilience::safe_matrix_inverse is more robust (thread-safety, metrics, proper pinv). Remove safe_inverse from numerical_safety.py and route all callers to resilience, or merge resilience's thread-safety into NumericalGuard and keep one canonical implementation.

---

### Entire LoadFlowSolver class including __init__, _build_jacobian, _calculate_power, _power_mismatch, solve, and all helper methods

**Category:** numerical

**Functions:**
- `LoadFlowSolver (entire class)` in `ETAP-AI-WORK/load_flow/load_flow.py:15` - 520-line file; canonical NR solver with PV→PQ switching, step limiting, damping, LM regularization
- `LoadFlowSolver (entire class)` in `ETAP-AI-WORK/load_flow/consolidated_solver.py:17` - 523-line file; near-identical class intended as consolidation but both persist
- `LoadFlowSolver (entire class)` in `AhmedETAP-Platform/load_flow/load_flow.py:15` - Cross-repo identical copy
- `LoadFlowSolver (entire class)` in `AhmedETAP-Platform/load_flow/consolidated_solver.py:17` - Cross-repo identical copy

**Differences:** The two files are near-identical class definitions (~520 lines each) with the same constructor, same _build_jacobian, same solve loop, same helper methods. consolidated_solver.py docstring says it 'consolidates' but load_flow.py also persists. Cross-repo copies are identical.

**Recommendation:** Keep `ETAP-AI-WORK/load_flow/load_flow.py::LoadFlowSolver` - Delete consolidated_solver.py entirely. It was meant to be the unified version but load_flow.py already serves as the canonical implementation. solver.py already re-exports from load_flow.py. Keeping both creates confusion about which is 'canonical'.

---

### Cross-repo byte-for-byte identical copies of core_model and engine numerical modules

**Category:** numerical

**Functions:**
- `(entire file)` in `ETAP-AI-WORK/core_model/line.py:1` - Identical to AhmedETAP-Platform/core_model/line.py
- `(entire file)` in `ETAP-AI-WORK/core_model/transformer.py:1` - Identical to AhmedETAP-Platform/core_model/transformer.py
- `(entire file)` in `ETAP-AI-WORK/core_model/generator.py:1` - Identical to AhmedETAP-Platform/core_model/generator.py
- `(entire file)` in `ETAP-AI-WORK/core_model/load.py:1` - Identical to AhmedETAP-Platform/core_model/load.py
- `(entire file)` in `ETAP-AI-WORK/engine/numerical_safety.py:1` - Identical to AhmedETAP-Platform/engine/numerical_safety.py
- `(entire file)` in `ETAP-AI-WORK/engine/resilience.py:1` - Identical to AhmedETAP-Platform/engine/resilience.py
- `(entire file)` in `ETAP-AI-WORK/engine/gpu_solver.py:1` - Identical to AhmedETAP-Platform/engine/gpu_solver.py
- `(entire file)` in `ETAP-AI-WORK/load_flow/load_flow.py:1` - Identical to AhmedETAP-Platform/load_flow/load_flow.py
- `(entire file)` in `ETAP-AI-WORK/load_flow/consolidated_solver.py:1` - Identical to AhmedETAP-Platform/load_flow/consolidated_solver.py

**Differences:** The two repos (ETAP-AI-WORK and AhmedETAP-Platform) contain identical copies of the numerical/engineering computation modules. These are not diverged forks — they are the same code duplicated across two deployment variants.

**Recommendation:** Keep `Extract into a shared Python package (e.g., etap-engineering-core) imported by both repos` - Two repos maintaining identical copies of the same numerical code is a maintenance hazard — any bug fix or improvement must be applied twice. Extract the shared core (core_model, engine numerical modules, load_flow solver) into a pip-installable package that both repos depend on.

---

### CDN/edge protection middleware — verify requests came through a CDN edge, enforce origin verification, rate limiting, and client-blocking policies

**Category:** security

**Functions:**
- `akamai_protection_middleware` in `ETAP-AI-WORK/api/akamai_protection.py:147` - Akamai-specific: checks bot scores, client reputation, bot categories. Attaches metadata as request.state.akamai.
- `cloudflare_protection_middleware` in `ETAP-AI-WORK/api/cloudflare_protection.py:148` - Cloudflare-specific: checks geo blocking (country), rate limits. Attaches metadata as request.state.cloudflare. Skips health paths identically.

**Differences:** Same structural pattern (origin verification → rate limit → policy checks → pass-through). Akamai enforces bot/reputation policies; Cloudflare enforces geo/country blocking. Different header names, different metadata keys, different env vars. Both already share RateLimiter from api._rate_limit module. Both skip same health-check paths.

**Recommendation:** Keep `api/cdn_protection.py (new unified module)` - Both modules follow the exact same middleware pattern: health-path skip, metadata extraction, origin-verification, rate-limit, policy-specific blocking, pass-through. The only differences are header names and which policies to enforce. A unified CDNProtectionMiddleware with a provider config (AkamaiConfig / CloudflareConfig) would eliminate ~300 lines of structural duplication while preserving all provider-specific behavior. The RateLimiter is already shared; origin-secret verification and client-IP extraction should be next.

---

### Verify X-Origin-Verify header against a shared secret to confirm request came through the CDN edge

**Category:** security

**Functions:**
- `_verify_origin_secret` in `ETAP-AI-WORK/api/akamai_protection.py:284` - Uses hmac.compare_digest against AKAMAI_ORIGIN_SECRET. Returns True in dev mode (no secret).
- `_verify_origin_secret` in `ETAP-AI-WORK/api/cloudflare_protection.py:244` - Uses hmac.compare_digest against CLOUDFLARE_ORIGIN_SECRET. Returns True in dev mode. Identical logic, only env var differs.

**Differences:** Identical implementation: both use hmac.compare_digest for constant-time comparison, both return True when no secret is configured (dev mode). Only the env var name (AKAMAI_ORIGIN_SECRET vs CLOUDFLARE_ORIGIN_SECRET) differs.

**Recommendation:** Keep `api/_cdn_origin_verify.py or within unified cdn_protection module` - Byte-for-byte identical logic. Can be parameterized by env_var name: verify_origin_secret(request, secret_env_var='AKAMAI_ORIGIN_SECRET').

---

### Log a structured security event with CDN metadata for audit/SIEM correlation

**Category:** security

**Functions:**
- `log_security_event` in `ETAP-AI-WORK/api/akamai_protection.py:324` - Logs with Akamai metadata (request_id, bot_score, client_reputation). Format: 'security_event: type=… severity=… client_ip=… akamai_request_id=…'
- `log_security_event` in `ETAP-AI-WORK/api/cloudflare_protection.py:289` - Logs with Cloudflare metadata (ray_id, country). Format: 'security_event: type=… severity=… client_ip=… cf_ray=… country=…'. Identical signature and severity handling.

**Differences:** Identical function signature (request, event_type, *, detail='', severity='info'). Same severity→log-level mapping. Only the metadata attribute name differs (request.state.akamai vs request.state.cloudflare) and the specific fields logged (akamai_request_id/bot_score/reputation vs cf_ray/country).

**Recommendation:** Keep `api/cdn_protection.py:log_security_event or api/security_events.py` - Same interface, same purpose. Should be unified to read from request.state.cdn_metadata (a common attribute set by the unified middleware) and log a canonical set of fields (client_ip, request_id, provider_name).

---

### Extract the real client IP from CDN-provided headers with fallback chain

**Category:** security

**Functions:**
- `get_client_ip` in `ETAP-AI-WORK/api/akamai_protection.py:109` - Prefers True-Client-IP, then X-Forwarded-For, then request.client.host.
- `get_client_ip` in `ETAP-AI-WORK/api/cloudflare_protection.py:103` - Prefers CF-Connecting-IP, then True-Client-IP, then X-Forwarded-For, then request.client.host.

**Differences:** Same 4-level fallback structure. Cloudflare adds CF-Connecting-IP as the primary header before True-Client-IP. Both end with X-Forwarded-For → request.client.host.

**Recommendation:** Keep `api/cdn_protection.py:get_client_ip` - Can be unified with a priority list parameter: get_client_ip(request, priority_headers=['cf-connecting-ip', 'true-client-ip']). The fallback chain (X-Forwarded-For → request.client.host) is identical.

---

### Validate an API key from request headers — check X-API-Key against a configured secret

**Category:** security

**Functions:**
- `_require_api_key` in `ETAP-AI-WORK/api/routes.py:126` - Simpler version: checks X-API-Key against ENGINEERING_SERVICE_API_KEY. Supports AUTH_DISABLED bypass. Raises 401.
- `verify_api_key` in `ETAP-AI-WORK/api/shared_handlers.py:330` - More complete: configurable env_var, skip_paths, JWT bypass (valid Bearer token skips API key). Raises 401.
- `get_api_key` in `ETAP-AI-WORK/api/dependencies.py:253` - FastAPI Depends-based: validates X-API-Key header with JWT bypass (valid Bearer token skips). Uses hmac.compare_digest. Returns the key string.
- `is_test_mode` in `ETAP-AI-WORK/api/_test_mode.py:32` - Checks if X-API-Key matches ENGINEERING_SERVICE_API_KEY — essentially the same validation logic (comparison without hmac.compare_digest). Returns bool instead of raising.
- `get_api_key_auth` in `ETAP-AI-WORK/api/_test_mode.py:81` - Calls is_test_mode(); returns user dict if valid, None otherwise. Derivative of is_test_mode.

**Differences:** _require_api_key is the simplest (no JWT bypass, no path skipping). verify_api_key is the most complete (configurable env_var, path skipping, JWT bypass). get_api_key is a FastAPI dependency version with JWT bypass. is_test_mode does the same key comparison but returns a bool. get_api_key_auth wraps is_test_mode to return a user dict. All fundamentally compare X-API-Key header to an env-var-stored secret.

**Recommendation:** Keep `api/shared_handlers.py:verify_api_key (most complete implementation)` - verify_api_key already has all the features the others lack (configurable env_var, path skipping, JWT bypass). The others should be replaced: routes.py should use verify_api_key as middleware; dependencies.py get_api_key should delegate to it; is_test_mode should call a shared validation helper rather than re-implementing comparison. This eliminates 4 separate implementations of 'compare X-API-Key to secret'.

---

### Redact secrets/credentials from strings — replace API keys, tokens, passwords, and other sensitive patterns with placeholder text

**Category:** security

**Functions:**
- `_redact_secrets` in `ETAP-AI-WORK/api/error_debugger.py:660` - Simpler: 5 regex patterns (api_key, token, password, secret, bearer). Replaces with '***REDACTED***'. Case-insensitive.
- `redact_text` in `ETAP-AI-WORK/security/log_redaction.py:120` - Comprehensive: 15+ regex patterns covering AWS keys, HF tokens, GitHub PATs, Slack tokens, JWTs, private keys, connection strings, TOTP secrets. Replaces with descriptive tags like '[REDACTED-HF-TOKEN]', '[REDACTED-AWS-KEY]'. Also provides SecretRedactionFilter logging filter class.

**Differences:** _redact_secrets uses generic patterns with ***REDACTED***; redact_text uses specific patterns with descriptive tags. redact_text covers far more secret types (AWS, GitHub, Slack, JWT, private keys, connection strings). redact_text is order-aware (private key blocks before generic patterns). _redact_secrets imports re inside the function loop (performance issue).

**Recommendation:** Keep `security/log_redaction.py:redact_text` - log_redaction.py is the authoritative, comprehensive implementation. _redact_secrets is a subset that should simply call redact_text() from security/log_redaction. This eliminates 5 redundant regex patterns and ensures error debug messages get the same level of secret coverage as log messages.

---

### Extract Bearer token from Authorization header string

**Category:** security

**Functions:**
- `_extract_bearer_token` in `ETAP-AI-WORK/api/dependencies.py:306` - Splits on space, validates 'Bearer' prefix, returns token string. Raises HTTPException on malformed header.
- `extract_token_from_header` in `ETAP-AI-WORK/acp_runtime/acp/security/auth.py:277` - Splits on whitespace (split(None, 1)), validates 'Bearer' prefix, returns token string. Returns None on malformed header (no exception).
- `validate_bearer_token` in `ETAP-AI-WORK/acp_runtime/acp/security/auth.py:241` - Extracts + validates Bearer token. Uses extract_token_from_header internally, then calls validator callable.

**Differences:** Both split the header and check for 'Bearer' prefix. dependencies.py raises HTTPException(401) on failure (FastAPI-specific). acp_runtime returns None on failure (framework-neutral). acp_runtime uses split(None, 1) which handles extra whitespace; dependencies.py uses split(' ') which is stricter. validate_bearer_token combines extraction and validation.

**Recommendation:** Keep `Both — different error handling contexts` - These serve different architectural layers: api/dependencies.py is a FastAPI HTTP layer (needs HTTPException), acp_runtime is a framework-neutral ACP layer (needs None return). The extraction logic is identical but the error contract differs by layer. Could share a core helper that returns Optional[str], with each layer wrapping it for its error semantics.

---

### Truncate text to a maximum character length for safe capture/logging in observability tools

**Category:** string-error-crypto

**Functions:**
- `_truncate_for_capture` in `ETAP-AI-WORK/integrations/langfuse_integration.py:98` - Truncates text to max char length for Langfuse capture; specific to Langfuse integration
- `_truncate_body` in `ETAP-AI-WORK/integrations/langfuse_middleware.py:76` - Truncates request/response body to max char length for safe capture; same purpose, different module

**Differences:** Both perform the same truncation logic (slice to max length with ellipsis). Slight naming difference reflects different caller contexts (generic body vs. capture-specific). Implementation likely identical: return text[:max_len] + '...' if len(text) > max_len else text.

**Recommendation:** Keep `integrations/langfuse_utils.py (new shared module)` - Both functions serve the identical purpose of truncating text for Langfuse observability capture. A single shared truncate_for_capture(text, max_len) in a langfuse_utils module would eliminate the duplication while serving both callers.

---

### Sanitize strings by removing dangerous/unsafe characters for security

**Category:** string-error-crypto

**Functions:**
- `sanitize_string` in `ETAP-AI-WORK/security/security_framework.py:633` - General-purpose string sanitization by removing dangerous characters; framework-level
- `_sanitize_string_input` in `ETAP-AI-WORK/etap_integration/etap_com.py:1027` - Sanitizes string input by removing dangerous characters AND truncating length; ETAP-specific
- `_sanitize_project_name` in `ETAP-AI-WORK/etap_integration/etap_com.py:1163` - Sanitizes an ETAP project name by removing unsafe characters; specialized subset of string sanitization

**Differences:** sanitize_string is a general-purpose utility. _sanitize_string_input adds truncation on top of character removal. _sanitize_project_name is a domain-specific variant for project names. All share the core pattern of removing unsafe characters from input strings.

**Recommendation:** Keep `security/security_framework.py::sanitize_string (enhanced with optional max_len param)` - The core sanitization logic is duplicated across three locations. A single sanitize_string with optional parameters (allowed_chars, max_len) can subsume all three. The ETAP-specific variants can call the shared function with domain-specific parameters.

---

### Normalize template variables/placeholders by substituting empty or unresolved Postman template values with defaults

**Category:** string-error-crypto

**Functions:**
- `normalize_template_var` in `ETAP-AI-WORK/api/_test_mode.py:52` - Normalizes a Postman template variable by substituting empty/unresolved placeholders with a default
- `_normalize_email` in `ETAP-AI-WORK/api/email_otp.py:100` - Normalizes an email address by handling unsubstituted Postman template variables
- `_normalize_code` in `ETAP-AI-WORK/api/email_otp.py:106` - Normalizes an OTP code by handling empty or template placeholder values
- `_normalize_token` in `ETAP-AI-WORK/api/magic_links.py:136` - Normalizes a magic link token by handling empty or template placeholder values

**Differences:** All four functions implement the same pattern: check if a string is empty or contains unresolved Postman template markers (like {{...}}), and substitute a default value. They differ only in the semantic name of the input (email, code, token, generic var) and the default value used. The core logic is identical.

**Recommendation:** Keep `api/_test_mode.py::normalize_template_var (already the most generic)` - All four functions share the identical template-variable normalization pattern. The existing normalize_template_var is already the most generic implementation. The other three wrappers (_normalize_email, _normalize_code, _normalize_token) should call it directly rather than reimplementing the same logic.

---

### Parse a string to an integer with a fallback default value on failure

**Category:** string-error-crypto

**Functions:**
- `_parse_id` in `ETAP-AI-WORK/etap_integration/sync_engine.py:545` - Parses a string ID to an integer with fallback default
- `_parse_int` in `ETAP-AI-WORK/api/akamai_protection.py:298` - Parse an optional string value to an integer, returning None on failure

**Differences:** Both parse strings to integers with safe fallback. _parse_id returns a default integer; _parse_int returns None on failure. The difference is only in the fallback value (None vs. a specific default). Core try/except pattern is identical.

**Recommendation:** Keep `utils/parsing.py (new shared utility)` - The same safe-int-parsing pattern is reimplemented in multiple modules. A single safe_int(value, default=None) utility would serve both callers. The default parameter handles the None vs. specific-default difference.

---

### Construct a JSON-RPC 2.0 error response envelope

**Category:** string-error-crypto

**Functions:**
- `to_wire` in `ETAP-AI-WORK/acp_runtime/acp/errors.py:40` - Serializes an error object as a JSON-RPC 2.0 error response
- `_error_response` in `ETAP-AI-WORK/acp_runtime/acp/router/router.py:407` - Constructs a JSON-RPC error response envelope
- `_send_parse_error` in `ETAP-AI-WORK/acp_runtime/acp/transport/server.py:110` - Sends a JSON-RPC parse error response to the client

**Differences:** to_wire is the canonical serialization method on the error object. _error_response re-implements the same JSON-RPC envelope construction in the router. _send_parse_error is a specialized version for parse errors that also sends the response. All three build the same JSON-RPC error structure: {jsonrpc: '2.0', error: {...}, id: ...}.

**Recommendation:** Keep `acp_runtime/acp/errors.py::to_wire` - The to_wire method on the error object is the canonical serialization. The router's _error_response and the server's _send_parse_error should delegate to to_wire instead of re-building the JSON-RPC envelope. This ensures consistent error formatting and a single point of change for the wire format.

---

### Fernet symmetric encryption/decryption of secrets (cipher initialization, encrypt, decrypt)

**Category:** string-error-crypto

**Functions:**
- `_init_cipher` in `ETAP-AI-WORK/services/api_key_store.py:147` - Initializes Fernet cipher for AES-256 encryption of API keys
- `_encrypt` in `ETAP-AI-WORK/services/api_key_store.py:176` - Encrypts a plaintext string into base64 ciphertext using Fernet
- `_decrypt` in `ETAP-AI-WORK/services/api_key_store.py:185` - Decrypts a base64 ciphertext back to plaintext using Fernet
- `_get_cipher` in `ETAP-AI-WORK/security/secrets_manager.py:55` - Gets the Fernet cipher for secret encryption/decryption; same pattern as _init_cipher
- `encrypt_secret` in `ETAP-AI-WORK/security/security_framework.py:363` - Encrypts a secret value using Fernet symmetric encryption; same as _encrypt
- `decrypt_secret` in `ETAP-AI-WORK/security/security_framework.py:367` - Decrypts a secret value using Fernet symmetric encryption; same as _decrypt

**Differences:** All three modules implement the same Fernet encrypt/decrypt pattern. _init_cipher and _get_cipher both lazily initialize a Fernet instance from an environment key. _encrypt/encrypt_secret and _decrypt/decrypt_secret perform the same Fernet.encrypt()/decrypt() operations. The only differences are the key source (env var names) and the storage backend (SQLite vs Vault vs in-memory).

**Recommendation:** Keep `security/crypto_utils.py (new shared module with FernetCipher class)` - Three independent Fernet cipher implementations exist. A shared FernetCipher class that handles key loading, lazy initialization, encrypt, and decrypt would eliminate the duplication. Each consumer (api_key_store, secrets_manager, security_framework) would instantiate FernetCipher with its key source. This also ensures consistent error handling and key rotation support.

---

### Password hashing and verification using bcrypt

**Category:** string-error-crypto

**Functions:**
- `_hash_password` in `ETAP-AI-WORK/api/auth.py:467` - Hashes a plaintext password using bcrypt with 14 rounds
- `_verify_password` in `ETAP-AI-WORK/api/auth.py:473` - Verifies that a plaintext password matches a bcrypt hashed password
- `_hash_password` in `ETAP-AI-WORK/security/security_framework.py:226` - Internal password hashing implementation (likely bcrypt)
- `_verify_password` in `ETAP-AI-WORK/security/security_framework.py:230` - Internal password verification implementation (likely bcrypt)

**Differences:** Both pairs implement the same bcrypt.hashpw/bcrypt.checkpw pattern. The api/auth.py version specifies 14 rounds explicitly. The security_framework.py version may use different rounds or configuration. The function names are identical, suggesting they were likely copied from one to the other.

**Recommendation:** Keep `security/security_framework.py::_hash_password / _verify_password` - Password hashing/verification is a security-critical operation that should have a single canonical implementation. The security_framework module is the appropriate home. api/auth.py should import and delegate to the security_framework implementation rather than duplicating it. This also ensures consistent bcrypt round configuration across the codebase.

---

### Create signed JWT tokens for authentication

**Category:** string-error-crypto

**Functions:**
- `_create_access_token` in `ETAP-AI-WORK/api/auth.py:478` - Creates a short-lived JWT access token for a user with given role
- `_create_refresh_token` in `ETAP-AI-WORK/api/auth.py:491` - Creates a longer-lived JWT refresh token for a user
- `issue` in `ETAP-AI-WORK/acp_runtime/acp/security/auth.py:170` - Issues a new signed JWT token for a given caller with scopes
- `_generate_token` in `ETAP-AI-WORK/security/security_framework.py:310` - Internal token generation implementation

**Differences:** All four create signed JWT tokens. _create_access_token and _create_refresh_token differ only in TTL and claims (role vs. refresh). The ACP issue() method uses a different signing key/claims structure (scope-based). _generate_token in security_framework may use a different algorithm or key. All follow the josejwt.encode pattern with different payload structures.

**Recommendation:** Keep `security/token_service.py (new unified token service)` - Four JWT token creation functions exist across three modules. The ACP token system uses a different claims structure (scopes vs. roles) and may legitimately need separate signing keys. However, the api/auth.py pair and security_framework._generate_token likely overlap. A unified TokenService with configurable TTL, claims, and signing key would reduce duplication while accommodating the different use cases. The ACP tokens may need to remain separate due to the different protocol context.

---

### API key storage and retrieval with Fernet encryption (CRUD operations for API keys)

**Category:** string-error-crypto

**Functions:**
- `set_key` in `ETAP-AI-WORK/services/api_key_store.py:222` - Stores an API key in the encrypted SQLite database
- `get_key` in `ETAP-AI-WORK/services/api_key_store.py:272` - Retrieves and decrypts an API key from the database
- `delete_key` in `ETAP-AI-WORK/services/api_key_store.py:338` - Deletes an API key from the database
- `set_api_key` in `ETAP-AI-WORK/security/secrets_manager.py:304` - Stores an API key in the secrets manager (Vault or local fallback)
- `get_api_key` in `ETAP-AI-WORK/security/secrets_manager.py:315` - Retrieves an API key from the secrets manager
- `delete_api_key` in `ETAP-AI-WORK/security/secrets_manager.py:360` - Deletes a stored API key from the secrets manager

**Differences:** Both provide CRUD operations for API keys with encryption. api_key_store uses SQLite as the backend; secrets_manager uses Vault with local file fallback. The interface is nearly identical (set/get/delete by service name). The secrets_manager also supports key rotation (rotate_key) which api_key_store lacks.

**Recommendation:** Keep `security/secrets_manager.py (enhanced as the single API key store)` - Two parallel API key storage systems exist with nearly identical interfaces. The secrets_manager is more feature-rich (Vault integration, key rotation) and is the appropriate centralized location. api_key_store should be deprecated in favor of secrets_manager, which already supports the same operations plus additional features. Migration path: add any missing SQLite-specific features to secrets_manager, then redirect api_key_store consumers.

---

### Check if ETAP is responsive via COM ping

**Category:** string-error-crypto

**Functions:**
- `is_etap_responsive` in `ETAP-AI-WORK/etap_integration/etap_error_recovery.py:246` - Public API: pings ETAP via COM to verify responsiveness
- `_ping_etap_com` in `ETAP-AI-WORK/etap_integration/etap_error_recovery.py:357` - Private helper: pings ETAP via COM to check if it is responsive

**Differences:** Both functions ping ETAP via COM to check responsiveness. is_etap_responsive is the public-facing wrapper; _ping_etap_com is the internal implementation. They likely do the same thing with slightly different error handling or return values.

**Recommendation:** Keep `etap_integration/etap_error_recovery.py::is_etap_responsive` - Two functions in the same module performing the same COM ping check. The private _ping_etap_com should be inlined into is_etap_responsive, or is_etap_responsive should be the sole implementation with _ping_etap_com removed.

---

### Cross-category: Mask or sanitize sensitive data for safe display/logging (string-utils ↔ crypto)

**Category:** string-error-crypto

**Functions:**
- `_mask_key` in `ETAP-AI-WORK/services/api_key_store.py:101` - [string-utils] Masks a key string by showing only the last few characters with asterisks
- `sanitize_result` in `ETAP-AI-WORK/api/shared_handlers.py:570` - [string-utils] Sanitizes result output to remove sensitive data before API response
- `_sanitize_string_input` in `ETAP-AI-WORK/etap_integration/etap_com.py:1027` - [string-utils] Sanitizes string input by removing dangerous characters and truncating
- `_sanitize_metric_name` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:319` - [string-utils] Sanitizes a metric name to comply with Prometheus naming rules

**Differences:** All perform sanitization but with different targets: _mask_key masks sensitive values for display (security); sanitize_result removes sensitive data from API responses (security/privacy); _sanitize_string_input removes dangerous characters from input (injection prevention); _sanitize_metric_name enforces naming conventions (format compliance). The unifying theme is 'make a string safe,' but the safety concern differs (security display vs. privacy vs. injection vs. format).

**Recommendation:** Keep `security/sanitization.py (new shared module with categorized sanitizers)` - Four different sanitization functions exist with overlapping but distinct purposes. A shared sanitization module could provide: mask_sensitive(value, visible_chars=4) for display, sanitize_for_output(data, rules) for API responses, sanitize_input(value, max_len) for injection prevention, and sanitize_name(value, pattern) for format compliance. This would centralize the sanitization logic while keeping the different safety concerns clearly separated.

---

### Validate password meets strength requirements (length, common-password check)

**Category:** validation

**Functions:**
- `_validate_password_strength` in `ETAP-AI-WORK/api/auth.py:43` - Private helper: checks len>=8 and not in _COMMON_PASSWORDS. Returns validated string.
- `validate_new_password` in `ETAP-AI-WORK/api/auth.py:378` - Pydantic field_validator on ChangePasswordRequest.new_password — directly delegates to _validate_password_strength(v)
- `validate_new_password` in `ETAP-AI-WORK/api/auth.py:401` - Pydantic field_validator on ResetPasswordRequest.new_password — directly delegates to _validate_password_strength(v). Identical to line 378 version.

**Differences:** The two validate_new_password validators (lines 378 and 401) are identical — both simply call _validate_password_strength(v). The validate_password_strength at line 328 on RegisterRequest adds an extra check: password must not contain username. _validate_password_strength itself is the core logic (8-char minimum + common password check).

**Recommendation:** Keep `_validate_password_strength (line 43)` - The two validate_new_password methods are pure delegation wrappers with identical bodies. They can remain as Pydantic field_validators but should call a single shared function. The validate_password_strength on RegisterRequest (line 328) could also delegate to _validate_password_strength and add the username check as an additional step, reducing the duplicated len/common-password logic.

---

### Sliding-window rate limit check per client identifier, returning True if allowed

**Category:** validation

**Functions:**
- `is_allowed` in `ETAP-AI-WORK/api/_rate_limit.py:34` - RateLimiter.is_allowed(key) — canonical implementation using module-level _store dict. Sliding window with pruning.
- `_rate_limit_check` in `ETAP-AI-WORK/api/akamai_protection.py:308` - Thin wrapper: delegates to _rate_limiter.is_allowed(client_ip). Kept for backward compatibility.
- `_rate_limit_check` in `ETAP-AI-WORK/api/cloudflare_protection.py:273` - Thin wrapper: delegates to _rate_limiter.is_allowed(client_ip). Identical implementation to akamai version.

**Differences:** The akamai and cloudflare _rate_limit_check functions are identical one-line wrappers delegating to RateLimiter.is_allowed. The RateLimiter class in _rate_limit.py was already extracted as a consolidation effort (documented in its module header). However, the two wrapper functions still exist as identical code in separate modules.

**Recommendation:** Keep `RateLimiter.is_allowed in api/_rate_limit.py` - Already partially consolidated — RateLimiter extracted. The remaining _rate_limit_check wrappers in akamai_protection.py and cloudflare_protection.py are identical one-liners. Callers should import RateLimiter directly or use a single shared alias, removing the two identical wrapper functions.

---

### Validate and normalize OTP purpose string (strip, lowercase, check against allowed set)

**Category:** validation

**Functions:**
- `_validate_purpose` in `ETAP-AI-WORK/api/email_otp.py:71` - Pydantic field_validator on SendOtpRequest.purpose: v.strip().lower(), check v in VALID_PURPOSES, raise ValueError if not.
- `_validate_purpose` in `ETAP-AI-WORK/api/email_otp.py:92` - Pydantic field_validator on VerifyOtpRequest.purpose: identical logic — v.strip().lower(), check v in VALID_PURPOSES, raise ValueError if not.

**Differences:** No implementation differences. The two validators have identical bodies (strip, lowercase, check against VALID_PURPOSES set). They are on two different Pydantic models (SendOtpRequest and VerifyOtpRequest) but perform exactly the same validation.

**Recommendation:** Keep `Extract a shared _validate_purpose helper function` - Both validators have identical logic. A single module-level helper function can be defined and both field_validators can delegate to it. This is standard Pydantic practice for shared validation across models.

---

### Check whether caller scopes permit invoking a capability (set intersection check)

**Category:** validation

**Functions:**
- `is_permitted` in `ETAP-AI-WORK/acp_runtime/acp/router/scope.py:34` - Method on ScopeValidator class. Checks if caller scopes (stored in self._scopes) intersect with required scopes. Returns True if required is empty (public capability).
- `check_scope` in `ETAP-AI-WORK/acp_runtime/acp/router/scope.py:48` - Standalone function. Docstring explicitly states: 'Functional equivalent of ScopeValidator.is_permitted'. Validates each scope string before checking intersection.

**Differences:** check_scope validates each string in caller_scopes against is_valid_scope before performing the intersection. is_permitted relies on validation already done in ScopeValidator.__init__. Otherwise, the intersection logic is identical.

**Recommendation:** Keep `ScopeValidator.is_permitted` - Explicitly documented as duplicate ('functional equivalent'). check_scope can be replaced by constructing a ScopeValidator and calling is_permitted, or check_scope can be simplified to just call ScopeValidator(scopes).is_permitted(required). Keeping both adds confusion about which to use.

---

### Validate a string matches a lowercase alphanumeric name pattern (regex-based)

**Category:** validation

**Functions:**
- `is_valid_capability_name` in `ETAP-AI-WORK/acp_runtime/acp/schema/capability.py:22` - Checks name against CAPABILITY_NAME_PATTERN regex r'^[a-z][a-z0-9_.\-]{0,127}$'. Returns bool.
- `is_valid_scope` in `ETAP-AI-WORK/acp_runtime/acp/schema/capability.py:26` - Checks scope against SCOPE_PATTERN regex r'^[a-z][a-z0-9_.\-]{0,127}$'. Identical regex pattern. Returns bool.

**Differences:** Both use the identical regex pattern (^[a-z][a-z0-9_.\-]{0,127}$) and identical implementation (isinstance check + regex match). Only difference is the name of the function and the variable name of the compiled regex (_CAPABILITY_NAME_RE vs _SCOPE_RE).

**Recommendation:** Keep `Merge into a single is_valid_name function or use one as canonical` - The regex patterns and implementations are identical. If capability names and scope names should always use the same pattern, they should share a single validator. If there's a possibility the patterns may diverge in the future, they could share a generic _is_valid_identifier helper that accepts the pattern as a parameter, while keeping the public API names for readability.

---

### Clamp/enforce numeric values to stay within specified min/max bounds

**Category:** validation

**Functions:**
- `clamp_to_bounds` in `ETAP-AI-WORK/engine/numerical_safety.py:140` - NumericalGuard method. Numpy-based: accepts float or ndarray, converts to array, uses np.clip. Logs warnings when values are out of bounds. Returns ndarray.
- `enforce_bounds` in `ETAP-AI-WORK/engine/resilience.py:859` - ResilienceGuard static method. Scalar-based: accepts single float, validates min_val <= max_val, uses max(min_val, min(value, max_val)). Returns float.

**Differences:** clamp_to_bounds works on numpy arrays with logging; enforce_bounds works on scalars with validation of min/max ordering. Core logic is identical (clip to bounds). The array version has richer diagnostics; the scalar version has input validation.

**Recommendation:** Keep `clamp_to_bounds in engine/numerical_safety.py (more general, handles arrays)` - Both do value clamping. The numpy-based version is more general (handles scalars and arrays) and has better diagnostics. The scalar version's min<=max validation should be folded in. enforce_bounds callers can pass scalar values to clamp_to_bounds which will still work correctly.

---

### Coerce various image inputs (PIL.Image, bytes, path) into a PIL.Image.Image object

**Category:** vision-email

**Functions:**
- `to_pil_image` in `ETAP-AI-WORK/integrations/_vision_base.py:34` - Canonical shared implementation. Accepts (image, pil_available) parameters.
- `_to_pil_image` in `ETAP-AI-WORK/integrations/anthropic_vision.py:269` - Already delegates to _vision_base.to_pil_image — correctly consolidated.
- `_to_pil_image` in `ETAP-AI-WORK/integrations/openai_vision.py:272` - Already delegates to _vision_base.to_pil_image — correctly consolidated.
- `_to_pil_image` in `ETAP-AI-WORK/integrations/gemini_vision.py:244` - STILL HAS INLINE COPY of the full logic — does NOT delegate to _vision_base. The exact same isinstance/BytesIO/Image.open logic is duplicated.
- `_to_pil_image` in `ETAP-AI-WORK/integrations/opencv_vision.py:322` - STILL HAS INLINE COPY of the full logic — does NOT delegate to _vision_base. Same isinstance/BytesIO/Image.open pattern duplicated.

**Differences:** Anthropic and OpenAI correctly delegate to the shared _vision_base.to_pil_image. Gemini and OpenCV still contain the full inline implementation — same logic (PIL_AVAILABLE check, isinstance checks for Image.Image, bytes/bytearray, str/Path), same exception handling, same logging pattern. Only difference: _vision_base accepts a pil_available parameter while the inline versions reference their own module-level PIL_AVAILABLE flag.

**Recommendation:** Keep `_vision_base.to_pil_image` - Gemini and OpenCV should delegate to _vision_base.to_pil_image exactly like Anthropic and OpenAI already do. The _vision_base module was specifically created to eliminate this duplication (see its module docstring). Two of four consumers have been migrated; two remain as stale copies.

---

### Convert a PIL Image to a base64-encoded string for API submission

**Category:** vision-email

**Functions:**
- `image_to_base64_png` in `ETAP-AI-WORK/integrations/_vision_base.py:62` - Canonical shared: resize if >1568px, save as PNG, b64encode. Returns raw base64 (no data URL prefix).
- `image_to_data_url` in `ETAP-AI-WORK/integrations/_vision_base.py:85` - Canonical shared: wraps image_to_base64_png and prepends 'data:image/png;base64,' prefix.
- `_image_to_base64` in `ETAP-AI-WORK/integrations/anthropic_vision.py:278` - Already delegates to _vision_base.image_to_base64_png — correctly consolidated.
- `_image_to_data_url` in `ETAP-AI-WORK/integrations/openai_vision.py:281` - Already delegates to _vision_base.image_to_data_url — correctly consolidated.
- `encode_screenshot_base64` in `ETAP-AI-WORK/integrations/gemini_vision.py:310` - Different: reads a file path directly (no PIL resize step). Used for audit log embedding, not API submission. Semantically different purpose.

**Differences:** Anthropic and OpenAI correctly delegate to _vision_base helpers. Gemini's encode_screenshot_base64 is actually semantically different — it reads a raw file and base64-encodes it without any resize/PIL processing, intended for audit log embedding rather than API payload construction. The two _vision_base functions (image_to_base64_png and image_to_data_url) are not duplicates of each other — one produces raw base64, the other adds a data URL prefix. They form a layered pair.

**Recommendation:** Keep `_vision_base.image_to_base64_png + _vision_base.image_to_data_url` - The _vision_base functions are the canonical implementations and Anthropic/OpenAI already delegate correctly. Gemini's encode_screenshot_base64 serves a different purpose (file-based audit log encoding, no resize) and should remain separate. No consolidation needed — the migration to _vision_base is already complete for the relevant consumers.

---

### Analyze a screenshot to identify UI elements and recommend next action — same public API contract across multiple vision backends

**Category:** vision-email

**Functions:**
- `analyze_screenshot` in `ETAP-AI-WORK/integrations/anthropic_vision.py:178` - Anthropic Claude Vision backend. Sends base64 image via Anthropic Messages API.
- `analyze_screenshot` in `ETAP-AI-WORK/integrations/gemini_vision.py:179` - Google Gemini backend. Sends PIL image via genai SDK with inline retry loop.
- `analyze_screenshot` in `ETAP-AI-WORK/integrations/openai_vision.py:191` - OpenAI-compatible backend. Sends data URL via OpenAI Chat Completions API.
- `analyze_screenshot` in `ETAP-AI-WORK/integrations/opencv_vision.py:183` - Local offline backend. Uses OpenCV edge detection + Tesseract OCR — no network call.
- `analyze_screenshot` in `ETAP-AI-WORK/integrations/resilience.py:286` - Router/facade that tries each backend in fallback chain (Gemini → OpenAI → Anthropic → OpenCV). Delegates to the individual backends.

**Differences:** All 5 share identical public signature: (image, objective, context) -> dict|None with same output schema keys (description, ui_elements, next_action, objective_complete, confidence, source). However, the implementations are intentionally different — this is a Strategy pattern where each backend uses a different API/SDK. The resilience.py version is a facade that delegates. The structural similarity (same signature, same output schema) is by design, not accidental duplication.

**Recommendation:** Keep `All five — each backend serves a distinct purpose` - This is a deliberate Strategy pattern with multi-vendor fallback. Each backend targets a different cloud API or local processing method. The identical signature is the contract that enables resilience.py's HybridVisionRouter to swap backends transparently. Consolidating would break the fallback chain architecture.

---

### Identical SYSTEM_PROMPT string defining the Visual Perception Layer instructions and JSON output schema

**Category:** vision-email

**Functions:**
- `SYSTEM_PROMPT` in `ETAP-AI-WORK/integrations/anthropic_vision.py:79` - Exact same 40+ line string — instructions for JSON output with description, ui_elements, next_action, safety rules.
- `SYSTEM_PROMPT` in `ETAP-AI-WORK/integrations/gemini_vision.py:71` - Exact same string — identical text including safety rules, JSON schema, coordinate rules.
- `SYSTEM_PROMPT` in `ETAP-AI-WORK/integrations/openai_vision.py:85` - Exact same string — identical text. Only comment differs ('same contract as Gemini Vision').

**Differences:** The SYSTEM_PROMPT is literally the same multi-line string across all 3 cloud vision modules. Approximately 40 lines of identical text including: agent description, instructions (describe screen, identify elements, recommend action), action type definitions (click/type/hotkey/wait/done/unknown), safety rules (never click destructive dialogs), and JSON output schema. No variation at all.

**Recommendation:** Keep `_vision_base.SYSTEM_PROMPT` - Move SYSTEM_PROMPT to _vision_base.py and have all 3 cloud vision modules import it. This eliminates ~120 lines of identical duplicated text. Since _vision_base.py already exists for shared vision helpers, it's the natural location. OpenCV vision doesn't use this prompt (it's offline/heuristic), so it remains unaffected.

---

### Generate fallback HTML email body when template file is missing — 11 functions sharing identical HTML wrapper boilerplate

**Category:** vision-email

**Functions:**
- `_fallback_otp_html` in `ETAP-AI-WORK/services/email_service.py:540` - Wraps OTP code display in standard boilerplate: <!doctype html><html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
- `_fallback_reset_html` in `ETAP-AI-WORK/services/email_service.py:551` - Same boilerplate wrapper with Reset Password button link.
- `_fallback_welcome_html` in `ETAP-AI-WORK/services/email_service.py:561` - Same boilerplate wrapper with welcome message.
- `_fallback_verify_html` in `ETAP-AI-WORK/services/email_service.py:569` - Same boilerplate wrapper with Verify Email button link.
- `_fallback_login_alert_html` in `ETAP-AI-WORK/services/email_service.py:577` - Same boilerplate wrapper with red (#dc2626) heading for security alert.
- `_fallback_lockout_html` in `ETAP-AI-WORK/services/email_service.py:587` - Same boilerplate wrapper with red heading for lockout notice.
- `_fallback_notification_html` in `ETAP-AI-WORK/services/email_service.py:595` - Same boilerplate wrapper with minimal title+message content.
- `_fallback_study_html` in `ETAP-AI-WORK/services/email_service.py:602` - Same boilerplate wrapper; handles both complete (green) and failed (red) states.
- `_fallback_role_html` in `ETAP-AI-WORK/services/email_service.py:612` - Same boilerplate wrapper with role update content.
- `_fallback_pwd_change_html` in `ETAP-AI-WORK/services/email_service.py:620` - Same boilerplate wrapper with password change confirmation.
- `_fallback_critical_html` in `ETAP-AI-WORK/services/email_service.py:629` - Same boilerplate wrapper with red border-left accent and CRITICAL ALERT heading.

**Differences:** All 11 functions use the identical HTML wrapper: <!doctype html><html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">...</body></html>. They differ only in: (1) the heading color — blue (#1e40af) for informational, red (#dc2626) for security/alerts; (2) the inner content specific to each email type; (3) a few add extra styling (critical_html adds border-left). Each function is 3-8 lines of f-string HTML.

**Recommendation:** Keep `A single _fallback_html_wrapper(title, body_content, heading_color='#1e40af', extra_styles='') function in email_service.py` - Extract the repeated HTML boilerplate into a _fallback_html_wrapper() helper that accepts (title, inner_body_html, heading_color, extra_body_styles). Each _fallback_* function would then call this wrapper with its specific content, reducing ~100 lines of duplicated wrapper markup to a single shared template. The per-email content generation would remain as simple content-building helpers that return just the inner HTML, not the full document.

---

### Send an email via the Resend API — two entry points that do the same thing

**Category:** vision-email

**Functions:**
- `send` in `ETAP-AI-WORK/integrations/resend_email.py:393` - Method on ResendEmailClient class. The actual implementation: validates, rate-limits, builds payload, calls _send_with_retries.
- `send_email` in `ETAP-AI-WORK/integrations/resend_email.py:482` - Module-level convenience function. Single line: `return await resend_client.send(params)`. Pure trivial wrapper.

**Differences:** send_email is a one-line wrapper that delegates entirely to resend_client.send(). No additional logic, no transformation, no default filling. It exists purely as a convenience for callers who prefer `from integrations.resend_email import send_email` over `from integrations.resend_email import resend_client; await resend_client.send(...)`.

**Recommendation:** Keep `ResendEmailClient.send (the method)` - send_email is a trivial one-line convenience wrapper with zero added value beyond avoiding `resend_client.` prefix. Check if any callers actually use send_email directly — if they do, it's harmless but unnecessary API surface. If no callers use it, remove it. If callers exist, consider whether exposing resend_client.send directly is cleaner. Low priority — this is cosmetic duplication, not logic duplication.

---

### Send a templated email following the same structural pattern — 12 functions with identical flow

**Category:** vision-email

**Functions:**
- `send_email_otp` in `ETAP-AI-WORK/services/email_service.py:118` - Pattern: build subject → load template → build context → render or fallback → build text → resend_client.send(EmailParams)
- `send_password_reset` in `ETAP-AI-WORK/services/email_service.py:176` - Same pattern. Subject: 'Reset Your Password'. Template: password_reset.html.
- `send_welcome` in `ETAP-AI-WORK/services/email_service.py:207` - Same pattern. Subject: 'Welcome to ...'. Template: welcome.html.
- `send_email_verification` in `ETAP-AI-WORK/services/email_service.py:232` - Same pattern. Subject: 'Verify Your Email'. Template: verify_email.html.
- `send_login_alert` in `ETAP-AI-WORK/services/email_service.py:260` - Same pattern. Subject: 'New Login'. Template: login_alert.html.
- `send_account_lockout` in `ETAP-AI-WORK/services/email_service.py:299` - Same pattern. Subject: 'Account Locked'. Template: lockout.html.
- `send_notification_email` in `ETAP-AI-WORK/services/email_service.py:334` - Same pattern. Subject: '[Brand] title'. Template: notification.html.
- `send_study_complete_email` in `ETAP-AI-WORK/services/email_service.py:369` - Same pattern. Subject: 'Study Completed'. Template: study_complete.html.
- `send_study_failed_email` in `ETAP-AI-WORK/services/email_service.py:403` - Same pattern. Subject: 'Study Failed'. Template: study_failed.html.
- `send_role_change_email` in `ETAP-AI-WORK/services/email_service.py:435` - Same pattern. Subject: 'Role Updated'. Template: role_change.html.
- `send_password_change_email` in `ETAP-AI-WORK/services/email_service.py:466` - Same pattern. Subject: 'Password Changed'. Template: password_change.html.
- `send_critical_alert` in `ETAP-AI-WORK/services/email_service.py:502` - Same pattern. Subject: '[CRITICAL] ...'. Template: critical_alert.html.

**Differences:** All 12 functions follow the exact same 6-step structural pattern: (1) compose subject line from _BRAND_NAME + purpose label, (2) load template via _load_template(name), (3) build context dict via _common_context(**specific_kwargs), (4) render template OR call fallback HTML function, (5) compose plain-text version, (6) call resend_client.send(EmailParams(to, subject, html, text, tags)). They differ only in: subject text, template filename, context keys/values, fallback function name, and tags. The code structure is mechanically identical across all 12.

**Recommendation:** Keep `A generic _send_templated_email(subject, template_name, ctx, text_body, fallback_func, tags) helper + keep thin public wrappers` - Extract the repeated 6-step pattern into a private _send_templated_email() helper. Each public send_* function would become a 5-10 line thin wrapper that just provides its specific parameters (subject formula, template name, context kwargs, text body, fallback func, tags) and calls the helper. This eliminates ~400 lines of structural duplication while preserving the clear public API (each flow remains a named function with typed parameters). The helper encapsulates the template-loading-or-fallback decision, EmailParams construction, and resend_client.send() call.

---


## MEDIUM Confidence Duplicates

These functions likely do the same thing. Investigate before consolidating.

### Domain-specific retry that duplicates general retry mechanisms

**Category:** async-utils

**Functions:**
- `_send_with_retry` in `ETAP-AI-WORK/security/siem.py:402` - Async retry for SIEM event forwarding; hand-rolled exponential backoff (delay *= 2); returns bool instead of raising; domain-specific (SecurityEvent batching)
- `_initialize_cache_with_retry` in `ETAP-AI-WORK/core/bootstrap.py:385` - Async retry for cache initialization; hand-rolled exponential backoff (2**attempt sleep); falls back to in-memory cache on exhaustion; domain-specific (StudyCache)

**Differences:** Both embed hand-rolled exponential backoff retry logic inline, duplicating what the general retry mechanisms already provide. _send_with_retry doubles delay each attempt and returns bool. _initialize_cache_with_retry uses 2**attempt sleep and falls back gracefully. Both could delegate to an existing RetryHandler.async_execute or tenacity-based decorator rather than reimplementing retry logic.

**Recommendation:** CONSOLIDATE - These domain-specific functions embed their own retry logic, which duplicates the general retry mechanisms. They should keep their domain-specific behavior (fallback logic, SIEM-specific stats tracking) but delegate the retry loop to RetryHandler.async_execute or a tenacity decorator, eliminating the duplicated backoff computation and error handling.

---

### Determine which exceptions should trigger a retry

**Category:** async-utils

**Functions:**
- `_default_retryable` in `ETAP-AI-WORK/engine/resilience.py:108` - Checks if exception is ConnectionError, TimeoutError, or IOError; default predicate for RetryHandler
- `_is_retryable` in `ETAP-AI-WORK/engine/resilience.py:226` - Configurable retryable check; uses provided exception types or falls back to _default_retryable
- `network_retry` in `ETAP-AI-WORK/core/retry.py:36` - Uses tenacity retry_if_exception_type((ConnectionError, TimeoutError, OSError)) inline — same logic as _default_retryable but via tenacity
- `skill_retry` in `ETAP-AI-WORK/core/retry.py:70` - Uses tenacity retry_if_exception_type((ImportError, ModuleNotFoundError)) — different exception set for skill loading

**Differences:** _default_retryable and network_retry both check for ConnectionError/TimeoutError/OSError (IOError vs OSError — these are aliases in Python 3). _is_retryable is a configurable version that delegates to custom predicates. skill_retry uses a different exception set (ImportError/ModuleNotFoundError). The logic is duplicated between the hand-rolled _default_retryable and the tenacity-based retry_if_exception_type in network_retry.

**Recommendation:** INVESTIGATE - The retryable exception classification is a supporting mechanism for the retry logic, not a standalone duplicate. The duplication between _default_retryable and tenacity's retry_if_exception_type is minor. However, a single canonical list of 'network retryable exceptions' should be defined once (e.g., in core/retry.py) and referenced by both the tenacity decorators and the RetryHandler, rather than hardcoded independently in each.

---

### Compute exponential backoff delay for retry attempts

**Category:** async-utils

**Functions:**
- `_compute_delay` in `ETAP-AI-WORK/engine/resilience.py:100` - Method on RetryHandler: delay = base_delay * exponential_base^attempt, capped at max_delay, with optional jitter
- `retry_with_backoff` in `ETAP-AI-WORK/integrations/resilience.py:58` - Inline: min(base_delay * 2^(attempt-1), max_delay) — same formula but hardcoded exponential_base=2
- `retry_with_backoff` in `ETAP-AI-WORK/integrations/_vision_base.py:97` - Inline: backoff_seconds * 2^(attempt-1) — same formula but no max_delay cap
- `_send_with_retry` in `ETAP-AI-WORK/security/siem.py:402` - Inline: delay *= 2 (multiplicative doubling) — simplest variant
- `_initialize_cache_with_retry` in `ETAP-AI-WORK/core/bootstrap.py:385` - Inline: asyncio.sleep(2**attempt) — pure power-of-2 sleep

**Differences:** All five implementations compute the same mathematical pattern (exponential delay growth), but with different levels of sophistication: _compute_delay is the most complete (configurable base, exponential_base, max_delay cap, jitter). The others are simplified inline versions that hardcode exponential_base=2 and lack either max_delay caps or jitter. This is a supporting computation for the retry logic rather than a standalone duplicate.

**Recommendation:** INVESTIGATE - The backoff computation is a supporting detail of retry implementations. Once the retry implementations are consolidated (see Group 1), the inline backoff computations will naturally be eliminated. The canonical approach should be either RetryHandler._compute_delay or tenacity's wait_exponential, both already available.

---

### Return the number of entries currently in the cache

**Category:** caching

**Functions:**
- `dbsize` in `ETAP-AI-WORK/engine/caching.py:123` - Returns the number of non-expired entries in the in-memory cache — StudyCache low-level
- `set_cache_entries` in `ETAP-AI-WORK/core/metrics.py:313` - Update the Prometheus cache-entry gauge to current count — uses cache size for monitoring

**Differences:** dbsize is a direct count of cache entries. set_cache_entries reads the cache size and publishes it to Prometheus. They serve overlapping purposes: dbsize is a query, set_cache_entries is a metrics push that relies on size data. dbsize's output is also contained within get_stats (which reports entry_count).

**Recommendation:** INVESTIGATE - dbsize is redundant with the entry_count field in get_stats. If a lightweight count is needed, add a size property to the consolidated CacheManager. set_cache_entries should call get_stats()['entry_count'] or CacheManager.size rather than having its own counting logic.

---

### Invalidate all cache entries for a specific category/tag

**Category:** caching

**Functions:**
- `invalidate_by_tag` in `ETAP-AI-WORK/engine/cache_manager.py:168` - Remove all cache entries associated with a given tag — CalculationCache, tag-based grouping
- `invalidate_study_type` in `ETAP-AI-WORK/engine/caching.py:368` - Invalidate all cached results for a given study type — StudyCache, study-type grouping

**Differences:** Both remove a group of entries filtered by a category. invalidate_by_tag uses a generic tag system (any string tag). invalidate_study_type uses the study type as the grouping criterion. invalidate_by_tag is more general; invalidate_study_type is a domain-specific specialization of the same pattern.

**Recommendation:** CONSOLIDATE - invalidate_by_tag is the general-purpose version. Study types can be stored as tags on entries, so invalidate_study_type becomes a simple call to invalidate_by_tag(study_type_tag). This eliminates the need for a separate study-type invalidation method.

---

### Report cache memory usage and provide optimization recommendations

**Category:** caching

**Functions:**
- `get_memory_usage` in `ETAP-AI-WORK/engine/cache_manager.py:425` - Reports cache memory usage: entry count and estimated bytes
- `get_memory_report` in `ETAP-AI-WORK/engine/cache_manager.py:508` - Generates a detailed memory report including recommendations
- `_generate_recommendations` in `ETAP-AI-WORK/engine/cache_manager.py:517` - Generates optimization recommendations based on memory usage and stats

**Differences:** get_memory_usage is a compact summary (count + bytes). get_memory_report is a detailed analysis that wraps get_memory_usage and adds recommendations via _generate_recommendations. These are layered, not duplicated — but get_memory_report could subsume get_memory_usage entirely if callers always want the full report.

**Recommendation:** INVESTIGATE - get_memory_report already includes get_memory_usage data. Consider whether any caller needs only the compact summary; if not, merge get_memory_usage into get_memory_report as the sole reporting method, or keep get_memory_usage as a lightweight alternative for frequent polling.

---

### Evict cache entries under memory/size pressure

**Category:** caching

**Functions:**
- `_evict_if_needed` in `ETAP-AI-WORK/engine/cache_manager.py:247` - Evict LRU entries when adding new data would exceed size limits — size-based eviction
- `evict_if_needed` in `ETAP-AI-WORK/engine/cache_manager.py:455` - Evict entries if memory pressure exceeds configured threshold — memory-pressure eviction
- `evict_one_lru` in `ETAP-AI-WORK/engine/cache_manager.py:272` - Evict the least-recently-used entry under its own lock — single LRU eviction

**Differences:** _evict_if_needed (line 247) is triggered on set() when the cache would exceed its configured max size. evict_if_needed (line 455) is triggered by external memory pressure monitoring. evict_one_lru evicts exactly one entry. These are complementary eviction strategies (size-based vs memory-pressure vs single-entry), not true duplicates, but they share the same underlying eviction mechanism.

**Recommendation:** KEEP_SEPARATE - These serve different eviction triggers (size limit vs memory pressure vs explicit single eviction) and are correctly layered. However, they should share a single internal eviction helper to avoid duplicating the LRU/LFU selection logic.

---

### Build BusRecord/BranchRecord objects from different input formats (CSV row vs JSON dict)

**Category:** data-transform

**Functions:**
- `_make_bus_record` in `ETAP-AI-WORK/api/data_import.py:185` - Builds BusRecord from CSV DictReader row (string values, .strip(), float coercion with 'if row.get()')
- `_json_bus_record` in `ETAP-AI-WORK/api/data_import.py:208` - Builds BusRecord from JSON dict (mixed types, 'is not None' checks, accepts id/name/aliases)
- `_make_branch_record` in `ETAP-AI-WORK/api/data_import.py:195` - Builds BranchRecord from CSV DictReader row
- `_json_branch_record` in `ETAP-AI-WORK/api/data_import.py:218` - Builds BranchRecord from JSON dict (accepts from_bus/from/source aliases, to_bus/to/target aliases)

**Differences:** CSV versions receive string-valued dicts and do .strip() + conditional float() coercion. JSON versions receive mixed-type dicts with 'is not None' checks and accept more key aliases (from_bus/from/source). Both produce the same BusRecord/BranchRecord output types.

**Recommendation:** CONSOLIDATE - The JSON versions are more flexible (accept aliases, handle typed values). Create a unified _normalize_bus_input(raw_dict) that normalizes key names and types, then a single _build_bus_record(normalized) factory. CSV rows can be pre-normalized into the same format, eliminating the need for separate _make_bus_record/_json_bus_record.

---

### get_impedance method duplicated across multiple core model classes

**Category:** electrical-eng-digital-twin

**Functions:**
- `get_impedance` in `ETAP-AI-WORK/core_model/generator.py:69` - Returns impedance dict lookup: self.impedance.get(seq, complex(0, 0))
- `get_impedance` in `ETAP-AI-WORK/core_model/line.py:54` - Returns seq-based lookup: z1/z2/z0 with ValueError for invalid seq
- `get_impedance` in `ETAP-AI-WORK/core_model/transformer.py:62` - Returns seq-based lookup: z1/z2/z0 with ValueError for invalid seq — identical to Line
- `get_impedance` in `ETAP-AI-WORK/core_model/load.py:57` - Returns impedance dict lookup: self.impedance.get(seq, complex(1e9, 0))

**Differences:** Three distinct implementation patterns exist: (1) Generator/Load use dict.get() with a default (0+0j for Generator, 1e9+0j for Load — the 1e9 default models an open circuit for loads); (2) Line/Transformer use explicit if/elif with ValueError for invalid sequence — structurally identical code between Line and Transformer. All share the same signature get_impedance(seq='1'). This is polymorphic by design (system.build_sequence_networks calls get_impedance on any branch element), but Line and Transformer have truly identical implementations that could share a base class.

**Recommendation:** INVESTIGATE - Line and Transformer have character-identical get_impedance and get_shunt_admittance implementations. Extract a SequenceImpedanceMixin or BranchElementBase that provides these methods. Generator and Load have different default values and should keep their own implementations. The polymorphic intent is correct — this is about reducing copy-paste, not removing functional overlap.

---

### to_dict serialization — 10 instances across digital twin state_store and validation_gateway

**Category:** electrical-eng-digital-twin

**Functions:**
- `to_dict (BusState)` in `ETAP-AI-WORK/digital_twin/state_store.py:51` - Serialize BusState fields to dict
- `to_dict (SwitchState)` in `ETAP-AI-WORK/digital_twin/state_store.py:74` - Serialize SwitchState fields to dict
- `to_dict (GeneratorState)` in `ETAP-AI-WORK/digital_twin/state_store.py:93` - Serialize GeneratorState fields to dict
- `to_dict (LoadState)` in `ETAP-AI-WORK/digital_twin/state_store.py:113` - Serialize LoadState fields to dict
- `to_dict (StateSnapshot)` in `ETAP-AI-WORK/digital_twin/state_store.py:137` - Serialize StateSnapshot with bus voltages to dict
- `to_dict (DigitalTwinStateStore)` in `ETAP-AI-WORK/digital_twin/state_store.py:191` - Serialize state store version data to dict
- `to_json (StateSnapshot)` in `ETAP-AI-WORK/digital_twin/state_store.py:226` - Serialize to JSON string (calls to_dict + json.dumps)
- `to_dict (ValidationResult)` in `ETAP-AI-WORK/digital_twin/validation_gateway.py:74` - Serialize validation result data to dict
- `to_dict (ValidationGateway)` in `ETAP-AI-WORK/digital_twin/validation_gateway.py:97` - Serialize validation gateway statistics to dict

**Differences:** Each to_dict method operates on a different dataclass/class with different fields, but all follow the same pattern: manually enumerating fields into a plain dict, handling complex numbers by splitting into real/imag. The BusState/SwitchState/GeneratorState/LoadState to_dicts are structural clones — enumerate dataclass fields, split complex values. StateSnapshot.to_dict calls sub-object to_dicts. ValidationResult and ValidationGateway have different fields. to_json is a trivial wrapper over to_dict + json.dumps. The pattern of manually writing to_dict for each dataclass is boilerplate that Python dataclasses can automate.

**Recommendation:** CONSOLIDATE - Replace 9 manual to_dict implementations with a generic dataclass serialization utility (e.g., using dataclasses.asdict with a custom complex-number encoder, or a reusable SerializationMixin). This eliminates ~200 lines of boilerplate and ensures consistent handling of complex numbers, nested objects, and missing fields. Keep to_json as a thin wrapper over the shared serializer.

---

### Fault analysis / short circuit — DT refresh method wraps core EE fault engine

**Category:** electrical-eng-digital-twin

**Functions:**
- `_refresh_short_circuit` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:597` - DT: refreshes short circuit results from current state
- `run_fault_analysis` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:1236` - DT public API: runs fault analysis on bound system
- `three_phase_fault` in `ETAP-AI-WORK/fault_analysis/fault.py:97` - Core EE: compute 3-phase fault current at a bus
- `line_to_ground_fault` in `ETAP-AI-WORK/fault_analysis/fault.py:123` - Core EE: compute SLG fault current
- `line_to_line_fault` in `ETAP-AI-WORK/fault_analysis/fault.py:148` - Core EE: compute LL fault current
- `double_line_to_ground_fault` in `ETAP-AI-WORK/fault_analysis/fault.py:175` - Core EE: compute DLG fault current
- `_compute_zbus` in `ETAP-AI-WORK/fault_analysis/iec60909_engine.py:120` - IEC 60909: Zbus computation for standardized fault analysis

**Differences:** The DT methods (_refresh_short_circuit, run_fault_analysis) orchestrate fault analysis by rebuilding the system topology and then calling the core fault.py functions. They add DT-specific bookkeeping (snapshot updates, event publishing). The core fault.py functions are pure computation (Zbus inversion + sequence network math). The DT methods are not code-level duplicates — they delegate — but they represent overlapping orchestration: run_fault_analysis and _refresh_short_circuit both trigger fault computation in the same class, similar to the load flow pattern.

**Recommendation:** INVESTIGATE - The DT orchestration methods should be simplified to a single entry point that delegates to the core fault engine. _refresh_short_circuit and run_fault_analysis should be unified (similar to load flow recommendation). The core EE modules should remain as pure computation engines. ETAP fault analysis (etap_com._run_short_circuit) should stay separate as it uses a different execution platform.

---

### Arc flash refresh — DT method wraps core EE arc flash engine

**Category:** electrical-eng-digital-twin

**Functions:**
- `_refresh_arc_flash` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:607` - DT: refreshes arc flash results from current fault data, calls arc_flash_engine
- `calculate_arc_flash` in `ETAP-AI-WORK/fault_analysis/arc_flash_calc.py:36` - Convenience wrapper around ArcFlashEngine
- `calculate` in `ETAP-AI-WORK/fault_analysis/arc_flash_engine.py:461` - Complete IEEE 1584 arc flash computation
- `_run_arc_flash` in `ETAP-AI-WORK/etap_integration/etap_com.py:423` - ETAP COM: arc flash study via external ETAP application

**Differences:** _refresh_arc_flash in DT core calls arc_flash_calc.calculate_arc_flash or ArcFlashEngine directly, adds DT bookkeeping (snapshot update, propagation logging). The etap_com._run_arc_flash is genuinely different (external tool). The DT method and arc_flash_calc wrapper both serve as orchestration layers over the same ArcFlashEngine.calculate core. Having both a convenience wrapper AND a DT refresh method adds unnecessary indirection.

**Recommendation:** INVESTIGATE - After removing arc_flash_calc.py wrapper (recommendation #2), the DT's _refresh_arc_flash should call ArcFlashEngine.calculate directly. This removes one layer of indirection. ETAP COM arc flash should remain separate. The pattern of DT refresh methods adding snapshot/logging bookkeeping is intentional and should be preserved, but the delegation chain should be shortened.

---

### Protection coordination — DT refresh method wraps core EE coordination engine

**Category:** electrical-eng-digital-twin

**Functions:**
- `_refresh_protection` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:676` - DT: refreshes protection coordination from current fault data
- `run_protection_coordination` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:1273` - DT public API: runs protection coordination analysis
- `check_coordination` in `ETAP-AI-WORK/coordination/coordination.py:32` - Core EE: coordination check between two relays
- `check_coordination_range` in `ETAP-AI-WORK/coordination/coordination.py:71` - Core EE: coordination check across fault current range
- `verify_coordination` in `ETAP-AI-WORK/agents/coordination_agent.py:187` - Agent-level: reimplements coordination logic (see group #3)
- `_run_protection_coordination` in `ETAP-AI-WORK/etap_integration/etap_com.py:794` - ETAP COM: protection coordination via external ETAP

**Differences:** Three overlapping layers: (1) CoordinationEngine (core computation), (2) CoordinationAgent (reimplemented logic — duplicate, see group #3), (3) DT refresh/public methods (orchestration with DT bookkeeping). The DT methods delegate to CoordinationEngine but add snapshot updates and event logging. Again, _refresh_protection and run_protection_coordination are two entry points in the same DT class for the same computation.

**Recommendation:** INVESTIGATE - After consolidating CoordinationAgent to delegate to CoordinationEngine (group #3), simplify DT's protection coordination to a single public method (run_protection_coordination) that handles both on-demand analysis and propagation-pipeline refresh. ETAP COM method stays separate.

---

### Publish/emit/propagate an event to subscribers or downstream handlers

**Category:** logging-config-event

**Functions:**
- `publish` in `ETAP-AI-WORK/digital_twin/event_bus.py:384` - Publish domain event to all subscribed handlers
- `emit` in `ETAP-AI-WORK/acp_runtime/acp/runtime/progress.py:89` - Record and optionally transmit a progress event
- `propagate_switch_change` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:438` - Propagate switch state change through twin workflow
- `propagate_load_change` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:481` - Propagate load power change through twin workflow
- `schedule_event` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:1003` - Schedule domain event for future simulation time
- `open_switch` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:1307` - Open switch + propagate topology change
- `close_switch` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:1336` - Close switch + propagate topology change
- `change_load` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:1357` - Change load power + propagate
- `detect_fault` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:1371` - Detect fault + trigger analysis propagation
- `inject_scada_update` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:1393` - Inject SCADA measurements into twin

**Differences:** event_bus.publish is a general publish-subscribe dispatch. progress.emit is a simpler single-sink event transmission. The digital_twin propagate_* and action methods (open_switch, change_load, etc.) are domain-specific wrappers that internally call event_bus.publish. schedule_event defers publication to a future simulation time.

**Recommendation:** KEEP_SEPARATE - event_bus.publish is the canonical dispatch mechanism. The digital_twin propagate_* and action methods are domain-specific facades that compose publish with business logic — they should remain separate as they add domain meaning. progress.emit serves a different transport (stdio/websocket) and should stay independent. Only schedule_event could potentially merge into event_bus.

---

### Subscribe a handler to receive events from an event bus

**Category:** logging-config-event

**Functions:**
- `subscribe` in `ETAP-AI-WORK/digital_twin/event_bus.py:340` - Subscribe handler to specific event type with priority
- `subscribe_all` in `ETAP-AI-WORK/digital_twin/event_bus.py:361` - Subscribe handler to all event types (wildcard)
- `_subscribe_to_events` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:782` - Subscribe digital twin to all input domain events
- `_ensure_subscriptions` in `ETAP-AI-WORK/digital_twin/gis_bridge.py:112` - Ensure GIS bridge is subscribed to digital twin events

**Differences:** event_bus.subscribe and subscribe_all are the core subscription API. _subscribe_to_events and _ensure_subscriptions are module-specific convenience methods that call event_bus.subscribe internally. _subscribe_to_events binds all domain handlers; _ensure_subscriptions is a lazy-init pattern.

**Recommendation:** KEEP_SEPARATE - The event_bus methods are the fundamental subscription mechanism. _subscribe_to_events and _ensure_subscriptions are module-specific initialization convenience methods that delegate to event_bus.subscribe — they add domain-specific binding logic and should stay in their modules.

---

### Configure and initialize application services on startup (lifespan/create/build patterns)

**Category:** logging-config-event

**Functions:**
- `lifespan` in `ETAP-AI-WORK/core/bootstrap.py:351` - Async lifespan manager that initializes services on startup
- `create_app` in `ETAP-AI-WORK/copilot/api/routes.py:322` - Create and configure copilot FastAPI application
- `_build_observability` in `ETAP-AI-WORK/acp_runtime/acp/cli.py:114` - Construct observability components from CLI args
- `_build_runtime` in `ETAP-AI-WORK/acp_runtime/acp/cli.py:144` - Construct AcpRuntime from CLI args
- `_build_router` in `ETAP-AI-WORK/acp_runtime/acp/cli.py:189` - Construct Router from CLI args
- `setup_tracing` in `ETAP-AI-WORK/core/tracing.py:63` - Configure and initialize OpenTelemetry tracing
- `set_runtime` in `ETAP-AI-WORK/acp_runtime/acp/health.py:56` - Attach AcpRuntime for readiness probing
- `setup_structured_logging` in `ETAP-AI-WORK/api/error_debugger.py:1099` - Configure structured JSON logging for the service

**Differences:** bootstrap.lifespan is a FastAPI async context manager. create_app is a FastAPI factory. acp _build_* functions are CLI-driven component constructors. setup_tracing and setup_structured_logging are one-time init calls. All happen at startup but with different frameworks (FastAPI vs CLI), different scopes (full app vs single subsystem), and different patterns (lifespan context manager vs factory function).

**Recommendation:** INVESTIGATE - 8 startup/init functions across different frameworks. Each is framework-specific (FastAPI lifespan vs CLI builder vs manual setup call), so full consolidation isn't feasible. However, the repeated service-init patterns (tracing, logging, metrics) could be extracted into a shared init_services() function called by both lifespan and create_app.

---

### Return a snapshot of all metrics from a registry (counter, histogram, gauge, or full registry)

**Category:** logging-config-event

**Functions:**
- `snapshot` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:110` - Counter label series snapshot
- `snapshot` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:188` - Histogram label series snapshot
- `snapshot` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:276` - Gauge label series snapshot
- `snapshot` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:312` - Abstract: full registry snapshot
- `snapshot` in `ETAP-AI-WORK/acp_runtime/acp/observability/metrics.py:457` - In-memory registry full snapshot implementation
- `metrics` in `ETAP-AI-WORK/acp_runtime/acp/health.py:93` - Metrics snapshot dictionary if registry configured

**Differences:** These are OOP method overrides on different metric types (Counter, Histogram, Gauge, Registry) — same name, different classes. This is intentional polymorphism, not duplication. The health.metrics endpoint wraps the registry snapshot for HTTP consumption.

**Recommendation:** KEEP_SEPARATE - These snapshot methods are polymorphic overrides on different metric types in the observability metrics module — this is intentional OOP design, not semantic duplication. Each class returns its type-specific data. The health.metrics endpoint is a thin HTTP wrapper. No consolidation needed.

---

### Structured/contextual logging with bound context fields

**Category:** logging-config-event

**Functions:**
- `with_context` in `ETAP-AI-WORK/acp_runtime/acp/observability/structured_logger.py:100` - Return new logger with merged context fields
- `bind` in `ETAP-AI-WORK/acp_runtime/acp/observability/structured_logger.py:109` - Add context fields to logger in-place
- `unbind` in `ETAP-AI-WORK/acp_runtime/acp/observability/structured_logger.py:113` - Remove context fields from logger in-place
- `filter` in `ETAP-AI-WORK/core/bootstrap.py:136` - Filter log records by including current trace ID
- `_structlog_processor_wrapper` in `ETAP-AI-WORK/core/bootstrap.py:145` - Inject trace_id from thread-local into structlog event dicts
- `get_logger` in `ETAP-AI-WORK/core/bootstrap.py:438` - Return configured application logger instance
- `install_globally` in `ETAP-AI-WORK/security/log_redaction.py:211` - Install redaction filter globally on all log handlers
- `setup_structured_logging` in `ETAP-AI-WORK/api/error_debugger.py:1099` - Configure structured JSON logging for service
- `_setup_logger` in `ETAP-AI-WORK/security/secrets_manager.py:411` - Set up logger for secrets manager

**Differences:** structured_logger provides a full context-binding API (with_context/bind/unbind). bootstrap provides structlog integration with trace ID injection. log_redaction filters sensitive data. error_debugger configures JSON formatting. secrets_manager._setup_logger is a minimal module-level logger setup. All configure/enrich structured logging but at different layers (context binding, trace injection, redaction, formatting, module setup).

**Recommendation:** INVESTIGATE - Multiple modules independently configure logging enrichment. bootstrap._structlog_processor_wrapper and log_redaction.install_globally both modify log handlers globally. Could investigate merging these into the structured_logger's pipeline so context-binding, trace-injection, and redaction are all configured through one API.

---

### Detect near-singular matrices via SVD-based analysis

**Category:** numerical

**Functions:**
- `condition_number` in `ETAP-AI-WORK/engine/numerical_safety.py:187` - Computes condition number via numpy.linalg.cond; returns inf on failure or empty matrix
- `check_matrix_singularity` in `ETAP-AI-WORK/engine/resilience.py:744` - Computes min/max singular value ratio via SVD and compares against tolerance; returns bool; adds thread-safe metrics
- `condition_number` in `AhmedETAP-Platform/engine/numerical_safety.py:187` - Cross-repo identical copy
- `check_matrix_singularity` in `AhmedETAP-Platform/engine/resilience.py:744` - Cross-repo identical copy

**Differences:** condition_number returns a float (the condition number itself), while check_matrix_singularity returns a boolean verdict. Both use SVD but condition_number uses numpy's cond() wrapper while check_matrix_singularity manually computes the ratio. They serve slightly different use-cases (diagnostic value vs boolean gate).

**Recommendation:** INVESTIGATE - These serve different purposes — one returns diagnostic info, the other returns a boolean gate check. However, they could be unified: condition_number could be used by check_matrix_singularity internally (e.g., condition_number > threshold → singular). Cross-repo copies should still be eliminated.

---

### Construct the Ybus admittance matrix from the power system model topology

**Category:** numerical

**Functions:**
- `build_ybus` in `ETAP-AI-WORK/core_model/system.py:56` - Dense numpy matrix; iterates lines, transformers, generators, loads; handles tap/phase-shift for transformers; includes gen impedance for non-positive-seq or fault analysis
- `build_sparse_ybus` in `ETAP-AI-WORK/engine/data_optimizer.py:46` - Sparse CSR matrix via COO construction; same topology iteration (lines, transformers, gens, loads); same tap/phase-shift handling; same conditional gen/load inclusion logic

**Differences:** Same mathematical logic but different output formats (dense ndarray vs sparse csr_matrix). data_optimizer accumulates COO triplets (rows, cols, data) instead of filling a dense matrix. The tap/phase-shift formulas are identical. Gen/load inclusion conditions are identical but data_optimizer uses truthiness checks (z and z != 0j) vs system.py uses abs(z) > 1e-12.

**Recommendation:** KEEP_SEPARATE - Dense and sparse Ybus construction serve different performance needs. However, the topology iteration logic (which components contribute, tap handling, gen/load inclusion) is duplicated and should be extracted into a shared YbusTopologyIterator that yields (bus_i, bus_j, admittance_value) tuples, then both dense and sparse builders just accumulate those tuples in their preferred format.

---

### Dual-control / dual-confirmation system — require a second person's approval before executing a critical action

**Category:** security

**Functions:**
- `create_approval_request` in `ETAP-AI-WORK/api/dual_control.py:25` - Simple in-memory approval request creation. Sync, returns dict. 5-min auto-reject timeout.
- `request` in `ETAP-AI-WORK/api/cua_confirmation_ws.py:154` - WebSocket-based confirmation request via ConfirmationBroker. Requires 2 distinct humans. Configurable timeout (default 120s). Async event-based.
- `approve_request` in `ETAP-AI-WORK/api/dual_control.py:56` - Simple approval with optional QR secret validation. Returns dict.
- `confirm` in `ETAP-AI-WORK/api/cua_confirmation_ws.py:255` - WebSocket confirmation tracking session_ids. Sets asyncio.Event when enough confirmations received. Async.
- `reject_request` in `ETAP-AI-WORK/api/dual_control.py:84` - Simple rejection with reason. Returns dict.
- `reject` in `ETAP-AI-WORK/api/cua_confirmation_ws.py:290` - WebSocket rejection, broadcasts to clients, sets asyncio.Event. Async.
- `get_pending_approvals` in `ETAP-AI-WORK/api/dual_control.py:103` - Return all non-expired pending requests. Sync.

**Differences:** dual_control.py is a simple sync in-memory store with basic approve/reject/get_pending. cua_confirmation_ws.py is a full async WebSocket-based broker requiring 2 distinct humans, with real-time broadcast, asyncio.Event for blocking the caller, and session_id tracking. Different timeouts (5 min vs 120s), different concurrency models (sync vs async).

**Recommendation:** INVESTIGATE - These are semantically similar (both implement dual-confirmation) but architecturally different. dual_control.py appears to be a simpler, earlier implementation. cua_confirmation_ws.py is the evolved, production version. Need to verify whether dual_control.py is still actively used by any callers — if not, it should be removed. If both are needed (different use cases), they should share a common ApprovalRequest data model.

---

### Authorization check — verify that the current user has required role/permission to access an endpoint

**Category:** security

**Functions:**
- `require_role` in `ETAP-AI-WORK/api/dependencies.py:220` - FastAPI dependency factory. Checks user.role against a set of allowed roles. Simple RBAC: if user.role not in roles → 403.
- `_check_role` in `ETAP-AI-WORK/api/dependencies.py:235` - Inner function of require_role. Checks CurrentUser.role membership against allowed roles.
- `require_permission` in `ETAP-AI-WORK/api/rbac.py:249` - FastAPI dependency factory. Checks user's permission (resource:action) via database role→permission lookup. Admin bypass.
- `_check_permission` in `ETAP-AI-WORK/api/rbac.py:261` - Inner function of require_permission. Queries user's roles→permissions from DB. Admin bypass.
- `_require_admin` in `ETAP-AI-WORK/api/email_dashboard.py:51` - Ad-hoc admin check accepting X-API-Key or JWT Bearer token. Returns user dict or raises 403. Doesn't use require_role or require_permission.

**Differences:** require_role checks a single role string on CurrentUser (no DB query). require_permission does a DB query through role-permission association tables. _require_admin is an ad-hoc implementation that accepts multiple auth methods (API key, JWT, dev mode) and hardcodes admin check. ABAC (security/abac.py) adds attribute-based evaluation that includes role rules, overlapping with require_role.

**Recommendation:** CONSOLIDATE - require_role is a simple role-check shortcut; require_permission is the proper DB-backed permission check. _require_admin is an ad-hoc reimplemention that should use require_role('admin') or require_permission('dashboard', 'admin'). The RBAC and ABAC systems should be integrated: ABAC should delegate role-only checks to RBAC rather than reimplementing role evaluation in make_role_policy. All three authorization patterns should funnel through a single authorization pipeline.

---

### Rate limit check — determine if a client IP/request is allowed under sliding-window rate limits

**Category:** security

**Functions:**
- `_rate_limit_check` in `ETAP-AI-WORK/api/akamai_protection.py:308` - Delegates to shared RateLimiter from api._rate_limit. Wrapper for backward compat.
- `_rate_limit_check` in `ETAP-AI-WORK/api/cloudflare_protection.py:273` - Delegates to shared RateLimiter from api._rate_limit. Wrapper for backward compat.
- `is_allowed` in `ETAP-AI-WORK/api/shared_handlers.py:418` - InMemoryRateLimiter.is_allowed method — thread-safe sliding-window implementation. Separate from CDN rate limiting.

**Differences:** Akamai and Cloudflare _rate_limit_check already share RateLimiter from api._rate_limit (partially consolidated). shared_handlers.InMemoryRateLimiter.is_allowed is a different rate limiter instance used for general API rate limiting (not CDN-specific). Different configs (CDN: 300/min, general: 120/min).

**Recommendation:** INVESTIGATE - Akamai and Cloudflare already consolidated their rate limiter to api._rate_limit.RateLimiter. The remaining question: should shared_handlers.InMemoryRateLimiter also use the same RateLimiter class? They have different configurations but could share the same implementation class. The _rate_limit_check wrapper functions in both CDN modules are pure backward-compat aliases and could be removed.

---

### Admin role authorization check — verify user has admin role before allowing access to a resource

**Category:** security

**Functions:**
- `_require_admin` in `ETAP-AI-WORK/api/email_dashboard.py:51` - Accepts X-API-Key, JWT Bearer, or dev-mode bypass. Returns user dict. Hardcodes admin role check. Does NOT use require_role or require_permission.
- `require_role` in `ETAP-AI-WORK/api/dependencies.py:220` - FastAPI dependency factory for role-based access. Could be called with require_role('admin').

**Differences:** _require_admin has its own auth extraction logic (API key, JWT, dev mode) that duplicates logic from verify_api_key, get_api_key_auth, and get_current_user_from_header. require_role is a clean dependency that only checks the role after auth is already resolved.

**Recommendation:** CONSOLIDATE - _require_admin reimplements auth extraction that already exists in dependencies.py and shared_handlers.py. It should be replaced by combining existing auth dependencies: get_current_user_from_header + require_role('admin'). This eliminates 30+ lines of duplicated auth extraction.

---

### Read content from stdin for sandboxed execution environments

**Category:** string-error-crypto

**Functions:**
- `_read_code_from_stdin` in `ETAP-AI-WORK/security/secure_executor.py:43` - Reads Python code content from stdin for sandboxed execution
- `_read_command_from_stdin` in `ETAP-AI-WORK/security/secure_powershell_executor.py:185` - Reads a PowerShell command from stdin for sandboxed execution

**Differences:** Both read from stdin for sandboxed execution. The only difference is the language context (Python code vs. PowerShell command). The core stdin-reading logic is identical: sys.stdin.read().

**Recommendation:** CONSOLIDATE - Both functions perform the same stdin.read() operation. A shared read_from_stdin() utility eliminates the duplication. The semantic difference (code vs. command) is caller-context, not implementation.

---

### SHA-256 hashing for various purposes (checksum, cache key, integrity verification, pseudo-embedding)

**Category:** string-error-crypto

**Functions:**
- `_hash_code` in `ETAP-AI-WORK/services/otp_store.py:131` - Hashes an OTP code using SHA-256 for secure storage
- `hash_code` in `ETAP-AI-WORK/ai_context_engine/indexer.py:163` - Computes SHA-256 hash of source code string
- `hash_params` in `ETAP-AI-WORK/engine/cache_manager.py:293` - Hashes function arguments using SHA-256 for cache key generation
- `hash_system_state` in `ETAP-AI-WORK/engine/cache_manager.py:303` - Hashes a system object state using SHA-256 for cache invalidation tracking
- `_compute_ybus_checksum` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:206` - Computes a checksum of the Ybus matrix for topology change detection
- `_embed` in `ETAP-AI-WORK/services/memory_service.py:88` - Generates a deterministic pseudo-embedding vector using SHA-256 hashing

**Differences:** All use SHA-256 (hashlib.sha256) but with different input preparation and output formats. _hash_code hashes a simple string. hash_code hashes source code. hash_params serializes arguments before hashing. hash_system_state serializes a system state dict. _compute_ybus_checksum serializes a matrix. _embed uses SHA-256 to produce a pseudo-embedding vector (numeric array output). The core hashlib.sha256(data).hexdigest() pattern is identical; the differences are in input serialization and output formatting.

**Recommendation:** INVESTIGATE - While the core SHA-256 call is identical, the input serialization varies significantly per domain. A thin sha256_hash(data: bytes) -> str utility could replace the repeated hashlib boilerplate, but each consumer would still need its own serialization logic. The _embed function is a special case (produces a vector, not a hex digest) and may not fit the shared utility. Worth consolidating the simple hex-digest cases.

---

### Extract base MVA value from power system file formats

**Category:** string-error-crypto

**Functions:**
- `_parse_psse_header` in `ETAP-AI-WORK/api/data_import.py:355` - Extracts the base MVA value from the PSS/E file header line
- `_parse_matpower_base_mva` in `ETAP-AI-WORK/api/data_import.py:402` - Extracts the base MVA value from a MATPOWER case file

**Differences:** Both extract the same value (base MVA) from different file formats (PSS/E vs MATPOWER). The parsing logic differs because the file formats are different, but the intent and output type are the same.

**Recommendation:** KEEP_SEPARATE - While both extract base MVA, they parse fundamentally different file formats with different syntax. Consolidation would require format-specific branching that reduces readability. These are better kept as separate format-specific parsers, possibly unified under a common extract_base_mva(content, format) dispatcher.

---

### Generate text reports of analysis results

**Category:** string-error-crypto

**Functions:**
- `generate_report` in `ETAP-AI-WORK/fault_analysis/harmonic_analysis.py:560` - Generates a text report of harmonic analysis results
- `generate_report` in `ETAP-AI-WORK/load_flow/optimal_power_flow.py:487` - Generates a text report of optimal power flow results

**Differences:** Both generate text reports from analysis results, but the data structures and report content are domain-specific (harmonic analysis vs. optimal power flow). They share the same function name and the same structural pattern (iterate results, format sections, return string).

**Recommendation:** KEEP_SEPARATE - The reports contain fundamentally different domain content. A shared report template/framework could extract common formatting patterns (headers, sections, tables), but the actual report generation logic is domain-specific. Consider a shared ReportFormatter base class for structural consistency.

---

### Cross-category: Sensitive data in error contexts — error formatting may leak secrets that should be masked

**Category:** string-error-crypto

**Functions:**
- `build` in `ETAP-AI-WORK/api/error_debugger.py:535` - [error-handling] Builds full error context dictionary — may include sensitive data in stack traces
- `_extract_stack_trace` in `ETAP-AI-WORK/api/error_debugger.py:643` - [error-handling] Extracts Python stack trace as string — may contain variable values with secrets
- `_mask_key` in `ETAP-AI-WORK/services/api_key_store.py:101` - [string-utils] Masks key string for safe display — should be applied in error contexts
- `sanitize_result` in `ETAP-AI-WORK/api/shared_handlers.py:570` - [string-utils] Sanitizes result output to remove sensitive data — should be applied to error responses

**Differences:** The error-handling functions build and extract_stack_trace create rich error context but may not consistently apply sanitization. The string-utils functions _mask_key and sanitize_result provide sanitization but are not integrated into the error-building pipeline. This is a cross-cutting concern where error context generation and sensitive data sanitization should be integrated.

**Recommendation:** INVESTIGATE - Error context builders should integrate sanitization to prevent leaking sensitive data in error responses. The build() and _extract_stack_trace() functions should apply _mask_key and sanitize_result logic before returning error context. This is a cross-cutting concern that requires investigation of whether error responses currently leak secrets in stack traces, variable values, or error messages.

---

### Token validation/verification across authentication systems

**Category:** string-error-crypto

**Functions:**
- `validate` in `ETAP-AI-WORK/acp_runtime/acp/security/auth.py:135` - Validates a JWT token string and returns a CallerIdentity (ACP protocol)
- `validate_token` in `ETAP-AI-WORK/security/security_framework.py:327` - Validates an authentication token (general application)

**Differences:** Both validate JWT tokens. The ACP validate() returns a CallerIdentity with scope information. The security_framework validate_token() may use a different verification key or claim structure. The core JWT decode/verify pattern is the same.

**Recommendation:** INVESTIGATE - If both systems use the same JWT signing key and similar claim structures, they should be consolidated. If they use different keys (ACP vs. application tokens), they may need to remain separate. Investigate whether the ACP auth module can delegate to the security_framework for token validation.

---

### HMAC-SHA256 signing and verification for webhook payloads

**Category:** string-error-crypto

**Functions:**
- `_verify_resend_signature` in `ETAP-AI-WORK/api/email_webhooks.py:112` - Verifies the HMAC-SHA256 signature of an inbound Resend webhook payload
- `_sign_payload` in `ETAP-AI-WORK/api/email_webhooks.py:292` - Signs an outbound webhook payload with HMAC-SHA256 using a shared secret

**Differences:** One verifies, one signs — they are complementary operations using the same HMAC-SHA256 algorithm. Both use the same shared secret pattern. They are currently in the same module which is appropriate.

**Recommendation:** KEEP_SEPARATE - Sign and verify are complementary operations (not duplicates). They are correctly co-located in the same module. However, if other modules need HMAC-SHA256 signing/verification, a shared utility should be extracted.

---

### Redis-backed sliding-window rate limiting with in-memory fallback for API endpoints

**Category:** validation

**Functions:**
- `_check_rate_limit` in `ETAP-AI-WORK/api/auth.py:504` - Per-username rate limit. Uses Redis INCR+EXPIRE when available, falls back to in-memory OrderedDict. Raises HTTPException(429) on limit exceeded. Replica-aware in-memory limits.
- `_check_rate_limit` in `ETAP-AI-WORK/api/routes.py:199` - Per-client_id rate limit. Uses Redis INCR+EXPIRE when available, falls back to in-memory dict store. Returns bool (True=allowed). Falls back to True on Redis error.

**Differences:** Both use the same Redis sliding-window pattern (INCR+EXPIRE) with in-memory fallback. Key differences: (1) auth version raises HTTPException on limit, routes returns bool; (2) auth uses username keys, routes uses client_id keys; (3) auth has replica-aware fallback limits, routes does not; (4) auth uses OrderedDict with eviction, routes uses plain dict with stale cleanup.

**Recommendation:** INVESTIGATE - Core pattern is identical (Redis INCR+EXPIRE + in-memory fallback) but the two functions differ in error-handling strategy (raise vs return), key naming, replica awareness, and store management. Could potentially be unified into a single Redis-backed rate limiter class in _rate_limit.py that supports both behaviors via configuration, but requires careful migration of callers.

---

### Check whether a numeric value or result lies within specified bounds/range

**Category:** validation

**Functions:**
- `is_within_bounds` in `ETAP-AI-WORK/engine/numerical_safety.py:162` - NumericalGuard method. Checks if all elements of value (float or ndarray) lie within [min_val, max_val]. Returns bool. Pure bounds check, no NaN/Inf handling.
- `validate_numerical_result` in `ETAP-AI-WORK/engine/resilience.py:881` - ResilienceGuard static method. Checks if result (float) is within expected_range AND is finite (not NaN/Inf). Returns bool. Combines bounds check with NaN/Inf check.

**Differences:** is_within_bounds is a pure bounds check on arrays/scalars. validate_numerical_result adds NaN/Inf detection and only works on scalars. Same core purpose (is value in range?) but validate_numerical_result is more comprehensive for scalar results.

**Recommendation:** INVESTIGATE - Overlapping purpose but different scope. validate_numerical_result is a richer check that could be expressed as is_within_bounds + isfinite check. If numerical_safety.py adds a finite-check component, validate_numerical_result could delegate to it. However, the different interfaces (array vs scalar) and additional checks make full consolidation non-trivial.

---

### Detect whether iterative solver values are diverging (exceeding threshold or growing anomalously)

**Category:** validation

**Functions:**
- `check_divergence` in `ETAP-AI-WORK/engine/numerical_safety.py:96` - NumericalGuard method. Takes a history sequence externally. Checks if abs diffs > threshold or recent values exceed threshold. Returns bool.
- `is_diverging` in `ETAP-AI-WORK/engine/numerical_safety.py:233` - ConvergenceMonitor method. Uses internally stored _history + current value. Checks absolute magnitude exceeds divergence_threshold AND anomalous step growth (>10x mean diffs). More sophisticated detection.

**Differences:** check_divergence accepts external history, is_diverging uses stored internal history. is_diverging has more sophisticated detection (anomalous growth factor). Both are in the same file but different classes. Same fundamental purpose: detect divergence in iteration sequences.

**Recommendation:** INVESTIGATE - Same file, different classes. The ConvergenceMonitor.is_diverging is more sophisticated and stateful. NumericalGuard.check_divergence is simpler and stateless. They serve different use cases (one-shot check vs ongoing monitoring). Could potentially share the divergence detection logic via a helper, but the stateful vs stateless distinction makes full consolidation difficult.

---

### Check whether an iterative solver has converged (mismatch within tolerance)

**Category:** validation

**Functions:**
- `is_converged` in `ETAP-AI-WORK/engine/numerical_safety.py:229` - ConvergenceMonitor method. Simple: abs(current_value) <= tolerance. Returns bool.
- `check_convergence` in `ETAP-AI-WORK/engine/resilience.py:815` - ResilienceGuard method. Takes a history sequence + window + tolerance. Checks final mismatch over last window steps. Also tracks statistics (checks_performed, violations_detected). Returns bool.

**Differences:** is_converged is a simple single-value tolerance check. check_convergence uses a sliding window of history and tracks stats. Different interfaces and different complexity levels. check_convergence also increments internal counters.

**Recommendation:** KEEP_SEPARATE - While both check convergence, they serve fundamentally different needs: is_converged is a lightweight stateless check for monitoring; check_convergence is a comprehensive statistical check with audit tracking. Consolidation would either lose the simplicity of is_converged or the richness of check_convergence.

---

### Validate voltage magnitude values are within acceptable per-unit range

**Category:** validation

**Functions:**
- `validate_voltage_magnitude` in `ETAP-AI-WORK/core_model/specs.py:87` - Pydantic field_validator on BusSpec. Validates single voltage_magnitude field is in [0.5, 2.0] pu. Raises ValueError on violation.
- `check_voltage_profile` in `ETAP-AI-WORK/engine/numerical_safety.py:325` - ConsistencyChecker method. Validates array of bus voltages against configurable [vmin, vmax] (defaults 0.95-1.05). Returns dict with violation statistics.

**Differences:** validate_voltage_magnitude validates a single value at model construction time with a wider range (0.5-2.0). check_voltage_profile validates runtime arrays with a tighter operational range (0.95-1.05 default). Different return types (exception vs result dict), different scope (input validation vs runtime check).

**Recommendation:** KEEP_SEPARATE - Same domain (voltage bounds) but fundamentally different roles: one is input validation at model construction with permissive bounds; the other is runtime consistency checking with operational bounds and statistical reporting. Keeping them separate is appropriate — they guard different stages of the pipeline.

---

### Validate that required environment configuration/secrets are present at startup

**Category:** validation

**Functions:**
- `_validate_environment` in `ETAP-AI-WORK/core/bootstrap.py:327` - Checks for JWT_SECRET_KEY and ENGINEERING_SERVICE_API_KEY in production env. Only warns (no hard failure).
- `check_missing_secrets` in `ETAP-AI-WORK/security/secrets_manager.py:518` - Checks all REQUIRED_SECRETS. Also detects placeholder values (starts with 'generate-' or contains 'your-'). Returns list of missing secret names.

**Differences:** _validate_environment only checks 2 specific vars in production and only warns. check_missing_secrets checks a full required_secrets list, detects placeholder/template values, and returns the list of missing ones. check_missing_secrets is more comprehensive.

**Recommendation:** INVESTIGATE - Overlapping purpose (ensure required config is present) but different scope and rigor. _validate_environment could delegate to SecretsManager.check_missing_secrets for a more thorough startup check, or the two could be merged so bootstrap calls secrets_manager. However, _validate_environment's production-only conditional logic would need to be preserved.

---

### Validate PowerShell commands for safety via whitelist checking

**Category:** validation

**Functions:**
- `_validate_cmdlet_whitelist` in `ETAP-AI-WORK/security/secure_powershell_executor.py:87` - Regex-based: finds all Verb-Noun cmdlet patterns in command, checks each against ALLOWED_CMDLETS set. Returns bool.
- `validate_powershell_command` in `ETAP-AI-WORK/security/security_framework.py:525` - Multi-layer validation: checks dangerous patterns (Invoke-Expression, IEX, etc.), .NET type access, backtick escaping, then whitelist of first command word. More comprehensive.

**Differences:** _validate_cmdlet_whitelist only checks cmdlet whitelist via regex matching. validate_powershell_command does broader checks (dangerous patterns, .NET access, backtick escaping) AND whitelist but only checks the first word of the command. They overlap on whitelist checking but have different scope and methodology.

**Recommendation:** INVESTIGATE - Overlapping whitelist functionality but validate_powershell_command is broader and uses a different whitelist approach (first-word vs regex-all-cmdlets). Could be consolidated by having validate_powershell_command call _validate_cmdlet_whitelist as one of its checks, but this requires aligning the whitelist sets and approach. Needs domain expert input on which whitelist strategy is correct.

---

### Retry with exponential backoff on transient failures — three separate implementations

**Category:** vision-email

**Functions:**
- `retry_with_backoff` in `ETAP-AI-WORK/integrations/_vision_base.py:97` - Function-based: takes make_request + parse_response callables. Used by Anthropic and OpenAI vision clients.
- `retry_with_backoff` in `ETAP-AI-WORK/integrations/resilience.py:58` - Decorator-based: wraps a function with retry logic. Used by HybridVisionRouter._call_backend and as a general utility.
- `analyze_screenshot (inline retry loop)` in `ETAP-AI-WORK/integrations/gemini_vision.py:206` - Inline retry loop inside analyze_screenshot that duplicates the exponential backoff pattern: attempt loop, exception catch, sleep(backoff * 2^(attempt-1)).
- `_send_with_retries` in `ETAP-AI-WORK/integrations/resend_email.py:422` - Inline retry loop for email HTTP calls. Same pattern: attempt loop, exception catch, exponential sleep.

**Differences:** Four implementations of the same retry-with-exponential-backoff pattern: (1) _vision_base.retry_with_backoff is a function taking callables (make_request, parse_response) — specific to vision API calls; (2) resilience.retry_with_backoff is a general-purpose decorator; (3) Gemini's inline loop in analyze_screenshot duplicates the pattern from _vision_base but doesn't use it; (4) resend_email._send_with_retries has its own inline retry loop for HTTP calls. All share the same core algorithm (attempt loop, catch exceptions, sleep with exponential delay) but differ in: input form (callables vs decorator vs inline), retry semantics (some re-raise, some return error dicts), and domain context (vision API vs email API vs general).

**Recommendation:** CONSOLIDATE - The resilience.retry_with_backoff decorator is the most general and reusable implementation. Gemini's analyze_screenshot should delegate to _vision_base.retry_with_backoff (like Anthropic/OpenAI already do) instead of having an inline retry loop. The resend_email._send_with_retries could also be refactored to use resilience.retry_with_backoff, though its async nature and domain-specific error handling (4xx vs 5xx classification) make this less straightforward. Priority: migrate Gemini's inline retry first.

---

### Return a health status dict for /health endpoints — same pattern across all vision backends

**Category:** vision-email

**Functions:**
- `health_check` in `ETAP-AI-WORK/integrations/anthropic_vision.py:253` - Returns {enabled, model, base_url, api_key_set, pil_available, httpx_available, timeout_seconds, max_retries}
- `health_check` in `ETAP-AI-WORK/integrations/gemini_vision.py:229` - Returns {enabled, model, api_key_set, sdk_available, pil_available, timeout_seconds, max_retries} — no base_url, no httpx_available
- `health_check` in `ETAP-AI-WORK/integrations/openai_vision.py:256` - Returns {enabled, model, base_url, api_key_set, pil_available, httpx_available, timeout_seconds, max_retries} — identical shape to Anthropic
- `health_check` in `ETAP-AI-WORK/integrations/opencv_vision.py:309` - Returns {enabled, cv2_available, pil_available, ocr_enabled, tesseract_status} — different keys, no model/timeout
- `health_check` in `ETAP-AI-WORK/integrations/resilience.py:332` - Aggregates all 4 backend health_checks plus chain/primary/fallback_count. Facade pattern.

**Differences:** Anthropic and OpenAI return identical dict shapes (7 keys each, same names). Gemini differs slightly: 'sdk_available' instead of 'httpx_available', no 'base_url'. OpenCV differs significantly: entirely different keys (cv2_available, ocr_enabled, tesseract_status) reflecting its offline nature. All follow the same pattern of reporting enabled status + provider-specific capability flags, but the specific fields vary per provider. The resilience version aggregates all of them.

**Recommendation:** INVESTIGATE - Anthropic and OpenAI have identical dict shapes and could share a base helper from _vision_base for the common fields (enabled, model, base_url, api_key_set, pil_available, timeout_seconds, max_retries), with each provider adding its own specific fields. Gemini and OpenCV have sufficiently different fields that forcing a single template would be awkward. The resilience facade is correctly separate. Low-risk refactor: extract common dict construction, keep provider-specific additions.

---

### HTTP request via httpx with urllib fallback — same dual-client pattern across vision and email modules

**Category:** vision-email

**Functions:**
- `_make_request_httpx` in `ETAP-AI-WORK/integrations/anthropic_vision.py:294` - httpx.Client POST with timeout, raise_for_status, .json(). Used if HTTPX_AVAILABLE=True.
- `_make_request_urllib` in `ETAP-AI-WORK/integrations/anthropic_vision.py:305` - urllib.request.Request POST fallback. json.dumps payload, urlopen with timeout.
- `_make_request_httpx` in `ETAP-AI-WORK/integrations/openai_vision.py:342` - Identical pattern to Anthropic's: httpx.Client POST, raise_for_status, .json().
- `_make_request_urllib` in `ETAP-AI-WORK/integrations/openai_vision.py:355` - Identical pattern to Anthropic's urllib fallback.
- `_http_post_json` in `ETAP-AI-WORK/integrations/resend_email.py:133` - Async version: httpx.AsyncClient POST or asyncio.to_thread(urllib). Same dual-client pattern but async.

**Differences:** Anthropic and OpenAI vision modules have identical _make_request_httpx and _make_request_urllib methods — same httpx.Client pattern, same urllib fallback pattern, same JSON encoding. These are exact copies. Resend's _http_post_json follows the same dual-client philosophy (httpx → urllib) but is async (AsyncClient + asyncio.to_thread), handles HTTPError separately, and is a standalone function rather than methods. The vision modules' methods are instance methods that access self.timeout.

**Recommendation:** CONSOLIDATE - Anthropic and OpenAI vision have identical _make_request_httpx and _make_request_urllib methods. These should be extracted to _vision_base.py as a shared _http_post_sync() function (httpx-first, urllib-fallback). Each vision client would call this shared function instead of having its own copy. Resend's async _http_post_json is fundamentally different (async) and should remain separate. This eliminates 4 duplicated methods (2 per client).

---


## LOW Confidence (Possibly Related)

These functions might be related. Review if time permits.

### Store and retrieve OTP verification records in an in-memory cache

**Category:** caching

**Functions:**
- `set` in `ETAP-AI-WORK/services/otp_store.py:84`
- `get` in `ETAP-AI-WORK/services/otp_store.py:87`
- `update` in `ETAP-AI-WORK/services/otp_store.py:96`
- `delete` in `ETAP-AI-WORK/services/otp_store.py:99`

**Notes:** OTP store uses the same in-memory dict pattern as the other caches but has domain-specific semantics: update() modifies verification state (attempts, verified flag), which is not a generic cache operation. The OTP lifecycle (create → verify → expire/delete) is fundamentally different from general caching (populate → retrieve → evict).

---

### Parse Gemini vision API response into standard format dict

**Category:** data-transform

**Functions:**
- `_parse_response` in `ETAP-AI-WORK/integrations/gemini_vision.py:278`
- `_parse_response` in `AhmedETAP-Platform/integrations/gemini_vision.py:278`

**Notes:** Gemini _parse_response is fundamentally different from Anthropic/OpenAI versions: it operates on Google SDK objects (not raw dicts), uses attribute access (not dict.get()), tries multiple extraction strategies (response.text vs candidates path), and does NOT strip markdown fences or add a source tag. Same ultimate intent (API response → standard dict) but implementation is too different to share code directly with Anthropic/OpenAI.

---

### Serialize dataclass/model instances to dictionaries for JSON output

**Category:** data-transform

**Functions:**
- `to_dict` in `ETAP-AI-WORK/core/models.py:168`
- `to_dict` in `ETAP-AI-WORK/core_model/motor_model.py:301`
- `to_dict` in `ETAP-AI-WORK/core_model/zip_load.py:168`
- `to_dict` in `ETAP-AI-WORK/api/coverage_report.py:75`
- `to_dict` in `ETAP-AI-WORK/api/cua_confirmation_ws.py:81`

**Notes:** Each to_dict serializes a DIFFERENT dataclass with different fields, so they are not true duplicates. They share a common pattern but operate on unrelated data. Some use asdict() directly (FunctionInfo), others manually construct dicts (UniversalElement, CoverageReport). The manual constructions handle special cases like enum→value, datetime→isoformat, nested object→recursive to_dict.

---

### get_statistics summary reporting — repeated across three DT modules

**Category:** electrical-eng-digital-twin

**Functions:**
- `get_statistics` in `ETAP-AI-WORK/digital_twin/state_store.py:417`
- `get_statistics` in `ETAP-AI-WORK/digital_twin/validation_gateway.py:624`
- `get_statistics` in `ETAP-AI-WORK/etap_integration/sync_engine.py:586`

**Notes:** All three return dict summaries but about entirely different domains (state versioning vs validation health vs ETAP sync). No shared fields or computation. The method name pattern is coincidental — each module independently needs a statistics accessor. Not a true semantic duplicate.

---

### Ybus/Zbus matrix computation — fault.py vs iec60909_engine.py vs consolidated_solver vs system.py

**Category:** electrical-eng-digital-twin

**Functions:**
- `_invert_ybus` in `ETAP-AI-WORK/fault_analysis/fault.py:61`
- `_zbus_element` in `ETAP-AI-WORK/fault_analysis/fault.py:54`
- `_compute_zbus` in `ETAP-AI-WORK/fault_analysis/iec60909_engine.py:120`
- `build_sequence_networks` in `ETAP-AI-WORK/core_model/system.py:164`
- `_ensure_ybus_current` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:1165`
- `_rebuild_base_engine` in `ETAP-AI-WORK/digital_twin/digital_twin_core.py:1171`

**Notes:** Multiple Ybus/Zbus computation paths exist: fault.py uses pseudo-inverse for Zbus; iec60909_engine.py has its own _compute_zbus; system.py builds Ybus via build_sequence_networks; DT core rebuilds Ybus on topology changes. These are genuinely different algorithms for different standards (ANSI vs IEC 60909) and different contexts (steady-state vs fault vs DT propagation). However, the Ybus construction from system components is conceptually identical across system.py and DT's _ensure_ybus_current.

---

### Return cached Ybus matrix for a sequence, building if not cached

**Category:** numerical

**Functions:**
- `get_ybus` in `ETAP-AI-WORK/core_model/system.py:150`
- `get_ybus` in `ETAP-AI-WORK/engine/data_optimizer.py:284`

**Notes:** Same caching pattern but one delegates to dense build, other to sparse build. Return types differ (ndarray vs csr_matrix).

---

### MFA TOTP setup and verification — generate TOTP secret, produce QR code, verify TOTP code

**Category:** security

**Functions:**
- `setup_totp` in `ETAP-AI-WORK/api/mfa.py:15`
- `enable_totp` in `ETAP-AI-WORK/security/mfa.py:320`
- `verify_totp` in `ETAP-AI-WORK/api/mfa.py:55`
- `verify_code` in `ETAP-AI-WORK/security/mfa.py:236`
- `generate_qr_code` in `ETAP-AI-WORK/security/mfa.py:204`

**Notes:** These are layered, not duplicated. api/mfa.py is the HTTP endpoint layer (request parsing, JSON responses, error handling). security/mfa.py is the core TOTP logic (secret generation, code verification, QR code creation). api/mfa.py explicitly imports and delegates to security/mfa.TOTPProvider.

---

### Extract code chunks from source files using different parsing strategies

**Category:** string-error-crypto

**Functions:**
- `extract_with_ast` in `ETAP-AI-WORK/ai_context_engine/indexer.py:44`
- `extract_with_tree_sitter` in `ETAP-AI-WORK/ai_context_engine/indexer.py:74`

**Notes:** Different parsing backends (AST vs Tree-sitter) for the same purpose. AST is Python-only; Tree-sitter supports multiple languages. They are intentionally alternative implementations with a dispatcher (extract() at line 114).

---

### Validate AgentResult objects from agent tasks

**Category:** validation

**Functions:**
- `validate_result` in `ETAP-AI-WORK/agents/coordination_agent.py:530`
- `validate_result` in `ETAP-AI-WORK/agents/digital_twin_agent.py:419`

**Notes:** Same method name and same AgentResult parameter type, but entirely different domain-specific validation logic. One validates relay coordination data; the other validates digital twin metrics. No shared validation steps.

---

### Test LLM API key validity by making a real HTTP request to the provider

**Category:** validation

**Functions:**
- `_test_openai_key` in `ETAP-AI-WORK/api/settings.py:299`
- `_test_gemini_key` in `ETAP-AI-WORK/api/settings.py:327`
- `_test_anthropic_key` in `ETAP-AI-WORK/api/settings.py:352`

**Notes:** Same structural pattern (httpx request, status check, success/failure dict) but fundamentally different per provider: different endpoints, different auth methods (Bearer vs query param vs header), different HTTP methods (GET vs POST), different response parsing. Anthropic even sends a payload body.

---

### Check if library/dependency is available for import at runtime

**Category:** validation

**Functions:**
- `_check_opencv_available` in `ETAP-AI-WORK/integrations/opencv_vision.py:66`
- `_check_pil_available` in `ETAP-AI-WORK/integrations/opencv_vision.py:91`
- `_check_tesseract_available` in `ETAP-AI-WORK/integrations/opencv_vision.py:77`

**Notes:** Same try/import pattern but different libraries. _check_tesseract_available is more thorough (also checks binary availability) and returns a tuple with reason instead of bool. Same file — these are intentionally separate per-library checks.

---

