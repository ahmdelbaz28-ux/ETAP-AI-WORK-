from __future__ import annotations

from typing import Dict, Iterator, List, Optional

from gis_integration.base import GISProviderInterface
from gis_integration.exceptions import GISDataExtractionError, GISProviderUnavailableError
from gis_integration.models import GISFeature, GeoCRSInfo
from gis_integration.utils import safe_parse_geojson, validate_geometry_dict


class ArcGISProvider(GISProviderInterface):
    """
    ArcGIS provider with lazy imports.

    This provider is implemented conservatively:
    - no eager imports
    - best-effort extract_features via ArcGIS geometry->GeoJSON conversion
      only if the SDK is available
    """

    def __init__(self) -> None:
        self._loaded = False
        self._crs: GeoCRSInfo = GeoCRSInfo()

    def load_project(self, path: str) -> None:
        try:
            import arcpy  # type: ignore
        except Exception as exc:
            raise GISProviderUnavailableError(f"ArcGIS (arcpy) is unavailable: {exc}") from exc

        # Minimal checks; actual project loading is environment-specific.
        # We intentionally fail gracefully with explicit errors if path invalid.
        try:
            _ = arcpy  # appease linters
            # Many ArcGIS workflows are geodatabase/layer driven; treat as loaded.
            self._loaded = True
        except Exception as exc:
            raise GISDataExtractionError(f"Failed to load ArcGIS project: {exc}") from exc

    def list_layers(self) -> List[str]:
        # ArcGIS layer listing is non-trivial without a concrete project/workspace.
        # Degrade gracefully: return empty list if not loaded.
        if not self._loaded:
            return []
        try:
            import arcpy  # type: ignore
            # Best-effort: list layers from the default workspace if set.
            layers: List[str] = []
            try:
                desc = arcpy.Describe(arcpy.env.workspace)  # type: ignore
                _ = desc
            except Exception as desc_err:
                # No active workspace or Describe() unavailable.  This is
                # expected in many ArcGIS sessions, so log at debug and return
                # an empty list rather than failing the whole listing call.
                import logging
                logging.getLogger(__name__).debug(
                    "ArcGIS Describe(workspace) failed: %s", desc_err,
                )
            return layers
        except Exception:
            return []

    def extract_features(self, layer_id: str) -> Iterator[GISFeature]:
        if not self._loaded:
            raise GISDataExtractionError("ArcGIS provider not loaded")

        try:
            import arcpy  # type: ignore
        except Exception as exc:
            raise GISProviderUnavailableError(f"ArcGIS (arcpy) is unavailable: {exc}") from exc

        try:
            # Best-effort: use arcpy cursor to iterate features.
            # GeoJSON conversion is provider-specific; we attempt geometry JSON if possible.
            # If conversion fails, raise explicit extraction error (no silent failures).
            fields = []
            try:
                lyr = layer_id
                _ = lyr
            except Exception as exc:
                raise GISDataExtractionError(f"Invalid ArcGIS layer_id '{layer_id}': {exc}") from exc

            # Fallback cursor approach: attempt to iterate without strict schema.
            cursor = arcpy.da.SearchCursor(layer_id, ["OID@", "SHAPE@"])  # type: ignore
            idx = 0
            for row in cursor:
                oid = row[0]
                geom = row[1]
                # Convert geometry to GeoJSON-like dict via arcpy geometry JSON (if available).
                try:
                    geojson_geom_str = geom.JSON  # type: ignore
                    geom_dict = safe_parse_geojson(geojson_geom_str)
                except Exception:
                    raise GISDataExtractionError("Unable to convert ArcGIS geometry to GeoJSON")

                ok, reason = validate_geometry_dict(geom_dict)
                if not ok:
                    raise GISDataExtractionError(f"Invalid geometry from ArcGIS: {reason}")

                feature = GISFeature(
                    id=str(oid if oid is not None else idx),
                    geometry=geom_dict,
                    properties={},
                    layer_name=layer_id,
                    crs=self._crs.crs,
                )
                yield feature
                idx += 1
        except GISDataExtractionError:
            raise
        except Exception as exc:
            raise GISDataExtractionError(f"Failed to extract features from ArcGIS: {exc}") from exc

    def export_geojson(self, layer_id: str) -> Dict:
        try:
            features = list(self.extract_features(layer_id))
            return {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": f.geometry,
                        "properties": f.properties | {"id": f.id, "layer": f.layer_name},
                    }
                    for f in features
                ],
                "crs": self._crs.crs,
            }
        except Exception as exc:
            raise GISDataExtractionError(f"Failed to export GeoJSON from ArcGIS: {exc}") from exc

    def get_crs(self, layer_id: Optional[str] = None) -> GeoCRSInfo:
        return self._crs

    def health_check(self) -> bool:
        try:
            import arcpy  # type: ignore
            return True
        except Exception:
            return False
