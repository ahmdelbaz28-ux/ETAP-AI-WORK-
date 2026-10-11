"""tests/test_harmonic_analysis_acceptance.py — Dual Acceptance & Fail-Closed Gate Suite for Harmonic Analysis (PILOT).

Validates:
1. Fail-closed gate: Execution rejected with SpecializedExecutionUnavailableError when flag is OFF.
2. Parameter validation: Rejection when empty parameters provided to native dispatch.
3. System requirement: Rejection when system model is missing.
4. Positive execution: Full analytical execution when flag is enabled via strict environment override,
   returning IEEE 519-2022 THD/TDD metrics and pilot provenance.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from core.exceptions import SpecializedExecutionUnavailableError
from core_model.specs import BusSpec, LineSpec, SystemSpec
from services.study_executor import StudyExecutor


@pytest.fixture(name="sample_system")
def fixture_sample_system():
    """Create a 2-bus test system (13.8 kV)."""
    spec = SystemSpec(
        base_mva=100.0,
        buses=[
            BusSpec(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=13.8),
            BusSpec(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=13.8),
        ],
        lines=[
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.02, x1=0.08, bshunt1=0.01),
        ],
        transformers=[],
        generators=[],
        loads=[],
    )
    executor = StudyExecutor(cache=None)
    return executor._build_system_from_spec(spec)


def test_harmonic_analysis_rejected_when_flag_disabled(sample_system, monkeypatch):
    """Fail-Closed Test 1: Flag disabled (default) must raise SpecializedExecutionUnavailableError."""
    monkeypatch.setenv("FEATURE_FLAG_HARMONIC_ANALYSIS", "false")
    executor = StudyExecutor(cache=None)

    params = {
        "harmonic_sources": [
            {"source_id": "VFD-1", "bus_id": "2", "harmonic_order": 5, "magnitude_pu": 0.08, "angle_deg": 0.0}
        ],
        "voltage_kv": 13.8,
    }

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("harmonic_analysis", sample_system, params)

    assert exc_info.value.study_type == "harmonic_analysis"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
    assert "disabled" in str(exc_info.value).lower()


def test_harmonic_analysis_rejected_when_empty_parameters(sample_system):
    """Fail-Closed Test 2: Empty parameters must raise SpecializedExecutionUnavailableError."""
    executor = StudyExecutor(cache=None)

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("harmonic_analysis", sample_system, {})

    assert exc_info.value.study_type == "harmonic_analysis"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"


def test_harmonic_analysis_rejected_when_system_missing():
    """Fail-Closed Test 3: Missing system model must raise ValueError."""
    executor = StudyExecutor(cache=None)
    params = {
        "harmonic_sources": [
            {"source_id": "VFD-1", "bus_id": "2", "harmonic_order": 5, "magnitude_pu": 0.08, "angle_deg": 0.0}
        ],
        "voltage_kv": 13.8,
    }

    with pytest.raises(ValueError) as exc_info:
        executor._dispatch("harmonic_analysis", None, params)

    assert "requires a 'system'" in str(exc_info.value)


def test_harmonic_analysis_positive_execution(sample_system, monkeypatch):
    """Positive Test: With flag enabled, executes IEEE 519-2022 harmonic power flow and returns pilot provenance."""
    monkeypatch.setenv("FEATURE_FLAG_HARMONIC_ANALYSIS", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "harmonic_sources": [
            {
                "source_id": "VFD-1",
                "bus_id": "2",
                "harmonic_order": 5,
                "magnitude_pu": 0.08,
                "angle_deg": 0.0,
            },
            {
                "source_id": "VFD-2",
                "bus_id": "2",
                "harmonic_order": 7,
                "magnitude_pu": 0.05,
                "angle_deg": 0.0,
            },
        ],
        "voltage_kv": 13.8,
        "isc_il_ratio": 50.0,
    }

    result = executor._dispatch("harmonic_analysis", sample_system, params)

    assert isinstance(result, dict)
    assert "thd_voltage" in result
    assert "2" in result["thd_voltage"]
    assert result["thd_voltage"]["2"] > 0.0
    assert "compliance_status" in result
    assert "standard" in result
    assert result["standard"] == "IEEE 519-2022"

    provenance = result.get("provenance", {})
    assert provenance.get("lifecycle") == "pilot"
    assert provenance.get("standard") == "IEEE 519-2022"
    assert provenance.get("handler") == "agents.registry.HarmonicAnalysisAgent"
