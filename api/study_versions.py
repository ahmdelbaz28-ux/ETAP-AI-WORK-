"""
api/study_versions.py — Version Control for Studies.

Provides:
- StudyVersion model with diff tracking
- Rollback capabilities
- Side-by-side comparison API
- Changelog tracking

Exposes endpoints under ``/api/v1/studies/{study_id}/versions``:
* ``GET  /``                    — List versions
* ``POST /``                    — Create version (snapshot)
* ``GET  /{version_id}``        — Get version details
* ``POST /{version_id}/rollback`` — Rollback to version
* ``GET  /{v1}/compare/{v2}``   — Compare two versions
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

UTC = timezone.utc

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    DateTime, Integer, String, Text, JSON,
    select, func, desc,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base, get_db
from api.dependencies import (
    CurrentUser,
    get_current_user_from_header,
    pagination_params,
    PaginationParams,
)
from api.rbac import require_permission


class StudyVersion(Base):
    """A snapshot of a study at a point in time."""

    __tablename__ = "study_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    study_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)  # Full study config at this version
    results_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Results at this version
    diff_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # What changed
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )


class VersionCreateRequest(BaseModel):
    label: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    study_id: str
    project_id: str
    version_number: int
    label: Optional[str] = None
    description: Optional[str] = None
    config_snapshot: Optional[dict] = None
    diff_summary: Optional[str] = None
    created_by: str = ""
    created_at: Optional[datetime] = None


class VersionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    versions: list[VersionResponse]
    total: int


class CompareResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    version_a: VersionResponse
    version_b: VersionResponse
    config_diff: dict[str, Any]
    results_diff: Optional[dict[str, Any]] = None


router = APIRouter(prefix="/api/v1/projects", tags=["Study Versions"])


async def _get_study_result(project_id: str, study_id: str, db: AsyncSession) -> Any:
    """Get study result from database."""
    from api.projects import StudyResult
    result = await db.execute(
        select(StudyResult).where(
            StudyResult.id == study_id,
            StudyResult.project_id == project_id,
        )
    )
    study = result.scalar_one_or_none()
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")
    return study


@router.get("/{project_id}/studies/{study_id}/versions", response_model=VersionListResponse)
async def list_versions(
    project_id: str, study_id: str, db, 
    user: CurrentUser = Depends(get_current_user_from_header),
):
    """List all versions for a study."""
    result = await db.execute(
        select(StudyVersion)
        .where(
            StudyVersion.study_id == study_id,
            StudyVersion.project_id == project_id,
        )
        .order_by(desc(StudyVersion.version_number))
    )
    versions = result.scalars().all()
    return VersionListResponse(
        versions=[VersionResponse(
            id=str(v.id),
            study_id=v.study_id,
            project_id=v.project_id,
            version_number=v.version_number,
            label=v.label,
            description=v.description,
            diff_summary=v.diff_summary,
            created_by=v.created_by,
            created_at=v.created_at,
        ) for v in versions],
        total=len(versions),
    )


@router.post("/{project_id}/studies/{study_id}/versions", response_model=VersionResponse, status_code=201)
async def create_version(
    project_id: str, study_id: str, body: VersionCreateRequest, db,
    user: CurrentUser = Depends(require_permission("studies", "update")),
):
    """Create a new version snapshot of a study."""
    study = await _get_study_result(project_id, study_id, db)

    # Get current version count
    count_result = await db.execute(
        select(func.count()).select_from(StudyVersion).where(
            StudyVersion.study_id == study_id
        )
    )
    version_number = count_result.scalar_one() + 1

    version = StudyVersion(
        id=str(uuid.uuid4()),
        study_id=study_id,
        project_id=project_id,
        version_number=version_number,
        label=body.label or f"Version {version_number}",
        description=body.description,
        config_snapshot=study.config or {},
        results_snapshot=study.results,
        created_by=user.user_id,
    )
    db.add(version)
    await db.flush()
    await db.refresh(version)

    return VersionResponse(
        id=str(version.id),
        study_id=version.study_id,
        project_id=version.project_id,
        version_number=version.version_number,
        label=version.label,
        description=version.description,
        created_by=version.created_by,
        created_at=version.created_at,
    )


@router.post("/{project_id}/studies/{study_id}/versions/{version_id}/rollback", response_model=dict)
async def rollback_version(
    project_id: str, study_id: str, version_id: str, db,
    user: CurrentUser = Depends(require_permission("studies", "update")),
):
    """Rollback a study to a specific version."""
    from api.projects import StudyResult

    result = await db.execute(
        select(StudyVersion).where(
            StudyVersion.id == version_id,
            StudyVersion.study_id == study_id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")

    study = await _get_study_result(project_id, study_id, db)
    study.config = version.config_snapshot
    study.results = version.results_snapshot
    db.add(study)
    await db.flush()

    return {"message": f"Study rolled back to version {version.version_number}", "version": version.version_number}


@router.get("/{project_id}/studies/{study_id}/versions/{v1}/compare/{v2}", response_model=CompareResponse)
async def compare_versions(
    project_id: str, study_id: str, v1: str, v2: str, db,
    user: CurrentUser = Depends(require_permission("studies", "read")),
):
    """Compare two versions of a study."""
    result_a = await db.execute(
        select(StudyVersion).where(StudyVersion.id == v1, StudyVersion.study_id == study_id)
    )
    result_b = await db.execute(
        select(StudyVersion).where(StudyVersion.id == v2, StudyVersion.study_id == study_id)
    )
    va = result_a.scalar_one_or_none()
    vb = result_b.scalar_one_or_none()
    if not va or not vb:
        raise HTTPException(status_code=404, detail="Version not found")

    def compute_diff(a: dict, b: dict) -> dict:
        diff = {}
        all_keys = set(a.keys()) | set(b.keys())
        for key in all_keys:
            av = json.dumps(a.get(key), default=str, sort_keys=True)
            bv = json.dumps(b.get(key), default=str, sort_keys=True)
            if av != bv:
                diff[key] = {"from": a.get(key), "to": b.get(key)}
        return diff

    return CompareResponse(
        version_a=VersionResponse(
            id=str(va.id), study_id=va.study_id, project_id=va.project_id,
            version_number=va.version_number, label=va.label, description=va.description,
            created_by=va.created_by, created_at=va.created_at,
        ),
        version_b=VersionResponse(
            id=str(vb.id), study_id=vb.study_id, project_id=vb.project_id,
            version_number=vb.version_number, label=vb.label, description=vb.description,
            created_by=vb.created_by, created_at=vb.created_at,
        ),
        config_diff=compute_diff(va.config_snapshot, vb.config_snapshot),
        results_diff=compute_diff(va.results_snapshot or {}, vb.results_snapshot or {}),
    )