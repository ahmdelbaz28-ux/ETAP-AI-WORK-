from __future__ import annotations

from gis_integration.exceptions import NotImplementedFeature

MSG_ARCGIS_ARCHIVED = "ArcGISProvider is archived; use QGISProvider or MockGISProvider"


class ArcGISProvider:
    """
    🗃️ ARCHIVED — Not implemented; raises NotImplementedFeature.

    This provider was archived as part of WP7 GIS surgery. Use QGISProvider or
    MockGISProvider instead. The factory (gis_integration/providers/__init__.py)
    will raise NotImplementedFeature when 'arcgis' is requested.
    """

    def health_check(self) -> bool:
        raise NotImplementedFeature(MSG_ARCGIS_ARCHIVED)

    def load_project(self, path: str) -> None:
        raise NotImplementedFeature(MSG_ARCGIS_ARCHIVED)

    def list_layers(self) -> list[str]:
        raise NotImplementedFeature(MSG_ARCGIS_ARCHIVED)

    def extract_features(self, layer_id: str):
        raise NotImplementedFeature(MSG_ARCGIS_ARCHIVED)

    def export_geojson(self, layer_id: str) -> dict:
        raise NotImplementedFeature(MSG_ARCGIS_ARCHIVED)

    def get_crs(self, layer_id: str | None = None):
        raise NotImplementedFeature(MSG_ARCGIS_ARCHIVED)
