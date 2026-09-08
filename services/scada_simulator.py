"""services/scada_simulator.py — SCADA telemetry acquisition and simulation service.

Separates real SCADA bridge communication (ETAPScadaBridge / IEC 61850 / zenon)
from mock synthetic data generation.
"""

from __future__ import annotations

import random
import secrets
from datetime import datetime, timezone
from typing import Any, Dict

try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

_bridge_instance = None
_bridge_checked = False


def _get_bridge():
    global _bridge_instance, _bridge_checked
    if not _bridge_checked:
        _bridge_checked = True
        try:
            from etap_scada_bridge import ETAPScadaBridge

            _bridge_instance = ETAPScadaBridge()
        except Exception:
            _bridge_instance = None
    return _bridge_instance


def generate_simulated_scada() -> Dict[str, Any]:
    """Generate mock SCADA data for demonstration purposes."""
    scada_data: Dict[str, Any] = {
        "is_simulated": True,
        "timestamp": datetime.now(UTC).isoformat(),
        "measurements": {
            "bus_voltages": [
                {
                    "bus_id": "BUS_1",
                    "voltage_kV": round(random.uniform(11.0, 12.5), 3),
                    "angle_deg": round(random.uniform(-5, 5), 2),
                },
                {
                    "bus_id": "BUS_2",
                    "voltage_kV": round(random.uniform(11.0, 12.5), 3),
                    "angle_deg": round(random.uniform(-5, 5), 2),
                },
                {
                    "bus_id": "BUS_3",
                    "voltage_kV": round(random.uniform(11.0, 12.5), 3),
                    "angle_deg": round(random.uniform(-5, 5), 2),
                },
            ],
            "line_flows": [
                {
                    "line_id": "LINE_1_2",
                    "mw": round(random.uniform(10, 100), 2),
                    "mvar": round(random.uniform(5, 50), 2),
                },
                {
                    "line_id": "LINE_2_3",
                    "mw": round(random.uniform(10, 100), 2),
                    "mvar": round(random.uniform(5, 50), 2),
                },
            ],
            "generator_outputs": [
                {
                    "gen_id": "GEN_1",
                    "mw": round(random.uniform(50, 200), 2),
                    "mvar": round(random.uniform(20, 80), 2),
                },
                {
                    "gen_id": "GEN_2",
                    "mw": round(random.uniform(50, 200), 2),
                    "mvar": round(random.uniform(20, 80), 2),
                },
            ],
            "load_values": [
                {
                    "load_id": "LOAD_1",
                    "mw": round(random.uniform(10, 50), 2),
                    "mvar": round(random.uniform(5, 25), 2),
                },
                {
                    "load_id": "LOAD_2",
                    "mw": round(random.uniform(10, 50), 2),
                    "mvar": round(random.uniform(5, 25), 2),
                },
            ],
        },
        "alarms": [],
        "system_status": "NORMAL",
    }

    if secrets.randbelow(10) == 0:  # 10% chance of alarm
        severity = "WARNING" if secrets.randbelow(10) < 7 else "CRITICAL"
        scada_data["alarms"].append(
            {
                "alarm_id": f"ALARM_{secrets.randbelow(9000) + 1000}",
                "timestamp": datetime.now(UTC).isoformat(),
                "severity": severity,
                "description": f"Simulated alarm for equipment {secrets.choice(['Transformer', 'Breaker', 'Line'])}",
                "location": secrets.choice(["SUBSTATION_A", "SUBSTATION_B", "FEEDER_C"]),
            },
        )

    return scada_data


def get_scada_telemetry() -> Dict[str, Any]:
    """Read telemetry from real SCADA bridge if connected, otherwise fallback to simulation."""
    try:
        bridge = _get_bridge()
        if bridge and hasattr(bridge, "is_connected") and bridge.is_connected():
            telemetry = bridge.read_telemetry()
            if telemetry:
                return {
                    "is_simulated": False,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "measurements": telemetry,
                    "alarms": [],
                    "system_status": "NORMAL",
                }
    except Exception:
        pass

    return generate_simulated_scada()
