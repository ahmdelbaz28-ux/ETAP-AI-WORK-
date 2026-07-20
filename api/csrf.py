"""
CSRF Protection for AhmedETAP Engineering Service API.

Provides token-based CSRF protection for state-changing endpoints.

Architecture
------------
Current: JWT stored in localStorage → CSRF risk is low (no automatic cookie
inclusion). However, ``allow_credentials=True`` is set in CORS when specific
origins are configured, which means if cookies are introduced later the API
becomes vulnerable to CSRF.

This module implements defense-in-depth:
  1. A signed CSRF token (HMAC-SHA256) that the frontend includes in the
     ``X-CSRF-Token`` header on all mutating requests (POST/PUT/PATCH/DELETE).
  2. An opt-in ``X-CSRF-Token: bypass`` for API clients that don't use cookies.
  3. ``SameSite=Strict`` cookie documentation so if cookies are ever introduced
     they default to Strict.
  4. A ``/api/v1/csrf/token`` endpoint for the frontend to obtain fresh tokens.

Usage
-----
In the FastAPI app::

    from api.csrf import CSRFMiddleware, csrf_router
    app.add_middleware(CSRFMiddleware)
    app.include_router(csrf_router)

The frontend should call ``GET /api/v1/csrf/token`` once (e.g. at login) and
include the returned token in the ``X-CSRF-Token`` header of every
state-changing request.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("api.csrf")

# ─── Constants ────────────────────────────────────────────────────────────────

_CSRF_SALT_LENGTH = 32  # bytes of random salt per token
_CSRF_TOKEN_TTL = 3600  # seconds (1 hour)
_CSRF_HEADER = "x-csrf-token"
_BYPASS_VALUE = "bypass"  # API clients can opt-out

# Default secret — must be overridden in production via CSRF_SECRET env var
_DEFAULT_SECRET = "change-me-csrf-secret-in-production"


# ─── Token helpers ────────────────────────────────────────────────────────────


def _get_secret() -> str:
    """Return the CSRF signing secret.

    Falls back to ``SECRET_KEY`` then ``JWT_SECRET_KEY`` for environments that
    already have one configured, so deployments don't need yet another env var.
    """
    secret = (
        os.environ.get("CSRF_SECRET")
        or os.environ.get("SECRET_KEY")
        or os.environ.get("JWT_SECRET_KEY")
        or _DEFAULT_SECRET
    )
    return secret


def generate_csrf_token() -> str:
    """Generate a time-limited signed CSRF token.

    Format: ``<expiry_timestamp>.<salt>.<signature>`` where signature is
    HMAC-SHA256 of ``expiry_timestamp`` + ``salt``.
    """
    secret = _get_secret()
    expires = int(time.time()) + _CSRF_TOKEN_TTL
    salt = secrets.token_hex(_CSRF_SALT_LENGTH)
    message = f"{expires}.{salt}"
    sig = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{message}.{sig}"


def validate_csrf_token(token: str, *, tolerate_expired: bool = False) -> str:
    """Validate a CSRF token.

    Returns one of:
      ``"valid"``          — token is current and correctly signed.
      ``"expired"``        — signature is valid but token has expired
                             (only returned when ``tolerate_expired=True``).
      ``"invalid"``        — signature mismatch or malformed payload.

    The caller must decide whether to accept expired tokens (e.g. for
    long-running operations).
    """
    try:
        expires_str, salt, sig = token.split(".")
        message = f"{expires_str}.{salt}"
        secret = _get_secret()

        expected_sig = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, sig):
            return "invalid"

        expires = int(expires_str)
        if time.time() > expires:
            if tolerate_expired:
                return "expired"
            return "invalid"

        return "valid"
    except (ValueError, AttributeError, TypeError):
        return "invalid"


# ─── Middleware ────────────────────────────────────────────────────────────────

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class CSRFMiddleware(BaseHTTPMiddleware):
    """Protect state-changing endpoints from CSRF attacks.

    Sits *before* the route handler and validates the ``X-CSRF-Token`` header
    for all POST, PUT, PATCH, and DELETE requests.

    Bypass mechanisms (in order):
      1. API key authentication (``X-API-Key`` header with known key) —
         assumed to be server-to-server, not browser-originated.
      2. Explicit ``X-CSRF-Token: bypass`` header — for documented API clients
         that do not use cookies.
      3. Skipped entirely when ``AUTH_DISABLED=true`` in development.
    """

    def __init__(self, app: Any, *, tolerate_expired: bool = False) -> None:
        super().__init__(app)
        self._tolerate_expired = tolerate_expired
        self._api_key = os.environ.get("ENGINEERING_SERVICE_API_KEY", "")
        self._auth_disabled = os.environ.get(
            "ENGINEERING_SERVICE_AUTH_DISABLED", ""
        ).lower() in ("1", "true", "yes")

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> JSONResponse:
        # Only validate mutating methods
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        # Skip CSRF check for API-key-authenticated clients (server-to-server)
        if self._api_key:
            provided_key = request.headers.get("x-api-key", "")
            if hmac.compare_digest(provided_key, self._api_key):
                return await call_next(request)

        # Skip when auth is disabled (local development only)
        if self._auth_disabled:
            _env = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development"))
            if _env.lower() in ("development", "dev"):
                return await call_next(request)

        # Validate CSRF token
        token = request.headers.get(_CSRF_HEADER, "")
        if token == _BYPASS_VALUE:
            return await call_next(request)

        status = validate_csrf_token(token, tolerate_expired=self._tolerate_expired)
        if status != "valid":
            logger.warning(
                "CSRF validation failed: %s — %s %s",
                status,
                request.method,
                request.url.path,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        f"CSRF token missing or invalid ({status}). "
                        "Include a valid X-CSRF-Token header or use "
                        "X-CSRF-Token: bypass for API-only clients. "
                        "Call GET /api/v1/csrf/token to obtain a fresh token."
                    ),
                },
            )

        return await call_next(request)


# ─── Router ───────────────────────────────────────────────────────────────────

csrf_router = APIRouter(tags=["csrf"])


@csrf_router.get("/api/v1/csrf/token")
async def get_csrf_token() -> dict[str, str]:
    """Return a fresh CSRF token.

    The frontend should call this once (e.g. after login) and include the
    returned token in the ``X-CSRF-Token`` header of every state-changing
    request.

    The token is HMAC-signed and expires after ``CSRF_TOKEN_TTL`` seconds
    (default: 1 hour).
    """
    return {"token": generate_csrf_token()}
