"""Standalone SCADA simulator — runs a Modbus slave with fake measurements.

Used by docker-compose.scada.yml to provide a test target for the
AhmedETAP SCADAProtocolManager's Modbus client.

Usage::

    python -m scripts.scada_simulator --modbus-port 5021 --interval-ms 1000
"""

from __future__ import annotations

import argparse
import math
import socket
import sys
import time
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scada_protocols.common.base import AdapterRole
from scada_protocols.common.config import ModbusConfig
from scada_protocols.modbus import ModbusAdapter


def _free_port_if_zero(port: int) -> int:
    if port != 0:
        return port
    s = socket.socket()
    s.bind(("0.0.0.0", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main() -> int:
    parser = argparse.ArgumentParser(description="SCADA simulator (Modbus slave)")
    parser.add_argument("--modbus-port", type=int, default=5021,
                        help="TCP port for the Modbus slave (0 = random free port)")
    parser.add_argument("--interval-ms", type=int, default=1000,
                        help="Provider refresh interval in milliseconds")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Bind address")
    args = parser.parse_args()

    port = _free_port_if_zero(args.modbus_port)
    start_time = time.time()

    # Register map: 4 typical measurements.
    register_map = [
        {
            "name": "BUS1_V",
            "element_id": "BUS-SIM-1",
            "measurement_type": "voltage_magnitude",
            "address": 0,
            "data_type": "float32",
            "unit": "p.u.",
        },
        {
            "name": "BUS1_P",
            "element_id": "BUS-SIM-1",
            "measurement_type": "active_power",
            "address": 2,
            "data_type": "float32",
            "unit": "MW",
        },
        {
            "name": "BUS1_F",
            "element_id": "BUS-SIM-1",
            "measurement_type": "frequency",
            "address": 4,
            "data_type": "float32",
            "unit": "Hz",
        },
        {
            "name": "BRK1_STATUS",
            "element_id": "BRK-SIM-1",
            "measurement_type": "breaker_status",
            "address": 6,
            "data_type": "uint16",
            "unit": "0/1",
        },
    ]

    def provider() -> Dict[str, float]:
        elapsed = time.time() - start_time
        # Voltage: 1.0 p.u. ± 2% with slow oscillation.
        v = 1.0 + 0.02 * math.sin(0.1 * elapsed)
        # Active power: 12 MW ± 10%.
        p = 12.0 + 1.2 * math.sin(0.05 * elapsed)
        # Frequency: 50 Hz ± 0.05 Hz.
        f = 50.0 + 0.05 * math.sin(0.2 * elapsed)
        # Breaker status: closed (1) for the first 60s, then toggles every 30s.
        brk = 1 if (elapsed % 60) < 30 else 0
        return {
            "BUS1_V": round(v, 4),
            "BUS1_P": round(p, 4),
            "BUS1_F": round(f, 4),
            "BRK1_STATUS": float(brk),
        }

    cfg = ModbusConfig(
        enabled=True,
        role=AdapterRole.SERVER,
        server_host=args.host,
        server_port=port,
        server_unit_id=1,
        clients=[],
        register_map=register_map,
        scan_rate_ms=args.interval_ms,
    )
    adapter = ModbusAdapter(
        config=cfg,
        role=AdapterRole.SERVER,
        provider=provider,
    )

    print(f"SCADA simulator starting Modbus slave on {args.host}:{port} "
          f"(unit_id=1, refresh={args.interval_ms}ms)", flush=True)
    print("Connect a Modbus master to read 4 measurements:", flush=True)
    for entry in register_map:
        print(f"  addr={entry['address']:>3}  {entry['name']:<14} "
              f"({entry['measurement_type']}, {entry['data_type']})", flush=True)

    adapter.start()

    # Run forever until Ctrl+C.
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopping SCADA simulator...", flush=True)
        adapter.stop()
        return 0


if __name__ == "__main__":
    sys.exit(main())
