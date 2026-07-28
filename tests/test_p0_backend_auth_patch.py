"""P0 Backend Auth Patch — verification tests for Conditions A and E.

Condition A: 5 dual-control REST endpoints must require
              ``Depends(require_role("admin", "engineer"))`` AND pull
              operator/approver/rejector identity from the JWT
              (``user.user_id``), NOT from the request body.

Condition E: ``/ws/cua/confirmation`` was previously registered in TWO
              places (``api/routes.py`` + ``hf-space/app.py``) with
              DIVERGENT auth logic. After the patch, both registration
              sites delegate to the shared
              ``api.cua_confirmation_ws.authenticate_cua_confirmation_ws``
              helper, eliminating duplication AND fixing the silent-skip
              fail-open bug that previously existed in hf-space/app.py.

These tests run without a live database — they use:
  * AST parsing for source-level structural checks (no import needed)
  * FastAPI route introspection for dependency-wiring checks
  * Direct unit tests of the shared auth helper using a fake WebSocket
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import inspect
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers — module loading
# ---------------------------------------------------------------------------


def _read_source(rel_path: str) -> str:
    """Read a source file from the repo and return its text."""
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _load_module(rel_path: str, module_name: str):
    """Load a Python module from a file path without polluting sys.modules."""
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Condition A — 5 dual-control REST endpoints
# ---------------------------------------------------------------------------

# Endpoint paths that MUST be patched
DUAL_CONTROL_REST_PATHS = [
    ("/api/v1/dual-control/request", "POST"),
    ("/api/v1/dual-control/approve/{request_id}", "POST"),
    ("/api/v1/dual-control/reject/{request_id}", "POST"),
    ("/api/v1/dual-control/pending", "GET"),
    ("/api/v1/dual-control/qr/{request_id}", "GET"),
]


class TestConditionA_SourceStructure:
    """Source-level structural checks — no import required."""

    @pytest.fixture(scope="class")
    def hf_source(self) -> str:
        return _read_source("hf-space/app.py")

    @pytest.fixture(scope="class")
    def hf_tree(self, hf_source: str) -> ast.Module:
        return ast.parse(hf_source)

    @pytest.mark.parametrize("endpoint_path,method", DUAL_CONTROL_REST_PATHS)
    def test_endpoint_has_require_role_dependency(
        self, hf_source: str, endpoint_path: str, method: str
    ) -> None:
        """Each dual-control endpoint MUST depend on require_role(admin, engineer)."""
        # Find the @app.post / @app.get decorator with the exact path
        expected_decorator = f'@app.{method.lower()}("{endpoint_path}"'
        assert expected_decorator in hf_source, (
            f"Could not find decorator {expected_decorator!r} in hf-space/app.py — "
            "endpoint may have been moved or renamed."
        )
        # Slice from the decorator to the next @app decorator (or end of file)
        start = hf_source.index(expected_decorator)
        # Find the next @app. after start (marks the next endpoint)
        next_decorator = hf_source.find("\n@app.", start + 1)
        if next_decorator == -1:
            endpoint_block = hf_source[start:]
        else:
            endpoint_block = hf_source[start:next_decorator]

        assert "require_role" in endpoint_block, (
            f"Endpoint {method} {endpoint_path} is missing `require_role` dependency. "
            "CONDITION A requires role-based auth on all 5 dual-control REST endpoints."
        )
        assert '"admin"' in endpoint_block and '"engineer"' in endpoint_block, (
            f"Endpoint {method} {endpoint_path} must require roles admin AND engineer, "
            "not just one or the other."
        )
        assert "Depends(" in endpoint_block, (
            f"Endpoint {method} {endpoint_path} must wrap require_role in Depends()."
        )

    @pytest.mark.parametrize("endpoint_path,method", DUAL_CONTROL_REST_PATHS)
    def test_endpoint_signature_has_user_param(
        self, hf_source: str, endpoint_path: str, method: str
    ) -> None:
        """Each dual-control endpoint MUST have a `user: CurrentUser` parameter."""
        expected_decorator = f'@app.{method.lower()}("{endpoint_path}"'
        start = hf_source.index(expected_decorator)
        next_decorator = hf_source.find("\n@app.", start + 1)
        endpoint_block = (
            hf_source[start:] if next_decorator == -1 else hf_source[start:next_decorator]
        )

        # The function signature must include `user: CurrentUser = Depends(...)`
        assert "user: CurrentUser" in endpoint_block, (
            f"Endpoint {method} {endpoint_path} must have `user: CurrentUser` parameter "
            "in its signature — identity must come from JWT, not body."
        )

    def test_create_request_uses_jwt_user_id_not_body(self, hf_source: str) -> None:
        """create_request must use user.user_id (JWT) for operator_id, not body.get()."""
        start = hf_source.index('@app.post("/api/v1/dual-control/request"')
        next_decorator = hf_source.find("\n@app.", start + 1)
        block = hf_source[start:] if next_decorator == -1 else hf_source[start:next_decorator]

        assert "operator_id=user.user_id" in block, (
            "create_approval_request must be called with operator_id=user.user_id "
            "(from JWT), not body.get('operator_id', ...)."
        )
        assert "operator_id=body.get" not in block, (
            "create_approval_request must NOT read operator_id from request body — "
            "this allows impersonation attacks (Condition A core fix)."
        )

    def test_approve_uses_jwt_user_id_not_body(self, hf_source: str) -> None:
        """approve must use user.user_id (JWT) for approver_id, not body.get()."""
        start = hf_source.index('@app.post("/api/v1/dual-control/approve/{request_id}"')
        next_decorator = hf_source.find("\n@app.", start + 1)
        block = hf_source[start:] if next_decorator == -1 else hf_source[start:next_decorator]

        assert "approver_id=user.user_id" in block, (
            "approve_request must be called with approver_id=user.user_id (from JWT), "
            "not body.get('approver_id', ...)."
        )
        assert "approver_id=body.get" not in block, (
            "approve_request must NOT read approver_id from request body — "
            "impersonation vulnerability (Condition A core fix)."
        )

    def test_reject_uses_jwt_user_id_not_body(self, hf_source: str) -> None:
        """reject must use user.user_id (JWT) for rejector_id, not body.get()."""
        start = hf_source.index('@app.post("/api/v1/dual-control/reject/{request_id}"')
        next_decorator = hf_source.find("\n@app.", start + 1)
        block = hf_source[start:] if next_decorator == -1 else hf_source[start:next_decorator]

        assert "rejector_id=user.user_id" in block, (
            "reject_request must be called with rejector_id=user.user_id (from JWT), "
            "not body.get('rejector_id', ...)."
        )
        assert "rejector_id=body.get" not in block, (
            "reject_request must NOT read rejector_id from request body — "
            "impersonation vulnerability (Condition A core fix)."
        )

    def test_approve_still_accepts_secret_in_body(self, hf_source: str) -> None:
        """approve must still accept `secret` (QR secret) in body — it's a 2FA factor, not identity."""
        start = hf_source.index('@app.post("/api/v1/dual-control/approve/{request_id}"')
        next_decorator = hf_source.find("\n@app.", start + 1)
        block = hf_source[start:] if next_decorator == -1 else hf_source[start:next_decorator]
        assert 'secret=body.get("secret")' in block, (
            "approve must still accept `secret` from body (QR 2FA factor). "
            "Only identity fields (approver_id) move to JWT."
        )

    def test_dependencies_imported(self, hf_source: str) -> None:
        """hf-space/app.py must import CurrentUser + require_role from api.dependencies."""
        assert "from api.dependencies import" in hf_source, (
            "hf-space/app.py must import from api.dependencies for the auth patch."
        )
        # Pull just the import line
        for line in hf_source.splitlines():
            if "from api.dependencies import" in line:
                assert "CurrentUser" in line, "Import must include CurrentUser"
                assert "require_role" in line, "Import must include require_role"
                return
        pytest.fail("Could not find `from api.dependencies import` line")

    def test_depends_imported_from_fastapi(self, hf_source: str) -> None:
        """hf-space/app.py must import Depends from fastapi."""
        # Either `from fastapi import Depends, ...` or `from fastapi import ..., Depends, ...`
        assert "Depends" in hf_source, "Depends not used anywhere in hf-space/app.py"
        for line in hf_source.splitlines():
            if line.startswith("from fastapi import"):
                assert "Depends" in line, f"Depends must be in the fastapi import line: {line!r}"
                return
        pytest.fail("No `from fastapi import` line found")


# ---------------------------------------------------------------------------
# Condition A — runtime introspection of FastAPI app
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def hf_app():
    """Load the HF Space FastAPI app for runtime introspection.

    ENV-VAR ISOLATION STRATEGY:
    We deliberately do NOT set ``ENGINEERING_SERVICE_API_KEY`` here.
    Reason: ``api.dependencies`` captures it at module load time
    (``API_KEY = os.getenv("ENGINEERING_SERVICE_API_KEY", "")``) and the
    captured value persists in the cached module even after env-var
    restore. If we set it, subsequent test files (e.g.,
    ``test_engineering_service.py``) that import ``api.routes`` would
    see the captured test value from our cached module, causing
    their no-auth requests to fail with 401 instead of 422.

    By NOT setting it, ``API_KEY = ""`` → no auth enforced → safe for
    introspection. The auth behavior is verified separately by the
    ``TestConditionE_SharedHelper`` tests, which set the env var
    INSIDE each test (and restore it via try/finally).
    """
    # Save & restore only DATABASE_URL (needed to avoid creating a real
    # ./data/etap_platform.db file during module load).
    _saved_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

    try:
        mod = _load_module("hf-space/app.py", "hf_space_app_p0_test")
        yield mod.app
    finally:
        if _saved_db_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = _saved_db_url


class TestConditionA_RuntimeWiring:
    """Runtime checks via FastAPI route introspection."""

    @pytest.mark.parametrize("endpoint_path,method", DUAL_CONTROL_REST_PATHS)
    def test_endpoint_registered(self, hf_app, endpoint_path: str, method: str) -> None:
        """Each dual-control endpoint must be registered on the app."""
        matching = [
            r
            for r in hf_app.routes
            if hasattr(r, "path")
            and r.path == endpoint_path
            and hasattr(r, "methods")
            and method in r.methods
        ]
        assert len(matching) == 1, (
            f"Expected exactly 1 route for {method} {endpoint_path}, found {len(matching)}"
        )

    @pytest.mark.parametrize("endpoint_path,method", DUAL_CONTROL_REST_PATHS)
    def test_endpoint_has_user_dependency(self, hf_app, endpoint_path: str, method: str) -> None:
        """Each dual-control endpoint must have a `user` parameter wired to Depends()."""
        matching = [
            r
            for r in hf_app.routes
            if hasattr(r, "path")
            and r.path == endpoint_path
            and hasattr(r, "methods")
            and method in r.methods
        ]
        assert matching, f"Route {method} {endpoint_path} not found"
        route = matching[0]
        sig = inspect.signature(route.endpoint)
        assert "user" in sig.parameters, (
            f"Endpoint {method} {endpoint_path} is missing `user` parameter. "
            "CONDITION A: identity must come from JWT, not body."
        )
        user_param = sig.parameters["user"]
        assert user_param.default is not inspect.Parameter.empty, (
            f"Endpoint {method} {endpoint_path} `user` param must have a Depends() default."
        )
        # The default should be a Depends() wrapping require_role(...)
        default_repr = repr(user_param.default)
        assert "Depends" in default_repr, (
            f"Endpoint {method} {endpoint_path} `user` param default must be Depends(...), "
            f"got: {default_repr}"
        )


# ---------------------------------------------------------------------------
# Condition E — /ws/cua/confirmation shared auth helper
# ---------------------------------------------------------------------------


class TestConditionE_SharedHelper:
    """Verify the shared authenticate_cua_confirmation_ws helper exists and behaves correctly."""

    @pytest.fixture(scope="class")
    def cua_ws_module(self):
        """Load cua_confirmation_ws module.

        This module has minimal side effects (no env-var reads at import
        time — env vars are read inside the helper function). Safe to
        cache for the duration of the test class.
        """
        return _load_module(
            "api/cua_confirmation_ws.py",
            "api_cua_confirmation_ws_p0_test",
        )

    def test_helper_is_exported(self, cua_ws_module) -> None:
        """authenticate_cua_confirmation_ws must be exported from the module."""
        assert hasattr(cua_ws_module, "authenticate_cua_confirmation_ws"), (
            "authenticate_cua_confirmation_ws must be defined in api/cua_confirmation_ws.py"
        )
        assert "authenticate_cua_confirmation_ws" in cua_ws_module.__all__, (
            "authenticate_cua_confirmation_ws must be in __all__"
        )

    def test_helper_uses_hmac_compare_digest(self) -> None:
        """The helper must use hmac.compare_digest (constant-time comparison)."""
        src = _read_source("api/cua_confirmation_ws.py")
        # Locate the helper function body
        marker = "async def authenticate_cua_confirmation_ws"
        assert marker in src, "authenticate_cua_confirmation_ws function not found"
        start = src.index(marker)
        body = src[start : start + 4000]
        assert "hmac.compare_digest" in body, (
            "authenticate_cua_confirmation_ws must use hmac.compare_digest "
            "(constant-time comparison) to prevent timing attacks"
        )

    def test_helper_reads_env_var(self) -> None:
        """The helper must read ENGINEERING_SERVICE_API_KEY from env."""
        src = _read_source("api/cua_confirmation_ws.py")
        start = src.index("async def authenticate_cua_confirmation_ws")
        body = src[start : start + 4000]
        assert "ENGINEERING_SERVICE_API_KEY" in body, (
            "Helper must read ENGINEERING_SERVICE_API_KEY env var"
        )

    def test_helper_accepts_header_or_query_param(self) -> None:
        """The helper must accept the key via x-api-key header OR ?token= query param."""
        src = _read_source("api/cua_confirmation_ws.py")
        start = src.index("async def authenticate_cua_confirmation_ws")
        body = src[start : start + 4000]
        assert 'websocket.headers.get("x-api-key")' in body, "Helper must check x-api-key header"
        assert 'websocket.query_params.get("token"' in body, (
            "Helper must check ?token= query param (for browser WS clients that can't set headers)"
        )

    def test_helper_fails_closed_when_env_unset(self, cua_ws_module, monkeypatch) -> None:
        """If ENGINEERING_SERVICE_API_KEY is not set, the helper MUST close with 1011."""
        # Use a fake WebSocket
        fake_ws = MagicMock()
        fake_ws.close = AsyncMock()
        fake_ws.headers = {}
        fake_ws.query_params = {}

        # Ensure env var is unset (monkeypatch auto-restores at test end)
        monkeypatch.delenv("ENGINEERING_SERVICE_API_KEY", raising=False)

        result = asyncio.run(cua_ws_module.authenticate_cua_confirmation_ws(fake_ws))

        assert result is False, (
            "Helper must return False (fail-closed) when ENGINEERING_SERVICE_API_KEY is unset"
        )
        fake_ws.close.assert_awaited_once()
        call_kwargs = fake_ws.close.call_args.kwargs
        assert call_kwargs.get("code") == 1011, (
            f"Helper must close with code 1011 (Internal Error) when env var is unset, "
            f"got {call_kwargs.get('code')}. Life-safety endpoints must NEVER fail open."
        )

    def test_helper_rejects_missing_key(self, cua_ws_module, monkeypatch) -> None:
        """Missing API key → close with 1008 (Policy Violation)."""
        monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "test-secret-12345")
        fake_ws = MagicMock()
        fake_ws.close = AsyncMock()
        fake_ws.headers = {}  # No x-api-key
        fake_ws.query_params = {}  # No ?token=

        result = asyncio.run(cua_ws_module.authenticate_cua_confirmation_ws(fake_ws))
        assert result is False
        fake_ws.close.assert_awaited_once()
        assert fake_ws.close.call_args.kwargs.get("code") == 1008

    def test_helper_rejects_wrong_key(self, cua_ws_module, monkeypatch) -> None:
        """Wrong API key → close with 1008."""
        monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "correct-secret")
        fake_ws = MagicMock()
        fake_ws.close = AsyncMock()
        fake_ws.headers = {"x-api-key": "WRONG-key"}
        fake_ws.query_params = {}

        result = asyncio.run(cua_ws_module.authenticate_cua_confirmation_ws(fake_ws))
        assert result is False
        assert fake_ws.close.call_args.kwargs.get("code") == 1008

    def test_helper_accepts_correct_header(self, cua_ws_module, monkeypatch) -> None:
        """Correct x-api-key header → return True, do not close."""
        monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "correct-secret")
        fake_ws = MagicMock()
        fake_ws.close = AsyncMock()
        fake_ws.headers = {"x-api-key": "correct-secret"}
        fake_ws.query_params = {}

        result = asyncio.run(cua_ws_module.authenticate_cua_confirmation_ws(fake_ws))
        assert result is True
        fake_ws.close.assert_not_awaited()

    def test_helper_accepts_correct_query_param(self, cua_ws_module, monkeypatch) -> None:
        """Correct ?token= query param → return True (mobile/browser client path)."""
        monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "correct-secret")
        fake_ws = MagicMock()
        fake_ws.close = AsyncMock()
        fake_ws.headers = {}  # No header
        fake_ws.query_params = {"token": "correct-secret"}

        result = asyncio.run(cua_ws_module.authenticate_cua_confirmation_ws(fake_ws))
        assert result is True
        fake_ws.close.assert_not_awaited()

    def test_helper_header_takes_precedence_over_query(self, cua_ws_module, monkeypatch) -> None:
        """If both header and query param are present, header value is used."""
        monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "correct-secret")
        fake_ws = MagicMock()
        fake_ws.close = AsyncMock()
        fake_ws.headers = {"x-api-key": "correct-secret"}
        fake_ws.query_params = {"token": "WRONG"}

        result = asyncio.run(cua_ws_module.authenticate_cua_confirmation_ws(fake_ws))
        assert result is True, (
            "Header should take precedence — if header matches, ignore query param"
        )


# ---------------------------------------------------------------------------
# Condition E — both registration sites delegate to the shared helper
# ---------------------------------------------------------------------------


class TestConditionE_BothSitesDelegate:
    """Verify BOTH api/routes.py AND hf-space/app.py use the shared helper."""

    def test_routes_py_uses_shared_helper(self) -> None:
        """api/routes.py /ws/cua/confirmation handler must call authenticate_cua_confirmation_ws."""
        src = _read_source("api/routes.py")
        marker = '@app.websocket("/ws/cua/confirmation")'
        assert marker in src
        start = src.index(marker)
        next_decorator = src.find("\n@app.", start + 1)
        block = src[start:] if next_decorator == -1 else src[start:next_decorator]

        assert "authenticate_cua_confirmation_ws" in block, (
            "api/routes.py /ws/cua/confirmation must call authenticate_cua_confirmation_ws "
            "(shared helper) — eliminates duplicate auth logic (Condition E)"
        )
        assert "from api.cua_confirmation_ws import" in block, (
            "api/routes.py must import authenticate_cua_confirmation_ws from api.cua_confirmation_ws"
        )

    def test_hf_space_uses_shared_helper(self) -> None:
        """hf-space/app.py /ws/cua/confirmation handler must call authenticate_cua_confirmation_ws."""
        src = _read_source("hf-space/app.py")
        marker = '@app.websocket("/ws/cua/confirmation")'
        assert marker in src
        start = src.index(marker)
        next_decorator = src.find("\n@app.", start + 1)
        block = src[start:] if next_decorator == -1 else src[start:next_decorator]

        assert "authenticate_cua_confirmation_ws" in block, (
            "hf-space/app.py /ws/cua/confirmation must call authenticate_cua_confirmation_ws "
            "(shared helper) — eliminates duplicate auth logic (Condition E)"
        )
        assert "from api.cua_confirmation_ws import" in block, (
            "hf-space/app.py must import authenticate_cua_confirmation_ws"
        )

    def test_routes_py_no_inline_auth(self) -> None:
        """api/routes.py must NOT have inline auth (hmac.compare_digest) in the WS handler."""
        src = _read_source("api/routes.py")
        marker = '@app.websocket("/ws/cua/confirmation")'
        start = src.index(marker)
        next_decorator = src.find("\n@app.", start + 1)
        block = src[start:] if next_decorator == -1 else src[start:next_decorator]

        # The inline auth check should be GONE — moved to the shared helper
        assert "hmac.compare_digest(api_key" not in block, (
            "api/routes.py WS handler must NOT have inline hmac.compare_digest — "
            "auth is now delegated to the shared helper."
        )

    def test_hf_space_no_silent_skip(self) -> None:
        """hf-space/app.py must NOT have the `if _hf_api_key:` silent-skip fail-open branch.

        We use AST parsing to check for the actual `if` statement (not just the
        substring, which could appear in a comment documenting the fix).
        """
        import ast as _ast

        src = _read_source("hf-space/app.py")
        tree = _ast.parse(src)

        # Walk the AST to find the websocket_cua_confirmation function
        for node in _ast.walk(tree):
            if (
                isinstance(node, _ast.AsyncFunctionDef)
                and node.name == "websocket_cua_confirmation"
            ):
                # Check that no `if` statement inside this function body
                # has a Name node referencing `_hf_api_key`
                for child in _ast.walk(node):
                    if isinstance(child, _ast.If):
                        # Walk the test condition to look for _hf_api_key Name
                        for name_node in _ast.walk(child.test):
                            if isinstance(name_node, _ast.Name) and name_node.id == "_hf_api_key":
                                pytest.fail(
                                    "hf-space/app.py websocket_cua_confirmation must NOT "
                                    "contain an `if _hf_api_key:` statement — this was "
                                    "the silent-skip fail-open bug. Auth is now delegated "
                                    "to the shared fail-closed helper."
                                )
                return
        pytest.fail("websocket_cua_confirmation function not found in hf-space/app.py")

    def test_both_apps_register_same_path(self) -> None:
        """Sanity: both apps still register /ws/cua/confirmation (the registration
        itself is intentional — two separate FastAPI apps for two deployment targets).
        The DUPLICATE is in the auth LOGIC, which is now shared. The path
        registration on two separate apps is correct and intentional."""
        routes_src = _read_source("api/routes.py")
        hf_src = _read_source("hf-space/app.py")
        assert '@app.websocket("/ws/cua/confirmation")' in routes_src
        assert '@app.websocket("/ws/cua/confirmation")' in hf_src


# ---------------------------------------------------------------------------
# Regression — make sure we didn't break the /ws/scada/live WS auth
# ---------------------------------------------------------------------------


class TestRegression_ScadaWSAuth:
    """The /ws/scada/live WS auth (separate from /ws/cua/confirmation) must be untouched."""

    def test_routes_py_scada_ws_auth_intact(self) -> None:
        """api/routes.py /ws/scada/live must still have its inline auth check."""
        src = _read_source("api/routes.py")
        marker = '@app.websocket("/ws/scada/live")'
        assert marker in src
        start = src.index(marker)
        next_decorator = src.find("\n@app.", start + 1)
        block = src[start:] if next_decorator == -1 else src[start:next_decorator]
        assert "hmac.compare_digest" in block, (
            "/ws/scada/live must retain its inline hmac.compare_digest auth — "
            "the Condition E refactor should NOT touch this separate endpoint."
        )

    def test_hf_space_dual_control_ws_auth_intact(self) -> None:
        """hf-space/app.py /ws/dual-control/approve (separate WS) must be untouched."""
        src = _read_source("hf-space/app.py")
        marker = '@app.websocket("/ws/dual-control/approve")'
        # If the path is different, just verify a dual-control WS still exists with auth
        if marker not in src:
            # Search for any /ws/dual-control* registration
            assert "/ws/dual-control" in src, "Expected /ws/dual-control/* WS endpoint"
            return
        start = src.index(marker)
        next_decorator = src.find("\n@app.", start + 1)
        block = src[start:] if next_decorator == -1 else src[start:next_decorator]
        # /ws/dual-control/approve uses a token-based auth — verify it's intact
        assert "compare_digest" in block or "token" in block.lower(), (
            "/ws/dual-control/approve auth must be intact — Condition E refactor "
            "should NOT have touched this separate WS endpoint."
        )


# ---------------------------------------------------------------------------
# Phase-2 P0 conditions doc — quick sanity check on the approval artifacts
# ---------------------------------------------------------------------------


class TestPhase2ApprovalArtifacts:
    """Verify the Phase-2 approval JSON reflects Conditions A + E (sanity only)."""

    @pytest.fixture(scope="class")
    def approval_json(self):
        path = Path("/home/z/my-project/download/ETAP_audit_artifacts/phase2_approval_batch.json")
        if not path.exists():
            pytest.skip("phase2_approval_batch.json not found (run outside audit context)")
        import json

        return json.loads(path.read_text())

    def test_dual_control_endpoints_count(self, approval_json) -> None:
        """The approval JSON must list exactly 5 dual-control endpoints."""
        dc = approval_json.get("dual_control_endpoints", [])
        assert len(dc) == 5, f"Expected 5 dual-control endpoints, got {len(dc)}"

    def test_dual_control_endpoints_paths(self, approval_json) -> None:
        """The 5 paths must match the endpoints we just patched."""
        dc = approval_json.get("dual_control_endpoints", [])
        actual_paths = {ep["path"] for ep in dc}
        expected_paths = {p for p, _ in DUAL_CONTROL_REST_PATHS}
        assert actual_paths == expected_paths, (
            f"Approval JSON paths mismatch.\n"
            f"  Expected: {expected_paths}\n"
            f"  Actual:   {actual_paths}"
        )
