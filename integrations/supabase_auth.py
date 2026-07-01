"""
Supabase Auth helpers for AhmedETAP (optional social login).

This module provides OPTIONAL Supabase Auth integration. The existing
bcrypt/JWT auth in ``api/auth.py`` continues to work unchanged. This
module adds support for:

1. **Social login** (Google, GitHub, etc.) — Supabase Auth handles the
   OAuth flow; we verify the Supabase JWT and create/link a local user.
2. **Magic-link email login** — passwordless email login via Supabase.
3. **Session validation** — verify that a Supabase access token is valid.

Usage
-----
::

    from integrations.supabase_auth import (
        verify_supabase_token,
        get_oauth_url,
        exchange_oauth_code,
    )

    # 1. Frontend redirects user to OAuth provider via Supabase
    url = get_oauth_url(provider="google", redirect_to="https://app/callback")

    # 2. User comes back with a Supabase access token
    user_info = verify_supabase_token(access_token)

Safety
------
- Supabase tokens are verified via the Supabase Auth API (not locally),
  so we trust the verdict.
- The local user record is created on first login with a random bcrypt
  password (so the account cannot be accessed via local login — only via
  the OAuth provider).
- This module is OFF by default. Set ``SUPABASE_AUTH_ENABLED=true`` to
  enable social login.
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_AUTH_ENABLED = os.environ.get(
    "SUPABASE_AUTH_ENABLED", "false"
).lower() in ("1", "true", "yes", "on")


class SupabaseAuthError(ValueError):
    """Raised when a Supabase Auth operation fails."""


def _check_enabled() -> None:
    """Raise if Supabase Auth is disabled."""
    if not SUPABASE_AUTH_ENABLED:
        raise SupabaseAuthError(
            "Supabase Auth is disabled. Set SUPABASE_AUTH_ENABLED=true to enable."
        )
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise SupabaseAuthError(
            "SUPABASE_URL and SUPABASE_ANON_KEY must be set for Supabase Auth."
        )


# ─── Token verification ─────────────────────────────────────────────────


def verify_supabase_token(access_token: str) -> dict[str, Any]:
    """Verify a Supabase access token and return the user info.

    Calls the Supabase Auth ``/auth/v1/user`` endpoint with the access
    token. Returns the user dict if valid, raises SupabaseAuthError if
    invalid or expired.

    Parameters
    ----------
    access_token : str
        The Supabase JWT access token (from the frontend).

    Returns
    -------
    dict
        User info: ``{"id": ..., "email": ..., "user_metadata": {...},
        "app_metadata": {...}, "created_at": ...}``
    """
    _check_enabled()
    try:
        r = httpx.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {access_token}",
            },
            timeout=10,
        )
        if r.status_code != 200:
            raise SupabaseAuthError(
                f"Invalid Supabase token (status {r.status_code}): {r.text[:200]}"
            )
        return r.json()
    except httpx.HTTPError as e:
        raise SupabaseAuthError(f"Supabase Auth unreachable: {e}") from e


# ─── OAuth flow ─────────────────────────────────────────────────────────


def get_oauth_url(
    *,
    provider: str,
    redirect_to: str,
    scopes: Optional[list[str]] = None,
) -> str:
    """Return the URL to redirect the user to for OAuth login.

    Parameters
    ----------
    provider : str
        OAuth provider: ``"google"``, ``"github"``, ``"azure"``,
        ``"facebook"``, ``"twitter"``, etc. (must be enabled in the
        Supabase dashboard).
    redirect_to : str
        URL to redirect to after the OAuth flow completes. Supabase will
        append ``?access_token=...&refresh_token=...`` to this URL.
    scopes : list[str], optional
        Additional OAuth scopes to request.

    Returns
    -------
    str
        The URL to redirect the user's browser to.
    """
    _check_enabled()
    # Build the OAuth URL — Supabase handles the actual OAuth dance.
    # We use the GET /auth/v1/authorize endpoint.
    params = {
        "provider": provider,
        "redirect_to": redirect_to,
    }
    if scopes:
        params["scopes"] = " ".join(scopes)

    # Use httpx to build the URL with proper encoding
    import urllib.parse

    query = urllib.parse.urlencode(params)
    return f"{SUPABASE_URL}/auth/v1/authorize?{query}"


# ─── Magic-link email login ─────────────────────────────────────────────


def send_magic_link(*, email: str, redirect_to: str) -> bool:
    """Send a passwordless magic-link login email.

    Parameters
    ----------
    email : str
        The user's email address.
    redirect_to : str
        URL to redirect to after the user clicks the link.

    Returns
    -------
    bool
        True if the email was sent, False on failure.
    """
    _check_enabled()
    try:
        r = httpx.post(
            f"{SUPABASE_URL}/auth/v1/otp",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Content-Type": "application/json",
            },
            json={"email": email, "redirect_to": redirect_to},
            timeout=10,
        )
        return r.status_code == 200
    except httpx.HTTPError as e:
        logger.warning("Magic-link send failed: %s", e)
        return False


# ─── Local user creation (for first OAuth login) ────────────────────────


def link_or_create_local_user(
    supabase_user: dict[str, Any],
    *,
    local_user_creator: Optional[callable] = None,
) -> dict[str, Any]:
    """Link a Supabase user to a local user, creating one if needed.

    This is a HOOK — the actual local user creation depends on your
    user model. Pass a ``local_user_creator`` callable that takes
    ``(email, random_password)`` and returns the local user record.

    Parameters
    ----------
    supabase_user : dict
        The user info returned by ``verify_supabase_token``.
    local_user_creator : callable, optional
        Function to create a local user if one doesn't exist. Receives
        ``(email, random_password)`` and returns the local user record.
        If None, just returns the Supabase user info.

    Returns
    -------
    dict
        ``{"supabase_id": ..., "email": ..., "local_user": ... or None,
           "created": bool}``
    """
    email = supabase_user.get("email")
    if not email:
        raise SupabaseAuthError("Supabase user has no email")

    supabase_id = supabase_user.get("id", "")

    # If the caller provided a local_user_creator, use it
    if local_user_creator is not None:
        # Generate a random 32-byte password — the local account can
        # only be accessed via Supabase OAuth (not via local login)
        random_password = secrets.token_urlsafe(32)
        try:
            local_user = local_user_creator(email, random_password)
            created = True
        except Exception as e:
            logger.warning("Local user creation failed: %s", e)
            local_user = None
            created = False
    else:
        local_user = None
        created = False

    return {
        "supabase_id": supabase_id,
        "email": email,
        "local_user": local_user,
        "created": created,
    }


# ─── Health check ───────────────────────────────────────────────────────


def health_check() -> dict[str, Any]:
    """Return the Supabase Auth integration status."""
    return {
        "enabled": SUPABASE_AUTH_ENABLED,
        "url": SUPABASE_URL or None,
        "anon_key_set": bool(SUPABASE_ANON_KEY),
    }


__all__ = [
    "SupabaseAuthError",
    "verify_supabase_token",
    "get_oauth_url",
    "send_magic_link",
    "link_or_create_local_user",
    "health_check",
]
