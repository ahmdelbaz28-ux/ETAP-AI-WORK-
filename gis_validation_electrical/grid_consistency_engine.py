from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from gis_integration.models import ADMSAsset
from gis_validation_electrical.cim_mapper import CIMModel, map_adms_to_cim
from gis_validation_electrical.electrical_model import ElectricalModel, build_electrical_model
from gis_validation_electrical.impedance_validator import validate_impedance_consistency
from gis_validation_electrical.load_flow_validator import validate_load_flow
from gis_validation_electrical.radiality_checker import validate_radiality


@dataclass(frozen=True)
class ElectricalFailure:
    failure_classification: str  # GEOMETRIC_ERROR, TOPOLOGY_ERROR, ELECTRICAL_ERROR, CIM_MISMATCH, LOADFLOW_INCONSISTENCY
    asset_ids: List[str]
    root_cause: str
    details: Dict[str, Any]


@dataclass(frozen=True)
class GridConsistencyReport:
    ok: bool
    failures: List[ElectricalFailure]
    electrical_model: ElectricalModel | None = None
    cim_model: CIMModel | None = None


def grid_consistency_engine(assets: List[ADMSAsset]) -> GridConsistencyReport:
    """
    Final electrical grid consistency validation layer.

    Validates:
      - electrical topology compliance (radiality/islands/loops)
      - impedance consistency
      - simplified deterministic load-flow invariants
      - CIM mapping consistency (traceability present and connectivity node coverage)

    Returns a report with explicit, traceable failure classification.
    """
    failures: List[ElectricalFailure] = []

    # Core electrical model build (deterministic from ADMS assets)
    model = build_electrical_model(assets)
    if not model.nodes and not model.edges:
        # If transformation produced no electrical model, treat as failure.
        failures.append(
            ElectricalFailure(
                failure_classification="ELECTRICAL_ERROR",
                asset_ids=[a.asset_id for a in assets],
                root_cause="electrical_model_empty",
                details={},
            )
        )
        return GridConsistencyReport(ok=False, failures=failures, electrical_model=model, cim_model=None)

    # Radiality compliance (electrical graph theory)
    ok_rad, rad_issues = validate_radiality(model)
    if not ok_rad:
        for i in rad_issues:
            failures.append(
                ElectricalFailure(
                    failure_classification="ELECTRICAL_ERROR",
                    asset_ids=list(set(i.affected_edges)) if i.affected_edges else [],
                    root_cause=i.issue_type,
                    details=dict(i.details),
                )
            )

    # Impedance consistency
    ok_imp, imp_issues = validate_impedance_consistency(model)
    if not ok_imp:
        for i in imp_issues:
            failures.append(
                ElectricalFailure(
                    failure_classification="ELECTRICAL_ERROR",
                    asset_ids=list(set(i.affected_edges)) if i.affected_edges else [],
                    root_cause=i.issue_type,
                    details=dict(i.details),
                )
            )

    # Load-flow simplified validation (deterministic invariants)
    ok_lf, lf_issues = validate_load_flow(model)
    if not ok_lf:
        for i in lf_issues:
            failures.append(
                ElectricalFailure(
                    failure_classification="LOADFLOW_INCONSISTENCY",
                    asset_ids=list(set(i.affected_assets)) if i.affected_assets else [],
                    root_cause=i.issue_type,
                    details=dict(i.details),
                )
            )

    # CIM mapping consistency (traceability + node coverage)
    cim: CIMModel = map_adms_to_cim(assets)

    # Traceability: ensure every CE/CN is mapped back to some ADMS asset_id deterministically
    if not cim.traceability:
        failures.append(
            ElectricalFailure(
                failure_classification="CIM_MISMATCH",
                asset_ids=[a.asset_id for a in assets],
                root_cause="cim_traceability_empty",
                details={},
            )
        )
    else:
        # ConnectivityNode coverage: all electrical model nodes must have CIM connectivity nodes
        for node_id in model.nodes.keys():
            cn_id = f"CN::{node_id}"
            if cn_id not in cim.connectivity_nodes:
                failures.append(
                    ElectricalFailure(
                        failure_classification="CIM_MISMATCH",
                        asset_ids=[node_id],
                        root_cause="missing_connectivity_node_in_cim",
                        details={"connectivity_node_id": cn_id},
                    )
                )

    ok = len(failures) == 0
    return GridConsistencyReport(ok=ok, failures=failures, electrical_model=model, cim_model=cim)
