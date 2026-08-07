from __future__ import annotations

from dataclasses import dataclass, field
<<<<<<< HEAD
from typing import Any, Optional
=======
from typing import Any, Dict, List, Tuple
>>>>>>> origin/fix/scenario-tests-properly

from gis_integration.models import ADMSAsset, ADMSAssetType


@dataclass(frozen=True)
class ElectricalNode:
    node_id: str  # typically substation asset_id
<<<<<<< HEAD
    voltage_level_kv: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)
=======
    voltage_level_kv: float | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)
>>>>>>> origin/fix/scenario-tests-properly


@dataclass(frozen=True)
class ElectricalEdge:
    """
    Deterministic electrical connection between two electrical nodes.
    """

    edge_id: str
    from_node: str
    to_node: str
<<<<<<< HEAD
    asset_ids: tuple[str, ...]
    resistance_ohm: float
    impedance_ohm: float
    metadata: dict[str, Any] = field(default_factory=dict)
=======
    asset_ids: Tuple[str, ...]
    resistance_ohm: float
    impedance_ohm: float
    metadata: Dict[str, Any] = field(default_factory=dict)
>>>>>>> origin/fix/scenario-tests-properly


@dataclass(frozen=True)
class ElectricalModel:
<<<<<<< HEAD
    nodes: dict[str, ElectricalNode]
    edges: dict[str, ElectricalEdge]
    asset_to_node: dict[str, str]  # ADMS asset_id -> electrical node_id


def _stable_float_from_str(s: str, *, min_val: float, max_val: float) -> float:
=======
    nodes: Dict[str, ElectricalNode]
    edges: Dict[str, ElectricalEdge]
    asset_to_node: Dict[str, str]  # ADMS asset_id -> electrical node_id


def _stable_float_from_str(s: str, *, scale: float, min_val: float, max_val: float) -> float:
>>>>>>> origin/fix/scenario-tests-properly
    """
    Deterministic numeric mapping without randomness.
    Uses a simple polynomial rolling hash to generate a stable float in [min_val, max_val].
    """
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    span = max_val - min_val
    return min_val + (h % 100000) / 100000.0 * span


<<<<<<< HEAD
def build_electrical_model(  # NOSONAR
    assets: list[ADMSAsset],
) -> ElectricalModel:  # NOSONAR cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
=======
def build_electrical_model(assets: List[ADMSAsset]) -> ElectricalModel:
>>>>>>> origin/fix/scenario-tests-properly
    """
    Build a simplified deterministic electrical model derived from ADMS assets.

    Rules (deterministic):
    - SUBSTATION assets become electrical nodes.
    - LINE/FEEDER assets are edges between substations by using their geometry endpoints.
      Endpoints are matched by exact GeoJSON coordinates to substation point coordinates.
    - SWITCH assets do not create edges; they are treated as modifiers (open/closed) in later stages.
      If switch state is absent, we assume closed for electrical conservatism (fail-closed elsewhere).
    - TRANSFORMER assets are edges with an impedance scaled differently; transformer voltage metadata
      is not interpreted beyond presence/absence.

    Impedance/resistance values are deterministic pseudo-parameters derived from asset_id
    to support validity checks without a full power solver.
    """
    substations = [a for a in assets if a.asset_type == ADMSAssetType.SUBSTATION]
    if not substations:
        return ElectricalModel(nodes={}, edges={}, asset_to_node={})

    # Map substation coordinate -> node_id
<<<<<<< HEAD
    sub_coords: dict[tuple[float, float], str] = {}
    nodes: dict[str, ElectricalNode] = {}
    asset_to_node: dict[str, str] = {}
=======
    sub_coords: Dict[Tuple[float, float], str] = {}
    nodes: Dict[str, ElectricalNode] = {}
    asset_to_node: Dict[str, str] = {}
>>>>>>> origin/fix/scenario-tests-properly

    for s in substations:
        geom = s.geometry
        coords = geom.get("coordinates")
        if isinstance(coords, list) and len(coords) >= 2:
            key = (float(coords[0]), float(coords[1]))
            sub_coords[key] = s.asset_id
            nodes[s.asset_id] = ElectricalNode(
<<<<<<< HEAD
                node_id=s.asset_id,
                voltage_level_kv=None,
                metadata=dict(s.metadata),
            )
            asset_to_node[s.asset_id] = s.asset_id

    edges: dict[str, ElectricalEdge] = {}

    def endpoints_from_linestring(
        geom: dict[str, Any],
    ) -> tuple[tuple[float, float], tuple[float, float]] | None:
=======
                node_id=s.asset_id, voltage_level_kv=None, metadata=dict(s.metadata)
            )
            asset_to_node[s.asset_id] = s.asset_id

    edges: Dict[str, ElectricalEdge] = {}

    def endpoints_from_linestring(
        geom: Dict[str, Any],
    ) -> Tuple[Tuple[float, float], Tuple[float, float]] | None:
>>>>>>> origin/fix/scenario-tests-properly
        if geom.get("type") != "LineString":
            return None
        coords = geom.get("coordinates")
        if not isinstance(coords, list) or len(coords) < 2:
            return None
        a = coords[0]
        b = coords[-1]
        if not (isinstance(a, list) and isinstance(b, list) and len(a) >= 2 and len(b) >= 2):
            return None
        return (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))

    def add_edge(asset: ADMSAsset, *, impedance_scale: float) -> None:
        ep = endpoints_from_linestring(asset.geometry)
        if not ep:
            return
        a_ep, b_ep = ep
        if a_ep not in sub_coords or b_ep not in sub_coords:
            return
        from_node = sub_coords[a_ep]
        to_node = sub_coords[b_ep]

        # Deterministic impedance parameters
<<<<<<< HEAD
        base_imp = _stable_float_from_str(asset.asset_id, min_val=0.1, max_val=5.0)
=======
        base_imp = _stable_float_from_str(asset.asset_id, scale=1.0, min_val=0.1, max_val=5.0)
>>>>>>> origin/fix/scenario-tests-properly
        impedance_ohm = base_imp * impedance_scale
        resistance_ohm = impedance_ohm * 0.6

        edge_id = f"{asset.asset_id}__edge"
        edges[edge_id] = ElectricalEdge(
            edge_id=edge_id,
            from_node=from_node,
            to_node=to_node,
            asset_ids=(asset.asset_id,),
            resistance_ohm=resistance_ohm,
            impedance_ohm=impedance_ohm,
            metadata=dict(asset.metadata),
        )

        asset_to_node[asset.asset_id] = from_node

    for a in assets:
        if a.asset_type in (ADMSAssetType.LINE, ADMSAssetType.FEEDER):
            add_edge(a, impedance_scale=1.0)
        elif a.asset_type == ADMSAssetType.TRANSFORMER:
            # Transformers affect impedance domain scaling.
            add_edge(a, impedance_scale=0.5)

    return ElectricalModel(nodes=nodes, edges=edges, asset_to_node=asset_to_node)
