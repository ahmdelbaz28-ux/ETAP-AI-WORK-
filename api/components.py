"""api/components.py — Standardized Component Library Management API.

Provides:
- Component model for catalog items (cables, transformers, breakers, relays, etc.)
- Public read access for verified standard components
- Multi-faceted search and filtering (type, standard, category, tags, specs)
- ETAP .etp/.etpx bulk XML import
- Community submission and maker-checker approval workflow
- Automated seed loading from data/components/

Prefix: /api/v1/components
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

UTC = timezone.utc  # noqa: UP017

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
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

from api.database import Base, get_db
from api.dependencies import (
    CurrentUser,
    PaginationParams,
    get_api_key,
    get_current_user_from_header,
    pagination_params,
)
from integrations.etap_component_importer import etap_importer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------


class Component(Base):
    """A standardized power-system component in the shared catalog."""

    __tablename__ = "components"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # cable, transformer, breaker, relay, template
    category: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    subcategory: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    model_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    specs: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    standards: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    source: Mapped[str] = mapped_column(
        String(50), default="iec-standard"
    )  # iec-standard, ieee-standard, etap-import, user
    contributor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    review_status: Mapped[str] = mapped_column(
        String(30), default="approved", index=True
    )  # approved, pending, rejected
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
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
# Pydantic v2 Schemas
# ---------------------------------------------------------------------------


class ComponentContributeRequest(BaseModel):
    """Payload for community component submission."""

    model_config = ConfigDict(strict=False)

    type: str = Field(min_length=1, max_length=50)
    category: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9\s\-_/]+$")
    subcategory: Optional[str] = Field(
        default=None, max_length=128, pattern=r"^[a-zA-Z0-9\s\-_/]+$"
    )
    name: str = Field(min_length=1, max_length=255)
    manufacturer: Optional[str] = Field(default=None, max_length=255)
    model_number: Optional[str] = Field(default=None, max_length=255)
    specs: Dict[str, Any] = Field(default_factory=dict)
    standards: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    contributor_notes: Optional[str] = Field(default=None, max_length=2000)


class ComponentVerifyRequest(BaseModel):
    """Payload for verifying a pending submission."""

    notes: Optional[str] = Field(default=None, max_length=1000)


class ComponentRejectRequest(BaseModel):
    """Payload for rejecting a pending submission."""

    reason: str = Field(min_length=1, max_length=1000)


class ComponentResponse(BaseModel):
    """Public component representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    category: str
    subcategory: Optional[str] = None
    name: str
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    specs: Optional[Dict[str, Any]] = None
    standards: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    is_verified: bool
    source: str
    contributor_id: Optional[str] = None
    tenant_id: Optional[str] = None
    review_status: str
    review_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ComponentListResponse(BaseModel):
    """Paginated component list response."""

    model_config = ConfigDict(from_attributes=True)

    components: List[ComponentResponse]
    total: int
    page: int
    page_size: int


class TypeCountResponse(BaseModel):
    type: str
    count: int


class StandardCountResponse(BaseModel):
    standard: str
    count: int


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/v1/components",
    tags=["Component Library"],
    dependencies=[Depends(get_api_key)],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_component_by_id(db: AsyncSession, component_id: str) -> Component:
    result = await db.execute(select(Component).where(Component.id == component_id))
    component = result.scalar_one_or_none()
    if component is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Component not found: {component_id}",
        )
    return component


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ComponentListResponse,
    summary="List components with multi-faceted filtering",
)
@router.get("/", include_in_schema=False, response_model=ComponentListResponse)
async def list_components(
    pagination: PaginationParams = Depends(pagination_params),
    type: Optional[str] = Query(
        None, description="Filter by type (cable, transformer, breaker, relay, template)"
    ),
    category: Optional[str] = Query(None, description="Filter by category"),
    standard: Optional[str] = Query(
        None, description="Filter by standard (e.g. IEC 60364, IEEE C57)"
    ),
    manufacturer: Optional[str] = Query(None, description="Filter by manufacturer"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(
        None, description="Search name, manufacturer, model, subcategory"
    ),
    verified: Optional[bool] = Query(
        None, description="Filter by verification status (default: true)"
    ),
    db: AsyncSession = Depends(get_db),
) -> ComponentListResponse:
    """Retrieve paginated components matching query criteria.

    Defaults to verified components (public catalog) unless verified=false is explicitly requested.
    """
    query = select(Component)
    count_query = select(func.count(Component.id))

    filters = []

    # Default to verified components unless explicitly queried
    if verified is not None:
        filters.append(Component.is_verified == verified)
    else:
        # Show verified or approved components
        filters.append(or_(Component.is_verified.is_(True), Component.review_status == "approved"))

    if type:
        filters.append(func.lower(Component.type) == type.strip().lower())

    if category:
        filters.append(func.lower(Component.category).contains(category.strip().lower()))

    if manufacturer:
        filters.append(func.lower(Component.manufacturer).contains(manufacturer.strip().lower()))

    if search:
        s = f"%{search.strip().lower()}%"
        filters.append(
            or_(
                func.lower(Component.name).like(s),
                func.lower(Component.manufacturer).like(s),
                func.lower(Component.model_number).like(s),
                func.lower(Component.subcategory).like(s),
                func.lower(Component.category).like(s),
            )
        )
    if standard:
        from sqlalchemy import cast

        filters.append(cast(Component.standards, String).ilike(f"%{standard.strip()}%"))

    if tag:
        from sqlalchemy import cast

        filters.append(cast(Component.tags, String).ilike(f"%{tag.strip()}%"))

    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    # Total count
    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    # Paginated results
    query = (
        query.order_by(Component.type.asc(), Component.name.asc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    result = await db.execute(query)
    items = list(result.scalars().all())

    return ComponentListResponse(
        components=[ComponentResponse.model_validate(item) for item in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/types",
    response_model=List[TypeCountResponse],
    summary="Available component types with counts",
)
async def get_component_types(db: AsyncSession = Depends(get_db)) -> List[TypeCountResponse]:
    """Return available component types with item counts."""
    stmt = (
        select(Component.type, func.count(Component.id))
        .where(Component.is_verified.is_(True))
        .group_by(Component.type)
        .order_by(func.count(Component.id).desc())
    )
    res = await db.execute(stmt)
    return [TypeCountResponse(type=row[0], count=row[1]) for row in res.fetchall()]


@router.get(
    "/standards",
    response_model=List[StandardCountResponse],
    summary="Available standards with counts",
)
async def get_component_standards(
    db: AsyncSession = Depends(get_db),
) -> List[StandardCountResponse]:
    """Return standards referenced across components with occurrence counts."""
    result = await db.execute(select(Component.standards).where(Component.is_verified.is_(True)))
    counts: dict[str, int] = {}
    for (standards,) in result.fetchall():
        if isinstance(standards, list):
            for s in standards:
                std_clean = str(s).strip()
                counts[std_clean] = counts.get(std_clean, 0) + 1
    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [StandardCountResponse(standard=k, count=v) for k, v in sorted_items]


@router.get(
    "/pending",
    response_model=List[ComponentResponse],
    summary="List unverified community submissions",
)
async def list_pending_components(
    user: CurrentUser = Depends(get_current_user_from_header),
    db: AsyncSession = Depends(get_db),
) -> List[ComponentResponse]:
    """Admin queue for unverified community submissions."""
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")

    stmt = (
        select(Component)
        .where(Component.review_status == "pending")
        .order_by(Component.created_at.desc())
    )

    # Add tenant filtering for non-platform admins
    if user.tenant_id and not getattr(user, "is_platform_admin", False):
        stmt = stmt.where(Component.tenant_id == user.tenant_id)

    res = await db.execute(stmt)
    return [ComponentResponse.model_validate(c) for c in res.scalars().all()]


@router.get("/{id}", response_model=ComponentResponse, summary="Get component details")
async def get_component(id: str, db: AsyncSession = Depends(get_db)) -> ComponentResponse:
    """Retrieve detailed specifications for a single component."""
    comp = await _get_component_by_id(db, id)
    return ComponentResponse.model_validate(comp)


@router.post(
    "/contribute",
    response_model=ComponentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Contribute component",
)
async def contribute_component(
    payload: ComponentContributeRequest,
    user: CurrentUser = Depends(get_current_user_from_header),
    db: AsyncSession = Depends(get_db),
) -> ComponentResponse:
    """Submit a component to the community library. Creates an unverified item in 'pending' status."""
    comp_id = f"{payload.type.lower()}-contrib-{uuid.uuid4().hex[:10]}"
    comp = Component(
        id=comp_id,
        type=payload.type.lower().strip(),
        category=payload.category.strip(),
        subcategory=payload.subcategory.strip() if payload.subcategory else None,
        name=payload.name.strip(),
        manufacturer=payload.manufacturer.strip() if payload.manufacturer else None,
        model_number=payload.model_number.strip() if payload.model_number else None,
        specs=payload.specs,
        standards=payload.standards,
        tags=payload.tags,
        is_verified=False,
        source="user",
        contributor_id=user.user_id,
        tenant_id=user.tenant_id,
        review_status="pending",
        review_notes=payload.contributor_notes,
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    logger.info("Component contributed by user %s: %s (%s)", user.user_id, comp.name, comp.id)
    return ComponentResponse.model_validate(comp)


@router.put(
    "/{id}/verify", response_model=ComponentResponse, summary="Approve and verify component (admin)"
)
@router.post("/{id}/verify", response_model=ComponentResponse, include_in_schema=False)
async def verify_component(
    id: str,
    payload: ComponentVerifyRequest,
    user: CurrentUser = Depends(get_current_user_from_header),
    db: AsyncSession = Depends(get_db),
) -> ComponentResponse:
    """Admin action to approve and verify a contributed component."""
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")

    comp = await _get_component_by_id(db, id)
    comp.is_verified = True
    comp.review_status = "approved"
    comp.reviewed_by = user.user_id
    comp.reviewed_at = datetime.now(UTC)
    if payload.notes:
        comp.review_notes = payload.notes
    await db.commit()
    await db.refresh(comp)
    logger.info("Component %s approved by admin %s", id, user.user_id)
    return ComponentResponse.model_validate(comp)


@router.put(
    "/{id}/reject", response_model=ComponentResponse, summary="Reject component submission (admin)"
)
@router.post("/{id}/reject", response_model=ComponentResponse, include_in_schema=False)
async def reject_component(
    id: str,
    payload: ComponentRejectRequest,
    user: CurrentUser = Depends(get_current_user_from_header),
    db: AsyncSession = Depends(get_db),
) -> ComponentResponse:
    """Admin action to reject a submitted component with explanation notes."""
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")

    comp = await _get_component_by_id(db, id)
    comp.is_verified = False
    comp.review_status = "rejected"
    comp.review_notes = payload.reason
    comp.reviewed_by = user.user_id
    comp.reviewed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(comp)
    logger.info("Component %s rejected by admin %s: %s", id, user.user_id, payload.reason)
    return ComponentResponse.model_validate(comp)


@router.post(
    "/import/etap",
    response_model=List[ComponentResponse],
    summary="Bulk import components from ETAP .etp XML",
)
async def import_etap_components(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user_from_header),
    db: AsyncSession = Depends(get_db),
) -> List[ComponentResponse]:
    """Extract and bulk-create standardized component definitions from an ETAP project XML file."""
    if user.role not in ("admin", "engineer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Engineer or admin role required"
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        extracted = etap_importer.parse_xml_content(content)
    except ValueError as e:
        logger.warning("Failed to parse ETAP XML content: %s", e)
        raise HTTPException(status_code=400, detail="Invalid ETAP XML format") from e

    created_components: List[Component] = []
    for item in extracted:
        comp = Component(
            id=item["id"],
            type=item["type"],
            category=item["category"],
            subcategory=item.get("subcategory"),
            name=item["name"],
            manufacturer=item.get("manufacturer"),
            model_number=item.get("model_number"),
            specs=item.get("specs"),
            standards=item.get("standards"),
            tags=item.get("tags"),
            is_verified=True,
            source=item.get("source", "etap-import"),
            contributor_id=user.user_id,
            tenant_id=user.tenant_id,
            review_status="approved",
        )
        db.add(comp)
        created_components.append(comp)

    await db.commit()
    for c in created_components:
        await db.refresh(c)

    logger.info("Imported %d components from ETAP file %s", len(created_components), file.filename)
    return [ComponentResponse.model_validate(c) for c in created_components]


@router.post(
    "/import/json",
    response_model=List[ComponentResponse],
    summary="Bulk import components from JSON",
)
async def import_json_components(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user_from_header),
    db: AsyncSession = Depends(get_db),
) -> List[ComponentResponse]:
    """Bulk-import component definitions from a JSON list payload."""
    if user.role not in ("admin", "engineer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Engineer or admin role required"
        )

    content = await file.read()
    try:
        data = json.loads(content.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e

    items = data if isinstance(data, list) else data.get("components", [])
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="Expected JSON array of components")

    created: List[Component] = []
    for item in items:
        cid = str(uuid.uuid4())
        comp = Component(
            id=cid,
            type=item.get("type", "other"),
            category=item.get("category", "General"),
            subcategory=item.get("subcategory"),
            name=item.get("name", "Unnamed Component"),
            manufacturer=item.get("manufacturer"),
            model_number=item.get("model_number"),
            specs=item.get("specs"),
            standards=item.get("standards", []),
            tags=item.get("tags", []),
            is_verified=item.get("is_verified", False),
            source=item.get("source", "user"),
            contributor_id=user.user_id,
            tenant_id=user.tenant_id,
            review_status="approved" if user.role == "admin" else "pending",
        )
        db.add(comp)
        created.append(comp)

    await db.commit()
    for c in created:
        await db.refresh(c)

    return [ComponentResponse.model_validate(c) for c in created]


# ---------------------------------------------------------------------------
# Seed Data Loader
# ---------------------------------------------------------------------------


async def ensure_seed_data(db: AsyncSession) -> None:
    """Ensure standard seed components exist in database."""
    count_stmt = select(func.count(Component.id))
    res = await db.execute(count_stmt)
    count = res.scalar() or 0
    if count > 0:
        return

    base_dir = Path(__file__).resolve().parent.parent / "data" / "components"
    if not base_dir.exists():
        return

    json_files = list(base_dir.rglob("*.json"))
    loaded = 0
    for p in json_files:
        if p.name in ("index.json", "schema.json"):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                item = json.load(f)
            if not isinstance(item, dict) or "type" not in item or "name" not in item:
                continue

            comp = Component(
                id=item.get("id", str(uuid.uuid4())),
                type=item["type"],
                category=item.get("category", "Standard"),
                subcategory=item.get("subcategory"),
                name=item["name"],
                manufacturer=item.get("manufacturer"),
                model_number=item.get("model_number"),
                specs=item.get("specs"),
                standards=item.get("standards", []),
                tags=item.get("tags", []),
                is_verified=item.get("is_verified", True),
                source=item.get("source", "iec-standard"),
                contributor_id="system-seed",
                review_status="approved",
            )
            db.add(comp)
            loaded += 1
        except Exception as err:
            logger.warning("Failed to load seed component from %s: %s", p, err)

    if loaded > 0:
        await db.commit()
        logger.info("Loaded %d standardized seed components into database", loaded)
