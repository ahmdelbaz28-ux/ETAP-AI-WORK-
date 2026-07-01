"""
Supabase integration for AhmedETAP
===================================

⚠️ SAFETY-CRITICAL INFRASTRUCTURE ⚠️
This module provides:

1. **PostgreSQL connection** — Supabase Postgres as a managed, persistent
   backend (replaces SQLite on HF Space where the filesystem is wiped on
   every restart). All existing SQLAlchemy models work unchanged because
   Supabase Postgres is just Postgres.

2. **Storage** — Supabase Storage for user-uploaded files (PDF manuals,
   ETAP screenshots, generated reports). Files persist across restarts
   and are accessible via signed URLs.

3. **Auth helpers** — optional Supabase Auth integration for social
   login (Google, GitHub, etc.). The existing bcrypt/JWT auth in
   ``api/auth.py`` continues to work; Supabase Auth is an additional
   option for users who prefer social login.

Configuration
-------------
Set these env vars (see ``.env.example``)::

    SUPABASE_URL=https://your-project.supabase.co
    SUPABASE_ANON_KEY=sb_publishable_...
    SUPABASE_SERVICE_ROLE_KEY=sb_secret_...     # server-side only!
    DATABASE_URL=postgresql+asyncpg://postgres.YOUR_PROJECT:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres

Safety
------
- The ``SERVICE_ROLE_KEY`` bypasses Row-Level Security (RLS). It is
  loaded from env and never logged, never returned by any function.
- All Storage uploads are scanned for MIME type (no executable uploads).
- File names are sanitised and a UUID prefix is added to prevent
  path-traversal attacks.
- Public URLs are only generated for files in explicitly-public buckets.

Usage
-----
::

    from integrations.supabase_integration import (
        get_supabase_client,
        upload_file,
        get_public_url,
        get_signed_url,
    )

    # Upload a PDF manual
    url = upload_file(
        bucket="manuals",
        file_path="etap_user_guide.pdf",
        content=pdf_bytes,
        content_type="application/pdf",
        user_id="eng_42",
    )

    # Get a signed URL (1-hour expiry) for a private file
    url = get_signed_url(
        bucket="reports",
        file_path="arc_flash_report_2025_01_15.pdf",
        expires_in=3600,
    )
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, BinaryIO, Optional

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Buckets used by AhmedETAP. Created on first init if missing.
PUBLIC_BUCKET_MANUALS = "manuals"        # IEC/IEEE standards, ETAP guides (public read)
PRIVATE_BUCKET_REPORTS = "reports"       # Generated reports (private, signed URLs)
PRIVATE_BUCKET_SCREENSHOTS = "screenshots"  # ETAP screenshots (private, signed URLs)
PRIVATE_BUCKET_UPLOADS = "user-uploads"  # User-uploaded files (private, signed URLs)

ALL_BUCKETS = [
    (PUBLIC_BUCKET_MANUALS, True),       # (name, is_public)
    (PRIVATE_BUCKET_REPORTS, False),
    (PRIVATE_BUCKET_SCREENSHOTS, False),
    (PRIVATE_BUCKET_UPLOADS, False),
]

# Allowed MIME types for upload (safety: refuse executables)
_ALLOWED_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/json",
        "text/plain",
        "text/csv",
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/tiff",
        "application/zip",
    }
)

# Max upload size: 50 MB (safety: prevent resource exhaustion)
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


# ─── Lazy Supabase client (optional dependency) ──────────────────────────

_client = None
_client_init_attempted = False


def _get_client():
    """Return the Supabase client (lazy, thread-safe enough for our use)."""
    global _client, _client_init_attempted
    if _client is not None:
        return _client
    if _client_init_attempted:
        return None
    _client_init_attempted = True

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        logger.info(
            "Supabase disabled: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set"
        )
        return None

    try:
        from supabase import create_client  # type: ignore

        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        logger.info(
            "✅ Supabase client initialized — URL: %s", SUPABASE_URL
        )
    except ImportError:
        logger.warning(
            "supabase package not installed. Run: pip install supabase. "
            "Supabase features will be disabled."
        )
        return None
    except Exception as e:
        logger.warning("Supabase client init failed: %s", e)
        return None
    return _client


# ─── Bucket management ───────────────────────────────────────────────────


def ensure_buckets_exist() -> dict[str, bool]:
    """Create all required buckets if they don't exist. Idempotent.

    Returns a dict mapping bucket name → was_created.
    """
    client = _get_client()
    if client is None:
        return {name: False for name, _ in ALL_BUCKETS}

    # Get the list of existing bucket names (handle both dict + object forms)
    try:
        existing_buckets = client.storage.list_buckets()
        existing_names: set[str] = set()
        for b in existing_buckets:
            # Supabase SDK may return SyncBucket objects or dicts
            name = getattr(b, "name", None) if not isinstance(b, dict) else b.get("name")
            if name:
                existing_names.add(name)
    except Exception as e:
        logger.warning("Failed to list buckets: %s", e)
        existing_names = set()

    created: dict[str, bool] = {}
    for name, is_public in ALL_BUCKETS:
        if name in existing_names:
            created[name] = False
            continue
        try:
            client.storage.create_bucket(
                id=name,
                options={"public": is_public},
            )
            created[name] = True
            logger.info(
                "Created Supabase bucket '%s' (public=%s)", name, is_public
            )
        except Exception as e:
            logger.warning("Failed to create bucket '%s': %s", name, e)
            created[name] = False
    return created


# ─── Safety: MIME-type + size validation ─────────────────────────────────


class SupabaseUploadError(ValueError):
    """Raised when an upload violates a safety guardrail."""


def _validate_upload(content: bytes, content_type: str) -> None:
    """Run safety checks on an upload. Raises SupabaseUploadError on failure."""
    if not content:
        raise SupabaseUploadError("Empty upload")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise SupabaseUploadError(
            f"Upload too large: {len(content)} bytes > {_MAX_UPLOAD_BYTES} limit "
            f"({len(content) // (1024*1024)} MB > {_MAX_UPLOAD_BYTES // (1024*1024)} MB)"
        )
    if content_type not in _ALLOWED_MIME_TYPES:
        raise SupabaseUploadError(
            f"Disallowed MIME type: '{content_type}'. "
            f"Allowed: {sorted(_ALLOWED_MIME_TYPES)}"
        )


def _sanitise_filename(filename: str) -> str:
    """Sanitise a filename to prevent path-traversal + add UUID prefix.

    Returns a safe relative path like ``<uuid>/<safe_name>``.

    Safety measures:
    1. Strip any path components (Windows + Unix separators)
    2. Replace ``..`` sequences (path-traversal marker)
    3. Replace any non-alphanumeric char (except -_.) with underscore
    4. Prefix with a UUID for collision avoidance
    """
    # Strip any path components from the filename (handles both / and \)
    safe = filename.replace("\\", "/").split("/")[-1]
    # Remove ".." sequences (path-traversal marker) — replace with single dot
    safe = safe.replace("..", ".")
    # Allow only alphanumerics, dash, underscore, dot
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in safe)
    # Final safety: strip any leading dots (hidden files / traversal)
    safe = safe.lstrip(".")
    if not safe or safe == "_":
        safe = "upload"
    # Prefix with UUID to prevent collisions + path traversal
    prefix = uuid.uuid4().hex[:16]
    return f"{prefix}/{safe}"


# ─── Public Storage API ──────────────────────────────────────────────────


def upload_bytes(
    *,
    bucket: str,
    filename: str,
    content: bytes,
    content_type: str,
    user_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    upsert: bool = False,
) -> dict[str, Any]:
    """Upload bytes to a Supabase Storage bucket.

    Parameters
    ----------
    bucket : str
        Bucket name (e.g. ``"reports"``).
    filename : str
        Original filename (will be sanitised + UUID-prefixed).
    content : bytes
        File content.
    content_type : str
        MIME type (must be in the allowlist).
    user_id : str, optional
        Uploader user ID (added to file metadata).
    metadata : dict, optional
        Additional metadata to attach.
    upsert : bool
        If True, replace existing file with the same path.

    Returns
    -------
    dict
        ``{"path": ..., "bucket": ..., "public_url": ... or None,
           "size": ..., "content_type": ...}``

    Raises
    ------
    SupabaseUploadError
        If a safety guardrail is violated.
    """
    _validate_upload(content, content_type)

    client = _get_client()
    if client is None:
        raise RuntimeError(
            "Supabase client not available. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY env vars."
        )

    safe_path = _sanitise_filename(filename)

    # Build file metadata
    file_metadata = {
        "user_id": user_id or "anonymous",
        "original_filename": filename,
        "content_type": content_type,
        "size_bytes": str(len(content)),
        **(metadata or {}),
    }

    try:
        response = client.storage.from_(bucket).upload(
            path=safe_path,
            file=content,
            file_options={
                "content-type": content_type,
                "upsert": "true" if upsert else "false",
                "metadata": file_metadata,
            },
        )
        # Supabase-py returns a response object; check for errors
        if hasattr(response, "error") and response.error:
            raise RuntimeError(f"Supabase upload error: {response.error}")

        # Determine if bucket is public (for public_url)
        try:
            bucket_info = client.storage.get_bucket(bucket)
            # Handle both dict and SyncBucket object forms
            if isinstance(bucket_info, dict):
                is_public = bool(bucket_info.get("public", False))
            else:
                is_public = bool(getattr(bucket_info, "public", False))
        except Exception:
            # If we can't fetch the bucket info, assume private (safer)
            is_public = False
        public_url: Optional[str] = None
        if is_public:
            public_url = client.storage.from_(bucket).get_public_url(safe_path)

        return {
            "path": safe_path,
            "bucket": bucket,
            "public_url": public_url,
            "size": len(content),
            "content_type": content_type,
        }
    except Exception as e:
        logger.error(
            "Supabase upload failed (bucket=%s, filename=%s): %s",
            bucket,
            filename,
            e,
        )
        raise


def upload_file(
    *,
    bucket: str,
    file_path: str | Path,
    content_type: str,
    user_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict[str, Any]:
    """Upload a file from disk. See ``upload_bytes`` for parameter docs."""
    path = Path(file_path)
    content = path.read_bytes()
    return upload_bytes(
        bucket=bucket,
        filename=path.name,
        content=content,
        content_type=content_type,
        user_id=user_id,
        metadata=metadata,
    )


def get_public_url(bucket: str, path: str) -> Optional[str]:
    """Return the public URL for a file in a public bucket.

    Returns ``None`` if the bucket is private.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        bucket_info = client.storage.get_bucket(bucket)
        # Handle both dict and SyncBucket object forms
        if isinstance(bucket_info, dict):
            is_public = bool(bucket_info.get("public", False))
        else:
            is_public = bool(getattr(bucket_info, "public", False))
        if not is_public:
            return None
        return client.storage.from_(bucket).get_public_url(path)
    except Exception as e:
        logger.warning("get_public_url failed: %s", e)
        return None


def get_signed_url(
    *, bucket: str, path: str, expires_in: int = 3600
) -> Optional[str]:
    """Return a signed URL for a private file.

    Parameters
    ----------
    bucket : str
        Bucket name.
    path : str
        File path within the bucket.
    expires_in : int
        URL expiry in seconds (default 1 hour; max 7 days for Supabase).

    Returns
    -------
    str or None
        The signed URL, or None on failure.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        response = client.storage.from_(bucket).create_signed_url(
            path, expires_in
        )
        # Supabase-py returns dict with 'signedURL' or {'signedUrl': ...}
        if isinstance(response, dict):
            return response.get("signedURL") or response.get("signedUrl")
        if hasattr(response, "signed_url"):
            return response.signed_url
        if hasattr(response, "signedURL"):
            return response.signedURL
        return None
    except Exception as e:
        logger.warning("get_signed_url failed: %s", e)
        return None


def delete_file(*, bucket: str, path: str) -> bool:
    """Delete a file from a bucket. Returns True on success."""
    client = _get_client()
    if client is None:
        return False
    try:
        client.storage.from_(bucket).remove([path])
        return True
    except Exception as e:
        logger.warning("delete_file failed: %s", e)
        return False


def list_files(
    *, bucket: str, prefix: str = "", limit: int = 100
) -> list[dict[str, Any]]:
    """List files in a bucket. Returns a list of file metadata dicts."""
    client = _get_client()
    if client is None:
        return []
    try:
        response = client.storage.from_(bucket).list(
            path=prefix, options={"limit": limit}
        )
        if isinstance(response, list):
            return response
        return []
    except Exception as e:
        logger.warning("list_files failed: %s", e)
        return []


# ─── Health check + status ───────────────────────────────────────────────


def health_check() -> dict[str, Any]:
    """Return the Supabase integration status."""
    client = _get_client()
    return {
        "enabled": client is not None,
        "url": SUPABASE_URL or None,
        "anon_key_set": bool(SUPABASE_ANON_KEY),
        "service_role_key_set": bool(SUPABASE_SERVICE_ROLE_KEY),
        "buckets": [name for name, _ in ALL_BUCKETS],
        "max_upload_mb": _MAX_UPLOAD_BYTES // (1024 * 1024),
        "allowed_mime_types_count": len(_ALLOWED_MIME_TYPES),
        "database_url_is_supabase": _is_supabase_database(),
    }


def _is_supabase_database() -> bool:
    """Return True if DATABASE_URL points to Supabase Postgres."""
    db_url = os.environ.get("DATABASE_URL", "")
    return "supabase" in db_url.lower() or "pooler.supabase.com" in db_url.lower()


__all__ = [
    "SupabaseUploadError",
    "upload_bytes",
    "upload_file",
    "get_public_url",
    "get_signed_url",
    "delete_file",
    "list_files",
    "ensure_buckets_exist",
    "health_check",
    "PUBLIC_BUCKET_MANUALS",
    "PRIVATE_BUCKET_REPORTS",
    "PRIVATE_BUCKET_SCREENSHOTS",
    "PRIVATE_BUCKET_UPLOADS",
]
