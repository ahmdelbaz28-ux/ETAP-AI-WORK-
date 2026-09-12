"""integrations/etap_component_importer.py — ETAP .etp / .etpx XML Component Importer.

Parses ETAP project and library XML files to extract standardized component records:
- <Cable> elements → cable components
- <Transformer> elements → transformer components
- <Breaker> / <CircuitBreaker> elements → circuit breaker components
- <Relay> / <ProtectiveDevice> elements → protection components

Uses defusedxml for entity expansion protection and secure parsing.
"""

from __future__ import annotations

import importlib
import logging
import re
import uuid
from typing import Any, Optional

try:
    _defused_et = importlib.import_module("defusedxml.ElementTree")
    ET = _defused_et
except ImportError:
    import xml.etree.ElementTree as ET  # type: ignore

logger = logging.getLogger("etap.component_importer")


def _safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely convert value to float, ignoring non-numeric characters."""
    if val is None:
        return default
    try:
        cleaned = re.sub(r"[^\d.-]", "", str(val))
        return float(cleaned) if cleaned else default
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: Optional[int] = None) -> Optional[int]:
    """Safely convert value to int."""
    if val is None:
        return default
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return default


class ETAPComponentImporter:
    """Parser and importer for ETAP project XML (*.etp, *.etpx) component definitions."""

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def parse_xml_content(self, content: bytes | str) -> list[dict[str, Any]]:
        """Parse ETAP XML content and extract list of normalized component records."""
        self.warnings = []
        if isinstance(content, str):
            content = content.encode("utf-8")

        try:
            root = ET.fromstring(content)
        except Exception as err:
            logger.error("Failed to parse ETAP XML: %s", err)
            raise ValueError(f"Invalid ETAP XML: {err}") from err

        components: list[dict[str, Any]] = []

        components.extend(self._extract_cables(root))
        components.extend(self._extract_transformers(root))
        components.extend(self._extract_breakers(root))
        components.extend(self._extract_relays(root))

        return components

    def _extract_cables(self, root: Any) -> list[dict[str, Any]]:
        cables: list[dict[str, Any]] = []
        for elem in root.iter():
            tag = elem.tag.split("}")[-1].lower()
            if tag in ("cable", "cabledata", "branch_cable"):
                name = elem.attrib.get("Name") or elem.attrib.get("ID") or elem.findtext("Name") or f"Cable-{uuid.uuid4().hex[:6]}"
                mat = elem.attrib.get("Material") or elem.findtext("Material") or "Copper"
                ins = elem.attrib.get("Insulation") or elem.findtext("Insulation") or "XLPE"
                kv = _safe_float(elem.attrib.get("kV") or elem.attrib.get("RatedkV") or elem.findtext("kV"), 1.0)
                cores = _safe_int(elem.attrib.get("Cores") or elem.attrib.get("NoOfCores") or elem.findtext("Cores"), 1)
                size = _safe_float(elem.attrib.get("Size") or elem.attrib.get("SizeMM2") or elem.findtext("Size"), 50.0)
                r = _safe_float(elem.attrib.get("R") or elem.attrib.get("R_per_km") or elem.findtext("R"), 0.387)
                x = _safe_float(elem.attrib.get("X") or elem.attrib.get("X_per_km") or elem.findtext("X"), 0.093)
                ampacity = _safe_float(elem.attrib.get("Ampacity") or elem.attrib.get("CurrentRating") or elem.findtext("Ampacity"), 150.0)

                comp_id = f"cable-etap-{uuid.uuid4().hex[:8]}"
                cables.append({
                    "id": comp_id,
                    "type": "cable",
                    "category": "ETAP Imported Cables",
                    "subcategory": f"{mat}/{ins} {kv}kV",
                    "name": str(name),
                    "manufacturer": elem.attrib.get("Manufacturer") or elem.findtext("Manufacturer") or "ETAP Library",
                    "model_number": elem.attrib.get("Model") or elem.findtext("Model") or None,
                    "specs": {
                        "conductor_material": mat.lower(),
                        "insulation": ins.lower(),
                        "voltage_rating_kv": kv,
                        "cores": cores,
                        "cross_section_mm2": size,
                        "resistance_ohm_per_km": r,
                        "reactance_ohm_per_km": x,
                        "current_rating_a": ampacity,
                    },
                    "standards": ["IEC 60364", "IEC 60502"],
                    "tags": ["etap-import", "cable", mat.lower(), ins.lower()],
                    "is_verified": True,
                    "source": "etap-import",
                })
        return cables

    def _extract_transformers(self, root: Any) -> list[dict[str, Any]]:
        transformers: list[dict[str, Any]] = []
        for elem in root.iter():
            tag = elem.tag.split("}")[-1].lower()
            if tag in ("transformer", "transformer2w", "xfmr"):
                name = elem.attrib.get("Name") or elem.attrib.get("ID") or elem.findtext("Name") or f"XFMR-{uuid.uuid4().hex[:6]}"
                mva = _safe_float(elem.attrib.get("MVA") or elem.attrib.get("RatedMVA") or elem.findtext("MVA"))
                kva = _safe_float(elem.attrib.get("kVA") or elem.attrib.get("RatedkVA") or elem.findtext("kVA"))
                rated_power = mva * 1000.0 if mva else (kva if kva else 1000.0)

                prim_kv = _safe_float(elem.attrib.get("PriKV") or elem.attrib.get("PrimkV") or elem.findtext("PriKV"), 11.0)
                sec_kv = _safe_float(elem.attrib.get("SecKV") or elem.attrib.get("SeckV") or elem.findtext("SecKV"), 0.415)
                z_pct = _safe_float(elem.attrib.get("Z") or elem.attrib.get("ZPercent") or elem.findtext("Z"), 5.0)
                xr = _safe_float(elem.attrib.get("XR") or elem.attrib.get("XRRatio") or elem.findtext("XR"), 6.0)
                vector = elem.attrib.get("VectorGroup") or elem.findtext("VectorGroup") or "Dyn11"

                comp_id = f"xfmr-etap-{uuid.uuid4().hex[:8]}"
                transformers.append({
                    "id": comp_id,
                    "type": "transformer",
                    "category": "ETAP Imported Transformers",
                    "subcategory": "Distribution & Power Transformers",
                    "name": str(name),
                    "manufacturer": elem.attrib.get("Manufacturer") or elem.findtext("Manufacturer") or "ETAP Library",
                    "model_number": elem.attrib.get("Model") or elem.findtext("Model") or None,
                    "specs": {
                        "rated_power_kva": rated_power,
                        "primary_voltage_kv": prim_kv,
                        "secondary_voltage_kv": sec_kv,
                        "impedance_percent": z_pct,
                        "xr_ratio": xr,
                        "vector_group": vector,
                        "phases": 3,
                    },
                    "standards": ["IEEE C57.12.00", "IEC 60076"],
                    "tags": ["etap-import", "transformer", f"{rated_power}kva"],
                    "is_verified": True,
                    "source": "etap-import",
                })
        return transformers

    def _extract_breakers(self, root: Any) -> list[dict[str, Any]]:
        breakers: list[dict[str, Any]] = []
        for elem in root.iter():
            tag = elem.tag.split("}")[-1].lower()
            if tag in ("breaker", "circuitbreaker", "hvcbreaper", "lvcbreaper", "cb"):
                name = elem.attrib.get("Name") or elem.attrib.get("ID") or elem.findtext("Name") or f"CB-{uuid.uuid4().hex[:6]}"
                rated_kv = _safe_float(elem.attrib.get("kV") or elem.attrib.get("RatedkV") or elem.findtext("kV"), 0.415)
                rated_a = _safe_float(elem.attrib.get("RatedA") or elem.attrib.get("ContinuousA") or elem.attrib.get("Amps") or elem.findtext("Amps"), 630.0)
                ka = _safe_float(elem.attrib.get("BreakingkA") or elem.attrib.get("kA") or elem.attrib.get("InterruptingkA") or elem.findtext("kA"), 36.0)
                cb_type = elem.attrib.get("Type") or elem.findtext("Type") or ("VCB" if rated_kv >= 1.0 else "MCCB")

                comp_id = f"cb-etap-{uuid.uuid4().hex[:8]}"
                breakers.append({
                    "id": comp_id,
                    "type": "breaker",
                    "category": "ETAP Imported Breakers",
                    "subcategory": f"{cb_type} {rated_kv}kV",
                    "name": str(name),
                    "manufacturer": elem.attrib.get("Manufacturer") or elem.findtext("Manufacturer") or "ETAP Library",
                    "model_number": elem.attrib.get("Model") or elem.findtext("Model") or None,
                    "specs": {
                        "rated_voltage_kv": rated_kv,
                        "rated_current_a": rated_a,
                        "breaking_capacity_ka": ka,
                        "breaker_type": cb_type,
                        "poles": 3,
                    },
                    "standards": ["IEC 62271-100" if rated_kv >= 1.0 else "IEC 60947-2"],
                    "tags": ["etap-import", "breaker", cb_type.lower(), f"{rated_a}a"],
                    "is_verified": True,
                    "source": "etap-import",
                })
        return breakers

    def _extract_relays(self, root: Any) -> list[dict[str, Any]]:
        relays: list[dict[str, Any]] = []
        for elem in root.iter():
            tag = elem.tag.split("}")[-1].lower()
            if tag in ("relay", "protectivedevice", "ocr"):
                name = elem.attrib.get("Name") or elem.attrib.get("ID") or elem.findtext("Name") or f"Relay-{uuid.uuid4().hex[:6]}"
                function_ansi = elem.attrib.get("ANSI") or elem.attrib.get("Function") or elem.findtext("Function") or "50/51"
                curve = elem.attrib.get("Curve") or elem.attrib.get("CurveType") or elem.findtext("Curve") or "IEC Normal Inverse"

                comp_id = f"relay-etap-{uuid.uuid4().hex[:8]}"
                relays.append({
                    "id": comp_id,
                    "type": "relay",
                    "category": "ETAP Imported Protection",
                    "subcategory": "Protective Relays",
                    "name": str(name),
                    "manufacturer": elem.attrib.get("Manufacturer") or elem.findtext("Manufacturer") or "ETAP Library",
                    "model_number": elem.attrib.get("Model") or elem.findtext("Model") or None,
                    "specs": {
                        "ansi_function": function_ansi,
                        "curve_type": curve,
                        "phase_pickup_pu": _safe_float(elem.attrib.get("Pickup") or elem.findtext("Pickup"), 1.0),
                        "time_dial": _safe_float(elem.attrib.get("TimeDial") or elem.findtext("TimeDial"), 0.1),
                    },
                    "standards": ["IEC 60255", "IEEE C37.112"],
                    "tags": ["etap-import", "relay", "protection", function_ansi.lower()],
                    "is_verified": True,
                    "source": "etap-import",
                })
        return relays


etap_importer = ETAPComponentImporter()
