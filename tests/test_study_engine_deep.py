"""
Unit & Integration Test Suite for StudyEngine.
"""

import pytest

from core.study_engine import (
    StudyEngine,
    StudyResult,
    StudyStatus,
    study_engine,
)


@pytest.fixture
def engine():
    return StudyEngine()


@pytest.mark.asyncio
async def test_dry_run_execution(engine):
    res = await engine.execute(
        study_type="load_flow",
        parameters={"max_iterations": 20},
        dry_run=True,
    )
    assert isinstance(res, StudyResult)
    assert res.status == StudyStatus.DRY_RUN
    assert res.success is True
    assert "IEEE 3002.7" in res.standards_compliance


@pytest.mark.asyncio
async def test_arc_flash_calculation(engine):
    res = await engine.execute(
        study_type="arc_flash",
        parameters={
            "voltage_kv": 0.48,
            "fault_current_ka": 25.0,
            "clearing_time_s": 0.08,
            "working_distance_mm": 457.2,
            "arc_gap_mm": 25.0,
        },
    )
    assert res.success is True
    assert res.status == StudyStatus.COMPLETED
    assert "incident_energy_cal_cm2" in res.data
    assert "ppe_category" in res.data
    assert "arc_flash_boundary_mm" in res.data
    assert "IEEE 1584" in res.standards_compliance[0]


@pytest.mark.asyncio
async def test_cable_sizing_calculation(engine):
    res = await engine.execute(
        study_type="cable_sizing",
        parameters={
            "load_current_a": 120.0,
            "length_m": 75.0,
            "voltage_v": 400.0,
        },
    )
    assert res.success is True
    assert res.status == StudyStatus.COMPLETED
    assert "selected_cross_section_mm2" in res.data
    assert "voltage_drop_percent" in res.data
    assert "IEC 60364" in res.standards_compliance[0]


@pytest.mark.asyncio
async def test_short_circuit_fallback(engine):
    res = await engine.execute(
        study_type="short_circuit",
        parameters={
            "voltage_kv": 11.0,
            "ik_ss_ka": 31.5,
            "fault_bus": "SWBD_MAIN",
            "rx_ratio": 0.1,
            "allow_single_bus_synthesis": True,
        },
    )
    assert res.success is True
    assert res.data["ik_initial_ka"] == 31.5
    assert res.data["ip_peak_ka"] > 31.5


@pytest.mark.asyncio
async def test_arc_flash_missing_param_fails_closed(engine):
    """Ensure silent injection of default voltage/current/distance/gap is rejected."""
    res = await engine.execute(
        study_type="arc_flash",
        parameters={
            "fault_current_ka": 25.0,
            "clearing_time_s": 0.08,
            # voltage_kv, working_distance_mm, arc_gap_mm omitted
        },
    )
    assert res.success is False
    assert res.status == StudyStatus.FAILED
    assert "Missing required arc flash parameter" in res.data["error"]


@pytest.mark.asyncio
async def test_short_circuit_unflagged_synthesis_fails_closed(engine):
    """Ensure synthesizing a single-bus network without allow_single_bus_synthesis flag is rejected."""
    res = await engine.execute(
        study_type="short_circuit",
        parameters={
            "voltage_kv": 11.0,
            "ik_ss_ka": 31.5,
            "fault_bus": "SWBD_MAIN",
            "rx_ratio": 0.1,
            # allow_single_bus_synthesis omitted
        },
    )
    assert res.success is False
    assert res.status == StudyStatus.FAILED
    assert "allow_single_bus_synthesis" in res.data["error"]


@pytest.mark.asyncio
async def test_error_handling_invalid_params(engine):
    res = await engine.execute(
        study_type="load_flow",
        parameters={"system": "not_a_valid_system_object"},
        dry_run=False,
    )
    assert res.success is False
    assert res.status == StudyStatus.FAILED
    assert "error" in res.data
