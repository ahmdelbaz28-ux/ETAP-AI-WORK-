"""
api/equipment.py — Equipment Library Management API.

Provides:
- EquipmentCategory model (transformers, cables, breakers, etc.)
- Equipment model with full specifications
- EquipmentTemplate model for pre-configured systems
- CRUD endpoints for equipment management
- Import/Export equipment data
- Search and filter capabilities

Exposes endpoints under the ``/api/v1/equipment`` prefix:
* ``GET    /categories``               — List equipment categories
* ``POST   /categories``               — Create equipment category
* ``PUT    /categories/{category_id}`` — Update category
* ``DELETE /categories/{category_id}`` — Delete category
* ``GET    /``                         — List equipment (paginated, filterable)
* ``POST   /``                         — Create new equipment
* ``GET    /{equipment_id}``           — Get equipment by ID
* ``PUT    /{equipment_id}``           — Update equipment
* ``DELETE /{equipment_id}``           — Delete equipment
* ``GET    /search``                   — Search equipment by specs
* ``POST   /import``                   — Import equipment from file
* ``GET    /export``                   — Export equipment to file
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, Optional

UTC = UTC

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    and_,
    func,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base, get_db
from api.dependencies import (
    CurrentUser,
    PaginationParams,
    pagination_params,
)
from api.rbac import require_permission

# ---------------------------------------------------------------------------
# SQLAlchemy ORM models
# ---------------------------------------------------------------------------


class EquipmentCategory(Base):
    """A category/type of equipment (e.g. Transformer, Cable, Breaker)."""

    __tablename__ = "equipment_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    equipment_list = relationship("Equipment", back_populates="category", lazy="selectin")


class Equipment(Base):
    """A piece of electrical equipment with specifications."""

    __tablename__ = "equipment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("equipment_categories.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Electrical specifications (JSON for flexibility)
    specs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Physical specifications
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dimensions: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # "LxWxH"

    # Standards compliance
    standards: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {"IEEE": "C57.12.00", "IEC": "60076"}

    # Metadata
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    category = relationship("EquipmentCategory", back_populates="equipment_list")


# ---------------------------------------------------------------------------
# Pydantic v2 schemas — Categories
# ---------------------------------------------------------------------------


class CategoryCreateRequest(BaseModel):
    """Payload for ``POST /api/v1/equipment/categories``."""

    model_config = ConfigDict(strict=False)

    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9_-]+$")
    description: Optional[str] = Field(default=None, max_length=500)
    icon: Optional[str] = Field(default=None, max_length=64)
    display_order: int = Field(default=0, ge=0)


class CategoryUpdateRequest(BaseModel):
    """Payload for ``PUT /api/v1/equipment/categories/{category_id}``."""

    model_config = ConfigDict(strict=False)

    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=128, pattern=r"^[a-z0-9_-]+$")
    description: Optional[str] = Field(default=None, max_length=500)
    icon: Optional[str] = Field(default=None, max_length=64)
    display_order: Optional[int] = Field(default=None, ge=0)


class CategoryResponse(BaseModel):
    """Public category representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    display_order: int = 0
    equipment_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CategoryListResponse(BaseModel):
    """List of categories response."""

    model_config = ConfigDict(from_attributes=True)

    categories: list[CategoryResponse]
    total: int


# ---------------------------------------------------------------------------
# Pydantic v2 schemas — Equipment
# ---------------------------------------------------------------------------


class EquipmentCreateRequest(BaseModel):
    """Payload for ``POST /api/v1/equipment``."""

    model_config = ConfigDict(strict=False)

    category_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=255)
    manufacturer: Optional[str] = Field(default=None, max_length=255)
    model_number: Optional[str] = Field(default=None, max_length=255)
    serial_number: Optional[str] = Field(default=None, max_length=255)
    specs: Optional[dict[str, Any]] = None
    weight_kg: Optional[float] = None
    dimensions: Optional[str] = Field(default=None, max_length=255)
    standards: Optional[dict[str, str]] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class EquipmentUpdateRequest(BaseModel):
    """Payload for ``PUT /api/v1/equipment/{equipment_id}``."""

    model_config = ConfigDict(strict=False)

    category_id: Optional[str] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    manufacturer: Optional[str] = Field(default=None, max_length=255)
    model_number: Optional[str] = Field(default=None, max_length=255)
    serial_number: Optional[str] = Field(default=None, max_length=255)
    specs: Optional[dict[str, Any]] = None
    weight_kg: Optional[float] = None
    dimensions: Optional[str] = Field(default=None, max_length=255)
    standards: Optional[dict[str, str]] = None
    tags: Optional[list[str]] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class EquipmentResponse(BaseModel):
    """Public equipment representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    category_id: str
    category_name: str = ""
    name: str
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    serial_number: Optional[str] = None
    specs: Optional[dict[str, Any]] = None
    weight_kg: Optional[float] = None
    dimensions: Optional[str] = None
    standards: Optional[dict[str, str]] = None
    tags: Optional[list[str]] = None
    is_active: bool = True
    notes: Optional[str] = None
    created_by: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EquipmentListResponse(BaseModel):
    """Paginated equipment list response."""

    model_config = ConfigDict(from_attributes=True)

    equipment: list[EquipmentResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/equipment", tags=["Equipment"])


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


async def _get_category_by_id(db: AsyncSession, category_id: str) -> EquipmentCategory:
    """Fetch a category by ID or raise 404."""
    result = await db.execute(
        select(EquipmentCategory).where(EquipmentCategory.id == category_id)
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category not found: {category_id}",
        )
    return category


async def _get_equipment_by_id(db: AsyncSession, equipment_id: str) -> Equipment:
    """Fetch equipment by ID or raise 404."""
    result = await db.execute(
        select(Equipment).where(Equipment.id == equipment_id)
    )
    equipment = result.scalar_one_or_none()
    if equipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment not found: {equipment_id}",
        )
    return equipment


async def _build_equipment_response(
    db: AsyncSession, equipment: Equipment,
) -> EquipmentResponse:
    """Build an EquipmentResponse with category name."""
    category_name = ""
    if equipment.category:
        category_name = equipment.category.name
    return EquipmentResponse(
        id=str(equipment.id),
        category_id=equipment.category_id,
        category_name=category_name,
        name=equipment.name,
        manufacturer=equipment.manufacturer,
        model_number=equipment.model_number,
        serial_number=equipment.serial_number,
        specs=equipment.specs,
        weight_kg=equipment.weight_kg,
        dimensions=equipment.dimensions,
        standards=equipment.standards,
        tags=equipment.tags,
        is_active=equipment.is_active,
        notes=equipment.notes,
        created_by=equipment.created_by,
        created_at=equipment.created_at,
        updated_at=equipment.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints — Categories
# ---------------------------------------------------------------------------


@router.get(
    "/categories",
    response_model=CategoryListResponse,
    summary="List equipment categories",
)
async def list_categories(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("equipment", "list")),  # noqa: B008
) -> Any:
    """Return all equipment categories with equipment counts."""
    result = await db.execute(
        select(EquipmentCategory).order_by(EquipmentCategory.display_order.asc())
    )
    categories = result.scalars().all()

    response_categories = []
    for cat in categories:
        count_result = await db.execute(
            select(func.count()).select_from(Equipment).where(
                Equipment.category_id == cat.id,
                Equipment.is_active == True,
            )
        )
        count = count_result.scalar_one()

        response_categories.append(CategoryResponse(
            id=str(cat.id),
            name=cat.name,
            slug=cat.slug,
            description=cat.description,
            icon=cat.icon,
            display_order=cat.display_order,
            equipment_count=count,
            created_at=cat.created_at,
            updated_at=cat.updated_at,
        ))

    return CategoryListResponse(
        categories=response_categories,
        total=len(response_categories),
    )


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create equipment category",
)
async def create_category(
    body: CategoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("equipment", "create")),  # noqa: B008
) -> Any:
    """Create a new equipment category."""
    # Check name uniqueness
    existing = await db.execute(
        select(EquipmentCategory).where(
            or_(
                EquipmentCategory.name == body.name,
                EquipmentCategory.slug == body.slug,
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category with this name or slug already exists",
        )

    category = EquipmentCategory(
        id=str(uuid.uuid4()),
        name=body.name,
        slug=body.slug,
        description=body.description,
        icon=body.icon,
        display_order=body.display_order,
    )
    db.add(category)
    await db.flush()
    await db.refresh(category)

    return CategoryResponse(
        id=str(category.id),
        name=category.name,
        slug=category.slug,
        description=category.description,
        icon=category.icon,
        display_order=category.display_order,
        equipment_count=0,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


@router.put(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    summary="Update equipment category",
)
async def update_category(
    category_id: str,
    body: CategoryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("equipment", "update")),  # noqa: B008
) -> Any:
    """Update an equipment category."""
    category = await _get_category_by_id(db, category_id)

    if body.name is not None:
        existing = await db.execute(
            select(EquipmentCategory).where(
                EquipmentCategory.name == body.name,
                EquipmentCategory.id != category_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category with this name already exists",
            )
        category.name = body.name

    if body.slug is not None:
        existing = await db.execute(
            select(EquipmentCategory).where(
                EquipmentCategory.slug == body.slug,
                EquipmentCategory.id != category_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category with this slug already exists",
            )
        category.slug = body.slug

    if body.description is not None:
        category.description = body.description
    if body.icon is not None:
        category.icon = body.icon
    if body.display_order is not None:
        category.display_order = body.display_order

    category.updated_at = datetime.now(UTC)
    db.add(category)
    await db.flush()
    await db.refresh(category)

    return CategoryResponse(
        id=str(category.id),
        name=category.name,
        slug=category.slug,
        description=category.description,
        icon=category.icon,
        display_order=category.display_order,
        equipment_count=0,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete equipment category",
)
async def delete_category(
    category_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("equipment", "delete")),  # noqa: B008
) -> dict[str, str]:
    """Delete an equipment category."""
    category = await _get_category_by_id(db, category_id)

    # Check if category has equipment
    count_result = await db.execute(
        select(func.count()).select_from(Equipment).where(
            Equipment.category_id == category_id
        )
    )
    if count_result.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete category with existing equipment. Remove or reassign equipment first.",
        )

    await db.delete(category)
    await db.flush()

    return {"message": f"Category '{category.name}' deleted successfully"}


# ---------------------------------------------------------------------------
# Endpoints — Equipment
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=EquipmentListResponse,
    summary="List equipment (paginated, filterable)",
)
async def list_equipment(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("equipment", "list")),  # noqa: B008
    pagination: PaginationParams = Depends(pagination_params),  # noqa: B008
    category_id: Optional[str] = Query(None, description="Filter by category"),
    manufacturer: Optional[str] = Query(None, description="Filter by manufacturer"),
    search: Optional[str] = Query(None, description="Search by name/model"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
) -> Any:
    """Return a paginated, filterable list of equipment."""
    # Build query
    query = select(Equipment)

    filters = []
    if category_id:
        filters.append(Equipment.category_id == category_id)
    if manufacturer:
        filters.append(Equipment.manufacturer.ilike(f"%{manufacturer}%"))
    if search:
        filters.append(
            or_(
                Equipment.name.ilike(f"%{search}%"),
                Equipment.model_number.ilike(f"%{search}%"),
                Equipment.manufacturer.ilike(f"%{search}%"),
            )
        )
    if is_active is not None:
        filters.append(Equipment.is_active == is_active)

    if filters:
        query = query.where(and_(*filters))

    # Total count
    count_query = select(func.count()).select_from(Equipment)
    if filters:
        count_query = count_query.where(and_(*filters))
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Paginated query
    result = await db.execute(
        query.order_by(Equipment.name.asc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    equipment_list = result.scalars().all()

    # Build responses with category names
    equipment_responses = []
    for equip in equipment_list:
        equipment_responses.append(await _build_equipment_response(db, equip))

    return EquipmentListResponse(
        equipment=equipment_responses,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "/",
    response_model=EquipmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new equipment",
)
async def create_equipment(
    body: EquipmentCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("equipment", "create")),  # noqa: B008
) -> Any:
    """Add a new piece of equipment to the library."""
    # Verify category exists
    await _get_category_by_id(db, body.category_id)

    equipment = Equipment(
        id=str(uuid.uuid4()),
        category_id=body.category_id,
        name=body.name,
        manufacturer=body.manufacturer,
        model_number=body.model_number,
        serial_number=body.serial_number,
        specs=body.specs,
        weight_kg=body.weight_kg,
        dimensions=body.dimensions,
        standards=body.standards,
        tags=body.tags,
        notes=body.notes,
        created_by=user.user_id,
    )
    db.add(equipment)
    await db.flush()
    await db.refresh(equipment)

    return await _build_equipment_response(db, equipment)


@router.get(
    "/{equipment_id}",
    response_model=EquipmentResponse,
    summary="Get equipment by ID",
)
async def get_equipment(
    equipment_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("equipment", "read")),  # noqa: B008
) -> Any:
    """Get detailed information about a specific piece of equipment."""
    equipment = await _get_equipment_by_id(db, equipment_id)
    return await _build_equipment_response(db, equipment)


@router.put(
    "/{equipment_id}",
    response_model=EquipmentResponse,
    summary="Update equipment",
)
async def update_equipment(
    equipment_id: str,
    body: EquipmentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("equipment", "update")),  # noqa: B008
) -> Any:
    """Update equipment specifications."""
    equipment = await _get_equipment_by_id(db, equipment_id)

    if body.category_id is not None:
        await _get_category_by_id(db, body.category_id)
        equipment.category_id = body.category_id
    if body.name is not None:
        equipment.name = body.name
    if body.manufacturer is not None:
        equipment.manufacturer = body.manufacturer
    if body.model_number is not None:
        equipment.model_number = body.model_number
    if body.serial_number is not None:
        equipment.serial_number = body.serial_number
    if body.specs is not None:
        equipment.specs = body.specs
    if body.weight_kg is not None:
        equipment.weight_kg = body.weight_kg
    if body.dimensions is not None:
        equipment.dimensions = body.dimensions
    if body.standards is not None:
        equipment.standards = body.standards
    if body.tags is not None:
        equipment.tags = body.tags
    if body.is_active is not None:
        equipment.is_active = body.is_active
    if body.notes is not None:
        equipment.notes = body.notes

    equipment.updated_at = datetime.now(UTC)
    db.add(equipment)
    await db.flush()
    await db.refresh(equipment)

    return await _build_equipment_response(db, equipment)


@router.delete(
    "/{equipment_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete equipment",
)
async def delete_equipment(
    equipment_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("equipment", "delete")),  # noqa: B008
) -> dict[str, str]:
    """Delete a piece of equipment from the library."""
    equipment = await _get_equipment_by_id(db, equipment_id)

    await db.delete(equipment)
    await db.flush()

    return {"message": f"Equipment '{equipment.name}' deleted successfully"}


@router.get(
    "/search",
    response_model=EquipmentListResponse,
    summary="Search equipment by specifications",
)
async def search_equipment(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("equipment", "list")),  # noqa: B008
    query: str = Query(..., min_length=1, description="Search query"),
    category_id: Optional[str] = Query(None, description="Filter by category"),
    pagination: PaginationParams = Depends(pagination_params),  # noqa: B008
) -> Any:
    """Search equipment by name, model, manufacturer, or specs."""
    search_filter = or_(
        Equipment.name.ilike(f"%{query}%"),
        Equipment.manufacturer.ilike(f"%{query}%"),
        Equipment.model_number.ilike(f"%{query}%"),
        Equipment.notes.ilike(f"%{query}%"),
    )

    if category_id:
        search_filter = and_(search_filter, Equipment.category_id == category_id)

    count_result = await db.execute(
        select(func.count()).select_from(Equipment).where(search_filter)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Equipment)
        .where(search_filter)
        .order_by(Equipment.name.asc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    equipment_list = result.scalars().all()

    equipment_responses = []
    for equip in equipment_list:
        equipment_responses.append(await _build_equipment_response(db, equip))

    return EquipmentListResponse(
        equipment=equipment_responses,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


# ---------------------------------------------------------------------------
# Endpoints — Import/Export
# ---------------------------------------------------------------------------


@router.post(
    "/import",
    response_model=Dict[str, Any],
    summary="Import equipment from JSON or CSV file",
)
async def import_equipment(
    file: UploadFile = File(...),
    db: DbDep = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(require_permission("equipment", "create")),  # noqa: B008
) -> Any:
    """Import equipment from an uploaded JSON or CSV file."""
    content = await file.read()
    imported = 0
    errors: list[str] = []

    if file.filename and file.filename.endswith(".csv"):
        # Parse CSV
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        for row_num, row in enumerate(reader, start=2):
            try:
                name = row.get("name", "").strip()
                category_name = row.get("category", "").strip()
                if not name or not category_name:
                    errors.append(f"Row {row_num}: Missing required fields (name, category)")
                    continue

                # Find or create category
                cat_result = await db.execute(
                    select(EquipmentCategory).where(
                        EquipmentCategory.name == category_name
                    )
                )
                category = cat_result.scalar_one_or_none()
                if category is None:
                    slug = category_name.lower().replace(" ", "_")
                    category = EquipmentCategory(
                        id=str(uuid.uuid4()),
                        name=category_name,
                        slug=slug,
                    )
                    db.add(category)
                    await db.flush()

                equipment = Equipment(
                    id=str(uuid.uuid4()),
                    category_id=category.id,
                    name=name,
                    manufacturer=row.get("manufacturer", "").strip() or None,
                    model_number=row.get("model_number", "").strip() or None,
                    specs={"voltage": row.get("voltage"), "power": row.get("power")},
                    created_by=user.user_id,
                )
                db.add(equipment)
                imported += 1
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

    else:
        # Parse JSON
        try:
            data = json.loads(content)
            if not isinstance(data, list):
                data = [data]

            for item in data:
                try:
                    name = item.get("name", "").strip()
                    category_name = item.get("category", "").strip()
                    if not name or not category_name:
                        errors.append(f"Missing required fields in item: {item}")
                        continue

                    cat_result = await db.execute(
                        select(EquipmentCategory).where(
                            EquipmentCategory.name == category_name
                        )
                    )
                    category = cat_result.scalar_one_or_none()
                    if category is None:
                        slug = category_name.lower().replace(" ", "_")
                        category = EquipmentCategory(
                            id=str(uuid.uuid4()),
                            name=category_name,
                            slug=slug,
                        )
                        db.add(category)
                        await db.flush()

                    equipment = Equipment(
                        id=str(uuid.uuid4()),
                        category_id=category.id,
                        name=name,
                        manufacturer=item.get("manufacturer"),
                        model_number=item.get("model_number"),
                        specs=item.get("specs"),
                        weight_kg=item.get("weight_kg"),
                        dimensions=item.get("dimensions"),
                        standards=item.get("standards"),
                        tags=item.get("tags"),
                        notes=item.get("notes"),
                        created_by=user.user_id,
                    )
                    db.add(equipment)
                    imported += 1
                except Exception as e:
                    errors.append(f"Error importing item {item.get('name', 'unknown')}: {str(e)}")

        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON file: {str(e)}",
            )

    await db.flush()

    return {
        "message": f"Imported {imported} equipment items",
        "imported_count": imported,
        "error_count": len(errors),
        "errors": errors[:20],  # Limit error reporting
    }


@router.get(
    "/export",
    response_model=Dict[str, Any],
    summary="Export equipment to JSON",
)
async def export_equipment(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("equipment", "list")),  # noqa: B008
    category_id: Optional[str] = Query(None, description="Filter by category"),
) -> Any:
    """Export all equipment (optionally filtered by category) as JSON."""
    query = select(Equipment).where(Equipment.is_active == True)
    if category_id:
        query = query.where(Equipment.category_id == category_id)

    result = await db.execute(query.order_by(Equipment.name.asc()))
    equipment_list = result.scalars().all()

    export_data = []
    for equip in equipment_list:
        equip_response = await _build_equipment_response(db, equip)
        export_data.append(equip_response.model_dump())

    return {
        "count": len(export_data),
        "equipment": export_data,
        "exported_at": datetime.now(UTC).isoformat(),
    }
