"""
api/results_store.py — P5 secure ResultStore.

Result *metadata* (summary, TTL, ownership) lives in the ``results`` table;
per-file metadata lives in ``result_files``. Heavy payloads are **never**
stored inside the database — each file is written to a per-tenant,
per-result directory on the local filesystem.

Storage layout
--------------
    {RESULT_STORE_DIR}/tenants/{tenant}/results/{result_id}/{file_path}

``RESULT_STORE_DIR`` defaults to ``./data/results`` and can be overridden
with the ``RESULT_STORE_DIR`` environment variable.

Security guarantees
-------------------
* **Tenant isolation** — every read/stream is filtered by the authenticated
  user's tenant (``CurrentUser.tenant_id``). A cross-tenant result or file
  resolves to 404 (no existence disclosure).
* **Tenant binding** — ``tenant_id`` NEVER comes from a request body; it is
  stamped from the authenticated user context only. Spoofed ``tenant_id``
  payload fields are ignored.
* **File safety** — ``../``, ``..\\``, absolute paths, drive letters, null
  bytes, and any path that resolves outside the result directory are
  rejected *before* any storage or access.
* **Size limit** — files larger than :data:`RESULT_FILE_MAX_BYTES`
  (10 MiB) fail *before* anything is written.
* **Expiry** — an expired result is never returned as valid content and is
  removed by :func:`cleanup_expired_results` (DB record + ``result_files``
  metadata + physical files), never touching other tenants' data.
* **Write atomicity** — file bytes are staged to ``<name>.uploading``,
  flushed/fsynced, then atomically renamed to their final name BEFORE the
  DB transaction is committed. A DB failure removes the staged directory;
  a file-write failure never leaves a DB row pointing at a missing file.
"""

from __future__ import annotations

import contextlib
import base64
import hashlib
import json
import logging
import os
import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base, async_session
from api.dependencies import CurrentUser, get_current_user_from_header

logger = logging.getLogger(__name__)

UTC = timezone.utc

# ---------------------------------------------------------------------------
# Configuration / limits
# ---------------------------------------------------------------------------

RESULT_FILE_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB hard per-file limit
DEFAULT_TTL_DAYS = 30
DEFAULT_TTL = timedelta(days=DEFAULT_TTL_DAYS)
# Keep summary_json lightweight — heavy content belongs in result_files.
MAX_SUMMARY_JSON_BYTES = 512 * 1024
_MAX_FILES_PER_RESULT = 200

_DEFAULT_STORAGE_ROOT = os.environ.get(
    "RESULT_STORE_DIR", os.path.join("data", "results")
)


def _storage_root() -> Path:
    """Resolve the on-disk result-store root (env read per call for tests)."""
    raw = os.environ.get("RESULT_STORE_DIR", _DEFAULT_STORAGE_ROOT) or ""
    return Path(raw).resolve()


def _utcnow() -> datetime:
    """Current UTC wall-clock time (timezone-aware)."""
    return datetime.now(UTC)


def _as_aware(value: datetime) -> datetime:
    """Normalise a DB-loaded datetime to timezone-aware UTC.

    SQLite (used in tests/dev) returns naive datetimes; PostgreSQL returns
    aware ones. Comparing a naive value against :func:`_utcnow` would raise
    ``TypeError``, and ``astimezone`` on a naive value would wrongly assume
    local time — so re-anchor to UTC first (same pattern as api/approvals.py).
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _iso(value: datetime) -> str:
    """ISO-8601 'Z' string for API responses."""
    return _as_aware(value).astimezone(UTC).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# ORM models — registered on api.database.Base so init_db()/Alembic build them
# ---------------------------------------------------------------------------


class ResultRecord(Base):
    """A stored result owned by exactly one tenant."""

    __tablename__ = "results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # Metadata only — heavy content belongs in result_files on disk.
    summary_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    files: Mapped[List["ResultFileRecord"]] = relationship(
        back_populates="result",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ResultFileRecord(Base):
    """Metadata for one physical file stored for a :class:`ResultRecord`."""

    __tablename__ = "result_files"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    result_id: Mapped[str] = mapped_column(
        ForeignKey("results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime: Mapped[str] = mapped_column(
        String(128), nullable=False, default="application/octet-stream"
    )
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    result: Mapped[ResultRecord] = relationship(back_populates="files")


# ---------------------------------------------------------------------------
# On-disk layout helpers — {ROOT}/tenants/{tenant}/results/{result}/...
# ---------------------------------------------------------------------------


def _safe_component(value: str, fallback: str) -> str:
    """Sanitize a tenant/result key so it can never escape its directory."""
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", value or "").strip(".")
    return sanitized or fallback


def _tenant_dir(tenant_id: str) -> Path:
    return _storage_root() / "tenants" / _safe_component(tenant_id, "default")


def _result_dir(tenant_id: str, result_id: str) -> Path:
    return _tenant_dir(tenant_id) / "results" / _safe_component(result_id, "unknown")


# ---------------------------------------------------------------------------
# File path safety
# ---------------------------------------------------------------------------

_ABSOLUTE_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/])")
_NULL_BYTE = "\x00"


def _validate_file_path(rel_path: str) -> str:
    """Validate a client-supplied relative file path.

    Rejects null bytes, absolute paths (Unix ``/x`` or Windows ``C:\\``),
    drive letters, ``..`` segments (both ``../`` and ``..\\`` forms, after
    separator normalisation) and empty/dot segments. Returns the normalised
    forward-slash relative path on success.
    """
    if rel_path is None or not isinstance(rel_path, str):
        raise HTTPException(status_code=400, detail="Invalid file path")
    if _NULL_BYTE in rel_path:
        raise HTTPException(status_code=400, detail="Invalid file path")
    candidate = rel_path.strip().replace("\\", "/")
    if not candidate:
        raise HTTPException(status_code=400, detail="Invalid file path")
    if _ABSOLUTE_PATH_RE.match(candidate):
        raise HTTPException(status_code=400, detail="Absolute paths are not allowed")
    segments = candidate.split("/")
    if any(seg in ("", ".", "..") for seg in segments):
        raise HTTPException(status_code=400, detail="Path traversal is not allowed")
    if "//" in candidate or candidate.endswith("/"):
        raise HTTPException(status_code=400, detail="Invalid file path")
    if len(candidate) > 400:
        raise HTTPException(status_code=400, detail="File path too long")
    return candidate


def _is_within(base: Path, candidate: Path) -> bool:
    """True when *candidate* (resolved) is strictly inside *base* (resolved)."""
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Metadata persistence helpers
# ---------------------------------------------------------------------------


def _serialize_result(record: ResultRecord) -> dict:
    return {
        "id": record.id,
        "tenant_id": record.tenant_id,
        "project_id": record.project_id,
        "created_by": record.created_by,
        "summary": record.summary_json,
        "created_at": _iso(record.created_at),
        "expires_at": _iso(record.expires_at),
    }


async def _fetch_result_row(tenant_id: str, result_id: str) -> ResultRecord | None:
    """Fetch a result row strictly scoped to the caller's tenant."""
    async with async_session() as session:
        row = (
            await session.execute(
                select(ResultRecord).where(
                    ResultRecord.id == result_id,
                    ResultRecord.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            # Force-load the relationship so the result is consistent after commit.
            _ = row.files
        return row


async def create_result(
    tenant_id: str,
    project_id: Optional[str] = None,
    created_by: Optional[str] = None,
    summary_json: Optional[dict] = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> str:
    """Create a result record owned by *tenant_id* and return its id.

    The tenant must come from the authenticated-user context of the caller.
    ``summary_json`` is metadata only and is capped at
    :data:`MAX_SUMMARY_JSON_BYTES`.
    """
    ttl_days = int(ttl_days or DEFAULT_TTL_DAYS)
    if ttl_days < 1:
        raise HTTPException(status_code=400, detail="ttl_days must be >= 1")

    if summary_json is not None:
        try:
            encoded = json.dumps(summary_json, separators=(",", ":"), default=str)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400, detail="summary must be JSON-serializable"
            ) from exc
        if len(encoded) > MAX_SUMMARY_JSON_BYTES:
            raise HTTPException(
                status_code=413,
                detail="summary_json is too large; store heavy content as files",
            )

    result_id = str(uuid.uuid4())
    now = _utcnow()
    expires_at = now + timedelta(days=ttl_days)

    async with async_session() as session:
        record = ResultRecord(
            id=result_id,
            tenant_id=(tenant_id or "").strip() or "default",
            project_id=project_id,
            created_by=created_by,
            summary_json=summary_json,
            created_at=now,
            expires_at=expires_at,
        )
        session.add(record)
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    return result_id


async def get_result(tenant_id: str, result_id: str) -> dict | None:
    """Return serialized result + files, or ``None``.

    Missing, cross-tenant and expired results all return ``None`` so the
    caller can respond 404 without disclosing existence.
    """
    row = await _fetch_result_row(tenant_id, result_id)
    if row is None:
        return None
    if row.expires_at is not None and _as_aware(row.expires_at) <= _utcnow():
        return None  # expired results are never returned as valid content
    files = [
        {
            "id": f.id,
            "path": f.path,
            "mime": f.mime,
            "size_bytes": f.size_bytes,
        }
        for f in sorted(row.files, key=lambda fw: fw.path)
    ]
    data = _serialize_result(row)
    data["files"] = files
    return data


async def store_result_file(
    tenant_id: str,
    result_id: str,
    rel_path: str,
    data: bytes,
    mime: str = "application/octet-stream",
    size_limit: int = RESULT_FILE_MAX_BYTES,
) -> str:
    """Atomically store one file for a result and persist its metadata row.

    Ordering guarantees:
      1. The path and the 10 MiB size limit are enforced BEFORE any file or
         DB write (``fails before final storage``).
      2. Bytes are staged next to the target, flushed + fsynced, then
         atomically renamed into place.
      3. Only after the physical file is finalised is the ``result_files``
         row committed. If the commit fails the staged file is removed, so a
         DB row never points at a missing file and files are never orphaned
         by a failed commit.
    """
    rel_path = _validate_file_path(rel_path)
    if data is None or not isinstance(data, (bytes, bytearray)):
        raise HTTPException(status_code=400, detail="File data is required")
    if len(data) > size_limit:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {size_limit} byte ({size_limit // (1024 * 1024)} MiB) limit",
        )

    row = await _fetch_result_row(tenant_id, result_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Result not found")
    if row.expires_at is not None and _as_aware(row.expires_at) <= _utcnow():
        raise HTTPException(status_code=404, detail="Result not found")

    rdir = _result_dir(tenant_id, result_id)
    target = (rdir / rel_path).resolve()
    if not _is_within(rdir, target):
        raise HTTPException(status_code=400, detail="Path traversal is not allowed")

    target.parent.mkdir(parents=True, exist_ok=True)

    tmp_target = target.parent / f".{target.name}.uploading-{uuid.uuid4().hex}"
    try:
        with open(str(tmp_target), "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(str(tmp_target), str(target))
    except Exception:
        with contextlib.suppress(Exception):
            if os.path.exists(str(tmp_target)):
                os.remove(str(tmp_target))
        logger.exception(
            "result_file_write_failed result_id=%s path=%s", result_id, rel_path
        )
        raise HTTPException(status_code=500, detail="File storage failed")

    file_id = str(uuid.uuid4())
    try:
        async with async_session() as session:
            session.add(
                ResultFileRecord(
                    id=file_id,
                    result_id=result_id,
                    path=rel_path,
                    mime=mime or "application/octet-stream",
                    size_bytes=len(data),
                )
            )
            await session.commit()
    except Exception:
        # DB commit failed — remove the physical file so nothing is orphaned.
        with contextlib.suppress(Exception):
            if os.path.exists(str(target)):
                os.remove(str(target))
        logger.exception(
            "result_file_db_commit_failed result_id=%s path=%s", result_id, rel_path
        )
        raise HTTPException(status_code=500, detail="File metadata persistence failed")
    return file_id


async def open_result_file(
    tenant_id: str, result_id: str, rel_path: str
) -> tuple[Path, ResultFileRecord] | None:
    """Resolve a physical file for a tenant-scoped result, or ``None``."""
    rel_path = _validate_file_path(rel_path)
    row = await _fetch_result_row(tenant_id, result_id)
    if row is None:
        return None
    if row.expires_at is not None and _as_aware(row.expires_at) <= _utcnow():
        return None
    rdir = _result_dir(tenant_id, result_id)
    target = (rdir / rel_path).resolve()
    if not _is_within(rdir, target):
        return None
    if not target.is_file():
        return None
    meta = next((f for f in row.files if f.path == rel_path), None)
    return target, meta


async def delete_result(tenant_id: str, result_id: str) -> bool:
    """Delete a result record, its file metadata, and its physical files.

    Returns ``False`` when the result is missing or belongs to another tenant
    (no-op — the caller maps it to 404).
    """
    row = await _fetch_result_row(tenant_id, result_id)
    if row is None:
        return False
    rdir = _result_dir(tenant_id, result_id)
    async with async_session() as session:
        stored = (
            await session.execute(
                select(ResultRecord).where(
                    ResultRecord.id == result_id,
                    ResultRecord.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if stored is None:
            return False
        await session.delete(stored)
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    with contextlib.suppress(Exception):
        shutil.rmtree(str(rdir), ignore_errors=True)
    return True


async def cleanup_expired_results(now: Optional[datetime] = None) -> int:
    """Delete every EXPIRED result for every tenant.

    Only results whose ``expires_at <= now`` are touched — live results in
    any tenant are never affected. For each expired result the DB record and
    its ``result_files`` metadata are deleted first (committed), then the
    physical files are removed; a failure to remove a file after a successful
    commit leaves at most an orphaned file that is no longer referenced.
    """
    cutoff = now or _utcnow()
    removed = 0
    async with async_session() as session:
        expired = (
            await session.execute(
                select(ResultRecord).where(
                    ResultRecord.expires_at.is_not(None),
                    ResultRecord.expires_at <= cutoff,
                )
            )
        ).scalars().all()
        for record in expired:
            rdir = _result_dir(record.tenant_id, record.id)
            await session.delete(record)
            removed += 1
            # Commit per record so one failing tenant never blocks others.
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception(
                    "cleanup_expired_commit_failed result_id=%s tenant=%s",
                    record.id,
                    record.tenant_id,
                )
                continue
            with contextlib.suppress(Exception):
                shutil.rmtree(str(rdir), ignore_errors=True)
    return removed


# ---------------------------------------------------------------------------
# Study-integration helper
# ---------------------------------------------------------------------------


async def persist_study_result(
    tenant_id: str,
    project_id: Optional[str] = None,
    created_by: Optional[str] = None,
    summary_json: Optional[dict] = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> str:
    """Persist a completed study's summary into the ResultStore.

    Called by ``api/studies.py`` after a successful native/ETAP study run.
    The tenant is taken from the authenticated request context, never from
    the study payload. Returns the new ``result_id``.
    """
    return await create_result(
        tenant_id=tenant_id,
        project_id=project_id,
        created_by=created_by,
        summary_json=summary_json,
        ttl_days=ttl_days,
    )


# ---------------------------------------------------------------------------
# HTTP API — all routes derive tenant_id from the authenticated user only.
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/results", tags=["results"])


class CreateResultRequest(BaseModel):
    """Body for POST /api/v1/results.

    Deliberately has NO ``tenant_id`` field — a spoofed tenant in the body is
    silently ignored because the tenant always comes from the authenticated
    user context.
    """

    model_config = ConfigDict(extra="ignore")  # unknown/spoofed fields dropped

    project_id: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    ttl_days: Optional[int] = Field(default=None, ge=1, le=365)


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    """Stream an upload in chunks, failing as soon as the limit is exceeded."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {limit} byte ({limit // (1024 * 1024)} MiB) limit",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("", status_code=201)
async def create_result_endpoint(
    req: CreateResultRequest,
    user: CurrentUser = Depends(get_current_user_from_header),
) -> dict:
    """Create a result record (metadata only)."""
    result_id = await create_result(
        tenant_id=user.tenant_id,
        project_id=req.project_id,
        created_by=user.user_id,
        summary_json=req.summary,
        ttl_days=req.ttl_days or DEFAULT_TTL_DAYS,
    )
    data = await get_result(user.tenant_id, result_id)
    if data is None:  # pragma: no cover — just created so must exist
        raise HTTPException(status_code=500, detail="Result creation failed")
    return data


@router.get("/{result_id}")
async def read_result_endpoint(
    result_id: str,
    user: CurrentUser = Depends(get_current_user_from_header),
) -> dict:
    """Return result metadata + file list. Missing/expired/cross-tenant → 404."""
    data = await get_result(user.tenant_id, result_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return data


@router.post("/{result_id}/files", status_code=201)
async def upload_result_file_endpoint(
    result_id: str,
    file: UploadFile = File(...),
    file_path: str = Form(...),
    user: CurrentUser = Depends(get_current_user_from_header),
) -> dict:
    """Upload one file for a result. Size/path checks run before any write."""
    data = await _read_limited(file, RESULT_FILE_MAX_BYTES)
    await file.close()
    mime = file.content_type or "application/octet-stream"
    file_id = await store_result_file(
        tenant_id=user.tenant_id,
        result_id=result_id,
        rel_path=file_path,
        data=data,
        mime=mime,
    )
    return {
        "file_id": file_id,
        "result_id": result_id,
        "path": file_path,
        "mime": mime,
        "size_bytes": len(data),
    }


@router.get("/{result_id}/files/{file_path:path}")
async def stream_result_file_endpoint(
    result_id: str,
    file_path: str,
    user: CurrentUser = Depends(get_current_user_from_header),
) -> FileResponse:
    """Stream a stored file. Cross-tenant/expired/missing → 404."""
    resolved = await open_result_file(user.tenant_id, result_id, file_path)
    if resolved is None:
        raise HTTPException(status_code=404, detail="File not found")
    target, meta = resolved
    mime = meta.mime if meta is not None else "application/octet-stream"
    return FileResponse(
        path=str(target),
        media_type=mime,
        filename=os.path.basename(str(target)),
    )


@router.delete("/{result_id}")
async def delete_result_endpoint(
    result_id: str,
    user: CurrentUser = Depends(get_current_user_from_header),
) -> dict:
    """Delete a result + its files. Cross-tenant/missing → 404."""
    deleted = await delete_result(user.tenant_id, result_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Result not found")
    return {"deleted": True, "result_id": result_id}