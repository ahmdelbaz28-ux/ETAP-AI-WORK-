"""tests/test_motor_starting_acceptance.py — Production Acceptance & Numerical Gate Suite for Motor Starting (PRODUCTION).

Validates:
1. Fail-closed gate: Execution rejected with SpecializedExecutionUnavailableError when flag is explicitly disabled via env override.
2. Parameter validation: Rejection when empty parameters provided to native dispatch.
3. System requirement: Rejection when system model is missing.
4. Positive execution: Dynamic time-domain simulation (RK4) & IEEE 399 voltage dip calculation when flag is enabled,
   returning IEEE 399 metrics and production provenance.
5. Deterministic production eligibility via engine.capability_registry.is_production_eligible().
6. IEEE 399 benchmark certification (DOL and Star-Delta dynamic simulation cases).
"""

from __future__ import annotations

import pytest

from core.exceptions import SpecializedExecutionUnavailableError
from core_model.specs import BusSpec, LineSpec, SystemSpec
from engine.benchmarks.ieee_cases import calculate_ieee_399_motor_starting_benchmark
from engine.capability_registry import LifecycleStatus, get_capability_registry
from services.study_executor import StudyExecutor


@pytest.fixture(name="motor_system")
def fixture_motor_system():
    """Create a 2-bus test system (460 V industrial bus)."""
    spec = SystemSpec(
        base_mva=10.0,
        buses=[
            BusSpec(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=0.48),
            BusSpec(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=0.48),
        ],
        lines=[
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.01, x1=0.04, bshunt1=0.0),
        ],
        transformers=[],
        generators=[],
        loads=[],
    )
    executor = StudyExecutor(cache=None)
    return executor._build_system_from_spec(spec)


def test_motor_starting_rejected_when_flag_disabled(motor_system, monkeypatch):
    """Fail-Closed Test 1: Flag disabled via env override must raise SpecializedExecutionUnavailableError."""
    monkeypatch.setenv("FEATURE_FLAG_MOTOR_STARTING", "false")
    executor = StudyExecutor(cache=None)

    params = {
        "motor_hp": 100.0,
        "rated_voltage_v": 460.0,
        "starting_method": "DOL",
        "analysis_type": "full",
    }

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("motor_starting", motor_system, params)

    assert exc_info.value.study_type == "motor_starting"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
    assert "disabled" in str(exc_info.value).lower()


def test_motor_starting_rejected_when_empty_parameters(motor_system):
    """Fail-Closed Test 2: Empty parameters must raise SpecializedExecutionUnavailableError."""
    executor = StudyExecutor(cache=None)

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("motor_starting", motor_system, {})

    assert exc_info.value.study_type == "motor_starting"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"


def test_motor_starting_rejected_when_system_missing():
    """Fail-Closed Test 3: Missing system model must raise ValueError."""
    executor = StudyExecutor(cache=None)
    params = {
        "motor_hp": 100.0,
        "rated_voltage_v": 460.0,
        "starting_method": "DOL",
    }

    with pytest.raises(ValueError) as exc_info:
        executor._dispatch("motor_starting", None, params)

    assert "requires a 'system'" in str(exc_info.value)


def test_motor_starting_positive_execution(motor_system, monkeypatch):
    """Positive Test: Executes IEEE 399 motor starting analysis and returns production provenance."""
    monkeypatch.setenv("FEATURE_FLAG_MOTOR_STARTING", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "motor_hp": 100.0,
        "rated_voltage_v": 460.0,
        "rated_rpm": 1780.0,
        "rated_eff": 0.93,
        "rated_pf": 0.88,
        "starting_method": "DOL",
        "analysis_type": "full",
        "z_source_r_ohms": 0.01,
        "z_source_x_ohms": 0.04,
    }

    result = executor._dispatch("motor_starting", motor_system, params)

    assert isinstance(result, dict)
    assert "starting_current" in result
    assert result["starting_current"]["lra_a"] > 0
    assert "voltage_dip" in result
    assert 0.0 <= result["voltage_dip"]["voltage_dip_percent"] <= 100.0
    assert "transient_voltage_drop" in result
    assert result["transient_voltage_drop"]["v_terminal_pu"] > 0.0

    provenance = result.get("provenance", {})
    assert provenance.get("lifecycle") == "production"
    assert provenance.get("standard") == "IEEE 399"
    assert provenance.get("handler") == "agents.motor_starting_agent.MotorStartingAgent"


def test_motor_starting_is_production_eligible():
    """Verify that motor_starting meets all deterministic criteria for PRODUCTION."""
    cap = get_capability_registry().get("motor_starting")
    assert cap is not None, "motor_starting capability must be registered"
    assert cap.lifecycle_status == LifecycleStatus.PRODUCTION
    assert cap.production_supported is True
    assert cap.benchmark_status == "VERIFIED_BENCHMARK"
    assert "IEEE 399" in cap.standards_scope
    assert "engine/benchmarks/ieee_cases.py" in cap.validation_evidence
    assert cap.is_production_eligible() is True


def test_motor_starting_ieee399_benchmark():
    """Verify IEEE 399 DOL and Star-Delta dynamic simulation benchmarks within tolerance."""
    res = calculate_ieee_399_motor_starting_benchmark()
    assert res["all_passed"] is True, f"IEEE 399 motor starting benchmark failed: {res}"
    assert res["max_error_pct"] <= 3.0, f"Error exceeded tolerance: {res['max_error_pct']}%"
    assert res["dol_case"]["passed"] is True
    assert res["star_delta_case"]["passed"] is True
