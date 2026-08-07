"""
core/models.py — Core data models for the Universal Data Model.

Combines standard dataclasses (for performance-sensitive paths) with
Pydantic BaseModels (for validation-heavy / API-facing schemas).
"""

from __future__ import annotations

from dataclasses import dataclass, field
<<<<<<< HEAD
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017

from typing import Any, Optional
=======
from datetime import UTC, datetime

UTC = UTC
from typing import Any, Dict, List
>>>>>>> origin/fix/scenario-tests-properly

from pydantic import BaseModel, Field, field_validator

from compat import StrEnum

# =========================================================================
# Pydantic models — validation + serialisation for API boundaries
# =========================================================================


class PydanticPoint3D(BaseModel):
    """Pydantic equivalent of Point3D with built-in validation."""

    x: float
    y: float
    z: float = 0.0


class PydanticGeometry(BaseModel):
    """Pydantic equivalent of Geometry with auto-validation."""

<<<<<<< HEAD
    points: list[PydanticPoint3D] = Field(default_factory=list)
    polyline_closed: bool = False
    area: Optional[float] = None
    perimeter: Optional[float] = None

    @field_validator("area")
    @classmethod
    def area_must_be_positive(cls, v: Optional[float]) -> Optional[float]:
=======
    points: List[PydanticPoint3D] = Field(default_factory=list)
    polyline_closed: bool = False
    area: float | None = None
    perimeter: float | None = None

    @field_validator("area")
    @classmethod
    def area_must_be_positive(cls, v: float | None) -> float | None:
>>>>>>> origin/fix/scenario-tests-properly
        if v is not None and v < 0:
            raise ValueError("area must be non-negative")
        return v


class PydanticSemanticProperties(BaseModel):
    """Pydantic equivalent of SemanticProperties with enum validation."""

    element_type: str
<<<<<<< HEAD
    name: Optional[str] = None
=======
    name: str | None = None
>>>>>>> origin/fix/scenario-tests-properly

    @field_validator("element_type")
    @classmethod
    def element_type_must_be_valid(cls, v: str) -> str:
        valid_types = {e.value for e in ElementType}
        if v not in valid_types:
            raise ValueError(
<<<<<<< HEAD
                f"'{v}' is not a valid ElementType. Choose from: {sorted(valid_types)}",
            )
        return v

    description: Optional[str] = None
    material: Optional[str] = None
    fire_rating: Optional[str] = None
    height: Optional[float] = None
    width: Optional[float] = None
    load_bearing: Optional[bool] = None
    layer: Optional[str] = None
    revit_category: Optional[str] = None
=======
                f"'{v}' is not a valid ElementType. Choose from: {sorted(valid_types)}"
            )
        return v

    description: str | None = None
    material: str | None = None
    fire_rating: str | None = None
    height: float | None = None
    width: float | None = None
    load_bearing: bool | None = None
    layer: str | None = None
    revit_category: str | None = None
>>>>>>> origin/fix/scenario-tests-properly


class PydanticUniversalElement(BaseModel):
    """Pydantic equivalent of UniversalElement for API use.

    Accepts either ``Relationship`` dataclass instances or plain dicts
    in the ``relationships`` field via a ``@field_validator``.

    Use ``PydanticUniversalElement.from_dataclass(elem)`` to convert from
    the internal ``UniversalElement`` dataclass in a single call.
    """

    element_id: str
<<<<<<< HEAD
    properties: Optional[PydanticSemanticProperties] = None
    geometry: Optional[PydanticGeometry] = None
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    created_timestamp: Optional[datetime] = None
    last_modified_timestamp: Optional[datetime] = None
    last_modified_by: Optional[str] = None
    source_file: Optional[str] = None
=======
    properties: PydanticSemanticProperties | None = None
    geometry: PydanticGeometry | None = None
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    created_timestamp: datetime | None = None
    last_modified_timestamp: datetime | None = None
    last_modified_by: str | None = None
    source_file: str | None = None
>>>>>>> origin/fix/scenario-tests-properly
    version: int = 0
    is_deleted: bool = False

    @field_validator("relationships", mode="before")
    @classmethod
    def coerce_relationship_objects(cls, v: Any) -> Any:
        """Coerce ``Relationship`` dataclass instances to dicts."""
        if isinstance(v, list):
            return [item.to_dict() if hasattr(item, "to_dict") else item for item in v]
        return v

    @classmethod
    def from_dataclass(cls, elem: UniversalElement) -> PydanticUniversalElement:
        """Build a Pydantic model from an internal ``UniversalElement`` dataclass."""
        return cls(
            element_id=elem.element_id,
            properties=PydanticSemanticProperties(**elem.properties.to_dict())
            if elem.properties
            else None,
            geometry=PydanticGeometry(**elem.geometry.to_dict()) if elem.geometry else None,
            relationships=[r.to_dict() for r in elem.relationships],
            created_timestamp=elem.created_timestamp,
            last_modified_timestamp=elem.last_modified_timestamp,
            last_modified_by=elem.last_modified_by,
            source_file=elem.source_file,
            version=elem.version,
            is_deleted=elem.is_deleted,
        )


# =========================================================================
# Dataclass models — lightweight, performance-optimised for internal use
# =========================================================================


# Moved BEFORE Pydantic models so that @field_validator in
# PydanticSemanticProperties can reference it without forward-reference issues.
class ElementType(StrEnum):
    WALL = "wall"
    DOOR = "door"
    WINDOW = "window"
    FLOOR = "floor"
    CEILING = "ceiling"
    COLUMN = "column"
    BEAM = "beam"
    STAIRS = "stairs"
    RAMP = "ramp"
    ROOF = "roof"
    GENERIC = "generic"


class ChangeSource(StrEnum):
    MANUAL = "manual"
    AUTOCAD = "autocad"
    REVIT = "revit"
    IFC = "ifc"
    DWG = "dwg"
    AI = "ai"


class ConflictType(StrEnum):
    GEOMETRY_MISMATCH = "geometry_mismatch"
    PROPERTY_MISMATCH = "property_mismatch"
    MISSING_IN_SOURCE_A = "missing_in_source_a"
    MISSING_IN_SOURCE_B = "missing_in_source_b"
    DUPLICATE = "duplicate"


@dataclass
class Point3D:
    x: float
    y: float
    z: float = 0.0

<<<<<<< HEAD
    def to_dict(self) -> dict[str, float]:
=======
    def to_dict(self) -> Dict[str, float]:
>>>>>>> origin/fix/scenario-tests-properly
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass
class Geometry:
<<<<<<< HEAD
    points: list[Point3D] = field(default_factory=list)
    polyline_closed: bool = False
    area: Optional[float] = None
    perimeter: Optional[float] = None
=======
    points: List[Point3D] = field(default_factory=list)
    polyline_closed: bool = False
    area: float | None = None
    perimeter: float | None = None
>>>>>>> origin/fix/scenario-tests-properly

    def calculate_area(self) -> float:
        """Calculate polygon area using shoelace formula."""
        if len(self.points) < 3:
            self.area = 0.0
            return 0.0

        n = len(self.points)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += self.points[i].x * self.points[j].y
            area -= self.points[j].x * self.points[i].y

        self.area = abs(area) / 2.0
        return self.area

<<<<<<< HEAD
    def to_dict(self) -> dict[str, Any]:
=======
    def to_dict(self) -> Dict[str, Any]:
>>>>>>> origin/fix/scenario-tests-properly
        return {
            "points": [p.to_dict() for p in self.points],
            "polyline_closed": self.polyline_closed,
            "area": self.area,
            "perimeter": self.perimeter,
        }


@dataclass
class SemanticProperties:
    element_type: ElementType
<<<<<<< HEAD
    name: Optional[str] = None
    description: Optional[str] = None
    material: Optional[str] = None
    fire_rating: Optional[str] = None
    height: Optional[float] = None
    width: Optional[float] = None
    load_bearing: Optional[bool] = None
    layer: Optional[str] = None
    revit_category: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
=======
    name: str | None = None
    description: str | None = None
    material: str | None = None
    fire_rating: str | None = None
    height: float | None = None
    width: float | None = None
    load_bearing: bool | None = None
    layer: str | None = None
    revit_category: str | None = None

    def to_dict(self) -> Dict[str, Any]:
>>>>>>> origin/fix/scenario-tests-properly
        return {
            "element_type": self.element_type.value,
            "name": self.name,
            "description": self.description,
            "material": self.material,
            "fire_rating": self.fire_rating,
            "height": self.height,
            "width": self.width,
            "load_bearing": self.load_bearing,
            "layer": self.layer,
            "revit_category": self.revit_category,
        }


@dataclass
class Relationship:
    from_element_id: str
    to_element_id: str
    relationship_type: str
    is_parametric: bool = False
<<<<<<< HEAD
    metadata: dict[str, Any] | None = None
    connection_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
=======
    metadata: Dict[str, Any] | None = None
    connection_id: str | None = None

    def to_dict(self) -> Dict[str, Any]:
>>>>>>> origin/fix/scenario-tests-properly
        return {
            "from_element_id": self.from_element_id,
            "to_element_id": self.to_element_id,
            "relationship_type": self.relationship_type,
            "is_parametric": self.is_parametric,
            "metadata": self.metadata,
            "connection_id": self.connection_id,
        }


@dataclass
class UniversalElement:
    element_id: str
<<<<<<< HEAD
    properties: Optional[SemanticProperties] = None
    geometry: Optional[Geometry] = None
    relationships: list[Relationship] = field(default_factory=list)
    created_timestamp: Optional[datetime] = None
    last_modified_timestamp: Optional[datetime] = None
    last_modified_by: Optional[str] = None
    source_file: Optional[str] = None
    version: int = 0
    is_deleted: bool = False
    autocad_handle: Optional[str] = None
    revit_element_id: Optional[str] = None
=======
    properties: SemanticProperties | None = None
    geometry: Geometry | None = None
    relationships: List[Relationship] = field(default_factory=list)
    created_timestamp: datetime | None = None
    last_modified_timestamp: datetime | None = None
    last_modified_by: str | None = None
    source_file: str | None = None
    version: int = 0
    is_deleted: bool = False
    autocad_handle: str | None = None
    revit_element_id: str | None = None
>>>>>>> origin/fix/scenario-tests-properly

    def __post_init__(self):
        if self.created_timestamp is None:
            self.created_timestamp = datetime.now(UTC)
        if self.last_modified_timestamp is None:
            self.last_modified_timestamp = self.created_timestamp

<<<<<<< HEAD
    def to_dict(self) -> dict[str, Any]:
=======
    def to_dict(self) -> Dict[str, Any]:
>>>>>>> origin/fix/scenario-tests-properly
        return {
            "element_id": self.element_id,
            "properties": self.properties.to_dict() if self.properties else None,
            "geometry": self.geometry.to_dict() if self.geometry else None,
            "relationships": [r.to_dict() for r in self.relationships],
            "created_timestamp": self.created_timestamp.isoformat()
            if self.created_timestamp
            else None,
            "last_modified_timestamp": self.last_modified_timestamp.isoformat()
            if self.last_modified_timestamp
            else None,
            "last_modified_by": self.last_modified_by,
            "source_file": self.source_file,
            "version": self.version,
            "is_deleted": self.is_deleted,
            "autocad_handle": self.autocad_handle,
            "revit_element_id": self.revit_element_id,
        }


@dataclass
class Conflict:
    conflict_id: str
    conflict_type: ConflictType
<<<<<<< HEAD
    element_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    source_a: ChangeSource = ChangeSource.MANUAL
    source_b: ChangeSource = ChangeSource.MANUAL
    change_a: dict[str, Any] | None = None
    change_b: dict[str, Any] | None = None
    resolution: dict[str, Any] | None = None
=======
    element_id: str | None = None
    timestamp: datetime | None = None
    source_a: ChangeSource = ChangeSource.MANUAL
    source_b: ChangeSource = ChangeSource.MANUAL
    change_a: Dict[str, Any] | None = None
    change_b: Dict[str, Any] | None = None
    resolution: Dict[str, Any] | None = None
>>>>>>> origin/fix/scenario-tests-properly
    resolved: bool = False

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(UTC)

<<<<<<< HEAD
    def to_dict(self) -> dict[str, Any]:
=======
    def to_dict(self) -> Dict[str, Any]:
>>>>>>> origin/fix/scenario-tests-properly
        return {
            "conflict_id": self.conflict_id,
            "element_id": self.element_id,
            "conflict_type": self.conflict_type.value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "source_a": self.source_a.value,
            "source_b": self.source_b.value,
            "change_a": self.change_a,
            "change_b": self.change_b,
            "resolution": self.resolution,
            "resolved": self.resolved,
        }
