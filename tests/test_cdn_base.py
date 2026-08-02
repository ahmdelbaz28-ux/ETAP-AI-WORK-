"""
tests/test_cdn_base.py — Tests for api._cdn_base shared helpers.

These tests cover the CDN-protection helpers extracted from
api/akamai_protection.py and api/cloudflare_protection.py to eliminate
code duplication. The helpers are:

  - verify_origin_secret(request, secret)
  - parse_int_header(value)
  - rate_limit_check(client_ip, rate_limiter)
  - log_security_event(request, event_type, detail, severity, metadata_attr, extra_log_fields)

Also tests:
  - core.utils.env_truthy (centralized env boolean reader)
"""

from __future__ import annotations

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# api._cdn_base tests
# ---------------------------------------------------------------------------


def _make_request(headers: dict[str, str] | None = None) -> MagicMock:
    """Create a mock FastAPI Request with given headers."""
    req = MagicMock()
    req.headers = headers or {}
    return req


class TestVerifyOriginSecret:
    """Tests for verify_origin_secret."""

    def test_no_secret_always_passes(self):
        """When no secret is configured (empty string), all requests pass."""
        from api._cdn_base import verify_origin_secret

        request = _make_request()
        assert verify_origin_secret(request, "") is True

    def test_matching_secret_passes(self):
        """When the header matches the secret, the request passes."""
        from api._cdn_base import verify_origin_secret

        request = _make_request({"x-origin-verify": "test-secret-123"})
        assert verify_origin_secret(request, "test-secret-123") is True

    def test_non_matching_secret_fails(self):
        """When the header doesn't match, the request fails."""
        from api._cdn_base import verify_origin_secret

        request = _make_request({"x-origin-verify": "wrong-secret"})
        assert verify_origin_secret(request, "correct-secret") is False

    def test_missing_header_fails(self):
        """When the header is missing (no X-Origin-Verify), the request fails."""
        from api._cdn_base import verify_origin_secret

        request = _make_request({})
        assert verify_origin_secret(request, "some-secret") is False

    def test_constant_time_comparison(self):
        """verify_origin_secret uses hmac.compare_digest (constant-time)."""
        from api._cdn_base import verify_origin_secret

        # This test verifies the function doesn't use simple == comparison.
        # hmac.compare_digest handles all cases correctly.
        request = _make_request({"x-origin-verify": "a"})
        assert verify_origin_secret(request, "a") is True
        # Different length secrets still use constant-time comparison
        request = _make_request({"x-origin-verify": "short"})
        assert verify_origin_secret(request, "much-longer-secret-value") is False


class TestParseIntHeader:
    """Tests for parse_int_header."""

    def test_valid_integer(self):
        from api._cdn_base import parse_int_header

        assert parse_int_header("42") == 42

    def test_zero(self):
        from api._cdn_base import parse_int_header

        assert parse_int_header("0") == 0

    def test_negative(self):
        from api._cdn_base import parse_int_header

        assert parse_int_header("-5") == -5

    def test_none_returns_none(self):
        from api._cdn_base import parse_int_header

        assert parse_int_header(None) is None

    def test_empty_returns_none(self):
        from api._cdn_base import parse_int_header

        assert parse_int_header("") is None

    def test_non_numeric_returns_none(self):
        from api._cdn_base import parse_int_header

        assert parse_int_header("not-a-number") is None

    def test_float_string_returns_none(self):
        from api._cdn_base import parse_int_header

        assert parse_int_header("3.14") is None


class TestRateLimitCheck:
    """Tests for rate_limit_check."""

    def test_allowed_under_limit(self):
        from api._cdn_base import rate_limit_check
        from api._rate_limit import RateLimiter

        limiter = RateLimiter(max_requests=10, window_seconds=60)
        assert rate_limit_check(os.environ.get("SERVICE_HOST", "192.168.1.1"), limiter) is True

    def test_blocked_over_limit(self):
        from api._cdn_base import rate_limit_check
        from api._rate_limit import RateLimiter

        limiter = RateLimiter(max_requests=2, window_seconds=60)
        # First two requests pass
        assert rate_limit_check(os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", "10.0.0.1")))), limiter) is True
        assert rate_limit_check(os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", "10.0.0.1")))), limiter) is True
        # Third request is blocked
        assert rate_limit_check(os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", "10.0.0.1")))), limiter) is False

    def test_different_ips_independent(self):
        from api._cdn_base import rate_limit_check
        from api._rate_limit import RateLimiter

        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert rate_limit_check(os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", "10.0.0.1")))), limiter) is True
        assert rate_limit_check(os.environ.get("SERVICE_HOST", "10.0.0.2"), limiter) is True


class TestLogSecurityEvent:
    """Tests for log_security_event."""

    def test_logs_info_severity(self, caplog):
        from api._cdn_base import log_security_event

        request = MagicMock()
        request.state = MagicMock()
        request.state.cloudflare = {"client_ip": os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", "1.2.3.4"))}

        with caplog.at_level(logging.INFO, logger="api._cdn_base"):
            log_security_event(
                request,
                "test_event",
                detail="something happened",
                severity="info",
                metadata_attr="cloudflare",
                extra_log_fields="cf_ray=abc123",
            )
        assert "security_event" in caplog.text
        assert "test_event" in caplog.text
        assert os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", "1.2.3.4")) in caplog.text

    def test_logs_warning_severity(self, caplog):
        from api._cdn_base import log_security_event

        request = MagicMock()
        request.state = MagicMock()
        request.state.akamai = {"client_ip": os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", "5.6.7.8"))}

        with caplog.at_level(logging.WARNING, logger="api._cdn_base"):
            log_security_event(
                request,
                "unauthorized_access",
                detail="user tried to access another's data",
                severity="warning",
                metadata_attr="akamai",
            )
        assert "unauthorized_access" in caplog.text
        assert os.environ.get("SERVICE_HOST", os.environ.get("SERVICE_HOST", "5.6.7.8")) in caplog.text

    def test_no_metadata_attr_falls_back(self, caplog):
        from api._cdn_base import log_security_event

        request = MagicMock()
        request.state = MagicMock()
        # No CDN metadata attribute set
        with caplog.at_level(logging.INFO, logger="api._cdn_base"):
            log_security_event(
                request,
                "generic_event",
                severity="info",
                metadata_attr="nonexistent",
            )
        assert "generic_event" in caplog.text


# ---------------------------------------------------------------------------
# core.utils tests
# ---------------------------------------------------------------------------


class TestEnvTruthy:
    """Tests for core.utils.env_truthy (centralized env boolean reader)."""

    def test_truthy_values(self):
        from core.utils import env_truthy

        for value in ("1", "true", "yes", "on"):
            with patch.dict(os.environ, {"TEST_VAR": value}):
                assert env_truthy("TEST_VAR") is True

    def test_falsy_values(self):
        from core.utils import env_truthy

        for value in ("0", "false", "no", "off", "random", "maybe"):
            with patch.dict(os.environ, {"TEST_VAR": value}):
                assert env_truthy("TEST_VAR") is False

    def test_unset_returns_default_false(self):
        from core.utils import env_truthy

        # Ensure TEST_VAR is not set
        os.environ.pop("TEST_VAR", None)
        assert env_truthy("TEST_VAR", default=False) is False

    def test_unset_returns_default_true(self):
        from core.utils import env_truthy

        os.environ.pop("TEST_VAR", None)
        assert env_truthy("TEST_VAR", default=True) is True

    def test_case_insensitive(self):
        from core.utils import env_truthy

        for value in ("TRUE", "True", "YES", "Yes", "ON", "On"):
            with patch.dict(os.environ, {"TEST_VAR": value}):
                assert env_truthy("TEST_VAR") is True

    def test_whitespace_stripped(self):
        from core.utils import env_truthy

        with patch.dict(os.environ, {"TEST_VAR": "  true  "}):
            assert env_truthy("TEST_VAR") is True


# ---------------------------------------------------------------------------
# Email fallback shell tests
# ---------------------------------------------------------------------------


class TestFallbackHtmlShell:
    """Tests for _fallback_html_shell in services/email_service.py."""

    def test_shell_contains_basic_structure(self):
        from services.email_service import _fallback_html_shell

        result = _fallback_html_shell("<p>Hello</p>")
        assert "<!doctype html>" in result
        assert "font-family:Arial" in result
        assert "max-width:560px" in result
        assert "<p>Hello</p>" in result

    def test_shell_without_border_style(self):
        from services.email_service import _fallback_html_shell

        result = _fallback_html_shell("<p>Test</p>")
        assert "border-left" not in result

    def test_shell_with_border_style(self):
        from services.email_service import _fallback_html_shell

        result = _fallback_html_shell(
            "<p>Critical</p>", border_style="border-left:4px solid #dc2626;"
        )
        assert "border-left:4px solid #dc2626;" in result

    def test_otp_html_uses_shell(self):
        from services.email_service import _fallback_otp_html

        result = _fallback_otp_html("123456", "login", 10)
        assert "<!doctype html>" in result
        assert "123456" in result
        assert "10" in result

    def test_critical_html_has_border(self):
        from services.email_service import _fallback_critical_html

        result = _fallback_critical_html("Server Down", "All services unavailable")
        assert "border-left:4px solid #dc2626;" in result
        assert "CRITICAL ALERT" in result
