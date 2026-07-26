"""Phase 7: Self-critique Round 5 — admin auth, CUA WebSocket auth, security headers, Helm anti-affinity.

Tests verify:
- S-15: All admin endpoints require API key authentication
- S-15: CUA confirmation WebSocket requires API key authentication
- S-16: Security headers middleware exists (X-Content-Type-Options, X-Frame-Options, Referrer-Policy)
- Helm: Pod anti-affinity configured in values.yaml
- F-1: Admin rollback endpoint has error handling (try/except)
- I-1: pylock.toml has updated openai/anthropic versions
"""
from __future__ import annotations

import importlib
import os
import textwrap
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_file(relative: str) -> str:
    return (_REPO_ROOT / relative).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# S-15: Admin endpoints require API key authentication
# ---------------------------------------------------------------------------

class TestAdminEndpointAuthentication:
    """Verify all admin endpoints call _require_api_key(request)."""

    ADMIN_ENDPOINTS = [
        ("GET", "/admin/cua/kill-switch"),
        ("POST", "/admin/cua/kill-switch/activate"),
        ("POST", "/admin/cua/kill-switch/deactivate"),
        ("POST", "/admin/cua/rollback"),
        ("GET", "/admin/cua/audit-log"),
        ("GET", "/api/v1/benchmark"),
    ]

    @pytest.fixture(scope="class")
    def routes_source(self) -> str:
        return _read_file("api/routes.py")

    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    def test_admin_endpoint_has_require_api_key(self, routes_source: str, method: str, path: str) -> None:
        """Each admin endpoint must call _require_api_key(request)."""
        # Find the route decorator and the function that follows
        # Check that within the function body, _require_api_key is called
        assert f"@app.{method.lower()}(\"{path}\"" in routes_source, (
            f"Route decorator for {method} {path} not found"
        )
        # Find the function definition after the decorator
        decorator_pos = routes_source.index(f"@app.{method.lower()}(\"{path}\"")
        # Get the next ~500 characters after the decorator (should contain the function body)
        func_body = routes_source[decorator_pos:decorator_pos + 3000]
        assert "_require_api_key(request)" in func_body, (
            f"{method} {path} does NOT call _require_api_key(request)"
        )

    def test_admin_activate_has_request_param(self, routes_source: str) -> None:
        """The activate endpoint must accept request: Request parameter."""
        assert "async def cua_kill_switch_activate(request: Request)" in routes_source

    def test_admin_deactivate_has_request_param(self, routes_source: str) -> None:
        """The deactivate endpoint must accept request: Request parameter."""
        assert "async def cua_kill_switch_deactivate(request: Request)" in routes_source

    def test_admin_kill_switch_status_has_request_param(self, routes_source: str) -> None:
        """The kill-switch status endpoint must accept request: Request parameter."""
        assert "async def cua_kill_switch_status(request: Request)" in routes_source

    def test_admin_rollback_has_request_param(self, routes_source: str) -> None:
        """The rollback endpoint must accept request: Request parameter."""
        assert "async def cua_rollback(request: Request, body:" in routes_source

    def test_admin_audit_log_has_request_param(self, routes_source: str) -> None:
        """The audit-log endpoint must accept request: Request parameter."""
        assert "async def cua_audit_log(request: Request," in routes_source

    def test_benchmark_has_request_param(self, routes_source: str) -> None:
        """The benchmark endpoint must accept request: Request parameter."""
        assert "async def benchmark(request: Request)" in routes_source


# ---------------------------------------------------------------------------
# S-15: CUA WebSocket requires API key authentication
# ---------------------------------------------------------------------------

class TestCUAWebSocketAuthentication:
    """Verify /ws/cua/confirmation WebSocket requires API key."""

    @pytest.fixture(scope="class")
    def routes_source(self) -> str:
        return _read_file("api/routes.py")

    def test_cua_websocket_has_api_key_check(self, routes_source: str) -> None:
        """CUA confirmation WebSocket must validate x-api-key header."""
        assert 'websocket.headers.get("x-api-key")' in routes_source
        # Check hmac.compare_digest is used
        ws_section = routes_source[routes_source.index("@app.websocket(\"/ws/cua/confirmation\")"):]
        assert "hmac.compare_digest" in ws_section[:1000], (
            "CUA WebSocket must use hmac.compare_digest for constant-time comparison"
        )
        assert 'code=1008' in ws_section[:1000], (
            "CUA WebSocket must close with code 1008 on auth failure"
        )

    def test_cua_websocket_closes_on_missing_key(self, routes_source: str) -> None:
        """CUA WebSocket must close connection if API key is missing."""
        ws_section = routes_source[routes_source.index("@app.websocket(\"/ws/cua/confirmation\")"):]
        assert 'await websocket.close(' in ws_section[:1500]

    def test_cua_websocket_closes_on_exception(self, routes_source: str) -> None:
        """CUA WebSocket must close on any auth exception."""
        ws_section = routes_source[routes_source.index("@app.websocket(\"/ws/cua/confirmation\")"):]
        assert "except Exception:" in ws_section[:1500]


# ---------------------------------------------------------------------------
# S-16: Security headers middleware
# ---------------------------------------------------------------------------

class TestSecurityHeadersMiddleware:
    """Verify security headers are set by the application middleware."""

    @pytest.fixture(scope="class")
    def routes_source(self) -> str:
        return _read_file("api/routes.py")

    def test_x_content_type_options(self, routes_source: str) -> None:
        """Must set X-Content-Type-Options: nosniff."""
        assert '"X-Content-Type-Options"' in routes_source
        assert '"nosniff"' in routes_source

    def test_x_frame_options(self, routes_source: str) -> None:
        """Must set X-Frame-Options: SAMEORIGIN."""
        assert '"X-Frame-Options"' in routes_source
        assert '"SAMEORIGIN"' in routes_source

    def test_referrer_policy(self, routes_source: str) -> None:
        """Must set Referrer-Policy: strict-origin-when-cross-origin."""
        assert '"Referrer-Policy"' in routes_source
        assert '"strict-origin-when-cross-origin"' in routes_source

    def test_hsts_configurable(self, routes_source: str) -> None:
        """HSTS must be configurable via HSTS_MAX_AGE env var."""
        assert "HSTS_MAX_AGE" in routes_source
        assert '"Strict-Transport-Security"' in routes_source

    def test_security_headers_middleware_exists(self, routes_source: str) -> None:
        """Security headers middleware function must be defined."""
        assert "_security_headers_middleware" in routes_source


# ---------------------------------------------------------------------------
# Helm: Pod anti-affinity
# ---------------------------------------------------------------------------

class TestHelmAntiAffinity:
    """Verify pod anti-affinity is configured in Helm values."""

    @pytest.fixture(scope="class")
    def values_yaml(self) -> str:
        return _read_file("helm/etap-ai/values.yaml")

    def test_pod_anti_affinity_configured(self, values_yaml: str) -> None:
        """api.affinity must contain podAntiAffinity."""
        assert "podAntiAffinity" in values_yaml, (
            "Helm values.yaml must define podAntiAffinity under api.affinity"
        )

    def test_anti_affinity_topology_key(self, values_yaml: str) -> None:
        """Anti-affinity must use kubernetes.io/hostname topology key."""
        assert "kubernetes.io/hostname" in values_yaml

    def test_anti_affinity_preferred(self, values_yaml: str) -> None:
        """Anti-affinity should use preferredDuringScheduling (not required)."""
        assert "preferredDuringSchedulingIgnoredDuringExecution" in values_yaml

    def test_anti_affinity_label_selector(self, values_yaml: str) -> None:
        """Anti-affinity must have a labelSelector with matchExpressions."""
        assert "matchExpressions" in values_yaml
        assert "app.kubernetes.io/component" in values_yaml


# ---------------------------------------------------------------------------
# F-1: Admin rollback error handling
# ---------------------------------------------------------------------------

class TestAdminRollbackErrorHandling:
    """Verify admin rollback endpoint has try/except with safe error response."""

    @pytest.fixture(scope="class")
    def routes_source(self) -> str:
        return _read_file("api/routes.py")

    def test_rollback_has_try_except(self, routes_source: str) -> None:
        """Rollback endpoint must have try/except block."""
        rollback_pos = routes_source.index("async def cua_rollback(")
        rollback_body = routes_source[rollback_pos:rollback_pos + 2000]
        assert "try:" in rollback_body
        assert "except Exception" in rollback_body

    def test_rollback_error_no_str_exc(self, routes_source: str) -> None:
        """Rollback error response must NOT use str(exc) or str(e)."""
        rollback_pos = routes_source.index("async def cua_rollback(")
        rollback_body = routes_source[rollback_pos:rollback_pos + 2000]
        except_block = rollback_body[rollback_body.index("except Exception"):]
        # The error response must not leak internal details
        assert '"Rollback operation failed"' in except_block
        # Verify NO str(exc) in the JSON response
        lines_after_except = except_block.split("\n")
        for line in lines_after_except[:10]:
            assert "str(exc)" not in line or "logger" in line, (
                f"str(exc) in HTTP response: {line}"
            )


# ---------------------------------------------------------------------------
# I-1: Stale dependencies updated
# ---------------------------------------------------------------------------

class TestDependencyUpdates:
    """Verify openai and anthropic SDK versions are updated."""

    @pytest.fixture(scope="class")
    def pylock(self) -> str:
        return _read_file("pylock.toml")

    def test_openai_version_updated(self, pylock: str) -> None:
        """openai must be >= 1.60.0 (was 1.35.10 with known issues)."""
        assert "openai = " in pylock
        for line in pylock.splitlines():
            if line.startswith("openai = "):
                version = line.split('"')[1]
                major, minor = map(int, version.split(".")[:2])
                assert (major, minor) >= (1, 60), (
                    f"openai version {version} is too old (>= 1.60.0 required)"
                )

    def test_anthropic_version_updated(self, pylock: str) -> None:
        """anthropic must be >= 0.49.0 (was 0.28.1 with known issues)."""
        assert "anthropic = " in pylock
        for line in pylock.splitlines():
            if line.startswith("anthropic = "):
                version = line.split('"')[1]
                major, minor = map(int, version.split(".")[:2])
                assert (major, minor) >= (0, 49), (
                    f"anthropic version {version} is too old (>= 0.49.0 required)"
                )

    def test_no_very_old_openai(self, pylock: str) -> None:
        """openai must NOT be the old 1.35.10 version."""
        assert 'openai = "1.35.10"' not in pylock

    def test_no_very_old_anthropic(self, pylock: str) -> None:
        """anthropic must NOT be the old 0.28.1 version."""
        assert 'anthropic = "0.28.1"' not in pylock
