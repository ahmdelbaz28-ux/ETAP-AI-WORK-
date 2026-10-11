"""
Unit and integration tests for Digital Twin PILOT mode (silent-observer).
==========================================================================
Verifies:
(a) Drift thresholds: MDI < 0.05 -> pass, MDI > 0.15 -> drift flag + suggestion
(b) Stale data: timestamp age > 30s OR quality BAD -> {"success": False, "reason": "STALE_DATA"}
(c) Multi-tenant isolation: Tenant A writes are strictly invisible to Tenant B
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from core_model.specs import BusSpec, LineSpec, SystemSpec
from digital_twin.time_series_store import TimeSeriesStore
from digital_twin.topology_store import TopologyStore
from services.study_executor import StudyExecutor


@pytest.fixture
def test_system():
    spec = SystemSpec(
        base_mva=100.0,
        buses=[
            BusSpec(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=11.0),
            BusSpec(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=11.0),
        ],
        lines=[
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.01, x1=0.05, bshunt1=0.0),
        ],
    )
    return StudyExecutor()._build_system_from_spec(spec)


def test_pilot_drift_thresholds(test_system):
    """(a) Test drift thresholds in PILOT mode: MDI < 0.05 -> pass, MDI > 0.15 -> drift flag + suggestion."""
    executor = StudyExecutor()

    with patch("api.feature_flags.is_strict_feature_enabled", return_value=True):
        # Case 1: Minimal deviation (MDI < 0.05 -> pass, no drift flag)
        now = time.time()
        params_pass = {
            "system": test_system,
            "predicted_values": [1.0, 1.0, 1.0],
            "measured_values": [1.005, 0.998, 1.002],
            "scada_snapshot": {
                "timestamp": now,
                "readings": [{"tag": "B1/V", "value": 1.005, "quality": "GOOD"}],
            },
            "tenant_id": "tenant_alpha",
            "trace_id": "trace_pass_001",
        }
        res_pass = executor._dispatch("digital_twin", test_system, params_pass)
        assert res_pass["success"] is True
        assert res_pass["mdi"] < 0.05
        assert res_pass["drift_flags"] == []
        assert res_pass["calibration_suggestion"] == ""
        assert res_pass["provenance"]["lifecycle"] == "pilot"
        assert res_pass["provenance"]["tenant_id"] == "tenant_alpha"

        # Case 2: Significant deviation (MDI > 0.15 -> drift flag + calibration suggestion)
        params_drift = {
            "system": test_system,
            "predicted_values": [1.0, 1.0, 1.0],
            "measured_values": [1.30, 0.75, 1.25],
            "scada_snapshot": {
                "timestamp": now,
                "readings": [{"tag": "B1/V", "value": 1.30, "quality": "GOOD"}],
            },
            "tenant_id": "tenant_alpha",
            "trace_id": "trace_drift_002",
        }
        res_drift = executor._dispatch("digital_twin", test_system, params_drift)
        assert res_drift["success"] is True
        assert res_drift["mdi"] > 0.15
        assert "drift" in res_drift["drift_flags"]
        assert len(res_drift["calibration_suggestion"]) > 0
        assert "calibration recommended" in res_drift["calibration_suggestion"].lower()


def test_pilot_stale_data(test_system):
    """(b) Test stale data rejection: timestamp age > 30s OR quality BAD -> {"success": False, "reason": "STALE_DATA"}."""
    executor = StudyExecutor()

    with patch("api.feature_flags.is_strict_feature_enabled", return_value=True):
        # Case 1: Stale timestamp (age = 45s > 30s threshold)
        stale_time = time.time() - 45.0
        params_stale_ts = {
            "system": test_system,
            "predicted_values": [1.0, 1.0],
            "measured_values": [1.0, 1.0],
            "scada_snapshot": {
                "timestamp": stale_time,
                "readings": [{"tag": "B1/V", "value": 1.0, "quality": "GOOD"}],
            },
            "tenant_id": "tenant_alpha",
        }
        res_stale = executor._dispatch("digital_twin", test_system, params_stale_ts)
        assert res_stale["success"] is False
        assert res_stale["reason"] == "STALE_DATA"

        # Case 2: BAD quality reading in measurements list
        now = time.time()
        params_bad_quality = {
            "system": test_system,
            "predicted_values": [1.0, 1.0],
            "measured_values": [1.0, 1.0],
            "measurements": [
                {"tag": "B1/V", "value": 1.0, "quality_code": "BAD", "timestamp": now}
            ],
            "tenant_id": "tenant_alpha",
        }
        res_bad = executor._dispatch("digital_twin", test_system, params_bad_quality)
        assert res_bad["success"] is False
        assert res_bad["reason"] == "STALE_DATA"


def test_pilot_tenant_isolation():
    """(c) Test multi-tenant isolation: Tenant A writes are completely invisible to Tenant B."""
    ts_store = TimeSeriesStore()
    topo_store = TopologyStore()

    tenant_a = "tenant_utility_a"
    tenant_b = "tenant_utility_b"

    now = time.time()

    # 1. Time-series append for Tenant A
    ts_store.append(tenant_a, now, "voltage", 1.02)
    ts_store.append(tenant_a, now + 5.0, "voltage", 1.03)

    # 2. Topology update for Tenant A
    topo_store.set_breaker_state(tenant_a, "CB-101", "OPEN")

    # 3. Verify Tenant A can read its data
    a_series = ts_store.get_range(tenant_a, "voltage", now - 10, now + 10)
    assert len(a_series) == 2
    assert topo_store.get_breaker_state(tenant_a, "CB-101") == "OPEN"

    # 4. Verify Tenant B sees nothing (strict multi-tenant isolation)
    b_series = ts_store.get_range(tenant_b, "voltage", now - 10, now + 10)
    assert b_series == []

    b_breaker = topo_store.get_breaker_state(tenant_b, "CB-101")
    assert b_breaker is None

    b_topo = topo_store.get_tenant_topology(tenant_b)
    assert b_topo == {}
