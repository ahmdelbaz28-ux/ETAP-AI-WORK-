from __future__ import annotations

import logging
import os
from collections.abc import Iterator

from gis_integration.base import GISProviderInterface
from gis_integration.exceptions import GISDataExtractionError, GISProviderUnavailableError
from gis_integration.models import GeoCRSInfo, GISFeature
from gis_integration.utils import safe_parse_geojson, validate_geometry_dict

logger = logging.getLogger(__name__)


class QGISProvider(GISProviderInterface):
    """
    QGIS provider with lazy imports.

    Notes:
    - This implementation is dependency-safe: it does NOT import QGIS on module import.
    - If QGIS bindings are unavailable at runtime, it raises GISProviderUnavailableError.
    - health_check() probes actual QgsApplication availability.
    """

    def __init__(self) -> None:
        self._loaded = False
        self._project_path: str | None = None
        self._crs: GeoCRSInfo = GeoCRSInfo()
        self._layers: list[str] = []
        self._layer_index: dict[str, str] = {}

    def _init_qgs(self, prefix_path: str | None = None) -> None:
        """Initialize QgsApplication if not already initialized.

        Args:
            prefix_path: Optional QGIS prefix path (from QGIS_PREFIX_PATH env var).

        Raises:
            GISProviderUnavailableError: If QGIS cannot be initialized.
        """
        try:
            from qgis.core import QgsApplication  # type: ignore

            if QgsApplication.instance() is None:
                prefix = prefix_path or os.getenv("QGIS_PREFIX_PATH", "")
                QgsApplication.setPrefixPath(prefix if prefix else "/usr", True)
                QgsApplication.initQgis()
        except Exception as exc:
            raise GISProviderUnavailableError(f"Failed to initialize QGIS: {exc}") from exc

    def load_project(self, path: str) -> None:
        try:
            from qgis.core import QgsProject  # type: ignore
        except Exception as exc:
            raise GISProviderUnavailableError(f"QGIS is unavailable: {exc}") from exc

        self._init_qgs()

        self._project_path = path
        try:
            self._project = QgsProject.instance()
            self._project.read(path)
        except Exception as exc:
            raise GISDataExtractionError(f"Failed to load QGIS project: {exc}") from exc

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

    def get_crs(self, layer_id: str | None = None) -> GeoCRSInfo:
        # Best-effort: keep default unless provider can supply.
        # QGIS CRS extraction is omitted here to avoid brittle SDK dependency assumptions.
        return self._crs

    def health_check(self) -> bool:
        try:
            from qgis.core import QgsApplication  # type: ignore

            return QgsApplication.instance() is not None
        except Exception:
            return False
