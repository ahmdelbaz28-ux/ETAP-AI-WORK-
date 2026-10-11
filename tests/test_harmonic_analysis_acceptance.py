"""tests/test_harmonic_analysis_acceptance.py — Dual Acceptance & Fail-Closed Gate Suite for Harmonic Analysis (PRODUCTION).

Validates:
1. Fail-closed gate: Execution rejected with SpecializedExecutionUnavailableError when flag is OFF.
2. Parameter validation: Rejection when empty parameters provided to native dispatch.
3. System requirement: Rejection when system model is missing.
4. Positive execution: Full analytical execution when flag is enabled,
   returning IEEE 519-2022 THD/TDD metrics and production provenance.
5. Production eligibility: Deterministic verification of is_production_eligible().
6. Benchmark verification: 3 published IEEE 519 cases passing within <= 3.0% error.
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
    assert provenance.get("lifecycle") == "production"
    assert provenance.get("standard") == "IEEE 519-2022"
    assert provenance.get("handler") == "agents.registry.HarmonicAnalysisAgent"


def test_harmonic_analysis_is_production_eligible():
    """Verify that harmonic_analysis satisfies all criteria in is_production_eligible()."""
    from engine.capability_registry import LifecycleStatus, get_capability_registry

    registry = get_capability_registry()
    cap = registry.get("harmonic_analysis")
    assert cap is not None
    assert cap.lifecycle_status == LifecycleStatus.PRODUCTION
    assert cap.production_supported is True
    assert cap.benchmark_status == "VERIFIED_BENCHMARK"
    assert "IEEE 519-2022" in cap.standards_scope
    assert "benchmark suite" in cap.validation_evidence
    assert cap.is_production_eligible() is True


def test_harmonic_analysis_3_published_benchmarks():
    """Verify that all 3 published IEEE 519-2022 benchmarks pass with error <= 3.0%."""
    from engine.benchmarks.ieee_cases import calculate_ieee_519_harmonic_benchmarks

    bench_results = calculate_ieee_519_harmonic_benchmarks()
    assert bench_results["all_passed"] is True
    assert bench_results["max_error_pct"] <= 3.0
    assert len(bench_results["benchmarks"]) == 3

    for case_id, case in bench_results["benchmarks"].items():
        assert case["passed"] is True
        assert case["error_pct"] <= 3.0
        assert case["computed_thd_pct"] <= 5.0
