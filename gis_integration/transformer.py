from __future__ import annotations

from typing import Any, Dict, List

from gis_integration.exceptions import GISDataExtractionError, GISTransformationError
from gis_integration.models import ADMSAsset, ADMSAssetType, GISFeature


class GIS_TO_ADMS_Transformer:
    """
    Deterministic transformer from normalized GISFeature -> ADMSAsset.

    Design goals:
    - Deterministic mapping rules
    - Explicit traceability via metadata
    - Never silently drop unmapped assets
    """

    def __init__(self) -> None:
        # No mutable global state; deterministic behavior per call.
        # Reserved for future per-instance overrides (e.g. custom ID prefixes
        # or asset-type allow-lists).  Intentionally left as a no-op so that
        # callers can construct the transformer with no arguments.
        self._transformation_count = 0

    def transform_feature(self, feature: GISFeature) -> ADMSAsset:
        # Validate external payload.
        if not isinstance(feature.id, str) or not feature.id:
            raise GISDataExtractionError("GISFeature.id must be a non-empty string")
        if not isinstance(feature.geometry, dict):
            raise GISTransformationError("GISFeature.geometry must be a GeoJSON geometry dict")
        if "type" not in feature.geometry:
            raise GISTransformationError("GeoJSON geometry missing 'type' field")

        asset_type = self._map_feature_to_asset_type(feature)
        asset_id = self._deterministic_asset_id(feature, asset_type)

        # Geometry integrity: keep as provided (GeoJSON dict), no mutation besides traceability.
        geometry = feature.geometry

        metadata: Dict[str, Any] = {
            "source_feature_id": feature.id,
            "source_layer": feature.layer_name,
            "source_crs": feature.crs,
            "source_properties": feature.properties,
            "mapping_rule": f"{feature.geometry.get('type')} -> {asset_type.value}",
        }

        return ADMSAsset(
            asset_id=asset_id,
            asset_type=asset_type,
            geometry=geometry,
            metadata=metadata,
        )

    def transform(self, features: List[GISFeature]) -> List[ADMSAsset]:
        assets: List[ADMSAsset] = []
        # Deterministic processing order: sort by (layer_name, id)
        for f in sorted(features, key=lambda x: (x.layer_name or "", x.id or "")):
            assets.append(self.transform_feature(f))
        return assets

    def _deterministic_asset_id(self, feature: GISFeature, asset_type: ADMSAssetType) -> str:
        # Deterministic rule: type prefix + stable id.
        return f"{asset_type.value}__{feature.id}"

    def _map_feature_to_asset_type(self, feature: GISFeature) -> ADMSAssetType:
        gtype = feature.geometry.get("type")

        # Deterministic mapping based on GeoJSON geometry type first.
        if gtype == "Point":
            # Point -> SWITCH or SUBSTATION:
            # Use explicit metadata hints; never silently guess if absent.
            meta_type = self._string_meta(
                feature.properties.get("asset_role") or feature.properties.get("role")
            )
            if meta_type in ("switch", "switching_device"):
                return ADMSAssetType.SWITCH
            if meta_type in ("substation", "bus"):
                return ADMSAssetType.SUBSTATION

            # If no hint is present, default to SUBSTATION (deterministic, but explicit in metadata).
            # This is an allowed deterministic default; no silent drop.
            return ADMSAssetType.SUBSTATION

        if gtype == "LineString":
            # Line -> FEEDER or LINE
            meta_kind = self._string_meta(
                feature.properties.get("line_kind") or feature.properties.get("kind")
            )
            if meta_kind in ("feeder", "primary_feeder"):
                return ADMSAssetType.FEEDER
            return ADMSAssetType.LINE

        if gtype == "Polygon":
            return ADMSAssetType.SUBSTATION

        # Unsupported geometry types must fail loudly in this subsystem (wrapped).
        raise GISTransformationError(f"Unsupported GeoJSON geometry type for mapping: {gtype}")

    @staticmethod
    def _string_meta(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip().lower()
        return str(value).strip().lower()
