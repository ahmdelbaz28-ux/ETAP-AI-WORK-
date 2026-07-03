from __future__ import annotations

import json
from typing import Any

from gis_integration.exceptions import GISDataExtractionError


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
    """
    if isinstance(geojson, str):
        try:
            geojson = json.loads(geojson)
        except Exception as exc:
            raise GISDataExtractionError(f"Invalid GeoJSON string: {exc}") from exc

    if not isinstance(geojson, dict):
        raise GISDataExtractionError("GeoJSON payload must be a dict")

    return geojson
