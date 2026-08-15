"""
api/tenants.py — Tenant (organization) model and CRUD router.

Provides:
- Tenant ORM model (organizations / accounts)
- Tenant provisioning endpoint (admin only)
- Tenant lookup by slug

This is the foundation for multi-tenant isolation:
  - Every tenant-scoped table has a ``tenant_id`` FK → tenants.id
  - Row-Level Security (RLS) in PostgreSQL restricts rows to the
    current tenant set via ``SET app.current_tenant_id``
  - The TenantMiddleware (backend/request_context.py) extracts
    tenant_id from JWT claims and sets the session variable
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base, get_db
from api.dependencies import (
    CurrentUser,
    require_role,
)

# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------


class Tenant(Base):
    """An organization / account in the multi-tenant system.

    Each tenant represents a separate organization. All tenant-scoped
    tables (users, projects, assets, etc.) have a ``tenant_id`` FK
    pointing to this table. Row-Level Security (RLS) policies in
    PostgreSQL use ``tenant_id`` to enforce data isolation.
    """

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default="free", nullable=False)
    max_projects: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_users: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Pydantic v2 schemas
# ---------------------------------------------------------------------------


class TenantCreateRequest(BaseModel):
    """Payload for ``POST /api/v1/tenants``."""

    model_config = ConfigDict(strict=False)

    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    plan: str = Field(default="free", max_length=32)
    max_projects: int = Field(default=10, ge=1)
    max_users: int = Field(default=5, ge=1)


class TenantResponse(BaseModel):
    """Public tenant representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    is_active: bool = True
    plan: str = "free"
    max_projects: int = 10
    max_users: int = 5
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/tenants", tags=["Tenants"])


@router.post(
    "",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tenant (admin only)",
)
async def create_tenant(
    body: TenantCreateRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(require_role("admin")),  # noqa: B008
) -> Any:
    """Create a new tenant (organization). Requires admin role."""
    # Check slug uniqueness
    existing = await db.execute(select(Tenant).where(Tenant.slug == body.slug))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant slug already exists: {body.slug}",
        )

    tenant = Tenant(
        id=str(uuid.uuid4()),
        name=body.name,
        slug=body.slug,
        plan=body.plan,
        max_projects=body.max_projects,
        max_users=body.max_users,
    )
    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)
    return TenantResponse.model_validate(tenant)


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Get a tenant by ID (admin only)",
)
async def get_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(require_role("admin")),  # noqa: B008
) -> Any:
    """Retrieve a tenant by ID. Requires admin role."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant not found: {tenant_id}",
        )
    return TenantResponse.model_validate(tenant)

