"""
api/storage_management.py — Storage management API for R2 object lifecycle.

Provides endpoints for monitoring storage usage, purging temporary/old files,
and managing retention policies for the Cloudflare R2 bucket.

Endpoints (under ``/api/v1/storage``):
* ``GET  /metrics``              — storage usage metrics (total objects, sizes, by prefix)
* ``POST /purge``                — purge temporary files (prefix filter, age filter, dry_run)
* ``GET  /retention``            — get current retention policy
* ``PUT  /retention``            — update retention policy (days, auto_purge_enabled)
* ``DELETE /artifacts/cad``      — clear temporary CAD artifacts specifically

All endpoints require a valid API key (X-API-Key) or JWT Bearer token.

Safety:
    - The ``POST /purge`` endpoint defaults to ``dry_run=true`` so that
      accidental calls without ``dry_run=false`` will NOT delete anything.
    - Large purges (>100 objects) require an explicit ``confirm=true`` flag
      in addition to ``dry_run=false`` to prevent accidental mass deletion.
    - All operations are logged at INFO level for audit purposes.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any, Optional

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import get_api_key
from api.r2_storage import (
    delete_many,
    is_r2_enabled,
    list_objects,
)

# SECURITY: S5145 - strip control characters from user-controlled values
# before they reach the logger. Prevents log injection / CRLF spoofing.
# Mirrors the helper in api/copilot_config.py (SonarCloud S5145 batch 5).
_SAFE_LOG_RE = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_for_log(value: object, max_len: int = 200) -> str:
    """Sanitize user-controlled input before writing to logs.

    Strips control characters and truncates to prevent log-flooding / injection.
    """
    if value is None:
        return "None"
    s = _SAFE_LOG_RE.sub("_", str(value))
    if len(s) > max_len:
        s = s[:max_len] + "...[truncated]"
    return s


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/storage", tags=["storage", "r2"])

# Type alias for FastAPI dependency (SonarCloud S8410)
ApiKeyDep = Annotated[str, Depends(get_api_key)]

# ---------------------------------------------------------------------------
# In-memory retention policy (persisted via env vars or defaults)
# ---------------------------------------------------------------------------

_retention_lock = threading.Lock()

# Default retention policy — can be overridden via env vars
_DEFAULT_RETENTION_DAYS = int(os.getenv("R2_RETENTION_DAYS", "90"))
_DEFAULT_AUTO_PURGE = os.getenv("R2_AUTO_PURGE_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
)

# Mutable module-level state (protected by _retention_lock)
_retention_days: int = _DEFAULT_RETENTION_DAYS
_auto_purge_enabled: bool = _DEFAULT_AUTO_PURGE

# Known storage prefixes used for by-prefix breakdown in metrics
_KNOWN_PREFIXES: list[str] = [
    "reports/",
    "studies/",
    "cad/",
    "uploads/",
    "exports/",
    "temp/",
]

# Maximum number of objects to scan in a single metrics call (safety bound)
_METRICS_MAX_OBJECTS = 5000

# Threshold above which a purge requires explicit confirmation
_LARGE_PURGE_THRESHOLD = 100


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class StorageObjectInfo(BaseModel):
    """Metadata for a single R2 object."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(..., description="R2 object key (path)")
    size: int = Field(..., description="Object size in bytes")
    last_modified: Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp of last modification",
    )
    content_type: Optional[str] = Field(
        default=None,
        description="MIME type of the object (if known)",
    )


class ByPrefixBreakdown(BaseModel):
    """Size and object count for a specific prefix."""

    prefix: str = Field(..., description="Object key prefix")
    total_size_bytes: int = Field(..., description="Total bytes under this prefix")
    total_objects: int = Field(..., description="Number of objects under this prefix")


class StorageMetricsResponse(BaseModel):
    """Storage usage metrics for the R2 bucket."""

    model_config = ConfigDict(frozen=True)

    total_size_bytes: int = Field(
        ..., description="Total storage consumed in bytes across all objects"
    )
    total_objects: int = Field(..., description="Total number of objects in the bucket")
    by_prefix: list[ByPrefixBreakdown] = Field(
        default_factory=list,
        description="Breakdown of size and object count by prefix",
    )
    retention_days: int = Field(..., description="Current retention period in days")


class StoragePurgeRequest(BaseModel):
    """Request body for the purge endpoint.

    Safety: ``dry_run`` defaults to ``True`` so that a bare POST without
    this field will NOT delete anything — it will only report what would
    be deleted.
    """

    prefix: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Only purge objects with this key prefix (e.g. 'temp/')",
    )
    older_than_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=3650,
        description="Only purge objects older than this many days",
    )
    dry_run: bool = Field(
        default=True,
        description="If true (default), report what would be deleted without actually deleting",
    )
    confirm: bool = Field(
        default=False,
        description="Required when dry_run=false AND purge count > 100 to prevent accidental mass deletion",
    )


class StoragePurgeResponse(BaseModel):
    """Response from the purge endpoint."""

    model_config = ConfigDict(frozen=True)

    deleted_count: int = Field(..., description="Number of objects deleted (0 if dry_run)")
    freed_bytes: int = Field(..., description="Bytes freed by the purge (0 if dry_run)")
    dry_run: bool = Field(..., description="Whether this was a dry run (no actual deletion)")
    candidates: Optional[list[StorageObjectInfo]] = Field(
        default=None,
        description="Objects that would be deleted (populated in dry_run mode)",
    )


class RetentionPolicyResponse(BaseModel):
    """Current retention policy for the R2 bucket."""

    model_config = ConfigDict(frozen=True)

    retention_days: int = Field(
        ..., description="Number of days to retain objects before they are eligible for purge"
    )
    auto_purge_enabled: bool = Field(..., description="Whether automatic purge is enabled")
    last_updated: Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp of the last policy update",
    )


class RetentionPolicyUpdate(BaseModel):
    """Request body for updating the retention policy."""

    retention_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=3650,
        description="Number of days to retain objects (1–3650)",
    )
    auto_purge_enabled: Optional[bool] = Field(
        default=None,
        description="Enable or disable automatic purge",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_utc() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(UTC)


def _get_retention_state() -> tuple[int, bool]:
    """Return the current retention policy (thread-safe)."""
    with _retention_lock:
        return _retention_days, _auto_purge_enabled


def _set_retention_state(days: Optional[int], auto_purge: Optional[bool]) -> None:
    """Update the retention policy (thread-safe). Only non-None values are applied."""
    global _retention_days, _auto_purge_enabled
    with _retention_lock:
        if days is not None:
            _retention_days = days
        if auto_purge is not None:
            _auto_purge_enabled = auto_purge


async def _list_all_objects(prefix: str = "") -> list[dict[str, Any]]:
    """List all objects under a prefix, paginating up to _METRICS_MAX_OBJECTS."""
    all_objects: list[dict[str, Any]] = []
    continuation_token: Optional[str] = None  # noqa: F841
    fetched = 0

    while fetched < _METRICS_MAX_OBJECTS:
        batch_size = min(1000, _METRICS_MAX_OBJECTS - fetched)
        # R2 list_objects_v2 supports ContinuationToken for pagination.
        # Our list_objects wrapper doesn't expose it, so we fetch in
        # large batches and rely on the limit parameter.
        batch = await list_objects(prefix=prefix, limit=batch_size)
        if not batch:
            break
        all_objects.extend(batch)
        fetched += len(batch)
        if len(batch) < batch_size:
            # Fewer results than requested — no more objects
            break

    return all_objects


def _filter_objects_by_age(
    objects: list[dict[str, Any]],
    older_than_days: int,
) -> list[dict[str, Any]]:
    """Filter objects to those older than ``older_than_days`` days."""
    cutoff = _now_utc() - timedelta(days=older_than_days)
    filtered: list[dict[str, Any]] = []
    for obj in objects:
        last_modified_str = obj.get("last_modified")
        if not last_modified_str:
            continue
        try:
            last_modified = datetime.fromisoformat(last_modified_str)
            # Ensure timezone-aware comparison
            if last_modified.tzinfo is None:
                last_modified = last_modified.replace(tzinfo=UTC)
            if last_modified < cutoff:
                filtered.append(obj)
        except (ValueError, TypeError):
            logger.warning(
                "storage_purge_skip_invalid_date key=%s last_modified=%s",
                obj.get("key", "?"),
                last_modified_str,
            )
            continue
    return filtered


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=StorageMetricsResponse,
    summary="Get storage usage metrics",
    description="Return storage usage metrics including total objects, sizes, "
    "and a breakdown by key prefix. Requires API key or JWT.",
)
async def get_storage_metrics(
    _api_key: ApiKeyDep,
) -> StorageMetricsResponse:
    """Return storage usage metrics for the R2 bucket.

    Computes total size, total object count, and a by-prefix breakdown
    for the known storage prefixes (reports/, studies/, cad/, uploads/,
    exports/, temp/).
    """
    if not is_r2_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="R2 storage is not configured. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, and R2_SECRET_ACCESS_KEY.",
        )

    logger.info("storage_metrics_requested")

    # Gather all objects (up to the safety bound)
    all_objects = await _list_all_objects(prefix="")

    total_size = sum(obj.get("size", 0) for obj in all_objects)
    total_objects = len(all_objects)

    # Build by-prefix breakdown
    by_prefix: list[ByPrefixBreakdown] = []
    for prefix in _KNOWN_PREFIXES:
        prefix_objects = [obj for obj in all_objects if obj.get("key", "").startswith(prefix)]
        prefix_size = sum(obj.get("size", 0) for obj in prefix_objects)
        prefix_count = len(prefix_objects)
        by_prefix.append(
            ByPrefixBreakdown(
                prefix=prefix,
                total_size_bytes=prefix_size,
                total_objects=prefix_count,
            )
        )

    # Add an "other/" bucket for objects not matching any known prefix
    accounted_keys: set[str] = set()
    for prefix in _KNOWN_PREFIXES:
        for obj in all_objects:
            if obj.get("key", "").startswith(prefix):
                accounted_keys.add(obj.get("key"))
    other_objects = [obj for obj in all_objects if obj.get("key") not in accounted_keys]
    if other_objects:
        other_size = sum(obj.get("size", 0) for obj in other_objects)
        by_prefix.append(
            ByPrefixBreakdown(
                prefix="other/",
                total_size_bytes=other_size,
                total_objects=len(other_objects),
            )
        )

    retention_days, _ = _get_retention_state()

    return StorageMetricsResponse(
        total_size_bytes=total_size,
        total_objects=total_objects,
        by_prefix=by_prefix,
        retention_days=retention_days,
    )


@router.post(
    "/purge",
    response_model=StoragePurgeResponse,
    summary="Purge temporary files",
    description="Purge temporary or old files from R2 storage. "
    "Defaults to dry_run=true for safety — no files are deleted unless "
    "dry_run=false is explicitly set. Large purges (>100 objects) require "
    "confirm=true in addition to dry_run=false.",
)
async def purge_storage(
    request: StoragePurgeRequest,
    _api_key: ApiKeyDep,
) -> StoragePurgeResponse:
    """Purge temporary/old files from R2 storage.

    Safety mechanisms:
    1. ``dry_run`` defaults to ``True`` — no data is deleted unless explicitly set to ``False``.
    2. Purges affecting >100 objects require ``confirm=True`` alongside ``dry_run=False``.
    3. All operations are logged for audit.
    """
    if not is_r2_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="R2 storage is not configured.",
        )

    prefix = request.prefix or ""
    older_than_days = request.older_than_days

    logger.info(
        "storage_purge_requested prefix=%s older_than_days=%s dry_run=%s",
        prefix or "(all)",
        older_than_days,
        request.dry_run,
    )

    # List objects matching the prefix
    objects = await _list_all_objects(prefix=prefix)

    # Filter by age if requested
    if older_than_days is not None:
        objects = _filter_objects_by_age(objects, older_than_days)

    # Compute totals
    candidate_keys = [obj["key"] for obj in objects]
    freed_bytes = sum(obj.get("size", 0) for obj in objects)

    # Build candidate info for dry_run response
    candidates = [
        StorageObjectInfo(
            key=obj["key"],
            size=obj.get("size", 0),
            last_modified=obj.get("last_modified"),
            content_type=obj.get("content_type"),
        )
        for obj in objects
    ]

    # ── Dry run: just report what would be deleted ──
    if request.dry_run:
        logger.info(
            "storage_purge_dry_run candidates=%d freed_bytes=%d",
            len(candidate_keys),
            freed_bytes,
        )
        return StoragePurgeResponse(
            deleted_count=0,
            freed_bytes=0,
            dry_run=True,
            candidates=candidates,
        )

    # ── Safety check: large purge requires confirmation ──
    if len(candidate_keys) > _LARGE_PURGE_THRESHOLD and not request.confirm:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Purge would delete {len(candidate_keys)} objects (> {_LARGE_PURGE_THRESHOLD}). "
                "Set confirm=true to proceed with this large purge."
            ),
        )

    # ── Actually delete ──
    deleted_count = 0
    if candidate_keys:
        deleted_count = await delete_many(candidate_keys)

    logger.info(
        "storage_purge_completed deleted=%d freed_bytes=%d prefix=%s",
        deleted_count,
        freed_bytes,
        prefix or "(all)",
    )

    return StoragePurgeResponse(
        deleted_count=deleted_count,
        freed_bytes=freed_bytes,
        dry_run=False,
        candidates=None,
    )


@router.get(
    "/retention",
    response_model=RetentionPolicyResponse,
    summary="Get current retention policy",
    description="Return the current retention policy for the R2 bucket, "
    "including the retention period in days and whether auto-purge is enabled.",
)
async def get_retention_policy(
    _api_key: ApiKeyDep,
) -> RetentionPolicyResponse:
    """Return the current retention policy.

    The retention policy determines how long objects are kept before they
    become eligible for automatic purge. The policy is stored in-memory
    and can be updated via the PUT /retention endpoint.
    """
    days, auto_purge = _get_retention_state()
    return RetentionPolicyResponse(
        retention_days=days,
        auto_purge_enabled=auto_purge,
        last_updated=None,  # Could be enhanced to track last update time
    )


@router.put(
    "/retention",
    response_model=RetentionPolicyResponse,
    summary="Update retention policy",
    description="Update the retention policy for the R2 bucket. "
    "Only non-null fields in the request body will be updated.",
)
async def update_retention_policy(
    body: RetentionPolicyUpdate,
    _api_key: ApiKeyDep,
) -> RetentionPolicyResponse:
    """Update the retention policy.

    Accepts partial updates — only fields that are explicitly set will be
    changed. For example, to enable auto-purge without changing the
    retention days, send only ``{"auto_purge_enabled": true}``.
    """
    if body.retention_days is None and body.auto_purge_enabled is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of retention_days or auto_purge_enabled must be provided.",
        )

    _set_retention_state(body.retention_days, body.auto_purge_enabled)

    logger.info(
        "storage_retention_updated days=%s auto_purge=%s",
        body.retention_days,
        body.auto_purge_enabled,
    )

    days, auto_purge = _get_retention_state()
    return RetentionPolicyResponse(
        retention_days=days,
        auto_purge_enabled=auto_purge,
        last_updated=_now_utc().isoformat(),
    )


@router.delete(
    "/artifacts/cad",
    response_model=StoragePurgeResponse,
    summary="Clear temporary CAD artifacts",
    description="Delete all temporary CAD artifacts from the R2 bucket. "
    "These are objects stored under the ``cad/`` prefix. "
    "Defaults to dry_run=true for safety.",
)
async def clear_cad_artifacts(
    _api_key: ApiKeyDep,
    dry_run: bool = Query(
        default=True,
        description="If true (default), report what would be deleted without actually deleting",
    ),
    confirm: bool = Query(
        default=False,
        description="Required when dry_run=false AND purge count > 100",
    ),
) -> StoragePurgeResponse:
    """Delete all temporary CAD artifacts (objects under ``cad/`` prefix).

    CAD artifacts are typically intermediate simulation outputs that can be
    safely removed after the final report is generated. This endpoint
    provides a convenient shortcut for cleaning up these files.

    Safety:
    - Defaults to dry_run=true (no actual deletion).
    - Requires confirm=true for large purges (>100 objects).
    """
    if not is_r2_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="R2 storage is not configured.",
        )

    logger.info("storage_cad_artifacts_purge_requested dry_run=%s", dry_run)

    # List all CAD artifacts
    objects = await _list_all_objects(prefix="cad/")

    candidate_keys = [obj["key"] for obj in objects]
    freed_bytes = sum(obj.get("size", 0) for obj in objects)

    # Build candidate info for dry_run response
    candidates = [
        StorageObjectInfo(
            key=obj["key"],
            size=obj.get("size", 0),
            last_modified=obj.get("last_modified"),
            content_type=obj.get("content_type"),
        )
        for obj in objects
    ]

    # Dry run — just report
    if dry_run:
        logger.info(
            "storage_cad_artifacts_dry_run candidates=%d freed_bytes=%d",
            len(candidate_keys),
            freed_bytes,
        )
        return StoragePurgeResponse(
            deleted_count=0,
            freed_bytes=0,
            dry_run=True,
            candidates=candidates,
        )

    # Safety check: large purge requires confirmation
    if len(candidate_keys) > _LARGE_PURGE_THRESHOLD and not confirm:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Purge would delete {len(candidate_keys)} CAD artifacts "
                f"(> {_LARGE_PURGE_THRESHOLD}). "
                "Set confirm=true to proceed with this large purge."
            ),
        )

    # Actually delete
    deleted_count = 0
    if candidate_keys:
        deleted_count = await delete_many(candidate_keys)

    logger.info(
        "storage_cad_artifacts_purged deleted=%d freed_bytes=%d",
        deleted_count,
        freed_bytes,
    )

    return StoragePurgeResponse(
        deleted_count=deleted_count,
        freed_bytes=freed_bytes,
        dry_run=False,
        candidates=None,
    )

