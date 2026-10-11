"""tests/test_scada_acceptance.py — Dual Acceptance & Fail-Closed Gate Suite for SCADA Integration (PILOT).

Validates:
1. Fail-closed gate: Execution rejected with SpecializedExecutionUnavailableError when flag is OFF.
2. Parameter validation: Rejection when empty parameters provided to native dispatch.
3. System requirement: Rejection when system model is missing.
4. Positive execution: IEC 61850 data model mapping, measurement telemetry, and bus mapping
   when flag is enabled, returning IEC 61850 metrics and pilot provenance.
"""

from __future__ import annotations

import pytest

from core.exceptions import SpecializedExecutionUnavailableError
from core_model.specs import BusSpec, LineSpec, SystemSpec
from services.study_executor import StudyExecutor


@pytest.fixture(name="scada_system")
def fixture_scada_system():
    """Create a 3-bus substation test system for SCADA integration."""
    spec = SystemSpec(
        base_mva=100.0,
        buses=[
            BusSpec(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=13.8),
            BusSpec(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=13.8),
            BusSpec(bus_id=3, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=13.8),
        ],
        lines=[
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.01, x1=0.04, bshunt1=0.0),
            LineSpec(line_id=2, from_bus_id=2, to_bus_id=3, r1=0.02, x1=0.05, bshunt1=0.0),
        ],
        transformers=[],
        generators=[],
        loads=[],
    )
    executor = StudyExecutor(cache=None)
    return executor._build_system_from_spec(spec)


def test_scada_rejected_when_flag_disabled(scada_system, monkeypatch):
    """Fail-Closed Test 1: Flag disabled (default) must raise SpecializedExecutionUnavailableError."""
    monkeypatch.setenv("FEATURE_FLAG_SCADA", "false")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "connect",
        "scada_server": "substation1.grid.local",
        "scada_port": 102,
    }

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("scada", scada_system, params)

    assert exc_info.value.study_type == "scada"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"
    assert "disabled" in str(exc_info.value).lower()


def test_scada_rejected_when_empty_parameters(scada_system):
    """Fail-Closed Test 2: Empty parameters must raise SpecializedExecutionUnavailableError."""
    executor = StudyExecutor(cache=None)

    with pytest.raises(SpecializedExecutionUnavailableError) as exc_info:
        executor._dispatch("scada", scada_system, {})

    assert exc_info.value.study_type == "scada"
    assert exc_info.value.code == "SPECIALIZED_EXECUTION_UNAVAILABLE"


def test_scada_rejected_when_system_missing():
    """Fail-Closed Test 3: Missing system model must raise ValueError."""
    executor = StudyExecutor(cache=None)
    params = {
        "analysis_type": "connect",
        "scada_server": "substation1.grid.local",
    }

    with pytest.raises(ValueError) as exc_info:
        executor._dispatch("scada", None, params)

    assert "requires a 'system'" in str(exc_info.value)


def test_scada_positive_execution_connect(scada_system, monkeypatch):
    """Positive Test 1: With flag enabled, executes IEC 61850 SCADA connection protocol."""
    monkeypatch.setenv("FEATURE_FLAG_SCADA", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "connect",
        "scada_server": "substation1.grid.local",
        "scada_port": 102,
        "scada_protocol": "IEC61850",
    }

    raw = executor._dispatch("scada", scada_system, params)

    assert "connection" in raw
    conn = raw["connection"]
    assert conn.get("server") == "substation1.grid.local"
    assert conn.get("protocol") == "IEC61850"

    provenance = raw.get("provenance", {})
    assert provenance.get("standard") == "IEC 61850"
    assert provenance.get("lifecycle") == "pilot"
    assert provenance.get("handler") == "agents.scada_agent.SCADAAgent"


def test_scada_positive_execution_iec61850_model(scada_system, monkeypatch):
    """Positive Test 2: With flag enabled, retrieves IEC 61850 logical node data model."""
    monkeypatch.setenv("FEATURE_FLAG_SCADA", "true")
    executor = StudyExecutor(cache=None)

    params = {
        "analysis_type": "iec61850_model",
        "logical_device": "LD0",
    }

    raw = executor._dispatch("scada", scada_system, params)

    assert "iec61850_model" in raw
    model = raw["iec61850_model"]
    assert "logical_nodes" in model
    ln_names = [ln.get("logical_node") for ln in model["logical_nodes"]]
    assert "MMXU" in ln_names
    assert "XCBR" in ln_names

    provenance = raw.get("provenance", {})
    assert provenance.get("standard") == "IEC 61850"
    assert provenance.get("lifecycle") == "pilot"
