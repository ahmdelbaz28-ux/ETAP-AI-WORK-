"""Live integration test — IEC 60870-5-104 server + client round-trip on loopback.

Starts an IEC104ServerAdapter with one M_ME_NC_1 (short float) point, then an
IEC104ClientAdapter that connects to it and ingests values via the bridge.

Requires ``c104`` to be installed; skips otherwise.
"""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scada_protocols.common.base import AdapterRole, probe_iec104
from scada_protocols.common.bridge import SCADAProtocolBridge, make_callback
from scada_protocols.common.config import Iec104Config
from scada_protocols.iec104 import IEC104Adapter

iec104_available, _ = probe_iec104()
pytestmark = pytest.mark.skipif(
    not iec104_available, reason="c104 not installed"
)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_iec104_server_client_round_trip():
    """Server writes 1.05 via provider; client reads it via the bridge."""
    port = _free_port()

    point_map = [
        {
            "ca": 1,
            "ioa": 1001,
            "element_id": "BUS-1",
            "measurement_type": "voltage_magnitude",
            "type_id": "M_ME_NC_1",
            "unit": "p.u.",
        }
    ]

    # Provider pushes 1.05 p.u. to ioa=1001 on the server side.
    def provider():
        return {1001: 1.05}

    server_cfg = Iec104Config(
        enabled=True,
        role=AdapterRole.SERVER,
        server_bind_ip="127.0.0.1",
        server_port=port,
        common_address=1,
        clients=[],
        point_map=point_map,
    )
    server = IEC104Adapter(
        config=server_cfg,
        role=AdapterRole.SERVER,
        provider=provider,
    )

    # Client side.
    bridge = SCADAProtocolBridge()
    client_cfg = Iec104Config(
        enabled=True,
        role=AdapterRole.CLIENT,
        server_bind_ip="127.0.0.1",
        server_port=port,
        common_address=1,
        clients=[
            {
                "name": "local-rtu",
                "host": "127.0.0.1",
                "port": port,
                "common_address": 1,
            }
        ],
        point_map=point_map,
    )
    client = IEC104Adapter(
        config=client_cfg,
        role=AdapterRole.CLIENT,
        on_measurement=make_callback(bridge),
    )

    try:
        server.start()
        # Give the server a moment to bind + push the first spontaneous transmission.
        time.sleep(2.0)
        client.start()
        # Wait up to 10s for the client to receive at least one value.
        deadline = time.time() + 10.0
        while time.time() < deadline:
            if bridge.stats.total_ingested > 0:
                break
            time.sleep(0.1)
        assert bridge.stats.total_ingested > 0, "client never ingested any value"
        assert bridge.stats.by_type.get("VOLTAGE_MAGNITUDE", 0) > 0
        assert bridge.stats.by_protocol.get("iec104:local-rtu", 0) > 0
    finally:
        client.stop()
        server.stop()
