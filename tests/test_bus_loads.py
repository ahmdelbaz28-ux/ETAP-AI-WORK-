"""
Regression Test: Bus Load Equivalence & Duplicate Load Protection (Q2)
======================================================================

Tests:
1. 3-bus network with loads defined inside bus fields (load_power_real / load_power_imag).
2. Same network with loads defined in separate loads array (loads: [{load_id, bus_id, p_mw, q_mvar}]).
   Verifies that both paths produce identical numerical solutions within 1e-6.
3. Sending loads both in bus fields and in separate loads array for the same bus
   is rejected fail-closed with 422 (no double-counting, no silent ignoring).
"""

import math

import pytest
from pydantic import ValidationError

from core_model.specs import BusSpec, LineSpec, LoadSpec, StudyRequest, SystemSpec
from services.study_executor import StudyExecutor


def build_3bus_network_with_bus_loads() -> SystemSpec:
    """3-bus network with load defined on bus 2 and bus 3 fields."""
    buses = [
        BusSpec(bus_id=1, bus_type="slack", voltage_magnitude=1.05, voltage_angle=0.0),
        BusSpec(bus_id=2, bus_type="pq", voltage_magnitude=1.0, voltage_angle=0.0, load_power_real=0.3, load_power_imag=0.1),
        BusSpec(bus_id=3, bus_type="pq", voltage_magnitude=1.0, voltage_angle=0.0, load_power_real=0.2, load_power_imag=0.05),
    ]
    lines = [
        LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.02, x1=0.08),
        LineSpec(line_id=2, from_bus_id=2, to_bus_id=3, r1=0.02, x1=0.08),
    ]
    return SystemSpec(base_mva=100.0, buses=buses, lines=lines)


def build_3bus_network_with_separate_loads() -> SystemSpec:
    """Same 3-bus network with loads defined in separate loads array (in MW/MVAr on base_mva=100)."""
    buses = [
        BusSpec(bus_id=1, bus_type="slack", voltage_magnitude=1.05, voltage_angle=0.0),
        BusSpec(bus_id=2, bus_type="pq", voltage_magnitude=1.0, voltage_angle=0.0),
        BusSpec(bus_id=3, bus_type="pq", voltage_magnitude=1.0, voltage_angle=0.0),
    ]
    lines = [
        LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.02, x1=0.08),
        LineSpec(line_id=2, from_bus_id=2, to_bus_id=3, r1=0.02, x1=0.08),
    ]
    loads = [
        LoadSpec(load_id=1, bus_id=2, p_mw=30.0, q_mvar=10.0),
        LoadSpec(load_id=2, bus_id=3, p_mw=20.0, q_mvar=5.0),
    ]
    return SystemSpec(base_mva=100.0, buses=buses, lines=lines, loads=loads)


@pytest.mark.asyncio
async def test_bus_loads_vs_separate_loads_equivalence():
    """Verify that both load modeling paths produce identical voltage profiles."""
    executor = StudyExecutor()

    # Path 1: loads inside bus fields
    spec_bus_loads = build_3bus_network_with_bus_loads()
    req1 = StudyRequest(study_type="load_flow", system=spec_bus_loads)
    res1 = await executor.execute(req1)
    assert res1.success is True, f"Bus loads run failed: {res1.errors}"
    v1 = res1.result["bus_voltages"]

    # Path 2: loads in separate array
    spec_separate_loads = build_3bus_network_with_separate_loads()
    req2 = StudyRequest(study_type="load_flow", system=spec_separate_loads)
    res2 = await executor.execute(req2)
    assert res2.success is True, f"Separate loads run failed: {res2.errors}"
    v2 = res2.result["bus_voltages"]

    # Both must match exactly
    for bid in ("1", "2", "3"):
        v1_c = complex(v1[bid]["re"], v1[bid]["im"])
        v2_c = complex(v2[bid]["re"], v2[bid]["im"])
        assert abs(v1_c - v2_c) < 1e-6, f"Bus {bid} mismatch between load paths: {v1_c} vs {v2_c}"

    # Verify voltage drop occurs from load
    assert abs(complex(v1["2"]["re"], v1["2"]["im"])) < 1.05
    assert abs(complex(v1["3"]["re"], v1["3"]["im"])) < abs(complex(v1["2"]["re"], v1["2"]["im"]))


def test_duplicate_load_definition_rejected():
    """Verify that specifying loads in both places for the same bus raises ValidationError."""
    buses = [
        BusSpec(bus_id=1, bus_type="slack", voltage_magnitude=1.0, voltage_angle=0.0),
        BusSpec(bus_id=2, bus_type="pq", voltage_magnitude=1.0, voltage_angle=0.0, load_power_real=0.3, load_power_imag=0.1),
    ]
    lines = [
        LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.02, x1=0.08),
    ]
    loads = [
        LoadSpec(load_id=1, bus_id=2, p_mw=30.0, q_mvar=10.0),
    ]

    with pytest.raises(ValidationError) as excinfo:
        SystemSpec(base_mva=100.0, buses=buses, lines=lines, loads=loads)

    err_str = str(excinfo.value)
    assert "Duplicate load definition is rejected" in err_str or "Bus 2 has load defined both" in err_str
