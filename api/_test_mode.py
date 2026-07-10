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

    When true:
    - OTP send: skip rate limiting, return the code in the response
    - OTP verify: auto-verify placeholder codes (999999)
    - Magic link request: skip rate limiting, return the token in the response
    - Magic link verify: auto-verify placeholder tokens
    - Dashboard: accept API key as alternative to JWT

    Returns True only if:
    1. X-API-Key header is present AND
    2. ENGINEERING_SERVICE_API_KEY env var is set AND
    3. They match exactly
    """
    api_key = request.headers.get("x-api-key", "")
    expected_key = os.getenv("ENGINEERING_SERVICE_API_KEY", "")
    return bool(api_key and expected_key and api_key == expected_key)


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
    """Check if request has valid API key auth. Returns user dict or None.

    This is used by dashboard endpoints that accept X-API-Key as an
    alternative to JWT Bearer tokens.

    Returns:
        {"user_id": "service", "role": "admin", "auth_method": "api_key"}
        if valid API key, None otherwise.
    """
    if is_test_mode(request):
        return {
            "user_id": "service",
            "role": "admin",
            "auth_method": "api_key",
        }
    return None


__all__ = ["is_test_mode", "normalize_template_var", "get_api_key_auth"]
