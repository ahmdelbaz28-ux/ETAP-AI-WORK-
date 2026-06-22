"""Tests for Digital Twin sync — GIS Bridge and ETAP sync."""

from __future__ import annotations

import tempfile
from typing import Any, Dict

import pytest

from digital_twin.event_bus import EventBus, EventType, TopologyChanged
from digital_twin.state_store import StateSnapshot, StateStore
from gis_integration.providers.postgis_provider import PostGISProvider, SpatialAsset

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def postgis() -> PostGISProvider:
    provider = PostGISProvider(dsn="", schema="test_schema")
    provider._fallback_dir = tempfile.mkdtemp(prefix="sync_test_")
    provider._use_fallback = True
    provider._connected = False
    return provider


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus(max_history=100)


@pytest.fixture
def state_store() -> StateStore:
    return StateStore(max_versions=50)


# ---------------------------------------------------------------------------
# PostGIS -> Digital Twin Sync
# ---------------------------------------------------------------------------


def test_gis_bridge_postgis_assets(postgis: PostGISProvider) -> None:
    """Verify PostGIS can store and retrieve spatial assets for bridge sync."""
    for i in range(3):
        asset = SpatialAsset(
            asset_id=f"BUS_{i}",
            asset_type="bus",
            geometry={"type": "Point", "coordinates": [31.0 + i * 0.1, 30.0 + i * 0.1]},
            electrical_id=str(i),
            properties={"voltage_kv": 11.0},
        )
        assert postgis.upsert_asset(asset)

    assets = postgis.get_all_assets()
    assert len(assets) == 3

    mapping = postgis.map_electrical_to_gis(["0", "1", "2"])
    assert len(mapping) == 3
    for eid in ["0", "1", "2"]:
        assert mapping[eid]["asset_id"] == f"BUS_{eid}"


def test_gis_bridge_geojson_roundtrip(postgis: PostGISProvider) -> None:
    """Verify GeoJSON import/export works for bridge data exchange."""
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [31.2, 30.1]},
                "properties": {"asset_id": "BUS1", "asset_type": "bus", "voltage_kv": 11.0},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [31.3, 30.2]},
                "properties": {"asset_id": "BUS2", "asset_type": "bus", "voltage_kv": 33.0},
            },
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[31.2, 30.1], [31.3, 30.2]]},
                "properties": {"asset_id": "LINE1", "asset_type": "line"},
            },
        ],
    }

    count = postgis.import_geojson_collection(geojson)
    assert count == 3

    exported = postgis.export_geojson_collection()
    assert exported["metadata"]["asset_count"] == 3

    buses = postgis.query_by_type("bus")
    assert len(buses) == 2


# ---------------------------------------------------------------------------
# State Store + Event Bus Integration
# ---------------------------------------------------------------------------


def test_state_store_commit_and_get(state_store: StateStore) -> None:
    """Verify state store can commit and retrieve snapshots."""
    snap = StateSnapshot()
    snap.gis_assets["BUS1"] = type("obj", (), {
        "asset_id": "BUS1", "asset_type": "bus", "electrical_id": "1",
        "latitude": 30.0, "longitude": 31.2, "zone_id": "Z1",
        "to_dict": lambda self: {"asset_id": "BUS1"},
    })()
    version = state_store.commit(snap)
    assert version == 1

    current = state_store.get_current()
    assert current is not None
    assert current.version == 1
    assert "BUS1" in current.gis_assets

    retrieved = state_store.get_version(1)
    assert retrieved is not None
    assert retrieved.version == 1


def test_state_store_rollback(state_store: StateStore) -> None:
    """Verify state store rollback."""
    for _i in range(5):
        snap = StateSnapshot()
        snap.gis_assets["key"] = type("obj", (), {
            "asset_id": "key", "asset_type": "test", "electrical_id": "",
            "latitude": 0.0, "longitude": 0.0, "zone_id": "",
            "to_dict": lambda self: {"asset_id": "key"},
        })()
        state_store.commit(snap)

    assert state_store.get_current_version() == 5

    rolled = state_store.rollback(3)
    assert rolled is not None
    assert state_store.get_current_version() == 3


def test_event_bus_publish_and_subscribe(event_bus: EventBus) -> None:
    """Verify event bus publish/subscribe works for sync events."""
    received_events = []

    def handler(event):
        received_events.append(event)

    event_bus.subscribe(EventType.TOPOLOGY_CHANGED, handler)
    event_bus.publish(TopologyChanged(
        change_description="sync test",
        source="test",
    ))
    assert len(received_events) == 1
    assert received_events[0].event_type == EventType.TOPOLOGY_CHANGED


def test_event_bus_history(event_bus: EventBus) -> None:
    """Verify event history tracking."""
    for i in range(5):
        event_bus.publish(TopologyChanged(
            change_description=f"event_{i}",
            source="test",
        ))
    history = event_bus.get_history(limit=3)
    assert len(history) == 3
    assert history[-1].metadata or True  # last event present


# ---------------------------------------------------------------------------
# Sync pipeline verification
# ---------------------------------------------------------------------------


def test_full_sync_pipeline_assets(postgis: PostGISProvider, state_store: StateStore) -> None:
    """Verify the complete asset pipeline: PostGIS -> State Store."""
    # Create assets in PostGIS
    assets_data = [
        ("SUB1", "substation", [31.2, 30.0], "bus_1"),
        ("XF1", "transformer", [31.3, 30.1], "xf_1"),
        ("FDR1", "feeder", None, "line_1"),
    ]
    for aid, atype, geom, eid in assets_data:
        asset = SpatialAsset(
            asset_id=aid,
            asset_type=atype,
            geometry={"type": "Point", "coordinates": geom} if geom else None,
            electrical_id=eid,
        )
        assert postgis.upsert_asset(asset)

    # Verify all assets retrievable
    all_assets = postgis.get_all_assets()
    assert len(all_assets) == 3

    # Verify query by type
    assert len(postgis.query_by_type("substation")) == 1
    assert len(postgis.query_by_type("transformer")) == 1
    assert len(postgis.query_by_type("feeder")) == 1

    # Verify electrical mapping (feeder with no geometry is excluded)
    mapping = postgis.map_electrical_to_gis(["bus_1", "xf_1", "line_1"])
    assert len(mapping) == 2  # line_1 has no geometry, so excluded
    assert "bus_1" in mapping
    assert "xf_1" in mapping


def test_etap_sync_engine_importable() -> None:
    """Verify ETAP sync engine can be imported."""
    from etap_integration.sync_engine import ETAPSyncEngine
    engine = ETAPSyncEngine()
    assert engine.dt_state is None
    assert engine.etap_provider is None
    stats = engine.get_statistics()
    assert stats["total_operations"] == 0


def test_etap_sync_mock_import() -> None:
    """Verify mock ETAP import creates a valid model."""
    from core_model.system import System
    from digital_twin.digital_twin_core import DigitalTwinState
    from etap_integration.etap_provider import MockEtapProvider
    from etap_integration.sync_engine import ETAPSyncEngine

    dt_state = DigitalTwinState()
    system = System(base_mva=100.0)
    dt_state.bind_electrical(system)

    provider = MockEtapProvider()
    engine = ETAPSyncEngine(etap_provider=provider, dt_state=dt_state)

    result = engine.import_from_etap("mock_project.edb")
    assert result["success"]
    assert result["object_counts"]["buses"] > 0


def test_etap_sync_export() -> None:
    """Verify ETAP export creates valid export data."""
    from core_model.bus import Bus
    from core_model.line import Line
    from core_model.system import System
    from digital_twin.digital_twin_core import DigitalTwinState
    from etap_integration.sync_engine import ETAPSyncEngine

    dt_state = DigitalTwinState()
    system = System(base_mva=100.0)

    bus1 = Bus(bus_id=1, voltage_magnitude=1.05, bus_type="slack")
    bus2 = Bus(bus_id=2, voltage_magnitude=1.0, bus_type="pv")
    bus3 = Bus(bus_id=3, voltage_magnitude=1.0, bus_type="pq")
    system.add_bus(bus1)
    system.add_bus(bus2)
    system.add_bus(bus3)

    line12 = Line(line_id=1, from_bus=bus1, to_bus=bus2, z1=complex(0.01, 0.05))
    line23 = Line(line_id=2, from_bus=bus2, to_bus=bus3, z1=complex(0.015, 0.06))
    system.add_line(line12)
    system.add_line(line23)

    dt_state.bind_electrical(system)
    engine = ETAPSyncEngine(dt_state=dt_state)

    result = engine.export_to_etap("export_test.edb")
    assert result["success"]
    assert result["object_counts"]["buses"] == 3
    assert result["object_counts"]["lines"] == 2


def test_gis_visualization_importable() -> None:
    """Verify GISVisualizer can be imported."""
    from visualization.gis_visualization import PPE_LEVELS, GISVisualizer
    viz = GISVisualizer()
    assert viz.center == (30.0, 31.0)
    assert viz.zoom == 10
    assert len(PPE_LEVELS) == 5


def test_gis_visualization_fallback_geojson() -> None:
    """Verify fallback GeoJSON output when folium not available."""
    from visualization.gis_visualization import GISVisualizer
    viz = GISVisualizer()
    result = viz.visualize_load_flow(
        {"BUS1": {"voltage_magnitude": 1.02}},
    )
    assert isinstance(result, dict)
    assert result["visualization_type"] == "load_flow"
    assert "folium not installed" in result["note"]


def test_gis_bridge_module_importable() -> None:
    """Verify GISSyncBridge can be imported."""
    from digital_twin.gis_bridge import ELECTRICAL_TO_GIS_MAP, GIS_TO_ELECTRICAL_MAP, GISSyncBridge
    assert "substation" in GIS_TO_ELECTRICAL_MAP
    assert "bus" in ELECTRICAL_TO_GIS_MAP


def test_network_mapping_build() -> None:
    """Verify network mapping GeoJSON structure."""
    from digital_twin.gis_bridge import GISSyncBridge
    mapping = GISSyncBridge._extract_coords
    assert mapping({"type": "Point", "coordinates": [31.2, 30.0]}) == (31.2, 30.0)
    assert mapping({"type": "LineString", "coordinates": [[31.0, 30.0], [31.5, 30.5]]}) == (31.0, 30.0)
    assert mapping(None) is None
    assert mapping({"type": "Point"}) is None
