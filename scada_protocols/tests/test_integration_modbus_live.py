"""Live integration test — Modbus server + client round-trip on loopback.

This test spins up a ModbusServerAdapter on 127.0.0.1:<random port>, then a
ModbusClientAdapter that polls it, and verifies the bridge receives the values.
It requires ``pymodbus`` to be installed; skips otherwise.
"""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scada_protocols.common.base import AdapterRole, probe_modbus
from scada_protocols.common.bridge import SCADAProtocolBridge, make_callback
from scada_protocols.common.config import ModbusConfig
from scada_protocols.modbus import ModbusAdapter

pymodbus_available, _ = probe_modbus()
pytestmark = pytest.mark.skipif(
    not pymodbus_available, reason="pymodbus not installed"
)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_modbus_server_client_round_trip():
    """Server writes a value via provider; client reads it via the bridge."""
    port = _free_port()
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

    # Provider pushes 1.05 p.u. into the server's register store.
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

    # Bridge + client.
    bridge = SCADAProtocolBridge()
    client_cfg = ModbusConfig(
        enabled=True,
        role=AdapterRole.CLIENT,
        server_host="127.0.0.1",
        server_port=port,
        server_unit_id=1,
        clients=[
            {
                "name": "local-server",
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
        # Give the server a moment to bind + push the first refresh.
        time.sleep(1.0)
        client.start()
        # Wait up to 5s for the client to read at least one value.
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if bridge.stats.total_ingested > 0:
                break
            time.sleep(0.1)
        assert bridge.stats.total_ingested > 0, "client never ingested any value"
        # The bridge should have received something close to 1.05 (within
        # float32 precision).
        assert bridge.stats.by_type.get("VOLTAGE_MAGNITUDE", 0) > 0
        assert bridge.stats.by_protocol.get("modbus:local-server", 0) > 0
    finally:
        client.stop()
        server.stop()
