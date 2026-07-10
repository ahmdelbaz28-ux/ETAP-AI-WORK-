"""
api/templates.py — Study Templates Management.

Provides:
- StudyTemplate model with pre-configured parameters
- Template categories
- CRUD endpoints for template management

Exposes endpoints under ``/api/v1/templates``:
* ``GET  /``                    — List templates (filterable)
* ``POST /``                    — Create template
* ``GET  /{template_id}``       — Get template details
* ``PUT  /{template_id}``       — Update template
* ``DELETE /{template_id}``     — Delete template
* ``POST /{template_id}/apply`` — Apply template to a study
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

UTC = UTC

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    String,
    Text,
    and_,
    func,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base
from api.dependencies import (
    CurrentUser,
    PaginationParams,
    get_current_user_from_header,
    pagination_params,
)
from api.rbac import require_permission


class StudyTemplate(Base):
    """A pre-configured study template."""

    __tablename__ = "study_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    study_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    system_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    usage_count: Mapped[int] = mapped_column(default=0)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class TemplateCreateRequest(BaseModel):
    model_config = ConfigDict(strict=False)
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    study_type: str = Field(min_length=1, max_length=64)
    parameters: dict[str, Any] = Field(default_factory=dict)
    system_config: Optional[dict[str, Any]] = None
    tags: Optional[list[str]] = None
    is_public: bool = False


class TemplateUpdateRequest(BaseModel):
    model_config = ConfigDict(strict=False)
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    study_type: Optional[str] = Field(default=None, min_length=1, max_length=64)
    parameters: Optional[dict[str, Any]] = None
    system_config: Optional[dict[str, Any]] = None
    tags: Optional[list[str]] = None
    is_public: Optional[bool] = None


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: Optional[str] = None
    study_type: str
    parameters: Optional[dict] = None
    system_config: Optional[dict] = None
    tags: Optional[list] = None
    is_public: bool = False
    usage_count: int = 0
    created_by: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TemplateListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    templates: list[TemplateResponse]
    total: int
    page: int
    page_size: int


router = APIRouter(prefix="/api/v1/templates", tags=["Study Templates"])


async def _get_template(template_id: str, db: AsyncSession) -> StudyTemplate:
    result = await db.execute(select(StudyTemplate).where(StudyTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.get("/", response_model=TemplateListResponse)
async def list_templates(
    db,
    user: CurrentUser = Depends(require_permission("templates", "list")),
    pagination: PaginationParams = Depends(pagination_params),
    study_type: Optional[str] = None,
    search: Optional[str] = None,
):
    filters = or_(StudyTemplate.is_public == True, StudyTemplate.created_by == user.user_id)
    if study_type:
        filters = and_(filters, StudyTemplate.study_type == study_type)
    if search:
        filters = and_(filters, StudyTemplate.name.ilike(f"%{search}%"))

    count = await db.execute(select(func.count()).select_from(StudyTemplate).where(filters))
    total = count.scalar_one()
    result = await db.execute(
        select(StudyTemplate).where(filters).order_by(StudyTemplate.usage_count.desc())
        .offset(pagination.offset).limit(pagination.page_size)
    )
    templates = result.scalars().all()
    return TemplateListResponse(
        templates=[TemplateResponse(
            id=str(t.id), name=t.name, description=t.description, study_type=t.study_type,
            parameters=t.parameters, system_config=t.system_config, tags=t.tags,
            is_public=t.is_public, usage_count=t.usage_count, created_by=t.created_by,
            created_at=t.created_at, updated_at=t.updated_at,
        ) for t in templates],
        total=total, page=pagination.page, page_size=pagination.page_size,
    )


@router.post("/", response_model=TemplateResponse, status_code=201)
async def create_template(
    body: TemplateCreateRequest, db,
    user: CurrentUser = Depends(require_permission("templates", "create")),
):
    template = StudyTemplate(
        id=str(uuid.uuid4()), name=body.name, description=body.description,
        study_type=body.study_type, parameters=body.parameters,
        system_config=body.system_config, tags=body.tags, is_public=body.is_public,
        created_by=user.user_id,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return TemplateResponse(
        id=str(template.id), name=template.name, description=template.description,
        study_type=template.study_type, parameters=template.parameters,
        system_config=template.system_config, tags=template.tags,
        is_public=template.is_public, usage_count=0, created_by=template.created_by,
        created_at=template.created_at, updated_at=template.updated_at,
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str, db, user: CurrentUser = Depends(get_current_user_from_header)):
    template = await _get_template(template_id, db)
    return TemplateResponse(
        id=str(template.id), name=template.name, description=template.description,
        study_type=template.study_type, parameters=template.parameters,
        system_config=template.system_config, tags=template.tags,
        is_public=template.is_public, usage_count=template.usage_count,
        created_by=template.created_by, created_at=template.created_at, updated_at=template.updated_at,
    )


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str, body: TemplateUpdateRequest, db,
    user: CurrentUser = Depends(require_permission("templates", "update")),
):
    template = await _get_template(template_id, db)
    if body.name is not None:
        template.name = body.name
    if body.description is not None:
        template.description = body.description
    if body.study_type is not None:
        template.study_type = body.study_type
    if body.parameters is not None:
        template.parameters = body.parameters
    if body.system_config is not None:
        template.system_config = body.system_config
    if body.tags is not None:
        template.tags = body.tags
    if body.is_public is not None:
        template.is_public = body.is_public
    template.updated_at = datetime.now(UTC)
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return TemplateResponse(
        id=str(template.id), name=template.name, description=template.description,
        study_type=template.study_type, parameters=template.parameters,
        system_config=template.system_config, tags=template.tags,
        is_public=template.is_public, usage_count=template.usage_count,
        created_by=template.created_by, created_at=template.created_at, updated_at=template.updated_at,
    )


@router.delete("/{template_id}")
async def delete_template(
    template_id: str, db,
    user: CurrentUser = Depends(require_permission("templates", "delete")),
):
    template = await _get_template(template_id, db)
    await db.delete(template)
    await db.flush()
    return {"message": f"Template '{template.name}' deleted successfully"}


@router.post("/{template_id}/apply")
async def apply_template(
    template_id: str, db,
    project_id: Optional[str] = None,
    user: CurrentUser = Depends(require_permission("templates", "update")),
):
    template = await _get_template(template_id, db)
    template.usage_count += 1
    db.add(template)
    await db.flush()
    return {
        "message": "Template applied successfully",
        "study_type": template.study_type,
        "parameters": template.parameters,
        "system_config": template.system_config,
    }
