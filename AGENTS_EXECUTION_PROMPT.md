# PROMPT — Safe Activation of Disabled Features: Execution Guide for the Execution Agent

**version:** 2.0.0
**date:** 2026-10-07
**status:** EXECUTION GUIDE
**risk_class:** HIGH — Requires documented engineering decision for each feature

---

## 1. Core Principle (Golden Rule)

> **"Never enable a feature before confirming a live execution path via STUDY_DISPATCH / StudyExecutor."**

Almost all problems today do not originate in the flags themselves, but in the mismatch between the requested implementation and the actual codebase structure. The current architecture is:

- `engine/capability_registry.py` — **Single Source of Truth** for capabilities, studies, lifecycle status (LifecycleStatus), and flags.
- `engine/dispatch.py` — **`STUDY_DISPATCH`** dynamically built from CapabilityRegistry (a derived projection, not a hardcoded table).
- `services/study_executor.py` — `StudyExecutor` contains `_dispatch()`, `_dispatch_native()`, `_dispatch_agent()`, which delegate to `PowerSystemEngine` (native) or `BaseAgent` (agent).
- `agents/registry.py` — `CANONICAL_AGENT_KEYS` (27 keys) and `create_agent_registry()` (agent registry).

> **Difference from the old prompt:** There is no `AGENT_REGISTRY` dictionary. No `elif` chain. `_dispatch()` does not handle `elif study_type`; it branches according to `registration.handler_type`.



## 3. Activation Procedure (Phase A → B → C)

### Phase A — Feature Flag + Write Execution Path

**Goal:** Add a "live execution path" for disabled studies (e.g., `harmonic_analysis`, `optimal_power_flow`, `motor_starting`, `transient_stability`, `cable_sizing`, `earth_grid`, `renewable_integration`, `battery_storage`, `scada`, `digital_twin`). Do not add a simple `elif`. Start with the correct path.

#### Step 1 — Define the Target and Accuracy
1. Identify the study required and its internal code (snake_case or `StudyType` enum).
2. Find the **capability ID** in `engine/capability_registry.py` — do not invent a code without a source.
3. Verify `LifecycleStatus` in the registry: must be `EXPERIMENTAL`, `INTERNAL`, `PILOT`, or `DISABLED` before activation.
4. Record the `feature_flag` key (from `api/feature_flags.py::DEFAULT_FEATURE_FLAGS`) and `risk_class`.

#### Step 2 — Verify the Live Execution Path

**Use this template when examining `services/study_executor.py::StudyExecutor._dispatch()`:**

```python
# 1. Confirm the study exists in STUDY_DISPATCH
#    (Built from CapabilityRegistry — not hardcoded; engine/dispatch.py:89-124)
canonical = _NATIVE_ALIASES.get(study_type, study_type)
assert canonical in STUDY_DISPATCH, f"Unregistered: {study_type}"

# 2. Check handler_type of the current study
#    (native → PowerSystemEngine; agent → BaseAgent; external → evaluator)
registration = STUDY_DISPATCH[canonical]
assert registration.handler_type in {"native", "agent", "external"}

# 3. If agent-routed, follow the _dispatch_agent() path:
#    - resolve_agent_key(study_type) (agents/registry.py:134-137)
#    - create_agent_registry() (agents/registry.py:129-132)
#    - agents[canonical_key].execute(task) via EngineeringTask
#    - special cases: etap_expert, etap_gui, ahmed_etap_orchestration

# 4. If native, follow the _dispatch_native() path:
#    - PowerSystemEngine(system) (engine/engine.py)
#    - method = getattr(engine, registration.handler)
#    - parameters validation via registration.required_params
#    - return method(**parameters)
```

**Key points:**
- If no processing block exists in `_dispatch()` and `handler_type` is not `native`, write: "No live path: scaffolding only — DO NOT auto-execute."
- If `registration.requires_system` and `system` is not provided, raise `ValueError` before any execution.

---

## 2. Three Security Layers (Reference for All Steps)

### Layer 1 — Fail-Closed Gate (Feature Flag)
- Each agent/study has a feature flag in `api/feature_flags.py::DEFAULT_FEATURE_FLAGS`.
- Dangerous agents (`generative_design`, `breaker_duty`) use `is_strict_feature_enabled()` **without forcing True in dev/test**.

#### Phase B: Calibration
1. Refer to `scripts/run_ieee_benchmarks.py` (exists).
2. Use IEEE benchmark cases:
   - `harmonic_analysis`: IEEE 519-2022, THD target
   - `optimal_power_flow`: IEEE 30-bus (`tests/load_flow/test_optimal_power_flow.py`)
   - `motor_starting`: IEEE 399, Direct-on-Delta / Star-Delta (`test_motor_starting_simulation.py`)
   - `transient_stability`: Swing equation (RK4) (`tests/scenarios/test_stability_scenario.py`)
   - `cable_sizing`: IEC 60364 + IEC 60287 (`tests/scenarios/test_cable_sizing_scenario.py`)
   - `earth_grid`: IEEE 80, Leybourne-Smith (`tests/scenarios/test_earth_grid_scenario.py`)
3. Document results in `docs/validation/<study_type>_validation.md` (create the directory if needed).

#### Phase C: Production Increment
- Do not enable 100% rollout directly.
- Use `rollout_percentage`, `allow_list`, `status` from `DEFAULT_FEATURE_FLAGS`.
- Refer to `docs/ARCHITECTURAL_CONSOLIDATION_REPORT.md` for updates.

---

## 4. Agent Patterns (Correct Patterns)

### 4.1 — Register the Study in CapabilityRegistry

When registering a study in `engine/capability_registry.py::CapabilityRegistry::register()`, include the minimum required fields:

```python
registry.register(
    CapabilityDefinition(
        capability_id="harmonic_analysis",      # from study (snake_case)
        study_type="harmonic_analysis",          # matches StudyType
        executor_kind=ExecutorKind.AGENT,        # or NATIVE / ETAP / ...
        handler="agents.harmonic_analysis_agent.HarmonicAnalysisAgent",  # or "load_flow.load_flow.run_load_flow"
        requires_system=True,
        required_params=(),
        agent_key="harmonic_analysis",           # matches CANONICAL_AGENT_KEYS
        risk_class="medium",
        version="<next-version>",
        lifecycle_status=LifecycleStatus.EXPERIMENTAL,
        description="Harmonic analysis (IEEE 519)",
    )
)
```

> **Note:** `CapabilityRegistry` is a logical dictionary stored in `_DEFAULT_REGISTRY` (singleton). Registration must happen before `STUDY_DISPATCH` runs (it is created on import). If adding a new study, ensure its registration occurs in `get_capability_registry()` or in `engine/capability_registry.py` (via `get_capability_registry()`).

### 4.2 — Add Execution Path in StudyExecutor

Replace the incorrect pattern from the old prompt:

```python
# ❌ WRONG — do not do this (assumes legacy architecture)
elif study_type == "<STUDY_TYPE>":
    agent = AGENT_REGISTRY["<agent_key>"]   # ← does not exist
    ...
```

Use the correct pattern when adding a new agent-routed study:

```python
# ✅ CORRECT — agent-routed study (e.g., harmonic_analysis, cable_sizing, ...)
if canonical == "<study_type>":
    from agents.registry import create_agent_registry, resolve_agent_key
    canonical_key = resolve_agent_key("<study_type>")
    agents = create_agent_registry()
    if canonical_key in agents:
        agent = agents[canonical_key]
        task = EngineeringTask(
            task_id=f"agent_task_{canonical_key}_{int(time.time() * 1000)}",
            description=f"Specialist agent execution for {canonical}",
            study_types=[StudyType(canonical_key)],
            parameters=parameters,
        )
        # For async: wrap asyncio.run with ThreadPoolExecutor
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: agent.execute(task)  # or asyncio.run(agent.execute(task)) if no loop running
        )
        return result.data
    raise SpecializedExecutionUnavailableError(
        canonical, f"No agent registered for study type '{canonical}'"
    )
```

When adding a new native study:

```python
# ✅ CORRECT — native study (e.g., optimal_power_flow, short_circuit, ...)
if registration.handler_type == "native":
    from engine.engine import PowerSystemEngine
    engine = PowerSystemEngine(system)
    method = getattr(engine, registration.handler)
    # Verify required_params
    missing = [p for p in registration.required_params if parameters.get(p) is None]
    if missing:
        raise ValueError(f"Missing required params: {missing}")
    return method(**parameters)
```

When adding a special path (e.g., `breaker_duty`) — follow the similar pattern to what exists:

```python
if canonical == "breaker_duty":
    from api.feature_flags import is_strict_feature_enabled
    if not is_strict_feature_enabled("breaker_duty"):
        raise SpecializedExecutionUnavailableError(
            "breaker_duty", "Feature flag 'breaker_duty' is disabled"
        )
    from breaker_duty.evaluator import BreakerDutyEvaluator
    return BreakerDutyEvaluator().execute_study(parameters)


## 5. Testing and Calibration Requirements (from Phase A)

| Study | Step | Test Command | Standard | Reference File |
|-------|------|--------------|----------|----------------|
| `harmonic_analysis` | First | `pytest tests/test_harmonic_analysis_ieee519.py` | THD ±3% | `scripts/run_ieee_benchmarks.py` |
| `optimal_power_flow` | Second | `pytest tests/load_flow/test_optimal_power_flow.py` | IEEE 30-bus | Same file |
| `motor_starting` | Third | `pytest tests/test_motor_starting_simulation.py` | IEEE 399 | Same file |
| `transient_stability` | Fourth | `pytest tests/scenarios/test_stability_scenario.py` | Swing Eq | Same file |
| `cable_sizing` | Fifth | `pytest tests/scenarios/test_cable_sizing_scenario.py` | IEC 60364 | Same file |
| `earth_grid` | Sixth | `pytest tests/scenarios/test_earth_grid_scenario.py` | IEEE 80 | Same file |
| `renewable_integration` | Seventh (optional) | Verify `RenewableAgent` tests | IEEE 1547 | Same file |
| `battery_storage` | Eighth (optional) | Verify `BatteryStorageAgent` tests | IEC 62933 | Same file |
| `scada` | Defer | Build infrastructure | — | Deferred |
| `digital_twin` | Defer | Build stream infrastructure | — | Deferred |

**Mandatory test rule for every feature:**
1. **Success test:** scientific test proving `StudyExecutor().execute_native()` returns `success=True` when `enabled=True`.
2. **Reject test:** scientific test proving `execute_native()` raises an error when `enabled=False`.
3. **Physical calibration:** comparison with published benchmarks within `% ACCEPTED_ERROR`.
4. **Documentation:** `docs/ARCHITECTURAL_CONSOLIDATION_REPORT.md` updated.

```

- **Never modify these functions** — they are the primary protection.

### Layer 2 — Executor Gate (Live Execution Path)
- Even when a flag is enabled, a processing block must exist in `StudyExecutor._dispatch()` (or the appropriate execution path).
- Without a live path, `SpecializedExecutionUnavailableError` or `ValueError` is raised immediately.
- **Absence** of a processing block in `_dispatch()` is not a code error — it is an indicator that the study is still "scaffold".

### Layer 3 — Validation Gate (Result Calibration)
- Physical transformers require calibration tests against published benchmark cases.
- Without calibration, results are not trustworthy and must not be used in actual designs.


## 6. Non-Negotiable Rules

### ❌ Strictly Forbidden
1. Modify `is_feature_enabled()` or `is_strict_feature_enabled()` to force True.
2. Remove the feature flag gate from any execution path.
3. Enable a feature in production without clear calibration testing.
4. Increase rollout from 0% to 100% in one step.
5. Enable `generative_design` without a licensed engineer's approval + risk acceptance document.
6. Call a function in `StudyExecutor._dispatch()` that does not exist without adding its definition first.
7. Assume `AGENT_REGISTRY` is a fixed dictionary — use `create_agent_registry()` and `resolve_agent_key()`.

### ✅ Fully Required
1. Write a test proving success when the flag is enabled.
2. Write a test proving rejection when the flag is disabled.
3. Document reference cases and expected results.
4. Add `risk_class` and `lifecycle_status` in `CapabilityRegistry`.
5. Update `docs/ARCHITECTURAL_CONSOLIDATION_REPORT.md` for each activated study.
6. Add Prometheus metrics for monitoring success/failure of each activated study.
7. Document `docs/safety/` for each high-risk feature (`generative_design` in particular).

---

## 7. Execution Order for the Agent

When the execution agent starts, it must follow this exact sequence:

```
1. Read api/feature_flags.py:69-230 → understand DEFAULT_FEATURE_FLAGS and is_feature_enabled / is_strict_feature_enabled
2. Read engine/capability_registry.py → understand CapabilityRegistry and ExecutorKind / LifecycleStatus
3. Read engine/dispatch.py (all) → understand STUDY_DISPATCH and StudyRegistration
4. Read services/study_executor.py → understand _dispatch(), _dispatch_native(), _dispatch_agent()
5. Read agents/registry.py → understand CANONICAL_AGENT_KEYS and create_agent_registry() and resolve_agent_key()
6. Read agents/models.py → understand StudyType enum (17 members)
7. Select one study from the list below and write the correct path in the plan
8. Add a processing block in StudyExecutor._dispatch() using the correct pattern
9. Write a test in tests/ proving:
   a. Success when the flag is enabled
   b. Rejection when the flag is disabled
10. Run pytest on the new test
11. Update capability_registry.py: lifecycle_status ← BETA/ALPHA (not DISABLED)
12. Update docs/ARCHITECTURAL_CONSOLIDATION_REPORT.md for the study
13. Run full regression tests: pytest tests/ -q --timeout=60
14. If all steps succeed → deliver a report of actions taken
```

### Possible Studies (from `StudyType` enum — agents/models.py)

| Order | Study | Feature Flag | Agent Key / Executor |
|-------|-------|--------------|---------------------|
| 1 | `harmonic_analysis` | `harmonic_analysis` | Agent (harmonic_analysis) |
| 2 | `optimal_power_flow` | `optimal_power_flow` | Agent (optimal_power_flow) + native |
| 3 | `motor_starting` | `motor_starting` | Agent (`test_motor_starting_simulation.py`) |
| 4 | `transient_stability` | `transient_stability` | Agent (`tests/scenarios/test_stability_scenario.py`) |
| 5 | `cable_sizing` | `cable_sizing` | Agent (`tests/scenarios/test_cable_sizing_scenario.py`) |
| 6 | `earth_grid` | `earth_grid` | Agent (`tests/scenarios/test_earth_grid_scenario.py`) |
| 7 | `renewable_integration` | `renewable_integration` | Agent (renewable_integration) |
| 8 | `battery_storage` | `battery_storage` | Agent (battery_storage) |
| 9 | `scada` | `scada` | Agent (scada) — requires infrastructure build |
| 10 | `digital_twin` | `digital_twin` | Agent (digital_twin) — requires infrastructure build |

---

## 8. Completion Checklist

Before declaring any feature enabled, ensure all final items are complete:

- [ ] **Live execution path:** `StudyExecutor._dispatch()` contains a block or path for the study
- [ ] **Success test when flag enabled:** pytest passes when `enabled=True`
- [ ] **Reject test when flag disabled:** pytest passes when `enabled=False`
- [ ] **Physical calibration:** study results match published benchmarks within accepted error
- [ ] **Documentation:** `docs/ARCHITECTURAL_CONSOLIDATION_REPORT.md` updated
- [ ] **Safety record:** `engine/capability_registry.py` contains correct `lifecycle_status` (not DISABLED)
- [ ] **Registration:** `CapabilityDefinition` registered with `feature_flag` and `risk_class`
- [ ] **Calibration:** `scripts/run_ieee_benchmarks.py` run (as available)
- [ ] **Monitoring:** Prometheus metric + Grafana dashboard updated
- [ ] **Error tracking:** Langfuse traces for the study
- [ ] **Rollback strategy:** `DEPLOYMENT_ROLLBACK.md` updated

---

*Generated by Integration Specialist — based on current codebase architecture (Centralized Registry + Dynamic Dispatch).*

- Calibration is not only `pytest` — it must be a standard: `ACCURACY_TOLERANCES.md`.
