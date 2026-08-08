"""End-to-end integration test with the real AhmedETAP stack.

This test wires ``scada_protocols`` into the actual ``scada_model.scada_model``
and ``digital_twin.event_bus`` modules from the AhmedETAP repository, then
verifies that:

1. A Modbus server push flows through the bridge into SCADADatabase.
2. The bridge publishes a ``SCADAUpdateReceived`` event on the EventBus.
3. A subscriber registered on the EventBus receives the event.

Requires the AhmedETAP source tree to be on sys.path; skips otherwise.
"""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

import pytest

# Add the AhmedETAP source tree to sys.path so we can import its modules.
ETAP_ROOT = Path("/home/z/my-project/etap-source/ETAP-AI-WORK-")
if not ETAP_ROOT.exists():
    pytest.skip("AhmedETAP source tree not available", allow_module_level=True)

sys.path.insert(0, str(ETAP_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Try to import the real AhmedETAP modules.
try:
    from scada_model.scada_model import (
        SCADADatabase,
        MeasurementType,
        QualityFlag,
    )
    from digital_twin.event_bus import (
        EventBus,
        SCADAUpdateReceived,
        EventType,
    )
    ETAP_AVAILABLE = True
except Exception as _exc:  # pragma: no cover - environment-dependent
    ETAP_AVAILABLE = False
    _IMPORT_ERROR = _exc

pytestmark = pytest.mark.skipif(
    not ETAP_AVAILABLE, reason=f"AhmedETAP modules not importable: {_IMPORT_ERROR if not ETAP_AVAILABLE else ''}"
)

from scada_protocols.common.base import AdapterRole, probe_modbus
from scada_protocols.common.bridge import SCADAProtocolBridge, make_callback
from scada_protocols.common.config import ModbusConfig
from scada_protocols.modbus import ModbusAdapter

pymodbus_available, _ = probe_modbus()


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.mark.skipif(not pymodbus_available, reason="pymodbus not installed")
def test_end_to_end_with_real_etap_stack():
    """Server -> client -> bridge -> SCADADatabase + EventBus subscriber."""
    port = _free_port()

    # --- Set up the real AhmedETAP SCADADatabase + EventBus ---
    db = SCADADatabase(measurement_ttl_seconds=300.0)
    bus = EventBus()

    received_events = []

    def _subscriber(event):
        received_events.append(event)

    bus.subscribe(EventType.SCADA_UPDATE_RECEIVED, _subscriber)

    # --- Build the bridge wired to the real targets ---
    bridge = SCADAProtocolBridge(scada_db=db, event_bus=bus)
    assert bridge.has_scada_db()
    assert bridge.has_event_bus()

    # --- Build the Modbus server + client pair ---
    register_map = [
        {
            "name": "BUS1_V",
            "element_id": "BUS-1",
            "measurement_type": "voltage_magnitude",
            "address": 0,
            "data_type": "float32",
            "scale": 1.0,
            "offset": 0.0,
            "unit": "p.u.",
        }
    ]

    def provider():
        return {"BUS1_V": 1.05}

    server_cfg = ModbusConfig(
        enabled=True,
        role=AdapterRole.SERVER,
        server_host="127.0.0.1",
        server_port=port,
        server_unit_id=1,
        clients=[],
        register_map=register_map,
        scan_rate_ms=200,
    )
    server = ModbusAdapter(
        config=server_cfg,
        role=AdapterRole.SERVER,
        provider=provider,
    )

    client_cfg = ModbusConfig(
        enabled=True,
        role=AdapterRole.CLIENT,
        server_host="127.0.0.1",
        server_port=port,
        server_unit_id=1,
        clients=[
            {
                "name": "etap-stack",
                "host": "127.0.0.1",
                "port": port,
                "unit_id": 1,
                "scan_rate_ms": 200,
                "timeout_sec": 2.0,
            }
        ],
        register_map=register_map,
        scan_rate_ms=200,
    )
    client = ModbusAdapter(
        config=client_cfg,
        role=AdapterRole.CLIENT,
        on_measurement=make_callback(bridge),
    )

    try:
        server.start()
        time.sleep(1.0)
        client.start()

        # Wait up to 5s for the client to read at least one value.
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if bridge.stats.total_ingested > 0:
                break
            time.sleep(0.1)

        # --- Verify the bridge ingested at least one point ---
        assert bridge.stats.total_ingested > 0, "bridge never ingested any value"

        # --- Verify SCADADatabase received the measurement ---
        # The bridge calls db.add_measurement() with measurement_id like
        # "modbus:etap-stack::BUS-1::VOLTAGE_MAGNITUDE".
        matching = [
            m
            for m in db.measurements.values()
            if m.element_id == "BUS-1"
            and m.measurement_type == MeasurementType.VOLTAGE_MAGNITUDE
        ]
        assert len(matching) > 0, "SCADADatabase has no measurement for BUS-1"
        latest = matching[-1]
        assert abs(latest.value - 1.05) < 1e-3, f"unexpected value: {latest.value}"
        assert latest.quality == QualityFlag.GOOD

        # --- Verify EventBus subscriber was notified ---
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if received_events:
                break
            time.sleep(0.05)
        assert len(received_events) > 0, "EventBus subscriber never received event"
        event = received_events[0]
        assert isinstance(event, SCADAUpdateReceived)
        assert event.source.startswith("modbus:")
        assert len(event.measurements) > 0
        m0 = event.measurements[0]
        assert m0["element_id"] == "BUS-1"
        assert m0["type"] == "VOLTAGE_MAGNITUDE"
        assert abs(m0["value"] - 1.05) < 1e-3

        # --- Verify get_latest_voltage works on the database ---
        v = db.get_latest_voltage("BUS-1")
        assert v is not None
        assert abs(v - 1.05) < 1e-3

    finally:
        client.stop()
        server.stop()
