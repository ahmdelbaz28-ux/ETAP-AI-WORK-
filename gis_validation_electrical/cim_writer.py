"""
gis_validation_electrical/cim_writer.py — Schneider-profile CIM XML Exporter.

Serializes CIMModel (from gis_validation_electrical.cim_mapper) into
CIM RDF/XML compatible with Schneider EcoStruxure ADMS (EQ, SSH, TP, SV, FULL profiles).

References:
- IEC 61970-301 (CIM base), IEC 61970-452 / 456 (profiles: EQ, SSH, TP, SV)
- ENTSO-E CGMES 2.4.15
- Schneider EcoStruxure ADMS Model Exchange Specification
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import yaml

from gis_validation_electrical.cim_mapper import CIMModel

logger = logging.getLogger("gis_validation_electrical.cim_writer")

MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MiB limit

# NCName regex for XML rdf:ID validity
ID_REGEX = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


class CIMTooLargeError(Exception):
    """Raised when generated CIM XML exceeds 10 MiB fail-closed limit."""

    def __init__(self, size_bytes: int, limit_bytes: int = MAX_FILE_SIZE):
        super().__init__(
            f"CIM_TOO_LARGE: Generated CIM XML file size ({size_bytes} bytes) exceeds limit of "
            f"{limit_bytes} bytes (10 MiB). Split export by feeder or substation."
        )
        self.code = "CIM_TOO_LARGE"
        self.size_bytes = size_bytes
        self.limit_bytes = limit_bytes


def _load_schneider_profile_config() -> dict[str, Any]:
    """Load Schneider CIM profile settings from config/cim_schneider_profiles.yaml."""
    config_paths = [
        Path(__file__).resolve().parent.parent / "config" / "cim_schneider_profiles.yaml",
        Path("config/cim_schneider_profiles.yaml"),
    ]
    for p in config_paths:
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as exc:
                logger.warning("Failed to parse %s: %s", p, exc)

    logger.warning("config/cim_schneider_profiles.yaml not found or unreadable; using unified built-in fallback profile map.")
    # Built-in fallback matching the YAML schema if file is unavailable
    return {
        "default_version": "cim16",
        "default_profile": "EQ",
        "versions": {
            "cim16": {
                "namespace": "http://iec.ch/TC57/2013/CIM-schema-cim16#",
                "rdf_namespace": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "entsoe_namespace": "http://entsoe.eu/CIM/SchemaExtension/3/1#",
                "schema_version": "16",
            },
            "cim17": {
                "namespace": "http://iec.ch/TC57/CIM100#",
                "rdf_namespace": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "entsoe_namespace": "http://entsoe.eu/CIM/SchemaExtension/3/2#",
                "schema_version": "17",
            },
            "cgmes_2_4_15": {
                "namespace": "http://iec.ch/TC57/2013/CIM-schema-cim16#",
                "rdf_namespace": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "entsoe_namespace": "http://entsoe.eu/CIM/SchemaExtension/3/1#",
                "schema_version": "2.4.15",
            },
        },
        "profile_class_map": {
            "EQ": {
                "description": "Equipment Profile",
                "classes": [
                    "TopologicalNode",
                    "ConnectivityNode",
                    "Terminal",
                    "ACLineSegment",
                    "PowerTransformer",
                    "PowerTransformerEnd",
                    "Breaker",
                    "Disconnector",
                    "LoadBreakSwitch",
                    "Substation",
                    "VoltageLevel",
                    "BaseVoltage",
                    "PositionPoint",
                    "Location",
                ],
            },
            "SSH": {
                "description": "Steady State Hypothesis",
                "classes": [
                    "Breaker",
                    "Disconnector",
                    "LoadBreakSwitch",
                    "Terminal",
                    "SvStatus",
                ],
            },
            "TP": {
                "description": "Topology Profile",
                "classes": [
                    "TopologicalNode",
                    "TopologicalIsland",
                    "Terminal",
                ],
            },
            "SV": {
                "description": "State Variables",
                "classes": [
                    "SvVoltage",
                    "SvPowerFlow",
                    "SvStatus",
                    "SvTapStep",
                ],
            },
            "FULL": {
                "description": "Full Combined Model",
                "classes": [
                    "TopologicalNode",
                    "ConnectivityNode",
                    "Terminal",
                    "ACLineSegment",
                    "PowerTransformer",
                    "PowerTransformerEnd",
                    "Breaker",
                    "Disconnector",
                    "LoadBreakSwitch",
                    "Substation",
                    "VoltageLevel",
                    "BaseVoltage",
                    "PositionPoint",
                    "Location",
                    "SvVoltage",
                    "SvPowerFlow",
                    "SvStatus",
                ],
            },
        },
        "required_fields": {
            "SUBSTATION": ["name", "Lifecycle_Status", "AOR"],
            "FEEDER": ["name", "Lifecycle_Status", "base_kv"],
            "LINE": ["name", "Lifecycle_Status", "base_kv"],
            "TRANSFORMER": ["name", "Lifecycle_Status"],
            "SWITCH": ["name", "Lifecycle_Status"],
        },
        "schneider_defaults": {
            "Lifecycle_Status": "In_Service",
            "AOR": "Default_AOR",
            "normalOpen": False,
        },
    }


def make_rdf_id(raw_id: str, profile: str = "EQ") -> str:
    """
    Generate a deterministic, schema-valid rdf:ID from internal CIM ID.

    Rules:
    - Never reuse CE::, CN::, TE::, PT::, BR:: raw prefix.
    - Sanitized to [A-Za-z0-9_.-].
    - Guaranteed to match ^[A-Za-z_][A-Za-z0-9_.-]*$.
    - Deterministic across runs for identical raw_id.
    """
    cleaned = re.sub(r"^(CE|CN|TE|PT|BR)::", "", str(raw_id))
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", cleaned).strip("._") or "obj"
    # Deterministic hash to avoid collision while maintaining byte-level reproducibility
    uid_hex = uuid.uuid5(uuid.NAMESPACE_URL, f"urn:etap:cim:{profile}:{raw_id}").hex[:12]
    candidate = f"_{uid_hex}_{sanitized}"
    if not ID_REGEX.match(candidate):
        candidate = f"_id_{uid_hex}"
    return candidate


def make_mrid(raw_id: str) -> str:
    """Generate RFC 4122 mRID UUID string for IdentifiedObject.mRID."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:etap:mrid:{raw_id}"))


def build_cim_xml(
    cim_model: CIMModel,
    profile: str = "EQ",
    namespace_version: str = "cim16",
    crs: str = "EPSG:4326",
) -> bytes:
    """
    Build a Schneider EcoStruxure ADMS compatible CIM RDF/XML document.

    Parameters
    ----------
    cim_model : CIMModel
        Normalized CIM model containing conducting_equipment, connectivity_nodes,
        terminals, power_transformers, breakers, and traceability.
    profile : str
        Target CIM profile: 'EQ' (Equipment), 'SSH' (Steady State Hypothesis),
        'TP' (Topology), 'SV' (State Variables), or 'FULL'.
    namespace_version : str
        Target CIM standard version: 'cim16', 'cim17', or 'cgmes_2_4_15'.
    crs : str
        Spatial reference system string (default 'EPSG:4326').

    Returns
    -------
    bytes
        UTF-8 encoded CIM RDF/XML payload.

    Raises
    ------
    CIMTooLargeError
        If payload exceeds 10 MiB limit.
    ValueError
        If profile or namespace version is unsupported.
    """
    cfg = _load_schneider_profile_config()
    versions_cfg = cfg.get("versions", {})
    norm_version = namespace_version.strip().lower()
    if norm_version not in versions_cfg:
        raise ValueError(
            f"Unsupported CIM version '{namespace_version}'. Allowed: {list(versions_cfg.keys())}"
        )

    norm_profile = profile.strip().upper()
    profile_class_map = cfg.get("profile_class_map", {})
    if norm_profile not in profile_class_map:
        raise ValueError(
            f"Unsupported CIM profile '{profile}'. Allowed: {list(profile_class_map.keys())}"
        )

    profile_entry = profile_class_map[norm_profile]
    if isinstance(profile_entry, dict):
        class_list = profile_entry.get("classes", [])
    elif isinstance(profile_entry, (list, tuple, set)):
        class_list = list(profile_entry)
    else:
        class_list = []
    allowed_classes = set(class_list)
    v_info = versions_cfg[norm_version]
    cim_ns = v_info.get("namespace", "http://iec.ch/TC57/2013/CIM-schema-cim16#")
    rdf_ns = v_info.get("rdf_namespace", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
    entsoe_ns = v_info.get("entsoe_namespace", "http://entsoe.eu/CIM/SchemaExtension/3/1#")

    schneider_defs = cfg.get("schneider_defaults", {})
    lifecycle_def = schneider_defs.get("Lifecycle_Status", "In_Service")
    aor_def = schneider_defs.get("AOR", "Default_AOR")

    # Sort elements deterministically by cim_id for byte-identical reproducibility
    sorted_eq = sorted(cim_model.conducting_equipment.items(), key=lambda kv: kv[0])
    sorted_cn = sorted(cim_model.connectivity_nodes.items(), key=lambda kv: kv[0])
    sorted_te = sorted(cim_model.terminals.items(), key=lambda kv: kv[0])
    sorted_pt = sorted(cim_model.power_transformers.items(), key=lambda kv: kv[0])
    sorted_br = sorted(cim_model.breakers.items(), key=lambda kv: kv[0])

    lines: list[str] = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<rdf:RDF xmlns:rdf="{rdf_ns}" xmlns:cim="{cim_ns}" xmlns:entsoe="{entsoe_ns}">',
    ]

    # -------------------------------------------------------------------------
    # 1. TopologicalNode / ConnectivityNode (EQ, TP, FULL)
    # -------------------------------------------------------------------------
    if "TopologicalNode" in allowed_classes:
        for cn_id, cn in sorted_cn:
            rdf_id = make_rdf_id(cn.cim_id, "EQ")
            mrid = make_mrid(cn.cim_id)
            label = escape(str(cn.metadata.get("name") or cn.label or cn.cim_id))
            lines.append(f'  <cim:TopologicalNode rdf:ID="{rdf_id}">')
            lines.append(f"    <cim:IdentifiedObject.mRID>{mrid}</cim:IdentifiedObject.mRID>")
            lines.append(f"    <cim:IdentifiedObject.name>{label}</cim:IdentifiedObject.name>")
            if cn.voltage_level_kv is not None:
                lines.append(f"    <cim:TopologicalNode.nominalVoltage>{cn.voltage_level_kv}</cim:TopologicalNode.nominalVoltage>")
            lines.append("  </cim:TopologicalNode>")

    if "ConnectivityNode" in allowed_classes:
        for cn_id, cn in sorted_cn:
            cn_rdf_id = make_rdf_id(f"CN_NODE_{cn.cim_id}", "EQ")
            topo_ref = make_rdf_id(cn.cim_id, "EQ")
            label = escape(str(cn.metadata.get("name") or cn.label or cn.cim_id))
            lines.append(f'  <cim:ConnectivityNode rdf:ID="{cn_rdf_id}">')
            lines.append(f"    <cim:IdentifiedObject.name>{label}</cim:IdentifiedObject.name>")
            lines.append(f'    <cim:ConnectivityNode.TopologicalNode rdf:resource="#{topo_ref}"/>')
            lines.append("  </cim:ConnectivityNode>")

    # -------------------------------------------------------------------------
    # 2. ConductingEquipment (EQ, FULL)
    # -------------------------------------------------------------------------
    if "Substation" in allowed_classes:
        for ce_id, ce in sorted_eq:
            if ce.kind == "substation":
                rdf_id = make_rdf_id(ce.cim_id, "EQ")
                mrid = make_mrid(ce.cim_id)
                name = escape(ce.name or ce.cim_id)
                status = escape(str(ce.metadata.get("Lifecycle_Status", lifecycle_def)))
                aor = escape(str(ce.metadata.get("AOR", aor_def)))
                lines.append(f'  <cim:Substation rdf:ID="{rdf_id}">')
                lines.append(f"    <cim:IdentifiedObject.mRID>{mrid}</cim:IdentifiedObject.mRID>")
                lines.append(f"    <cim:IdentifiedObject.name>{name}</cim:IdentifiedObject.name>")
                lines.append(f"    <entsoe:AOR>{aor}</entsoe:AOR>")
                lines.append(f"    <entsoe:Lifecycle_Status>{status}</entsoe:Lifecycle_Status>")
                lines.append("  </cim:Substation>")

    if "ACLineSegment" in allowed_classes:
        for ce_id, ce in sorted_eq:
            if ce.kind in ("line", "feeder"):
                rdf_id = make_rdf_id(ce.cim_id, "EQ")
                mrid = make_mrid(ce.cim_id)
                name = escape(ce.name or ce.cim_id)
                status = escape(str(ce.metadata.get("Lifecycle_Status", lifecycle_def)))
                lines.append(f'  <cim:ACLineSegment rdf:ID="{rdf_id}">')
                lines.append(f"    <cim:IdentifiedObject.mRID>{mrid}</cim:IdentifiedObject.mRID>")
                lines.append(f"    <cim:IdentifiedObject.name>{name}</cim:IdentifiedObject.name>")
                lines.append(f"    <entsoe:Lifecycle_Status>{status}</entsoe:Lifecycle_Status>")
                if "base_kv" in ce.metadata and ce.metadata["base_kv"] is not None:
                    lines.append(f"    <cim:Conductor.baseKV>{float(ce.metadata['base_kv'])}</cim:Conductor.baseKV>")
                if "r" in ce.metadata and ce.metadata["r"] is not None:
                    lines.append(f"    <cim:ACLineSegment.r>{float(ce.metadata['r'])}</cim:ACLineSegment.r>")
                if "x" in ce.metadata and ce.metadata["x"] is not None:
                    lines.append(f"    <cim:ACLineSegment.x>{float(ce.metadata['x'])}</cim:ACLineSegment.x>")
                if "b" in ce.metadata and ce.metadata["b"] is not None:
                    lines.append(f"    <cim:ACLineSegment.bch>{float(ce.metadata['b'])}</cim:ACLineSegment.bch>")
                lines.append("  </cim:ACLineSegment>")

    if "PowerTransformer" in allowed_classes:
        for pt_id, pt in sorted_pt:
            ce = cim_model.conducting_equipment.get(pt.equipment_id)
            name = escape(ce.name if ce else pt.cim_id)
            rdf_id = make_rdf_id(pt.cim_id, "EQ")
            mrid = make_mrid(pt.cim_id)
            status = escape(str(pt.metadata.get("Lifecycle_Status", lifecycle_def)))
            lines.append(f'  <cim:PowerTransformer rdf:ID="{rdf_id}">')
            lines.append(f"    <cim:IdentifiedObject.mRID>{mrid}</cim:IdentifiedObject.mRID>")
            lines.append(f"    <cim:IdentifiedObject.name>{name}</cim:IdentifiedObject.name>")
            lines.append(f"    <entsoe:Lifecycle_Status>{status}</entsoe:Lifecycle_Status>")
            lines.append("  </cim:PowerTransformer>")

    # -------------------------------------------------------------------------
    # 3. Breaker / Switch (EQ: definition, SSH: operating state)
    # -------------------------------------------------------------------------
    if norm_profile in ("EQ", "FULL") and "Breaker" in allowed_classes:
        for br_id, br in sorted_br:
            ce = cim_model.conducting_equipment.get(br.equipment_id)
            name = escape(ce.name if ce else br.cim_id)
            rdf_id = make_rdf_id(br.cim_id, "EQ")
            mrid = make_mrid(br.cim_id)
            status = escape(str(br.metadata.get("Lifecycle_Status", lifecycle_def)))
            lines.append(f'  <cim:Breaker rdf:ID="{rdf_id}">')
            lines.append(f"    <cim:IdentifiedObject.mRID>{mrid}</cim:IdentifiedObject.mRID>")
            lines.append(f"    <cim:IdentifiedObject.name>{name}</cim:IdentifiedObject.name>")
            lines.append(f"    <entsoe:Lifecycle_Status>{status}</entsoe:Lifecycle_Status>")
            # Note: No <cim:Switch.open> here — state belongs strictly to SSH profile
            lines.append("  </cim:Breaker>")

    if norm_profile == "SSH" and "Breaker" in allowed_classes:
        for br_id, br in sorted_br:
            eq_ref = make_rdf_id(br.cim_id, "EQ")
            open_str = "true" if br.open_state else "false"
            lines.append(f'  <cim:Breaker rdf:about="#{eq_ref}">')
            lines.append(f"    <cim:Switch.open>{open_str}</cim:Switch.open>")
            lines.append("  </cim:Breaker>")

    # -------------------------------------------------------------------------
    # 4. Terminal (EQ, TP, SSH, FULL)
    # -------------------------------------------------------------------------
    if "Terminal" in allowed_classes and norm_profile != "SSH":
        for t_id, t in sorted_te:
            rdf_id = make_rdf_id(t.cim_id, norm_profile)
            mrid = make_mrid(t.cim_id)
            role = escape(t.terminal_role or "hub")
            lines.append(f'  <cim:Terminal rdf:ID="{rdf_id}">')
            lines.append(f"    <cim:IdentifiedObject.mRID>{mrid}</cim:IdentifiedObject.mRID>")
            lines.append(f"    <cim:IdentifiedObject.name>{role}</cim:IdentifiedObject.name>")
            if norm_profile in ("EQ", "FULL"):
                eq_ref = make_rdf_id(t.equipment_id, "EQ")
                cn_ref = make_rdf_id(f"CN_NODE_{t.connectivity_node_id}", "EQ")
                lines.append(f'    <cim:Terminal.ConductingEquipment rdf:resource="#{eq_ref}"/>')
                lines.append(f'    <cim:Terminal.ConnectivityNode rdf:resource="#{cn_ref}"/>')
            if norm_profile in ("TP", "FULL"):
                topo_ref = make_rdf_id(t.connectivity_node_id, "EQ")
                lines.append(f'    <cim:Terminal.TopologicalNode rdf:resource="#{topo_ref}"/>')
            lines.append("  </cim:Terminal>")

    # -------------------------------------------------------------------------
    # 5. PositionPoint & Location for GIS positions (EQ, FULL)
    # -------------------------------------------------------------------------
    if norm_profile in ("EQ", "FULL") and "PositionPoint" in allowed_classes:
        for cn_id, cn in sorted_cn:
            geom = cn.metadata.get("geometry") or {}
            coords = geom.get("coordinates")
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                lon, lat = float(coords[0]), float(coords[1])
                loc_id = make_rdf_id(f"LOC_{cn.cim_id}", "EQ")
                pos_id = make_rdf_id(f"POS_{cn.cim_id}", "EQ")
                lines.append(f'  <cim:Location rdf:ID="{loc_id}">')
                lines.append(f"    <cim:Location.CoordinateSystem>{escape(crs)}</cim:Location.CoordinateSystem>")
                lines.append("  </cim:Location>")
                lines.append(f'  <cim:PositionPoint rdf:ID="{pos_id}">')
                lines.append(f'    <cim:PositionPoint.Location rdf:resource="#{loc_id}"/>')
                lines.append(f"    <cim:PositionPoint.xPosition>{lon}</cim:PositionPoint.xPosition>")
                lines.append(f"    <cim:PositionPoint.yPosition>{lat}</cim:PositionPoint.yPosition>")
                lines.append("  </cim:PositionPoint>")

    # -------------------------------------------------------------------------
    # 6. State Variables (SV, FULL)
    # -------------------------------------------------------------------------
    if "SvVoltage" in allowed_classes:
        for cn_id, cn in sorted_cn:
            v_mag = cn.metadata.get("voltage_magnitude_pu", 1.0)
            v_ang = cn.metadata.get("voltage_angle_deg", 0.0)
            sv_id = make_rdf_id(f"SV_VOLT_{cn.cim_id}", "SV")
            topo_ref = make_rdf_id(cn.cim_id, "EQ")
            lines.append(f'  <cim:SvVoltage rdf:ID="{sv_id}">')
            lines.append(f'    <cim:SvVoltage.TopologicalNode rdf:resource="#{topo_ref}"/>')
            lines.append(f"    <cim:SvVoltage.v>{float(v_mag)}</cim:SvVoltage.v>")
            lines.append(f"    <cim:SvVoltage.angle>{float(v_ang)}</cim:SvVoltage.angle>")
            lines.append("  </cim:SvVoltage>")

    lines.append("</rdf:RDF>")
    lines.append("")  # trailing newline

    xml_text = "\n".join(lines)
    xml_bytes = xml_text.encode("utf-8")

    # Enforce 10 MiB limit fail-closed
    if len(xml_bytes) > MAX_FILE_SIZE:
        raise CIMTooLargeError(size_bytes=len(xml_bytes), limit_bytes=MAX_FILE_SIZE)

    return xml_bytes
