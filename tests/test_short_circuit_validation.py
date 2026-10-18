"""
Regression Test: Short Circuit Parameter Validation Fail-Closed (R1)
===================================================================

Verifies that short_circuit study with invalid parameters (invalid bus_id,
invalid fault_type) fails cleanly with HTTP 422 and a structured error message
instead of crashing with an uncaught 500 internal server error.
"""

import pytest
from pydantic import ValidationError

from core_model.specs import BusSpec, LineSpec, StudyRequest, SystemSpec
from services.study_executor import StudyExecutor


def build_sample_system():
    buses = [
        BusSpec(bus_id=1, bus_type="slack", voltage_magnitude=1.0, voltage_angle=0.0, base_kv=13.8),
        BusSpec(bus_id=2, bus_type="pq", voltage_magnitude=1.0, voltage_angle=0.0, base_kv=13.8),
    ]
    lines = [
        LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.05, x1=0.2),
    ]
    return SystemSpec(base_mva=100.0, buses=buses, lines=lines)


def test_short_circuit_invalid_bus_id_raises_validation_error():
    """Verify invalid bus_id in parameters raises Pydantic ValidationError (HTTP 422)."""
    sys_spec = build_sample_system()
    with pytest.raises(ValidationError) as exc_info:
        StudyRequest(
            study_type="short_circuit",
            system=sys_spec,
            parameters={"bus_id": 999, "fault_type": "three_phase"},
        )
    err = str(exc_info.value)
    assert "bus_id 999 specified in parameters not found in system buses" in err


def test_short_circuit_invalid_fault_type_raises_validation_error():
    """Verify invalid fault_type in parameters raises Pydantic ValidationError (HTTP 422)."""
    sys_spec = build_sample_system()
    with pytest.raises(ValidationError) as exc_info:
        StudyRequest(
            study_type="short_circuit",
            system=sys_spec,
            parameters={"bus_id": 1, "fault_type": "quantum_fluctuation"},
        )
    err = str(exc_info.value)
    assert "Invalid fault_type 'quantum_fluctuation'" in err


@pytest.mark.asyncio
async def test_short_circuit_valid_runs_successfully():
    """Verify valid short_circuit parameters run cleanly and return fault results."""
    sys_spec = build_sample_system()
    req = StudyRequest(
        study_type="short_circuit",
        system=sys_spec,
        parameters={"bus_id": 1, "fault_type": "three_phase"},
    )
    executor = StudyExecutor()
    res = await executor.execute(req)
    assert res.success is True
    assert "fault_current" in str(res.result).lower() or "current" in str(res.result).lower()
