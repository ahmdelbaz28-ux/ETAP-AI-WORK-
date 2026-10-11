"""tests/test_optimal_power_flow_acceptance.py — Dual Acceptance & Fail-Closed Gate Suite for OPF (PILOT).

Validates:
1. Fail-closed gate: Execution rejected with SpecializedExecutionUnavailableError when flag is OFF.
2. Parameter validation: Rejection when empty parameters provided to native dispatch.
3. System requirement: Rejection when system model is missing.
4. Positive execution: Economic merit-order dispatch and DC-OPF calculation when flag is enabled,
   returning IEEE 3002.7 metrics and pilot provenance.
"""

from __future__ import annotations

import pytest

from core.exceptions import SpecializedExecutionUnavailableError
from core_model.specs import BusSpec, LineSpec, SystemSpec
from services.study_executor import StudyExecutor


@pytest.fixture(name="opf_system")
def fixture_opf_system():
    """Create a 3-bus triangle test system for economic dispatch."""
    spec = SystemSpec(
        base_mva=100.0,
        buses=[
            BusSpec(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=11.0),
            BusSpec(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pv", base_kv=11.0),
            BusSpec(bus_id=3, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=11.0),
        ],
        lines=[
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.01, x1=0.1, bshunt1=0.0),
            LineSpec(line_id=2, from_bus_id=2, to_bus_id=3, r1=0.01, x1=0.1, bshunt1=0.0),
            LineSpec(line_id=3, from_bus_id=1, to_bus_id=3, r1=0.02, x1=0.2, bshunt1=0.0),
        ],
        transformers=[],
        generators=[],
        loads=[],
    )
    executor = StudyExecutor(cache=None)
    system = executor._build_system_from_spec(spec)
    # Set load of 80 MW at Bus 3
    system.buses[3].load_power = complex(80.0, 0.0)
    return system


def test_opf_rejected_when_flag_disabled(opf_system, monkeypatch):
    """Fail-Closed Test 1: Flag disabled (default) must raise SpecializedExecutionUnavailableError."""
    monkeypatch.setenv("FEATURE_FLAG_OPTIMAL_POWER_FLOW", "false")
    executor = StudyExecutor(cache=None)

    params = {
        "generator_costs": [
            {"generator_id": 1, "cost_coefficients": [0.0, 15.0, 0.0], "p_min": 0.0, "p_max": 100.0, "q_min": -50.0, "q_max": 50.0},
        ],
        "generator_locations": {1: 1},
        "method": "dc",
    }

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("optimal_power_flow", opf_system, params)

    assert exc_info.value.study_type == "optimal_power_flow"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
    assert "disabled" in str(exc_info.value).lower()


def test_opf_rejected_when_empty_parameters(opf_system):
    """Fail-Closed Test 2: Empty parameters must raise SpecializedExecutionUnavailableError."""
    executor = StudyExecutor(cache=None)

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("optimal_power_flow", opf_system, {})

    assert exc_info.value.study_type == "optimal_power_flow"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"


def test_opf_rejected_when_system_missing():
    """Fail-Closed Test 3: Missing system model must raise ValueError."""
    executor = StudyExecutor(cache=None)
    params = {
        "generator_costs": [
            {"generator_id": 1, "cost_coefficients": [0.0, 15.0, 0.0], "p_min": 0.0, "p_max": 100.0, "q_min": -50.0, "q_max": 50.0},
        ],
        "generator_locations": {1: 1},
    }

    with pytest.raises(ValueError) as exc_info:
        executor._dispatch("optimal_power_flow", None, params)

    assert "requires a 'system'" in str(exc_info.value)


def test_opf_positive_execution(opf_system, monkeypatch):
    """Positive Test: With flag enabled, executes DC-OPF merit-order economic dispatch and returns pilot provenance."""
    monkeypatch.setenv("FEATURE_FLAG_OPTIMAL_POWER_FLOW", "true")
    executor = StudyExecutor(cache=None)

    # Gen 1 ($15/MWh cheap) vs Gen 2 ($40/MWh expensive) to serve 80 MW load at Bus 3
    params = {
        "generator_costs": [
            {"generator_id": 1, "cost_coefficients": [0.0, 15.0, 0.0], "p_min": 0.0, "p_max": 100.0, "q_min": -50.0, "q_max": 50.0},
            {"generator_id": 2, "cost_coefficients": [0.0, 40.0, 0.0], "p_min": 0.0, "p_max": 100.0, "q_min": -50.0, "q_max": 50.0},
        ],
        "generator_locations": {1: 1, 2: 2},
        "method": "dc",
    }

    result = executor._dispatch("optimal_power_flow", opf_system, params)

    assert isinstance(result, dict)
    assert result.get("success") is True
    assert "generator_dispatch" in result
    assert 1 in result["generator_dispatch"]
    # Gen 1 should serve the full 80 MW since it is cheaper ($15 vs $40)
    assert result["generator_dispatch"][1]["P_MW"] == pytest.approx(80.0, abs=1e-2)
    assert result["generator_dispatch"][2]["P_MW"] == pytest.approx(0.0, abs=1e-2)
    assert result["total_generation_mw"] == pytest.approx(80.0, abs=1e-2)

    provenance = result.get("provenance", {})
    assert provenance.get("lifecycle") == "pilot"
    assert provenance.get("handler") == "agents.registry.OptimalPowerFlowAgent"
