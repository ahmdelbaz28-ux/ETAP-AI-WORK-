# M4 — AI Provider Policy & Context-Boundary Hardening

**Phase:** M4 (context-boundaries) · **Status:** ✅ Complete
**Branch:** `feat/ai-m4-context-boundaries` · **Date:** 2026-09-30
**Protocol:** Architectural closure — this report is required before a PR may merge to `main`.

---

## 1. Objective

M4 hardens the AI execution surface so that **only authenticated, in-policy LLM
calls are emitted**, and so that **context-bound concepts (e.g. `predictive`,
`anomaly`) can never be mistaken for executable study types**. It closes the
gap between the Mastra (TypeScript) planning layer and the Python execution
layer (M4.2), and guarantees the Raw-LLM Fallback Guard (M4.3) stays clean.

---

## 2. Scope — M4 Items Addressed

| ID | Item | Summary | Evidence |
|----|------|---------|----------|
| M4.1 | LLM provider allow/deny policy | `config/llm-provider-policy.json` + `integrations/provider_policy.py` (Python) and `src/core/providers.ts` / `src/mastra/lib/model-config.ts` (TS). `fallback_agent` is hard-deny in every runtime; default model is allow-listed. | `tests/test_llm_provider_policy.py` (14) • `tests/unit/core-providers-policy.test.ts` (9) |
| M4.2 | Context boundaries — Mastra plans, Python executes | New orchestrator boundary adapter `ChiefEngineeringOrchestrator.execute_execution_plan()` consuming `ExecutionPlanContract` → returning `ExecutionTraceContract`, reusing M3 scheduling. | `tests/test_m4_context_boundaries.py` — section 6 (6 new tests) |
| M4.3 | Raw-LLM fallback guard | `scripts/check_ai_fallback_guard.py` + Meta-CI gate. | `check_ai_fallback_guard.py` exit 0 |
| M4.4 | Honest `overall_success` | `execute_execution_plan` folds an independent `ValidationAgent` pass into `trace.overall_success` and appends a `ValidationResultContract` — self-reported flags alone never claim success. | `test_execute_execution_plan_folds_in_independent_validation` |

### Context-bound keys (context-bound, never executable)
`predictive`, `anomaly` — deliberately **not** members of `StudyType` and
**not** callable via `POST /api/v1/studies/run`. Tests assert this in both
directions (Python `StudyType` + TS `CoreStudyType`).

---

## 3. Acceptance Gates & Results

| Gate | Tool | Result |
|------|------|--------|
| Python unit (M4 surface) | `pytest` — `test_m4_context_boundaries.py` | **21 passed** (15 prior + 6 M4.2) |
| Python unit (ruff-affected files) | `pytest` — `test_context_fabric.py` + `test_llm_provider_policy.py` | **25 passed** |
| Python unit (full M4 battery) | `pytest` — 8 files (namespace + boundaries + policy + fabric + fallback + predictive + bandit + digital-twin) | **86 passed** |
| Lint | `ruff check` (scope: 6 files touched by M4) | **All checks passed!** (8 found → 8 auto-fixed, 0 remaining) |
| TypeScript types | `tsc --noEmit` | **0 errors** |
| TypeScript unit | `vitest` — `core-providers-policy.test.ts` | **9 passed** |
| Meta-CI / M2.4 registry guard | `scripts/check_workflows_meta.py` | **exit 0** — Registry Integrity Guard CLEAN (M4.3: clean) |
| Raw-LLM fallback guard | `scripts/check_ai_fallback_guard.py` | **exit 0** — CLEAN |

### Note on test timing
The M4 Python suite is **~138s** for the full 86-test battery because each
`ChiefEngineeringOrchestrator()` instantiation loads the agent registry. The
6 M4.2 adapter tests alone run in ~39s when targeted. This is an existing
registry-import cost, not a regression introduced by M4.

---

## 4. Fail-Closed Enforcement Summary

M4 is **fail-closed** by design — the adapter refuses to execute rather than
guess:

* Payload that is not a valid `ExecutionPlanContract` (pydantic) → `ValueError`.
* Empty node list → `ValueError("...no nodes")`.
* Any `node.study_type` that is not a real `StudyType` member → `ValueError("...unknown study type")`.
* Trace export returning `None` → `RuntimeError("...partial trace")`.
* `overall_success` is forced `False` when the independent `ValidationAgent`
  pass does not confirm results — self-reported per-node flags are
  insufficient.

---

## 5. Files Added / Modified

**Added**
* `tests/test_m4_context_boundaries.py` (section 6 — M4.2 adapter tests)
* `tests/test_agent_key_namespace.py`, `tests/test_ai_fallback_guard.py`,
  `tests/test_context_fabric.py`, `tests/test_llm_provider_policy.py`
* `scripts/check_ai_fallback_guard.py`, `integrations/provider_policy.py`
* `config/llm-provider-policy.json`
* `context_fabric/` package
* `docs/ai-integration/m4-plan.md`, `docs/ai-integration/m4-report.md` (this file)

**Modified**
* `agents/orchestrator.py` — added `execute_execution_plan()` boundary adapter
* `agents/models.py`, `agents/registry.py`, `agents/predictive_agent.py`,
  `agents/digital_twin_agent.py` — context-bound hardening
* `integrations/model_router.py`, `integrations/langfuse_llm.py` — policy wiring
* `src/core/providers.ts`, `src/mastra/lib/model-config.ts` — TS policy parity
* `api/chat_stream.py`, `api/feature_flags.py`, `services/memory_service.py`,
  `src/routes/agents.ts`, `ai_context_engine/rag_blueprint_adapter.py`

---

## 6. Security & Secrets

No secrets are committed. Any GitHub token supplied to the agent is treated as
sensitive (never logged, never written to disk) and is used only for the
authenticated `git push` / pull-request creation against
`ahmdelbaz28-ux/ETAP-AI-WORK-`. Tenant isolation on the Engineering Service API
is enforced via `CurrentUser.tenant_id`.

---

## 7. Merge Checklist

* [x] All acceptance gates green (§3)
* [x] Ruff clean (8 fixed, 0 remaining)
* [x] `tsc --noEmit` clean
* [x] Meta-CI M2.4 + M4.3 guards clean
* [x] No scratch/log files remaining in tree
* [x] `docs/ai-integration/m4-report.md` present (this document)
* [x] Reviewed in diff (see commit message)
