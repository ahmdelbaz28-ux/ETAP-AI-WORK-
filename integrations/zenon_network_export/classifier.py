"""Zenon Raw Dump Classifier.

Translates raw variable/screen dumps from zenon SCADA into the canonical
ZenonNetworkExport v1 contract using configurable element patterns and field mappings.

Rules:
- Strictly ordered classification rules (BB\\d+ -> bus, XCBR -> breaker, etc.).
- Unclassified items are returned in unmapped[] with explicit warnings (no guessing).
- Missing topology (from_bus/to_bus/bus) places items into incomplete[] with explicit reasons.
- Zero synthetic electrical defaults are invented.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from integrations.zenon_network_export.contract import (
    ZenonBreaker,
    ZenonBus,
    ZenonCable,
    ZenonCapacitor,
    ZenonGenerator,
    ZenonLine,
    ZenonLoad,
    ZenonMotor,
    ZenonNetworkExport,
    ZenonProjectMetadata,
    ZenonReactor,
    ZenonRelay,
    ZenonSource,
    ZenonSwitch,
    ZenonTransformer,
)
from integrations.zenon_network_export.mapping import ZenonFieldMapper
from integrations.zenon_network_export.raw_dump import ZenonRawDump

logger = logging.getLogger(__name__)

DEFAULT_PATTERNS_PATH = Path("config/zenon_element_patterns.yaml")


@dataclass
class ClassifyResult:
    """Result of classifying a ZenonRawDump into a ZenonNetworkExport contract."""

    contract: ZenonNetworkExport
    unmapped: list[dict[str, Any]] = field(default_factory=list)
    incomplete: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


class ZenonClassifier:
    """Classifies raw variables and screen elements into canonical electrical objects."""

    def __init__(
        self,
        patterns_path: str | Path | None = None,
        field_mapper: Optional[ZenonFieldMapper] = None,
    ) -> None:
        self.patterns_path = Path(patterns_path) if patterns_path else DEFAULT_PATTERNS_PATH
        self.field_mapper = field_mapper or ZenonFieldMapper()
        self.classification_rules: list[dict[str, Any]] = []
        self.branch_topology_pattern: Optional[re.Pattern] = None
        self.attribute_patterns: dict[str, list[re.Pattern]] = {}
        self._load_patterns()

    def _load_patterns(self) -> None:
        if self.patterns_path.is_file():
            try:
                with open(self.patterns_path, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                for rule in cfg.get("classification_rules", []):
                    compiled = [re.compile(p) for p in rule.get("patterns", [])]
                    self.classification_rules.append(
                        {"type": rule.get("type"), "compiled": compiled}
                    )
                branch_pat = cfg.get("branch_topology_pattern")
                if branch_pat:
                    self.branch_topology_pattern = re.compile(branch_pat)
                for attr, pats in cfg.get("attribute_patterns", {}).items():
                    self.attribute_patterns[attr] = [re.compile(p) for p in pats]
                logger.info("Loaded element patterns from %s", self.patterns_path)
            except Exception as e:
                logger.warning("Failed to load %s: %s; using builtin rules", self.patterns_path, e)
                self._apply_builtin_rules()
        else:
            self._apply_builtin_rules()

    def _apply_builtin_rules(self) -> None:
        builtins = [
            (
                "transformer",
                [
                    r"(?i)^TR[_\-.]?\w+",
                    r"(?i)^XF[_\-.]?\w+",
                    r"(?i).*_XFMR[_\-.]?\w*",
                    r"(?i).*_TR[_\-.]?\d+.*",
                ],
            ),
            ("line", [r"(?i)^LINE[_\-.]?\w+", r"(?i).*_LINE[_\-.]?\w*", r"(?i)^LN[_\-.]?\w+"]),
            ("cable", [r"(?i)^CBL[_\-.]?\w+", r"(?i)^CABLE[_\-.]?\w+", r"(?i).*_CABLE[_\-.]?\w*"]),
            ("breaker", [r"(?i).*XCBR.*", r"(?i)^CB[_\-.]?\w+", r"(?i).*_CB[_\-.]?\w*"]),
            (
                "switch",
                [
                    r"(?i).*XSWI.*",
                    r"(?i)^SW[_\-.]?\w+",
                    r"(?i).*_SW[_\-.]?\w*",
                    r"(?i).*DISC[_\-.]?\w*",
                ],
            ),
            ("load", [r"(?i)^LOAD[_\-.]?\w+", r"(?i)^LD[_\-.]?\w+", r"(?i).*_LOAD[_\-.]?\w*"]),
            (
                "generator",
                [
                    r"(?i)^GEN[_\-.]?\w+",
                    r"(?i).*_GENERATOR[_\-.]?\w*",
                    r"(?i)^PV[_\-.]?\w*",
                    r"(?i)^DG[_\-.]?\w*",
                ],
            ),
            (
                "source",
                [
                    r"(?i)^GRID[_\-.]?\w*",
                    r"(?i)^SOURCE[_\-.]?\w*",
                    r"(?i)^INCOMER[_\-.]?\w*",
                    r"(?i).*_SOURCE[_\-.]?\w*",
                ],
            ),
            ("motor", [r"(?i)^MTR[_\-.]?\w+", r"(?i)^MOTOR[_\-.]?\w+", r"(?i).*_MOTOR[_\-.]?\w*"]),
            (
                "relay",
                [r"(?i).*PTOC.*", r"(?i).*PDIS.*", r"(?i)^RELAY[_\-.]?\w+", r"(?i)^RLY[_\-.]?\w*"],
            ),
            ("capacitor", [r"(?i)^CAP[_\-.]?\w+", r"(?i).*_CAPACITOR[_\-.]?\w*"]),
            ("reactor", [r"(?i)^REACT[_\-.]?\w+", r"(?i).*_REACTOR[_\-.]?\w*"]),
            (
                "bus",
                [
                    r"(?i)^BB\d+",
                    r"(?i)^BUS[_\-.]?\w+",
                    r"(?i).*_BUSBAR[_\-.]?\w*",
                    r"(?i).*_BB\d+.*",
                ],
            ),
        ]
        self.classification_rules = [
            {"type": t, "compiled": [re.compile(p) for p in pats]} for t, pats in builtins
        ]
        self.branch_topology_pattern = re.compile(
            r"(?i)^(?:LINE|CBL|CABLE|XF|TR|CB|SW|REACT)_(?P<from_bus>[A-Za-z0-9_]+)_(?P<to_bus>[A-Za-z0-9_]+)$"
        )

    def _classify_type(self, identifier: str) -> Optional[str]:
        for rule in self.classification_rules:
            for pat in rule["compiled"]:
                if pat.search(identifier):
                    return rule["type"]
        return None

    def _split_tag(self, var_name: str) -> tuple[str, Optional[str]]:
        """Splits a variable name into (element_id, attribute_name).

        Handles dots, colons, or trailing underscores.
        e.g. 'BUS1.V_MAG' -> ('BUS1', 'V_MAG')
             'LINE_B1_B2.R' -> ('LINE_B1_B2', 'R')
             'BB01' -> ('BB01', None)
        """
        for sep in [".", ":", "/"]:
            if sep in var_name:
                parts = var_name.rsplit(sep, 1)
                return parts[0], parts[1]

        # Check attribute patterns against suffix
        for attr, pats in self.attribute_patterns.items():
            for pat in pats:
                m = pat.search(var_name)
                if m:
                    elem_part = var_name[: m.start()].rstrip("._-")
                    if elem_part:
                        return elem_part, attr

        return var_name, None

    def _normalize_status(self, val: Any) -> Optional[str]:
        if val is None:
            return None
        s = str(val).strip().lower()
        if s in ("1", "true", "closed", "close", "normal_closed"):
            return "closed"
        if s in ("0", "false", "open", "normal_open"):
            return "open"
        if s in ("connected", "in_service"):
            return "connected"
        if s in ("disconnected", "out_of_service"):
            return "disconnected"
        return None

    def classify_raw_dump(self, raw_dump: ZenonRawDump) -> ClassifyResult:
        """Classify a ZenonRawDump into a ZenonNetworkExport contract."""
        warnings: list[str] = []
        errors: list[str] = []
        unmapped: list[dict[str, Any]] = []
        incomplete: list[dict[str, Any]] = []

        # Diagnostics from raw dump forwarded as warnings
        for diag in raw_dump.diagnostics:
            warnings.append(f"Zenon Collector Diagnostic: {diag}")

        # Group raw variables by element identifier
        elements_data: dict[str, dict[str, Any]] = {}
        var_records: dict[str, list[dict[str, Any]]] = {}

        for var in raw_dump.variables:
            elem_id, attr = self._split_tag(var.name)
            # If identification has LN or hint, check it too
            if elem_id not in elements_data:
                elements_data[elem_id] = {
                    "id": elem_id,
                    "name": elem_id,
                    "raw_attributes": {},
                    "identification": var.identification,
                    "source_ref": var.name,
                }
                var_records[elem_id] = []

            var_records[elem_id].append(var.model_dump())

            if attr:
                elements_data[elem_id]["raw_attributes"][attr] = var.value
            else:
                # Store whole variable value if scalar
                if var.value is not None:
                    elements_data[elem_id]["raw_attributes"]["VALUE"] = var.value

        # Screens integration: augment elements or link topology
        for screen in raw_dump.screens:
            for el in screen.elements:
                elem_id, _ = self._split_tag(el.name)
                if elem_id not in elements_data:
                    elements_data[elem_id] = {
                        "id": elem_id,
                        "name": el.name,
                        "raw_attributes": {},
                        "source_ref": f"Screen:{screen.name}/{el.name}",
                    }
                    var_records[elem_id] = []
                for linked in el.linked_variables:
                    l_elem, l_attr = self._split_tag(linked)
                    if l_attr:
                        elements_data[elem_id]["raw_attributes"][f"LINKED_{l_attr}"] = linked
                    else:
                        if self._classify_type(l_elem) == "bus":
                            elements_data[elem_id]["raw_attributes"]["BUS"] = l_elem

        # Containers for classified contract elements
        buses: list[ZenonBus] = []
        lines: list[ZenonLine] = []
        cables: list[ZenonCable] = []
        transformers: list[ZenonTransformer] = []
        breakers: list[ZenonBreaker] = []
        switches: list[ZenonSwitch] = []
        loads: list[ZenonLoad] = []
        generators: list[ZenonGenerator] = []
        motors: list[ZenonMotor] = []
        relays: list[ZenonRelay] = []
        capacitors: list[ZenonCapacitor] = []
        reactors: list[ZenonReactor] = []
        sources: list[ZenonSource] = []

        # Classify each element
        for elem_id, item in elements_data.items():
            # Check element ID and identification for classification
            classifier_target = elem_id
            if item.get("identification"):
                classifier_target = f"{elem_id} {item['identification']}"

            elem_type = self._classify_type(classifier_target)
            if not elem_type:
                # Unmapped element -> record and warn without fabricating type
                msg = f"Element '{elem_id}' could not be classified into any known electrical type."
                warnings.append(msg)
                unmapped.append(
                    {
                        "id": elem_id,
                        "name": item["name"],
                        "reason": "unrecognized_element_type",
                        "variables": var_records.get(elem_id, []),
                    }
                )
                continue

            raw_attrs = item["raw_attributes"]
            # Apply field mapping
            canonical_attrs, map_warns = self.field_mapper.map_element_attributes(
                elem_type, elem_id, raw_attrs
            )
            warnings.extend(map_warns)

            # Topology deduction
            from_bus: Optional[str] = (
                canonical_attrs.get("from_bus")
                or raw_attrs.get("from_bus")
                or raw_attrs.get("FROM_BUS")
            )
            to_bus: Optional[str] = (
                canonical_attrs.get("to_bus") or raw_attrs.get("to_bus") or raw_attrs.get("TO_BUS")
            )
            bus: Optional[str] = (
                canonical_attrs.get("bus") or raw_attrs.get("bus") or raw_attrs.get("BUS")
            )

            if self.branch_topology_pattern:
                m = self.branch_topology_pattern.match(elem_id)
                if m:
                    if not from_bus:
                        from_bus = m.group("from_bus")
                    if not to_bus:
                        to_bus = m.group("to_bus")

            # Check completeness and build domain element
            if elem_type == "bus":
                base_kv = canonical_attrs.get("base_kv")
                if base_kv is not None:
                    try:
                        base_kv = float(base_kv)
                    except (ValueError, TypeError):
                        base_kv = None
                v_mag = canonical_attrs.get("v_mag")
                if v_mag is not None:
                    try:
                        v_mag = float(v_mag)
                    except (ValueError, TypeError):
                        v_mag = None
                v_ang = canonical_attrs.get("v_ang")
                if v_ang is not None:
                    try:
                        v_ang = float(v_ang)
                    except (ValueError, TypeError):
                        v_ang = None

                buses.append(
                    ZenonBus(
                        id=elem_id,
                        name=item["name"],
                        base_kv=base_kv,
                        v_mag=v_mag,
                        v_ang=v_ang,
                        bus_type=canonical_attrs.get("bus_type"),
                        source_ref=item.get("source_ref"),
                        metadata={"raw_attributes": raw_attrs},
                    )
                )

            elif elem_type == "line":
                if not from_bus or not to_bus:
                    incomplete.append(
                        {
                            "id": elem_id,
                            "type": "line",
                            "reason": "missing_terminal_buses",
                            "missing_fields": [
                                f for f, v in [("from_bus", from_bus), ("to_bus", to_bus)] if not v
                            ],
                        }
                    )
                    continue
                lines.append(
                    ZenonLine(
                        id=elem_id,
                        name=item["name"],
                        from_bus=from_bus,
                        to_bus=to_bus,
                        r_pu=float(canonical_attrs["r_pu"])
                        if "r_pu" in canonical_attrs and canonical_attrs["r_pu"] is not None
                        else None,
                        x_pu=float(canonical_attrs["x_pu"])
                        if "x_pu" in canonical_attrs and canonical_attrs["x_pu"] is not None
                        else None,
                        b_pu=float(canonical_attrs["b_pu"])
                        if "b_pu" in canonical_attrs and canonical_attrs["b_pu"] is not None
                        else None,
                        length_km=float(canonical_attrs["length_km"])
                        if "length_km" in canonical_attrs
                        and canonical_attrs["length_km"] is not None
                        else None,
                        rating_mva=float(canonical_attrs["rating_mva"])
                        if "rating_mva" in canonical_attrs
                        and canonical_attrs["rating_mva"] is not None
                        else None,
                        rating_a=float(canonical_attrs["rating_a"])
                        if "rating_a" in canonical_attrs and canonical_attrs["rating_a"] is not None
                        else None,
                        source_ref=item.get("source_ref"),
                        metadata={"raw_attributes": raw_attrs},
                    )
                )

            elif elem_type == "cable":
                if not from_bus or not to_bus:
                    incomplete.append(
                        {
                            "id": elem_id,
                            "type": "cable",
                            "reason": "missing_terminal_buses",
                            "missing_fields": [
                                f for f, v in [("from_bus", from_bus), ("to_bus", to_bus)] if not v
                            ],
                        }
                    )
                    continue
                cables.append(
                    ZenonCable(
                        id=elem_id,
                        name=item["name"],
                        from_bus=from_bus,
                        to_bus=to_bus,
                        r_pu=float(canonical_attrs["r_pu"])
                        if "r_pu" in canonical_attrs and canonical_attrs["r_pu"] is not None
                        else None,
                        x_pu=float(canonical_attrs["x_pu"])
                        if "x_pu" in canonical_attrs and canonical_attrs["x_pu"] is not None
                        else None,
                        b_pu=float(canonical_attrs["b_pu"])
                        if "b_pu" in canonical_attrs and canonical_attrs["b_pu"] is not None
                        else None,
                        length_km=float(canonical_attrs["length_km"])
                        if "length_km" in canonical_attrs
                        and canonical_attrs["length_km"] is not None
                        else None,
                        rating_a=float(canonical_attrs["rating_a"])
                        if "rating_a" in canonical_attrs and canonical_attrs["rating_a"] is not None
                        else None,
                        conductor_material=canonical_attrs.get("conductor_material"),
                        source_ref=item.get("source_ref"),
                        metadata={"raw_attributes": raw_attrs},
                    )
                )

            elif elem_type == "transformer":
                if not from_bus or not to_bus:
                    incomplete.append(
                        {
                            "id": elem_id,
                            "type": "transformer",
                            "reason": "missing_terminal_buses",
                            "missing_fields": [
                                f for f, v in [("from_bus", from_bus), ("to_bus", to_bus)] if not v
                            ],
                        }
                    )
                    continue
                transformers.append(
                    ZenonTransformer(
                        id=elem_id,
                        name=item["name"],
                        from_bus=from_bus,
                        to_bus=to_bus,
                        rating_mva=float(canonical_attrs["rating_mva"])
                        if "rating_mva" in canonical_attrs
                        and canonical_attrs["rating_mva"] is not None
                        else None,
                        prim_kv=float(canonical_attrs["prim_kv"])
                        if "prim_kv" in canonical_attrs and canonical_attrs["prim_kv"] is not None
                        else None,
                        sec_kv=float(canonical_attrs["sec_kv"])
                        if "sec_kv" in canonical_attrs and canonical_attrs["sec_kv"] is not None
                        else None,
                        r_pu=float(canonical_attrs["r_pu"])
                        if "r_pu" in canonical_attrs and canonical_attrs["r_pu"] is not None
                        else None,
                        x_pu=float(canonical_attrs["x_pu"])
                        if "x_pu" in canonical_attrs and canonical_attrs["x_pu"] is not None
                        else None,
                        tap_ratio=float(canonical_attrs["tap_ratio"])
                        if "tap_ratio" in canonical_attrs
                        and canonical_attrs["tap_ratio"] is not None
                        else None,
                        vector_group=canonical_attrs.get("vector_group"),
                        source_ref=item.get("source_ref"),
                        metadata={"raw_attributes": raw_attrs},
                    )
                )

            elif elem_type == "breaker":
                st = self._normalize_status(canonical_attrs.get("status"))
                breakers.append(
                    ZenonBreaker(
                        id=elem_id,
                        name=item["name"],
                        bus=bus,
                        from_bus=from_bus,
                        to_bus=to_bus,
                        status=st,  # type: ignore[arg-type]
                        rated_a=float(canonical_attrs["rated_a"])
                        if "rated_a" in canonical_attrs and canonical_attrs["rated_a"] is not None
                        else None,
                        breaking_capacity_ka=float(canonical_attrs["breaking_capacity_ka"])
                        if "breaking_capacity_ka" in canonical_attrs
                        and canonical_attrs["breaking_capacity_ka"] is not None
                        else None,
                        source_ref=item.get("source_ref"),
                        metadata={"raw_attributes": raw_attrs},
                    )
                )

            elif elem_type == "switch":
                st = self._normalize_status(canonical_attrs.get("status"))
                switches.append(
                    ZenonSwitch(
                        id=elem_id,
                        name=item["name"],
                        bus=bus,
                        from_bus=from_bus,
                        to_bus=to_bus,
                        status=st,  # type: ignore[arg-type]
                        rated_a=float(canonical_attrs["rated_a"])
                        if "rated_a" in canonical_attrs and canonical_attrs["rated_a"] is not None
                        else None,
                        source_ref=item.get("source_ref"),
                        metadata={"raw_attributes": raw_attrs},
                    )
                )

            elif elem_type == "load":
                target_bus = bus or from_bus
                if not target_bus:
                    incomplete.append(
                        {
                            "id": elem_id,
                            "type": "load",
                            "reason": "missing_bus_connection",
                            "missing_fields": ["bus"],
                        }
                    )
                    continue
                loads.append(
                    ZenonLoad(
                        id=elem_id,
                        name=item["name"],
                        bus=target_bus,
                        p_mw=float(canonical_attrs["p_mw"])
                        if "p_mw" in canonical_attrs and canonical_attrs["p_mw"] is not None
                        else None,
                        q_mvar=float(canonical_attrs["q_mvar"])
                        if "q_mvar" in canonical_attrs and canonical_attrs["q_mvar"] is not None
                        else None,
                        model=canonical_attrs.get("model"),
                        status=self._normalize_status(canonical_attrs.get("status")),  # type: ignore[arg-type]
                        source_ref=item.get("source_ref"),
                        metadata={"raw_attributes": raw_attrs},
                    )
                )

            elif elem_type == "generator":
                target_bus = bus or from_bus
                if not target_bus:
                    incomplete.append(
                        {
                            "id": elem_id,
                            "type": "generator",
                            "reason": "missing_bus_connection",
                            "missing_fields": ["bus"],
                        }
                    )
                    continue
                generators.append(
                    ZenonGenerator(
                        id=elem_id,
                        name=item["name"],
                        bus=target_bus,
                        p_mw=float(canonical_attrs["p_mw"])
                        if "p_mw" in canonical_attrs and canonical_attrs["p_mw"] is not None
                        else None,
                        q_mvar=float(canonical_attrs["q_mvar"])
                        if "q_mvar" in canonical_attrs and canonical_attrs["q_mvar"] is not None
                        else None,
                        rating_mva=float(canonical_attrs["rating_mva"])
                        if "rating_mva" in canonical_attrs
                        and canonical_attrs["rating_mva"] is not None
                        else None,
                        v_setpoint=float(canonical_attrs["v_setpoint"])
                        if "v_setpoint" in canonical_attrs
                        and canonical_attrs["v_setpoint"] is not None
                        else None,
                        q_min=float(canonical_attrs["q_min"])
                        if "q_min" in canonical_attrs and canonical_attrs["q_min"] is not None
                        else None,
                        q_max=float(canonical_attrs["q_max"])
                        if "q_max" in canonical_attrs and canonical_attrs["q_max"] is not None
                        else None,
                        status=self._normalize_status(canonical_attrs.get("status")),  # type: ignore[arg-type]
                        source_ref=item.get("source_ref"),
                        metadata={"raw_attributes": raw_attrs},
                    )
                )

            elif elem_type == "source":
                target_bus = bus or from_bus
                if not target_bus:
                    incomplete.append(
                        {
                            "id": elem_id,
                            "type": "source",
                            "reason": "missing_bus_connection",
                            "missing_fields": ["bus"],
                        }
                    )
                    continue
                sources.append(
                    ZenonSource(
                        id=elem_id,
                        name=item["name"],
                        bus=target_bus,
                        base_kv=float(canonical_attrs["base_kv"])
                        if "base_kv" in canonical_attrs and canonical_attrs["base_kv"] is not None
                        else None,
                        s_sc_mva=float(canonical_attrs["s_sc_mva"])
                        if "s_sc_mva" in canonical_attrs and canonical_attrs["s_sc_mva"] is not None
                        else None,
                        rx_ratio=float(canonical_attrs["rx_ratio"])
                        if "rx_ratio" in canonical_attrs and canonical_attrs["rx_ratio"] is not None
                        else None,
                        status=self._normalize_status(canonical_attrs.get("status")),  # type: ignore[arg-type]
                        source_ref=item.get("source_ref"),
                        metadata={"raw_attributes": raw_attrs},
                    )
                )

            elif elem_type == "motor":
                target_bus = bus or from_bus
                if not target_bus:
                    incomplete.append(
                        {
                            "id": elem_id,
                            "type": "motor",
                            "reason": "missing_bus_connection",
                            "missing_fields": ["bus"],
                        }
                    )
                    continue
                motors.append(
                    ZenonMotor(
                        id=elem_id,
                        name=item["name"],
                        bus=target_bus,
                        rated_kw=float(canonical_attrs["rated_kw"])
                        if "rated_kw" in canonical_attrs and canonical_attrs["rated_kw"] is not None
                        else None,
                        rated_kv=float(canonical_attrs["rated_kv"])
                        if "rated_kv" in canonical_attrs and canonical_attrs["rated_kv"] is not None
                        else None,
                        pf=float(canonical_attrs["pf"])
                        if "pf" in canonical_attrs and canonical_attrs["pf"] is not None
                        else None,
                        efficiency=float(canonical_attrs["efficiency"])
                        if "efficiency" in canonical_attrs
                        and canonical_attrs["efficiency"] is not None
                        else None,
                        status=self._normalize_status(canonical_attrs.get("status")),  # type: ignore[arg-type]
                        source_ref=item.get("source_ref"),
                        metadata={"raw_attributes": raw_attrs},
                    )
                )

            elif elem_type == "relay":
                target_bus = bus or from_bus
                if not target_bus:
                    incomplete.append(
                        {
                            "id": elem_id,
                            "type": "relay",
                            "reason": "missing_bus_connection",
                            "missing_fields": ["bus"],
                        }
                    )
                    continue
                relays.append(
                    ZenonRelay(
                        id=elem_id,
                        name=item["name"],
                        bus=target_bus,
                        protected_element=canonical_attrs.get("protected_element"),
                        curve_type=canonical_attrs.get("curve_type"),
                        time_dial=float(canonical_attrs["time_dial"])
                        if "time_dial" in canonical_attrs
                        and canonical_attrs["time_dial"] is not None
                        else None,
                        pickup_a=float(canonical_attrs["pickup_a"])
                        if "pickup_a" in canonical_attrs and canonical_attrs["pickup_a"] is not None
                        else None,
                        source_ref=item.get("source_ref"),
                        metadata={"raw_attributes": raw_attrs},
                    )
                )

            elif elem_type == "capacitor":
                target_bus = bus or from_bus
                if not target_bus:
                    incomplete.append(
                        {
                            "id": elem_id,
                            "type": "capacitor",
                            "reason": "missing_bus_connection",
                            "missing_fields": ["bus"],
                        }
                    )
                    continue
                capacitors.append(
                    ZenonCapacitor(
                        id=elem_id,
                        name=item["name"],
                        bus=target_bus,
                        q_mvar=float(canonical_attrs["q_mvar"])
                        if "q_mvar" in canonical_attrs and canonical_attrs["q_mvar"] is not None
                        else None,
                        rated_kv=float(canonical_attrs["rated_kv"])
                        if "rated_kv" in canonical_attrs and canonical_attrs["rated_kv"] is not None
                        else None,
                        status=self._normalize_status(canonical_attrs.get("status")),  # type: ignore[arg-type]
                        source_ref=item.get("source_ref"),
                        metadata={"raw_attributes": raw_attrs},
                    )
                )

            elif elem_type == "reactor":
                reactors.append(
                    ZenonReactor(
                        id=elem_id,
                        name=item["name"],
                        bus=bus,
                        from_bus=from_bus,
                        to_bus=to_bus,
                        x_pu=float(canonical_attrs["x_pu"])
                        if "x_pu" in canonical_attrs and canonical_attrs["x_pu"] is not None
                        else None,
                        rating_mva=float(canonical_attrs["rating_mva"])
                        if "rating_mva" in canonical_attrs
                        and canonical_attrs["rating_mva"] is not None
                        else None,
                        status=self._normalize_status(canonical_attrs.get("status")),  # type: ignore[arg-type]
                        source_ref=item.get("source_ref"),
                        metadata={"raw_attributes": raw_attrs},
                    )
                )

        # Build contract metadata from raw project
        p_raw = raw_dump.project
        contract_project = ZenonProjectMetadata(
            name=p_raw.name,
            version=p_raw.version,
            substation_name=p_raw.substation_name or p_raw.name,
            system_frequency_hz=p_raw.system_frequency_hz,
            base_mva=p_raw.base_mva,
            source_system="zenon_raw_dump_classifier",
        )

        contract = ZenonNetworkExport(
            contract_version="1.0.0",
            project=contract_project,
            buses=buses,
            lines=lines,
            cables=cables,
            transformers=transformers,
            breakers=breakers,
            switches=switches,
            loads=loads,
            generators=generators,
            motors=motors,
            relays=relays,
            capacitors=capacitors,
            reactors=reactors,
            sources=sources,
            metadata={"raw_dump_version": raw_dump.dump_version},
        )

        return ClassifyResult(
            contract=contract,
            unmapped=unmapped,
            incomplete=incomplete,
            warnings=warnings,
            errors=errors,
        )
