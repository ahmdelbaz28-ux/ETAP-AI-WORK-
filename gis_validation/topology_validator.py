from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

from gis_integration.models import ADMSAsset, ADMSAssetType


@dataclass(frozen=True)
class TopologyIssue:
    issue_type: str
    affected_assets: List[str]
    details: Dict[str, Any]


class ADMSGraphModel:
    """
    Minimal graph model derived from ADMSAsset list.

    We avoid guessing electrical connectivity beyond deterministic rules:
    - nodes are asset_ids
    - edges are inferred only from explicit geometry endpoints for determinism
    """

    def __init__(self, assets: List[ADMSAsset]) -> None:
        self.assets = assets
        self.nodes: Set[str] = {a.asset_id for a in assets}
        self.edges: Dict[str, Set[str]] = {a.asset_id: set() for a in assets}
        self._build_deterministic_edges()

    @staticmethod
    def _extract_endpoints(
        geometry: Dict[str, Any],
    ) -> Tuple[Tuple[float, float], Tuple[float, float]] | None:
        gtype = geometry.get("type")
        coords = geometry.get("coordinates")
        if gtype == "LineString" and isinstance(coords, list) and len(coords) >= 2:
            # GeoJSON coords: [lon, lat] pairs
            a = coords[0]
            b = coords[-1]
            if isinstance(a, list) and isinstance(b, list) and len(a) >= 2 and len(b) >= 2:
                return (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))
        return None

    def _build_deterministic_edges(self) -> None:
        # Deterministic: connect LINE/FEEDER assets to nearest substations by matching endpoints exactly
        # when possible (within exact equality). No tolerance to avoid nondeterminism.
        substations = [a for a in self.assets if a.asset_type in (ADMSAssetType.SUBSTATION,)]
        lines = [
            a for a in self.assets if a.asset_type in (ADMSAssetType.LINE, ADMSAssetType.FEEDER)
        ]

        sub_endpoints: Dict[Tuple[float, float], List[str]] = {}
        for s in substations:
            geom = s.geometry
            if geom.get("type") == "Point":
                coords = geom.get("coordinates")
                if isinstance(coords, list) and len(coords) >= 2:
                    key = (float(coords[0]), float(coords[1]))
                    sub_endpoints.setdefault(key, []).append(s.asset_id)

        for l in lines:
            endpoints = self._extract_endpoints(l.geometry)
            if not endpoints:
                continue
            (a_lonlat, b_lonlat) = endpoints
            for node_endpoint in (a_lonlat, b_lonlat):
                matches = sub_endpoints.get(node_endpoint, [])
                for sid in matches:
                    self.edges[l.asset_id].add(sid)
                    self.edges[sid].add(l.asset_id)

    def find_disconnected_components(self) -> List[Set[str]]:
        visited: Set[str] = set()
        comps: List[Set[str]] = []
        for n in self.nodes:
            if n in visited:
                continue
            stack = [n]
            comp: Set[str] = set()
            while stack:
                cur = stack.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                comp.add(cur)
                for nb in self.edges.get(cur, set()):
                    if nb not in visited:
                        stack.append(nb)
            comps.append(comp)
        return comps


def validate_adms_topology(assets: List[ADMSAsset]) -> Tuple[bool, List[TopologyIssue]]:
    """
    Validate basic electrical consistency derived from geometry.

    Checks:
    - feeder continuity (graph connectivity among feeder/line assets and substations)
    - node isolation detection (substations with no connected edges)
    - disconnected components
    - dangling lines (line assets with no edges)
    """
    issues: List[TopologyIssue] = []
    if not assets:
        return False, [TopologyIssue("empty_graph", [], {"reason": "No assets provided"})]

    graph = ADMSGraphModel(assets)

    components = graph.find_disconnected_components()
    if len(components) > 1:
        # Deterministic classification: disconnected components exist.
        issues.append(
            TopologyIssue(
                issue_type="disconnected_components",
                affected_assets=sorted([a for comp in components for a in comp]),
                details={"component_count": len(components)},
            )
        )

    substations = [a.asset_id for a in assets if a.asset_type == ADMSAssetType.SUBSTATION]
    lines = [
        a.asset_id for a in assets if a.asset_type in (ADMSAssetType.LINE, ADMSAssetType.FEEDER)
    ]

    # Node isolation: substations with degree 0
    isolated_subs = [sid for sid in substations if len(graph.edges.get(sid, set())) == 0]
    if isolated_subs:
        issues.append(
            TopologyIssue(
                issue_type="isolated_substations",
                affected_assets=isolated_subs,
                details={},
            )
        )

    # Dangling lines: line/feeder with degree 0
    dangling = [lid for lid in lines if len(graph.edges.get(lid, set())) == 0]
    if dangling:
        issues.append(
            TopologyIssue(
                issue_type="dangling_lines",
                affected_assets=dangling,
                details={},
            )
        )

    ok = len(issues) == 0
    return ok, issues
