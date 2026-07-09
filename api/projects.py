"""
api/projects.py — Power-system project CRUD router.

Exposes the following endpoints under the ``/api/v1/projects`` prefix:

* ``POST /``                       — Create a new project
* ``GET /``                        — List projects (paginated, filterable by status)
* ``GET /{project_id}``            — Get a single project by ID
* ``PUT /{project_id}``            — Update a project
* ``DELETE /{project_id}``         — Soft-delete a project
* ``POST /{project_id}/studies``   — Run a study on a saved project config
* ``GET /{project_id}/studies``    — List study results for a project

All mutating endpoints require a valid JWT. Listing and reading endpoints
accept either a JWT or a valid ``X-API-Key`` header.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

UTC = timezone.utc  # noqa: UP017

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base
from compat import StrEnum

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProjectStatus(StrEnum):
    """Allowed values for project status."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class StudyType(StrEnum):
    """Supported power-system study types."""

    LOAD_FLOW = "load_flow"
    SHORT_CIRCUIT = "short_circuit"
    ARC_FLASH = "arc_flash"
    HARMONIC = "harmonic"
    MOTOR_STARTING = "motor_starting"
    PROTECTION_COORDINATION = "protection_coordination"
    OPTIMAL_POWER_FLOW = "optimal_power_flow"
    STABILITY = "stability"


class StudyStatus(StrEnum):
    """Execution status of a study run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# SQLAlchemy ORM models
# ---------------------------------------------------------------------------


class Project(Base):
    """Persisted power-system project."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    system_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=ProjectStatus.ACTIVE.value)


class StudyResult(Base):
    """Persisted study result linked to a project."""

    __tablename__ = "study_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    study_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=StudyStatus.PENDING.value)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)


# ---------------------------------------------------------------------------
# Pydantic v2 schemas — Projects
# ---------------------------------------------------------------------------


class ProjectCreateRequest(BaseModel):
    """Payload for ``POST /api/v1/projects``."""

    model_config = ConfigDict(strict=False)

    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    system_config: Optional[dict[str, Any]] = None


class ProjectUpdateRequest(BaseModel):
    """Payload for ``PUT /api/v1/projects/{project_id}``."""

    model_config = ConfigDict(strict=False)

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    system_config: Optional[dict[str, Any]] = None
    status: Optional[ProjectStatus] = None

    @field_validator("status")
    @classmethod
    def reject_deleted_status(cls, v: Optional[ProjectStatus]) -> Optional[ProjectStatus]:
        """Prevent setting status to 'deleted' via the update endpoint."""
        if v == ProjectStatus.DELETED:
            raise ValueError("Use DELETE endpoint to soft-delete a project")
        return v


class ProjectResponse(BaseModel):
    """Public project representation returned by API endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    system_config: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: str
    status: str


class ProjectListResponse(BaseModel):
    """Paginated project list response."""

    model_config = ConfigDict(from_attributes=True)

    projects: list[ProjectResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Pydantic v2 schemas — Studies
# ---------------------------------------------------------------------------


class StudyRunRequest(BaseModel):
    """Payload for ``POST /api/v1/projects/{project_id}/studies``."""

    model_config = ConfigDict(strict=False)

    study_type: StudyType
    config: Optional[dict[str, Any]] = None


class StudyResultResponse(BaseModel):
    """Public study result representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    study_type: str
    status: str
    config: Optional[dict[str, Any]] = None
    results: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: str


class StudyListResponse(BaseModel):
    """Paginated list of study results for a project."""

    model_config = ConfigDict(from_attributes=True)

    studies: list[StudyResultResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
#
# These endpoints were previously declared in the module docstring but never
# implemented — the router was created with no routes, causing the frontend
# to receive 404 on every /api/v1/projects call. The implementation below
# provides the minimal CRUD surface the React UI needs.
#
# Auth model:
#   - Listing and reading endpoints accept EITHER a JWT Bearer token OR an
#     X-API-Key header. The get_api_key dependency handles this bypass
#     (see api/dependencies.py).
#   - Mutating endpoints (POST/PUT/DELETE) require a valid JWT via the
#     CurrentUser dependency.


try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

from fastapi import Depends, HTTPException, Query, status  # noqa: E402
from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from api.database import get_db  # noqa: E402
from api.dependencies import (  # noqa: E402
    PaginationParams,
    get_api_key,
    pagination_params,
)
from api.auth import CurrentUserDep  # noqa: E402


DbDep = Annotated[AsyncSession, Depends(get_db)]
ApiKeyDep = Annotated[str, Depends(get_api_key)]
UserDep = Annotated[CurrentUserDep, Depends()]


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List projects",
    dependencies=[Depends(get_api_key)],
)
@router.get(
    "/",
    response_model=ProjectListResponse,
    summary="List projects (trailing slash)",
    include_in_schema=False,
    dependencies=[Depends(get_api_key)],
)
async def list_projects(
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    db: DbDep,
    status_filter: Annotated[Optional[ProjectStatus], Query(alias="status", description="Filter by status")] = None,
) -> Any:
    """Return a paginated, filterable list of power-system projects."""
    base_query = select(Project).where(Project.status != ProjectStatus.DELETED)
    if status_filter is not None:
        base_query = base_query.where(Project.status == status_filter.value)

    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    result = await db.execute(
        base_query.order_by(Project.updated_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size),
    )
    projects = result.scalars().all()

    return ProjectListResponse(
        projects=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project (trailing slash)",
    include_in_schema=False,
)
async def create_project(
    body: ProjectCreateRequest,
    db: DbDep,
    user: UserDep,
) -> Any:
    """Create a new power-system project."""
    project = Project(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        system_config=body.system_config,
        status=ProjectStatus.ACTIVE.value,
        created_by=str(user.id),
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get a single project",
    dependencies=[Depends(get_api_key)],
)
async def get_project(
    project_id: str,
    db: DbDep,
) -> Any:
    """Return a single project by ID."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project",
)
async def update_project(
    project_id: str,
    body: ProjectUpdateRequest,
    db: DbDep,
    user: UserDep,
) -> Any:
    """Update a project's name, description, or system config."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    if body.system_config is not None:
        project.system_config = body.system_config
    project.updated_at = datetime.now(UTC)
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a project",
)
async def delete_project(
    project_id: str,
    db: DbDep,
    user: UserDep,
) -> None:
    """Soft-delete a project by setting status to 'deleted'."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    project.status = ProjectStatus.DELETED.value
    project.updated_at = datetime.now(UTC)
    db.add(project)
