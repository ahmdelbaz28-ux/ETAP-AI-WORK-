from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from gis_validation_electrical.electrical_model import ElectricalModel


@dataclass(frozen=True)
class RadialityIssue:
    issue_type: str  # e.g. "loop_detected", "island_detected"
    affected_nodes: list[str]
    affected_edges: list[str]
    details: dict[str, object]


def _undirected_adjacency(model: ElectricalModel) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = {nid: set() for nid in model.nodes}
    for e in model.edges.values():
        if e.from_node in adj and e.to_node in adj:
            adj[e.from_node].add(e.to_node)
            adj[e.to_node].add(e.from_node)
    return adj


def _find_components(adj: dict[str, set[str]]) -> list[set[str]]:
    visited: set[str] = set()
    comps: list[set[str]] = []
    for start in adj:
        if start in visited:
            continue
        stack = [start]
        comp: set[str] = set()
        while stack:
            n = stack.pop()
            if n in visited:
                continue
            visited.add(n)
            comp.add(n)
            for nb in adj.get(n, set()):
                if nb not in visited:
                    stack.append(nb)
        comps.append(comp)
    return comps


def _has_undirected_loop(adj: dict[str, set[str]]) -> tuple[bool, list[str]]:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """
    Detect cycles in an undirected graph.
    Returns (has_loop, one_cycle_nodes_best_effort).

    Deterministic and bounded: uses DFS with parent tracking.
    """
    visited: set[str] = set()
    parent: dict[str, Optional[str]] = {}
    stack: list[tuple[str, Optional[str]]] = []

    for root in adj:
        if root in visited:
            continue
        parent[root] = None
        stack = [(root, None)]
        while stack:
            node, par = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            parent[node] = par
            for nb in adj.get(node, set()):
                if nb == par:
                    continue
                if nb in visited:
                    # Cycle detected: collect node + nb + current chain best-effort.
                    cycle_nodes = [node, nb]
                    return True, cycle_nodes
                stack.append((nb, node))

    return False, []


def validate_radiality(model: ElectricalModel) -> tuple[bool, list[RadialityIssue]]:
    """
    Radiality validation:
    - No loops in the electrical graph (undirected cycle check)
    - Electrical islands are detected (disconnected substations)

    Note: This is electrical-graph radiality only (not GIS topology validation).
    """
    issues: list[RadialityIssue] = []

    if not model.nodes:
        return True, issues

    adj = _undirected_adjacency(model)
    comps = _find_components(adj)

    # Island detection: more than one component means electrical isolation exists.
    if len(comps) > 1:
        # Best-effort: treat the smallest component as isolated.
        # SonarCloud python:S8517: min() instead of sort()[0] — O(n) vs O(n log n).
        smallest = min(comps, key=lambda c: len(c))
        affected_edges = [
            e.edge_id
            for e in model.edges.values()
            if e.from_node in smallest and e.to_node in smallest
        ]
        issues.append(
            RadialityIssue(
                issue_type="island_detected",
                affected_nodes=sorted(smallest),
                affected_edges=sorted(affected_edges),
                details={"component_count": len(comps)},
            ),
        )

    # Loop detection.
    has_loop, cycle_nodes = _has_undirected_loop(adj)
    if has_loop:
        affected_edges = [
            e.edge_id
            for e in model.edges.values()
            if e.from_node in cycle_nodes or e.to_node in cycle_nodes
        ]
        issues.append(
            RadialityIssue(
                issue_type="loop_detected",
                affected_nodes=sorted(set(cycle_nodes)),
                affected_edges=sorted(affected_edges),
                details={},
            ),
        )

    ok = len(issues) == 0
    return ok, issues
