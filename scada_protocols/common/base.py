"""
scada_protocols.common.base
============================
Abstract base for all SCADA protocol adapters.

Design contract:
- Each protocol (Modbus / OPC UA / IEC 104) implements ``ProtocolAdapter``.
- The adapter is *direction-agnostic*: it can run as a SERVER (slave/RTU that
  exposes measurements) and/or as a CLIENT (master that ingests measurements).
- Ingested measurements are pushed into the platform's existing
  ``scada_model.scada_model.SCADADatabase`` via the bridge in ``bridge.py``.
- Nothing here imports a protocol library eagerly. Adapters lazy-import their
  own dependencies so the package loads cleanly even when a library is absent.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data containers
# ---------------------------------------------------------------------------


class ProtocolType(str, Enum):
    """Identifies the SCADA protocol implementation."""

    MODBUS_TCP = "modbus_tcp"
    OPC_UA = "opc_ua"
    IEC_104 = "iec_104"


class AdapterRole(str, Enum):
    """Whether the adapter acts as a server (slave), a client (master), or both."""

    SERVER = "server"
    CLIENT = "client"
    BOTH = "both"


class AdapterState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class ProtocolMetric:
    """Lightweight metric snapshot for observability."""

    protocol: ProtocolType
    role: AdapterRole
    state: AdapterState
    points_ingested: int = 0
    points_served: int = 0
    errors: int = 0
    last_message_ts: Optional[float] = None
    last_error: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol": self.protocol.value,
            "role": self.role.value,
            "state": self.state.value,
            "points_ingested": self.points_ingested,
            "points_served": self.points_served,
            "errors": self.errors,
            "last_message_ts": self.last_message_ts,
            "last_error": self.last_error,
            "extras": self.extras,
        }


# A measurement callback is the only contract the bridge needs.
# Signature: (element_id, measurement_type_str, value, quality_str, source) -> None
MeasurementCallback = Callable[[str, str, float, str, str], None]


# ---------------------------------------------------------------------------
# Abstract adapter
# ---------------------------------------------------------------------------


class ProtocolAdapter(ABC):
    """Base class for every SCADA protocol adapter.

    Subclasses MUST implement:
      - ``start_server()`` / ``stop_server()``  (if ``supports_server`` is True)
      - ``start_client()`` / ``stop_client()``  (if ``supports_client`` is True)
      - ``health_check()``

    Subclasses SHOULD set:
      - ``protocol`` (ProtocolType)
      - ``supports_server`` / ``supports_client`` (bool)
      - call ``self._ingest(...)`` for every measurement received as a client.
    """

    protocol: ProtocolType
    supports_server: bool = True
    supports_client: bool = True

    def __init__(
        self,
        role: AdapterRole = AdapterRole.BOTH,
        on_measurement: Optional[MeasurementCallback] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.role: AdapterRole = role
        self._on_measurement: Optional[MeasurementCallback] = on_measurement
        self._config: Dict[str, Any] = dict(config or {})
        self._state: AdapterState = AdapterState.STOPPED
        self._metric: ProtocolMetric = ProtocolMetric(
            protocol=self.protocol,
            role=self.role,
            state=self._state,
        )
        self._server_task: Optional[Any] = None
        self._client_task: Optional[Any] = None

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        """Start the adapter according to its role."""
        if self._state == AdapterState.RUNNING:
            return
        self._state = AdapterState.STARTING
        self._metric.state = self._state
        try:
            if self.role in (AdapterRole.SERVER, AdapterRole.BOTH) and self.supports_server:
                self.start_server()
            if self.role in (AdapterRole.CLIENT, AdapterRole.BOTH) and self.supports_client:
                self.start_client()
            self._state = AdapterState.RUNNING
            self._metric.state = self._state
            logger.info(
                "[%s/%s] adapter started", self.protocol.value, self.role.value
            )
        except Exception as exc:
            self._state = AdapterState.ERROR
            self._metric.state = self._state
            self._metric.errors += 1
            self._metric.last_error = str(exc)
            logger.exception("[%s] failed to start: %s", self.protocol.value, exc)
            raise

    def stop(self) -> None:
        """Stop the adapter. Best-effort; logs but does not raise."""
        try:
            if self.role in (AdapterRole.CLIENT, AdapterRole.BOTH) and self.supports_client:
                self.stop_client()
        except Exception as exc:
            logger.warning("[%s] stop_client failed: %s", self.protocol.value, exc)
            self._metric.errors += 1
            self._metric.last_error = str(exc)
        try:
            if self.role in (AdapterRole.SERVER, AdapterRole.BOTH) and self.supports_server:
                self.stop_server()
        except Exception as exc:
            logger.warning("[%s] stop_server failed: %s", self.protocol.value, exc)
            self._metric.errors += 1
            self._metric.last_error = str(exc)
        self._state = AdapterState.STOPPED
        self._metric.state = self._state
        logger.info("[%s/%s] adapter stopped", self.protocol.value, self.role.value)

    # -- subclass hooks -----------------------------------------------------

    @abstractmethod
    def start_server(self) -> None: ...

    @abstractmethod
    def stop_server(self) -> None: ...

    @abstractmethod
    def start_client(self) -> None: ...

    @abstractmethod
    def stop_client(self) -> None: ...

    @abstractmethod
    def health_check(self) -> bool: ...

    # -- ingestion helper (used by client implementations) ------------------

    def _ingest(
        self,
        element_id: str,
        measurement_type: str,
        value: float,
        quality: str = "good",
        source: Optional[str] = None,
    ) -> None:
        """Push a measurement into the bridge callback (if registered)."""
        self._metric.points_ingested += 1
        self._metric.last_message_ts = time.time()
        if self._on_measurement is not None:
            try:
                self._on_measurement(
                    element_id,
                    measurement_type,
                    float(value),
                    quality,
                    source or self.protocol.value,
                )
            except Exception as exc:
                # Never let a bridge error kill the protocol loop.
                self._metric.errors += 1
                self._metric.last_error = f"bridge_error: {exc}"
                logger.exception(
                    "[%s] bridge callback raised: %s", self.protocol.value, exc
                )

    def _mark_served(self, n: int = 1) -> None:
        self._metric.points_served += n
        self._metric.last_message_ts = time.time()

    def _mark_error(self, msg: str) -> None:
        self._metric.errors += 1
        self._metric.last_error = msg
        logger.warning("[%s] %s", self.protocol.value, msg)

    # -- introspection ------------------------------------------------------

    @property
    def state(self) -> AdapterState:
        return self._state

    @property
    def metric(self) -> ProtocolMetric:
        return self._metric

    def is_running(self) -> bool:
        return self._state == AdapterState.RUNNING

    def describe(self) -> Dict[str, Any]:
        return {
            "protocol": self.protocol.value,
            "role": self.role.value,
            "supports_server": self.supports_server,
            "supports_client": self.supports_client,
            "state": self._state.value,
            "config_keys": list(self._config.keys()),
        }


# ---------------------------------------------------------------------------
# Protocol library availability probes (lazy, non-fatal)
# ---------------------------------------------------------------------------


def probe_modbus() -> Tuple[bool, str]:
    try:
        import pymodbus  # type: ignore

        return True, getattr(pymodbus, "__version__", "unknown")
    except Exception as exc:
        return False, str(exc)


def probe_opcua() -> Tuple[bool, str]:
    try:
        import asyncua  # type: ignore

        return True, getattr(asyncua, "__version__", "unknown")
    except Exception as exc:
        return False, str(exc)


def probe_iec104() -> Tuple[bool, str]:
    try:
        import c104  # type: ignore

        return True, getattr(c104, "__version__", "unknown") or "installed"
    except Exception as exc:
        return False, str(exc)


def probe_all() -> Dict[str, Dict[str, Any]]:
    """Probe every protocol library. Used by /health and config validation."""
    results: Dict[str, Dict[str, Any]] = {}
    for name, probe in (
        ("modbus_tcp", probe_modbus),
        ("opc_ua", probe_opcua),
        ("iec_104", probe_iec104),
    ):
        ok, info = probe()
        results[name] = {"available": ok, "info": info}
    return results


__all__ = [
    "ProtocolType",
    "AdapterRole",
    "AdapterState",
    "ProtocolMetric",
    "MeasurementCallback",
    "ProtocolAdapter",
    "probe_modbus",
    "probe_opcua",
    "probe_iec104",
    "probe_all",
]
