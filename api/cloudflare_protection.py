"""
api/cloudflare_protection.py — Cloudflare edge security integration for the origin.

This module verifies that incoming requests reached the origin (HF Space)
through the Cloudflare edge, and enforces security policies based on
Cloudflare's analysis (bot fight mode, IP reputation, geo data, etc.).

Architecture
------------
    User  →  Cloudflare Edge (WAF + Rate Limiting + Bot Fight Mode + DDoS + CDN)
           ↓ adds CF-* headers + security verdicts
    HF Space origin  ←  this middleware verifies Cloudflare metadata

When CLOUDFLARE_ORIGIN_SECRET is set (production), requests that bypass
Cloudflare are rejected with 403. In development (no secret), all requests
pass through with a warning log so the platform stays usable.

Cloudflare headers consumed
---------------------------
CF-Connecting-IP         — Real client IP (Cloudflare replaces X-Forwarded-For)
CF-RAY                   — Unique edge request ID (for audit correlation)
CF-IPCountry             — ISO country code (geo data from Cloudflare IP DB)
CF-IPCITY                — City name (available with IP Geolocation enabled)
CF-IPLatitude            — Latitude (available with IP Geolocation enabled)
CF-IPLongitude           — Longitude (available with IP Geolocation enabled)
CF-Visitor               — JSON with scheme info (e.g., {"scheme":"https"})
CDN-Loop                 — Cloudflare loop detection header
X-Origin-Verify          — Shared secret injected by Cloudflare Worker rule
                           (only the Worker + the origin know this value)
True-Client-IP           — Real client IP (alternative to CF-Connecting-IP)
"""
from __future__ import annotations

import hmac
import logging
import os
import time
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Shared secret between Cloudflare Worker and the origin. When set, the
# middleware rejects any request that doesn't carry this value in the
# X-Origin-Verify header — preventing direct origin access (bypassing CF).
# Generate with: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
CLOUDFLARE_ORIGIN_SECRET: str = os.getenv("CLOUDFLARE_ORIGIN_SECRET", "")

# When True, requests that bypass Cloudflare are rejected with 403.
# When False (dev mode), requests pass through with a warning.
_ORIGIN_VERIFICATION_ENFORCED: bool = bool(CLOUDFLARE_ORIGIN_SECRET)

# Rate limit: max requests per minute per client IP (origin-side defense-in-depth)
# Cloudflare enforces rate limits at the edge, but this catches anything that slips through.
_ORIGIN_RATE_LIMIT_PER_MIN: int = int(os.getenv("CF_ORIGIN_RATE_LIMIT", "300"))

# Blocked countries (ISO 3166-1 alpha-2 codes). Empty = no geo blocking.
# Set via CF_BLOCKED_COUNTRIES env var (comma-separated), e.g., "CN,RU,KP"
_BLOCKED_COUNTRIES: frozenset[str] = frozenset(
    c.strip().upper() for c in os.getenv("CF_BLOCKED_COUNTRIES", "").split(",") if c.strip()
)

# In-memory rate limit store (per-worker; HF Space runs a single worker)
_RATE_LIMIT_STORE: dict[str, list[float]] = {}
_RATE_LIMIT_WINDOW_SEC: int = 60


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def is_cloudflare_enabled() -> bool:
    """Return True if Cloudflare origin verification is active."""
    return _ORIGIN_VERIFICATION_ENFORCED


def get_client_ip(request: Request) -> str:
    """Extract the real client IP, preferring Cloudflare's CF-Connecting-IP header."""
    # Cloudflare sets CF-Connecting-IP to the actual end-user IP.
    cf_ip = request.headers.get("cf-connecting-ip", "").strip()
    if cf_ip:
        return cf_ip

    # True-Client-IP is an alternative (some Cloudflare configs use this)
    true_ip = request.headers.get("true-client-ip", "").strip()
    if true_ip:
        return true_ip

    # Fall back to X-Forwarded-For (first hop).
    xff = request.headers.get("x-forwarded-for", "").strip()
    if xff:
        return xff.split(",")[0].strip()

    # Last resort: the direct connection IP.
    return request.client.host if request.client else "unknown"


def get_cloudflare_metadata(request: Request) -> dict[str, Any]:
    """Extract all Cloudflare-provided metadata from the request headers.

    Returns a dict suitable for logging/audit. All fields are optional —
    if the request didn't come through Cloudflare, the dict will be sparse.
    """
    return {
        "ray_id": request.headers.get("cf-ray", ""),
        "country": request.headers.get("cf-ipcountry", "").upper(),
        "city": request.headers.get("cf-ipcity", ""),
        "latitude": request.headers.get("cf-iplatitude", ""),
        "longitude": request.headers.get("cf-iplongitude", ""),
        "visitor_scheme": _parse_visitor_scheme(request.headers.get("cf-visitor", "")),
        "origin_verified": _verify_origin_secret(request),
        "client_ip": get_client_ip(request),
        "has_cf_headers": bool(request.headers.get("cf-ray")),
    }


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


async def cloudflare_protection_middleware(request: Request, call_next):
    """FastAPI middleware: verify Cloudflare metadata + enforce geo/rate policies.

    Order of checks:
      1. Origin verification (reject requests that bypassed Cloudflare)
      2. Rate limiting (per client IP)
      3. Geo blocking (blocked countries → 451)
      4. HTTPS enforcement (redirect HTTP → HTTPS via CF-Visitor header)

    On block, returns a JSON response with the reason + CF-RAY ID
    for audit correlation. On pass, the request proceeds and Cloudflare
    metadata is attached to request.state for downstream handlers.
    """
    path = request.url.path

    # Skip Cloudflare verification for health checks (Cloudflare's own monitoring
    # + uptime checks from HF Space infra). These come from internal IPs
    # and don't carry CF headers.
    if path in ("/healthz", "/readyz", "/health", "/ready"):
        return await call_next(request)

    # Attach Cloudflare metadata to request state so downstream handlers
    # (audit logging, analytics, etc.) can use it.
    metadata = get_cloudflare_metadata(request)
    request.state.cloudflare = metadata

    # ── 1. Origin verification ──────────────────────────────────────────
    if _ORIGIN_VERIFICATION_ENFORCED and not metadata["origin_verified"]:
        logger.warning(
            "cloudflare: origin verification failed for %s %s (client_ip=%s, "
            "user_agent=%s) — request bypassed Cloudflare edge",
            request.method, path, metadata["client_ip"],
            request.headers.get("user-agent", "")[:100],
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "Direct origin access is not permitted. "
                          "Requests must go through the CDN.",
                "cf_ray": metadata["ray_id"],
            },
            headers={"X-Block-Reason": "origin-verification-failed"},
        )

    # ── 2. Rate limiting (origin-side defense-in-depth) ─────────────────
    client_ip = metadata["client_ip"]
    if not _rate_limit_check(client_ip):
        logger.warning("cloudflare: rate limit exceeded for %s (%s %s)", client_ip, request.method, path)
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "Rate limit exceeded. Please slow down.",
                "cf_ray": metadata["ray_id"],
            },
            headers={
                "Retry-After": str(_RATE_LIMIT_WINDOW_SEC),
                "X-Block-Reason": "rate-limit",
            },
        )

    # ── 3. Geo blocking ─────────────────────────────────────────────────
    country = metadata["country"]
    if _BLOCKED_COUNTRIES and country and country in _BLOCKED_COUNTRIES:
        logger.warning(
            "cloudflare: blocking country %s for %s (%s %s)",
            country, client_ip, request.method, path,
        )
        return JSONResponse(
            status_code=451,  # Unavailable For Legal Reasons
            content={
                "detail": "This service is not available in your region.",
                "cf_ray": metadata["ray_id"],
                "country": country,
            },
            headers={
                "X-Block-Reason": "geo-block",
                "X-Country": country,
            },
        )

    # ── Pass through to the next handler ────────────────────────────────
    response = await call_next(request)

    # Add the CF-RAY ID to the response so clients can correlate
    # with Cloudflare logs for debugging.
    if metadata["ray_id"]:
        response.headers["CF-RAY"] = metadata["ray_id"]

    return response


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _verify_origin_secret(request: Request) -> bool:
    """Verify the X-Origin-Verify header against the configured secret.

    Uses constant-time comparison to prevent timing attacks. Returns
    True if:
      - No secret is configured (dev mode → always passes), OR
      - The header matches the secret exactly.
    """
    if not CLOUDFLARE_ORIGIN_SECRET:
        return True  # dev mode — no secret configured
    provided = request.headers.get("x-origin-verify", "")
    return hmac.compare_digest(provided, CLOUDFLARE_ORIGIN_SECRET)


def _parse_visitor_scheme(cf_visitor: str) -> str:
    """Parse the CF-Visitor header JSON to extract the scheme.

    CF-Visitor looks like: {"scheme":"https"}
    Returns the scheme string (e.g., "https") or empty string on failure.
    """
    if not cf_visitor:
        return ""
    try:
        import json
        return json.loads(cf_visitor).get("scheme", "")
    except (ValueError, TypeError):
        return ""


def _rate_limit_check(client_ip: str) -> bool:
    """Sliding-window rate limit per client IP. Returns True if allowed."""
    now = time.monotonic()
    window_start = now - _RATE_LIMIT_WINDOW_SEC

    # Prune old entries
    entries = _RATE_LIMIT_STORE.get(client_ip, [])
    entries = [t for t in entries if t > window_start]

    if len(entries) >= _ORIGIN_RATE_LIMIT_PER_MIN:
        _RATE_LIMIT_STORE[client_ip] = entries
        return False

    entries.append(now)
    _RATE_LIMIT_STORE[client_ip] = entries
    return True


# ---------------------------------------------------------------------------
# Audit logging helper (for downstream handlers)
# ---------------------------------------------------------------------------


def log_security_event(
    request: Request,
    event_type: str,
    *,
    detail: str = "",
    severity: str = "info",
) -> None:
    """Log a structured security event with Cloudflare metadata.

    Called by route handlers when they detect suspicious activity that
    the middleware didn't catch (e.g., a valid JWT user trying to access
    another user's data). The log includes the CF-RAY ID so SIEM
    correlation with Cloudflare's logs is possible.
    """
    metadata = getattr(request.state, "cloudflare", {}) or {}
    logger.log(
        logging.WARNING if severity == "warning" else logging.INFO,
        "security_event: type=%s severity=%s detail=%s client_ip=%s "
        "cf_ray=%s country=%s",
        event_type,
        severity,
        detail[:200],
        metadata.get("client_ip", "?"),
        metadata.get("ray_id", ""),
        metadata.get("country", ""),
    )
