"""
scada_protocols.iec104.asdu_mapper
==================================
Maps IEC 60870-5-104 ASDU type identifiers to the platform's
``MeasurementType`` enum names and back.

Each point in the YAML ``iec104.point_map`` is configured with:
- ``ca``    — common address of the station
- ``ioa``   — information object address
- ``element_id`` — which bus/line/transformer this point measures
- ``measurement_type`` — one of the alias strings from
  ``scada_protocols.common.bridge._TYPE_ALIASES``
- ``type_id`` — ASDU type identifier string (e.g. ``M_ME_NC_1``)
- ``cot`` (optional) — Cause of Transmission, default ``PERIODIC``

The mapper decodes an incoming ``c104.Information`` object to a float and
pairs it with the configured ``element_id`` / ``measurement_type``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ASDU type identifiers we care about for monitoring (server -> client).
# The keys mirror ``c104.Type`` enum names.
_MONITORING_TYPES = {
    # Single-point information
    "M_SP_NA_1": "breaker_status",      # single point (0/1)
    "M_SP_TA_1": "breaker_status",      # single point with timestamp
    # Double-point information (used for switch status: 0=undefined, 1=off, 2=on, 3=undefined)
    "M_DP_NA_1": "breaker_status",
    "M_DP_TA_1": "breaker_status",
    # Measured values, normalized [-1..1] — typical for voltage/current in p.u.
    "M_ME_NA_1": "voltage_magnitude",   # normalized
    "M_ME_TA_1": "voltage_magnitude",
    # Measured values, scaled (integer)
    "M_ME_NB_1": "active_power",
    "M_ME_TB_1": "active_power",
    # Measured values, short floating point — most common in modern RTUs
    "M_ME_NC_1": "voltage_magnitude",
    "M_ME_TF_1": "voltage_magnitude",
    # Integrated totals (counters)
    "M_IT_NA_1": "energy",
    "M_IT_TA_1": "energy",
}

# Default COT for spontaneous transmission in our adapters.
DEFAULT_COT = "PERIODIC"


@dataclass
class IEC104Point:
    ca: int
    ioa: int
    element_id: str
    measurement_type: str
    type_id: str
    cot: str = DEFAULT_COT
    scale: float = 1.0
    offset: float = 0.0
    unit: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ca": self.ca,
            "ioa": self.ioa,
            "element_id": self.element_id,
            "measurement_type": self.measurement_type,
            "type_id": self.type_id,
            "cot": self.cot,
            "scale": self.scale,
            "offset": self.offset,
            "unit": self.unit,
        }


class PointMap:
    """Bidirectional lookup between (ca, ioa) and IEC104Point."""

    def __init__(self, entries: Optional[List[Dict[str, Any]]] = None) -> None:
        self._by_ioa: Dict[int, IEC104Point] = {}
        self._by_element_type: Dict[tuple, IEC104Point] = {}
        if entries:
            for raw in entries:
                self.add_entry(raw)

    def add_entry(self, raw: Dict[str, Any]) -> IEC104Point:
        pt = IEC104Point(
            ca=int(raw["ca"]),
            ioa=int(raw["ioa"]),
            element_id=str(raw["element_id"]),
            measurement_type=str(raw["measurement_type"]),
            type_id=str(raw.get("type_id", "M_ME_NC_1")),
            cot=str(raw.get("cot", DEFAULT_COT)),
            scale=float(raw.get("scale", 1.0)),
            offset=float(raw.get("offset", 0.0)),
            unit=str(raw.get("unit", "")),
        )
        self._by_ioa[pt.ioa] = pt
        self._by_element_type[(pt.element_id, pt.measurement_type)] = pt
        return pt

    def find_by_ioa(self, ioa: int) -> Optional[IEC104Point]:
        return self._by_ioa.get(ioa)

    def find_by_element_type(
        self, element_id: str, measurement_type: str
    ) -> Optional[IEC104Point]:
        return self._by_element_type.get((element_id, measurement_type))

    def all_points(self) -> List[IEC104Point]:
        return list(self._by_ioa.values())

    def __len__(self) -> int:
        return len(self._by_ioa)


# ---------------------------------------------------------------------------
# Codec helpers
# ---------------------------------------------------------------------------


def decode_information(info: Any, point: IEC104Point) -> Optional[float]:
    """Decode an ``c104.Information`` object (or any duck-typed object) to a float.

    Dispatch is attribute-based rather than class-name-based so that the
    function works with both real ``c104`` info objects and lightweight
    test doubles. We check for the presence of characteristic attributes
    in priority order:

    1. ``actual`` (NormalizedInfo)  — value in [-1.0, 1.0]
    2. ``on``     (SingleInfo / DoubleInfo) — boolean
    3. ``value``  (ShortInfo / ScaledInfo / BinaryCounterInfo / generic)
    """
    if info is None:
        return None

    raw: Optional[float] = None
    try:
        # NormalizedInfo carries an ``actual`` NormalizedFloat.
        actual = getattr(info, "actual", None)
        if actual is not None:
            raw = float(actual)
        else:
            # SingleInfo / DoubleInfo carry an ``on`` boolean.
            on = getattr(info, "on", None)
            if on is not None:
                raw = 1.0 if bool(on) else 0.0
            else:
                # Generic fallback: any object exposing ``value``.
                v = getattr(info, "value", None)
                if v is not None:
                    raw = float(v)
    except Exception as exc:
        logger.debug("decode_information failed: %s", exc)
        return None

    if raw is None:
        return None

    # Apply scale/offset
    return raw * point.scale + point.offset


def decode_quality(info: Any) -> str:
    """Decode a ``c104.Information.quality`` to a bridge-compatible string."""
    if info is None:
        return "missing"
    q = getattr(info, "quality", None)
    if q is None:
        return "good"
    try:
        if getattr(q, "is_good", lambda: False)():
            return "good"
        if getattr(q, "Invalid", False):
            return "invalid"
        if getattr(q, "NonTopical", False) or getattr(q, "ElapsedTimeInvalid", False):
            return "questionable"
        if getattr(q, "Blocked", False) or getattr(q, "Substituted", False):
            return "questionable"
    except Exception:
        pass
    return "good"


# Map an ASDU type name (e.g. ``"M_ME_NC_1"``) to a default measurement_type.
def default_measurement_type_for(type_id: str) -> str:
    return _MONITORING_TYPES.get(type_id, "voltage_magnitude")


# Map our internal measurement_type alias back to a suggested ASDU type id.
_MEASUREMENT_TYPE_TO_ASDU = {
    "voltage_magnitude": "M_ME_NC_1",
    "voltage_angle": "M_ME_NC_1",
    "current_magnitude": "M_ME_NC_1",
    "current_angle": "M_ME_NC_1",
    "active_power": "M_ME_NC_1",
    "reactive_power": "M_ME_NC_1",
    "frequency": "M_ME_NC_1",
    "breaker_status": "M_SP_NA_1",
    "tap_position": "M_ST_NA_1",
    "temperature": "M_ME_NC_1",
}


def suggested_asdu_type(measurement_type: str) -> str:
    return _MEASUREMENT_TYPE_TO_ASDU.get(measurement_type, "M_ME_NC_1")


__all__ = [
    "IEC104Point",
    "PointMap",
    "DEFAULT_COT",
    "decode_information",
    "decode_quality",
    "default_measurement_type_for",
    "suggested_asdu_type",
]
