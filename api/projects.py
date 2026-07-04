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

import json
import uuid
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import JSON, DateTime, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base, get_db
from api.dependencies import (
    CurrentUser,
    PaginationParams,
    get_api_key,
    get_current_user,
    get_current_user_from_header,
    pagination_params,
)
from compat import StrEnum

# ---------------------------------------------------------------------------
# Combined auth dependency (API key OR JWT)
# ---------------------------------------------------------------------------


async def _require_api_key_or_jwt(
    x_api_key: str = Header(default="", alias="X-API-Key"),
    authorization: str = Header(default="", alias="Authorization"),
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> str:
    """Allow authentication via EITHER a valid X-API-Key OR a Bearer JWT.

    .. note::
       The ``API_KEY`` value is read **dynamically** from
       ``api.dependencies`` at request time (not at module import). This
       allows tests to patch ``api.dependencies.API_KEY`` and have the
       change take effect immediately — see
       ``tests/test_security_e2e.py::TestAPIKeyBypass``.
    """
    import hmac

    # Re-read API_KEY from the source module so test patches take effect.
    from api import dependencies as _dep

    _api_key = _dep.API_KEY

    # Try API key first
    if _api_key and x_api_key and hmac.compare_digest(x_api_key, _api_key):
        return "api_key"
    # Then try JWT
    if authorization:
        try:
            await get_current_user(db=db, authorization=authorization)
            return "jwt"
        except HTTPException:
            pass
    if not _api_key:
        return "dev"
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


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
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    system_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)


# ---------------------------------------------------------------------------
# Pydantic v2 schemas — Projects
# ---------------------------------------------------------------------------


class ProjectCreateRequest(BaseModel):
    """Payload for ``POST /api/v1/projects``."""

    model_config = ConfigDict(strict=False)

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    system_config: dict[str, Any] | None = None


class ProjectUpdateRequest(BaseModel):
    """Payload for ``PUT /api/v1/projects/{project_id}``."""

    model_config = ConfigDict(strict=False)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    system_config: dict[str, Any] | None = None
    status: ProjectStatus | None = None

    @field_validator("status")
    @classmethod
    def reject_deleted_status(cls, v: ProjectStatus | None) -> ProjectStatus | None:
        """Prevent setting status to 'deleted' via the update endpoint."""
        if v == ProjectStatus.DELETED:
            raise ValueError("Use DELETE endpoint to soft-delete a project")
        return v


class ProjectResponse(BaseModel):
    """Public project representation returned by API endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    system_config: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
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
    config: dict[str, Any] | None = None


class StudyResultResponse(BaseModel):
    """Public study result representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    study_type: str
    status: str
    config: dict[str, Any] | None = None
    results: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
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
# Endpoints — Projects CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
    dependencies=[Depends(get_api_key)],  # enforce X-API-Key when API_KEY is configured
)
async def create_project(
    body: ProjectCreateRequest,
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Create a new power-system project.

    The authenticated user is recorded as the project creator.
    """
    project = Project(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        system_config=body.system_config,
        created_by=user.user_id,
        status=ProjectStatus.ACTIVE.value,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)

    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        system_config=project.system_config,
        created_at=project.created_at,
        updated_at=project.updated_at,
        created_by=project.created_by,
        status=project.status,
    )


@router.get(
    "/",
    response_model=ProjectListResponse,
    summary="List projects",
    dependencies=[Depends(get_api_key)],  # enforce X-API-Key when API_KEY is configured
)
async def list_projects(
    status_filter: ProjectStatus | None = None,
    pagination: PaginationParams = Depends(pagination_params),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    auth: str = Depends(_require_api_key_or_jwt),
) -> Any:
    """Return a paginated list of projects.

    Results can be filtered by status. If no filter is given, only
    non-deleted projects are returned.
    """
    base_query = select(Project)

    if status_filter is not None:
        base_query = base_query.where(Project.status == status_filter.value)
    else:
        # By default exclude soft-deleted projects
        base_query = base_query.where(Project.status != ProjectStatus.DELETED.value)

    # Total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Paginated results
    result = await db.execute(
        base_query.order_by(Project.updated_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size),
    )
    projects = result.scalars().all()

    return ProjectListResponse(
        projects=[
            ProjectResponse(
                id=str(p.id),
                name=p.name,
                description=p.description,
                system_config=p.system_config,
                created_at=p.created_at,
                updated_at=p.updated_at,
                created_by=p.created_by,
                status=p.status,
            )
            for p in projects
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project by ID",
    dependencies=[Depends(get_api_key)],  # enforce X-API-Key when API_KEY is configured
)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    auth: str = Depends(_require_api_key_or_jwt),
) -> Any:
    """Retrieve a single project by its UUID."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",  # NOSONAR — S1192: intentional repetition (audit constant)
        )

    if project.status == ProjectStatus.DELETED.value:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Project has been deleted",  # NOSONAR — S1192: intentional repetition (audit constant)
        )

    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        system_config=project.system_config,
        created_at=project.created_at,
        updated_at=project.updated_at,
        created_by=project.created_by,
        status=project.status,
    )


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project",
    dependencies=[Depends(get_api_key)],  # enforce X-API-Key when API_KEY is configured
)
async def update_project(
    project_id: str,
    body: ProjectUpdateRequest,
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Update one or more fields of an existing project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if project.status == ProjectStatus.DELETED.value:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Project has been deleted",
        )

    # Apply updates
    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    if body.system_config is not None:
        project.system_config = body.system_config
    if body.status is not None:
        project.status = body.status.value

    project.updated_at = datetime.now(UTC)
    db.add(project)
    await db.flush()
    await db.refresh(project)

    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        system_config=project.system_config,
        created_at=project.created_at,
        updated_at=project.updated_at,
        created_by=project.created_by,
        status=project.status,
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="Soft-delete a project",
    dependencies=[Depends(get_api_key)],  # enforce X-API-Key when API_KEY is configured
)
async def delete_project(
    project_id: str,
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    """Soft-delete a project by setting its status to ``deleted``."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if project.status == ProjectStatus.DELETED.value:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Project has already been deleted",
        )

    project.status = ProjectStatus.DELETED.value
    project.updated_at = datetime.now(UTC)
    db.add(project)
    await db.flush()

    return {"message": "Project has been soft-deleted"}


# ---------------------------------------------------------------------------
# Endpoints — Studies
# ---------------------------------------------------------------------------


@router.post(
    "/{project_id}/studies",
    response_model=StudyResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run a study on a saved project config",
    dependencies=[Depends(get_api_key)],  # enforce X-API-Key when API_KEY is configured
)
async def run_study(
    project_id: str,
    body: StudyRunRequest,
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Queue a study run against the project's saved configuration.

    The study is created in ``pending`` status. In a production
    deployment this would enqueue a background job. For now, we
    attempt to execute it inline using the PowerSystemEngine.
    """
    # Verify project exists and is not deleted
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if project.status == ProjectStatus.DELETED.value:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Project has been deleted",
        )

    # Merge project config with per-study config overrides
    merged_config: dict[str, Any] = {}
    if project.system_config:
        merged_config.update(project.system_config)
    if body.config:
        merged_config.update(body.config)

    # Create the study result record
    study = StudyResult(
        id=str(uuid.uuid4()),
        project_id=project_id,
        study_type=body.study_type.value,
        status=StudyStatus.PENDING.value,
        config=merged_config,
        created_by=user.user_id,
    )
    db.add(study)
    await db.flush()

    # Attempt to run the study inline via the engine
    study.status = StudyStatus.RUNNING.value
    db.add(study)
    await db.flush()

    try:
        study_results = _execute_study(
            study_type=body.study_type.value,
            config=merged_config,
        )
        study.results = study_results
        study.status = StudyStatus.COMPLETED.value
        study.completed_at = datetime.now(UTC)
    except Exception as exc:
        study.status = StudyStatus.FAILED.value
        study.error_message = str(exc)[:2000]
        study.completed_at = datetime.now(UTC)

    db.add(study)
    await db.flush()
    await db.refresh(study)

    return StudyResultResponse(
        id=str(study.id),
        project_id=study.project_id,
        study_type=study.study_type,
        status=study.status,
        config=study.config,
        results=study.results,
        error_message=study.error_message,
        created_at=study.created_at,
        completed_at=study.completed_at,
        created_by=study.created_by,
    )


@router.get(
    "/{project_id}/studies",
    response_model=StudyListResponse,
    summary="List study results for a project (paginated)",
    dependencies=[Depends(get_api_key)],  # enforce X-API-Key when API_KEY is configured
)
async def list_studies(
    project_id: str,
    pagination: PaginationParams = Depends(pagination_params),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
) -> Any:
    """Return a paginated list of study results associated with the given project."""
    # Verify project exists
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Total count
    count_query = select(func.count()).select_from(
        select(StudyResult).where(StudyResult.project_id == project_id).subquery(),
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Paginated results
    result = await db.execute(
        select(StudyResult)
        .where(StudyResult.project_id == project_id)
        .order_by(StudyResult.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size),
    )
    studies = result.scalars().all()

    return StudyListResponse(
        studies=[
            StudyResultResponse(
                id=str(s.id),
                project_id=s.project_id,
                study_type=s.study_type,
                status=s.status,
                config=s.config,
                results=s.results,
                error_message=s.error_message,
                created_at=s.created_at,
                completed_at=s.completed_at,
                created_by=s.created_by,
            )
            for s in studies
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


# ---------------------------------------------------------------------------
# Internal study execution helper
# ---------------------------------------------------------------------------


def _execute_study(
    study_type: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Execute a power-system study using the PowerSystemEngine.

    This is a lightweight wrapper that attempts to load and run the
    engine. If the engine is unavailable (e.g., missing dependencies),
    a placeholder result is returned.

    Args:
        study_type: One of the :class:`StudyType` values.
        config: Merged project + per-study configuration dict.

    Returns:
        A dictionary of study results suitable for JSON storage.
    """
    try:
        from core_model.system import System  # type: ignore
        from engine.engine import PowerSystemEngine  # type: ignore

        # Build a system from config if available
        system = System(base_mva=config.get("base_mva", 100.0))
        engine = PowerSystemEngine(system)

        if study_type == StudyType.LOAD_FLOW.value:
            result = engine.run_load_flow()
        elif study_type == StudyType.SHORT_CIRCUIT.value:
            fault_type = config.get("fault_type", "three_phase")
            bus_id = config.get("bus_id", 1)
            result = engine.run_fault_analysis(fault_type, bus_id=bus_id)
        else:
            # For study types without direct engine support, return a
            # placeholder indicating the study was accepted.
            result = {
                "message": f"Study type '{study_type}' accepted",
                "config": config,
                "status": "completed_placeholder",
            }

        # Sanitize numpy types for JSON serialization
        return _sanitize_result(result)

    except Exception as exc:
        # Engine not available or study failed — return a placeholder
        return {
            "message": f"Study execution deferred: {exc!s}",
            "study_type": study_type,
            "config_snapshot": config,
            "status": "deferred",
        }


def _sanitize_result(obj: Any) -> Any:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """Recursively convert numpy types and other non-JSON-serializable
    objects into native Python primitives.
    """
    if obj is None:
        return None
    if isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        import math

        if not math.isfinite(obj):
            return None
        return obj
    if isinstance(obj, complex):
        return {"real": obj.real, "imag": obj.imag}
    if isinstance(obj, dict):
        return {str(k): _sanitize_result(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_result(x) for x in obj]

    # Try numpy types
    try:
        import numpy as np  # type: ignore

        if isinstance(obj, np.ndarray):
            return [_sanitize_result(x) for x in obj.tolist()]
        if isinstance(obj, (np.integer,)):
            return int(obj.item())
        if isinstance(obj, (np.floating,)):
            v = float(obj.item())
            import math

            if not math.isfinite(v):
                return None
            return v
        if isinstance(obj, (np.bool_,)):
            return bool(obj.item())
        if isinstance(obj, np.complexfloating):
            return {"real": float(obj.real), "imag": float(obj.imag)}
    except ImportError:
        pass

    # Fallback
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return str(obj)
