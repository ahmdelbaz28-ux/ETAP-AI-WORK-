"""Tests for PhysicalOperatingBounds and study version hash storage."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.pe_stamp import _compute_data_hash
from api.study_versions import StudyVersion, VersionResponse
from core_model.specs import PhysicalOperatingBounds
from services.study_executor import StudyExecutor


def test_physical_operating_bounds_defaults():
    bounds = PhysicalOperatingBounds()
    assert bounds.v_min_pu == 0.90
    assert bounds.v_max_pu == 1.10
    assert bounds.pf_min == 0.70


def test_physical_operating_bounds_valid_custom():
    bounds = PhysicalOperatingBounds(v_min_pu=0.95, v_max_pu=1.05, pf_min=0.85)
    assert bounds.v_min_pu == 0.95
    assert bounds.v_max_pu == 1.05
    assert bounds.pf_min == 0.85


def test_physical_operating_bounds_out_of_range():
    with pytest.raises(ValidationError):
        PhysicalOperatingBounds(v_min_pu=0.40)  # ge=0.5

    with pytest.raises(ValidationError):
        PhysicalOperatingBounds(v_max_pu=1.60)  # le=1.5

    with pytest.raises(ValidationError):
        PhysicalOperatingBounds(pf_min=-0.1)  # ge=0.0


def test_study_executor_pre_flight_voltage_bounds():
    executor = StudyExecutor()
    bounds = PhysicalOperatingBounds(v_min_pu=0.95, v_max_pu=1.05)

    # Valid within bounds
    buses_valid = [{"bus_id": 1, "voltage_magnitude": 1.0}]
    assert executor._pre_flight_voltage_bounds(buses_valid, bounds) is None

    # Severely degenerate voltage (<0.5) must error
    buses_degenerate = [{"bus_id": 1, "voltage_magnitude": 0.4}]
    res = executor._pre_flight_voltage_bounds(buses_degenerate, bounds)
    assert res is not None
    assert "out of realistic range" in res["error"]

    # In operating_bounds via _pre_flight_check
    sys_valid = {
        "base_mva": 100.0,
        "buses": [
            {"bus_id": 1, "voltage_magnitude": 1.0},
            {"bus_id": 2, "voltage_magnitude": 1.0},
        ],
        "lines": [{"line_id": "L1", "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05}],
        "operating_bounds": {"v_min_pu": 0.92, "v_max_pu": 1.08, "pf_min": 0.80},
    }
    assert executor._pre_flight_check(sys_valid) is None

    # Invalid operating_bounds payload
    sys_invalid_bounds = {
        "base_mva": 100.0,
        "buses": [
            {"bus_id": 1, "voltage_magnitude": 1.0},
            {"bus_id": 2, "voltage_magnitude": 1.0},
        ],
        "lines": [{"line_id": "L1", "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05}],
        "operating_bounds": {"v_min_pu": 0.20},
    }
    res_inv = executor._pre_flight_check(sys_invalid_bounds)
    assert res_inv is not None
    assert "Invalid physical operating bounds" in res_inv["error"]


def test_study_version_hashes_deterministic():
    config = {"study_type": "load_flow", "buses": [{"bus_id": 1}]}
    results = {"converged": True, "losses_mw": 0.12}

    h_cfg = _compute_data_hash(config)
    h_res = _compute_data_hash(results)

    assert len(h_cfg) == 64
    assert len(h_res) == 64
    assert h_cfg == _compute_data_hash(config)

    # Instantiate StudyVersion ORM model
    sv = StudyVersion(
        study_id="st-123",
        project_id="proj-456",
        version_number=1,
        config_snapshot=config,
        results_snapshot=results,
        input_hash=h_cfg,
        output_hash=h_res,
        created_by="user-789",
    )
    assert sv.input_hash == h_cfg
    assert sv.output_hash == h_res

    # VersionResponse schema reflection
    vr = VersionResponse(
        id="v-1",
        study_id="st-123",
        project_id="proj-456",
        version_number=1,
        input_hash=h_cfg,
        output_hash=h_res,
    )
    assert vr.input_hash == h_cfg
    assert vr.output_hash == h_res
