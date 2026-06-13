from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict

# -----------------------------
# Geometry & Feature Model
# -----------------------------

GeoJSONGeometry = Dict[str, Any]


@dataclass(frozen=True)
class GISFeature:
    """
    Normalized GIS feature for deterministic transformation.

    Rules:
    - geometry must be a GeoJSON geometry dict only (no Feature wrapper)
    - properties must be JSON-serializable
    - crs must be a string (e.g., "EPSG:4326") provided by the provider/normalizer
    """
    id: str
    geometry: GeoJSONGeometry
    properties: Dict[str, Any] = field(default_factory=dict)
    layer_name: str = ""
    crs: str = "EPSG:4326"


class ADMSAssetType(str, Enum):
    FEEDER = "FEEDER"
    SUBSTATION = "SUBSTATION"
    SWITCH = "SWITCH"
    TRANSFORMER = "TRANSFORMER"
    LINE = "LINE"


@dataclass(frozen=True)
class ADMSAsset:
    """
    ADMS-compatible asset representation.

    Rules:
    - JSON serializable (geometry is GeoJSON geometry dict)
    - no dynamic fields
    - deterministic mapping requirements handled by transformer
    """
    asset_id: str
    asset_type: ADMSAssetType
    geometry: GeoJSONGeometry
    metadata: Dict[str, Any] = field(default_factory=dict)


# -----------------------------
# Helper DTOs
# -----------------------------

@dataclass(frozen=True)
class GeoCRSInfo:
    crs: str = "EPSG:4326"
    # Marker indicating provider normalization was needed.
    normalized: bool = False
