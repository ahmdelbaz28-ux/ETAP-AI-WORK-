from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from gis_integration.models import ADMSAsset, ADMSAssetType


@dataclass(frozen=True)
class CRSIssue:
    issue_type: str
    affected_assets: List[str]
    details: Dict[str, Any]


def _asset_source_crs(asset: ADMSAsset) -> Optional[str]:
    # Deterministic: transformer stores source_crs in metadata.
    try:
        return asset.metadata.get("source_crs")
    except Exception:
        return None


def _normalize_epsg(crs: Optional[str]) -> Optional[str]:
    if not crs or not isinstance(crs, str):
        return None
    s = crs.strip().upper()
    # accept common forms: "EPSG:4326", "EPSG:3857"
    if s.startswith("EPSG:"):
        return s
    return s


def validate_crs_consistency(assets: List[ADMSAsset]) -> Tuple[bool, List[CRSIssue]]:
    """
    CRS rules (deterministic, no external libs):
    - All assets must declare a consistent source CRS (metadata.source_crs).
    - At least one CRS must be present if any assets exist.
    """
    if not assets:
        return False, [CRSIssue("empty_assets", [], {"reason": "No assets provided"})]

    crs_values: Set[str] = set()
    missing: List[str] = []
    for a in assets:
        crs = _normalize_epsg(_asset_source_crs(a))
        if not crs:
            missing.append(a.asset_id)
        else:
            crs_values.add(crs)

    issues: List[CRSIssue] = []
    if missing:
        issues.append(CRSIssue("missing_crs_metadata", missing, {}))

    if len(crs_values) > 1:
        # mixed CRS contamination
        issues.append(
            CRSIssue(
                "mixed_crs_contamination",
                sorted([a.asset_id for a in assets]),
                {"crs_values": sorted(crs_values)},
            )
        )

    ok = len(issues) == 0
    return ok, issues


def validate_normalization_applied(assets: List[ADMSAsset]) -> Tuple[bool, List[CRSIssue]]:
    """
    Ensure metadata has source_crs; this subsystem assumes transformer already normalized.
    """
    if not assets:
        return False, [CRSIssue("empty_assets", [], {"reason": "No assets provided"})]

    issues: List[CRSIssue] = []
    missing_any = [a.asset_id for a in assets if not _asset_source_crs(a)]
    if missing_any:
        issues.append(CRSIssue("normalization_not_applied", missing_any, {}))

    return len(issues) == 0, issues
