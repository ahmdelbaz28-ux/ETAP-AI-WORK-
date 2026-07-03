import pytest  # added for S1244 float-equality fix
"""Tests for core/models.py — Universal Data Model core dataclasses."""

import uuid
from datetime import datetime

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


class TestPoint3D:
    def test_creation(self):
        p = Point3D(1.0, 2.0, 3.0)
        assert p.x == pytest.approx(1.0)
        assert p.y == pytest.approx(2.0)
        assert p.z == pytest.approx(3.0)

    def test_default_z(self):
        p = Point3D(1.0, 2.0)
        assert p.z == pytest.approx(0.0)

    def test_to_dict(self):
        p = Point3D(1.0, 2.0, 3.0)
        d = p.to_dict()
        assert d == {"x": 1.0, "y": 2.0, "z": 3.0}


class TestGeometry:
    def test_creation(self):
        g = Geometry()
        assert g.points == []
        assert g.polyline_closed is False
        assert g.area is None

    def test_calculate_area_triangle(self):
        points = [Point3D(0, 0), Point3D(4, 0), Point3D(0, 3)]
        g = Geometry(points=points)
        area = g.calculate_area()
        assert area == pytest.approx(6.0)
        assert g.area == pytest.approx(6.0)

    def test_calculate_area_less_than_3_points(self):
        points = [Point3D(0, 0), Point3D(4, 0)]
        g = Geometry(points=points)
        area = g.calculate_area()
        assert area == pytest.approx(0.0)

    def test_to_dict(self):
        points = [Point3D(0, 0), Point3D(4, 0), Point3D(0, 3)]
        g = Geometry(points=points, polyline_closed=True)
        d = g.to_dict()
        assert len(d["points"]) == 3
        assert d["polyline_closed"] is True


class TestSemanticProperties:
    def test_creation(self):
        props = SemanticProperties(element_type=ElementType.WALL)
        assert props.element_type == ElementType.WALL
        assert props.name is None

    def test_creation_with_all_fields(self):
        props = SemanticProperties(
            element_type=ElementType.DOOR,
            name="Front Door",
            material="Steel",
            height=2.1,
            width=0.9,
            load_bearing=False,
        )
        assert props.name == "Front Door"
        assert props.material == "Steel"

    def test_to_dict(self):
        props = SemanticProperties(element_type=ElementType.WINDOW, name="Window A")
        d = props.to_dict()
        assert d["element_type"] == "window"
        assert d["name"] == "Window A"

    def test_to_dict_enum_values(self):
        props = SemanticProperties(element_type=ElementType.COLUMN)
        d = props.to_dict()
        assert d["element_type"] == "column"


class TestRelationship:
    def test_creation(self):
        r = Relationship(from_element_id="a", to_element_id="b", relationship_type="connected")
        assert r.from_element_id == "a"
        assert r.to_element_id == "b"
        assert r.is_parametric is False

    def test_to_dict(self):
        r = Relationship(
            from_element_id="a",
            to_element_id="b",
            relationship_type="supported_by",
            is_parametric=True,
        )
        d = r.to_dict()
        assert d["from_element_id"] == "a"
        assert d["relationship_type"] == "supported_by"
        assert d["is_parametric"] is True


class TestUniversalElement:
    def test_creation(self):
        eid = str(uuid.uuid4())
        el = UniversalElement(element_id=eid)
        assert el.element_id == eid
        assert el.version == 0
        assert el.is_deleted is False
        assert el.created_timestamp is not None
        assert el.last_modified_timestamp is not None

    def test_post_init_sets_timestamps(self):
        el = UniversalElement(element_id=str(uuid.uuid4()))
        assert isinstance(el.created_timestamp, datetime)
        assert isinstance(el.last_modified_timestamp, datetime)
        assert el.last_modified_timestamp == el.created_timestamp

    def test_to_dict(self):
        el = UniversalElement(element_id="test-1")
        d = el.to_dict()
        assert d["element_id"] == "test-1"
        assert d["version"] == 0
        assert d["is_deleted"] is False
        assert d["properties"] is None
        assert d["geometry"] is None

    def test_to_dict_with_properties_and_geometry(self):
        props = SemanticProperties(element_type=ElementType.WALL, name="Main Wall")
        points = [Point3D(0, 0), Point3D(10, 0), Point3D(10, 5), Point3D(0, 5)]
        geom = Geometry(points=points, polyline_closed=True)
        el = UniversalElement(element_id="test-2", properties=props, geometry=geom)
        d = el.to_dict()
        assert d["properties"]["element_type"] == "wall"
        assert d["properties"]["name"] == "Main Wall"
        assert d["geometry"]["polyline_closed"] is True
        assert len(d["geometry"]["points"]) == 4

    def test_version_defaults_to_zero(self):
        el = UniversalElement(element_id=str(uuid.uuid4()))
        assert el.version == 0

    def test_is_deleted_defaults_to_false(self):
        el = UniversalElement(element_id=str(uuid.uuid4()))
        assert el.is_deleted is False

    def test_relationships_default_to_empty(self):
        el = UniversalElement(element_id=str(uuid.uuid4()))
        assert el.relationships == []


class TestConflict:
    def test_creation(self):
        cid = str(uuid.uuid4())
        c = Conflict(conflict_id=cid, conflict_type=ConflictType.DUPLICATE)
        assert c.conflict_id == cid
        assert c.conflict_type == ConflictType.DUPLICATE
        assert c.resolved is False
        assert c.timestamp is not None

    def test_post_init_sets_timestamp(self):
        c = Conflict(conflict_id=str(uuid.uuid4()), conflict_type=ConflictType.GEOMETRY_MISMATCH)
        assert isinstance(c.timestamp, datetime)

    def test_to_dict(self):
        c = Conflict(
            conflict_id=str(uuid.uuid4()),
            conflict_type=ConflictType.PROPERTY_MISMATCH,
            element_id="elem-1",
        )
        d = c.to_dict()
        assert d["conflict_type"] == "property_mismatch"
        assert d["element_id"] == "elem-1"
        assert d["resolved"] is False
        assert d["source_a"] == "manual"
        assert d["source_b"] == "manual"

    def test_to_dict_with_all_fields(self):
        c = Conflict(
            conflict_id=str(uuid.uuid4()),
            conflict_type=ConflictType.DUPLICATE,
            element_id="elem-1",
            source_a=ChangeSource.AUTOCAD,
            source_b=ChangeSource.REVIT,
            change_a={"old": "value_a"},
            change_b={"old": "value_b"},
            resolved=True,
        )
        d = c.to_dict()
        assert d["conflict_type"] == "duplicate"
        assert d["source_a"] == "autocad"
        assert d["source_b"] == "revit"
        assert d["change_a"] == {"old": "value_a"}
        assert d["resolved"] is True
