"""tests/test_battery_storage_acceptance.py — Dual Acceptance & Fail-Closed Gate Suite for Battery Storage (PILOT).

Validates:
1. Fail-closed gate: Execution rejected with SpecializedExecutionUnavailableError when flag is OFF.
2. Parameter validation: Rejection when empty parameters provided to native dispatch.
3. System requirement: Rejection when system model is missing.
4. Positive execution: IEC 62933 BESS capacity sizing and ROI financial evaluation
   when flag is enabled, returning IEC 62933 metrics and pilot provenance.
"""

from __future__ import annotations

import pytest

from core.exceptions import SpecializedExecutionUnavailableError
from core_model.specs import BusSpec, LineSpec, SystemSpec
from services.study_executor import StudyExecutor


@pytest.fixture(name="bess_system")
def fixture_bess_system():
    """Create a 2-bus test system for battery storage integration."""
    spec = SystemSpec(
        base_mva=5.0,
        buses=[
            BusSpec(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=0.48),
            BusSpec(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=0.48),
        ],
        lines=[
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.02, x1=0.05, bshunt1=0.0),
        ],
        transformers=[],
        generators=[],
        loads=[],
    )
    executor = StudyExecutor(cache=None)
    return executor._build_system_from_spec(spec)


def test_battery_storage_rejected_when_flag_disabled(bess_system, monkeypatch):
    """Fail-Closed Test 1: Flag disabled (default) must raise SpecializedExecutionUnavailableError."""
    monkeypatch.setenv("FEATURE_FLAG_BATTERY_STORAGE", "false")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "sizing",
        "load_profile_kw": [200.0, 300.0, 450.0, 520.0, 480.0, 300.0, 200.0],
        "target_peak_kw": 400.0,
    }

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("battery_storage", bess_system, params)

    assert exc_info.value.study_type == "battery_storage"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
    assert "disabled" in str(exc_info.value).lower()


def test_battery_storage_rejected_when_empty_parameters(bess_system):
    """Fail-Closed Test 2: Empty parameters must raise SpecializedExecutionUnavailableError."""
    executor = StudyExecutor(cache=None)

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("battery_storage", bess_system, {})

    assert exc_info.value.study_type == "battery_storage"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"


def test_battery_storage_rejected_when_system_missing():
    """Fail-Closed Test 3: Missing system model must raise ValueError."""
    executor = StudyExecutor(cache=None)
    params = {
        "analysis_type": "sizing",
        "load_profile_kw": [200.0, 300.0, 400.0],
    }

    with pytest.raises(ValueError) as exc_info:
        executor._dispatch("battery_storage", None, params)

    assert "requires a 'system'" in str(exc_info.value)


def test_battery_storage_positive_execution_sizing(bess_system, monkeypatch):
    """Positive Test 1: With flag enabled, executes IEC 62933 BESS capacity sizing for peak shaving."""
    monkeypatch.setenv("FEATURE_FLAG_BATTERY_STORAGE", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "sizing",
        "load_profile_kw": [
            200.0, 180.0, 160.0, 180.0, 250.0, 350.0, 450.0, 500.0,
            520.0, 510.0, 490.0, 500.0, 480.0, 460.0, 400.0, 380.0,
            350.0, 320.0, 280.0, 250.0, 220.0, 200.0, 190.0, 180.0,
        ],
        "target_peak_kw": 400.0,
        "discharge_duration_hours": 4.0,
    }

    raw = executor._dispatch("battery_storage", bess_system, params)

    assert "sizing" in raw
    sz = raw["sizing"]
    assert sz.get("power_capacity_kw") > 0.0
    assert sz.get("energy_capacity_kwh") > 0.0

    provenance = raw.get("provenance", {})
    assert provenance.get("standard") == "IEC 62933"
    assert provenance.get("lifecycle") == "pilot"
    assert provenance.get("handler") == "agents.battery_storage_agent.BatteryStorageAgent"


def test_battery_storage_positive_execution_roi(bess_system, monkeypatch):
    """Positive Test 2: With flag enabled, executes BESS financial ROI and payback period calculation."""
    monkeypatch.setenv("FEATURE_FLAG_BATTERY_STORAGE", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "roi",
        "bess_power_kw": 500.0,
        "bess_energy_kwh": 2000.0,
        "annual_revenue_usd": 85000.0,
        "capex_per_kwh": 300.0,
        "capex_per_kw": 100.0,
    }

    raw = executor._dispatch("battery_storage", bess_system, params)

    assert "roi" in raw
    roi_data = raw["roi"]
    assert "payback_period_years" in roi_data or "npv_usd" in roi_data or "simple_payback_years" in roi_data

    provenance = raw.get("provenance", {})
    assert provenance.get("standard") == "IEC 62933"
    assert provenance.get("lifecycle") == "pilot"
