from __future__ import annotations

import json
import logging
from typing import Any

from gis_integration.exceptions import GISDataExtractionError

logger = logging.getLogger(__name__)


def is_json_serializable(value: Any) -> bool:
    try:
        json.dumps(value)
        return True
    except Exception:
        return False


def validate_geometry_dict(geometry: dict[str, Any]) -> tuple[bool, str]:
    """
    Minimal GeoJSON geometry validation:
    - must be a dict
    - must include "type"
    - "type" must be one of supported geometry types
    - must have "coordinates" for supported types (best-effort)
    """
    if not isinstance(geometry, dict):
        return False, "geometry must be a dict"

    gtype = geometry.get("type")
    if not gtype or not isinstance(gtype, str):
        return False, "geometry.type must be a string"

    supported = {"Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon"}
    if gtype not in supported:
        return False, f"unsupported geometry type: {gtype}"

    # Best-effort checks: some providers may include custom CRS fields.
    if gtype in {"Point"} and "coordinates" not in geometry:
        return False, "Point geometry missing coordinates"
    if (
        gtype in {"LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon"}
        and "coordinates" not in geometry
    ):
        return False, f"{gtype} geometry missing coordinates"

    return True, "ok"


def safe_parse_geojson(geojson: Any) -> dict[str, Any]:
    """
    Ensure external GIS data payload is parseable as JSON dict.

    If the input looks like Esri JSON (has 'x'/'y', 'rings', 'paths',
    'points', or 'xmin'/'ymin' keys), it is automatically converted to
    GeoJSON via esri_json_to_geojson() before returning.

    This handles the common case where ArcGIS's SHAPE@JSON returns Esri
    JSON format, which is NOT compatible with GeoJSON validation.
    """
    if isinstance(geojson, str):
        try:
            geojson = json.loads(geojson)
        except Exception as exc:
            raise GISDataExtractionError(f"Invalid GeoJSON string: {exc}") from exc

    if not isinstance(geojson, dict):
        raise GISDataExtractionError("GeoJSON payload must be a dict")

    # Auto-detect Esri JSON and convert to GeoJSON
    if _looks_like_esri_json(geojson):
        geojson = esri_json_to_geojson(geojson)

    return geojson


def _looks_like_esri_json(data: dict[str, Any]) -> bool:
    """Detect if a dict is Esri JSON (not GeoJSON).

    Esri JSON has these distinctive keys:
    - Point: 'x', 'y' (and optionally 'z', 'm')
    - MultiPoint: 'points'
    - Polyline: 'paths'
    - Polygon: 'rings'
    - Envelope: 'xmin', 'ymin', 'xmax', 'ymax'

    GeoJSON has 'type' + 'coordinates' instead.
    """
    if "type" in data and "coordinates" in data:
        # Already GeoJSON
        return False

    esri_keys = {"x", "y", "points", "paths", "rings", "xmin", "ymin", "xmax", "ymax"}
    return bool(esri_keys & set(data.keys()))


def esri_json_to_geojson(esri: dict[str, Any]) -> dict[str, Any]:
    """
    Convert Esri JSON geometry to GeoJSON geometry.

    Esri JSON formats (from ArcGIS Pro arcpy SHAPE@JSON):
    - Point: {"x":.., "y":..}
    - MultiPoint: {"points": [[x,y],...]}
    - Polyline: {"paths": [[[x,y],...]]}
    - Polygon: {"rings": [[[x,y],...]]}
    - Envelope: {"xmin":.., "ymin":.., "xmax":.., "ymax":..}

    GeoJSON equivalents:
    - Point: {"type":"Point", "coordinates":[x,y]}
    - MultiPoint: {"type":"MultiPoint", "coordinates":[[x,y],...]}
    - LineString: {"type":"LineString", "coordinates":[[x,y],...]}
    - MultiLineString: {"type":"MultiLineString", "coordinates":[[[x,y],...]]}
    - Polygon: {"type":"Polygon", "coordinates":[[[x,y],...]]}

    Raises:
        GISDataExtractionError: if the Esri JSON shape is unknown.
    """
    if not isinstance(esri, dict):
        raise GISDataExtractionError(
            f"Esri JSON must be a dict, got {type(esri).__name__}"
        )

    # Point: {"x":.., "y":..}
    if "x" in esri and "y" in esri:
        return {"type": "Point", "coordinates": [esri["x"], esri["y"]]}

    # MultiPoint: {"points": [[x,y],...]}
    if "points" in esri:
        return {"type": "MultiPoint", "coordinates": esri["points"]}

    # Polyline: {"paths": [[[x,y],...]]}
    # A single path → LineString; multiple paths → MultiLineString
    if "paths" in esri:
        paths = esri["paths"]
        if not isinstance(paths, list):
            raise GISDataExtractionError(f"Esri 'paths' must be a list, got {type(paths).__name__}")
        if len(paths) == 1:
            return {"type": "LineString", "coordinates": paths[0]}
        return {"type": "MultiLineString", "coordinates": paths}

    # Polygon: {"rings": [[[x,y],...]]}
    # Esri rings: first ring = outer, subsequent = holes
    # GeoJSON Polygon: coordinates[0] = outer, coordinates[1+] = holes
    if "rings" in esri:
        rings = esri["rings"]
        if not isinstance(rings, list):
            raise GISDataExtractionError(f"Esri 'rings' must be a list, got {type(rings).__name__}")
        return {"type": "Polygon", "coordinates": rings}

    # Envelope (bounding box) → convert to Polygon
    if "xmin" in esri and "ymin" in esri and "xmax" in esri and "ymax" in esri:
        coords = [
            [esri["xmin"], esri["ymin"]],
            [esri["xmax"], esri["ymin"]],
            [esri["xmax"], esri["ymax"]],
            [esri["xmin"], esri["ymax"]],
            [esri["xmin"], esri["ymin"]],  # close the ring
        ]
        return {"type": "Polygon", "coordinates": [coords]}

    raise GISDataExtractionError(
        f"Unknown Esri JSON shape: keys={sorted(esri.keys())}. "
        f"Expected one of: x/y, points, paths, rings, xmin/ymin/xmax/ymax."
    )
