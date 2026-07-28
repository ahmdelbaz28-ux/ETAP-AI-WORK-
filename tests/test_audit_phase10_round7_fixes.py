"""Phase 10: Self-critique Round 7 — 7 routers auth, hf-space WebSocket auth, CI pinning.

Tests verify:
- R7-1: All 7 previously unauthenticated routers now have dependencies=[Depends(get_api_key)]
- R7-2: hf-space /ws/cua/confirmation has API key auth
- R7-3: hf-space /ws/dual-control uses hmac.compare_digest (not ==)
- R7-C2: trivy-action pinned to release tag (not @master)
- R7-B1: terraform aks_identity_id output has deprecation warning
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_file(relative: str) -> str:
    return (_REPO_ROOT / relative).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# R7-1: Routers now have auth dependency
# ---------------------------------------------------------------------------


class TestRouterAuthentication:
    """Verify all previously unauthenticated routers now require API key."""

    @pytest.mark.parametrize(
        "file,router_line_fragment",
        [
            ("api/equipment.py", "dependencies=[Depends(get_api_key)]"),
            ("api/study_versions.py", "dependencies=[Depends(get_api_key)]"),
            ("api/templates.py", "dependencies=[Depends(get_api_key)]"),
            ("api/export.py", "dependencies=[Depends(get_api_key)]"),
            ("api/email_digest.py", "dependencies=[Depends(get_api_key)]"),
            ("api/scada.py", "dependencies=[Depends(get_api_key)]"),
            ("api/digital_twin.py", "dependencies=[Depends(get_api_key)]"),
        ],
    )
    def test_router_has_auth_dependency(self, file: str, router_line_fragment: str) -> None:
        """Each router must declare dependencies=[Depends(get_api_key)]."""
        source = _read_file(file)
        assert router_line_fragment in source, (
            f"{file}: router does NOT have {router_line_fragment}"
        )

    @pytest.mark.parametrize(
        "file",
        [
            "api/equipment.py",
            "api/study_versions.py",
            "api/templates.py",
            "api/export.py",
            "api/email_digest.py",
            "api/scada.py",
            "api/digital_twin.py",
        ],
    )
    def test_router_imports_get_api_key(self, file: str) -> None:
        """Each router must import get_api_key from api.dependencies."""
        source = _read_file(file)
        assert "get_api_key" in source, f"{file}: does not import get_api_key"


# ---------------------------------------------------------------------------
# R7-2: hf-space /ws/cua/confirmation has auth
# ---------------------------------------------------------------------------


class TestHFSpaceCUAWebSocketAuth:
    """Verify hf-space CUA confirmation WebSocket requires API key.

    REVISED (Phase-2 P0 / Condition E): Auth logic has been refactored
    from inline checks in ``hf-space/app.py`` to the shared helper
    ``api.cua_confirmation_ws.authenticate_cua_confirmation_ws`` (same
    helper used by ``api/routes.py``). The tests now verify:
      1. ``hf-space/app.py`` delegates to the shared helper.
      2. The shared helper has all the required auth properties.
      3. The previous silent-skip fail-open branch (``if _hf_api_key:``)
         has been removed.
    """

    @pytest.fixture(scope="class")
    def hf_source(self) -> str:
        return _read_file("hf-space/app.py")

    @pytest.fixture(scope="class")
    def cua_ws_source(self) -> str:
        """Source of the shared auth helper module."""
        return _read_file("api/cua_confirmation_ws.py")

    def test_hf_space_delegates_to_shared_helper(self, hf_source: str) -> None:
        """hf-space/app.py /ws/cua/confirmation must call the shared helper."""
        ws_pos = hf_source.index("websocket_cua_confirmation")
        ws_body = hf_source[ws_pos : ws_pos + 1500]
        assert "authenticate_cua_confirmation_ws" in ws_body, (
            "hf-space/app.py /ws/cua/confirmation must call authenticate_cua_confirmation_ws "
            "(shared helper). Inline auth was removed in Condition E refactor."
        )

    def test_no_silent_skip_fail_open(self, hf_source: str) -> None:
        """The `if _hf_api_key:` silent-skip fail-open branch must be GONE.

        We use AST parsing to check for the actual `if` statement (not just
        the substring, which can legitimately appear in a comment documenting
        the bug fix).
        """
        import ast as _ast

        tree = _ast.parse(hf_source)
        for node in _ast.walk(tree):
            if (
                isinstance(node, _ast.AsyncFunctionDef)
                and node.name == "websocket_cua_confirmation"
            ):
                for child in _ast.walk(node):
                    if isinstance(child, _ast.If):
                        for name_node in _ast.walk(child.test):
                            if isinstance(name_node, _ast.Name) and name_node.id == "_hf_api_key":
                                pytest.fail(
                                    "hf-space/app.py websocket_cua_confirmation must NOT "
                                    "contain an `if _hf_api_key:` statement — this was the "
                                    "silent-skip fail-open bug. Auth is now delegated to the "
                                    "shared fail-closed helper."
                                )
                return
        pytest.fail("websocket_cua_confirmation function not found in hf-space/app.py")

    def test_shared_helper_has_compare_digest(self, cua_ws_source: str) -> None:
        """Shared helper must use hmac.compare_digest for constant-time comparison."""
        marker = "async def authenticate_cua_confirmation_ws"
        assert marker in cua_ws_source
        start = cua_ws_source.index(marker)
        helper_body = cua_ws_source[start : start + 4000]
        assert "compare_digest" in helper_body, "Shared helper must use hmac.compare_digest"

    def test_shared_helper_checks_x_api_key_or_token(self, cua_ws_source: str) -> None:
        """Shared helper must accept x-api-key header OR ?token= query param."""
        marker = "async def authenticate_cua_confirmation_ws"
        start = cua_ws_source.index(marker)
        helper_body = cua_ws_source[start : start + 4000]
        assert "x-api-key" in helper_body, "Shared helper must check x-api-key header"
        assert "token" in helper_body, "Shared helper must check ?token= query param"

    def test_shared_helper_closes_with_1008(self, cua_ws_source: str) -> None:
        """Shared helper must close with code 1008 on auth failure."""
        marker = "async def authenticate_cua_confirmation_ws"
        start = cua_ws_source.index(marker)
        helper_body = cua_ws_source[start : start + 4000]
        assert "1008" in helper_body, "Shared helper must close with code=1008 on auth failure"


# ---------------------------------------------------------------------------
# R7-3: hf-space /ws/dual-control uses hmac.compare_digest
# ---------------------------------------------------------------------------


class TestHFSpaceDualControlTimingAttack:
    """Verify dual-control WebSocket uses constant-time comparison."""

    @pytest.fixture(scope="class")
    def hf_source(self) -> str:
        return _read_file("hf-space/app.py")

    def test_dual_control_uses_compare_digest(self, hf_source: str) -> None:
        """Dual-control token must use hmac.compare_digest, not ==."""
        dc_pos = hf_source.index("dual_control")
        dc_body = hf_source[dc_pos : dc_pos + 5000]
        # The auth check section
        auth_section = (
            dc_body[dc_body.index("token != expected") - 200 :]
            if "token != expected" in dc_body
            else dc_body
        )
        assert "token != expected" not in auth_section, (
            "Dual-control must NOT use != for token comparison (timing attack)"
        )
        assert "compare_digest" in auth_section, (
            "Dual-control must use hmac.compare_digest for token comparison"
        )


# ---------------------------------------------------------------------------
# R7-C2: CI trivy-action pinned
# ---------------------------------------------------------------------------


class TestCIPinning:
    """Verify trivy-action is pinned to a release tag, not @master."""

    @pytest.fixture(scope="class")
    def ci_cd_source(self) -> str:
        return _read_file(".github/workflows/ci-cd.yml")

    def test_no_trivy_at_master(self, ci_cd_source: str) -> None:
        """trivy-action must NOT be pinned to @master."""
        assert "trivy-action@master" not in ci_cd_source, (
            "trivy-action must not use @master (supply chain risk)"
        )

    def test_trivy_pinned_to_tag(self, ci_cd_source: str) -> None:
        """trivy-action must be pinned to a specific version tag OR commit SHA.

        Updated R7-C2: pinning to a commit SHA is actually MORE secure than
        a version tag (tags can be moved by repo maintainers; commit SHAs
        are immutable). The CI/CD file was updated to use SHA pinning —
        this test now accepts either form.
        """
        # Accept either:
        #   trivy-action@0.9.2          (version tag — original R7-C2 form)
        #   trivy-action@<40-char SHA>  (commit SHA — stricter, current form)
        import re

        # Match `trivy-action@` followed by either:
        #   - a version tag like `0.9.2` (digits and dots)
        #   - a 40-char commit SHA (hex)
        pattern = r"trivy-action@(?:[0-9]+\.[0-9]+\.[0-9]+|[0-9a-f]{40})"
        assert re.search(pattern, ci_cd_source), (
            "trivy-action must be pinned to a version tag or commit SHA — "
            "must NOT use @master or @main (mutable refs)."
        )


# ---------------------------------------------------------------------------
# R7-B1: Terraform output bug documented
# ---------------------------------------------------------------------------


class TestTerraformOutputFix:
    """Verify terraform aks_identity_id output has deprecation warning."""

    @pytest.fixture(scope="class")
    def outputs_tf(self) -> str:
        return _read_file("terraform/modules/security/outputs.tf")

    def test_aks_identity_deprecated(self, outputs_tf: str) -> None:
        """aks_identity_id output must have deprecation warning."""
        assert "DEPRECATED" in outputs_tf, "aks_identity_id output must have DEPRECATED description"
        assert "deprecated  = true" in outputs_tf, (
            "aks_identity_id output must be marked as deprecated"
        )
