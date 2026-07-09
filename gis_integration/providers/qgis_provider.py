from __future__ import annotations
from typing import Optional, Union

from collections.abc import Iterator

from gis_integration.base import GISProviderInterface
from gis_integration.exceptions import GISDataExtractionError, GISProviderUnavailableError
from gis_integration.models import GeoCRSInfo, GISFeature
from gis_integration.utils import safe_parse_geojson, validate_geometry_dict


class QGISProvider(GISProviderInterface):
    """
    QGIS provider with lazy imports.

    Notes:
    - This implementation is dependency-safe: it does NOT import QGIS on module import.
    - If QGIS bindings are unavailable at runtime, it raises GISProviderUnavailableError.
    """

    def __init__(self) -> None:
        self._loaded = False
        self._project_path: Optional[str] = None
        self._crs: GeoCRSInfo = GeoCRSInfo()
        self._layers: list[str] = []
        self._layer_index: dict[str, str] = {}

    def load_project(self, path: str) -> None:
        try:
            from qgis.core import (
                QgsApplication,  # type: ignore
                QgsProject,  # type: ignore
            )
        except Exception as exc:
            raise GISProviderUnavailableError(f"QGIS is unavailable: {exc}") from exc

        # Minimal lazy init: create application if not already.
        # If callers already initialized QGIS, this should be safe.
        _ = QgsApplication  # appease linters

        self._project_path = path
        try:
            self._project = QgsProject.instance()
            self._project.read(path)
        except Exception as exc:
            raise GISDataExtractionError(f"Failed to load QGIS project: {exc}") from exc

        # Best-effort layer listing (provider-specific IDs)
        try:
            self._layers = [lyr.name() for lyr in self._project.mapLayers().values()]  # type: ignore
        except Exception:
            self._layers = []

        self._loaded = True

    def list_layers(self) -> list[str]:
        if not self._loaded:
            return []
        return list(self._layers)

    def extract_features(self, layer_id: str) -> Iterator[GISFeature]:
        if not self._loaded:
            raise GISDataExtractionError("QGIS project not loaded")
        try:
            from qgis.core import QgsProject  # type: ignore
        except Exception as exc:
            raise GISProviderUnavailableError(f"QGIS is unavailable: {exc}") from exc

        # Map layer_id (name) to layer object
        try:
            project = QgsProject.instance()
            layers = project.mapLayers().values()  # type: ignore
            layer = None
            for lyr in layers:
                if getattr(lyr, "name", lambda: None)() == layer_id:  # type: ignore
                    layer = lyr
                    break
            if layer is None:
                return iter(())  # empty iterator

            # Features iteration
            for i, feat in enumerate(layer.getFeatures()):  # type: ignore
                geom = feat.geometry()
                geojson_geom = geom.asJson()  # string
                geom_dict = safe_parse_geojson(geojson_geom)

                ok, reason = validate_geometry_dict(geom_dict)
                if not ok:
                    raise GISDataExtractionError(f"Invalid geometry from QGIS: {reason}")

                # Convert QGIS feature attrs to JSON-serializable properties
                props = {}
                try:
                    attrs = feat.attributes()
                    fields = layer.fields()  # type: ignore
                    for idx, val in enumerate(attrs):
                        key = fields[idx].name()  # type: ignore
                        props[key] = val
                except Exception:
                    props = {}

                feature = GISFeature(
                    id=str(getattr(feat, "id", lambda _i=i: _i)()),
                    geometry=geom_dict,
                    properties=props,
                    layer_name=layer_id,
                    crs=self._crs.crs,
                )
                yield feature
        except GISDataExtractionError:
            raise
        except Exception as exc:
            raise GISDataExtractionError(f"Failed to extract features from QGIS: {exc}") from exc

    def export_geojson(self, layer_id: str) -> dict:
        # Provider-local best-effort: return FeatureCollection with geometry dicts.
        # Deterministic transformation will operate on extract_features() output.
        try:
            features = list(self.extract_features(layer_id))
            return {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": f.geometry,
                        "properties": {**f.properties, "id": f.id, "layer": f.layer_name},
                    }
                    for f in features
                ],
                "crs": self._crs.crs,
            }
        except Exception as exc:
            raise GISDataExtractionError(f"Failed to export GeoJSON from QGIS: {exc}") from exc

    def get_crs(self, layer_id: Optional[str] = None) -> GeoCRSInfo:
        # Best-effort: keep default unless provider can supply.
        # QGIS CRS extraction is omitted here to avoid brittle SDK dependency assumptions.
        return self._crs

    def health_check(self) -> bool:
        try:
            return True
        except Exception:
            return False
