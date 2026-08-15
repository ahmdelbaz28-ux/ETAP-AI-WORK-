"""
api/_test_mode.py — Shared test-mode detection for AhmedETAP
=============================================================

Extracts the repeated pattern of detecting automation/CI requests
(via X-API-Key header matching ENGINEERING_SERVICE_API_KEY).

This module eliminates code duplication across:
- api/email_otp.py
- api/magic_links.py
- api/email_dashboard.py

Usage:
    from api._test_mode import is_test_mode, normalize_template_var

    if is_test_mode(request):
        # Skip rate limiting, return test codes, etc.
        ...

    # Normalize Postman template variables ({{var}}) that weren't substituted
    code = normalize_template_var(body.code, default="999999")

CRITICAL FIX — Test Mode in Production (v2 — fail-closed):
    Previous version defaulted to "development" when ENVIRONMENT env var
    was not set, which is a fail-open design: if the env var is accidentally
    unset or misconfigured in production, test mode is enabled, exposing
    OTP codes, magic-link tokens, and bypassing rate limits.

    v2 fix: The system now defaults to PRODUCTION (fail-closed) when
    the environment variable is not set. Additionally, a hard kill switch
    (DISABLE_TEST_MODE=true) is available that forces test mode OFF
    regardless of any other configuration. This ensures that even if
    all other checks fail, test mode cannot be enabled in production.
"""

from __future__ import annotations

import logging
import os

from fastapi import Request

_logger = logging.getLogger("api._test_mode")

# Hard kill switch: DISABLE_TEST_MODE=true forces test mode OFF
# regardless of ENVIRONMENT or any other setting. This is the
# ultimate safety net — set it in production deployments.
_DISABLE_TEST_MODE = os.getenv("DISABLE_TEST_MODE", "").lower().strip() in ("true", "1", "yes")

# Log the test mode status at module load time for audit trail
if _DISABLE_TEST_MODE:
    _logger.warning(
        "test_mode HARD DISABLED via DISABLE_TEST_MODE=true — test features are blocked"
    )


def _is_production_env() -> bool:
    """Return True when running in a production-like environment.

    CRITICAL FIX (v2 — fail-closed):
    Previous version defaulted to "development" when ENVIRONMENT was
    not set. This is a fail-open design: if the env var is accidentally
    unset or misconfigured in production, test mode is enabled, exposing
    OTP codes, magic-link tokens, and bypassing rate limits.

    v2 fix: The system now defaults to PRODUCTION (fail-closed) when
    the environment variable is not set. This means:
    - No ENVIRONMENT set → production (safe)
    - ENVIRONMENT=development → development (test mode possible)
    - ENVIRONMENT=typo → production (safe, because unknown = production)

    The only way to get development mode is to explicitly set
    ENVIRONMENT to a known development value. This is the correct
    security posture for a system that handles credentials.
    """
    env = os.getenv("ENVIRONMENT", os.getenv("ENV", "")).lower().strip()

    # No environment variable set → fail-closed → production
    if not env:
        _logger.debug("No ENVIRONMENT/ENV set — defaulting to production (fail-closed)")
        return True

    # Explicit dev/test values — never production.
    if env in ("development", "dev", "local", "localhost", "test", "testing", "ci"):
        return False

    # Anything starting with a production prefix is production.
    if any(
        env == prefix or env.startswith(prefix + "-") or env.startswith(prefix + "_")
        for prefix in ("production", "prod", "staging", "stage")
    ):
        return True

    # Unknown values → fail-closed → production
    # This catches typos like "prodution", "pod", "stageing"
    _logger.warning("Unknown ENVIRONMENT value %r — defaulting to production (fail-closed)", env)
    return True


def is_test_mode(request: Request) -> bool:
    """Check if the request is from automation/CI (X-API-Key matches service key).

    When true (AND not in production):
    - OTP send: skip rate limiting, return the code in the response
    - OTP verify: auto-verify placeholder codes (999999)
    - Magic link request: skip rate limiting, return the token in the response
    - Magic link verify: auto-verify placeholder tokens
    - Dashboard: accept API key as alternative to JWT

    SECURITY (v2 — fail-closed + hard kill switch):
    - ALWAYS returns False in production/staging environments
    - ALWAYS returns False if DISABLE_TEST_MODE=true (hard kill switch)
    - A leaked ENGINEERING_SERVICE_API_KEY must NEVER grant admin access,
      bypass rate limits, or expose OTP/magic-link tokens in responses
    - Defaults to production (fail-closed) when ENVIRONMENT is not set

    Returns True only if ALL of the following are true:
    1. DISABLE_TEST_MODE is not set to true (hard kill switch), AND
    2. Current environment is development (NOT production/staging), AND
    3. X-API-Key header is present AND
    4. ENGINEERING_SERVICE_API_KEY env var is set AND
    5. They match exactly (timing-safe comparison)
    """
    # Hard kill switch — always takes precedence
    if _DISABLE_TEST_MODE:
        return False

    # Production environment check — fail-closed
    if _is_production_env():
        return False

    api_key = request.headers.get("x-api-key", "")
    expected_key = os.getenv("ENGINEERING_SERVICE_API_KEY", "")
    if not api_key or not expected_key:
        return False
    # Timing-safe comparison to prevent timing attacks on key enumeration.
    import hmac

    return hmac.compare_digest(api_key, expected_key)


def normalize_template_var(value: str, default: str = "") -> str:
    """Normalize a value that might be an unsubstituted Postman template variable.

    Postman template variables look like {{variable_name}}. When Newman
    runs and the variable is empty/unset, the literal string {{variable_name}}
    is sent in the request body. This function detects that and returns
    a safe default value instead.

    Args:
        value: The input string (might be "{{otp_code}}", "{{test_email}}", etc.)
        default: The value to return if the input is a template var or empty

    Returns:
        The original value, or the default if it was a template var/empty.

    Examples:
        normalize_template_var("123456")  → "123456"
        normalize_template_var("{{otp_code}}", "999999")  → "999999"
        normalize_template_var("", "999999")  → "999999"
        normalize_template_var("user@example.com")  → "user@example.com"
    """
    if not value:
        return default
    value = value.strip()
    if value.startswith("{{") or value.endswith("}}"):
        return default
    return value


def get_api_key_auth(request: Request) -> dict | None:
    """Check if request has valid API key auth. Returns user dict or None.

    This is used by dashboard endpoints that accept X-API-Key as an
    alternative to JWT Bearer tokens.

    Returns:
        {"user_id": "service", "role": "service", "auth_method": "api_key"}
        if valid API key, None otherwise.

    SECURITY AUDIT 2026-07-25 — Fix S-05: role changed from "admin" to "service".
    Previously, the engineering API key granted full admin privileges.
    Now it grants only "service" role. Admin actions require explicit admin JWT.
    """
    if is_test_mode(request):
        return {
            "user_id": "service",
            "role": "service",  # SECURITY: was "admin", downgraded per audit S-05
            "auth_method": "api_key",
        }
    return None


__all__ = ["is_test_mode", "normalize_template_var", "get_api_key_auth"]

