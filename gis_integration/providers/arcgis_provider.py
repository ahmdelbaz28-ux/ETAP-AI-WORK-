from __future__ import annotations

from gis_integration.exceptions import NotImplementedFeature


class ArcGISProvider:
    """
    🗃️ ARCHIVED — Not implemented; raises NotImplementedFeature.

    This provider was archived as part of WP7 GIS surgery. Use QGISProvider or
    MockGISProvider instead. The factory (gis_integration/providers/__init__.py)
    will raise NotImplementedFeature when 'arcgis' is requested.
    """

    def health_check(self) -> bool:
        raise NotImplementedFeature(
            "ArcGISProvider is archived; use QGISProvider or MockGISProvider"
        )

    def load_project(self, path: str) -> None:
        raise NotImplementedFeature(
            "ArcGISProvider is archived; use QGISProvider or MockGISProvider"
        )

    def list_layers(self) -> list[str]:
        raise NotImplementedFeature(
            "ArcGISProvider is archived; use QGISProvider or MockGISProvider"
        )

    def extract_features(self, layer_id: str):
        raise NotImplementedFeature(
            "ArcGISProvider is archived; use QGISProvider or MockGISProvider"
        )

    def export_geojson(self, layer_id: str) -> dict:
        raise NotImplementedFeature(
            "ArcGISProvider is archived; use QGISProvider or MockGISProvider"
        )

    def get_crs(self, layer_id: str | None = None):
        raise NotImplementedFeature(
            "ArcGISProvider is archived; use QGISProvider or MockGISProvider"
        )
