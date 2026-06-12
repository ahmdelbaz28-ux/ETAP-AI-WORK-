"""GIS Model - Geographic Information System data models.

Provides spatial data structures for GIS zones, assets, coordinates,
and database integration used in electrical network modeling.
"""

from gis_model.gis_model import (
    GISDatabase,
    GISZone,
    GISZoneType,
    GISAsset,
    GISAssetType,
    GeoCoordinate,
    PolylineGeometry,
)

__all__ = [
    "GISDatabase",
    "GISZone",
    "GISZoneType",
    "GISAsset",
    "GISAssetType",
    "GeoCoordinate",
    "PolylineGeometry",
]
