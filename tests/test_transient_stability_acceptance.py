"""tests/test_transient_stability_acceptance.py — Production Acceptance & Numerical Gate Suite for Transient Stability (PRODUCTION).

Validates:
1. Fail-closed gate: Execution rejected with SpecializedExecutionUnavailableError when flag is explicitly disabled via env override.
2. Parameter validation: Rejection when empty parameters provided to native dispatch.
3. System requirement: Rejection when system model is missing.
4. Positive execution: SMIB critical clearing time and multi-machine transient stability (RK4)
   when flag is enabled, returning IEEE 399 metrics and production provenance.
5. Deterministic production eligibility via engine.capability_registry.is_production_eligible().
6. IEEE 399 benchmark certification (SMIB Equal Area Criterion CCT and 3-Machine RK4 Dynamic Swing).
"""

from __future__ import annotations

import numpy as np
import pytest

from core.exceptions import SpecializedExecutionUnavailableError
from core_model.specs import BusSpec, LineSpec, SystemSpec
from engine.benchmarks.ieee_cases import calculate_ieee_399_transient_stability_benchmark
from engine.capability_registry import LifecycleStatus, get_capability_registry
from services.study_executor import StudyExecutor


@pytest.fixture(name="stability_system")
def fixture_stability_system():
    """Create a 3-bus test system."""
    spec = SystemSpec(
        base_mva=100.0,
        buses=[
            BusSpec(bus_id=1, voltage_magnitude=1.05, voltage_angle=0.0, bus_type="slack", base_kv=230.0),
            BusSpec(bus_id=2, voltage_magnitude=1.02, voltage_angle=-0.05, bus_type="pv", base_kv=230.0),
            BusSpec(bus_id=3, voltage_magnitude=1.00, voltage_angle=-0.10, bus_type="pq", base_kv=230.0),
        ],
        lines=[
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.01, x1=0.05, bshunt1=0.0),
            LineSpec(line_id=2, from_bus_id=2, to_bus_id=3, r1=0.02, x1=0.10, bshunt1=0.0),
        ],
        transformers=[],
        generators=[],
        loads=[],
    )
    executor = StudyExecutor(cache=None)
    return executor._build_system_from_spec(spec)


def test_transient_stability_rejected_when_flag_disabled(stability_system, monkeypatch):
    """Fail-Closed Test 1: Flag disabled via env override must raise SpecializedExecutionUnavailableError."""
    monkeypatch.setenv("FEATURE_FLAG_TRANSIENT_STABILITY", "false")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "critical_clearing_time",
        "smib_H": 5.0,
        "smib_Pm": 0.8,
        "smib_E": 1.1,
        "smib_V_inf": 1.0,
        "smib_X_total": 0.5,
        "smib_X_faulted": 1e6,
        "smib_delta0": 0.5,
    }

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("transient_stability", stability_system, params)

    assert exc_info.value.study_type == "transient_stability"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
    assert "disabled" in str(exc_info.value).lower()


def test_transient_stability_rejected_when_empty_parameters(stability_system):
    """Fail-Closed Test 2: Empty parameters must raise SpecializedExecutionUnavailableError."""
    executor = StudyExecutor(cache=None)

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("transient_stability", stability_system, {})

    assert exc_info.value.study_type == "transient_stability"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"


def test_transient_stability_rejected_when_system_missing():
    """Fail-Closed Test 3: Missing system model must raise ValueError."""
    executor = StudyExecutor(cache=None)
    params = {
        "analysis_type": "critical_clearing_time",
        "smib_H": 5.0,
        "smib_Pm": 0.8,
        "smib_E": 1.1,
        "smib_V_inf": 1.0,
        "smib_X_total": 0.5,
        "smib_X_faulted": 1e6,
        "smib_delta0": 0.5,
    }

    with pytest.raises(ValueError) as exc_info:
        executor._dispatch("transient_stability", None, params)

    assert "requires a 'system'" in str(exc_info.value)


def test_transient_stability_positive_execution_cct(stability_system, monkeypatch):
    """Positive Test 1: With flag enabled, executes SMIB Critical Clearing Time analysis per IEEE 399."""
    monkeypatch.setenv("FEATURE_FLAG_TRANSIENT_STABILITY", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "critical_clearing_time",
        "smib_H": 5.0,
        "smib_Pm": 0.8,
        "smib_E": 1.1,
        "smib_V_inf": 1.0,
        "smib_X_total": 0.5,
        "smib_X_faulted": 1e6,
        "smib_delta0": 0.5,
    }

    raw = executor._dispatch("transient_stability", stability_system, params)

    assert "critical_clearing_time" in raw
    cct_data = raw["critical_clearing_time"]
    assert cct_data.get("critical_clearing_time_s") > 0.0
    assert cct_data.get("critical_clearing_angle_deg") > 0.0

    provenance = raw.get("provenance", {})
    assert provenance.get("standard") == "IEEE 399"
    assert provenance.get("lifecycle") == "production"
    assert provenance.get("handler") == "agents.stability_agent.StabilityAgent"


def test_transient_stability_positive_execution_multimachine(stability_system, monkeypatch):
    """Positive Test 2: With flag enabled, executes 3-machine transient stability simulation."""
    monkeypatch.setenv("FEATURE_FLAG_TRANSIENT_STABILITY", "true")
    executor = StudyExecutor(cache=None)

    ybus = np.array([
        [4.0 - 15.0j, -2.0 + 8.0j, -1.0 + 4.0j],
        [-2.0 + 8.0j, 5.0 - 18.0j, -2.0 + 7.0j],
        [-1.0 + 4.0j, -2.0 + 7.0j, 4.0 - 14.0j],
    ])

    params = {
        "analysis_type": "transient",
        "inertia_constants": [5.0, 4.0, 3.5],
        "damping_coefficients": [2.0, 2.0, 2.0],
        "mechanical_power": [0.8, 0.6, 0.5],
        "Ybus_reduced": ybus.tolist(),
        "internal_voltages": [1.05, 1.02, 1.00],
        "initial_angles_rad": [0.1, 0.05, 0.0],
        "fault_bus": 1,
        "fault_time_s": 0.0,
        "clearing_time_s": 0.10,
        "simulation_time_s": 1.5,
        "time_step_s": 0.01,
    }

    raw = executor._dispatch("transient_stability", stability_system, params)

    assert "transient_stability" in raw
    ts_data = raw["transient_stability"]
    assert "time" in ts_data
    assert len(ts_data.get("time", [])) > 10
    assert "delta_deg" in ts_data

    provenance = raw.get("provenance", {})
    assert provenance.get("standard") == "IEEE 399"
    assert provenance.get("lifecycle") == "production"


def test_transient_stability_is_production_eligible():
    """Verify that transient_stability meets all deterministic criteria for PRODUCTION."""
    cap = get_capability_registry().get("transient_stability")
    assert cap is not None, "transient_stability capability must be registered"
    assert cap.lifecycle_status == LifecycleStatus.PRODUCTION
    assert cap.production_supported is True
    assert cap.benchmark_status == "VERIFIED_BENCHMARK"
    assert "IEEE 399" in cap.standards_scope
    assert "engine/benchmarks/ieee_cases.py" in cap.validation_evidence
    assert cap.is_production_eligible() is True


def test_transient_stability_ieee399_benchmark():
    """Verify IEEE 399 SMIB CCT and 3-Machine RK4 dynamic simulation benchmarks within tolerance."""
    res = calculate_ieee_399_transient_stability_benchmark()
    assert res["all_passed"] is True, f"IEEE 399 transient stability benchmark failed: {res}"
    assert res["max_error_pct"] <= 0.5, f"Error exceeded tolerance: {res['max_error_pct']}%"
    assert res["smib_cct_case"]["passed"] is True
    assert res["multimachine_rk4_case"]["passed"] is True
