"""
scada_protocols.iec104.server
=============================
IEC 60870-5-104 server (RTU) adapter — ``c104`` based.

Exposes the platform's measurements to IEC 104 masters (SCADA front-ends).
A background thread refreshes point values from a registered
``MeasurementProvider`` callback and triggers spontaneous transmissions
(via ``point.transmit(cause=SPONTANEOUS)``) on every refresh.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from scada_protocols.common.base import (
    AdapterRole,
    MeasurementCallback,
    ProtocolAdapter,
    ProtocolType,
)
from scada_protocols.common.config import Iec104Config
from scada_protocols.iec104.asdu_mapper import (
    IEC104Point,
    PointMap,
    suggested_asdu_type,
)

logger = logging.getLogger(__name__)


MeasurementProvider = Callable[[], Dict[int, float]]


class IEC104ServerAdapter(ProtocolAdapter):
    """IEC 60870-5-104 server (RTU) exposing measurements to masters."""

    protocol = ProtocolType.IEC_104
    supports_server = True
    supports_client = False

    def __init__(
        self,
        config: Iec104Config,
        role: AdapterRole = AdapterRole.SERVER,
        on_measurement: Optional[MeasurementCallback] = None,
        provider: Optional[MeasurementProvider] = None,
    ) -> None:
        super().__init__(role=role, on_measurement=on_measurement, config={"config": config})
        if role != AdapterRole.SERVER:
            raise ValueError("IEC104ServerAdapter is server-only")
        self._cfg = config
        self._point_map = PointMap(config.point_map)
        self._provider = provider
        self._server: Any = None
        self._stations: Dict[int, Any] = {}
        self._points_by_ioa: Dict[int, Any] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop_event: Optional[threading.Event] = None
        self._refresh_thread: Optional[threading.Thread] = None

    # -- mutation -----------------------------------------------------------

    def set_provider(self, provider: MeasurementProvider) -> None:
        self._provider = provider

    @property
    def point_map(self) -> PointMap:
        return self._point_map

    # -- lifecycle ----------------------------------------------------------

    def start_server(self) -> None:
        if self._thread is not None:
            return
        try:
            import c104  # type: ignore
        except Exception as exc:
            raise ImportError(f"c104 (iec104-python) not available: {exc}") from exc

        self._c104 = c104
        self._server = c104.Server(
            ip=self._cfg.server_bind_ip,
            port=self._cfg.server_port,
            tick_rate_ms=100,
            max_connections=0,  # 0 = unlimited
        )

        # Group points by common address and create stations.
        cas_by_ca: Dict[int, List[IEC104Point]] = {}
        for pt in self._point_map.all_points():
            cas_by_ca.setdefault(pt.ca, []).append(pt)

        for ca, points in cas_by_ca.items():
            station = self._server.add_station(common_address=ca)
            self._stations[ca] = station
            for pt in points:
                # Pick the c104.Type by name. We support the most common
                # monitoring types; control types are not configured here.
                type_enum = getattr(self._c104.Type, pt.type_id, None)
                if type_enum is None:
                    # Fall back to a sensible default based on measurement_type.
                    suggested = suggested_asdu_type(pt.measurement_type)
                    type_enum = getattr(self._c104.Type, suggested, None)
                if type_enum is None:
                    self._mark_error(
                        f"unknown ASDU type {pt.type_id!r} for ioa={pt.ioa}"
                    )
                    continue
                # report_ms=0 means no cyclic auto-transmit; we drive it
                # ourselves from the refresh thread so we have full control.
                point = station.add_point(io_address=pt.ioa, type=type_enum, report_ms=0)
                self._points_by_ioa[pt.ioa] = point

                # Set up a before-read callback so masters doing interrogation
                # get the current value.
                def _make_read_cb(ioa: int):
                    def _cb(point_obj: Any) -> None:
                        snapshot = self._latest_snapshot
                        val = snapshot.get(ioa) if snapshot else None
                        if val is None:
                            return
                        self._set_point_value(point_obj, val, quality="good")

                    return _cb

                try:
                    point.on_before_read(callable=_make_read_cb(pt.ioa))
                except Exception as exc:
                    logger.debug("on_before_read failed for ioa=%d: %s", pt.ioa, exc)

        # Start the c104 server thread.
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run_server, name="iec104-server", daemon=True
        )
        self._thread.start()

        # Start our refresh thread that pushes spontaneous transmissions.
        self._refresh_thread = threading.Thread(
            target=self._refresh_loop, name="iec104-refresh", daemon=True
        )
        self._refresh_thread.start()

    def _run_server(self) -> None:
        try:
            self._server.start()  # blocking
        except Exception as exc:
            self._mark_error(f"server thread: {exc}")

    def _refresh_loop(self) -> None:
        interval = 1.0  # spontaneous transmission once per second by default
        while self._stop_event is not None and not self._stop_event.is_set():
            try:
                if self._provider is not None:
                    snapshot = self._provider() or {}
                    self._latest_snapshot = snapshot
                    # Push each value to its corresponding point and transmit.
                    for ioa, val in snapshot.items():
                        point = self._points_by_ioa.get(int(ioa))
                        if point is None:
                            continue
                        self._set_point_value(point, float(val), quality="good")
                        try:
                            self._c104_cot = getattr(self._c104.Cot, "SPONTANEOUS", None)
                            if self._c104_cot is not None:
                                point.transmit(cause=self._c104_cot)
                                self._mark_served()
                        except Exception as exc:
                            self._mark_error(f"transmit ioa={ioa}: {exc}")
            except Exception as exc:
                self._mark_error(f"refresh loop: {exc}")
            # Sleep 1s in small chunks so we can exit quickly.
            slept = 0.0
            while slept < interval:
                if self._stop_event is not None and self._stop_event.is_set():
                    return
                time.sleep(0.1)
                slept += 0.1

    def _set_point_value(self, point: Any, value: float, quality: str = "good") -> None:
        """Set a server-side point's value and quality.

        c104's ``point.value`` setter accepts primitive values (float/int/bool)
        or wrapped value objects (NormalizedFloat). It does NOT accept Info
        objects. Quality is set separately via ``point.quality``.
        """
        try:
            c104 = self._c104

            # Build the quality object.
            q = c104.Quality()
            if quality == "invalid":
                q = c104.Quality.Invalid
            elif quality == "questionable":
                q = c104.Quality.NonTopical

            # Determine which value to write based on the point's type.
            type_name = ""
            try:
                type_name = str(point.type).split(".")[-1]
            except Exception:
                pass

            if type_name.startswith("M_SP"):
                # Single-point: bool
                point.value = bool(value > 0.5)
            elif type_name.startswith("M_DP"):
                # Double-point: bool (True=closed/on, False=open/off)
                point.value = bool(value > 0.5)
            elif type_name.startswith("M_ME_NA"):
                # Normalized float [-1..1] — use NormalizedFloat wrapper
                # to enforce clamping.
                nf = c104.NormalizedFloat(max(-1.0, min(1.0, float(value))))
                point.value = nf
            elif type_name.startswith("M_ME_NB"):
                # Scaled int
                point.value = int(round(value))
            elif type_name.startswith("M_ME_NC") or type_name.startswith("M_ME_TF"):
                # Short float
                point.value = float(value)
            elif type_name.startswith("M_IT"):
                # Binary counter
                point.value = int(round(value))
            elif type_name.startswith("M_ST"):
                # Step position
                point.value = int(round(value))
            else:
                # Default: float
                point.value = float(value)

            # Set quality (may raise if the point type doesn't support it,
            # but we catch and ignore).
            try:
                point.quality = q
            except Exception:
                pass
        except Exception as exc:
            self._mark_error(f"set point value: {exc}")

    def stop_server(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        try:
            if self._server is not None:
                self._server.stop()
        except Exception as exc:
            self._mark_error(f"server.stop: {exc}")
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        if self._refresh_thread is not None:
            self._refresh_thread.join(timeout=3.0)
        self._thread = None
        self._refresh_thread = None
        self._stop_event = None
        self._server = None
        self._stations.clear()
        self._points_by_ioa.clear()

    # -- client stubs (server-only adapter) ---------------------------------

    def start_client(self) -> None:
        pass  # pragma: no cover

    def stop_client(self) -> None:
        pass  # pragma: no cover

    # -- health -------------------------------------------------------------

    def health_check(self) -> bool:
        try:
            # c104's Server.is_running is a property (bool), not a method.
            is_running = getattr(self._server, "is_running", False)
            if callable(is_running):
                is_running = is_running()
            if is_running:
                return True
            return self._thread is not None and self._thread.is_alive()
        except Exception:
            return False


__all__ = ["IEC104ServerAdapter", "MeasurementProvider"]
