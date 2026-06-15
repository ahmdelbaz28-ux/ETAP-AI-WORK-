from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from gis_validation_electrical.electrical_model import ElectricalModel


@dataclass(frozen=True)
class LoadFlowIssue:
    issue_type: str  # e.g. "voltage_propagation_inconsistent"
    affected_assets: List[str]
    details: Dict[str, object]


def _compute_deterministic_voltages(model: ElectricalModel) -> Dict[str, float]:
    """
    Simplified deterministic "voltage propagation" model:
    - Substation node voltage initialized deterministically (based on node_id)
    - Each edge drops voltage proportional to impedance_ohm
    - This is NOT a power-flow solver; it's an invariant checker.
    """
    if not model.nodes:
        return {}

    def init_voltage(nid: str) -> float:
        # keep within [0.9, 1.1] pu
        h = 0
        for ch in nid:
            h = (h * 17 + ord(ch)) & 0xFFFFFFFF
        pu = 0.9 + (h % 2000) / 20000.0  # 0.9..1.0
        return pu

    # BFS from each node (graph may be disconnected). For each node, compute best-effort.
    volt: Dict[str, float] = {}
    for nid in model.nodes.keys():
        if nid in volt:
            continue
        volt[nid] = init_voltage(nid)

        frontier: List[str] = [nid]
        while frontier:
            cur = frontier.pop(0)
            cur_v = volt[cur]
            # find neighboring edges
            for e in model.edges.values():
                if e.from_node != cur and e.to_node != cur:
                    continue
                nb = e.to_node if e.from_node == cur else e.from_node
                if nb not in volt:
                    # voltage drop proportional to impedance
                    drop_pu = min(0.2, e.impedance_ohm / 50.0)  # bounded
                    volt[nb] = max(0.0, cur_v - drop_pu)
                    frontier.append(nb)

    return volt


def validate_load_flow(model: ElectricalModel) -> Tuple[bool, List[LoadFlowIssue]]:
    """
    Deterministic simplified load-flow validation:
    - Voltage propagation consistency: edge endpoints must not violate bounded drop constraints.
    - Feeder continuity under electrical rules: nodes connected by edges must remain within
      plausible voltage range.
    """
    if not model.edges or not model.nodes:
        return True, []

    volt = _compute_deterministic_voltages(model)

    issues: List[LoadFlowIssue] = []

    for e in model.edges.values():
        v_from = volt.get(e.from_node)
        v_to = volt.get(e.to_node)
        if v_from is None or v_to is None:
            continue

        # Bound drop - since deterministic, a too-large impedance causes inconsistent propagation.
        drop = v_from - v_to
        if drop < 0:
            # Voltage increase along a purely resistive drop model is invalid.
            issues.append(
                LoadFlowIssue(
                    issue_type="voltage_propagation_direction_inconsistent",
                    affected_assets=list(e.asset_ids),
                    details={"edge_id": e.edge_id, "v_from": v_from, "v_to": v_to},
                )
            )
            continue

        if drop > 0.25:
            issues.append(
                LoadFlowIssue(
                    issue_type="voltage_propagation_inconsistent",
                    affected_assets=list(e.asset_ids),
                    details={
                        "edge_id": e.edge_id,
                        "impedance_ohm": e.impedance_ohm,
                        "drop_pu": drop,
                    },
                )
            )

        # Voltage plausibility bounds
        if v_to < 0.7 or v_to > 1.3:
            issues.append(
                LoadFlowIssue(
                    issue_type="voltage_out_of_bounds",
                    affected_assets=list(e.asset_ids),
                    details={"node_id": e.to_node, "v_pu": v_to},
                )
            )

    ok = len(issues) == 0
    return ok, issues
