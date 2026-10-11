"""tests/test_renewable_integration_acceptance.py — Dual Acceptance & Fail-Closed Gate Suite for Renewable Integration (PILOT).

Validates:
1. Fail-closed gate: Execution rejected with SpecializedExecutionUnavailableError when flag is OFF.
2. Parameter validation: Rejection when empty parameters provided to native dispatch.
3. System requirement: Rejection when system model is missing.
4. Positive execution: IEEE 1547 solar PV energy estimation & feeder hosting capacity
   when flag is enabled, returning IEEE 1547 metrics and pilot provenance.
"""

from __future__ import annotations

import pytest

from core.exceptions import SpecializedExecutionUnavailableError
from core_model.specs import BusSpec, LineSpec, SystemSpec
from services.study_executor import StudyExecutor


@pytest.fixture(name="renewable_system")
def fixture_renewable_system():
    """Create a 3-bus distribution feeder test system."""
    spec = SystemSpec(
        base_mva=10.0,
        buses=[
            BusSpec(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=13.8),
            BusSpec(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=13.8),
            BusSpec(bus_id=3, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=13.8),
        ],
        lines=[
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.01, x1=0.03, bshunt1=0.0),
            LineSpec(line_id=2, from_bus_id=2, to_bus_id=3, r1=0.02, x1=0.06, bshunt1=0.0),
        ],
        transformers=[],
        generators=[],
        loads=[],
    )
    executor = StudyExecutor(cache=None)
    return executor._build_system_from_spec(spec)


def test_renewable_integration_rejected_when_flag_disabled(renewable_system, monkeypatch):
    """Fail-Closed Test 1: Flag disabled (default) must raise SpecializedExecutionUnavailableError."""
    monkeypatch.setenv("FEATURE_FLAG_RENEWABLE_INTEGRATION", "false")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "solar_pv",
        "pv_dc_capacity_kw": 500.0,
        "pv_ac_capacity_kw": 400.0,
    }

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("renewable_integration", renewable_system, params)

    assert exc_info.value.study_type == "renewable_integration"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
    assert "disabled" in str(exc_info.value).lower()


def test_renewable_integration_rejected_when_empty_parameters(renewable_system):
    """Fail-Closed Test 2: Empty parameters must raise SpecializedExecutionUnavailableError."""
    executor = StudyExecutor(cache=None)

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("renewable_integration", renewable_system, {})

    assert exc_info.value.study_type == "renewable_integration"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"


def test_renewable_integration_rejected_when_system_missing():
    """Fail-Closed Test 3: Missing system model must raise ValueError."""
    executor = StudyExecutor(cache=None)
    params = {
        "analysis_type": "solar_pv",
        "pv_dc_capacity_kw": 500.0,
    }

    with pytest.raises(ValueError) as exc_info:
        executor._dispatch("renewable_integration", None, params)

    assert "requires a 'system'" in str(exc_info.value)


def test_renewable_integration_positive_execution_solar(renewable_system, monkeypatch):
    """Positive Test 1: With flag enabled, executes IEEE 1547 solar PV energy estimation."""
    monkeypatch.setenv("FEATURE_FLAG_RENEWABLE_INTEGRATION", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "solar_pv",
        "pv_dc_capacity_kw": 600.0,
        "pv_ac_capacity_kw": 500.0,
        "tilt_deg": 25.0,
        "azimuth_deg": 180.0,
    }

    raw = executor._dispatch("renewable_integration", renewable_system, params)

    assert "solar_pv" in raw
    pv_data = raw["solar_pv"]
    assert pv_data.get("annual_energy_kwh") > 0.0
    assert pv_data.get("ac_capacity_kw") == 500.0

    provenance = raw.get("provenance", {})
    assert provenance.get("standard") == "IEEE 1547"
    assert provenance.get("lifecycle") == "pilot"
    assert provenance.get("handler") == "agents.renewable_agent.RenewableAgent"


def test_renewable_integration_positive_execution_hosting_capacity(renewable_system, monkeypatch):
    """Positive Test 2: With flag enabled, executes feeder hosting capacity calculation."""
    monkeypatch.setenv("FEATURE_FLAG_RENEWABLE_INTEGRATION", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "hosting_capacity",
        "feeder_head_kva": 10000.0,
        "min_voltage_pu": 0.95,
        "max_voltage_pu": 1.05,
    }

    raw = executor._dispatch("renewable_integration", renewable_system, params)

    assert "hosting_capacity" in raw
    hc_data = raw["hosting_capacity"]
    assert hc_data.get("hosting_capacity_kw") > 0.0
    assert "limiting_constraint" in hc_data

    provenance = raw.get("provenance", {})
    assert provenance.get("standard") == "IEEE 1547"
    assert provenance.get("lifecycle") == "pilot"
