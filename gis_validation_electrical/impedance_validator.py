from __future__ import annotations

from dataclasses import dataclass
<<<<<<< HEAD
=======
from typing import Dict, List, Tuple
>>>>>>> origin/fix/scenario-tests-properly

from gis_validation_electrical.electrical_model import ElectricalEdge, ElectricalModel


@dataclass(frozen=True)
class ImpedanceIssue:
    issue_type: str  # e.g. "impedance_jump"
<<<<<<< HEAD
    affected_edges: list[str]
    affected_nodes: list[str]
    details: dict[str, object]


def validate_impedance_consistency(model: ElectricalModel) -> tuple[bool, list[ImpedanceIssue]]:
=======
    affected_edges: List[str]
    affected_nodes: List[str]
    details: Dict[str, object]


def validate_impedance_consistency(model: ElectricalModel) -> Tuple[bool, List[ImpedanceIssue]]:
>>>>>>> origin/fix/scenario-tests-properly
    """
    Deterministic impedance consistency validation:
    - Impedance values must not exhibit unrealistic discontinuities along connected edges.
    - Transformers should not create abrupt impedance domain shifts (modeled by scale factor).

    Since we don't have a real solver, we treat "jumps" as inconsistencies between
    adjacent edges sharing a node.
    """
    if not model.edges or not model.nodes:
        return True, []

    # Build adjacency between edges by node-sharing.
<<<<<<< HEAD
    node_to_edges: dict[str, list[ElectricalEdge]] = {nid: [] for nid in model.nodes}
=======
    node_to_edges: Dict[str, List[ElectricalEdge]] = {nid: [] for nid in model.nodes.keys()}
>>>>>>> origin/fix/scenario-tests-properly
    for e in model.edges.values():
        if e.from_node in node_to_edges:
            node_to_edges[e.from_node].append(e)
        if e.to_node in node_to_edges:
            node_to_edges[e.to_node].append(e)

<<<<<<< HEAD
    issues: list[ImpedanceIssue] = []
=======
    issues: List[ImpedanceIssue] = []
>>>>>>> origin/fix/scenario-tests-properly

    def edge_key(e: ElectricalEdge) -> float:
        return e.impedance_ohm

    # Deterministic discontinuity threshold
    # (bounded to avoid false positives on small graphs).
    for node_id, edges in node_to_edges.items():
        if len(edges) < 2:
            continue
        impedances = sorted([edge_key(e) for e in edges])
        min_imp = impedances[0]
        max_imp = impedances[-1]
        if min_imp <= 0:
            continue
        ratio = max_imp / min_imp
        if ratio > 10.0:
            affected_edge_ids = sorted({e.edge_id for e in edges})
            issues.append(
                ImpedanceIssue(
                    issue_type="impedance_jump",
                    affected_edges=affected_edge_ids,
                    affected_nodes=[node_id],
                    details={"impedance_ratio": ratio, "node_id": node_id},
<<<<<<< HEAD
                ),
=======
                )
>>>>>>> origin/fix/scenario-tests-properly
            )

    ok = len(issues) == 0
    return ok, issues
