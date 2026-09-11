"""
tests/test_worker_auth_contract.py — WP1 auth contract.

Contract under test: the cloud-side provider and the Windows worker speak the
SAME unified Bearer scheme.

1. RemoteEtapProvider sends ``Authorization: Bearer <ETAP_WORKER_API_KEY>``
   and never emits the removed legacy header.
2. The worker accepts that exact credential shape: Bearer JWT access
   tokens flow to RBAC, wrong/absent credentials are rejected, static key
   bypass is completely removed, and the legacy header no longer exists
   on the worker side.
"""

from __future__ import annotations

from typing import Any

import pytest
import requests

import etap_integration.etap_provider as provider_mod
import etap_integration.etap_worker_service as worker_mod
from etap_integration.etap_com import ETAPStudyType
from etap_integration.etap_provider import ETAPResult, RemoteEtapProvider

LEGACY_HEADER = "X-ETAP-Worker-Key"


# ---------------------------------------------------------------------------
# Provider side of the contract
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self) -> None:
        self.status_code = 200
        self.text = "ok"

    def json(self) -> dict[str, Any]:
        return {"success": True, "data": {}, "warnings": [], "errors": [], "execution_time": 0.1}


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> RemoteEtapProvider:
    monkeypatch.setenv("USE_ETAP", "true")
    return RemoteEtapProvider("http://worker.example:8081", "shared-secret-01")


def test_provider_sends_unified_bearer_header(
    provider: RemoteEtapProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def _fake_post(url: str, json: Any = None, headers: Any = None, timeout: Any = None):
        captured["url"] = url
        captured["headers"] = headers
        return _FakeResponse()

    monkeypatch.setattr(provider_mod.requests, "post", _fake_post)
    result = provider.execute_study("demo.edb", ETAPStudyType.LOAD_FLOW)

    assert result.success is True
    assert captured["headers"]["Authorization"] == "Bearer shared-secret-01"
    assert LEGACY_HEADER not in captured["headers"]


def test_provider_retries_preserve_bearer_header(
    provider: RemoteEtapProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen_headers: list[dict[str, str]] = []
    calls = {"n": 0}

    def _flaky_post(url: str, json: Any = None, headers: Any = None, timeout: Any = None):
        calls["n"] += 1
        seen_headers.append(dict(headers or {}))
        if calls["n"] < 3:
            raise ConnectionError("transient")
        return _FakeResponse()

    monkeypatch.setattr(provider_mod.requests, "post", _flaky_post)
    monkeypatch.setattr(provider_mod.time, "sleep", lambda *_a, **_k: None)
    result = provider.execute_study("demo.edb", ETAPStudyType.LOAD_FLOW)

    assert result.success is True
    assert calls["n"] == 3
    assert all(h.get("Authorization") == "Bearer shared-secret-01" for h in seen_headers)


# ---------------------------------------------------------------------------
# Worker side of the contract
# ---------------------------------------------------------------------------


class _FakeProject:
    def run_study(self, study_type: ETAPStudyType, **kwargs: Any):
        class _R:
            success = True
            data = {"echo": kwargs}
            warnings: list[str] = []
            errors: list[str] = []

        return _R()


class _FakeAutomation:
    def __init__(self, visible: bool = False) -> None:
        self.visible = visible

    def __enter__(self) -> _FakeAutomation:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def open_project(self, path: str) -> _FakeProject | None:
        return _FakeProject() if str(path).endswith(".edb") else None


@pytest.fixture
def worker_client(monkeypatch: pytest.MonkeyPatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(worker_mod, "ETAPAutomation", _FakeAutomation)
    return TestClient(worker_mod.app, raise_server_exceptions=False)


def test_no_static_key_bypass(worker_client) -> None:
    """Confirm static key environment variable and bypass logic are completely removed."""
    assert not hasattr(worker_mod, "STATIC_BEARER_ENV")
    assert not hasattr(worker_mod, "_get_static_bearer_key")
    response = worker_client.post(
        "/execute",
        json={"project_path": "demo.edb", "study_type": "LOAD_FLOW"},
        headers={"Authorization": "Bearer static-key-42"},
    )
    assert response.status_code in (401, 403)


def test_bearer_token_without_permission_rejected_403(
    worker_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bearer token without required study permission must return 403 Forbidden."""

    class _StubAuthzForbidden:
        def check_permission(self, token: str, permission: Any) -> bool:
            return False

    monkeypatch.setattr(worker_mod, "get_authz_manager", lambda: _StubAuthzForbidden())
    response = worker_client.post(
        "/execute",
        json={"project_path": "demo.edb", "study_type": "LOAD_FLOW"},
        headers={"Authorization": "Bearer valid-token-insufficient-perms"},
    )
    assert response.status_code == 403
    assert "insufficient permissions" in response.json().get("detail", "").lower()


def test_missing_authorization_rejected(worker_client) -> None:
    response = worker_client.post(
        "/execute",
        json={"project_path": "demo.edb", "study_type": "LOAD_FLOW"},
    )
    # HTTPBearer(auto_error=True) rejects a missing Authorization header
    assert response.status_code in (401, 403)


def test_jwt_shaped_token_flows_to_rbac(worker_client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Valid JWT credentials reach the RBAC manager and grant access upon permission."""
    checked: dict[str, Any] = {}

    class _StubAuthz:
        def check_permission(self, token: str, permission: Any) -> bool:
            checked["token"] = token
            return True

    monkeypatch.setattr(worker_mod, "get_authz_manager", lambda: _StubAuthz())
    response = worker_client.post(
        "/execute",
        json={"project_path": "demo.edb", "study_type": "LOAD_FLOW"},
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"},
    )
    assert response.status_code == 200
    assert checked["token"].startswith("eyJ")


# ---------------------------------------------------------------------------
# Cross-side contract assertions
# ---------------------------------------------------------------------------


def test_legacy_header_removed_from_both_sides() -> None:
    import inspect

    provider_src = inspect.getsource(provider_mod)
    worker_src = inspect.getsource(worker_mod)
    assert LEGACY_HEADER not in provider_src
    assert LEGACY_HEADER not in worker_src
    assert not hasattr(worker_mod, "api_key_header")
    assert not hasattr(worker_mod, "_reject_legacy_api_key")


def test_provider_result_dataclass_shape_matches_worker_response() -> None:
    """Provider consumes exactly the fields the worker's StudyResponse emits."""
    response_fields = set(worker_mod.StudyResponse.model_fields.keys())
    consumed = {"success", "data", "warnings", "errors", "execution_time"}
    assert consumed <= response_fields
    result = ETAPResult(True, {}, [], [], 0.5)
    assert {result.success is True} and result.execution_time == 0.5
