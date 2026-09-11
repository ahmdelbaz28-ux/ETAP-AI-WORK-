"""
api/rate_limit.py — Rate limiting configuration using SlowAPI.

Provides configured Limiter instances for authentication and general API endpoints.
Uses Redis backend when available, otherwise falls back gracefully to in-memory storage.
"""

from __future__ import annotations

import os

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

_REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
_REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
_REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")
_REDIS_URL = os.environ.get("REDIS_URL", "").strip()

if not _REDIS_URL and os.environ.get("USE_REDIS_RATE_LIMIT", "false").lower() == "true":
    if _REDIS_PASSWORD:
        _REDIS_URL = f"redis://:{_REDIS_PASSWORD}@{_REDIS_HOST}:{_REDIS_PORT}/0"
    else:
        _REDIS_URL = f"redis://{_REDIS_HOST}:{_REDIS_PORT}/0"

_STORAGE_URI = _REDIS_URL if _REDIS_URL.startswith(("redis://", "rediss://")) else "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_STORAGE_URI,
    strategy="moving-window",
)

# Auth endpoints: 10 requests per minute
auth_limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_STORAGE_URI,
    default_limits=["10/minute"],
    strategy="moving-window",
)

__all__ = [
    "limiter",
    "auth_limiter",
    "SlowAPIMiddleware",
    "RateLimitExceeded",
    "_rate_limit_exceeded_handler",
]
