"""tests/test_earth_grid_acceptance.py — Dual Acceptance & Fail-Closed Gate Suite for Earth Grid (PILOT).

Validates:
1. Fail-closed gate: Execution rejected with SpecializedExecutionUnavailableError when flag is OFF.
2. Parameter validation: Rejection when empty parameters provided to native dispatch.
3. System requirement: Rejection when system model is missing.
4. Positive execution: IEEE 80 substation ground grid design, mesh/step voltages, and safety verification
   when flag is enabled, returning IEEE 80 metrics and pilot provenance.
"""

from __future__ import annotations

import pytest

from core.exceptions import SpecializedExecutionUnavailableError
from core_model.specs import BusSpec, LineSpec, SystemSpec
from services.study_executor import StudyExecutor


@pytest.fixture(name="grid_system")
def fixture_grid_system():
    """Create a 2-bus substation test system."""
    spec = SystemSpec(
        base_mva=50.0,
        buses=[
            BusSpec(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=132.0),
            BusSpec(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=132.0),
        ],
        lines=[
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.02, x1=0.08, bshunt1=0.0),
        ],
        transformers=[],
        generators=[],
        loads=[],
    )
    executor = StudyExecutor(cache=None)
    return executor._build_system_from_spec(spec)


def test_earth_grid_rejected_when_flag_disabled(grid_system, monkeypatch):
    """Fail-Closed Test 1: Flag disabled (default) must raise SpecializedExecutionUnavailableError."""
    monkeypatch.setenv("FEATURE_FLAG_EARTH_GRID", "false")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "design",
        "rho_soil": 100.0,
        "Ig_max": 5000.0,
        "grid_length_m": 50.0,
        "grid_width_m": 40.0,
    }

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("earth_grid", grid_system, params)

    assert exc_info.value.study_type == "earth_grid"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
    assert "disabled" in str(exc_info.value).lower()


def test_earth_grid_rejected_when_empty_parameters(grid_system):
    """Fail-Closed Test 2: Empty parameters must raise SpecializedExecutionUnavailableError."""
    executor = StudyExecutor(cache=None)

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("earth_grid", grid_system, {})

    assert exc_info.value.study_type == "earth_grid"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"


def test_earth_grid_rejected_when_system_missing():
    """Fail-Closed Test 3: Missing system model must raise ValueError."""
    executor = StudyExecutor(cache=None)
    params = {
        "analysis_type": "design",
        "rho_soil": 100.0,
    }

    with pytest.raises(ValueError) as exc_info:
        executor._dispatch("earth_grid", None, params)

    assert "requires a 'system'" in str(exc_info.value)


def test_earth_grid_positive_execution_design(grid_system, monkeypatch):
    """Positive Test 1: With flag enabled, executes IEEE 80 ground grid design and safety check."""
    monkeypatch.setenv("FEATURE_FLAG_EARTH_GRID", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "design",
        "rho_soil": 100.0,
        "Ig_max": 5000.0,
        "grid_length_m": 60.0,
        "grid_width_m": 50.0,
        "n_rods": 8,
        "rod_length_m": 3.0,
        "rho_surface": 2500.0,
        "hs_surface_m": 0.15,
        "fault_duration_s": 0.5,
    }

    raw = executor._dispatch("earth_grid", grid_system, params)

    assert "grid_design" in raw
    gd = raw["grid_design"]
    assert "mesh_voltage" in gd
    assert "step_voltage" in gd
    assert "touch_voltage" in gd
    assert gd["touch_voltage"]["R_grid_ohm"] > 0.0

    provenance = raw.get("provenance", {})
    assert provenance.get("standard") == "IEEE 80"
    assert provenance.get("lifecycle") == "pilot"
    assert provenance.get("handler") == "agents.earth_grid_agent.EarthGridAgent"


def test_earth_grid_positive_execution_mesh_voltage(grid_system, monkeypatch):
    """Positive Test 2: With flag enabled, executes mesh voltage calculation per IEEE 80."""
    monkeypatch.setenv("FEATURE_FLAG_EARTH_GRID", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "mesh_voltage",
        "rho_soil": 80.0,
        "Ig_max": 4000.0,
        "grid_length_m": 50.0,
        "grid_width_m": 40.0,
        "n_rods": 4,
        "rod_length_m": 3.0,
    }

    raw = executor._dispatch("earth_grid", grid_system, params)

    assert "mesh_voltage" in raw
    mv = raw["mesh_voltage"]
    assert mv.get("E_mesh_V") > 0.0
    assert mv.get("K_m") > 0.0

    provenance = raw.get("provenance", {})
    assert provenance.get("standard") == "IEEE 80"
    assert provenance.get("lifecycle") == "pilot"
