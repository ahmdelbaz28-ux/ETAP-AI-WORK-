"""
scada_protocols.iec104.client
=============================
IEC 60870-5-104 client (master) adapter — ``c104`` based.

Connects to one or more RTUs, registers callbacks on configured points,
and pushes decoded measurements into the SCADA bridge.
"""

from __future__ import annotations

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
from scada_protocols.common.config import Iec104Config
from scada_protocols.iec104.asdu_mapper import (
    PointMap,
    decode_information,
    decode_quality,
)

logger = logging.getLogger(__name__)


class IEC104ClientAdapter(ProtocolAdapter):
    """IEC 60870-5-104 master that ingests measurements from remote RTUs."""

    protocol = ProtocolType.IEC_104
    supports_server = False
    supports_client = True

    def __init__(
        self,
        config: Iec104Config,
        role: AdapterRole = AdapterRole.CLIENT,
        on_measurement: Optional[MeasurementCallback] = None,
    ) -> None:
        super().__init__(role=role, on_measurement=on_measurement, config={"config": config})
        if role != AdapterRole.CLIENT:
            raise ValueError("IEC104ClientAdapter is client-only")
        self._cfg = config
        # Point map shared across all connections. The point_map keys are
        # (ca, ioa) pairs; for client-side we look up by ioa within the
        # connection's CA scope.
        self._point_map = PointMap(config.point_map)
        self._client: Any = None
        self._connections: Dict[str, Any] = {}  # name -> Connection
        self._stations: Dict[str, Dict[int, Any]] = {}  # name -> {ca: Station}
        self._points: Dict[str, Dict[int, Any]] = {}  # name -> {ioa: Point}
        self._thread: Optional[threading.Thread] = None
        self._stop_event: Optional[threading.Event] = None
        self._interrogation_thread: Optional[threading.Thread] = None

    # -- lifecycle ----------------------------------------------------------

    def start_client(self) -> None:
        if self._thread is not None:
            return
        try:
            import c104  # type: ignore
        except Exception as exc:
            raise ImportError(f"c104 (iec104-python) not available: {exc}") from exc

        self._c104 = c104
        self._client = c104.Client(tick_rate_ms=100)

        # Add a connection for each configured client entry.
        for cli in self._cfg.clients:
            name = str(cli.get("name", "rtu"))
            host = str(cli.get("host", "127.0.0.1"))
            port = int(cli.get("port", 2404))
            ca = int(cli.get("common_address", self._cfg.common_address))

            try:
                init = c104.Init.ALL
                conn = self._client.add_connection(ip=host, port=port, init=init)
                if conn is None:
                    self._mark_error(f"add_connection returned None for {name}")
                    continue
                self._connections[name] = conn
                self._stations[name] = {}
                self._points[name] = {}

                # Add station(s) for this connection based on point_map entries
                # that share this common address (or all entries if no per-
                # connection ca specified).
                cas_to_add = {ca}
                for pt in self._point_map.all_points():
                    if cli.get("common_address") is None:
                        cas_to_add.add(pt.ca)

                for ca_val in cas_to_add:
                    station = conn.add_station(common_address=ca_val)
                    if station is None:
                        continue
                    self._stations[name][ca_val] = station
                    for pt in self._point_map.all_points():
                        if pt.ca != ca_val:
                            continue
                        type_enum = getattr(c104.Type, pt.type_id, None)
                        if type_enum is None:
                            from scada_protocols.iec104.asdu_mapper import (
                                suggested_asdu_type,
                            )

                            type_enum = getattr(
                                c104.Type,
                                suggested_asdu_type(pt.measurement_type),
                                None,
                            )
                        if type_enum is None:
                            self._mark_error(
                                f"unknown ASDU type {pt.type_id!r} for ioa={pt.ioa}"
                            )
                            continue
                        try:
                            point = station.add_point(io_address=pt.ioa, type=type_enum)
                        except Exception as exc:
                            self._mark_error(
                                f"add_point failed (ca={ca_val}, ioa={pt.ioa}): {exc}"
                            )
                            continue
                        self._points[name][pt.ioa] = point

                        # Register receive callback. c104 validates the
                        # callback's type hints at registration time by
                        # stringifying them, so we cannot use `Any` (which
                        # stringifies to 'Any'). We must use the actual c104
                        # type objects in the annotations, not strings.
                        # `from __future__ import annotations` would make all
                        # annotations strings — so we build the callback via
                        # compile() with flags=0 to disable future annotations,
                        # then set __annotations__ explicitly to be safe.
                        _point_meta = pt
                        _src_name = name
                        _adapter = self

                        def _cb(point, previous_info, message):
                            try:
                                val = decode_information(previous_info, _point_meta)
                                q = decode_quality(previous_info)
                                if val is None:
                                    return c104.ResponseState.NONE
                                _adapter._ingest(
                                    _point_meta.element_id,
                                    _point_meta.measurement_type,
                                    float(val),
                                    quality=q,
                                    source="iec104:" + _src_name,
                                )
                            except Exception as exc:
                                _adapter._mark_error(
                                    "on_receive (ioa=" + str(_point_meta.ioa) + "): " + str(exc)
                                )
                            return c104.ResponseState.NONE

                        # Set real type-object annotations (not strings).
                        _cb.__annotations__ = {
                            "point": c104.Point,
                            "previous_info": c104.Information,
                            "message": c104.IncomingMessage,
                            "return": c104.ResponseState,
                        }

                        try:
                            point.on_receive(callable=_cb)
                        except Exception as exc:
                            self._mark_error(
                                f"on_receive register (ca={ca_val}, ioa={pt.ioa}): {exc}"
                            )
            except Exception as exc:
                self._mark_error(f"setup connection {name}: {exc}")

        # Start the c104 client thread.
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run_client, name="iec104-client", daemon=True
        )
        self._thread.start()

        # Start an interrogation loop that periodically polls each connection.
        self._interrogation_thread = threading.Thread(
            target=self._interrogation_loop, name="iec104-interrogation", daemon=True
        )
        self._interrogation_thread.start()

    def _run_client(self) -> None:
        try:
            self._client.start()  # blocking
        except Exception as exc:
            self._mark_error(f"client thread: {exc}")

    def _interrogation_loop(self) -> None:
        """Periodically issue interrogation commands on each connection."""
        interval = 1.0
        slept = 0.0
        # Allow the client a moment to establish connections.
        time.sleep(0.5)
        while self._stop_event is not None and not self._stop_event.is_set():
            try:
                for name, conn in self._connections.items():
                    if self._stop_event is not None and self._stop_event.is_set():
                        break
                    try:
                        # c104's Connection.is_connected is a property (bool),
                        # NOT a method. Use getattr to be safe across versions.
                        is_connected = getattr(conn, "is_connected", False)
                        if callable(is_connected):
                            is_connected = is_connected()
                        if not is_connected:
                            continue
                        # Issue a station interrogation. c104's Connection.interrogation
                        # signature is:
                        #   interrogation(common_address, cause=Cot.ACTIVATION,
                        #                  qualifier=Qoi.STATION, wait_for_response=True)
                        try:
                            conn.interrogation(common_address=self._cfg.common_address)
                        except TypeError:
                            # Older API: positional only.
                            try:
                                conn.interrogation(self._cfg.common_address)
                            except Exception as exc:
                                self._mark_error(f"interrogation {name}: {exc}")
                    except Exception as exc:
                        self._mark_error(f"interrogation {name}: {exc}")
            except Exception as exc:
                self._mark_error(f"interrogation loop: {exc}")
            slept = 0.0
            while slept < interval:
                if self._stop_event is not None and self._stop_event.is_set():
                    return
                time.sleep(0.1)
                slept += 0.1

    def stop_client(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        try:
            if self._client is not None:
                self._client.stop()
        except Exception as exc:
            self._mark_error(f"client.stop: {exc}")
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        if self._interrogation_thread is not None:
            self._interrogation_thread.join(timeout=3.0)
        self._thread = None
        self._interrogation_thread = None
        self._stop_event = None
        self._client = None
        self._connections.clear()
        self._stations.clear()
        self._points.clear()

    # -- server stubs (client-only adapter) ---------------------------------

    def start_server(self) -> None:
        pass  # pragma: no cover

    def stop_server(self) -> None:
        pass  # pragma: no cover

    # -- health -------------------------------------------------------------

    def health_check(self) -> bool:
        try:
            # c104's Client.is_running is a property (bool), not a method.
            is_running = getattr(self._client, "is_running", False)
            if callable(is_running):
                is_running = is_running()
            if is_running:
                return True
            return self._thread is not None and self._thread.is_alive()
        except Exception:
            return False


__all__ = ["IEC104ClientAdapter"]
