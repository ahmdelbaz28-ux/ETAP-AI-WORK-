"""
GIS Spatial Layer - ETAP GIS Equivalent
========================================
Implements geospatial grid system for power system assets.

Supports:
- Geo-referencing model (lat/lon/elevation/zone)
- Spatial network geometry (polylines, routing)
- GIS database layer (GeoJSON export/import, spatial indexing)
- Map visualization data structures (Mapbox/Leaflet ready)

Reference: IEC 61970 CIM Geographic Location model
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ============================================================
# GEO-REFERENCING MODEL
# ============================================================


class GISZoneType(Enum):
    SUBSTATION = "substation"
    FEEDER = "feeder"
    SWITCHING_AREA = "switching_area"
    PROTECTION_ZONE = "protection_zone"
    LOAD_AREA = "load_area"


@dataclass
class GeoCoordinate:
    """Geographic coordinate with optional elevation."""

    latitude: float
    longitude: float
    elevation: float | None = None

    def to_dict(self) -> dict:
        d = {"lat": self.latitude, "lon": self.longitude}
        if self.elevation is not None:
            d["elev"] = self.elevation
        return d

    @staticmethod
    def from_dict(data: dict) -> GeoCoordinate:
        return GeoCoordinate(
            latitude=data["lat"], longitude=data["lon"], elevation=data.get("elev"),
        )

    def distance_to(self, other: GeoCoordinate) -> float:
        """
        Calculate Haversine distance in meters between two coordinates.
        """
        R = 6371000.0  # Earth radius in meters
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def bearing_to(self, other: GeoCoordinate) -> float:
        """Calculate bearing in degrees from self to other."""
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        dlon = lon2 - lon1
        x = math.sin(dlon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing = math.degrees(math.atan2(x, y))
        return (bearing + 360) % 360


@dataclass
class GISZone:
    """GIS zone definition for spatial grouping of assets."""

    zone_id: str
    zone_type: GISZoneType
    name: str
    boundary: list[GeoCoordinate] = field(default_factory=list)
    parent_zone_id: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)

    def contains_point(self, point: GeoCoordinate) -> bool:
        """Check if a point is inside the zone boundary using ray casting."""
        if not self.boundary or len(self.boundary) < 3:
            return False
        n = len(self.boundary)
        inside = False
        x, y = point.longitude, point.latitude
        j = n - 1
        for i in range(n):
            xi, yi = self.boundary[i].longitude, self.boundary[i].latitude
            xj, yj = self.boundary[j].longitude, self.boundary[j].latitude
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def to_dict(self) -> dict:
        return {
            "zone_id": self.zone_id,
            "zone_type": self.zone_type.value,
            "name": self.name,
            "boundary": [c.to_dict() for c in self.boundary],
            "parent_zone_id": self.parent_zone_id,
            "properties": self.properties,
        }


# ============================================================
# SPATIAL NETWORK GEOMETRY
# ============================================================


@dataclass
class PolylineGeometry:
    """Polyline geometry for lines, feeders, and routes."""

    coordinates: list[GeoCoordinate] = field(default_factory=list)

    def total_length_meters(self) -> float:
        """Calculate total polyline length in meters."""
        total = 0.0
        for i in range(len(self.coordinates) - 1):
            total += self.coordinates[i].distance_to(self.coordinates[i + 1])
        return total

    def interpolate_point(self, fraction: float) -> GeoCoordinate:
        """Get a point along the polyline at a given fraction (0.0 to 1.0)."""
        if not self.coordinates:
            return GeoCoordinate(0, 0)
        if fraction <= 0:
            return self.coordinates[0]
        if fraction >= 1:  # NOSONAR — pythonbugs:S2583: not always true; fraction is in (0, +inf) at this point, this branch catches [1, +inf)
            return self.coordinates[-1]
        total = self.total_length_meters()
        target = fraction * total
        accumulated = 0.0
        for i in range(len(self.coordinates) - 1):
            seg_len = self.coordinates[i].distance_to(self.coordinates[i + 1])
            if accumulated + seg_len >= target:
                seg_frac = (target - accumulated) / seg_len if seg_len > 0 else 0
                lat = self.coordinates[i].latitude + seg_frac * (
                    self.coordinates[i + 1].latitude - self.coordinates[i].latitude
                )
                lon = self.coordinates[i].longitude + seg_frac * (
                    self.coordinates[i + 1].longitude - self.coordinates[i].longitude
                )
                elev = None
                if (
                    self.coordinates[i].elevation is not None
                    and self.coordinates[i + 1].elevation is not None
                ):
                    elev = self.coordinates[i].elevation + seg_frac * (
                        self.coordinates[i + 1].elevation - self.coordinates[i].elevation
                    )
                return GeoCoordinate(lat, lon, elev)
            accumulated += seg_len
        return self.coordinates[-1]

    def to_coordinate_pairs(self) -> list[list[float]]:
        """Convert to [lon, lat] pairs for GeoJSON compatibility."""
        return [[c.longitude, c.latitude] for c in self.coordinates]

    def to_dict(self) -> dict:
        return {"coordinates": [c.to_dict() for c in self.coordinates]}

    @staticmethod
    def from_dict(data: dict) -> PolylineGeometry:
        return PolylineGeometry(
            coordinates=[GeoCoordinate.from_dict(c) for c in data.get("coordinates", [])],
        )


# ============================================================
# GIS ASSET REGISTRY
# ============================================================


class GISAssetType(Enum):
    BUS = "bus"
    SUBSTATION = "substation"
    LINE = "line"
    TRANSFORMER = "transformer"
    LOAD = "load"
    GENERATOR = "generator"
    SWITCH = "switch"
    DER = "der"


@dataclass
class GISAsset:
    """GIS-referenced power system asset."""

    asset_id: str
    asset_type: GISAssetType
    electrical_id: str | None = None  # Link to electrical model ID
    position: GeoCoordinate | None = None  # Point geometry
    geometry: PolylineGeometry | None = None  # Line geometry
    zone_id: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "asset_id": self.asset_id,
            "asset_type": self.asset_type.value,
            "electrical_id": self.electrical_id,
            "zone_id": self.zone_id,
            "properties": self.properties,
        }
        if self.position:
            d["position"] = self.position.to_dict()
        if self.geometry:
            d["geometry"] = self.geometry.to_dict()
        return d

    @staticmethod
    def from_dict(data: dict) -> GISAsset:
        position = GeoCoordinate.from_dict(data["position"]) if "position" in data else None
        geometry = PolylineGeometry.from_dict(data["geometry"]) if "geometry" in data else None
        return GISAsset(
            asset_id=data["asset_id"],
            asset_type=GISAssetType(data["asset_type"]),
            electrical_id=data.get("electrical_id"),
            position=position,
            geometry=geometry,
            zone_id=data.get("zone_id"),
            properties=data.get("properties", {}),
        )


# ============================================================
# GIS DATABASE LAYER
# ============================================================


class GISDatabase:
    """
    GIS Database with spatial indexing, GeoJSON support,
    and distance calculations.

    Uses a simple grid-based spatial index for fast lookups.
    """

    def __init__(self, grid_cell_size_deg: float = 0.01):
        """
        Initialize GIS database.

        Parameters:
        grid_cell_size_deg (float): Grid cell size in degrees for spatial indexing.
                                     Default 0.01 deg ≈ 1.1 km at equator.
        """
        self.assets: dict[str, GISAsset] = {}
        self.zones: dict[str, GISZone] = {}
        self.grid_cell_size = grid_cell_size_deg
        self.spatial_index: dict[tuple[int, int], list[str]] = {}
        self.feeder_routes: dict[str, PolylineGeometry] = {}

    # --- Asset Management ---

    def add_asset(self, asset: GISAsset) -> None:
        """Add a GIS asset to the database."""
        self.assets[asset.asset_id] = asset
        self._index_asset(asset)

    def get_asset(self, asset_id: str) -> GISAsset | None:
        """Get a GIS asset by ID."""
        return self.assets.get(asset_id)

    def remove_asset(self, asset_id: str) -> None:
        """Remove a GIS asset from the database."""
        if asset_id in self.assets:
            self._deindex_asset(self.assets[asset_id])
            del self.assets[asset_id]

    def find_assets_by_type(self, asset_type: GISAssetType) -> list[GISAsset]:
        """Find all assets of a given type."""
        return [a for a in self.assets.values() if a.asset_type == asset_type]

    def find_assets_by_zone(self, zone_id: str) -> list[GISAsset]:
        """Find all assets in a given zone."""
        return [a for a in self.assets.values() if a.zone_id == zone_id]

    def find_asset_by_electrical_id(self, electrical_id: str) -> GISAsset | None:
        """Find GIS asset linked to an electrical model element."""
        for a in self.assets.values():
            if a.electrical_id == electrical_id:
                return a
        return None

    # --- Zone Management ---

    def add_zone(self, zone: GISZone) -> None:
        """Add a GIS zone."""
        self.zones[zone.zone_id] = zone

    def get_zone(self, zone_id: str) -> GISZone | None:
        """Get a GIS zone by ID."""
        return self.zones.get(zone_id)

    # --- Feeder Routing ---

    def add_feeder_route(self, feeder_id: str, route: PolylineGeometry) -> None:
        """Add a feeder routing path."""
        self.feeder_routes[feeder_id] = route

    def get_feeder_route(self, feeder_id: str) -> PolylineGeometry | None:
        """Get a feeder routing path."""
        return self.feeder_routes.get(feeder_id)

    # --- Spatial Indexing ---

    def _grid_key(self, coord: GeoCoordinate) -> tuple[int, int]:
        """Compute grid cell key for a coordinate."""
        lat_idx = int(coord.latitude / self.grid_cell_size)
        lon_idx = int(coord.longitude / self.grid_cell_size)
        return (lat_idx, lon_idx)

    def _index_asset(self, asset: GISAsset) -> None:
        """Add asset to spatial index."""
        coords = []
        if asset.position:
            coords.append(asset.position)
        if asset.geometry:
            coords.extend(asset.geometry.coordinates)
        for coord in coords:
            key = self._grid_key(coord)
            if key not in self.spatial_index:
                self.spatial_index[key] = []
            self.spatial_index[key].append(asset.asset_id)

    def _deindex_asset(self, asset: GISAsset) -> None:
        """Remove asset from spatial index."""
        coords = []
        if asset.position:
            coords.append(asset.position)
        if asset.geometry:
            coords.extend(asset.geometry.coordinates)
        for coord in coords:
            key = self._grid_key(coord)
            if key in self.spatial_index:
                if asset.asset_id in self.spatial_index[key]:
                    self.spatial_index[key].remove(asset.asset_id)
                if not self.spatial_index[key]:
                    del self.spatial_index[key]

    def find_nearby_assets(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        self, coord: GeoCoordinate, radius_meters: float,
    ) -> list[tuple[GISAsset, float]]:
        """
        Find all assets within a given radius of a coordinate.

        Returns:
        List of (asset, distance_meters) tuples sorted by distance.
        """
        results = []
        # Search nearby grid cells
        lat_range = int(radius_meters / 111000 / self.grid_cell_size) + 1
        lon_range = int(radius_meters / 111000 / self.grid_cell_size) + 1
        center_key = self._grid_key(coord)

        searched_ids = set()
        for di in range(-lat_range, lat_range + 1):
            for dj in range(-lon_range, lon_range + 1):
                key = (center_key[0] + di, center_key[1] + dj)
                for asset_id in self.spatial_index.get(key, []):
                    if asset_id in searched_ids:
                        continue
                    searched_ids.add(asset_id)
                    asset = self.assets.get(asset_id)
                    if asset and asset.position:
                        dist = coord.distance_to(asset.position)
                        if dist <= radius_meters:
                            results.append((asset, dist))

        results.sort(key=lambda x: x[1])
        return results

    def distance_between_assets(self, asset_id_1: str, asset_id_2: str) -> float | None:
        """Calculate distance between two assets in meters."""
        a1 = self.assets.get(asset_id_1)
        a2 = self.assets.get(asset_id_2)
        if a1 and a2 and a1.position and a2.position:
            return a1.position.distance_to(a2.position)
        return None

    # --- GeoJSON Export/Import ---

    def to_geojson(self, asset_types: list[GISAssetType] = None) -> dict:
        """
        Export all assets as GeoJSON FeatureCollection.

        Parameters:
        asset_types: Optional filter for asset types to export.

        Returns:
        dict: GeoJSON FeatureCollection.
        """
        features = []
        for asset in self.assets.values():
            if asset_types and asset.asset_type not in asset_types:
                continue
            feature = self._asset_to_geojson_feature(asset)
            if feature:
                features.append(feature)
        return {"type": "FeatureCollection", "features": features}

    def _asset_to_geojson_feature(self, asset: GISAsset) -> dict | None:
        """Convert a GIS asset to a GeoJSON feature."""
        properties = {
            "asset_id": asset.asset_id,
            "asset_type": asset.asset_type.value,
            "electrical_id": asset.electrical_id,
            "zone_id": asset.zone_id,
            **asset.properties,
        }

        if asset.position:
            geometry = {
                "type": "Point",
                "coordinates": [asset.position.longitude, asset.position.latitude],
            }
            if asset.position.elevation is not None:
                geometry["coordinates"].append(asset.position.elevation)
        elif asset.geometry:
            geometry = {"type": "LineString", "coordinates": asset.geometry.to_coordinate_pairs()}
        else:
            return None

        return {"type": "Feature", "geometry": geometry, "properties": properties}

    def from_geojson(self, geojson: dict) -> None:
        """
        Import assets from a GeoJSON FeatureCollection.
        """
        if geojson.get("type") != "FeatureCollection":
            raise ValueError("Expected GeoJSON FeatureCollection")
        for feature in geojson.get("features", []):
            asset = self._geojson_feature_to_asset(feature)
            if asset:
                self.add_asset(asset)

    def _geojson_feature_to_asset(self, feature: dict) -> GISAsset | None:
        """Convert a GeoJSON feature to a GIS asset."""
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        geom_type = geom.get("type", "")
        coords = geom.get("coordinates", [])

        asset_type = GISAssetType(props.get("asset_type", "bus"))
        asset_id = props.get("asset_id", "unknown")
        electrical_id = props.get("electrical_id")
        zone_id = props.get("zone_id")

        extra_props = {
            k: v
            for k, v in props.items()
            if k not in ("asset_id", "asset_type", "electrical_id", "zone_id")
        }

        position = None
        geometry = None

        if geom_type == "Point" and len(coords) >= 2:
            elevation = coords[2] if len(coords) > 2 else None
            position = GeoCoordinate(latitude=coords[1], longitude=coords[0], elevation=elevation)
        elif geom_type == "LineString" and len(coords) >= 2:
            gis_coords = [
                GeoCoordinate(latitude=c[1], longitude=c[0], elevation=c[2] if len(c) > 2 else None)
                for c in coords
            ]
            geometry = PolylineGeometry(coordinates=gis_coords)

        return GISAsset(
            asset_id=asset_id,
            asset_type=asset_type,
            electrical_id=electrical_id,
            position=position,
            geometry=geometry,
            zone_id=zone_id,
            properties=extra_props,
        )

    def export_geojson_string(self, asset_types: list[GISAssetType] = None) -> str:
        """Export as GeoJSON string."""
        return json.dumps(self.to_geojson(asset_types), indent=2)

    def import_geojson_string(self, geojson_str: str) -> None:
        """Import from GeoJSON string."""
        self.from_geojson(json.loads(geojson_str))

    # --- Map Visualization Data ---

    def get_map_layers(self) -> dict[str, dict]:
        """
        Generate layer-based data for Mapbox/Leaflet integration.

        Returns:
        Dict with layer names as keys and GeoJSON as values.
        """
        layers = {}
        for asset_type in GISAssetType:
            assets = self.find_assets_by_type(asset_type)
            if assets:
                layers[asset_type.value] = self.to_geojson([asset_type])
        return layers

    def get_substation_layer(self) -> dict:
        """Get GeoJSON layer for substations only."""
        return self.to_geojson([GISAssetType.SUBSTATION, GISAssetType.BUS])

    def get_line_layer(self) -> dict:
        """Get GeoJSON layer for lines only."""
        return self.to_geojson([GISAssetType.LINE])

    def get_transformer_layer(self) -> dict:
        """Get GeoJSON layer for transformers only."""
        return self.to_geojson([GISAssetType.TRANSFORMER])

    # --- Validation ---

    def validate_gis_electrical_alignment(self, electrical_ids: set) -> list[str]:
        """
        Validate that all GIS assets with electrical_id links exist in the electrical model.

        Returns:
        List of validation error messages.
        """
        errors = []
        for asset in self.assets.values():
            if asset.electrical_id and asset.electrical_id not in electrical_ids:
                errors.append(
                    f"GIS asset '{asset.asset_id}' references non-existent electrical_id '{asset.electrical_id}'",
                )
        return errors

    def validate_spatial_consistency(self) -> list[str]:
        """Validate spatial consistency of all assets."""
        errors = []
        for asset in self.assets.values():
            if asset.asset_type in (
                GISAssetType.BUS,
                GISAssetType.SUBSTATION,
                GISAssetType.LOAD,
                GISAssetType.GENERATOR,
                GISAssetType.SWITCH,
                GISAssetType.DER,
            ) and not asset.position:
                errors.append(
                    f"Point asset '{asset.asset_id}' ({asset.asset_type.value}) missing position",
                )
            if asset.asset_type in (GISAssetType.LINE,) and not asset.geometry:
                errors.append(f"Line asset '{asset.asset_id}' missing polyline geometry")
        return errors

    # --- Statistics ---

    def get_statistics(self) -> dict:
        """Get GIS database statistics."""
        type_counts = {}
        for at in GISAssetType:
            type_counts[at.value] = len(self.find_assets_by_type(at))
        return {
            "total_assets": len(self.assets),
            "total_zones": len(self.zones),
            "total_feeder_routes": len(self.feeder_routes),
            "spatial_index_cells": len(self.spatial_index),
            "assets_by_type": type_counts,
        }

    def __repr__(self):
        return f"GISDatabase({len(self.assets)} assets, {len(self.zones)} zones, {len(self.feeder_routes)} routes)"
