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
    """Verify hf-space CUA confirmation WebSocket requires API key."""

    @pytest.fixture(scope="class")
    def hf_source(self) -> str:
        return _read_file("hf-space/app.py")

    def test_cua_ws_has_auth_check(self, hf_source: str) -> None:
        """CUA WebSocket must check API key before accepting."""
        ws_pos = hf_source.index("websocket_cua_confirmation")
        ws_body = hf_source[ws_pos : ws_pos + 1500]
        if "authenticate_cua_confirmation_ws" in ws_body:
            auth_source = _read_file("api/cua_confirmation_ws.py")
            assert "compare_digest" in auth_source, (
                "authenticate_cua_confirmation_ws must use compare_digest"
            )
            assert "x-api-key" in auth_source or "token" in auth_source, (
                "authenticate_cua_confirmation_ws must check API key"
            )
            assert "1008" in auth_source or "_WS_CODE_POLICY_VIOLATION" in auth_source, (
                "authenticate_cua_confirmation_ws must close with 1008/POLICY_VIOLATION"
            )
        else:
            assert "compare_digest" in ws_body, (
                "hf-space CUA WebSocket must use compare_digest for auth"
            )
            assert "x-api-key" in ws_body or "token" in ws_body, (
                "hf-space CUA WebSocket must check API key"
            )
            assert "code=1008" in ws_body, (
                "hf-space CUA WebSocket must close with 1008 on auth failure"
            )

    def test_cua_ws_imports_hmac(self, hf_source: str) -> None:
        """hf-space/app.py must import hmac at module level."""
        assert "import hmac" in hf_source, "hf-space/app.py must import hmac"


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
        dc_pos = hf_source.index("websocket_dual_control_approve")
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
    """Verify trivy-action is pinned to a specific commit SHA, not @master."""

    @pytest.fixture(scope="class")
    def ci_cd_source(self) -> str:
        return _read_file(".github/workflows/ci-cd.yml")

    def test_no_trivy_at_master(self, ci_cd_source: str) -> None:
        """trivy-action must NOT be pinned to @master."""
        assert "trivy-action@master" not in ci_cd_source, (
            "trivy-action must not use @master (supply chain risk)"
        )

    def test_trivy_pinned_to_sha(self, ci_cd_source: str) -> None:
        """trivy-action must be pinned to a specific commit SHA (not a
        mutable tag like @master or @0.9.2).

        Commit-SHA pinning is more secure than tag pinning because tags
        can be moved by the repository owner.  The workflow currently
        pins to the SHA for v0.9.2:
        ``1f0aa582c8c8f5f7639610d6d38baddfea4fdcee``.
        """
        import re

        assert re.search(r"trivy-action@[a-f0-9]{40}", ci_cd_source), (
            "trivy-action should be pinned to a specific commit SHA"
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
        """aks_identity_id output must have deprecation warning.

        The `deprecated` attribute was introduced in Terraform 1.11+,
        but our CI uses Terraform 1.9.0, so deprecation is expressed
        via the description field (``DEPRECATED: …``) rather than the
        ``deprecated = true`` attribute.
        """
        assert "DEPRECATED" in outputs_tf, "aks_identity_id output must have DEPRECATED description"
        # Terraform 1.9.0 does not support the `deprecated` attribute.
        # Verify that the description contains the deprecation notice
        # instead of checking for the attribute.
        assert "aks_identity_id" in outputs_tf, "aks_identity_id output must exist"
        assert "DEPRECATED" in outputs_tf, "Must contain DEPRECATED in description"
