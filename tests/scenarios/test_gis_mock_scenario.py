import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from gis_integration.providers import MockGISProvider, get_gis_provider


class TestGISMockScenario:
    """Scenario tests verifying the MockGISProvider and get_gis_provider factory."""

    def test_factory_resolves_mock_provider(self, monkeypatch):
        """Test that get_gis_provider resolves MockGISProvider when configured."""
        # Scenario A: Explicit provider_type="mock"
        provider = get_gis_provider("mock")
        assert isinstance(provider, MockGISProvider)
        assert provider.health_check() is True

        # Scenario B: Environment variable USE_MOCK_GIS=true
        monkeypatch.setenv("USE_MOCK_GIS", "true")
        provider_env = get_gis_provider("qgis")
        assert isinstance(provider_env, MockGISProvider)

    def test_mock_provider_lifecycle(self):
        """Test the lifecycle methods load_project, list_layers, and get_crs."""
        provider = MockGISProvider()

        # Must raise error if project not loaded
        with pytest.raises(RuntimeError, match="No GIS project loaded"):
            provider.list_layers()

        # Load project
        provider.load_project("c:/cairo_grid.qgs")

        # Verify layers
        layers = provider.list_layers()
        assert "substations" in layers
        assert "lines" in layers
        assert "switches" in layers

        # Verify CRS
        crs_info = provider.get_crs()
        assert crs_info.crs == "EPSG:4326"
        assert crs_info.normalized is True

    def test_mock_feature_extraction(self):
        """Test feature extraction yields valid GISFeature structures."""
        provider = MockGISProvider()
        provider.load_project("c:/cairo_grid.qgs")

        # Extract features from substations layer
        features = list(provider.extract_features("substations"))
        assert len(features) == 2
        assert features[0].id == "sub_cairo_east"
        assert features[0].geometry["type"] == "Point"
        assert features[0].properties["voltage_kv"] == "220"

        # Extract features from lines layer
        lines = list(provider.extract_features("lines"))
        assert len(lines) == 1
        assert lines[0].id == "line_east_helwan"
        assert lines[0].geometry["type"] == "LineString"

    def test_mock_geojson_export(self):
        """Test exporting layer as GeoJSON FeatureCollection."""
        provider = MockGISProvider()
        provider.load_project("c:/cairo_grid.qgs")

        geojson = provider.export_geojson("substations")
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 2
        assert geojson["features"][0]["properties"]["id"] == "sub_cairo_east"
        assert geojson["crs"] == "EPSG:4326"
