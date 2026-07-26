"""Phase 8: Medium findings — unbounded params, CORS restricted in hf-space.

Tests verify:
- email_webhooks list_events: limit bounded to [1, 500]
- email_dashboard: limit bounded to [1, 500], days bounded to [1, 365]
- r2_storage list_objects: limit bounded to [1, 1000]
- hf-space CORS: methods and headers are restricted (not wildcard)
- hf-space max_steps: bounded to [1, 50]
- hf-space start_url: SSRF prevention with private IP rejection
"""
from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_file(relative: str) -> str:
    return (_REPO_ROOT / relative).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Unbounded limit parameters
# ---------------------------------------------------------------------------

class TestBoundedLimitParameters:
    """Verify all limit query parameters are bounded to prevent abuse."""

    @pytest.mark.parametrize("file,snippet", [
        ("api/email_webhooks.py", "max(1, min(limit, 500))"),
        ("api/email_dashboard.py", "max(1, min(limit, 500))"),
        ("api/r2_storage.py", "max(1, min(limit, 1000))"),
    ])
    def test_limit_is_bounded(self, file: str, snippet: str) -> None:
        """Each endpoint that accepts a limit parameter must bound it."""
        source = _read_file(file)
        assert snippet in source, f"{file}: expected '{snippet}' not found"

    def test_email_dashboard_days_bounded(self) -> None:
        """email_dashboard by-day endpoint must bound days parameter."""
        source = _read_file("api/email_dashboard.py")
        assert "max(1, min(days, 365))" in source


# ---------------------------------------------------------------------------
# HF Space CORS restrictions
# ---------------------------------------------------------------------------

class TestHFSpaceCORS:
    """Verify hf-space CORS is not using wildcard methods/headers."""

    @pytest.fixture(scope="class")
    def hf_source(self) -> str:
        return _read_file("hf-space/app.py")

    def test_cors_methods_not_wildcard(self, hf_source: str) -> None:
        """CORS must NOT use allow_methods=[\"*\"]."""
        assert 'allow_methods=["*"]' not in hf_source, (
            "hf-space CORS must not use wildcard methods"
        )

    def test_cors_headers_not_wildcard(self, hf_source: str) -> None:
        """CORS must NOT use allow_headers=[\"*\"]."""
        assert 'allow_headers=["*"]' not in hf_source, (
            "hf-space CORS must not use wildcard headers"
        )

    def test_cors_has_explicit_methods(self, hf_source: str) -> None:
        """CORS should have explicit method list."""
        assert 'allow_methods=["GET"' in hf_source

    def test_cors_has_explicit_headers(self, hf_source: str) -> None:
        """CORS should have explicit header list."""
        assert '"x-api-key"' in hf_source


# ---------------------------------------------------------------------------
# HF Space input validation
# ---------------------------------------------------------------------------

class TestHFSpaceInputValidation:
    """Verify hf-space has input validation on user-provided parameters."""

    @pytest.fixture(scope="class")
    def hf_source(self) -> str:
        return _read_file("hf-space/app.py")

    def test_max_steps_bounded(self, hf_source: str) -> None:
        """max_steps must be bounded to [1, 50]."""
        assert "min(int(body.get(\"max_steps\", 15)), 50)" in hf_source

    def test_ssrf_prevention(self, hf_source: str) -> None:
        """start_url must be validated against SSRF (private IP check)."""
        assert "is_private" in hf_source
        assert "is_loopback" in hf_source
        assert "ipaddress" in hf_source

    def test_url_scheme_validation(self, hf_source: str) -> None:
        """start_url must be validated for scheme (https/http only)."""
        assert "scheme not in" in hf_source or "parsed.scheme" in hf_source
