"""
api/_cdn_base.py — Shared helpers for Akamai and Cloudflare CDN protection.

Extracted from api/akamai_protection.py and api/cloudflare_protection.py
to eliminate duplicated code (SonarCloud new_duplicated_lines_density).

Both CDN modules had identical implementations of:
  - _verify_origin_secret()
  - _rate_limit_check()
  - log_security_event()
  - _parse_int()

This module provides those helpers in a CDN-provider-agnostic way, so each
module only needs its provider-specific configuration and middleware logic.
"""
from __future__ import annotations

import hmac
import logging
from typing import Any, Optional

from fastapi import Request

logger = logging.getLogger(__name__)


def verify_origin_secret(request: Request, secret: str) -> bool:
    """Verify the X-Origin-Verify header against the configured CDN secret.

    Uses constant-time comparison to prevent timing attacks. Returns
    True if:
      - No secret is configured (dev mode → always passes), OR
      - The header matches the secret exactly.

    Parameters
    ----------
    request : Request
        The incoming FastAPI request.
    secret : str
        The origin verification secret (e.g., AKAMAI_ORIGIN_SECRET or
        CLOUDFLARE_ORIGIN_SECRET). Empty string = dev mode (always passes).
    """
    if not secret:
        return True  # dev mode — no secret configured
    provided = request.headers.get("x-origin-verify", "")
    return hmac.compare_digest(provided, secret)


def parse_int_header(value: Optional[str]) -> Optional[int]:
    """Parse an optional integer header value. Returns None on failure.

    Used by both Akamai (bot score) and Cloudflare (status codes) to
    safely parse numeric CDN headers.
    """
    if not value:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def rate_limit_check(client_ip: str, rate_limiter: Any) -> bool:
    """Sliding-window rate limit per client IP. Returns True if allowed.

    Delegates to a ``RateLimiter`` instance (from ``api._rate_limit``).
    Each CDN module passes its own limiter instance, keeping per-module
    rate limit configuration independent.

    Parameters
    ----------
    client_ip : str
        The real client IP (extracted by get_client_ip).
    rate_limiter : RateLimiter
        The module-specific rate limiter instance.
    """
    return rate_limiter.is_allowed(client_ip)


def log_security_event(
    request: Request,
    event_type: str,
    *,
    detail: str = "",
    severity: str = "info",
    metadata_attr: str = "",
    extra_log_fields: str = "",
) -> None:
    """Log a structured security event with CDN metadata.

    Called by route handlers when they detect suspicious activity that
    the CDN middleware didn't catch (e.g., a valid JWT user trying to
    access another user's data). The log includes the CDN request ID
    so SIEM correlation with CDN logs is possible.

    Parameters
    ----------
    request : Request
        The incoming FastAPI request.
    event_type : str
        Type of security event (e.g., "unauthorized_access").
    detail : str
        Human-readable description (truncated to 200 chars).
    severity : str
        Log severity: "info" or "warning".
    metadata_attr : str
        The request.state attribute name holding CDN metadata
        (e.g., "akamai" or "cloudflare").
    extra_log_fields : str
        Additional fields to append to the log message (provider-specific).
    """
    metadata = getattr(request.state, metadata_attr, {}) or {}
    log_level = logging.WARNING if severity == "warning" else logging.INFO
    base_msg = (
        f"security_event: type={event_type} severity={severity} "
        f"detail={detail[:200]} client_ip={metadata.get('client_ip', '?')}"
    )
    if extra_log_fields:
        base_msg += f" {extra_log_fields}"
    logger.log(log_level, base_msg)
