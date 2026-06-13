from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from gis_integration.models import GISFeature
from gis_integration.transformer import GIS_TO_ADMS_Transformer
from gis_validation.crs_validator import validate_crs_consistency, validate_normalization_applied
from gis_validation.topology_validator import validate_adms_topology as topo_validate


@dataclass(frozen=True)
class GroundTruthMismatch:
    mismatch_type: str
    affected_assets: List[str]
    details: Dict[str, Any]


def _feature_count(assets: List[Any]) -> int:
    return len(assets)


def validate_real_gis_to_adms(
    *,
    extracted_features: List[GISFeature],
) -> Tuple[bool, Dict[str, Any]]:
    """
    Ground truth validator compares:
    - GIS extracted features (source of truth)
    - ADMS transformed assets (system result)

    Determinism constraints:
    - Use gis_integration.GIS_TO_ADMS_Transformer to produce assets.
    - Compare counts + basic invariants. (Full electrical fidelity is
      handled by topology validator + CRS checks here.)
    """
    transformer = GIS_TO_ADMS_Transformer()

    adms_assets = transformer.transform(extracted_features)

    # CRS checks (metadata-based; real SDK normalization is not executed here)
    ok_crs, issues_crs = validate_crs_consistency(adms_assets)
    ok_norm, issues_norm = validate_normalization_applied(adms_assets)

    # Topology/graph checks (geometry endpoint-based)
    ok_topo, issues_topo = topo_validate(adms_assets)

    mismatches: List[GroundTruthMismatch] = []

    # Feature count vs asset count (best-effort expectation: 1 feature -> 1 asset)
    if _feature_count(extracted_features) != _feature_count(adms_assets):
        mismatches.append(
            GroundTruthMismatch(
                mismatch_type="feature_asset_count_mismatch",
                affected_assets=[a.asset_id for a in adms_assets],
                details={
                    "gis_feature_count": _feature_count(extracted_features),
                    "adms_asset_count": _feature_count(adms_assets),
                },
            )
        )

    # Classification:
    ok = (ok_crs and ok_norm and ok_topo and len(mismatches) == 0)

    report = {
        "adms_assets": adms_assets,
        "ok_crs": ok_crs,
        "crs_issues": [i.__dict__ for i in issues_crs],
        "ok_norm": ok_norm,
        "norm_issues": [i.__dict__ for i in issues_norm],
        "ok_topology": ok_topo,
        "topology_issues": [i.__dict__ for i in issues_topo],
        "mismatches": [m.__dict__ for m in mismatches],
    }

    return ok, report
