"""
scada_protocols.tests.test_iec61850_no_fabrication
=================================================
Regression test suite guaranteeing zero fabricated or default measurements
(no hardcoded 1.0 or 0.0 values, no fake 'good' quality) in IEC 61850 telemetry.
"""

from unittest.mock import MagicMock, patch

import pytest

from scada_protocols.common.config import Iec61850Config
from scada_protocols.iec61850.client import IEC61850ClientAdapter


def _create_test_config() -> Iec61850Config:
    return Iec61850Config(
        enabled=True,
        server_host="192.168.1.50",
        server_port=102,
        ied_name="SEL_411L",
        point_map=[
            {
                "element_id": "BUS_1",
                "measurement_type": "voltage_magnitude",
                "logical_node": "MMXU1",
                "data_attribute": "Vol.mag.f",
                "unit": "kV",
            },
            {
                "element_id": "LINE_1",
                "measurement_type": "current_magnitude",
                "logical_node": "MMXU2",
                "data_attribute": "Amp.mag.f",
                "unit": "A",
            },
        ],
    )


def test_iec61850_mock_client_reads_real_values_from_connection():
    """When a real/mocked MMS client with read_value is connected, measurements come from it."""
    cfg = _create_test_config()
    adapter = IEC61850ClientAdapter(config=cfg)

    mock_conn = MagicMock()
    mock_conn.read_value.side_effect = lambda ln, attr: (13.85, "good") if ln == "MMXU1" else (412.3, "questionable")

    adapter._active_connections["ied_primary"] = mock_conn

    # Health check must pass when thread or connection exists
    with patch.object(adapter, "health_check", return_value=True):
        res = adapter.read_measurements()

    assert res["success"] is True
    assert res["measurement_count"] == 2
    meas = {m["element_id"]: m for m in res["measurements"]}

    assert meas["BUS_1"]["value"] == 13.85
    assert meas["BUS_1"]["quality"] == "good"
    assert meas["LINE_1"]["value"] == 412.3
    assert meas["LINE_1"]["quality"] == "questionable"
    assert mock_conn.read_value.call_count == 2


def test_iec61850_missing_library_raises_importerror():
    """Fail-closed: without iec61850datamodel or py61850, start_client raises ImportError."""
    cfg = _create_test_config()
    adapter = IEC61850ClientAdapter(config=cfg)

    with patch.dict("sys.modules", {"iec61850datamodel": None, "py61850": None}):
        with pytest.raises(ImportError) as exc_info:
            adapter.start_client()
        assert "Cannot start IEC 61850 client" in str(exc_info.value)


def test_iec61850_no_fabrication_regression():
    """Regression test: read_measurements and _dispatch_point NEVER emit fabricated 1.0 or 0.0 values."""
    cfg = _create_test_config()
    emitted = []

    def on_meas_cb(**kwargs):
        emitted.append(kwargs)

    adapter = IEC61850ClientAdapter(config=cfg, on_measurement=on_meas_cb)

    # 1. read_measurements with health_check True but no active MMS client must raise ConnectionError
    with patch.object(adapter, "health_check", return_value=True):
        with pytest.raises(ConnectionError) as exc_info:
            adapter.read_measurements()
        assert "REAL_INTEGRATION_UNAVAILABLE" in str(exc_info.value)

    # 2. _dispatch_point without active MMS connection must emit NOTHING (no 0.0, no fake good quality)
    assert len(emitted) == 0
    for pt in cfg.point_map:
        adapter._dispatch_point(pt)
    assert len(emitted) == 0, f"Expected zero emitted points without real connection, but got {emitted}"
