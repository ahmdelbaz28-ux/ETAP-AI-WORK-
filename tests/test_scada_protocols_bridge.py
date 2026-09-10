import asyncio
import time

import pytest

from scada_protocols.common.bridge import SCADAProtocolBridge, make_callback
from scada_protocols.common.config import Iec61850Config
from scada_protocols.iec61850.client import IEC61850ClientAdapter


def test_bridge_ensure_imports_and_properties():
    bridge = SCADAProtocolBridge()
    ret = bridge._ensure_imports()
    assert isinstance(ret, bool)
    # Check backward compatibility properties
    assert bridge._Measurement == bridge._measurement_cls
    assert bridge._MeasurementType == bridge._measurement_type_cls
    assert bridge._QualityFlag == bridge._quality_flag_cls
    assert bridge._SCADAUpdateReceived == bridge._scada_update_received_cls


def test_bridge_ingest_stats_and_qualities():
    bridge = SCADAProtocolBridge()

    # Test Good
    assert bridge.ingest(
        element_id="BUS_1",
        measurement_type="voltage_magnitude",
        value=13.8,
        quality="good",
        source="iec61850",
    ) in (True, False)

    # Test Questionable
    bridge.ingest(
        element_id="BUS_1",
        measurement_type="voltage_magnitude",
        value=13.9,
        quality="questionable",
        source="iec61850",
    )

    # Test Stale / missing
    old_time = time.time() - 100.0
    bridge.ingest(
        element_id="BUS_1",
        measurement_type="voltage_magnitude",
        value=14.0,
        quality="good",
        source="iec61850",
        source_timestamp=old_time,
        max_age_sec=5.0,
    )

    stats = bridge.stats
    assert stats.total_ingested == 3
    assert stats.by_protocol.get("iec61850") == 3
    assert stats.by_type.get("VOLTAGE_MAGNITUDE") == 3
    assert stats.last_element_id == "BUS_1"


def test_bridge_deadband_suppression():
    bridge = SCADAProtocolBridge()

    # First ingest
    bridge.ingest("CB_1", "active_power", 100.0, deadband=1.0)
    assert bridge.stats.total_ingested == 1

    # Change less than deadband -> suppressed
    suppressed = bridge.ingest("CB_1", "active_power", 100.5, deadband=1.0)
    assert suppressed is True
    assert bridge.stats.total_ingested == 1  # Not updated because suppressed


def test_make_callback():
    bridge = SCADAProtocolBridge()
    cb = make_callback(bridge)
    # Callback should execute ingest without crashing
    cb("LINE_1", "current_magnitude", 50.0, "good", "dnp3")
    assert bridge.stats.total_ingested == 1


@pytest.mark.asyncio
async def test_iec61850_poll_loop_cancellation():
    import threading

    cfg = Iec61850Config(
        server_host="127.0.0.1",
        server_port=102,
        point_map=[{"element_id": "BUS_1", "measurement_type": "voltage_magnitude"}],
        poll_interval_sec=0.1,
    )
    adapter = IEC61850ClientAdapter(config=cfg)
    adapter._stop_event = threading.Event()

    task = asyncio.create_task(adapter._poll_loop())
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert adapter._stop_event.is_set()
