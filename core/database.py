"""
core/database.py — Universal Data Model database.

Thread-safe SQLite-backed storage for BIM elements with conflict detection.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any, Dict, List, Optional

from core.models import (
    ChangeSource,
    Conflict,
    ConflictType,
    ElementType,
    Geometry,
    Point3D,
    Relationship,
    SemanticProperties,
    UniversalElement,
)

logger = logging.getLogger(__name__)


class UniversalDataModel:
    """Thread-safe universal data model for BIM elements."""

    def __init__(self, db_path: str = "udm_elements.db") -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._local = threading.local()
        self.elements: Dict[str, UniversalElement] = {}
        self.conflicts: Dict[str, Conflict] = {}
        self._init_db()
        self._load_elements()

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
            # check_same_thread=False is safe because we use thread-local connections:
            # each thread gets its own Connection object, so the connection is never
            # shared across threads. The flag is required for SQLite to accept
            # connections created in a different thread than the one using them.
            self._local.conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self) -> None:
        """Initialize database tables."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS elements (
                element_id TEXT PRIMARY KEY,
                element_type TEXT,
                name TEXT,
                description TEXT,
                material TEXT,
                fire_rating TEXT,
                height REAL,
                width REAL,
                load_bearing INTEGER,
                layer TEXT,
                revit_category TEXT,
                geometry TEXT,
                relationships TEXT,
                created_timestamp TEXT,
                last_modified_timestamp TEXT,
                last_modified_by TEXT,
                source_file TEXT,
                version INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0,
                autocad_handle TEXT,
                revit_element_id TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conflicts (
                conflict_id TEXT PRIMARY KEY,
                element_id TEXT,
                conflict_type TEXT,
                timestamp TEXT,
                source_a TEXT,
                source_b TEXT,
                change_a TEXT,
                change_b TEXT,
                resolution TEXT,
                resolved INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS element_projects (
                element_id TEXT,
                project_id TEXT,
                PRIMARY KEY (element_id, project_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                relationship_id TEXT PRIMARY KEY,
                from_element_id TEXT NOT NULL,
                to_element_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                is_parametric INTEGER DEFAULT 0,
                metadata TEXT,
                is_deleted INTEGER DEFAULT 0,
                last_modified_timestamp TEXT
            )
        """)

        conn.commit()

    def _load_elements(self) -> None:
        """Load elements from database into memory."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM elements WHERE is_deleted = 0")

            for row in cursor.fetchall():
                element = self._row_to_element(dict(row))
                if element:
                    self.elements[element.element_id] = element

            cursor.execute("SELECT * FROM conflicts")
            for row in cursor.fetchall():
                conflict = self._row_to_conflict(dict(row))
                if conflict:
                    self.conflicts[conflict.conflict_id] = conflict

    def _row_to_element(self, row: Dict[str, Any]) -> Optional[UniversalElement]:
        """Convert database row to UniversalElement."""
        try:
            geometry = None
            if row.get("geometry"):
                geom_data = json.loads(row["geometry"])
                geometry = Geometry(
                    points=[Point3D(**p) for p in geom_data.get("points", [])],
                    polyline_closed=geom_data.get("polyline_closed", False),
                    area=geom_data.get("area"),
                    perimeter=geom_data.get("perimeter"),
                )

            properties = SemanticProperties(
                element_type=ElementType(row.get("element_type", "generic")),
                name=row.get("name"),
                description=row.get("description"),
                material=row.get("material"),
                fire_rating=row.get("fire_rating"),
                height=row.get("height"),
                width=row.get("width"),
                load_bearing=bool(row.get("load_bearing"))
                if row.get("load_bearing") is not None
                else None,
                layer=row.get("layer"),
                revit_category=row.get("revit_category"),
            )

            relationships = []
            if row.get("relationships"):
                rel_data = json.loads(row["relationships"])
                for r in rel_data:
                    relationships.append(
                        Relationship(
                            from_element_id=r["from_element_id"],
                            to_element_id=r["to_element_id"],
                            relationship_type=r["relationship_type"],
                            is_parametric=r.get("is_parametric", False),
                            metadata=r.get("metadata"),
                            connection_id=r.get("connection_id"),
                        )
                    )

            return UniversalElement(
                element_id=row["element_id"],
                properties=properties,
                geometry=geometry,
                relationships=relationships,
                created_timestamp=datetime.fromisoformat(row["created_timestamp"])
                if row.get("created_timestamp")
                else None,
                last_modified_timestamp=datetime.fromisoformat(row["last_modified_timestamp"])
                if row.get("last_modified_timestamp")
                else None,
                last_modified_by=row.get("last_modified_by"),
                source_file=row.get("source_file"),
                version=row.get("version", 0),
                is_deleted=bool(row.get("is_deleted", 0)),
                autocad_handle=row.get("autocad_handle"),
                revit_element_id=row.get("revit_element_id"),
            )
        except Exception as e:
            logger.error("Error converting row to element: %s", e, exc_info=True)
            return None

    def _row_to_conflict(self, row: Dict[str, Any]) -> Optional[Conflict]:
        """Convert database row to Conflict."""
        try:
            return Conflict(
                conflict_id=row["conflict_id"],
                conflict_type=ConflictType(row.get("conflict_type", "geometry_mismatch")),
                element_id=row.get("element_id"),
                timestamp=datetime.fromisoformat(row["timestamp"])
                if row.get("timestamp")
                else None,
                source_a=ChangeSource(row.get("source_a", "manual")),
                source_b=ChangeSource(row.get("source_b", "manual")),
                change_a=json.loads(row["change_a"]) if row.get("change_a") else None,
                change_b=json.loads(row["change_b"]) if row.get("change_b") else None,
                resolution=json.loads(row["resolution"]) if row.get("resolution") else None,
                resolved=bool(row.get("resolved", 0)),
            )
        except Exception as e:
            logger.error("Error converting row to conflict: %s", e, exc_info=True)
            return None

    def add_element(self, element: UniversalElement) -> bool:
        """Add an element to the data model."""
        with self._lock:
            try:
                conn = self._get_conn()
                cursor = conn.cursor()
                now = datetime.now(UTC).isoformat()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO elements
                    (element_id, element_type, name, description, material, fire_rating,
                     height, width, load_bearing, layer, revit_category, geometry,
                     relationships, created_timestamp, last_modified_timestamp, last_modified_by,
                     source_file, version, is_deleted, autocad_handle, revit_element_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        element.element_id,
                        element.properties.element_type.value if element.properties else "generic",
                        element.properties.name if element.properties else None,
                        element.properties.description if element.properties else None,
                        element.properties.material if element.properties else None,
                        element.properties.fire_rating if element.properties else None,
                        element.properties.height if element.properties else None,
                        element.properties.width if element.properties else None,
                        int(element.properties.load_bearing)
                        if element.properties and element.properties.load_bearing is not None
                        else None,
                        element.properties.layer if element.properties else None,
                        element.properties.revit_category if element.properties else None,
                        json.dumps(element.geometry.to_dict()) if element.geometry else None,
                        json.dumps([r.to_dict() for r in element.relationships])
                        if element.relationships
                        else None,
                        element.created_timestamp.isoformat() if element.created_timestamp else now,
                        now,
                        element.last_modified_by,
                        element.source_file,
                        element.version,
                        int(element.is_deleted),
                        element.autocad_handle,
                        element.revit_element_id,
                    ),
                )
                conn.commit()
                self.elements[element.element_id] = element
                return True
            except Exception as e:
                logger.error("Error adding element: %s", e, exc_info=True)
                return False

    def get_element(self, element_id: str) -> Optional[UniversalElement]:
        """Get an element by ID."""
        with self._lock:
            return self.elements.get(element_id)

    def get_all_elements(self) -> List[UniversalElement]:
        """Get all non-deleted elements."""
        with self._lock:
            return [e for e in self.elements.values() if not e.is_deleted]

    def update_element(
        self,
        element_id: str,
        updates: Dict[str, Any],
        source: ChangeSource = ChangeSource.MANUAL,
        reason: str = "",
    ) -> bool:
        """Update an element."""
        with self._lock:
            element = self.elements.get(element_id)
            if not element:
                return False

            try:
                if "properties" in updates:
                    props_data = updates["properties"]
                    if isinstance(props_data, dict):
                        element.properties = SemanticProperties(
                            element_type=ElementType(props_data.get("element_type", "generic")),
                            name=props_data.get("name"),
                            description=props_data.get("description"),
                            material=props_data.get("material"),
                            fire_rating=props_data.get("fire_rating"),
                            height=props_data.get("height"),
                            width=props_data.get("width"),
                            load_bearing=props_data.get("load_bearing"),
                            layer=props_data.get("layer"),
                            revit_category=props_data.get("revit_category"),
                        )

                if "geometry" in updates:
                    geom_data = updates["geometry"]
                    if isinstance(geom_data, dict):
                        element.geometry = Geometry(
                            points=[Point3D(**p) for p in geom_data.get("points", [])],
                            polyline_closed=geom_data.get("polyline_closed", False),
                        )

                if "source_file" in updates:
                    element.source_file = updates["source_file"]
                if "last_modified_by" in updates:
                    element.last_modified_by = updates["last_modified_by"]
                if "is_deleted" in updates:
                    element.is_deleted = updates["is_deleted"]

                element.version += 1
                element.last_modified_timestamp = datetime.now(UTC)

                conn = self._get_conn()
                cursor = conn.cursor()
                now = datetime.now(UTC).isoformat()

                cursor.execute(
                    """
                    UPDATE elements SET
                        element_type = ?, name = ?, description = ?, material = ?,
                        fire_rating = ?, height = ?, width = ?, load_bearing = ?,
                        layer = ?, revit_category = ?, geometry = ?, relationships = ?,
                        last_modified_timestamp = ?, last_modified_by = ?, source_file = ?,
                        version = ?, is_deleted = ?
                    WHERE element_id = ?
                """,
                    (
                        element.properties.element_type.value if element.properties else "generic",
                        element.properties.name if element.properties else None,
                        element.properties.description if element.properties else None,
                        element.properties.material if element.properties else None,
                        element.properties.fire_rating if element.properties else None,
                        element.properties.height if element.properties else None,
                        element.properties.width if element.properties else None,
                        int(element.properties.load_bearing)
                        if element.properties and element.properties.load_bearing is not None
                        else None,
                        element.properties.layer if element.properties else None,
                        element.properties.revit_category if element.properties else None,
                        json.dumps(element.geometry.to_dict()) if element.geometry else None,
                        json.dumps([r.to_dict() for r in element.relationships])
                        if element.relationships
                        else None,
                        now,
                        element.last_modified_by,
                        element.source_file,
                        element.version,
                        int(element.is_deleted),
                        element_id,
                    ),
                )
                conn.commit()
                return True
            except Exception as e:
                logger.error("Error updating element: %s", e, exc_info=True)
                return False

    def delete_element(self, element_id: str, source: ChangeSource = ChangeSource.MANUAL) -> bool:
        """Soft-delete an element."""
        return self.update_element(element_id, {"is_deleted": True}, source=source)

    def detect_conflicts(self) -> List[Conflict]:
        """Detect conflicts between elements."""
        with self._lock:
            conflicts = []
            seen = {}
            for element in self.elements.values():
                if element.is_deleted:
                    continue
                key = f"{element.properties.name}:{element.properties.element_type.value if element.properties else 'generic'}"
                if key in seen:
                    conflict = Conflict(
                        conflict_id=str(uuid.uuid4()),
                        conflict_type=ConflictType.DUPLICATE,
                        element_id=element.element_id,
                        source_a=ChangeSource.MANUAL,
                        source_b=ChangeSource.MANUAL,
                        change_a={"element_id": seen[key]},
                        change_b={"element_id": element.element_id},
                    )
                    conflicts.append(conflict)
                else:
                    seen[key] = element.element_id
            return conflicts

    def resolve_conflict(self, conflict: Conflict, strategy: str = "SEMANTIC_MERGE") -> bool:
        """Resolve a conflict."""
        with self._lock:
            try:
                conflict.resolved = True
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE conflicts SET resolved = 1, resolution = ? WHERE conflict_id = ?",
                    (json.dumps({"strategy": strategy}), conflict.conflict_id),
                )
                conn.commit()
                return True
            except Exception as e:
                logger.error("Error resolving conflict: %s", e, exc_info=True)
                return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._lock:
            total = len(self.elements)
            deleted = sum(1 for e in self.elements.values() if e.is_deleted)
            active = total - deleted

            return {
                "total_elements": total,
                "deleted_elements": deleted,
                "active_elements": active,
                "pending_autocad_to_revit": 0,
                "pending_revit_to_autocad": 0,
                "database_version": 1,
                "last_sync": datetime.now(UTC).isoformat(),
            }

    def close(self) -> None:
        """Close database connections."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
