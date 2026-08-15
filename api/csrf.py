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
  2. ``SameSite=Strict`` cookie documentation so if cookies are ever introduced
     they default to Strict.
  3. A ``/api/v1/csrf/token`` endpoint for the frontend to obtain fresh tokens.

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

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from api.environment import auth_disabled_allowed

logger = logging.getLogger("api.csrf")

# ─── Constants ────────────────────────────────────────────────────────────────

_CSRF_SALT_LENGTH = 32  # bytes of random salt per token
_CSRF_TOKEN_TTL = 3600  # seconds (1 hour)
_CSRF_HEADER = "x-csrf-token"
# _BYPASS_VALUE removed — see SECURITY AUDIT 2026-07-25.
# The literal "bypass" string allowed any origin to bypass CSRF protection.
# API-key-authenticated clients are handled by the X-API-Key check above.

# Placeholder used ONLY to detect that no secret was configured. NEVER used
# to actually sign tokens — `_get_secret()` raises in production if no
# env var is set, and logs a warning in development when falling back to a
# per-process random key.
_SENTINEL_DEFAULT = "change-me-csrf-secret-in-production"

# Development-only random secret, generated ONCE per process and cached.
# SECURITY FIX (2026-08-06): previously `_get_secret()` generated a fresh
# random key on every call, so `generate_csrf_token()` signed with secret A
# while `validate_csrf_token()` recomputed with a new secret B — every
# token was rejected as invalid, breaking all state-changing endpoints in
# development (no CSRF_SECRET configured). Caching the key per-process
# makes generation and validation use the same secret.
_dev_random_secret: str = ""


def _is_production_env() -> bool:
    """Return True when running in a production-like environment."""
    env = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
    return env in ("production", "prod", "staging")


# ─── Token helpers ────────────────────────────────────────────────────────────


def _get_secret() -> str:
    """Return the CSRF signing secret.

    Falls back to ``SECRET_KEY`` then ``JWT_SECRET_KEY`` for environments that
    already have one configured, so deployments don't need yet another env var.

    SECURITY: In production/staging, raises RuntimeError if NO secret is
    configured via env var. A known-default secret in a public repo would
    allow attackers to forge CSRF tokens and bypass protection entirely.
    In development, falls back to a per-process random key (logged).
    """
    secret = (
        os.environ.get("CSRF_SECRET")
        or os.environ.get("SECRET_KEY")
        or os.environ.get("JWT_SECRET_KEY")
    )
    if secret:
        return secret

    if _is_production_env():
        raise RuntimeError(
            "CSRF_SECRET (or SECRET_KEY or JWT_SECRET_KEY) MUST be set in "
            "production/staging. The default placeholder secret is public "
            "and would allow CSRF token forgery. "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    # Development only: per-process random key (not stable across restarts,
    # but at least not the publicly known placeholder). Generated once and
    # cached so token generation and validation share the same secret.
    global _dev_random_secret
    if not _dev_random_secret:
        import secrets as _secrets

        _dev_random_secret = _secrets.token_hex(32)
        logger.warning(
            "CSRF_SECRET not set — generated per-process random key. "
            "CSRF tokens will NOT survive a restart. Set CSRF_SECRET in production."
        )
    return _dev_random_secret


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
      2. Skipped entirely when ``AUTH_DISABLED=true`` in development.
    """

    def __init__(self, app: Any, *, tolerate_expired: bool = False) -> None:
        super().__init__(app)
        self._tolerate_expired = tolerate_expired
        self._api_key = os.environ.get("ENGINEERING_SERVICE_API_KEY", "")
        self._auth_disabled = auth_disabled_allowed()

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

        # Skip when auth is disabled (local development & test environments only).
        # auth_disabled_allowed() already fail-closes outside the dev allow-list.
        if self._auth_disabled:
            return await call_next(request)

        # Validate CSRF token
        token = request.headers.get(_CSRF_HEADER, "")
        # SECURITY: CSRF bypass removed per audit finding S-01.
        # All state-changing requests must present a valid signed CSRF token.

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
                        "Include a valid X-CSRF-Token header. "
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

