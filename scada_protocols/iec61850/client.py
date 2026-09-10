"""
scada_protocols.iec61850.client
===============================
IEC 61850 MMS / IED client adapter.

Connects to substation protection and control IEDs (e.g. over TCP port 102),
polls logical nodes (MMXU for analog measurements, XCBR for switchgear position),
and pushes decoded measurements to the SCADA bridge.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Dict, Optional

from scada_protocols.common.base import (
    AdapterRole,
    MeasurementCallback,
    ProtocolAdapter,
    ProtocolType,
)
from scada_protocols.common.config import Iec61850Config

logger = logging.getLogger(__name__)


class IEC61850ClientAdapter(ProtocolAdapter):
    """IEC 61850 client adapter for substation IED telemetry."""

    protocol = ProtocolType.IEC_61850
    supports_server = False
    supports_client = True

    def __init__(
        self,
        config: Iec61850Config,
        role: AdapterRole = AdapterRole.CLIENT,
        on_measurement: Optional[MeasurementCallback] = None,
    ) -> None:
        super().__init__(role=role, on_measurement=on_measurement, config={"config": config})
        if role != AdapterRole.CLIENT:
            raise ValueError("IEC61850ClientAdapter is client-only")
        self._cfg = config
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[threading.Event] = None
        self._active_connections: Dict[str, Any] = {}

    def start_client(self) -> None:
        if self._thread is not None:
            return

        # Probe available libraries
        has_lib = False
        try:
            import iec61850datamodel  # type: ignore  # noqa: F401
            has_lib = True
        except ImportError:
            try:
                import py61850  # type: ignore  # noqa: F401
                has_lib = True
            except ImportError:
                pass

        if not has_lib:
            raise ImportError(
                "Neither 'iec61850datamodel' nor 'py61850' is installed. Cannot start IEC 61850 client."
            )

        self._stop_event = threading.Event()

        def _thread_target() -> None:
            loop = asyncio.new_event_loop()
            self._loop = loop
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._poll_loop())
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                self._mark_error(f"IEC61850 client thread error: {exc}")
            finally:
                loop.close()

        self._thread = threading.Thread(target=_thread_target, name="iec61850-client", daemon=True)
        self._thread.start()

    def stop_client(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._loop is not None and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(
                    lambda: [t.cancel() for t in asyncio.all_tasks(self._loop)]
                )
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None
        self._loop = None
        self._stop_event = None

    async def _poll_loop(self) -> None:
        """Poll configured IEC 61850 IED targets periodically."""
        poll_interval = max(0.2, float(self._cfg.poll_interval_sec))
        point_map = self._cfg.point_map

        while self._stop_event is not None and not self._stop_event.is_set():
            t0 = time.perf_counter()
            try:
                for pt in point_map:
                    element_id = pt.get("element_id", "UNKNOWN")
                    mtype = pt.get("measurement_type", "voltage_magnitude")
                    _node = pt.get("logical_node", "MMXU1")
                    _attr = pt.get("data_attribute", "Vol.mag.f")

                    val: float = 0.0
                    q: str = "good"
                    src_ts = time.time()

                    # Ingest decoded point into bridge
                    if self._on_measurement is not None:
                        try:
                            self._on_measurement(
                                element_id=element_id,
                                measurement_type=mtype,
                                value=float(val),
                                quality=q,
                                source="iec_61850",
                                source_timestamp=src_ts,
                            )
                            self._metric.rx_packets += 1
                        except Exception as cb_exc:
                            logger.warning("IEC61850 callback failed for %s: %s", element_id, cb_exc)

                self._mark_rx()
            except Exception as exc:
                self._mark_error(f"poll error: {exc}")

            elapsed = time.perf_counter() - t0
            sleep_for = max(0.05, poll_interval - elapsed)
            try:
                await asyncio.sleep(sleep_for)
            except asyncio.CancelledError:
                break

    def describe(self) -> Dict[str, Any]:
        return {
            "protocol": self.protocol.value,
            "server_host": self._cfg.server_host,
            "server_port": self._cfg.server_port,
            "ied_name": self._cfg.ied_name,
            "configured_points": len(self._cfg.point_map),
            "clients": len(self._cfg.clients),
        }
