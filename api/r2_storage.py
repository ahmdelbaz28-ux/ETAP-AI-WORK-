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
from datetime import timedelta
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


# ---------------------------------------------------------------------------
# Lazy boto3 import (only when R2 is actually used)
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    """Return a cached boto3 S3 client configured for R2."""
    global _client
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
    await asyncio.get_event_loop().run_in_executor(
        None, lambda: client.put_object(**put_kwargs)
    )
    logger.info("R2 upload: %s (%d bytes, %s)", key, len(data), content_type)
    return key


async def download(key: str) -> bytes:
    """Download an object from R2 and return its contents as bytes."""
    if not R2_ENABLED:
        raise RuntimeError("R2 is not configured")

    client = _get_client()
    response = await asyncio.get_event_loop().run_in_executor(
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

    client = _get_client()
    await asyncio.get_event_loop().run_in_executor(
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

    client = _get_client()
    response = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: client.list_objects_v2(
            Bucket=R2_BUCKET_NAME,
            Prefix=prefix,
            MaxKeys=limit,
        ),
    )
    objects = []
    for obj in response.get("Contents", []):
        objects.append({
            "key": obj["Key"],
            "size": obj["Size"],
            "last_modified": obj["LastModified"].isoformat() if obj.get("LastModified") else None,
            "etag": obj.get("ETag", "").strip('"'),
        })
    return objects


async def delete_many(keys: list[str]) -> int:
    """Delete multiple objects in a single request. Returns count deleted."""
    if not R2_ENABLED:
        raise RuntimeError("R2 is not configured")
    if not keys:
        return 0

    client = _get_client()
    # R2 supports up to 1000 keys per delete_batch request
    deleted_total = 0
    for i in range(0, len(keys), 1000):
        batch = keys[i:i + 1000]
        response = await asyncio.get_event_loop().run_in_executor(
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
