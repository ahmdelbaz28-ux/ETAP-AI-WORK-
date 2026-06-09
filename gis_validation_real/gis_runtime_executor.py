from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from gis_integration.exceptions import GISIntegrationError
from gis_integration.models import GISFeature
from gis_integration.transformer import GIS_TO_ADMS_Transformer
from gis_validation.crs_validator import validate_crs_consistency, validate_normalization_applied
from gis_validation.topology_validator import validate_adms_topology


@dataclass(frozen=True)
class RuntimeExtractionResult:
    provider_name: str
    project_path: str
    extracted_layers: Dict[str, List[GISFeature]]


@dataclass(frozen=True)
class RuntimeTransformationResult:
    adms_assets: List[Any]


def validate_real_assets_runtime(*, extracted_assets: List[GISFeature]) -> Dict[str, Any]:
    """
    Runtime validation for real assets:
    - transform using gis_integration.GIS_TO_ADMS_Transformer
    - validate CRS via metadata
    - validate topology via graph model
    """
    transformer = GIS_TO_ADMS_Transformer()
    adms_assets = transformer.transform(extracted_assets)

    ok_crs, issues_crs = validate_crs_consistency(adms_assets)
    ok_norm, issues_norm = validate_normalization_applied(adms_assets)
    ok_topo, issues_topo = validate_adms_topology(adms_assets)

    return {
        "adms_assets": adms_assets,
        "crs_ok": ok_crs,
        "crs_issues": [i.__dict__ for i in issues_crs],
        "norm_ok": ok_norm,
        "norm_issues": [i.__dict__ for i in issues_norm],
        "topology_ok": ok_topo,
        "topology_issues": [i.__dict__ for i in issues_topo],
    }
