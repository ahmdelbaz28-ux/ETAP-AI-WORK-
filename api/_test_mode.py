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
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Request


def is_test_mode(request: Request) -> bool:
    """Check if the request is from automation/CI (X-API-Key matches service key).

    SECURITY: Always returns False in production/staging environments.
    Test-mode bypasses (auto-verify OTP, return reset tokens in response,
    accept placeholder magic links) are dangerous in production and must
    never be active there, even if the API key is correct.

    When true (development/test only):
    - OTP send: skip rate limiting, return the code in the response
    - OTP verify: auto-verify placeholder codes (999999)
    - Magic link request: skip rate limiting, return the token in the response
    - Magic link verify: auto-verify placeholder tokens
    - Dashboard: accept API key as alternative to JWT

    Returns True only if ALL of:
    1. ENVIRONMENT is not production/prod/staging, AND
    2. X-API-Key header is present, AND
    3. ENGINEERING_SERVICE_API_KEY env var is set, AND
    4. They match exactly (constant-time comparison).
    """
    # SECURITY GUARD: never allow test-mode bypasses in production
    _env = os.getenv("ENVIRONMENT", "development").lower()
    if _env in ("production", "prod", "staging"):
        return False

    api_key = request.headers.get("x-api-key", "")
    expected_key = os.getenv("ENGINEERING_SERVICE_API_KEY", "")
    if not api_key or not expected_key:
        return False
    # Constant-time comparison to prevent timing attacks
    import hmac as _hmac
    return _hmac.compare_digest(api_key, expected_key)


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


def get_api_key_auth(request: Request) -> Optional[dict]:
    """Check if request has valid API key auth. Returns service dict or None.

    SECURITY (E-06 rev2): The previous implementation granted role='admin'
    unconditionally — a full admin backdoor if the API key leaked. Now:

    1. is_test_mode() already returns False in production (E-04 fix), so
       this function only returns a non-None value in development.
    2. The role granted is configurable via TEST_MODE_API_KEY_ROLE env var
       (default: 'service' — read-only dashboard access). Set to 'admin'
       only if a specific test needs admin privileges.
    3. Added 'service' to EMAIL_DASHBOARD_ADMIN_ROLES in email_dashboard.py
       so dashboard access still works with the new role.

    Returns:
        {"user_id": "service", "role": "<configured>", "auth_method": "api_key"}
        if valid API key in dev mode, None otherwise.
    """
    if is_test_mode(request):
        # Role is configurable for flexibility, defaults to 'service'
        # (read-only). Production is already blocked by is_test_mode().
        role = os.getenv("TEST_MODE_API_KEY_ROLE", "service")
        return {
            "user_id": "service",
            "role": role,
            "auth_method": "api_key",
        }
    return None


__all__ = ["is_test_mode", "normalize_template_var", "get_api_key_auth"]
