"""
AhmedETAP Platform — SCADA Client (IEC 61850)
=============================================

Provides real-time SCADA data ingestion via IEC 61850 protocol.
Falls back to a simulated/mock data source when no real IEC 61850
server is available (e.g., in development or CI environments).

Features:
- IEC 61850 MMS client for real SCADA data (via iec61850datamodel or py61850)
- Configurable polling interval (default 5 seconds)
- Automatic fallback to simulated data when no server is reachable
- Structured telemetry: voltages, currents, frequencies, power values
- Timestamps on every reading for audit trail

Usage::

    from etap_integration.scada_client import SCADAClient

    client = SCADAClient(host="192.168.1.100", port=102)
    data = await client.get_live_data()
    # {"voltages": [...], "currents": [...], "timestamp": 1718...}

Environment variables:
    SCADA_HOST     — IEC 61850 server IP (default: "" — uses simulation)
    SCADA_PORT     — IEC 61850 server port (default: 102)
    SCADA_POLL_SEC — Polling interval in seconds (default: 5)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_SCADA_HOST = os.environ.get("SCADA_HOST", "")
_SCADA_PORT = int(os.environ.get("SCADA_PORT", "102"))
_SCADA_POLL_SEC = int(os.environ.get("SCADA_POLL_SEC", "5"))


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class SCADAReading:
    """A single SCADA data point with timestamp."""

    tag: str
    value: float
    unit: str
    timestamp: float = field(default_factory=time.time)
    quality: str = "good"  # good, uncertain, bad


@dataclass
class SCADATelemetry:
    """Aggregated SCADA telemetry snapshot."""

    voltages: List[SCADAReading] = field(default_factory=list)
    currents: List[SCADAReading] = field(default_factory=list)
    frequencies: List[SCADAReading] = field(default_factory=list)
    active_power: List[SCADAReading] = field(default_factory=list)
    reactive_power: List[SCADAReading] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    source: str = "simulation"  # simulation, iec61850, mock


# ---------------------------------------------------------------------------
# IEC 61850 client (optional dependency)
# ---------------------------------------------------------------------------

_HAS_IEC61850 = False
_iec61850_module: Any = None

try:
    import iec61850datamodel as iec61850  # type: ignore

    _HAS_IEC61850 = True
    _iec61850_module = iec61850
    logger.info("IEC 61850 datamodel library loaded — real SCADA available")
except ImportError:
    try:
        from py61850 import Client as Py61850Client  # type: ignore  # noqa: F401

        _HAS_IEC61850 = True
        logger.info("py61850 library loaded — real SCADA available via py61850")
    except ImportError:
        logger.info(
            "No IEC 61850 library installed — SCADA client will use simulated data. "
            "Install iec61850datamodel or py61850 for real SCADA integration."
        )


# ---------------------------------------------------------------------------
# Simulated SCADA data generator
# ---------------------------------------------------------------------------

import math
import random


class SimulatedSCADA:
    """Generate realistic simulated SCADA data for development and testing.

    Produces sinusoidal voltage/current waveforms with realistic noise
    and load variation patterns.
    """

    def __init__(self, n_buses: int = 5) -> None:
        self._n_buses = n_buses
        self._start_time = time.time()
        self._random = random.Random(42)

    def generate_telemetry(self) -> SCADATelemetry:
        """Generate a complete telemetry snapshot."""
        elapsed = time.time() - self._start_time
        telemetry = SCADATelemetry(source="simulation")

        for i in range(self._n_buses):
            bus_name = f"BUS{i + 1}"

            # Voltage: 1.0 p.u. ± 3% with slow oscillation
            v_base = 1.0 + 0.02 * math.sin(0.1 * elapsed + i * 0.5)
            v_noise = self._random.gauss(0, 0.005)
            telemetry.voltages.append(
                SCADAReading(
                    tag=f"{bus_name}/Voltage",
                    value=round(v_base + v_noise, 4),
                    unit="p.u.",
                )
            )

            # Current: 0.5-0.9 p.u. with load pattern
            i_base = 0.7 + 0.15 * math.sin(0.05 * elapsed + i * 0.3)
            i_noise = self._random.gauss(0, 0.01)
            telemetry.currents.append(
                SCADAReading(
                    tag=f"{bus_name}/Current",
                    value=round(i_base + i_noise, 4),
                    unit="p.u.",
                )
            )

            # Frequency: 50 Hz ± 0.05 Hz
            f_base = 50.0 + 0.02 * math.sin(0.2 * elapsed)
            f_noise = self._random.gauss(0, 0.005)
            telemetry.frequencies.append(
                SCADAReading(
                    tag=f"{bus_name}/Frequency",
                    value=round(f_base + f_noise, 4),
                    unit="Hz",
                )
            )

            # Active power
            p_val = (v_base + v_noise) * (i_base + i_noise) * 0.85
            telemetry.active_power.append(
                SCADAReading(
                    tag=f"{bus_name}/ActivePower",
                    value=round(p_val, 4),
                    unit="p.u.",
                )
            )

            # Reactive power
            q_val = (v_base + v_noise) * (i_base + i_noise) * 0.53
            telemetry.reactive_power.append(
                SCADAReading(
                    tag=f"{bus_name}/ReactivePower",
                    value=round(q_val, 4),
                    unit="p.u.",
                )
            )

        return telemetry


# ---------------------------------------------------------------------------
# Main SCADA Client
# ---------------------------------------------------------------------------


class SCADAClient:
    """Real-time SCADA data client with IEC 61850 support.

    Attempts to connect to a real IEC 61850 server. If unavailable,
    falls back to simulated data for development and testing.

    Parameters
    ----------
    host : str
        IEC 61850 server IP address. Empty string triggers simulation mode.
    port : int
        IEC 61850 server port (default 102).
    poll_interval_sec : int
        Data refresh interval in seconds (default 5).
    """

    def __init__(
        self,
        host: str = "",
        port: int = 102,
        poll_interval_sec: int = 5,
    ) -> None:
        self._host = host or _SCADA_HOST
        self._port = port if port is not None else _SCADA_PORT
        self._poll_interval = (
            poll_interval_sec if poll_interval_sec is not None else _SCADA_POLL_SEC
        )
        self._connected = False
        self._last_telemetry: Optional[SCADATelemetry] = None
        self._simulated = SimulatedSCADA()
        self._client: Any = None

        # Try IEC 61850 connection if host is configured
        if self._host and _HAS_IEC61850:
            self._init_iec61850_client()
        elif self._host:
            logger.warning(
                "SCADA host '%s' configured but no IEC 61850 library available. "
                "Falling back to simulated data.",
                self._host,
            )

    def _init_iec61850_client(self) -> None:
        """Initialize the IEC 61850 client connection."""
        try:
            # Try py61850 Client
            from py61850 import Client as Py61850Client  # type: ignore

            self._client = Py61850Client(self._host, self._port)
            self._connected = True
            logger.info(
                "IEC 61850 client initialized: %s:%d",
                self._host,
                self._port,
            )
        except Exception as exc:
            logger.warning(
                "Failed to initialize IEC 61850 client (%s:%d): %s — using simulation",
                self._host,
                self._port,
                exc,
            )
            self._connected = False

    async def get_live_data(self) -> Dict[str, Any]:
        """Fetch current SCADA telemetry data.

        Returns
        -------
        dict
            Dictionary with keys: voltages, currents, frequencies,
            active_power, reactive_power, timestamp, source.
        """
        if self._connected and self._client is not None:
            return await self._read_from_server()
        return self._read_from_simulation()

    async def _read_from_server(self) -> Dict[str, Any]:
        """Read data from the IEC 61850 server."""
        try:
            telemetry = SCADATelemetry(source="iec61850", timestamp=time.time())

            # Read voltage measurements from IEC 61850 logical nodes
            voltage_refs = [
                "MMXU1$CF$Vol$mag$f",
                "MMXU2$CF$Vol$mag$f",
                "MMXU3$CF$Vol$mag$f",
            ]
            for i, ref in enumerate(voltage_refs):
                try:
                    val = self._client.read(f"SimpleGenericIO/GGIO1.{ref}")
                    telemetry.voltages.append(
                        SCADAReading(
                            tag=f"BUS{i + 1}/Voltage",
                            value=float(val) if val else 0.0,
                            unit="p.u.",
                        )
                    )
                except Exception:
                    telemetry.voltages.append(
                        SCADAReading(
                            tag=f"BUS{i + 1}/Voltage",
                            value=0.0,
                            unit="p.u.",
                            quality="bad",
                        )
                    )

            self._last_telemetry = telemetry
            return self._telemetry_to_dict(telemetry)

        except Exception as exc:
            logger.warning("IEC 61850 read failed: %s — falling back to simulation", exc)
            self._connected = False
            return self._read_from_simulation()

    def _read_from_simulation(self) -> Dict[str, Any]:
        """Read data from the simulated SCADA source."""
        telemetry = self._simulated.generate_telemetry()
        self._last_telemetry = telemetry
        return self._telemetry_to_dict(telemetry)

    @staticmethod
    def _telemetry_to_dict(telemetry: SCADATelemetry) -> Dict[str, Any]:
        """Convert SCADATelemetry to a JSON-serializable dictionary."""

        def readings_to_list(readings: List[SCADAReading]) -> List[Dict[str, Any]]:
            return [
                {
                    "tag": r.tag,
                    "value": r.value,
                    "unit": r.unit,
                    "timestamp": r.timestamp,
                    "quality": r.quality,
                }
                for r in readings
            ]

        return {
            "voltages": readings_to_list(telemetry.voltages),
            "currents": readings_to_list(telemetry.currents),
            "frequencies": readings_to_list(telemetry.frequencies),
            "active_power": readings_to_list(telemetry.active_power),
            "reactive_power": readings_to_list(telemetry.reactive_power),
            "timestamp": telemetry.timestamp,
            "source": telemetry.source,
            "n_buses": len(telemetry.voltages),
        }

    @property
    def is_connected(self) -> bool:
        """Whether the client is connected to a real SCADA server."""
        return self._connected

    @property
    def source(self) -> str:
        """Current data source: 'iec61850' or 'simulation'."""
        if self._connected and self._client is not None:
            return "iec61850"
        return "simulation"

    @property
    def last_telemetry(self) -> Optional[SCADATelemetry]:
        """The most recent telemetry snapshot."""
        return self._last_telemetry


# ---------------------------------------------------------------------------
# Async streaming interface
# ---------------------------------------------------------------------------


async def stream_scada_data(
    client: Optional[SCADAClient] = None,
    interval_sec: int = 5,
):
    """Async generator that yields SCADA telemetry at the configured interval.

    Parameters
    ----------
    client : SCADAClient, optional
        Client instance. Created with default settings if not provided.
    interval_sec : int
        Update interval in seconds (default 5).

    Yields
    ------
    dict
        SCADA telemetry data at each interval.
    """
    if client is None:
        client = SCADAClient()

    while True:
        data = await client.get_live_data()
        yield data
        await asyncio.sleep(interval_sec)
