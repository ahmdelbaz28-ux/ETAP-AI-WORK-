"""
api/akamai_protection.py — Akamai Edge security integration for the origin.

This module verifies that incoming requests reached the origin (HF Space)
through the Akamai edge, and enforces security policies based on Akamai's
analysis (bot scores, client reputation, geo data, etc.).

Architecture
------------
    User  →  Akamai Edge (WAF + Bot Manager + Rate Limit + CDN)
           ↓ adds security headers + verdicts
    HF Space origin  ←  this middleware verifies Akamai metadata

When AKAMAI_ORIGIN_SECRET is set (production), requests that bypass Akamai
are rejected with 403. In development (no secret), all requests pass through
with a warning log so the platform stays usable without Akamai.

Akamai headers consumed
-----------------------
X-Akamai-Edgescape          — geo data (country, city, lat/lon, zip)
Akamai-BM-Telemetry         — Bot Manager telemetry (JSON, base64)
X-Akamai-Bot-Score          — Bot risk score (0-100, higher = more likely bot)
X-Akamai-Bot-Category       — Bot category (HUMAN, BROWSER, BOT, MALICIOUS)
X-Akamai-Client-Reputation  — Client reputation score (GOOD, SUSPICIOUS, BAD)
X-Akamai-Request-ID         — Unique edge request ID (for audit correlation)
X-Origin-Verify             — Shared secret injected by Akamai property rule
                               (only the Akamai property + the origin know this value)
True-Client-IP              — Real client IP (Akamai replaces X-Forwarded-For)
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Any, Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Shared secret between Akamai Property and the origin. When set, the
# middleware rejects any request that doesn't carry this value in the
# X-Origin-Verify header — preventing direct origin access (bypassing Akamai).
# Generate with: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
AKAMAI_ORIGIN_SECRET: str = os.getenv("AKAMAI_ORIGIN_SECRET", "")

# When True, requests that bypass Akamai are rejected with 403.
# When False (dev mode), requests pass through with a warning.
_ORIGIN_VERIFICATION_ENFORCED: bool = bool(AKAMAI_ORIGIN_SECRET)

# Bot score thresholds (0-100, higher = more likely a bot)
BOT_SCORE_BLOCK_THRESHOLD: int = int(os.getenv("AKAMAI_BOT_SCORE_BLOCK", "80"))
BOT_SCORE_CHALLENGE_THRESHOLD: int = int(os.getenv("AKAMAI_BOT_SCORE_CHALLENGE", "50"))

# Client reputation levels that trigger blocking
_BLOCKED_REPUTATIONS: frozenset[str] = frozenset({
    "BAD",
    "MALICIOUS",
    "BOTNET",
    "SPAM",
    "SCANNER",
})

# Blocked bot categories
_BLOCKED_BOT_CATEGORIES: frozenset[str] = frozenset({
    "MALICIOUS",
    "BOT",
    "SCANNER",
    "SCRAPER",
})

# Rate limit: max requests per minute per client IP (origin-side defense-in-depth)
# Akamai enforces rate limits at the edge, but this catches anything that slips through.
_ORIGIN_RATE_LIMIT_PER_MIN: int = int(os.getenv("AKAMAI_ORIGIN_RATE_LIMIT", "300"))

# In-memory rate limit store (per-worker; HF Space runs a single worker)
# For multi-worker deployments, switch to Redis-backed counter.
_RATE_LIMIT_STORE: dict[str, list[float]] = {}
_RATE_LIMIT_WINDOW_SEC: int = 60

# Shared rate limiter instance (extracted to api._rate_limit to eliminate
# duplication with api/cloudflare_protection.py).
from api._rate_limit import RateLimiter  # noqa: E402

_rate_limiter: RateLimiter = RateLimiter(
    max_requests=_ORIGIN_RATE_LIMIT_PER_MIN,
    window_seconds=_RATE_LIMIT_WINDOW_SEC,
)
# Keep _RATE_LIMIT_STORE as an alias for backward compatibility (tests,
# debug endpoints may inspect it directly).
_RATE_LIMIT_STORE = _rate_limiter._store  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def is_akamai_enabled() -> bool:
    """Return True if Akamai origin verification is active."""
    return _ORIGIN_VERIFICATION_ENFORCED


def get_client_ip(request: Request) -> str:
    """Extract the real client IP, preferring Akamai's True-Client-IP header."""
    # Akamai sets True-Client-IP to the actual end-user IP.
    true_ip = request.headers.get("true-client-ip", "").strip()
    if true_ip:
        return true_ip

    # Fall back to X-Forwarded-For (first hop).
    xff = request.headers.get("x-forwarded-for", "").strip()
    if xff:
        return xff.split(",")[0].strip()

    # Last resort: the direct connection IP.
    return request.client.host if request.client else "unknown"


def get_akamai_metadata(request: Request) -> dict[str, Any]:
    """Extract all Akamai-provided metadata from the request headers.

    Returns a dict suitable for logging/audit. All fields are optional —
    if the request didn't come through Akamai, the dict will be empty.
    """
    return {
        "request_id": request.headers.get("x-akamai-request-id", ""),
        "bot_score": _parse_int(request.headers.get("x-akamai-bot-score")),
        "bot_category": request.headers.get("x-akamai-bot-category", "").upper(),
        "client_reputation": request.headers.get("x-akamai-client-reputation", "").upper(),
        "edgescape": request.headers.get("x-akamai-edgescape", ""),
        "origin_verified": _verify_origin_secret(request),
        "client_ip": get_client_ip(request),
    }


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


async def akamai_protection_middleware(request: Request, call_next):
    """FastAPI middleware: verify Akamai metadata + enforce bot/reputation policies.

    Order of checks:
      1. Origin verification (reject requests that bypassed Akamai)
      2. Rate limiting (per client IP)
      3. Bot score blocking (malicious bots → 403)
      4. Client reputation blocking (known-bad IPs → 403)
      5. Bot category blocking (scanners/scrapers → 403)

    On block, returns a JSON response with the reason + Akamai request ID
    for audit correlation. On pass, the request proceeds and Akamai
    metadata is attached to request.state for downstream handlers.
    """
    path = request.url.path

    # Skip Akamai verification for health checks (Akamai's own monitoring
    # + uptime checks from HF Space infra). These come from internal IPs
    # and don't carry Akamai headers.
    if path in ("/healthz", "/readyz", "/health", "/ready"):
        return await call_next(request)

    # Attach Akamai metadata to request state so downstream handlers
    # (audit logging, analytics, etc.) can use it.
    metadata = get_akamai_metadata(request)
    request.state.akamai = metadata

    # ── 1. Origin verification ──────────────────────────────────────────
    if _ORIGIN_VERIFICATION_ENFORCED and not metadata["origin_verified"]:
        logger.warning(
            "akamai: origin verification failed for %s %s (client_ip=%s, "
            "user_agent=%s) — request bypassed Akamai edge",
            request.method, path, metadata["client_ip"],
            request.headers.get("user-agent", "")[:100],
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "Direct origin access is not permitted. "
                          "Requests must go through the CDN.",
                "akamai_request_id": metadata["request_id"],
            },
            headers={"X-Block-Reason": "origin-verification-failed"},
        )

    # ── 2. Rate limiting (origin-side defense-in-depth) ─────────────────
    client_ip = metadata["client_ip"]
    if not _rate_limit_check(client_ip):
        logger.warning("akamai: rate limit exceeded for %s (%s %s)", client_ip, request.method, path)
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "Rate limit exceeded. Please slow down.",
                "akamai_request_id": metadata["request_id"],
            },
            headers={
                "Retry-After": str(_RATE_LIMIT_WINDOW_SEC),
                "X-Block-Reason": "rate-limit",
            },
        )

    # ── 3. Bot score blocking ───────────────────────────────────────────
    bot_score = metadata["bot_score"]
    if bot_score is not None and bot_score >= BOT_SCORE_BLOCK_THRESHOLD:
        logger.warning(
            "akamai: blocking high bot score (%d) for %s (%s %s)",
            bot_score, client_ip, request.method, path,
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "Request blocked by bot protection.",
                "akamai_request_id": metadata["request_id"],
                "bot_score": bot_score,
            },
            headers={
                "X-Block-Reason": "bot-score",
                "X-Bot-Score": str(bot_score),
            },
        )

    # ── 4. Client reputation blocking ───────────────────────────────────
    reputation = metadata["client_reputation"]
    if reputation and reputation in _BLOCKED_REPUTATIONS:
        logger.warning(
            "akamai: blocking bad reputation (%s) for %s (%s %s)",
            reputation, client_ip, request.method, path,
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "Request blocked by client reputation.",
                "akamai_request_id": metadata["request_id"],
                "reputation": reputation,
            },
            headers={
                "X-Block-Reason": "client-reputation",
                "X-Reputation": reputation,
            },
        )

    # ── 5. Bot category blocking ────────────────────────────────────────
    bot_category = metadata["bot_category"]
    if bot_category and bot_category in _BLOCKED_BOT_CATEGORIES:
        logger.warning(
            "akamai: blocking bot category (%s) for %s (%s %s)",
            bot_category, client_ip, request.method, path,
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "Request blocked by bot category filter.",
                "akamai_request_id": metadata["request_id"],
                "bot_category": bot_category,
            },
            headers={
                "X-Block-Reason": "bot-category",
                "X-Bot-Category": bot_category,
            },
        )

    # ── Pass through to the next handler ────────────────────────────────
    response = await call_next(request)

    # Add the Akamai request ID to the response so clients can correlate
    # with Akamai logs for debugging.
    if metadata["request_id"]:
        response.headers["X-Akamai-Request-ID"] = metadata["request_id"]

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
    if not AKAMAI_ORIGIN_SECRET:
        return True  # dev mode — no secret configured
    provided = request.headers.get("x-origin-verify", "")
    return hmac.compare_digest(provided, AKAMAI_ORIGIN_SECRET)


def _parse_int(value: Optional[str]) -> Optional[int]:
    """Parse an optional integer header value. Returns None on failure."""
    if not value:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _rate_limit_check(client_ip: str) -> bool:
    """Sliding-window rate limit per client IP. Returns True if allowed.

    Delegates to the shared RateLimiter instance `_rate_limiter` (initialized
    at module load from _ORIGIN_RATE_LIMIT_PER_MIN and _RATE_LIMIT_WINDOW_SEC).
    Kept as a module-level function for backward compatibility with existing
    callers that import `_rate_limit_check` directly.
    """
    return _rate_limiter.is_allowed(client_ip)


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
    """Log a structured security event with Akamai metadata.

    Called by route handlers when they detect suspicious activity that
    the middleware didn't catch (e.g., a valid JWT user trying to access
    another user's data). The log includes the Akamai request ID so
    SIEM correlation with Akamai's logs is possible.
    """
    metadata = getattr(request.state, "akamai", {}) or {}
    logger.log(
        logging.WARNING if severity == "warning" else logging.INFO,
        "security_event: type=%s severity=%s detail=%s client_ip=%s "
        "akamai_request_id=%s bot_score=%s reputation=%s",
        event_type,
        severity,
        detail[:200],
        metadata.get("client_ip", "?"),
        metadata.get("request_id", ""),
        metadata.get("bot_score"),
        metadata.get("client_reputation", ""),
    )
