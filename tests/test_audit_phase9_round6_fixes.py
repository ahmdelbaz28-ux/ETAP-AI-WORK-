"""Phase 9: Self-critique Round 6 — regression fixes + new auth gaps.

Tests verify:
- /admin/cua/audit-log regression fix — _require_api_key is actually called
- /ws/notifications WebSocket: token type check (must be "access")
- /ws/notifications WebSocket: JTI blacklist check
- /api/v1/scada/live: requires API key auth
- /api/v1/digital-twin/status: requires API key auth
- SQL injection safety: parameterized queries in all critical files
"""
from __future__ import annotations

from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_file(relative: str) -> str:
    return (_REPO_ROOT / relative).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# S-15 regression: /admin/cua/audit-log must have _require_api_key
# ---------------------------------------------------------------------------

class TestAuditLogRegressionFix:
    """Verify the audit-log endpoint actually calls _require_api_key (not just has the comment)."""

    @pytest.fixture(scope="class")
    def routes_source(self) -> str:
        return _read_file("api/routes.py")

    def test_audit_log_has_require_api_key_in_body(self, routes_source: str) -> None:
        """The function body must contain _require_api_key(request) AFTER the docstring."""
        marker = 'async def cua_audit_log('
        pos = routes_source.index(marker)
        body = routes_source[pos:pos + 2000]
        # Find end of docstring (triple quote)
        doc_end = body.index('"""', body.index('"""') + 3) + 3
        after_docstring = body[doc_end:doc_end + 500]
        assert "_require_api_key(request)" in after_docstring, (
            "/admin/cua/audit-log does NOT call _require_api_key after docstring — REGRESSION"
        )


# ---------------------------------------------------------------------------
# /ws/notifications: token type + blacklist checks
# ---------------------------------------------------------------------------

class TestNotificationsWebSocketSecurity:
    """Verify /ws/notifications validates token type and checks blacklist."""

    @pytest.fixture(scope="class")
    def routes_source(self) -> str:
        return _read_file("api/routes.py")

    def test_ws_notifications_has_token_type_check(self, routes_source: str) -> None:
        """WebSocket must reject non-access tokens."""
        ws_pos = routes_source.index('websocket_notifications_handler')
        ws_body = routes_source[ws_pos:ws_pos + 3000]
        assert 'token_type != "access"' in ws_body, (
            "/ws/notifications must check payload type == 'access'"
        )

    def test_ws_notifications_has_blacklist_check(self, routes_source: str) -> None:
        """WebSocket must check JTI against token blacklist."""
        ws_pos = routes_source.index('websocket_notifications_handler')
        ws_body = routes_source[ws_pos:ws_pos + 3000]
        assert "_is_token_blacklisted" in ws_body, (
            "/ws/notifications must call _is_token_blacklisted(jti)"
        )

    def test_ws_notifications_revoked_token_rejected(self, routes_source: str) -> None:
        """Revoked tokens must close the WebSocket."""
        ws_pos = routes_source.index('websocket_notifications_handler')
        ws_body = routes_source[ws_pos:ws_pos + 3000]
        assert "Token has been revoked" in ws_body, (
            "/ws/notifications must close with 'Token has been revoked' message"
        )


# ---------------------------------------------------------------------------
# New endpoint auth: /api/v1/scada/live and /api/v1/digital-twin/status
# ---------------------------------------------------------------------------

class TestNewEndpointAuthentication:
    """Verify newly authenticated endpoints."""

    @pytest.fixture(scope="class")
    def routes_source(self) -> str:
        return _read_file("api/routes.py")

    def test_scada_live_has_auth(self, routes_source: str) -> None:
        """/api/v1/scada/live must require API key."""
        marker = 'async def scada_live('
        pos = routes_source.index(marker)
        body = routes_source[pos:pos + 1500]
        assert "_require_api_key(request)" in body, (
            "/api/v1/scada/live must call _require_api_key(request)"
        )

    def test_scada_live_has_request_param(self, routes_source: str) -> None:
        """/api/v1/scada/live must accept request: Request."""
        assert "async def scada_live(request: Request)" in routes_source

    def test_digital_twin_has_auth(self, routes_source: str) -> None:
        """/api/v1/digital-twin/status must require API key."""
        marker = 'async def digital_twin_status('
        pos = routes_source.index(marker)
        body = routes_source[pos:pos + 1500]
        assert "_require_api_key(request)" in body, (
            "/api/v1/digital-twin/status must call _require_api_key(request)"
        )

    def test_digital_twin_has_request_param(self, routes_source: str) -> None:
        """/api/v1/digital-twin/status must accept request: Request."""
        assert "async def digital_twin_status(request: Request)" in routes_source


# ---------------------------------------------------------------------------
# SQL injection safety — parameterized queries
# ---------------------------------------------------------------------------

class TestSQLInjectionSafety:
    """Verify all critical DB-querying files use parameterized queries."""

    @pytest.mark.parametrize("file,unsafe_pattern", [
        ("api/auth.py", '.execute(.*f"'),
        ("api/auth.py", '.execute(.*%("'),
        ("api/magic_links.py", '.execute(.*f"'),
        ("api/dependencies.py", '.execute(.*f"'),
        ("api/equipment.py", '.execute(.*f"'),
        ("api/assets.py", '.execute(.*f"'),
        ("api/projects.py", '.execute(.*f"'),
    ])
    def test_no_fstring_sql(self, file: str, unsafe_pattern: str) -> None:
        """Critical files must NOT have f-string interpolated SQL."""
        import re
        source = _read_file(file)
        # Search for execute calls with f-strings
        matches = re.findall(r'\.execute\([^)]*f["\']', source)
        assert len(matches) == 0, (
            f"{file}: found {len(matches)} f-string SQL execute calls (SQL injection risk)"
        )

    def test_postgis_uses_parameterized(self) -> None:
        """PostGIS provider must use %s placeholders, not string formatting."""
        source = _read_file("gis_integration/providers/postgis_provider.py")
        # Should NOT have f-string or .format() in SQL
        import re
        fstring_sql = re.findall(r'\.execute\([^)]*f["\']', source)
        assert len(fstring_sql) == 0, (
            "postgis_provider.py must not use f-string SQL"
        )

    def test_api_key_store_uses_qmarks(self) -> None:
        """API key store must use ? parameterized placeholders."""
        source = _read_file("services/api_key_store.py")
        assert "execute(" in source  # Has execute calls
        # Should have ? placeholders
        assert "?)" in source, (
            "api_key_store.py must use ? parameterized placeholders"
        )
