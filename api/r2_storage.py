"""
api/r2_storage.py — Cloudflare R2 object storage integration.

Provides a simple interface for uploading, downloading, and managing files
in Cloudflare R2 buckets. Used for storing:
  - User-uploaded project files (grid configs, study inputs)
  - Generated reports (PDF exports, study results)
  - ETAP simulation outputs
  - Large analysis artifacts that don't fit in Postgres

R2 is S3-compatible — this module uses boto3 (AWS SDK) configured for
R2's S3-compatible endpoint. This avoids needing the Cloudflare Workers
API for every file operation.

Environment variables
---------------------
R2_ACCOUNT_ID           — Cloudflare account ID (e.g., 8ea129...)
R2_ACCESS_KEY_ID        — R2 API token with Object Read & Write
R2_SECRET_ACCESS_KEY    — R2 API token secret
R2_BUCKET_NAME          — Default bucket name (e.g., ahmedetap-storage)
R2_ENDPOINT_URL         — Auto-derived: https://<account_id>.r2.cloudflarestorage.com

Usage
-----
    from api.r2_storage import r2

    # Upload a file
    url = await r2.upload("reports/study-123.pdf", pdf_bytes, "application/pdf")

    # Download a file
    data = await r2.download("reports/study-123.pdf")

    # Delete a file
    await r2.delete("reports/study-123.pdf")

    # List files in a prefix
    files = await r2.list("reports/", limit=100)

    # Generate a presigned URL (valid for 1 hour)
    url = r2.presign("reports/study-123.pdf", expires=3600)
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME: str = os.getenv("R2_BUCKET_NAME", "ahmedetap-storage")

# R2's S3-compatible endpoint
R2_ENDPOINT_URL: str = os.getenv(
    "R2_ENDPOINT_URL",
    f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com" if R2_ACCOUNT_ID else "",
)

# Public access URL prefix (if a custom domain is configured for the bucket)
# E.g., https://storage.ahmed.net → files served publicly from this URL
R2_PUBLIC_URL_PREFIX: str = os.getenv("R2_PUBLIC_URL_PREFIX", "")

# Whether R2 is configured (all required env vars present)
R2_ENABLED: bool = bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY)

# V-26: Allowed MIME types for upload — prevents uploading dangerous content
# like HTML (XSS), shell scripts (RCE), or executables.
ALLOWED_MIME_TYPES: set[str] = {
    "application/pdf",
    "application/json",
    "application/xml",
    "text/csv",
    "text/plain",
    "text/xml",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/svg+xml",
    "image/webp",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-word",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/zip",
    "application/x-yaml",
    "text/yaml",
    "application/octet-stream",  # generic binary — but validated by extension
}

# V-26: Dangerous MIME types that are ALWAYS blocked
BLOCKED_MIME_TYPES: set[str] = {
    "text/html",  # XSS vector
    "application/x-sh",  # Shell script
    "application/x-shellscript",  # Shell script
    "application/x-bash",  # Bash script
    "application/x-python",  # Python script
    "application/x-executable",  # Binary executable
    "application/x-dosexec",  # Windows executable
    "application/x-msdownload",  # Windows download
}

# V-53: Dangerous file extensions that are ALWAYS blocked
BLOCKED_EXTENSIONS: set[str] = {
    ".html", ".htm",          # XSS vector
    ".js", ".mjs",            # JavaScript — can execute in browser
    ".vbs", ".vbe",           # VBScript
    ".wsf", ".wsh",           # Windows Script Host
    ".bat", ".cmd",           # Windows batch
    ".ps1", ".psm1",          # PowerShell
    ".sh", ".bash",           # Shell scripts
    ".py", ".pyw",            # Python
    ".exe", ".dll",           # Windows executables
    ".msi", ".msp",           # Windows installers
    ".scr", ".com",           # Screensaver / DOS executable
    ".hta",                   # HTML Application (IE)
    ".lnk",                   # Windows shortcut
    ".svg",                   # SVG can contain JavaScript (XSS)
}

# V-27: Maximum upload size (100 MB by default)
MAX_UPLOAD_SIZE_BYTES: int = int(os.getenv("R2_MAX_UPLOAD_SIZE_MB", "100")) * 1024 * 1024


# SECURITY AUDIT 2026-07-25 — Fix S-10: Path traversal validation for R2 keys.
def _validate_key(key: str) -> str:
    """Validate an R2 object key for path traversal attacks.

    Rejects keys containing: '..' (directory traversal), absolute paths
    (starting with '/'), null bytes, or other dangerous patterns.

    Args:
        key: The object key to validate.

    Returns:
        The normalized key if valid.

    Raises:
        ValueError: If the key contains traversal patterns.
    """
    if not key or not isinstance(key, str):
        raise ValueError("R2 object key must be a non-empty string")

    # Reject null bytes
    if "\x00" in key:
        raise ValueError("R2 object key contains null bytes")

    # Reject directory traversal
    if ".." in key:
        raise ValueError("R2 object key contains directory traversal ('..')")

    # Reject absolute paths
    if key.startswith("/"):
        raise ValueError("R2 object key must not start with '/'")

    # Normalize and verify it doesn't escape after normalization
    import posixpath

    normalized = posixpath.normpath(key)
    if normalized.startswith("..") or normalized != key.replace("//", "/").rstrip("/"):
        raise ValueError("R2 object key normalizes to an unsafe path")

    return normalized


# ---------------------------------------------------------------------------
# Lazy boto3 import (only when R2 is actually used)
# ---------------------------------------------------------------------------

import threading

_client = None
_client_lock = threading.Lock()

# SECURITY: Maximum presigned URL expiry (7 days). Without this cap,
# a caller could generate a presigned URL valid for years, creating a
# persistent unauthenticated access vector to the object.
_PRESIGN_MAX_EXPIRY = 7 * 24 * 3600  # 7 days in seconds


def _get_client():
    """Return a cached boto3 S3 client configured for R2 (thread-safe)."""
    global _client
    # Double-checked locking: fast path (no lock) if client exists
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client

        if not R2_ENABLED:
            raise RuntimeError(
                "R2 is not configured. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
                "and R2_SECRET_ACCESS_KEY environment variables."
            )

        import boto3
        from botocore.config import Config

        _client = boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT_URL,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name="auto",  # R2 uses "auto" region
            config=Config(
                retries={"max_attempts": 3, "mode": "adaptive"},
                max_pool_connections=10,
            ),
        )
        logger.info("R2 client created: endpoint=%s, bucket=%s", R2_ENDPOINT_URL, R2_BUCKET_NAME)
        return _client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_r2_enabled() -> bool:
    """Return True if R2 storage is configured and ready to use."""
    return R2_ENABLED


async def upload(
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    *,
    metadata: Optional[dict[str, str]] = None,
    cache_control: Optional[str] = None,
) -> str:
    """Upload bytes to R2 and return the object key.

    Parameters
    ----------
    key : str
        Object key (path) in the bucket, e.g., "reports/study-123.pdf"
    data : bytes
        File content as bytes
    content_type : str
        MIME type (e.g., "application/pdf", "image/png")
    metadata : dict, optional
        Custom metadata key-value pairs stored with the object
    cache_control : str, optional
        Cache-Control header value (e.g., "public, max-age=31536000")

    Returns
    -------
    str
        The object key (use presign() to get a download URL)
    """
    if not R2_ENABLED:
        raise RuntimeError("R2 is not configured")

    key = _validate_key(key)  # SECURITY S-10: path traversal validation

    # V-53: Validate file extension — reject dangerous extensions
    key_lower = key.lower()
    for ext in BLOCKED_EXTENSIONS:
        if key_lower.endswith(ext):
            raise ValueError(
                f"Blocked file extension: {ext}. "
                f"This file type is not allowed for security reasons."
            )

    # V-26: Validate MIME type — reject dangerous content types
    content_type_lower = content_type.lower().strip()
    if content_type_lower in BLOCKED_MIME_TYPES:
        raise ValueError(
            f"Blocked MIME type: {content_type_lower}. "
            f"This file type is not allowed for security reasons."
        )
    if content_type_lower not in ALLOWED_MIME_TYPES:
        logger.warning(
            "r2_upload_unsupported_mime type=%s key=%s — proceeding with caution",
            content_type_lower, key[:50],
        )

    # V-27: Enforce maximum upload size
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(
            f"File too large: {len(data)} bytes exceeds maximum "
            f"of {MAX_UPLOAD_SIZE_BYTES} bytes ({MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB)"
        )

    client = _get_client()
    put_kwargs: dict[str, Any] = {
        "Bucket": R2_BUCKET_NAME,
        "Key": key,
        "Body": data,
        "ContentType": content_type,
    }
    if metadata:
        put_kwargs["Metadata"] = metadata
    if cache_control:
        put_kwargs["CacheControl"] = cache_control

    # boto3 is synchronous — run in a thread pool to not block the event loop
    await asyncio.get_running_loop().run_in_executor(None, lambda: client.put_object(**put_kwargs))
    logger.info("R2 upload: %s (%d bytes, %s)", key, len(data), content_type)
    return key


async def download(key: str) -> bytes:
    """Download an object from R2 and return its contents as bytes."""
    if not R2_ENABLED:
        raise RuntimeError("R2 is not configured")

    key = _validate_key(key)  # SECURITY S-10: path traversal validation

    client = _get_client()
    response = await asyncio.get_running_loop().run_in_executor(
        None,
        lambda: client.get_object(Bucket=R2_BUCKET_NAME, Key=key),
    )
    data = response["Body"].read()
    logger.info("R2 download: %s (%d bytes)", key, len(data))
    return data


async def delete(key: str) -> None:
    """Delete an object from R2."""
    if not R2_ENABLED:
        raise RuntimeError("R2 is not configured")

    key = _validate_key(key)  # SECURITY S-10: path traversal validation

    client = _get_client()
    await asyncio.get_running_loop().run_in_executor(
        None,
        lambda: client.delete_object(Bucket=R2_BUCKET_NAME, Key=key),
    )
    logger.info("R2 delete: %s", key)


async def list_objects(
    prefix: str = "",
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List objects in the bucket under a given prefix.

    Returns a list of dicts with keys: key, size, last_modified, etag.
    """
    if not R2_ENABLED:
        raise RuntimeError("R2 is not configured")

    # SECURITY: Bound limit to prevent abuse
    limit = max(1, min(limit, 1000))

    # SECURITY (S-10): Validate prefix against path traversal
    if prefix:
        _validate_key(prefix)

    client = _get_client()
    response = await asyncio.get_running_loop().run_in_executor(
        None,
        lambda: client.list_objects_v2(
            Bucket=R2_BUCKET_NAME,
            Prefix=prefix,
            MaxKeys=limit,
        ),
    )
    objects = []
    for obj in response.get("Contents", []):
        objects.append(
            {
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat()
                if obj.get("LastModified")
                else None,
                "etag": obj.get("ETag", "").strip('"'),
            }
        )
    return objects


async def delete_many(keys: list[str]) -> int:
    """Delete multiple objects in a single request. Returns count deleted."""
    if not R2_ENABLED:
        raise RuntimeError("R2 is not configured")
    if not keys:
        return 0

    # SECURITY (S-10): Validate all keys against path traversal
    for key in keys:
        _validate_key(key)

    client = _get_client()
    # R2 supports up to 1000 keys per delete_batch request
    deleted_total = 0
    for i in range(0, len(keys), 1000):
        batch = keys[i : i + 1000]
        response = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda b=batch: client.delete_objects(
                Bucket=R2_BUCKET_NAME,
                Delete={"Objects": [{"Key": k} for k in b], "Quiet": True},
            ),
        )
        deleted_total += len(response.get("Deleted", []))
    logger.info("R2 delete_many: %d/%d objects deleted", deleted_total, len(keys))
    return deleted_total


def presign(key: str, *, expires: int = 3600) -> str:
    """Generate a presigned URL for downloading an object.

    Parameters
    ----------
    key : str
        Object key
    expires : int
        URL validity in seconds (default: 1 hour, max: 7 days)

    Returns
    -------
    str
        Presigned HTTPS URL
    """
    if not R2_ENABLED:
        raise RuntimeError("R2 is not configured")

    # SECURITY (S-10): Validate key against path traversal
    _validate_key(key)

    # SECURITY: Cap presigned URL expiry to 7 days maximum.
    # Without this, a caller could generate URLs valid for years.
    if expires > _PRESIGN_MAX_EXPIRY:
        logger.warning(
            "presign_expiry_capped requested=%d max=%d key=%s",
            expires, _PRESIGN_MAX_EXPIRY, key[:50],
        )
        expires = _PRESIGN_MAX_EXPIRY
    if expires < 60:
        expires = 60  # Minimum 1 minute

    client = _get_client()
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET_NAME, "Key": key},
        ExpiresIn=expires,
    )
    return url


def public_url(key: str) -> str:
    """Return the public URL for an object (if a custom domain is configured).

    If R2_PUBLIC_URL_PREFIX is not set, returns a presigned URL instead.
    """
    key = _validate_key(key)  # SECURITY S-10: path traversal validation
    if R2_PUBLIC_URL_PREFIX:
        return f"{R2_PUBLIC_URL_PREFIX.rstrip('/')}/{key.lstrip('/')}"
    return presign(key)


def generate_key(
    *,
    prefix: str = "",
    extension: str = "",
    user_id: Optional[str] = None,
) -> str:
    """Generate a unique object key with optional prefix and user scope.

    Example:
        generate_key(prefix="reports", extension="pdf", user_id="abc123")
        → "reports/abc123/550e8400-e29b-41d4-a716-446655440000.pdf"
    """
    parts = []
    if prefix:
        parts.append(prefix.strip("/"))
    if user_id:
        parts.append(user_id)
    parts.append(str(uuid.uuid4()))
    key = "/".join(parts)
    if extension:
        key += f".{extension.lstrip('.')}"
    return key


# ---------------------------------------------------------------------------
# Convenience: bucket management (called once during setup)
# ---------------------------------------------------------------------------


def ensure_bucket_exists() -> bool:
    """Create the default R2 bucket if it doesn't exist.

    Called once during application startup. Returns True if the bucket
    exists (or was created), False if R2 is not configured.
    """
    if not R2_ENABLED:
        return False

    client = _get_client()
    try:
        client.head_bucket(Bucket=R2_BUCKET_NAME)
        logger.info("R2 bucket exists: %s", R2_BUCKET_NAME)
        return True
    except client.exceptions.ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "404":
            # Bucket doesn't exist — create it
            client.create_bucket(Bucket=R2_BUCKET_NAME)
            logger.info("R2 bucket created: %s", R2_BUCKET_NAME)
            return True
        raise
