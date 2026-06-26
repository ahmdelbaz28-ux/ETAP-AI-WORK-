"""Tests for core/database.py — Universal Data Model database."""

import os
import tempfile
import threading
import uuid

import pytest

from core.database import UniversalDataModel
from core.models import (
    ConflictType,
    ElementType,
    Geometry,
    Point3D,
    SemanticProperties,
    UniversalElement,
)


@pytest.fixture
def udm():
    db_path = os.path.join(tempfile.mkdtemp(), "test_udm.db")
    model = UniversalDataModel(db_path)
    yield model
    model.close()
    if os.path.exists(db_path):
        os.remove(db_path)


class TestUniversalDataModelInit:
    def test_initialization(self, udm):
        assert udm.elements == {}
        assert udm.conflicts == {}

    def test_database_tables_created(self, udm):
        conn = udm._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row["name"] for row in cursor.fetchall()]
        assert "elements" in tables
        assert "conflicts" in tables
        assert "element_projects" in tables
        assert "relationships" in tables


class TestAddElement:
    def test_add_element_success(self, udm):
        el = UniversalElement(element_id=str(uuid.uuid4()))
        result = udm.add_element(el)
        assert result is True
        assert el.element_id in udm.elements

    def test_add_element_with_properties(self, udm):
        props = SemanticProperties(element_type=ElementType.WALL, name="Test Wall")
        el = UniversalElement(element_id=str(uuid.uuid4()), properties=props)
        udm.add_element(el)
        stored = udm.get_element(el.element_id)
        assert stored is not None
        assert stored.properties.name == "Test Wall"
        assert stored.properties.element_type == ElementType.WALL

    def test_add_element_with_geometry(self, udm):
        points = [Point3D(0, 0), Point3D(10, 0), Point3D(10, 5), Point3D(0, 5)]
        geom = Geometry(points=points, polyline_closed=True)
        el = UniversalElement(element_id=str(uuid.uuid4()), geometry=geom)
        udm.add_element(el)
        stored = udm.get_element(el.element_id)
        assert stored is not None
        assert stored.geometry.polyline_closed is True
        assert len(stored.geometry.points) == 4

    def test_add_duplicate_replaces(self, udm):
        eid = str(uuid.uuid4())
        el1 = UniversalElement(
            element_id=eid,
            properties=SemanticProperties(element_type=ElementType.WALL, name="First"),
        )
        el2 = UniversalElement(
            element_id=eid,
            properties=SemanticProperties(element_type=ElementType.DOOR, name="Second"),
        )
        udm.add_element(el1)
        udm.add_element(el2)
        stored = udm.get_element(eid)
        assert stored.properties.name == "Second"


class TestGetElement:
    def test_get_existing_element(self, udm):
        el = UniversalElement(element_id=str(uuid.uuid4()))
        udm.add_element(el)
        result = udm.get_element(el.element_id)
        assert result is not None
        assert result.element_id == el.element_id

    def test_get_nonexistent_element(self, udm):
        result = udm.get_element("nonexistent")
        assert result is None


class TestGetAllElements:
    def test_get_all_elements(self, udm):
        el1 = UniversalElement(element_id="a")
        el2 = UniversalElement(element_id="b")
        udm.add_element(el1)
        udm.add_element(el2)
        all_els = udm.get_all_elements()
        assert len(all_els) == 2

    def test_get_all_excludes_deleted(self, udm):
        el1 = UniversalElement(element_id="a")
        el2 = UniversalElement(element_id="b", is_deleted=True)
        udm.add_element(el1)
        udm.add_element(el2)
        all_els = udm.get_all_elements()
        assert len(all_els) == 1
        assert all_els[0].element_id == "a"


class TestUpdateElement:
    def test_update_properties(self, udm):
        eid = str(uuid.uuid4())
        el = UniversalElement(
            element_id=eid, properties=SemanticProperties(element_type=ElementType.WALL)
        )
        udm.add_element(el)
        result = udm.update_element(
            eid, {"properties": {"element_type": "door", "name": "Updated"}}
        )
        assert result is True
        stored = udm.get_element(eid)
        assert stored.properties.element_type == ElementType.DOOR
        assert stored.properties.name == "Updated"

    def test_update_geometry(self, udm):
        eid = str(uuid.uuid4())
        el = UniversalElement(element_id=eid)
        udm.add_element(el)
        result = udm.update_element(
            eid,
            {
                "geometry": {
                    "points": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 0, "y": 1}],
                    "polyline_closed": True,
                }
            },
        )
        assert result is True
        stored = udm.get_element(eid)
        assert len(stored.geometry.points) == 3
        assert stored.geometry.polyline_closed is True

    def test_update_nonexistent_element(self, udm):
        result = udm.update_element("nonexistent", {"is_deleted": True})
        assert result is False

    def test_update_increments_version(self, udm):
        eid = str(uuid.uuid4())
        el = UniversalElement(element_id=eid)
        udm.add_element(el)
        assert udm.get_element(eid).version == 0
        udm.update_element(eid, {"source_file": "test.dwg"})
        assert udm.get_element(eid).version == 1

    def test_update_source_file(self, udm):
        eid = str(uuid.uuid4())
        el = UniversalElement(element_id=eid)
        udm.add_element(el)
        udm.update_element(eid, {"source_file": "updated.dwg"})
        assert udm.get_element(eid).source_file == "updated.dwg"

    def test_update_last_modified_by(self, udm):
        eid = str(uuid.uuid4())
        el = UniversalElement(element_id=eid)
        udm.add_element(el)
        udm.update_element(eid, {"last_modified_by": "tester"})
        assert udm.get_element(eid).last_modified_by == "tester"


class TestDeleteElement:
    def test_soft_delete(self, udm):
        el = UniversalElement(element_id=str(uuid.uuid4()))
        udm.add_element(el)
        result = udm.delete_element(el.element_id)
        assert result is True
        stored = udm.get_element(el.element_id)
        assert stored.is_deleted is True

    def test_deleted_not_in_get_all(self, udm):
        eid = str(uuid.uuid4())
        udm.add_element(UniversalElement(element_id=eid))
        udm.delete_element(eid)
        all_els = udm.get_all_elements()
        assert eid not in [e.element_id for e in all_els]


class TestConflictDetection:
    def test_detect_no_conflicts(self, udm):
        udm.add_element(
            UniversalElement(
                element_id="a",
                properties=SemanticProperties(element_type=ElementType.WALL, name="Wall A"),
            )
        )
        udm.add_element(
            UniversalElement(
                element_id="b",
                properties=SemanticProperties(element_type=ElementType.DOOR, name="Door B"),
            )
        )
        conflicts = udm.detect_conflicts()
        assert len(conflicts) == 0

    def test_detect_duplicate_conflict(self, udm):
        udm.add_element(
            UniversalElement(
                element_id="a",
                properties=SemanticProperties(element_type=ElementType.WALL, name="Duplicate"),
            )
        )
        udm.add_element(
            UniversalElement(
                element_id="b",
                properties=SemanticProperties(element_type=ElementType.WALL, name="Duplicate"),
            )
        )
        conflicts = udm.detect_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.DUPLICATE

    def test_detect_ignores_deleted(self, udm):
        udm.add_element(
            UniversalElement(
                element_id="a",
                properties=SemanticProperties(element_type=ElementType.WALL, name="Same"),
            )
        )
        udm.add_element(
            UniversalElement(
                element_id="b",
                properties=SemanticProperties(element_type=ElementType.WALL, name="Same"),
                is_deleted=True,
            )
        )
        conflicts = udm.detect_conflicts()
        assert len(conflicts) == 0

    def test_detect_multiple_conflicts(self, udm):
        udm.add_element(
            UniversalElement(
                element_id="a",
                properties=SemanticProperties(element_type=ElementType.WALL, name="Dup1"),
            )
        )
        udm.add_element(
            UniversalElement(
                element_id="b",
                properties=SemanticProperties(element_type=ElementType.WALL, name="Dup1"),
            )
        )
        udm.add_element(
            UniversalElement(
                element_id="c",
                properties=SemanticProperties(element_type=ElementType.DOOR, name="Dup2"),
            )
        )
        udm.add_element(
            UniversalElement(
                element_id="d",
                properties=SemanticProperties(element_type=ElementType.DOOR, name="Dup2"),
            )
        )
        conflicts = udm.detect_conflicts()
        assert len(conflicts) == 2


class TestResolveConflict:
    def test_resolve_conflict(self, udm):
        udm.add_element(
            UniversalElement(
                element_id="a",
                properties=SemanticProperties(element_type=ElementType.WALL, name="Dup"),
            )
        )
        udm.add_element(
            UniversalElement(
                element_id="b",
                properties=SemanticProperties(element_type=ElementType.WALL, name="Dup"),
            )
        )
        conflicts = udm.detect_conflicts()
        assert len(conflicts) == 1
        result = udm.resolve_conflict(conflicts[0])
        assert result is True


class TestGetStatistics:
    def test_get_statistics_empty(self, udm):
        stats = udm.get_statistics()
        assert stats["total_elements"] == 0
        assert stats["active_elements"] == 0
        assert stats["deleted_elements"] == 0

    def test_get_statistics_with_data(self, udm):
        udm.add_element(
            UniversalElement(
                element_id="a", properties=SemanticProperties(element_type=ElementType.WALL)
            )
        )
        udm.add_element(
            UniversalElement(
                element_id="b", properties=SemanticProperties(element_type=ElementType.DOOR)
            )
        )
        udm.add_element(
            UniversalElement(
                element_id="c",
                properties=SemanticProperties(element_type=ElementType.WINDOW),
                is_deleted=True,
            )
        )
        stats = udm.get_statistics()
        assert stats["total_elements"] == 3
        assert stats["active_elements"] == 2
        assert stats["deleted_elements"] == 1

    def test_get_statistics_has_database_version(self, udm):
        stats = udm.get_statistics()
        assert stats["database_version"] == 1

    def test_get_statistics_has_last_sync(self, udm):
        stats = udm.get_statistics()
        assert "last_sync" in stats
        assert stats["last_sync"] is not None


class TestThreadSafety:
    def test_concurrent_add(self, udm):
        results = []

        def add_elements(start, count):
            try:
                for _i in range(start, start + count):
                    el = UniversalElement(element_id=str(uuid.uuid4()))
                    results.append(udm.add_element(el))
            finally:
                udm.close()

        threads = [
            threading.Thread(target=add_elements, args=(0, 10)),
            threading.Thread(target=add_elements, args=(10, 10)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(results)
        assert len(udm.get_all_elements()) == 20

    def test_concurrent_get(self, udm):
        eid = str(uuid.uuid4())
        udm.add_element(UniversalElement(element_id=eid))
        results = []

        def get_element():
            try:
                results.append(udm.get_element(eid))
            finally:
                udm.close()

        threads = [threading.Thread(target=get_element) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r is not None for r in results)


class TestClose:
    def test_close_connection(self, udm):
        conn = udm._get_conn()
        assert conn is not None
        udm.close()
        assert not hasattr(udm._local, "conn") or udm._local.conn is None
