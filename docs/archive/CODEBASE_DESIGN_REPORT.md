# Codebase Design Analysis Report

## Analysis Date
2026-07-22

## Methodology
Using the [codebase-design skill](.agents/skills/codebase-design/SKILL.md) vocabulary: **Module**, **Interface**, **Depth**, **Seam**, **Adapter**, **Leverage**, **Locality**.

---

## Key Findings

### 1. 🟡 `PowerSystemEngine` — God Object (engine/engine.py)

**Issue:** The `PowerSystemEngine` class handles load flow, fault analysis, arc flash, protection coordination, AND visualization. It accepts 4 optional dependencies via constructor injection (good seam discipline), but then exposes all of them as public attributes and routes everything through a single `run_study(**kwargs)` method.

**Assessment:** **Shallow** — the `run_study(**kwargs)` interface is nearly as complex as the combined implementation. The `**kwargs` dict pushes type checking to runtime.

**Recommendation:** Extract `run_study` dispatch into a registry pattern or separate runner modules.

**Status: ✅ Implemented (2026-08-07)** — `run_study` is now a thin, registry-backed JSON adapter at the external seam (HTTP API, MCP, AI agents, CLI, automation). The if/elif + `kwargs.get(...)` chain was replaced with a lookup against the module-private `_STUDY_REGISTRY` in `engine/engine.py`, which maps each `study_type` one-to-one to its typed method (`run_load_flow`, `run_fault_analysis`, `run_arc_flash`, `run_protection_coordination`) via `(required_kwargs, method_name)` specs. Validation is centralized in the module-private `_validate_study_kwargs` helper, reproducing every exception message byte-for-byte. The public signature `run_study(self, study_type: str, **kwargs: Any) -> dict[str, Any]` is unchanged; the registry is internal and not exported from `engine/__init__.py`. Behavioral equivalence is proven by `tests/test_run_study_behavioral_equivalence.py` (golden baseline + exception equivalence) and `tests/test_run_study_registry.py` (registry structure + validation semantics) — 29 tests, all passing with zero warnings/skips/errors.

### 2. 🟡 `etap_integration/__init__.py` — Massive Re-export Surface

**Issue:** 141 lines of boilerplate `__getattr__` lazy-loading 20+ names. Each group repeats the same pattern: check global, import, return. The interface is large (20+ symbols) and the implementation is thin (just delegation to submodules).

**Assessment:** **Shallow** — the interface is nearly as complex as the implementation.

**Recommendation:** Replace with explicit imports using standard `from X import Y` at the top level, keeping only the lazy-loading for the Windows-only `pywin32` dependency.

### 3. 🟡 `engine/__init__.py` — 100+ Re-exports

**Issue:** Re-exports 100+ symbols from 10 submodules. Zero implementation.

**Assessment:** **Shallow** — pure aggregation with no behavior.

**Recommendation:** This is standard Python package practice, but consider trimming to only what's needed by external callers.

### 4. 🔴 `etap_integration/etap_provider.py` — Repeated `USE_ETAP` Check

**Issue:** Every provider constructor (`LocalEtapProvider`, `RemoteEtapProvider`, `MockEtapProvider`, `NullEtapProvider`) repeats the same `os.getenv("USE_ETAP", "false").lower() == "true"` check. This is **D-R-Y violation**.

**Assessment:** **Shallow** — the check should live in one place. Four repetitions = four places to update if the env var name changes.

**Recommendation:** Extract to a shared method in `IEtapProvider` or a standalone helper.

### 5. ✅ Strong Patterns Found

| Module | Assessment | Why |
|--------|-----------|-----|
| `engine/interfaces.py` | **Deep** | 5 focused protocols, each with small surface area and clear responsibility |
| `engine/cache_manager.py` | **Deep** | `CalculationCache` has a small public API (get/set/invalidate/clear/stats) hiding 600 lines of eviction logic, tag indexing, and dual-storage management |
| `engine/error_handler.py` | **Deep** | `ErrorHandler` has a clean interface (handle_error, get_error_history, acknowledge, resolve, statistics) hiding alert dispatch, audit logging, and history management |
| `load_flow/load_flow.py` | **Deep** | `LoadFlowSolver` exposes just `solve()`, hiding Jacobian construction, Q-limit switching, oscillation detection, and Levenberg-Marquardt regularization |
| `engine/engine.py` | **Good** | Constructor injection of protocols enables testability (good seam discipline) |

---

## Previously Fixed Findings

| # | Finding | Recommendation | Status | Date |
|---|---------|----------------|--------|------|
| 1 | `PowerSystemEngine` — God Object (`run_study` dispatcher) | Extract `run_study` dispatch into a registry pattern | ✅ Implemented — registry-backed adapter in `engine/engine.py` (`_STUDY_REGISTRY` + `_validate_study_kwargs`); proven by `tests/test_run_study_behavioral_equivalence.py` + `tests/test_run_study_registry.py` (29 tests, zero warnings/skips/errors) | 2026-08-07 |

## Summary

- **Deep modules (good):** `engine/interfaces.py`, `engine/cache_manager.py`, `engine/error_handler.py`, `load_flow/load_flow.py`
- **Shallow modules (needs deepening):** `engine/__init__.py` (re-export), `etap_integration/__init__.py` (boilerplate lazy-load), individual provider `USE_ETAP` checks
- **Seam discipline:** Strong — protocols defined in `engine/interfaces.py`, constructor injection in `PowerSystemEngine`
- **Deletion test:** Remove `engine/__init__.py` re-exports? No code breaks if callers import from submodules directly (pass-through detected)
- **Fixed:** `run_study` registry-backed adapter (finding #1) — see "Previously Fixed Findings"
