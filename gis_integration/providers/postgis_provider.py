"""
PostGIS Provider — Geospatial Database Synchronization
=======================================================
Provides bidirectional PostGIS synchronization for QGIS, electrical assets,
and spatial queries used by the Digital Twin and visualization layers.

Architecture:
  AhmedETAP ↔ PostGIS ↔ QGIS

Features:
- Connection pool with configurable DSN
- GeoJSON import/export
- Spatial query (within radius, bounding box)
- Asset CRUD with automatic geometry/attribute sync
- Electrical network mapping via spatial joins
- CRS reprojection (EPSG:4326 ↔ EPSG:3857)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_DSN = os.environ.get("POSTGIS_DSN", "postgresql://etap:etap@localhost:5432/etap_gis")
DEFAULT_SCHEMA = os.environ.get("POSTGIS_SCHEMA", "etap_gis")
_SPATIAL_REF_SYS = 4326  # WGS84

# ---------------------------------------------------------------------------
# Security: schema name validation
# ---------------------------------------------------------------------------
# PostgreSQL identifiers (schema, table, column names) cannot be parameterized
# like values (%s). They must be passed via psycopg2.sql.Identifier, which
# properly quotes them to prevent SQL injection. We additionally enforce a
# strict whitelist regex to reject anything that doesn't look like a valid
# PostgreSQL identifier — defense in depth.
_SCHEMA_NAME_RE = re.compile(r"^[A-Za-z_]\w{0,62}$")


def _validate_schema_name(schema: str) -> str:
    """Validate that *schema* is a safe PostgreSQL identifier.

    Rejects anything containing special characters, whitespace, dots, or
    semicolons — even if psycopg2.sql would quote it correctly, we want to
    fail loudly instead of silently accepting a malicious value.

    Raises:
        ValueError: if the schema name is invalid.
    """
    if not schema or not _SCHEMA_NAME_RE.match(schema):
        raise ValueError(
            f"Invalid PostgreSQL schema name: {schema!r}. "
            r"Must match /^[A-Za-z_]\w{0,62}$/",
        )
    return schema

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class SpatialAsset:
    """A spatially-enabled asset in PostGIS."""

    asset_id: str
    asset_type: str  # bus, line, transformer, substation, switch, load, generator
    geometry: dict[str, Any] | None = None  # GeoJSON geometry dict
    properties: dict[str, Any] = field(default_factory=dict)
    electrical_id: Optional[str] = None
    crs: int = _SPATIAL_REF_SYS
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_geojson_feature(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": self.geometry,
            "properties": {
                "asset_id": self.asset_id,
                "asset_type": self.asset_type,
                "electrical_id": self.electrical_id or "",
                **self.properties,
            },
        }


# ---------------------------------------------------------------------------
# Lazy psycopg2 / postgres imports
# ---------------------------------------------------------------------------

_HAS_POSTGIS = False
_psycopg2 = None
try:
    import psycopg2  # type: ignore
    import psycopg2.extras  # type: ignore
    import psycopg2.pool  # type: ignore

    _psycopg2 = psycopg2
    _HAS_POSTGIS = True
except ImportError:
    logger.warning(
        "psycopg2 not installed. PostGIS provider will use file-based fallback. "
        "Install: pip install psycopg2-binary",
    )


# ---------------------------------------------------------------------------
# PostGIS Provider
# ---------------------------------------------------------------------------


class PostGISProvider:
    """Geospatial database provider for PostGIS-powered synchronization.

    Can operate in two modes:
    1. **Live mode** — requires psycopg2 + accessible PostGIS instance.
    2. **File fallback mode** — uses local GeoJSON files for development/testing.
    """

    def __init__(
        self,
        dsn: str = "",
        schema: str = DEFAULT_SCHEMA,
        pool_min: int = 1,
        pool_max: int = 10,
    ):
        # SECURITY: validate schema name against whitelist before any SQL use.
        # This prevents SQL injection via crafted schema names.
        self.schema = _validate_schema_name(schema)
        self.dsn = dsn or DEFAULT_DSN
        self._pool: Any = None
        self._connected = False
        self._fallback_dir: str = ""
        self._use_fallback = False
        self._init_connection(pool_min, pool_max)

    def _init_connection(self, pool_min: int, pool_max: int) -> None:
        """Initialize the connection pool or fall back to file mode."""
        if not _HAS_POSTGIS:
            self._use_fallback = True
            self._fallback_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "postgis_fallback",
            )
            os.makedirs(self._fallback_dir, exist_ok=True)
            logger.info("PostGIS: using file fallback mode at %s", self._fallback_dir)
            return

        try:
            self._pool = _psycopg2.pool.ThreadedConnectionPool(pool_min, pool_max, self.dsn)
            self._connected = True
            self._ensure_schema()
            logger.info(
                "PostGIS: connected to %s",
                self.dsn.replace(self.dsn.split("@")[0] if "@" in self.dsn else "", "***"),
            )
        except Exception as exc:
            self._use_fallback = True
            self._fallback_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "postgis_fallback",
            )
            os.makedirs(self._fallback_dir, exist_ok=True)
            logger.warning("PostGIS connection failed (%s) — using file fallback", exc)

    def _ensure_schema(self) -> None:
        """Create schema and extension tables if they don't exist."""
        # SECURITY: build all SQL via psycopg2.sql.SQL/Identifier composition.
        # The schema name is also pre-validated by _validate_schema_name()
        # in __init__, so even a malicious caller cannot inject SQL here.
        with self._conn() as conn:
            with conn.cursor() as cur:
                sql = _psycopg2.sql
                cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
                # CREATE SCHEMA — Identifier properly quotes the schema name
                cur.execute(
                    sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                        sql.Identifier(self.schema),
                    ),
                )
                # CREATE TABLE — compose schema.table safely
                cur.execute(
                    sql.SQL(
                        "CREATE TABLE IF NOT EXISTS {}.spatial_assets ("
                        "    asset_id TEXT PRIMARY KEY,"
                        "    asset_type TEXT NOT NULL,"
                        "    geometry GEOMETRY(%s),"
                        "    properties JSONB DEFAULT '{}'::jsonb,"
                        "    electrical_id TEXT,"
                        "    created_at TIMESTAMPTZ DEFAULT NOW(),"
                        "    updated_at TIMESTAMPTZ DEFAULT NOW()"
                        ")",
                    ).format(sql.Identifier(self.schema)),
                    (_SPATIAL_REF_SYS,),
                )
                # CREATE INDEX statements — three of them
                cur.execute(
                    sql.SQL(
                        "CREATE INDEX IF NOT EXISTS idx_spatial_assets_type "
                        "ON {}.spatial_assets (asset_type)",
                    ).format(sql.Identifier(self.schema)),
                )
                cur.execute(
                    sql.SQL(
                        "CREATE INDEX IF NOT EXISTS idx_spatial_assets_geom "
                        "ON {}.spatial_assets USING GIST (geometry)",
                    ).format(sql.Identifier(self.schema)),
                )
                cur.execute(
                    sql.SQL(
                        "CREATE INDEX IF NOT EXISTS idx_spatial_assets_electrical "
                        "ON {}.spatial_assets (electrical_id)",
                    ).format(sql.Identifier(self.schema)),
                )
            conn.commit()

    @contextmanager
    def _conn(self) -> Generator[Any, None, None]:
        """Get a connection from the pool (live mode only)."""
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    # ------------------------------------------------------------------
    # Security helpers
    # ------------------------------------------------------------------

    def _table_ref(self) -> Any:
        """Build a safe `schema.table` SQL identifier.

        Uses psycopg2.sql.Identifier to properly quote both the schema and
        the table name, preventing SQL injection. The schema was already
        validated against a strict whitelist in __init__, so this is
        defense-in-depth (not the only protection layer).
        """
        # _psycopg2 is guaranteed to be available here because _conn() is
        # only called in live mode (after _init_connection succeeded).
        return _psycopg2.sql.SQL("{}.spatial_assets").format(
            _psycopg2.sql.Identifier(self.schema),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_connected(self) -> bool:
        return self._connected and not self._use_fallback

    @property
    def using_fallback(self) -> bool:
        return self._use_fallback

    def health_check(self) -> dict[str, Any]:
        """Check PostGIS connectivity and return status info."""
        if self._use_fallback:
            return {"status": "fallback", "mode": "file", "path": self._fallback_dir}
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT postgis_version()")
                    version = cur.fetchone()[0]
                return {"status": "connected", "mode": "postgis", "version": version}
        except Exception as exc:
            return {"status": "error", "mode": "postgis", "error": str(exc)}

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------

    def upsert_asset(self, asset: SpatialAsset) -> bool:
        """Insert or update a spatial asset."""
        geom_json = json.dumps(asset.geometry) if asset.geometry else None
        props_json = json.dumps(asset.properties)
        now = time.time()

        if self._use_fallback:
            return self._fallback_upsert(asset)

        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    if geom_json:
                        cur.execute(
                            _psycopg2.sql.SQL(
                                "INSERT INTO {} "
                                "(asset_id, asset_type, geometry, properties, electrical_id, updated_at) "
                                "VALUES (%s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), %s), %s::jsonb, %s, to_timestamp(%s)) "
                                "ON CONFLICT (asset_id) DO UPDATE SET "
                                "    asset_type = EXCLUDED.asset_type, "
                                "    geometry = ST_SetSRID(ST_GeomFromGeoJSON(%s), %s), "
                                "    properties = EXCLUDED.properties, "
                                "    electrical_id = EXCLUDED.electrical_id, "
                                "    updated_at = EXCLUDED.updated_at",
                            ).format(_psycopg2.sql.Identifier(self.schema)),
                            (
                                asset.asset_id,
                                asset.asset_type,
                                geom_json,
                                _SPATIAL_REF_SYS,
                                props_json,
                                asset.electrical_id,
                                now,
                                geom_json,
                                _SPATIAL_REF_SYS,
                            ),
                        )
                    else:
                        cur.execute(
                            _psycopg2.sql.SQL(
                                "INSERT INTO {} "
                                "(asset_id, asset_type, properties, electrical_id, updated_at) "
                                "VALUES (%s, %s, %s::jsonb, %s, to_timestamp(%s)) "
                                "ON CONFLICT (asset_id) DO UPDATE SET "
                                "    asset_type = EXCLUDED.asset_type, "
                                "    properties = EXCLUDED.properties, "
                                "    electrical_id = EXCLUDED.electrical_id, "
                                "    updated_at = EXCLUDED.updated_at",
                            ).format(_psycopg2.sql.Identifier(self.schema)),
                            (
                                asset.asset_id,
                                asset.asset_type,
                                props_json,
                                asset.electrical_id,
                                now,
                            ),
                        )
                conn.commit()
            return True
        except Exception as exc:
            logger.exception("PostGIS upsert failed: %s", exc)
            return False

    def get_asset(self, asset_id: str) -> Optional[SpatialAsset]:
        """Get a single asset by ID."""
        if self._use_fallback:
            return self._fallback_get(asset_id)
        try:
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute(
                    _psycopg2.sql.SQL(
                        "SELECT asset_id, asset_type, "
                        "       ST_AsGeoJSON(geometry) AS geom_json, "
                        "       properties, electrical_id "
                        "FROM {}.spatial_assets "
                        "WHERE asset_id = %s",
                    ).format(_psycopg2.sql.Identifier(self.schema)),
                    (asset_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return SpatialAsset(
                    asset_id=row[0],
                    asset_type=row[1],
                    geometry=json.loads(row[2]) if row[2] else None,
                    properties=row[3]
                    if isinstance(row[3], dict)
                    else (json.loads(row[3]) if row[3] else {}),  # NOSONAR — S3358: nested conditional; extract to named variable (tech debt)
                    electrical_id=row[4],
                )
        except Exception as exc:
            logger.exception("PostGIS get failed: %s", exc)
            return None

    def query_by_type(self, asset_type: str) -> list[SpatialAsset]:
        """Get all assets of a given type."""
        if self._use_fallback:
            return self._fallback_query_by_type(asset_type)
        try:
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute(
                    _psycopg2.sql.SQL(
                        "SELECT asset_id, asset_type, "
                        "       ST_AsGeoJSON(geometry) AS geom_json, "
                        "       properties, electrical_id "
                        "FROM {}.spatial_assets "
                        "WHERE asset_type = %s",
                    ).format(_psycopg2.sql.Identifier(self.schema)),
                    (asset_type,),
                )
                results = []
                for row in cur:
                    results.append(
                        SpatialAsset(
                            asset_id=row[0],
                            asset_type=row[1],
                            geometry=json.loads(row[2]) if row[2] else None,
                            properties=row[3]
                            if isinstance(row[3], dict)
                            else (json.loads(row[3]) if row[3] else {}),  # NOSONAR — S3358: nested conditional; extract to named variable (tech debt)
                            electrical_id=row[4],
                        ),
                    )
                return results
        except Exception as exc:
            logger.exception("PostGIS query_by_type failed: %s", exc)
            return []

    def query_within_radius(self, lat: float, lon: float, radius_m: float) -> list[SpatialAsset]:
        """Spatial query: find all assets within a radius (meters)."""
        if self._use_fallback:
            return self._fallback_query_radius(lat, lon, radius_m)
        try:
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute(
                    _psycopg2.sql.SQL(
                        "SELECT asset_id, asset_type, "
                        "       ST_AsGeoJSON(geometry) AS geom_json, "
                        "       properties, electrical_id, "
                        "       ST_Distance("
                        "           geometry::geography, "
                        "           ST_SetSRID(ST_MakePoint(%s, %s), %s)::geography "
                        "       ) AS dist_m "
                        "FROM {}.spatial_assets "
                        "WHERE ST_DWithin("
                        "    geometry::geography, "
                        "    ST_SetSRID(ST_MakePoint(%s, %s), %s)::geography, "
                        "    %s "
                        ") "
                        "ORDER BY dist_m",
                    ).format(_psycopg2.sql.Identifier(self.schema)),
                    (lon, lat, _SPATIAL_REF_SYS, lon, lat, _SPATIAL_REF_SYS, radius_m),
                )
                results = []
                for row in cur:
                    results.append(
                        SpatialAsset(
                            asset_id=row[0],
                            asset_type=row[1],
                            geometry=json.loads(row[2]) if row[2] else None,
                            properties=row[3]
                            if isinstance(row[3], dict)
                            else (json.loads(row[3]) if row[3] else {}),  # NOSONAR — S3358: nested conditional; extract to named variable (tech debt)
                            electrical_id=row[4],
                        ),
                    )
                return results
        except Exception as exc:
            logger.exception("PostGIS radius query failed: %s", exc)
            return []

    def query_in_bbox(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float,
    ) -> list[SpatialAsset]:
        """Spatial query: find all assets within a bounding box."""
        if self._use_fallback:
            return self._fallback_query_bbox(min_lat, min_lon, max_lat, max_lon)
        try:
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute(
                    _psycopg2.sql.SQL(
                        "SELECT asset_id, asset_type, "
                        "       ST_AsGeoJSON(geometry) AS geom_json, "
                        "       properties, electrical_id "
                        "FROM {}.spatial_assets "
                        "WHERE geometry && ST_MakeEnvelope(%s, %s, %s, %s, %s)",
                    ).format(_psycopg2.sql.Identifier(self.schema)),
                    (min_lon, min_lat, max_lon, max_lat, _SPATIAL_REF_SYS),
                )
                results = []
                for row in cur:
                    results.append(
                        SpatialAsset(
                            asset_id=row[0],
                            asset_type=row[1],
                            geometry=json.loads(row[2]) if row[2] else None,
                            properties=row[3]
                            if isinstance(row[3], dict)
                            else (json.loads(row[3]) if row[3] else {}),  # NOSONAR — S3358: nested conditional; extract to named variable (tech debt)
                            electrical_id=row[4],
                        ),
                    )
                return results
        except Exception as exc:
            logger.exception("PostGIS bbox query failed: %s", exc)
            return []

    def delete_asset(self, asset_id: str) -> bool:
        """Delete an asset by ID."""
        if self._use_fallback:
            return self._fallback_delete(asset_id)
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        _psycopg2.sql.SQL(
                            "DELETE FROM {}.spatial_assets WHERE asset_id = %s",
                        ).format(_psycopg2.sql.Identifier(self.schema)),
                        (asset_id,),
                    )
                conn.commit()
            return True
        except Exception as exc:
            logger.exception("PostGIS delete failed: %s", exc)
            return False

    def get_all_assets(self) -> list[SpatialAsset]:
        """Get all spatial assets."""
        if self._use_fallback:
            return self._fallback_get_all()
        try:
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute(
                    _psycopg2.sql.SQL(
                        "SELECT asset_id, asset_type, "
                        "       ST_AsGeoJSON(geometry) AS geom_json, "
                        "       properties, electrical_id "
                        "FROM {}.spatial_assets "
                        "ORDER BY asset_type, asset_id",
                    ).format(_psycopg2.sql.Identifier(self.schema)),
                )
                results = []
                for row in cur:
                    results.append(
                        SpatialAsset(
                            asset_id=row[0],
                            asset_type=row[1],
                            geometry=json.loads(row[2]) if row[2] else None,
                            properties=row[3]
                            if isinstance(row[3], dict)
                            else (json.loads(row[3]) if row[3] else {}),  # NOSONAR — S3358: nested conditional; extract to named variable (tech debt)
                            electrical_id=row[4],
                        ),
                    )
                return results
        except Exception as exc:
            logger.exception("PostGIS get_all failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Network mapping
    # ------------------------------------------------------------------

    def map_electrical_to_gis(self, electrical_ids: list[str]) -> dict[str, dict[str, Any]]:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """Map electrical model IDs to their GIS spatial assets.

        Returns dict of electrical_id -> {asset_id, geometry, properties}
        """
        if self._use_fallback:
            result: dict[str, dict[str, Any]] = {}
            all_assets = self._fallback_get_all()
            for asset in all_assets:
                if asset.electrical_id and asset.electrical_id in electrical_ids and asset.geometry:
                    result[asset.electrical_id] = {
                        "asset_id": asset.asset_id,
                        "geometry": asset.geometry,
                        "properties": asset.properties,
                    }
            return result

        try:
            with self._conn() as conn:
                with conn.cursor(cursor_factory=_psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        _psycopg2.sql.SQL(
                            "SELECT electrical_id, asset_id, asset_type, "
                            "       ST_AsGeoJSON(geometry) AS geom_json, "
                            "       properties "
                            "FROM {}.spatial_assets "
                            "WHERE electrical_id = ANY(%s)",
                        ).format(_psycopg2.sql.Identifier(self.schema)),
                        (electrical_ids,),
                    )
                    result: dict[str, dict[str, Any]] = {}
                    for row in cur:
                        eid = row["electrical_id"]
                        geom = json.loads(row["geom_json"]) if row["geom_json"] else None
                        props = row["properties"] if isinstance(row["properties"], dict) else {}
                        if eid and geom:
                            result[eid] = {
                                "asset_id": row["asset_id"],
                                "geometry": geom,
                                "properties": props,
                            }
                    return result
        except Exception as exc:
            logger.exception("PostGIS electrical mapping failed: %s", exc)
            return {}

    def import_geojson_collection(self, geojson: dict[str, Any]) -> int:
        """Import a full GeoJSON FeatureCollection into PostGIS.

        Returns the number of assets imported.
        """
        count = 0
        features = geojson.get("features", [])
        for feat in features:
            geom = feat.get("geometry")
            props = feat.get("properties", {})
            asset_id = props.pop("asset_id", str(hash(str(geom))))
            asset_type = props.pop("asset_type", "generic")
            electrical_id = props.pop("electrical_id", None)
            asset = SpatialAsset(
                asset_id=asset_id,
                asset_type=asset_type,
                geometry=geom,
                properties=props,
                electrical_id=electrical_id or None,
            )
            if self.upsert_asset(asset):
                count += 1
        return count

    def export_geojson_collection(self, asset_type: Optional[str] = None) -> dict[str, Any]:
        """Export assets as a GeoJSON FeatureCollection."""
        assets = self.query_by_type(asset_type) if asset_type else self.get_all_assets()
        return {
            "type": "FeatureCollection",
            "features": [a.to_geojson_feature() for a in assets],
            "metadata": {
                "asset_count": len(assets),
                "asset_type": asset_type or "all",
                "crs": f"EPSG:{_SPATIAL_REF_SYS}",
            },
        }

    # ------------------------------------------------------------------
    # File-based fallback for development
    # ------------------------------------------------------------------

    def _fallback_path(self, asset_id: str) -> str:
        sanitized = asset_id.replace("/", "_").replace("\\", "_").replace(":", "_")
        return os.path.join(self._fallback_dir, f"{sanitized}.json")

    def _fallback_upsert(self, asset: SpatialAsset) -> bool:
        path = self._fallback_path(asset.asset_id)
        try:
            with open(path, "w") as f:
                json.dump(
                    {
                        "asset_id": asset.asset_id,
                        "asset_type": asset.asset_type,
                        "geometry": asset.geometry,
                        "properties": asset.properties,
                        "electrical_id": asset.electrical_id,
                        "updated_at": time.time(),
                    },
                    f,
                    indent=2,
                )
            return True
        except Exception as exc:
            logger.exception("Fallback upsert failed: %s", exc)
            return False

    def _fallback_get(self, asset_id: str) -> Optional[SpatialAsset]:
        path = self._fallback_path(asset_id)
        try:
            with open(path) as f:
                data = json.load(f)
            return SpatialAsset(**data)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _fallback_get_all(self) -> list[SpatialAsset]:
        results = []
        if not os.path.isdir(self._fallback_dir):
            return results
        for fname in os.listdir(self._fallback_dir):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(self._fallback_dir, fname)) as f:
                        data = json.load(f)
                    results.append(SpatialAsset(**data))
                except Exception:
                    continue
        return results

    def _fallback_query_by_type(self, asset_type: str) -> list[SpatialAsset]:
        return [a for a in self._fallback_get_all() if a.asset_type == asset_type]

    def _fallback_query_radius(self, lat: float, lon: float, radius_m: float) -> list[SpatialAsset]:
        """Simple Haversine filter for fallback mode."""
        results = []
        for asset in self._fallback_get_all():
            if not asset.geometry:
                continue
            coord = self._get_geometry_center(asset.geometry)
            if coord is None:
                continue
            alon, alat = coord
            d = self._haversine(lat, lon, alat, alon)
            if d <= radius_m:
                results.append(asset)
        return results

    def _fallback_query_bbox(self, min_lat, min_lon, max_lat, max_lon):
        results = []
        for asset in self._fallback_get_all():
            if not asset.geometry:
                continue
            coord = self._get_geometry_center(asset.geometry)
            if coord is None:
                continue
            alon, alat = coord
            if min_lat <= alat <= max_lat and min_lon <= alon <= max_lon:
                results.append(asset)
        return results

    def _fallback_delete(self, asset_id: str) -> bool:
        path = self._fallback_path(asset_id)
        try:
            os.remove(path)
            return True
        except FileNotFoundError:
            return False

    @staticmethod
    def _get_geometry_center(geometry: dict[str, Any]) -> tuple[float, float] | None:
        gtype = geometry.get("type")
        coords = geometry.get("coordinates")
        if not coords:
            return None
        if gtype == "Point":
            return tuple(coords[:2])  # type: ignore
        if gtype in ("LineString", "MultiPoint"):
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            return (sum(xs) / len(xs), sum(ys) / len(ys))
        if gtype in ("Polygon",):
            ring = coords[0]
            xs = [c[0] for c in ring]
            ys = [c[1] for c in ring]
            return (sum(xs) / len(xs), sum(ys) / len(ys))
        return None

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine distance in meters."""
        import math

        R = 6371000
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
