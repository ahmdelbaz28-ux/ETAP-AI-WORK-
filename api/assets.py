"""
api/assets.py — Asset management router.

Provides endpoints for managing electrical assets (transformers, generators,
breakers, motors, lines, relays) associated with power-system projects.

Assets are stored in the database and linked to projects via project_id.

Endpoints (under ``/api/v1/assets``):
* ``GET /``                  — List assets (filterable by project_id, type, status)
* ``GET /{asset_id}``        — Get a single asset
* ``POST /``                 — Create a new asset
* ``PUT /{asset_id}``        — Update an asset
* ``DELETE /{asset_id}``     — Delete an asset (returns 204 No Content)

All endpoints require a valid JWT (or X-API-Key when API_KEY is configured).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated


from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base, get_db
from api.dependencies import (
    CurrentUser,
    PaginationParams,
    get_api_key,
    get_current_user_from_header,
    pagination_params,
)
from compat import StrEnum

router = APIRouter(prefix="/api/v1/assets", tags=["Asset Management"])


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AssetType(StrEnum):
    """Electrical asset types."""

    TRANSFORMER = "Transformer"
    GENERATOR = "Generator"
    BREAKER = "Breaker"
    MOTOR = "Motor"
    LINE = "Line"
    RELAY = "Relay"
    CAPACITOR = "Capacitor"
    REACTOR = "Reactor"
    BUS = "Bus"
    OTHER = "Other"


class AssetStatus(StrEnum):
    """Asset operational status."""

    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    FAULTED = "faulted"
    OFFLINE = "offline"


# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------

class Asset(Base):
    """Electrical asset (transformer, generator, breaker, motor, line, relay)."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # AssetType
    rating: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "10 MVA"
    voltage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "13.8 kV"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AssetStatus.ACTIVE.value)
    project_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("projects.id"), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AssetCreateRequest(BaseModel):
    """Request body for creating an asset."""

    name: str = Field(..., min_length=1, max_length=255, description="Asset name")
    type: AssetType = Field(..., description="Asset type")
    rating: str | None = Field(None, max_length=100, description="Asset rating, e.g., '10 MVA'")
    voltage: str | None = Field(None, max_length=100, description="Operating voltage, e.g., '13.8 kV'")
    status: AssetStatus = Field(AssetStatus.ACTIVE, description="Initial status")
    project_id: str | None = Field(None, description="Optional project ID to link this asset to")
    notes: str | None = Field(None, max_length=1000, description="Free-form notes")


class AssetUpdateRequest(BaseModel):
    """Request body for updating an asset."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[AssetType] = None
    rating: Optional[str] = Field(None, max_length=100)
    voltage: Optional[str] = Field(None, max_length=100)
    status: Optional[AssetStatus] = None
    project_id: Optional[str] = Field(None)
    notes: Optional[str] = Field(None, max_length=1000)


class AssetResponse(BaseModel):
    """Response model for an asset."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: str
    rating: str | None = None
    voltage: str | None = None
    status: str
    project_id: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    notes: str | None = None


class AssetListResponse(BaseModel):
    """Paginated asset list response."""

    assets: list[AssetResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=AssetListResponse,
    summary="List assets",
    dependencies=[Depends(get_api_key)],
)
async def list_assets(
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: Annotated[str | None, Query(description="Filter by project ID")] = None,
    type_filter: Annotated[AssetType | None, Query(alias="type", description="Filter by asset type")] = None,
    status_filter: Annotated[AssetStatus | None, Query(alias="status", description="Filter by status")] = None,
) -> Any:
    """Return a paginated, filterable list of electrical assets."""
    base_query = select(Asset)

    if project_id is not None:
        base_query = base_query.where(Asset.project_id == project_id)
    if type_filter is not None:
        base_query = base_query.where(Asset.type == type_filter.value)
    if status_filter is not None:
        base_query = base_query.where(Asset.status == status_filter.value)

    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    result = await db.execute(
        base_query.order_by(Asset.updated_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size),
    )
    assets = result.scalars().all()

    return AssetListResponse(
        assets=[AssetResponse.model_validate(a) for a in assets],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="Get a single asset",
    dependencies=[Depends(get_api_key)],
)
async def get_asset(
    asset_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Return a single asset by ID."""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Asset '{asset_id}' not found")
    return AssetResponse.model_validate(asset)


@router.post(
    "",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new asset",
    dependencies=[Depends(get_api_key)],
)
async def create_asset(
    body: AssetCreateRequest,
    user: Annotated[CurrentUser, Depends(get_current_user_from_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Create a new electrical asset."""
    asset = Asset(
        id=str(uuid.uuid4()),
        name=body.name,
        type=body.type.value,
        rating=body.rating,
        voltage=body.voltage,
        status=body.status.value,
        project_id=body.project_id,
        created_by=user.user_id,
        notes=body.notes,
    )
    db.add(asset)
    await db.flush()
    await db.refresh(asset)
    return AssetResponse.model_validate(asset)


@router.put(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="Update an asset",
    dependencies=[Depends(get_api_key)],
)
async def update_asset(
    asset_id: str,
    body: AssetUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Update an existing asset. Only non-null fields are updated."""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Asset '{asset_id}' not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key in ("type", "status") and value is not None:
            value = value.value if hasattr(value, "value") else str(value)
        setattr(asset, key, value)

    await db.flush()
    await db.refresh(asset)
    return AssetResponse.model_validate(asset)


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete an asset",
    dependencies=[Depends(get_api_key)],
)
async def delete_asset(
    asset_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Permanently delete an asset.

    Returns 204 No Content on success (per RFC 9110 §15.3.5). Uses
    `response_class=Response` to opt out of FastAPI's default response-model
    validation, which would otherwise reject the 204 + body combination
    (FastAPI 0.115+ enforces this at route registration time).
    """
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Asset '{asset_id}' not found")
    await db.delete(asset)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
