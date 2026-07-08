from __future__ import annotations

from collections.abc import Iterator
import logging
from typing import Any

from gis_integration.base import GISProviderInterface
from gis_integration.models import GeoCRSInfo, GISFeature

logger = logging.getLogger(__name__)


class MockGISProvider(GISProviderInterface):
    """
    Mock GIS Provider for testing and development.
    
    Generates high-fidelity simulated spatial features in Egypt/Cairo region,
    allowing the platform to run and display GIS data in environments without
    direct access to desktop QGIS/ArcGIS SDKs (like Docker or Hugging Face Spaces).
    """

    def __init__(self) -> None:
        self._loaded = False
        self._project_path: str | None = None
        self._crs = GeoCRSInfo(crs="EPSG:4326", normalized=True)
        self._layers = ["substations", "lines", "switches"]

        # Mock features database
        self._features_db: dict[str, list[dict[str, Any]]] = {
            "substations": [
                {
                    "id": "sub_cairo_east",
                    "geometry": {"type": "Point", "coordinates": [31.2357, 30.0444]},
                    "properties": {
                        "name": "Cairo East Substation",
                        "voltage_kv": "220",
                        "status": "active",
                        "asset_type": "SUBSTATION"
                    }
                },
                {
                    "id": "sub_helwan",
                    "geometry": {"type": "Point", "coordinates": [31.3357, 29.8444]},
                    "properties": {
                        "name": "Helwan Industrial Substation",
                        "voltage_kv": "220",
                        "status": "active",
                        "asset_type": "SUBSTATION"
                    }
                }
            ],
            "lines": [
                {
                    "id": "line_east_helwan",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[31.2357, 30.0444], [31.3357, 29.8444]]
                    },
                    "properties": {
                        "name": "East-Helwan Intertie",
                        "voltage_kv": "220",
                        "status": "active",
                        "resistance": 0.045,
                        "reactance": 0.125,
                        "asset_type": "LINE"
                    }
                }
            ],
            "switches": [
                {
                    "id": "sw_east_001",
                    "geometry": {"type": "Point", "coordinates": [31.2400, 30.0400]},
                    "properties": {
                        "name": "East Sect. Breaker",
                        "status": "closed",
                        "rated_amps": 1200,
                        "asset_type": "SWITCH"
                    }
                }
            ]
        }

    def load_project(self, path: str) -> None:
        super().load_project(path)
        logger.info("Loaded mock GIS project from path: %s", path)

    def list_layers(self) -> list[str]:
        if not self._loaded:
            raise RuntimeError("No GIS project loaded; call load_project() first")
        return list(self._layers)

    def extract_features(self, layer_id: str) -> Iterator[GISFeature]:
        if not self._loaded:
            raise RuntimeError("No GIS project loaded; call load_project() first")
        
        if layer_id not in self._features_db:
            return iter(())

        for item in self._features_db[layer_id]:
            yield GISFeature(
                id=item["id"],
                geometry=item["geometry"],
                properties=item["properties"],
                layer_name=layer_id,
                crs=self._crs.crs
            )

    def export_geojson(self, layer_id: str) -> dict:
        if not self._loaded:
            raise RuntimeError("No GIS project loaded; call load_project() first")
        
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

    def get_crs(self, layer_id: str | None = None) -> GeoCRSInfo:
        return self._crs

    def health_check(self) -> bool:
        return True
