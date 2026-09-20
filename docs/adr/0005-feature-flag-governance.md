# ADR 0005: Governance of Heuristic and Performance Optimization Feature Flags

## Context
Advanced optimization techniques such as:
1. `use_pso_coordination`: Particle Swarm Optimization for multi-relay TMS and curve fitting.
2. `use_warm_start`: Voltage profile caching across repeated Newton-Raphson load flow executions.
3. `use_model_cascade`: Cost-aware LLM tier cascading.

were introduced into `api/feature_flags.py`. A question arose regarding their operational status: should these flags be unconditionally enabled (`enabled: True`) across all environments, or kept strictly opt-in (`enabled: False`)?

## Decision
We mandate that heuristic optimizers and stateful accelerators remain strictly opt-in via `is_strict_feature_enabled()`:

1. **Deterministic Benchmark Compliance**: Standard benchmark test suites (such as IEEE 14-bus, IEEE 30-bus, TR 60909-1, and IEEE 1584 test cases) rely on exact, deterministic, published calculation methodologies (Newton-Raphson flat start, linear TMS grading). Non-deterministic algorithms (e.g., stochastic PSO) would create non-deterministic test flakiness and subtle deviations from published standards.
2. **Opt-in Availability**: Users requiring high-speed repeated load flows or stochastic relay optimization can enable them on demand via:
   - Environment variables: `FEATURE_FLAG_USE_PSO_COORDINATION=1`, `FEATURE_FLAG_USE_WARM_START=1`
   - Runtime configuration: `PUT /api/v1/feature-flags/{flag}`
3. **Fail-Safe Fallback**: If disabled (the default), `coordination.py` uses verified linear TMS grading and `load_flow.py` uses standardized flat-start Newton-Raphson initialization.

## Status
**Accepted & Enforced** (2026-09-20)
