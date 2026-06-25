"""
scada_protocols.common.bridge
=============================
Glue between protocol adapters and the platform's existing ``SCADADatabase``.

The bridge is intentionally tiny:
- It receives ``(element_id, type_str, value, quality_str, source)`` callbacks
  from any protocol adapter (Modbus/OPC UA/IEC 104 client).
- It converts the payload to a ``scada_model.scada_model.Measurement`` and
  pushes it into the ``SCADADatabase`` (when one is registered).
- It also publishes a ``SCADAUpdateReceived`` event on the digital twin's
  ``EventBus`` (when one is registered), so the existing propagation chain
  in ``digital_twin/handlers.py`` kicks in automatically.

Both targets are optional and resolved lazily — the bridge degrades to
plain logging when neither is available, so it is safe to use in unit tests
and in environments where the digital_twin package is not installed.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


# Mapping from the loose ``measurement_type`` strings used in YAML configs to
# the canonical enum names defined in ``scada_model.scada_model.MeasurementType``.
# We do NOT import the enum here (would create a hard dependency on the host
# repo); the resolution happens lazily inside ``SCADAProtocolBridge.ingest``.
_TYPE_ALIASES: Dict[str, str] = {
    "voltage_magnitude": "VOLTAGE_MAGNITUDE",
    "voltage": "VOLTAGE_MAGNITUDE",
    "v": "VOLTAGE_MAGNITUDE",
    "vmag": "VOLTAGE_MAGNITUDE",
    "voltage_angle": "VOLTAGE_ANGLE",
    "vangle": "VOLTAGE_ANGLE",
    "current_magnitude": "CURRENT_MAGNITUDE",
    "current": "CURRENT_MAGNITUDE",
    "i": "CURRENT_MAGNITUDE",
    "imag": "CURRENT_MAGNITUDE",
    "current_angle": "CURRENT_ANGLE",
    "iangle": "CURRENT_ANGLE",
    "active_power": "ACTIVE_POWER",
    "p": "ACTIVE_POWER",
    "mw": "ACTIVE_POWER",
    "kw": "ACTIVE_POWER",
    "reactive_power": "REACTIVE_POWER",
    "q": "REACTIVE_POWER",
    "mvar": "REACTIVE_POWER",
    "kvar": "REACTIVE_POWER",
    "frequency": "FREQUENCY",
    "freq": "FREQUENCY",
    "hz": "FREQUENCY",
    "breaker_status": "BREAKER_STATUS",
    "switch_status": "BREAKER_STATUS",
    "tap_position": "TAP_POSITION",
    "tap": "TAP_POSITION",
    "temperature": "TEMPERATURE",
    "temp": "TEMPERATURE",
}

# Mapping from quality strings (case-insensitive) to ``QualityFlag`` enum names.
_QUALITY_ALIASES: Dict[str, str] = {
    "good": "GOOD",
    "ok": "GOOD",
    "valid": "GOOD",
    "questionable": "QUESTIONABLE",
    "uncertain": "QUESTIONABLE",
    "warning": "QUESTIONABLE",
    "invalid": "INVALID",
    "bad": "INVALID",
    "error": "INVALID",
    "missing": "MISSING",
    "timeout": "MISSING",
    "stale": "MISSING",
}


@dataclass
class BridgeStats:
    """Lightweight ingest stats exposed by the bridge."""

    total_ingested: int = 0
    by_protocol: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    by_quality: Dict[str, int] = field(default_factory=dict)
    last_element_id: Optional[str] = None
    last_ts: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_ingested": self.total_ingested,
            "by_protocol": dict(self.by_protocol),
            "by_type": dict(self.by_type),
            "by_quality": dict(self.by_quality),
            "last_element_id": self.last_element_id,
            "last_ts": self.last_ts,
        }


class SCADAProtocolBridge:
    """Receives measurements from protocol adapters and forwards them.

    Parameters
    ----------
    scada_db : optional
        A ``scada_model.scada_model.SCADADatabase`` instance. If None, the
        bridge will try to lazily create one on first ingest via
        ``_resolve_scada_db``.
    event_bus : optional
        A ``digital_twin.event_bus.EventBus`` instance. If provided, a
        ``SCADAUpdateReceived`` event is published on every successful ingest.
    """

    def __init__(
        self,
        scada_db: Any = None,
        event_bus: Any = None,
        default_quality: str = "good",
    ) -> None:
        self._scada_db = scada_db
        self._event_bus = event_bus
        self._default_quality = default_quality
        self._stats = BridgeStats()
        # Lazy caches
        self._MeasurementType: Any = None
        self._QualityFlag: Any = None
        self._Measurement: Any = None
        self._SCADAUpdateReceived: Any = None
        self._initialised = False

    # -- lazy resolution ----------------------------------------------------

    def _ensure_imports(self) -> bool:
        """Lazily import host-repo types. Returns True on success."""
        if self._initialised:
            return True
        try:
            from scada_model.scada_model import (  # type: ignore
                Measurement,
                MeasurementType,
                QualityFlag,
            )
            self._Measurement = Measurement
            self._MeasurementType = MeasurementType
            self._QualityFlag = QualityFlag
        except Exception as exc:
            logger.debug(
                "scada_model not importable; bridge will run in log-only mode (%s)",
                exc,
            )
            self._Measurement = None
            self._MeasurementType = None
            self._QualityFlag = None

        try:
            from digital_twin.event_bus import SCADAUpdateReceived  # type: ignore

            self._SCADAUpdateReceived = SCADAUpdateReceived
        except Exception as exc:
            logger.debug(
                "digital_twin.event_bus not importable; event publishing disabled (%s)",
                exc,
            )
            self._SCADAUpdateReceived = None

        self._initialised = True
        return True

    def _resolve_scada_db(self) -> Any:
        if self._scada_db is not None:
            return self._scada_db
        try:
            from scada_model.scada_model import SCADADatabase  # type: ignore

            self._scada_db = SCADADatabase()
            return self._scada_db
        except Exception as exc:
            logger.debug("could not auto-create SCADADatabase: %s", exc)
            return None

    # -- public API ---------------------------------------------------------

    def ingest(
        self,
        element_id: str,
        measurement_type: str,
        value: float,
        quality: Optional[str] = None,
        source: str = "unknown",
    ) -> bool:
        """Push a measurement into the SCADA database + event bus.

        Returns True if the measurement was accepted by the SCADADatabase,
        False otherwise (e.g. when no SCADADatabase is available — the bridge
        still logs the point and updates its stats).
        """
        self._ensure_imports()

        q_str = (quality or self._default_quality or "good").strip().lower()
        q_enum_name = _QUALITY_ALIASES.get(q_str, "GOOD")
        t_str = (measurement_type or "").strip().lower()
        t_enum_name = _TYPE_ALIASES.get(t_str, "VOLTAGE_MAGNITUDE")

        # Update stats regardless of whether SCADADatabase is available.
        self._stats.total_ingested += 1
        self._stats.by_protocol[source] = self._stats.by_protocol.get(source, 0) + 1
        self._stats.by_type[t_enum_name] = self._stats.by_type.get(t_enum_name, 0) + 1
        self._stats.by_quality[q_enum_name] = self._stats.by_quality.get(q_enum_name, 0) + 1
        self._stats.last_element_id = element_id
        self._stats.last_ts = time.time()

        # Try to push into the SCADADatabase.
        pushed = False
        db = self._resolve_scada_db()
        if db is not None and self._Measurement is not None:
            try:
                mtype = self._MeasurementType[t_enum_name]
                qflag = self._QualityFlag[q_enum_name]
                measurement = self._Measurement(
                    measurement_id=f"{source}::{element_id}::{t_enum_name}",
                    measurement_type=mtype,
                    element_id=element_id,
                    value=float(value),
                    timestamp=time.time(),
                    quality=qflag,
                    confidence=1.0 if q_enum_name == "GOOD" else 0.5,
                )
                db.add_measurement(measurement)
                pushed = True
            except Exception as exc:
                logger.warning(
                    "bridge: SCADADatabase.add_measurement failed for %s/%s: %s",
                    element_id,
                    t_enum_name,
                    exc,
                )
        else:
            logger.debug(
                "bridge ingest (log-only): src=%s elem=%s type=%s val=%.4f q=%s",
                source,
                element_id,
                t_enum_name,
                float(value),
                q_enum_name,
            )

        # Try to publish an event on the digital twin EventBus.
        # The SCADAUpdateReceived event in digital_twin.event_bus has this shape:
        #   SCADAUpdateReceived(
        #     source=str, measurements=[{element_id, type, value, quality, ts}, ...],
        #     switch_statuses={element_id: status}, metadata={...}
        #   )
        if self._event_bus is not None and self._SCADAUpdateReceived is not None:
            try:
                event = self._SCADAUpdateReceived(
                    source=source,
                    measurements=[
                        {
                            "element_id": element_id,
                            "type": t_enum_name,
                            "value": float(value),
                            "quality": q_enum_name,
                            "ts": time.time(),
                        }
                    ],
                    metadata={
                        "protocol_source": source,
                        "raw_measurement_type": measurement_type,
                    },
                )
                # EventBus.publish signature in the repo accepts a DomainEvent.
                try:
                    self._event_bus.publish(event)
                except TypeError:
                    # Fall back to dict payload if the EventBus API differs.
                    self._event_bus.publish(
                        {
                            "type": "scada_update_received",
                            "source": source,
                            "element_id": element_id,
                            "measurement_type": t_enum_name,
                            "value": float(value),
                            "quality": q_enum_name,
                        }
                    )
            except Exception as exc:
                logger.debug("bridge: event publish failed: %s", exc)

        return pushed

    # -- introspection ------------------------------------------------------

    @property
    def stats(self) -> BridgeStats:
        return self._stats

    def has_scada_db(self) -> bool:
        return self._resolve_scada_db() is not None

    def has_event_bus(self) -> bool:
        return self._event_bus is not None


def make_callback(bridge: SCADAProtocolBridge) -> Callable[..., None]:
    """Return a closure suitable as the ``on_measurement`` adapter callback.

    The closure swallows all exceptions from ``bridge.ingest`` so that a
    broken bridge (e.g. SCADADatabase failure, event bus serialization error)
    can never kill the protocol receive loop.
    """

    def _cb(
        element_id: str,
        measurement_type: str,
        value: float,
        quality: str,
        source: str,
    ) -> None:
        try:
            bridge.ingest(element_id, measurement_type, value, quality, source)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("SCADAProtocolBridge callback swallowed: %s", exc)

    return _cb


__all__ = [
    "BridgeStats",
    "SCADAProtocolBridge",
    "make_callback",
]
