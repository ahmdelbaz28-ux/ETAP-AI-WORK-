"""Live integration test — OPC UA server + client round-trip on loopback.

Starts an OpcUaServerAdapter with a small address space, then an
OpcUaClientAdapter that subscribes to it, and verifies the bridge receives
the values written by the server's provider callback.

Requires ``asyncua`` to be installed; skips otherwise.
"""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scada_protocols.common.base import AdapterRole, probe_opcua
from scada_protocols.common.bridge import SCADAProtocolBridge, make_callback
from scada_protocols.common.config import OpcUaConfig
from scada_protocols.opcua import OpcUaAdapter

opcua_available, _ = probe_opcua()
pytestmark = pytest.mark.skipif(
    not opcua_available, reason="asyncua not installed"
)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_opcua_server_client_round_trip():
    """Server writes 1.05 via provider; client reads it via the bridge."""
    port = _free_port()
    endpoint = f"opc.tcp://127.0.0.1:{port}/etap/server"

    node_map = [
        {
            "node_id": "ns=3;s=BUS1.Voltage",
            "element_id": "BUS-1",
            "measurement_type": "voltage_magnitude",
            "browse_name": "BUS1.Voltage",
            "unit": "p.u.",
            "folder": "Buses",
        }
    ]

    # Provider writes 1.05 p.u. into the server's address space.
    def provider():
        # The provider returns a dict keyed by the node_id_hint of each
        # variable; the server refresh loop looks them up by that hint.
        return {"ns=3;s=BUS1.Voltage": 1.05}

    server_cfg = OpcUaConfig(
        enabled=True,
        role=AdapterRole.SERVER,
        server_endpoint=endpoint,
        server_name="AhmedETAP.OPCUA.Server.Test",
        server_namespace=3,
        publish_interval_ms=200,
        clients=[],
        node_map=node_map,
    )
    server = OpcUaAdapter(
        config=server_cfg,
        role=AdapterRole.SERVER,
        provider=provider,
    )

    # Client side: subscribe to the same endpoint + node.
    bridge = SCADAProtocolBridge()
    client_cfg = OpcUaConfig(
        enabled=True,
        role=AdapterRole.CLIENT,
        server_endpoint=endpoint,
        server_name="AhmedETAP.OPCUA.Server.Test",
        server_namespace=3,
        publish_interval_ms=200,
        clients=[
            {
                "name": "local-server",
                "endpoint": endpoint,
                "publish_interval_ms": 200,
            }
        ],
        node_map=node_map,
    )
    client = OpcUaAdapter(
        config=client_cfg,
        role=AdapterRole.CLIENT,
        on_measurement=make_callback(bridge),
    )

    try:
        server.start()
        # OPC UA servers take longer to bind than Modbus. Wait up to 5s for
        # the server's health_check to report True (i.e. the thread is alive
        # and the server has had time to register its endpoint).
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if server.health_check():
                # Give the server an extra moment to finish registering
                # its address space before we hammer it with a client.
                time.sleep(1.0)
                break
            time.sleep(0.2)
        assert server.health_check(), "OPC UA server failed to start"

        client.start()
        # Wait up to 10s for the client to read at least one value.
        deadline = time.time() + 10.0
        while time.time() < deadline:
            if bridge.stats.total_ingested > 0:
                break
            time.sleep(0.1)
        assert bridge.stats.total_ingested > 0, "client never ingested any value"
        assert bridge.stats.by_type.get("VOLTAGE_MAGNITUDE", 0) > 0
        assert bridge.stats.by_protocol.get("opcua:local-server", 0) > 0
    finally:
        client.stop()
        server.stop()
