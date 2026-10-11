"""tests/test_cable_sizing_acceptance.py — Dual Acceptance & Fail-Closed Gate Suite for Cable Sizing (PILOT).

Validates:
1. Fail-closed gate: Execution rejected with SpecializedExecutionUnavailableError when flag is OFF.
2. Parameter validation: Rejection when empty parameters provided to native dispatch.
3. System requirement: Rejection when system model is missing.
4. Positive execution: IEC 60364 ampacity derating & optimal cross-section recommendation
   when flag is enabled, returning IEC 60364 metrics and pilot provenance.
"""

from __future__ import annotations

import pytest

from core.exceptions import SpecializedExecutionUnavailableError
from core_model.specs import BusSpec, LineSpec, SystemSpec
from services.study_executor import StudyExecutor


@pytest.fixture(name="cable_system")
def fixture_cable_system():
    """Create a 2-bus low voltage test system."""
    spec = SystemSpec(
        base_mva=1.0,
        buses=[
            BusSpec(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=0.4),
            BusSpec(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=0.4),
        ],
        lines=[
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.05, x1=0.02, bshunt1=0.0),
        ],
        transformers=[],
        generators=[],
        loads=[],
    )
    executor = StudyExecutor(cache=None)
    return executor._build_system_from_spec(spec)


def test_cable_sizing_rejected_when_flag_disabled(cable_system, monkeypatch):
    """Fail-Closed Test 1: Flag disabled (default) must raise SpecializedExecutionUnavailableError."""
    monkeypatch.setenv("FEATURE_FLAG_CABLE_SIZING", "false")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "ampacity",
        "cross_section_mm2": 70,
        "conductor_material": "Cu",
    }

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("cable_sizing", cable_system, params)

    assert exc_info.value.study_type == "cable_sizing"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
    assert "disabled" in str(exc_info.value).lower()


def test_cable_sizing_rejected_when_empty_parameters(cable_system):
    """Fail-Closed Test 2: Empty parameters must raise SpecializedExecutionUnavailableError."""
    executor = StudyExecutor(cache=None)

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("cable_sizing", cable_system, {})

    assert exc_info.value.study_type == "cable_sizing"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"


def test_cable_sizing_rejected_when_system_missing():
    """Fail-Closed Test 3: Missing system model must raise ValueError."""
    executor = StudyExecutor(cache=None)
    params = {
        "analysis_type": "ampacity",
        "cross_section_mm2": 70,
    }

    with pytest.raises(ValueError) as exc_info:
        executor._dispatch("cable_sizing", None, params)

    assert "requires a 'system'" in str(exc_info.value)


def test_cable_sizing_positive_execution_ampacity(cable_system, monkeypatch):
    """Positive Test 1: With flag enabled, executes IEC 60364 ampacity calculation."""
    monkeypatch.setenv("FEATURE_FLAG_CABLE_SIZING", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "ampacity",
        "cross_section_mm2": 70,
        "conductor_material": "Cu",
        "insulation": "XLPE",
        "installation_method": "in_air",
        "ambient_temp_C": 30.0,
        "n_circuits": 1,
    }

    raw = executor._dispatch("cable_sizing", cable_system, params)

    assert "ampacity" in raw
    amp_data = raw["ampacity"]
    assert amp_data.get("derated_ampacity_A") > 0.0
    assert amp_data.get("base_ampacity_A") == 278.0

    provenance = raw.get("provenance", {})
    assert provenance.get("standard") == "IEC 60364"
    assert provenance.get("lifecycle") == "pilot"
    assert provenance.get("handler") == "agents.cable_sizing_agent.CableSizingAgent"


def test_cable_sizing_positive_execution_recommendation(cable_system, monkeypatch):
    """Positive Test 2: With flag enabled, executes optimal cable selection and voltage drop check."""
    monkeypatch.setenv("FEATURE_FLAG_CABLE_SIZING", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "recommend",
        "load_current_A": 150.0,
        "cable_length_m": 80.0,
        "system_voltage_V": 400.0,
        "power_factor": 0.85,
        "conductor_material": "Cu",
        "insulation": "XLPE",
        "installation_method": "in_air",
        "ambient_temp_C": 35.0,
        "max_vdrop_percent": 5.0,
    }

    raw = executor._dispatch("cable_sizing", cable_system, params)

    assert "recommendation" in raw
    rec_data = raw["recommendation"]
    assert rec_data.get("recommended_cross_section_mm2") == 185
    assert rec_data.get("recommendation") == "Cable selected successfully"

    provenance = raw.get("provenance", {})
    assert provenance.get("standard") == "IEC 60364"
    assert provenance.get("lifecycle") == "pilot"
