from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from gis_integration.models import ADMSAsset, ADMSAssetType


@dataclass(frozen=True)
class CIMConductingEquipment:
    cim_id: str
    name: str
    kind: str  # FEEDER/LINE/TRANSFORMER/SWITCH/SUBSTATION
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CIMConnectivityNode:
    cim_id: str
    label: str
    voltage_level_kv: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CIMTerminal:
    cim_id: str
    equipment_id: str
    connectivity_node_id: str
    terminal_role: str  # from/to for edges, hub for substations
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CIMPowerTransformer:
    cim_id: str
    equipment_id: str
    transformer_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CIMBreaker:
    cim_id: str
    equipment_id: str
    open_state: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CIMModel:
    conducting_equipment: Dict[str, CIMConductingEquipment]
    connectivity_nodes: Dict[str, CIMConnectivityNode]
    terminals: Dict[str, CIMTerminal]
    power_transformers: Dict[str, CIMPowerTransformer]
    breakers: Dict[str, CIMBreaker]
    traceability: Dict[str, str]  # cim_id -> adms_asset_id


def _bool_from_metadata(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "open", "opened"):
            return True
        if v in ("false", "0", "closed", "close"):
            return False
    return default


def map_adms_to_cim(assets: List[ADMSAsset]) -> CIMModel:
    """
    Deterministic CIM-like mapping for validation traceability.

    Mapping rules (deterministic, no ambiguous classification):
    - SUBSTATION -> ConnectivityNode + ConductingEquipment(kind=substation)
    - LINE/FEEDER -> ConductingEquipment + two Terminals (from/to)
      Connectivity node assignment uses LineString endpoints matched to Substation point coords.
    - TRANSFORMER -> ConductingEquipment(kind=transformer) + two Terminals (from/to)
      plus CIMPowerTransformer wrapper for validation traceability.
    - SWITCH -> ConductingEquipment(kind=switch) + two Terminals (from/to where available)
      plus CIMBreaker with open/closed state from asset.metadata['state'] or 'open_state' keys.
    """
    # Coordinate helpers: match endpoints to substations by exact coordinate tuple.
    substations = [a for a in assets if a.asset_type == ADMSAssetType.SUBSTATION]
    sub_coords_to_node: Dict[Tuple[float, float], str] = {}

    conducting_equipment: Dict[str, CIMConductingEquipment] = {}
    connectivity_nodes: Dict[str, CIMConnectivityNode] = {}
    terminals: Dict[str, CIMTerminal] = {}
    power_transformers: Dict[str, CIMPowerTransformer] = {}
    breakers: Dict[str, CIMBreaker] = {}
    traceability: Dict[str, str] = {}

    for s in substations:
        geom = s.geometry or {}
        coords = geom.get("coordinates")
        if isinstance(coords, list) and len(coords) >= 2:
            key = (float(coords[0]), float(coords[1]))
            node_id = s.asset_id
            sub_coords_to_node[key] = node_id
            cn = CIMConnectivityNode(
                cim_id=f"CN::{node_id}",
                label=str(node_id),
                voltage_level_kv=None,
                metadata=dict(s.metadata),
            )
            connectivity_nodes[cn.cim_id] = cn

        eq = CIMConductingEquipment(
            cim_id=f"CE::{s.asset_id}",
            name=str(s.metadata.get("name", s.asset_id)),
            kind="substation",
            metadata=dict(s.metadata),
        )
        conducting_equipment[eq.cim_id] = eq
        traceability[eq.cim_id] = s.asset_id

    def endpoints_from_linestring(geom: Dict[str, Any]) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
        if (geom or {}).get("type") != "LineString":
            return None
        coords = geom.get("coordinates")
        if not isinstance(coords, list) or len(coords) < 2:
            return None
        a = coords[0]
        b = coords[-1]
        if not (isinstance(a, list) and isinstance(b, list) and len(a) >= 2 and len(b) >= 2):
            return None
        return (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))

    for a in assets:
        if a.asset_type not in (
            ADMSAssetType.LINE,
            ADMSAssetType.FEEDER,
            ADMSAssetType.TRANSFORMER,
            ADMSAssetType.SWITCH,
        ):
            continue

        kind = "line" if a.asset_type == ADMSAssetType.LINE else (
            "feeder" if a.asset_type == ADMSAssetType.FEEDER else (
                "transformer" if a.asset_type == ADMSAssetType.TRANSFORMER else "switch"
            )
        )

        ce_id = f"CE::{a.asset_id}"
        ce = CIMConductingEquipment(
            cim_id=ce_id,
            name=str(a.metadata.get("name", a.asset_id)),
            kind=kind,
            metadata=dict(a.metadata),
        )
        conducting_equipment[ce_id] = ce
        traceability[ce_id] = a.asset_id

        ep = endpoints_from_linestring(a.geometry or {})
        if not ep:
            continue

        (a_ep, b_ep) = ep
        a_node = sub_coords_to_node.get(a_ep)
        b_node = sub_coords_to_node.get(b_ep)
        if not a_node or not b_node:
            # For deterministic mapping, skip terminal creation if nodes can't be assigned.
            # This will be surfaced by CIM consistency checks later.
            continue

        for role, node_id in (("from", a_node), ("to", b_node)):
            t_id = f"TE::{a.asset_id}::{role}"
            t = CIMTerminal(
                cim_id=t_id,
                equipment_id=ce_id,
                connectivity_node_id=f"CN::{node_id}",
                terminal_role=role,
                metadata=dict(a.metadata),
            )
            terminals[t.cim_id] = t
            traceability[t.cim_id] = a.asset_id

        if a.asset_type == ADMSAssetType.TRANSFORMER:
            pt_id = f"PT::{a.asset_id}"
            power_transformers[pt_id] = CIMPowerTransformer(
                cim_id=pt_id,
                equipment_id=ce_id,
                transformer_type=str(a.metadata.get("transformer_type", "deterministic_transformer")),
                metadata=dict(a.metadata),
            )
            traceability[pt_id] = a.asset_id

        if a.asset_type == ADMSAssetType.SWITCH:
            br_id = f"BR::{a.asset_id}"
            open_state = _bool_from_metadata(
                a.metadata.get("open_state", a.metadata.get("state")),
                default=False,
            )
            breakers[br_id] = CIMBreaker(
                cim_id=br_id,
                equipment_id=ce_id,
                open_state=open_state,
                metadata=dict(a.metadata),
            )
            traceability[br_id] = a.asset_id

    return CIMModel(
        conducting_equipment=conducting_equipment,
        connectivity_nodes=connectivity_nodes,
        terminals=terminals,
        power_transformers=power_transformers,
        breakers=breakers,
        traceability=traceability,
    )
