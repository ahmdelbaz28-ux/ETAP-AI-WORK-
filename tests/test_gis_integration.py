"""Tests for GIS integration — PostGIS, QGIS bridge, and transformer."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict

import pytest

from gis_integration.exceptions import GISTransformationError
from gis_integration.models import ADMSAsset, ADMSAssetType, GISFeature
from gis_integration.providers.postgis_provider import PostGISProvider, SpatialAsset
from gis_integration.transformer import GIS_TO_ADMS_Transformer

# ---------------------------------------------------------------------------
# PostGIS Provider Tests (file fallback mode)
# ---------------------------------------------------------------------------


@pytest.fixture
def postgis() -> PostGISProvider:
    """Create a PostGIS provider in fallback mode with temp directory."""
    provider = PostGISProvider(dsn="", schema="test_schema")
    provider._fallback_dir = tempfile.mkdtemp(prefix="postgis_test_")
    provider._use_fallback = True
    provider._connected = False
    return provider


def test_postgis_uses_fallback(postgis: PostGISProvider) -> None:
    assert postgis.using_fallback
    assert not postgis.is_connected()


def test_postgis_upsert_and_get(postgis: PostGISProvider) -> None:
    asset = SpatialAsset(
        asset_id="BUS001",
        asset_type="bus",
        geometry={"type": "Point", "coordinates": [31.2, 30.0]},
        properties={"voltage_level": "11kV"},
        electrical_id="bus_1",
    )
    assert postgis.upsert_asset(asset)

    retrieved = postgis.get_asset("BUS001")
    assert retrieved is not None
    assert retrieved.asset_id == "BUS001"
    assert retrieved.asset_type == "bus"
    assert retrieved.electrical_id == "bus_1"
    assert retrieved.geometry == {"type": "Point", "coordinates": [31.2, 30.0]}
    assert retrieved.properties.get("voltage_level") == "11kV"


def test_postgis_upsert_overwrites(postgis: PostGISProvider) -> None:
    asset1 = SpatialAsset(
        asset_id="BUS001",
        asset_type="bus",
        properties={"version": "v1"},
    )
    asset2 = SpatialAsset(
        asset_id="BUS001",
        asset_type="bus",
        properties={"version": "v2"},
    )
    assert postgis.upsert_asset(asset1)
    assert postgis.upsert_asset(asset2)

    retrieved = postgis.get_asset("BUS001")
    assert retrieved.properties["version"] == "v2"


def test_postgis_get_missing(postgis: PostGISProvider) -> None:
    assert postgis.get_asset("NONEXISTENT") is None


def test_postgis_get_all(postgis: PostGISProvider) -> None:
    for i in range(5):
        asset = SpatialAsset(
            asset_id=f"ASSET{i}",
            asset_type="bus" if i % 2 == 0 else "line",
            properties={"index": i},
        )
        postgis.upsert_asset(asset)

    all_assets = postgis.get_all_assets()
    assert len(all_assets) == 5


def test_postgis_query_by_type(postgis: PostGISProvider) -> None:
    for i in range(5):
        asset = SpatialAsset(
            asset_id=f"ASSET{i}",
            asset_type="bus" if i % 2 == 0 else "line",
        )
        postgis.upsert_asset(asset)

    buses = postgis.query_by_type("bus")
    assert len(buses) == 3  # ASSET0, ASSET2, ASSET4
    lines = postgis.query_by_type("line")
    assert len(lines) == 2  # ASSET1, ASSET3


def test_postgis_delete(postgis: PostGISProvider) -> None:
    asset = SpatialAsset(asset_id="DELETE_ME", asset_type="bus")
    postgis.upsert_asset(asset)
    assert postgis.get_asset("DELETE_ME") is not None
    assert postgis.delete_asset("DELETE_ME")
    assert postgis.get_asset("DELETE_ME") is None


def test_postgis_geojson_import_export(postgis: PostGISProvider) -> None:
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [31.0, 30.0]},
                "properties": {"asset_id": "GEO1", "asset_type": "bus"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[31.0, 30.0], [31.5, 30.5]]},
                "properties": {"asset_id": "GEO2", "asset_type": "line"},
            },
        ],
    }

    count = postgis.import_geojson_collection(geojson)
    assert count == 2

    exported = postgis.export_geojson_collection()
    assert exported["type"] == "FeatureCollection"
    assert len(exported["features"]) == 2
    assert exported["metadata"]["asset_count"] == 2


def test_postgis_electrical_mapping(postgis: PostGISProvider) -> None:
    for i in range(3):
        asset = SpatialAsset(
            asset_id=f"BUS{i}",
            asset_type="bus",
            geometry={"type": "Point", "coordinates": [31.0 + i * 0.1, 30.0 + i * 0.1]},
            electrical_id=f"elec_{i}",
        )
        postgis.upsert_asset(asset)

    mapping = postgis.map_electrical_to_gis(["elec_0", "elec_1", "elec_99"])
    assert "elec_0" in mapping
    assert "elec_1" in mapping
    assert "elec_99" not in mapping
    assert mapping["elec_0"]["geometry"]["coordinates"] == [31.0, 30.0]


def test_postgis_health_check(postgis: PostGISProvider) -> None:
    health = postgis.health_check()
    assert health["status"] == "fallback"
    assert health["mode"] == "file"


# ---------------------------------------------------------------------------
# Spatial Asset Tests
# ---------------------------------------------------------------------------


def test_spatial_asset_to_geojson() -> None:
    asset = SpatialAsset(
        asset_id="SUB1",
        asset_type="substation",
        geometry={"type": "Point", "coordinates": [31.2, 30.1]},
        properties={"name": "Main Substation"},
        electrical_id="bus_1",
    )
    feature = asset.to_geojson_feature()
    assert feature["type"] == "Feature"
    assert feature["geometry"]["coordinates"] == [31.2, 30.1]
    assert feature["properties"]["asset_id"] == "SUB1"
    assert feature["properties"]["electrical_id"] == "bus_1"
    assert feature["properties"]["name"] == "Main Substation"


def test_spatial_asset_defaults() -> None:
    asset = SpatialAsset(asset_id="TEST", asset_type="test")
    assert asset.crs == 4326
    assert asset.properties == {}
    assert asset.electrical_id is None
    assert asset.updated_at > 0


# ---------------------------------------------------------------------------
# Transformer Tests
# ---------------------------------------------------------------------------


def test_transformer_point_to_substation() -> None:
    transformer = GIS_TO_ADMS_Transformer()
    feature = GISFeature(
        id="SUB1",
        geometry={"type": "Point", "coordinates": [31.2, 30.1]},
        properties={"asset_role": "substation"},
    )
    asset = transformer.transform_feature(feature)
    assert asset.asset_type == ADMSAssetType.SUBSTATION
    assert asset.asset_id == "SUBSTATION__SUB1"
    assert asset.geometry["coordinates"] == [31.2, 30.1]


def test_transformer_line_to_feeder() -> None:
    transformer = GIS_TO_ADMS_Transformer()
    feature = GISFeature(
        id="FDR1",
        geometry={"type": "LineString", "coordinates": [[31.0, 30.0], [31.5, 30.5]]},
        properties={"line_kind": "feeder"},
    )
    asset = transformer.transform_feature(feature)
    assert asset.asset_type == ADMSAssetType.FEEDER
    assert "FDR1" in asset.asset_id


def test_transformer_unsupported_geometry() -> None:
    transformer = GIS_TO_ADMS_Transformer()
    feature = GISFeature(
        id="UNK1",
        geometry={"type": "MultiPoint", "coordinates": [[31.0, 30.0], [31.5, 30.5]]},
    )
    with pytest.raises(GISTransformationError):
        transformer.transform_feature(feature)


def test_transformer_batch() -> None:
    transformer = GIS_TO_ADMS_Transformer()
    features = [
        GISFeature(id="P1", geometry={"type": "Point", "coordinates": [31.0, 30.0]},
                   properties={}),
        GISFeature(id="P2", geometry={"type": "Point", "coordinates": [31.5, 30.5]},
                   properties={"asset_role": "switch"}),
    ]
    assets = transformer.transform(features)
    assert len(assets) == 2
    assert assets[0].asset_type == ADMSAssetType.SUBSTATION
    assert assets[1].asset_type == ADMSAssetType.SWITCH


# ---------------------------------------------------------------------------
# Health endpoint verification
# ---------------------------------------------------------------------------


def test_postgis_provider_importable() -> None:
    """Verify module can be imported without psycopg2."""
    from gis_integration.providers.postgis_provider import PostGISProvider
    provider = PostGISProvider()
    assert provider.using_fallback
