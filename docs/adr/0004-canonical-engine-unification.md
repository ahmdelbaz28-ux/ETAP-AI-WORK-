# ADR 0004: Canonical Calculation Engine Unification (PowerSystemEngine)

## Context
AhmedETAP evolved with multiple entry points for engineering studies:
1. `engine/engine.py` hosting `PowerSystemEngine`, which serves as the direct calculation backbone integrated with Mastra TypeScript agents, FastAPI endpoints, and test suites.
2. `core/study_engine.py` (338 lines), an experimental wrapper introduced for unified study dispatch with separate dataclasses.

Having dual study dispatch mechanisms introduces duplication debt, maintenance overhead, and ambiguity about the authoritative source of truth.

## Decision
We declare `engine/engine.py :: PowerSystemEngine` as the single canonical calculation engine for all power system studies in AhmedETAP.

1. **Canonical Source of Truth**: All study executions (Load Flow, Short Circuit IEC 60909, Arc Flash IEEE 1584-2018, Harmonics IEEE 519, Protection Coordination IEC 60255, Motor Starting IEEE 399, Transient Stability, Cable Sizing, and Grounding) must route through `PowerSystemEngine` or its specialized modular sub-engines (`load_flow/`, `fault_analysis/`, `motor_starting/`, `contingency/`, `coordination/`).
2. **Deprecation of `core/study_engine.py`**: `core/study_engine.py` is maintained solely as a backward-compatibility facade for legacy tests (`tests/test_study_engine_deep.py`). No new production features or endpoints shall depend on `core.study_engine`.
3. **Alignment**: Confirms and reinforces the findings in `docs/SINGLE_ENGINE_ARCHITECTURE_ENFORCEMENT_REPORT.md`.

## Status
**Accepted & Enforced** (2026-09-20)
