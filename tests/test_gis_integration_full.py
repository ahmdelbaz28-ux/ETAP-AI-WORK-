"""
Full-stack integration tests for the GIS integration subsystem.

Covers:
- ArcGIS provider (mocked arcpy)
- PostGIS provider (fallback + mocked psycopg2)
- QGIS provider (mocked qgis.core)
- GIS models: GISFeature, ADMSAsset, GeoCRSInfo
- GIS transformer: GISFeature → ADMSAsset
- Topology validator: graph connectivity, island detection
- CRS validator: EPSG consistency, normalization checks
- Error handling across all providers

All external dependencies (arcpy, psycopg2, qgis.core) are mocked.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import pytest

from gis_integration.exceptions import (
    GISDataExtractionError,
    GISIntegrationError,
    GISProviderUnavailableError,
    GISTransformationError,
)
from gis_integration.models import ADMSAsset, ADMSAssetType, GeoCRSInfo, GISFeature
from gis_integration.transformer import GIS_TO_ADMS_Transformer
from gis_integration.utils import is_json_serializable, safe_parse_geojson, validate_geometry_dict
from gis_validation.crs_validator import (
    CRSIssue,
    _asset_source_crs,
    _normalize_epsg,
    validate_crs_consistency,
    validate_normalization_applied,
)
from gis_validation.topology_validator import (
    ADMSGraphModel,
    TopologyIssue,
    validate_adms_topology,
)

# ===========================================================================
# Helpers
# ===========================================================================


def _make_feature(
    fid: str = "feat-1",
    geometry: Dict[str, Any] | None = None,
    properties: Dict[str, Any] | None = None,
    layer_name: str = "layer-1",
    crs: str = "EPSG:4326",
) -> GISFeature:
    """Create a GISFeature with sensible defaults."""
    if geometry is None:
        geometry = {"type": "Point", "coordinates": [31.0, 30.0]}
    if properties is None:
        properties = {}
    return GISFeature(
        id=fid,
        geometry=geometry,
        properties=properties,
        layer_name=layer_name,
        crs=crs,
    )


def _make_asset(
    asset_id: str = "asset-1",
    asset_type: ADMSAssetType = ADMSAssetType.SUBSTATION,
    geometry: Dict[str, Any] | None = None,
    metadata: Dict[str, Any] | None = None,
) -> ADMSAsset:
    """Create an ADMSAsset with sensible defaults."""
    if geometry is None:
        geometry = {"type": "Point", "coordinates": [31.0, 30.0]}
    if metadata is None:
        metadata = {"source_crs": "EPSG:4326"}
    return ADMSAsset(
        asset_id=asset_id,
        asset_type=asset_type,
        geometry=geometry,
        metadata=metadata,
    )


# ===========================================================================
# 1. ArcGIS Provider — Feature Service Queries & Auth
# ===========================================================================


class TestArcGISProvider:
    """Test ArcGIS provider with mocked arcpy SDK."""

    def test_load_project_raises_when_arcpy_unavailable(self):
        """load_project should raise GISProviderUnavailableError if arcpy missing."""
        from gis_integration.providers.arcgis_provider import ArcGISProvider

        provider = ArcGISProvider()
        with patch.dict("sys.modules", {"arcpy": None}):
            # Force the import to fail
            with patch("builtins.__import__", side_effect=ImportError("no arcpy")):
                with pytest.raises(GISProviderUnavailableError, match="unavailable"):
                    provider.load_project("/tmp/test.gdb")

    def test_list_layers_returns_empty_when_not_loaded(self):
        """list_layers should return [] if provider not loaded."""
        from gis_integration.providers.arcgis_provider import ArcGISProvider

        provider = ArcGISProvider()
        assert provider.list_layers() == []

    def test_extract_features_raises_when_not_loaded(self):
        """extract_features should raise GISDataExtractionError if not loaded."""
        from gis_integration.providers.arcgis_provider import ArcGISProvider

        provider = ArcGISProvider()
        with pytest.raises(GISDataExtractionError, match="not loaded"):
            list(provider.extract_features("layer-1"))

    def test_export_geojson_raises_on_failure(self):
        """export_geojson should raise GISDataExtractionError on failure."""
        from gis_integration.providers.arcgis_provider import ArcGISProvider

        provider = ArcGISProvider()
        with pytest.raises(GISDataExtractionError):
            provider.export_geojson("nonexistent-layer")

    def test_get_crs_returns_default(self):
        """get_crs should return default GeoCRSInfo (EPSG:4326)."""
        from gis_integration.providers.arcgis_provider import ArcGISProvider

        provider = ArcGISProvider()
        crs_info = provider.get_crs()
        assert crs_info.crs == "EPSG:4326"

    def test_health_check_returns_true(self):
        """health_check should return True."""
        from gis_integration.providers.arcgis_provider import ArcGISProvider

        provider = ArcGISProvider()
        assert provider.health_check() is True

    def test_extract_features_with_mocked_arcpy(self):
        """extract_features should yield GISFeatures when arcpy is available."""
        from gis_integration.providers.arcgis_provider import ArcGISProvider

        provider = ArcGISProvider()
        provider._loaded = True  # Pretend loaded

        # Mock the arcpy module and SearchCursor
        mock_geom = Mock()
        mock_geom.JSON = '{"type": "Point", "coordinates": [31.5, 30.5]}'

        mock_cursor = iter([(1, mock_geom), (2, mock_geom)])

        mock_arcpy = Mock()
        mock_arcpy.da.SearchCursor.return_value = mock_cursor

        with patch.dict("sys.modules", {"arcpy": mock_arcpy, "arcpy.da": mock_arcpy.da}):
            with patch(
                "gis_integration.providers.arcgis_provider.safe_parse_geojson"
            ) as mock_parse:
                mock_parse.return_value = {"type": "Point", "coordinates": [31.5, 30.5]}
                with patch(
                    "gis_integration.providers.arcgis_provider.validate_geometry_dict"
                ) as mock_validate:
                    mock_validate.return_value = (True, "ok")
                    features = list(provider.extract_features("test_layer"))

        assert len(features) == 2
        assert isinstance(features[0], GISFeature)
        assert features[0].id == "1"


# ===========================================================================
# 2. PostGIS Provider — SQL Queries, Geometry, Connection Pool
# ===========================================================================


class TestPostGISProvider:
    """Test PostGIS provider in fallback mode and with mocked psycopg2."""

    def test_fallback_mode_when_psycopg2_missing(self):
        """PostGIS provider should use fallback when psycopg2 is not installed."""
        from gis_integration.providers.postgis_provider import PostGISProvider

        provider = PostGISProvider(dsn="", schema="test")
        # In test env, psycopg2 is likely not installed
        if provider.using_fallback:
            assert provider.is_connected() is False

    @pytest.fixture
    def fallback_provider(self):
        """Create a PostGIS provider in file fallback mode."""
        from gis_integration.providers.postgis_provider import PostGISProvider, SpatialAsset

        provider = PostGISProvider(dsn="", schema="test_schema")
        provider._fallback_dir = tempfile.mkdtemp(prefix="postgis_test_")
        provider._use_fallback = True
        provider._connected = False
        return provider

    def test_upsert_and_retrieve_asset(self, fallback_provider):
        """Upserting and retrieving an asset should preserve all fields."""
        from gis_integration.providers.postgis_provider import SpatialAsset

        asset = SpatialAsset(
            asset_id="BUS001",
            asset_type="bus",
            geometry={"type": "Point", "coordinates": [31.2, 30.0]},
            properties={"voltage_level": "11kV"},
            electrical_id="bus_1",
        )
        assert fallback_provider.upsert_asset(asset) is True
        retrieved = fallback_provider.get_asset("BUS001")
        assert retrieved is not None
        assert retrieved.asset_id == "BUS001"
        assert retrieved.asset_type == "bus"
        assert retrieved.geometry == {"type": "Point", "coordinates": [31.2, 30.0]}

    def test_query_within_radius_fallback(self, fallback_provider):
        """Fallback radius query should use haversine distance."""
        from gis_integration.providers.postgis_provider import SpatialAsset

        # Insert asset at known location
        asset = SpatialAsset(
            asset_id="NEAR",
            asset_type="substation",
            geometry={"type": "Point", "coordinates": [31.001, 30.001]},
        )
        fallback_provider.upsert_asset(asset)

        # Query within 1 km
        results = fallback_provider.query_within_radius(30.001, 31.001, 1000)
        assert len(results) >= 1

        # Query far away
        far_results = fallback_provider.query_within_radius(0.0, 0.0, 100)
        assert len(far_results) == 0

    def test_query_in_bbox_fallback(self, fallback_provider):
        """Fallback bbox query should filter by coordinate bounds."""
        from gis_integration.providers.postgis_provider import SpatialAsset

        asset = SpatialAsset(
            asset_id="INBOX",
            asset_type="bus",
            geometry={"type": "Point", "coordinates": [31.0, 30.0]},
        )
        fallback_provider.upsert_asset(asset)

        results = fallback_provider.query_in_bbox(29.0, 30.0, 31.0, 32.0)
        assert len(results) >= 1

    def test_health_check_fallback_mode(self, fallback_provider):
        """health_check should report fallback status."""
        health = fallback_provider.health_check()
        assert health["status"] == "fallback"
        assert health["mode"] == "file"

    def test_mocked_live_mode_upsert(self):
        """Test upsert_asset with mocked psycopg2 connection pool."""
        from gis_integration.providers.postgis_provider import PostGISProvider, SpatialAsset

        provider = PostGISProvider.__new__(PostGISProvider)
        provider.dsn = "postgresql://test:test@localhost/db"
        provider.schema = "test_schema"
        provider._use_fallback = False
        provider._connected = True

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        provider._pool = Mock()
        provider._pool.getconn.return_value = mock_conn

        asset = SpatialAsset(
            asset_id="LIVE01",
            asset_type="bus",
            geometry={"type": "Point", "coordinates": [31.0, 30.0]},
        )
        result = provider.upsert_asset(asset)
        assert result is True
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()


# ===========================================================================
# 3. QGIS Provider — Project Loading, Layer Access, Processing
# ===========================================================================


class TestQGISProvider:
    """Test QGIS provider with mocked QGIS SDK."""

    def test_load_project_raises_when_qgis_unavailable(self):
        """load_project should raise GISProviderUnavailableError if QGIS missing."""
        from gis_integration.providers.qgis_provider import QGISProvider

        provider = QGISProvider()
        with patch("builtins.__import__", side_effect=ImportError("no qgis")):
            with pytest.raises(GISProviderUnavailableError, match="unavailable"):
                provider.load_project("/tmp/test.qgs")

    def test_list_layers_returns_empty_when_not_loaded(self):
        """list_layers should return [] if project not loaded."""
        from gis_integration.providers.qgis_provider import QGISProvider

        provider = QGISProvider()
        assert provider.list_layers() == []

    def test_extract_features_raises_when_not_loaded(self):
        """extract_features should raise if project not loaded."""
        from gis_integration.providers.qgis_provider import QGISProvider

        provider = QGISProvider()
        with pytest.raises(GISDataExtractionError, match="not loaded"):
            list(provider.extract_features("layer-1"))

    def test_get_crs_returns_default(self):
        """get_crs should return default GeoCRSInfo."""
        from gis_integration.providers.qgis_provider import QGISProvider

        provider = QGISProvider()
        crs = provider.get_crs()
        assert crs.crs == "EPSG:4326"

    def test_health_check_returns_true(self):
        """health_check should return True."""
        from gis_integration.providers.qgis_provider import QGISProvider

        provider = QGISProvider()
        assert provider.health_check() is True

    def test_extract_features_with_mocked_qgis(self):
        """extract_features should yield GISFeatures with mocked QGIS."""
        from gis_integration.providers.qgis_provider import QGISProvider

        provider = QGISProvider()
        provider._loaded = True

        # Build mock QGIS feature
        mock_feat = Mock()
        mock_feat.id.return_value = 42
        mock_geom = Mock()
        mock_geom.asJson.return_value = '{"type": "Point", "coordinates": [31.0, 30.0]}'
        mock_feat.geometry.return_value = mock_geom
        mock_feat.attributes.return_value = ["value1"]
        mock_field = Mock()
        mock_field.name.return_value = "attr1"

        mock_layer = Mock()
        mock_layer.name.return_value = "substations"
        mock_layer.getFeatures.return_value = [mock_feat]
        mock_layer.fields.return_value = [mock_field]

        mock_project = Mock()
        mock_project.mapLayers.return_value = {"id1": mock_layer}

        mock_qgs_project = Mock()
        mock_qgs_project.instance.return_value = mock_project

        mock_qgs_app = Mock()

        mock_qgis_core = Mock()
        mock_qgis_core.QgsProject = mock_qgs_project
        mock_qgis_core.QgsApplication = mock_qgs_app

        with patch.dict(
            "sys.modules", {"qgis": Mock(core=mock_qgis_core), "qgis.core": mock_qgis_core}
        ):
            with patch("gis_integration.providers.qgis_provider.safe_parse_geojson") as mock_parse:
                mock_parse.return_value = {"type": "Point", "coordinates": [31.0, 30.0]}
                with patch(
                    "gis_integration.providers.qgis_provider.validate_geometry_dict"
                ) as mock_val:
                    mock_val.return_value = (True, "ok")
                    with patch(
                        "gis_integration.providers.qgis_provider.QgsProject",
                        mock_qgs_project,
                        create=True,
                    ):
                        # Mock import to return our mock module
                        with patch("builtins.__import__", return_value=mock_qgis_core):
                            features = list(provider.extract_features("substations"))

        assert len(features) == 1
        assert features[0].id == "42"


# ===========================================================================
# 4. GIS Models — Geometry Validation, Coordinate Systems
# ===========================================================================


class TestGISModels:
    """Test GISFeature, ADMSAsset, and GeoCRSInfo dataclass behavior."""

    def test_gisfeature_frozen(self):
        """GISFeature should be immutable (frozen dataclass)."""
        feat = _make_feature()
        with pytest.raises(AttributeError):
            feat.id = "changed"  # type: ignore

    def test_adms_asset_frozen(self):
        """ADMSAsset should be immutable (frozen dataclass)."""
        asset = _make_asset()
        with pytest.raises(AttributeError):
            asset.asset_id = "changed"  # type: ignore

    def test_geo_crs_info_defaults(self):
        """GeoCRSInfo should default to EPSG:4326 and normalized=False."""
        info = GeoCRSInfo()
        assert info.crs == "EPSG:4326"
        assert info.normalized is False

    def test_adms_asset_type_values(self):
        """ADMSAssetType enum should have expected values."""
        assert ADMSAssetType.FEEDER.value == "FEEDER"
        assert ADMSAssetType.SUBSTATION.value == "SUBSTATION"
        assert ADMSAssetType.SWITCH.value == "SWITCH"
        assert ADMSAssetType.TRANSFORMER.value == "TRANSFORMER"
        assert ADMSAssetType.LINE.value == "LINE"

    def test_gisfeature_with_complex_geometry(self):
        """GISFeature should accept Polygon geometry."""
        poly_geom = {
            "type": "Polygon",
            "coordinates": [[[31.0, 30.0], [31.1, 30.0], [31.1, 30.1], [31.0, 30.1], [31.0, 30.0]]],
        }
        feat = _make_feature(geometry=poly_geom)
        assert feat.geometry["type"] == "Polygon"


# ===========================================================================
# 5. Transformer — Coordinate Transformation, Data Format Conversion
# ===========================================================================


class TestGISTransformer:
    """Test GIS_TO_ADMS_Transformer deterministic mapping."""

    def test_point_default_to_substation(self):
        """Point geometry without role hint should map to SUBSTATION."""
        transformer = GIS_TO_ADMS_Transformer()
        feature = _make_feature(geometry={"type": "Point", "coordinates": [31.0, 30.0]})
        asset = transformer.transform_feature(feature)
        assert asset.asset_type == ADMSAssetType.SUBSTATION

    def test_point_with_switch_role(self):
        """Point geometry with asset_role=switch should map to SWITCH."""
        transformer = GIS_TO_ADMS_Transformer()
        feature = _make_feature(
            geometry={"type": "Point", "coordinates": [31.0, 30.0]},
            properties={"asset_role": "switch"},
        )
        asset = transformer.transform_feature(feature)
        assert asset.asset_type == ADMSAssetType.SWITCH

    def test_linestring_default_to_line(self):
        """LineString without kind hint should map to LINE."""
        transformer = GIS_TO_ADMS_Transformer()
        feature = _make_feature(
            geometry={"type": "LineString", "coordinates": [[31.0, 30.0], [31.5, 30.5]]},
        )
        asset = transformer.transform_feature(feature)
        assert asset.asset_type == ADMSAssetType.LINE

    def test_linestring_with_feeder_kind(self):
        """LineString with line_kind=feeder should map to FEEDER."""
        transformer = GIS_TO_ADMS_Transformer()
        feature = _make_feature(
            geometry={"type": "LineString", "coordinates": [[31.0, 30.0], [31.5, 30.5]]},
            properties={"line_kind": "feeder"},
        )
        asset = transformer.transform_feature(feature)
        assert asset.asset_type == ADMSAssetType.FEEDER

    def test_polygon_to_substation(self):
        """Polygon geometry should map to SUBSTATION."""
        transformer = GIS_TO_ADMS_Transformer()
        feature = _make_feature(
            geometry={
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            },
        )
        asset = transformer.transform_feature(feature)
        assert asset.asset_type == ADMSAssetType.SUBSTATION

    def test_unsupported_geometry_raises(self):
        """Unsupported geometry type (MultiPoint) should raise GISTransformationError."""
        transformer = GIS_TO_ADMS_Transformer()
        feature = _make_feature(
            geometry={"type": "MultiPoint", "coordinates": [[31.0, 30.0], [31.5, 30.5]]},
        )
        with pytest.raises(GISTransformationError, match="Unsupported"):
            transformer.transform_feature(feature)

    def test_empty_feature_id_raises(self):
        """Feature with empty id should raise GISDataExtractionError."""
        transformer = GIS_TO_ADMS_Transformer()
        feature = _make_feature(fid="")
        with pytest.raises(GISDataExtractionError):
            transformer.transform_feature(feature)

    def test_missing_geometry_type_raises(self):
        """Feature with geometry missing 'type' should raise GISTransformationError."""
        transformer = GIS_TO_ADMS_Transformer()
        feature = _make_feature(geometry={"coordinates": [31.0, 30.0]})
        with pytest.raises(GISTransformationError, match="type"):
            transformer.transform_feature(feature)

    def test_deterministic_asset_id(self):
        """Asset ID should follow deterministic pattern: TYPE__FEATURE_ID."""
        transformer = GIS_TO_ADMS_Transformer()
        feature = _make_feature(fid="SUB-42")
        asset = transformer.transform_feature(feature)
        assert asset.asset_id == "SUBSTATION__SUB-42"

    def test_batch_transform_sorts_deterministically(self):
        """Batch transform should sort by (layer_name, id) for deterministic order."""
        transformer = GIS_TO_ADMS_Transformer()
        features = [
            _make_feature(fid="B", layer_name="layer-z"),
            _make_feature(fid="A", layer_name="layer-a"),
            _make_feature(fid="C", layer_name="layer-a"),
        ]
        assets = transformer.transform(features)
        assert assets[0].metadata["source_feature_id"] == "A"
        assert assets[1].metadata["source_feature_id"] == "C"
        assert assets[2].metadata["source_feature_id"] == "B"

    def test_metadata_includes_traceability(self):
        """Transformed asset metadata should include source_crs, layer, mapping_rule."""
        transformer = GIS_TO_ADMS_Transformer()
        feature = _make_feature(
            fid="TRACE-1",
            layer_name="substations",
            crs="EPSG:3857",
            properties={"name": "Main Sub"},
        )
        asset = transformer.transform_feature(feature)
        assert asset.metadata["source_feature_id"] == "TRACE-1"
        assert asset.metadata["source_layer"] == "substations"
        assert asset.metadata["source_crs"] == "EPSG:3857"
        assert "Point -> SUBSTATION" in asset.metadata["mapping_rule"]


# ===========================================================================
# 6. Topology Validator — Connectivity Checks, Island Detection
# ===========================================================================


class TestTopologyValidator:
    """Test topology validation: connectivity, islands, dangling lines."""

    def test_empty_assets_returns_false(self):
        """validate_adms_topology with no assets should return False."""
        ok, issues = validate_adms_topology([])
        assert ok is False
        assert issues[0].issue_type == "empty_graph"

    def test_connected_network_is_valid(self):
        """A properly connected substation+line network should pass."""
        assets = [
            _make_asset("S1", geometry={"type": "Point", "coordinates": [31.0, 30.0]}),
            _make_asset(
                "L1",
                ADMSAssetType.LINE,
                geometry={"type": "LineString", "coordinates": [[31.0, 30.0], [31.1, 30.1]]},
            ),
            _make_asset("S2", geometry={"type": "Point", "coordinates": [31.1, 30.1]}),
        ]
        ok, issues = validate_adms_topology(assets)
        assert ok is True
        assert len(issues) == 0

    def test_isolated_substation_detected(self):
        """Isolated substations should be flagged."""
        assets = [
            _make_asset("S1", geometry={"type": "Point", "coordinates": [31.0, 30.0]}),
            _make_asset("S2", geometry={"type": "Point", "coordinates": [35.0, 35.0]}),
        ]
        ok, issues = validate_adms_topology(assets)
        assert ok is False
        types = [i.issue_type for i in issues]
        assert "isolated_substations" in types

    def test_dangling_line_detected(self):
        """Lines with no connected substations should be flagged as dangling."""
        assets = [
            _make_asset(
                "L1",
                ADMSAssetType.LINE,
                geometry={"type": "LineString", "coordinates": [[32.0, 31.0], [33.0, 32.0]]},
            ),
        ]
        ok, issues = validate_adms_topology(assets)
        assert ok is False
        types = [i.issue_type for i in issues]
        assert "dangling_lines" in types

    def test_disconnected_components_detected(self):
        """Multiple disconnected components should be detected."""
        assets = [
            _make_asset("S1", geometry={"type": "Point", "coordinates": [31.0, 30.0]}),
            _make_asset(
                "L1",
                ADMSAssetType.LINE,
                geometry={"type": "LineString", "coordinates": [[31.0, 30.0], [31.1, 30.1]]},
            ),
            _make_asset("S3", geometry={"type": "Point", "coordinates": [50.0, 50.0]}),
        ]
        ok, issues = validate_adms_topology(assets)
        assert ok is False
        types = [i.issue_type for i in issues]
        assert "disconnected_components" in types

    def test_feeder_connects_like_line(self):
        """FEEDER assets should connect to substations the same as LINE."""
        assets = [
            _make_asset("S1", geometry={"type": "Point", "coordinates": [31.0, 30.0]}),
            _make_asset(
                "F1",
                ADMSAssetType.FEEDER,
                geometry={"type": "LineString", "coordinates": [[31.0, 30.0], [31.2, 30.2]]},
            ),
        ]
        graph = ADMSGraphModel(assets)
        assert "F1" in graph.edges["S1"]
        assert "S1" in graph.edges["F1"]

    def test_graph_extract_endpoints_linestring(self):
        """_extract_endpoints should return first and last coordinates."""
        geometry = {"type": "LineString", "coordinates": [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]}
        result = ADMSGraphModel._extract_endpoints(geometry)
        assert result is not None
        a, b = result
        assert a == (1.0, 2.0)
        assert b == (5.0, 6.0)

    def test_graph_extract_endpoints_point_returns_none(self):
        """_extract_endpoints should return None for Point geometry."""
        geometry = {"type": "Point", "coordinates": [1.0, 2.0]}
        result = ADMSGraphModel._extract_endpoints(geometry)
        assert result is None

    def test_find_disconnected_components_single(self):
        """Connected graph should have one component."""
        assets = [
            _make_asset("S1", geometry={"type": "Point", "coordinates": [31.0, 30.0]}),
            _make_asset(
                "L1",
                ADMSAssetType.LINE,
                geometry={"type": "LineString", "coordinates": [[31.0, 30.0], [31.1, 30.1]]},
            ),
        ]
        graph = ADMSGraphModel(assets)
        comps = graph.find_disconnected_components()
        assert len(comps) == 1


# ===========================================================================
# 7. CRS Validator — EPSG Code Validation, Transformation Accuracy
# ===========================================================================


class TestCRSValidator:
    """Test CRS consistency validation and normalization checks."""

    def test_empty_assets_returns_false(self):
        """validate_crs_consistency with no assets should return False."""
        ok, issues = validate_crs_consistency([])
        assert ok is False
        assert issues[0].issue_type == "empty_assets"

    def test_single_asset_with_crs_is_valid(self):
        """Single asset with source_crs should be valid."""
        assets = [_make_asset("S1", metadata={"source_crs": "EPSG:4326"})]
        ok, issues = validate_crs_consistency(assets)
        assert ok is True

    def test_missing_crs_flagged(self):
        """Assets without source_crs should be flagged."""
        assets = [_make_asset("S1", metadata={})]
        ok, issues = validate_crs_consistency(assets)
        assert ok is False
        types = [i.issue_type for i in issues]
        assert "missing_crs_metadata" in types

    def test_mixed_crs_contamination(self):
        """Assets with different CRS values should be flagged."""
        assets = [
            _make_asset("S1", metadata={"source_crs": "EPSG:4326"}),
            _make_asset("S2", metadata={"source_crs": "EPSG:3857"}),
        ]
        ok, issues = validate_crs_consistency(assets)
        assert ok is False
        types = [i.issue_type for i in issues]
        assert "mixed_crs_contamination" in types

    def test_same_crs_is_valid(self):
        """Multiple assets with the same CRS should be valid."""
        assets = [
            _make_asset("S1", metadata={"source_crs": "EPSG:4326"}),
            _make_asset("S2", metadata={"source_crs": "EPSG:4326"}),
        ]
        ok, issues = validate_crs_consistency(assets)
        assert ok is True

    def test_normalize_epsg_case_insensitive(self):
        """_normalize_epsg should handle lowercase CRS strings."""
        assert _normalize_epsg("epsg:4326") == "EPSG:4326"
        assert _normalize_epsg("EPSG:3857") == "EPSG:3857"

    def test_normalize_epsg_none_returns_none(self):
        """_normalize_epsg should return None for None input."""
        assert _normalize_epsg(None) is None

    def test_normalize_epsg_non_epsg(self):
        """_normalize_epsg should pass through non-EPSG strings (uppercased)."""
        assert _normalize_epsg("custom") == "CUSTOM"

    def test_asset_source_crs_extraction(self):
        """_asset_source_crs should extract source_crs from metadata."""
        asset = _make_asset("S1", metadata={"source_crs": "EPSG:4326"})
        assert _asset_source_crs(asset) == "EPSG:4326"

    def test_normalization_applied_check(self):
        """validate_normalization_applied should verify source_crs presence."""
        assets = [
            _make_asset("S1", metadata={"source_crs": "EPSG:4326"}),
            _make_asset("S2", metadata={}),
        ]
        ok, issues = validate_normalization_applied(assets)
        assert ok is False
        assert issues[0].issue_type == "normalization_not_applied"

    def test_normalization_all_ok(self):
        """validate_normalization_applied should pass when all have source_crs."""
        assets = [
            _make_asset("S1", metadata={"source_crs": "EPSG:4326"}),
            _make_asset("S2", metadata={"source_crs": "EPSG:3857"}),
        ]
        ok, issues = validate_normalization_applied(assets)
        assert ok is True


# ===========================================================================
# 8. Utility Functions — GeoJSON Parsing, Geometry Validation
# ===========================================================================


class TestGISUtils:
    """Test utility functions for GeoJSON parsing and geometry validation."""

    def test_validate_geometry_valid_point(self):
        """Valid Point geometry should pass validation."""
        ok, reason = validate_geometry_dict({"type": "Point", "coordinates": [31.0, 30.0]})
        assert ok is True
        assert reason == "ok"

    def test_validate_geometry_valid_linestring(self):
        """Valid LineString geometry should pass validation."""
        ok, reason = validate_geometry_dict(
            {"type": "LineString", "coordinates": [[31.0, 30.0], [31.5, 30.5]]}
        )
        assert ok is True

    def test_validate_geometry_missing_type(self):
        """Geometry without 'type' should fail validation."""
        ok, reason = validate_geometry_dict({"coordinates": [31.0, 30.0]})
        assert ok is False
        assert "type" in reason.lower()

    def test_validate_geometry_unsupported_type(self):
        """Unsupported geometry type should fail validation."""
        ok, reason = validate_geometry_dict({"type": "GeometryCollection"})
        assert ok is False
        assert "unsupported" in reason.lower()

    def test_validate_geometry_missing_coordinates(self):
        """Point geometry without coordinates should fail."""
        ok, reason = validate_geometry_dict({"type": "Point"})
        assert ok is False
        assert "coordinates" in reason.lower()

    def test_validate_geometry_not_dict(self):
        """Non-dict input should fail validation."""
        ok, reason = validate_geometry_dict("not a dict")
        assert ok is False

    def test_safe_parse_geojson_from_string(self):
        """safe_parse_geojson should parse valid JSON string."""
        result = safe_parse_geojson('{"type": "Point", "coordinates": [31.0, 30.0]}')
        assert result["type"] == "Point"

    def test_safe_parse_geojson_invalid_string_raises(self):
        """safe_parse_geojson should raise on invalid JSON string."""
        with pytest.raises(GISDataExtractionError, match="Invalid GeoJSON"):
            safe_parse_geojson("not valid json{{{")

    def test_safe_parse_geojson_non_dict_raises(self):
        """safe_parse_geojson should raise on non-dict JSON."""
        with pytest.raises(GISDataExtractionError, match="must be a dict"):
            safe_parse_geojson(42)

    def test_is_json_serializable(self):
        """is_json_serializable should return True for valid JSON types."""
        assert is_json_serializable({"key": "value"}) is True
        assert is_json_serializable([1, 2, 3]) is True
        assert is_json_serializable("hello") is True

    def test_is_not_json_serializable(self):
        """is_json_serializable should return False for non-JSON types."""
        assert is_json_serializable(set()) is False


# ===========================================================================
# 9. Exception Hierarchy
# ===========================================================================


class TestExceptions:
    """Test GIS exception hierarchy and error propagation."""

    def test_exception_hierarchy(self):
        """All custom exceptions should inherit from GISIntegrationError."""
        assert issubclass(GISProviderUnavailableError, GISIntegrationError)
        assert issubclass(GISDataExtractionError, GISIntegrationError)
        assert issubclass(GISTransformationError, GISIntegrationError)

    def test_provider_unavailable_message(self):
        """GISProviderUnavailableError should carry a message."""
        exc = GISProviderUnavailableError("QGIS missing")
        assert "QGIS" in str(exc)

    def test_data_extraction_message(self):
        """GISDataExtractionError should carry a message."""
        exc = GISDataExtractionError("bad data")
        assert "bad data" in str(exc)

    def test_transformation_error_message(self):
        """GISTransformationError should carry a message."""
        exc = GISTransformationError("unsupported type")
        assert "unsupported" in str(exc)


# ===========================================================================
# 10. End-to-End Integration — Provider → Transformer → Validator
# ===========================================================================


class TestEndToEndIntegration:
    """Test the full pipeline: features → transformer → topology/CRS validation."""

    def test_full_pipeline_valid_network(self):
        """Valid network should pass both topology and CRS validation."""
        # Simulate features extracted from a provider
        features = [
            _make_feature(
                fid="SUB-1",
                geometry={"type": "Point", "coordinates": [31.0, 30.0]},
                properties={"asset_role": "substation"},
                crs="EPSG:4326",
            ),
            _make_feature(
                fid="LINE-1",
                geometry={"type": "LineString", "coordinates": [[31.0, 30.0], [31.1, 30.1]]},
                properties={"line_kind": "feeder"},
                crs="EPSG:4326",
            ),
            _make_feature(
                fid="SUB-2",
                geometry={"type": "Point", "coordinates": [31.1, 30.1]},
                properties={"asset_role": "substation"},
                crs="EPSG:4326",
            ),
        ]

        # Transform to ADMS assets
        transformer = GIS_TO_ADMS_Transformer()
        assets = transformer.transform(features)
        assert len(assets) == 3

        # Validate topology
        ok_topo, topo_issues = validate_adms_topology(assets)
        assert ok_topo is True

        # Validate CRS
        ok_crs, crs_issues = validate_crs_consistency(assets)
        assert ok_crs is True

    def test_full_pipeline_detects_crs_mismatch(self):
        """Pipeline should detect CRS mismatch after transformation."""
        features = [
            _make_feature(
                fid="SUB-A",
                geometry={"type": "Point", "coordinates": [31.0, 30.0]},
                crs="EPSG:4326",
            ),
            _make_feature(
                fid="SUB-B",
                geometry={"type": "Point", "coordinates": [31.5, 30.5]},
                crs="EPSG:3857",
            ),
        ]

        transformer = GIS_TO_ADMS_Transformer()
        assets = transformer.transform(features)

        ok_crs, crs_issues = validate_crs_consistency(assets)
        assert ok_crs is False
        types = [i.issue_type for i in crs_issues]
        assert "mixed_crs_contamination" in types

    def test_full_pipeline_detects_isolated_substations(self):
        """Pipeline should detect isolated substations in topology."""
        features = [
            _make_feature(
                fid="SUB-X",
                geometry={"type": "Point", "coordinates": [31.0, 30.0]},
                properties={"asset_role": "substation"},
            ),
            _make_feature(
                fid="SUB-Y",
                geometry={"type": "Point", "coordinates": [50.0, 50.0]},
                properties={"asset_role": "substation"},
            ),
        ]

        transformer = GIS_TO_ADMS_Transformer()
        assets = transformer.transform(features)

        ok_topo, topo_issues = validate_adms_topology(assets)
        assert ok_topo is False
        types = [i.issue_type for i in topo_issues]
        assert "isolated_substations" in types

    def test_postgis_roundtrip_with_transformation(self):
        """PostGIS fallback store → retrieve → transform should preserve data."""
        from gis_integration.providers.postgis_provider import PostGISProvider, SpatialAsset

        provider = PostGISProvider(dsn="", schema="roundtrip_test")
        provider._fallback_dir = tempfile.mkdtemp(prefix="postgis_roundtrip_")
        provider._use_fallback = True
        provider._connected = False

        # Insert spatial assets
        assets_in = [
            SpatialAsset(
                asset_id="RT-SUB1",
                asset_type="substation",
                geometry={"type": "Point", "coordinates": [31.0, 30.0]},
            ),
            SpatialAsset(
                asset_id="RT-LINE1",
                asset_type="line",
                geometry={"type": "LineString", "coordinates": [[31.0, 30.0], [31.5, 30.5]]},
            ),
        ]
        for a in assets_in:
            provider.upsert_asset(a)

        # Retrieve and convert to GISFeature
        all_assets = provider.get_all_assets()
        features = [
            GISFeature(
                id=a.asset_id,
                geometry=a.geometry or {},
                properties={"asset_type": a.asset_type},
                crs="EPSG:4326",
            )
            for a in all_assets
        ]

        # Transform to ADMS
        transformer = GIS_TO_ADMS_Transformer()
        adms_assets = transformer.transform(features)
        assert len(adms_assets) == 2

    def test_postgis_electrical_mapping_integration(self):
        """PostGIS electrical mapping should integrate with asset retrieval."""
        from gis_integration.providers.postgis_provider import PostGISProvider, SpatialAsset

        provider = PostGISProvider(dsn="", schema="elec_test")
        provider._fallback_dir = tempfile.mkdtemp(prefix="postgis_elec_")
        provider._use_fallback = True
        provider._connected = False

        for i in range(3):
            provider.upsert_asset(
                SpatialAsset(
                    asset_id=f"BUS{i}",
                    asset_type="bus",
                    geometry={"type": "Point", "coordinates": [31.0 + i * 0.1, 30.0]},
                    electrical_id=f"elec_{i}",
                )
            )

        mapping = provider.map_electrical_to_gis(["elec_0", "elec_1", "elec_99"])
        assert "elec_0" in mapping
        assert "elec_1" in mapping
        assert "elec_99" not in mapping


# ===========================================================================
# 11. Error Handling Across All Providers
# ===========================================================================


class TestProviderErrorHandling:
    """Test error handling resilience across all GIS providers."""

    def test_arcgis_invalid_geometry_in_cursor(self):
        """ArcGIS provider should raise on invalid geometry from cursor."""
        from gis_integration.providers.arcgis_provider import ArcGISProvider

        provider = ArcGISProvider()
        provider._loaded = True

        mock_geom = Mock()
        mock_geom.JSON = '{"type": "InvalidType", "coordinates": []}'

        mock_cursor = iter([(1, mock_geom)])
        mock_arcpy = Mock()
        mock_arcpy.da.SearchCursor.return_value = mock_cursor

        with patch.dict("sys.modules", {"arcpy": mock_arcpy, "arcpy.da": mock_arcpy.da}):
            with patch(
                "gis_integration.providers.arcgis_provider.safe_parse_geojson"
            ) as mock_parse:
                mock_parse.return_value = {"type": "InvalidType", "coordinates": []}
                with patch(
                    "gis_integration.providers.arcgis_provider.validate_geometry_dict"
                ) as mock_val:
                    mock_val.return_value = (False, "unsupported geometry type: InvalidType")
                    with pytest.raises(GISDataExtractionError, match="Invalid geometry"):
                        list(provider.extract_features("bad_layer"))

    def test_qgis_export_geojson_failure(self):
        """QGIS export_geojson should raise GISDataExtractionError on failure."""
        from gis_integration.providers.qgis_provider import QGISProvider

        provider = QGISProvider()
        # Not loaded → extract_features raises → export_geojson propagates
        with pytest.raises(GISDataExtractionError):
            provider.export_geojson("nonexistent")

    def test_postgis_get_nonexistent_asset(self):
        """PostGIS get_asset should return None for missing assets."""
        from gis_integration.providers.postgis_provider import PostGISProvider

        provider = PostGISProvider(dsn="", schema="test")
        provider._fallback_dir = tempfile.mkdtemp(prefix="postgis_miss_")
        provider._use_fallback = True
        provider._connected = False

        assert provider.get_asset("DOES_NOT_EXIST") is None

    def test_postgis_delete_nonexistent_asset(self):
        """PostGIS delete_asset should return False for missing assets in fallback."""
        from gis_integration.providers.postgis_provider import PostGISProvider

        provider = PostGISProvider(dsn="", schema="test")
        provider._fallback_dir = tempfile.mkdtemp(prefix="postgis_del_")
        provider._use_fallback = True
        provider._connected = False

        assert provider.delete_asset("DOES_NOT_EXIST") is False

    def test_transformer_non_dict_geometry_raises(self):
        """Transformer should raise on non-dict geometry."""
        transformer = GIS_TO_ADMS_Transformer()
        feature = GISFeature(
            id="bad-geom",
            geometry="not a dict",  # type: ignore
        )
        with pytest.raises(GISTransformationError):
            transformer.transform_feature(feature)
