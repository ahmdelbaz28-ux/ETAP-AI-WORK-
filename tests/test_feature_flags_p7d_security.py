"""P7d — backend-authoritative security tests for api/feature_flags.py.

Complements tests/test_feature_flags.py with the P7d security contract:

* Safe defaults      — every registry flag fails closed; chat_first_ui is NOT
                       in the registry (P10 rollout stays backend-controlled).
* Authorization      — unauthenticated reads/mutations are rejected in
                       production mode.
* Contract           — unknown flags are rejected (404) and malformed values
                       are rejected (422) on GET and PATCH.
* Audit              — security-sensitive PATCH emits a feature_flag_toggled
                       audit record and never leaks the API key / secrets.
* Precedence         — ENV overrides behave as documented (dev forces
                       effective ON; production honours the persisted value).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.feature_flags import DEFAULT_FEATURE_FLAGS

# ---------------------------------------------------------------------------
# Fixtures (same deployment mode as tests/test_feature_flags.py: API-key auth
# with api.rbac unavailable so the router falls back to get_api_key).
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / ".feature-flags.json"
    monkeypatch.setenv("FEATURE_FLAGS_PATH", str(db))
    return db


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "test-secret-key-for-pytest")
    import api.dependencies as deps

    monkeypatch.setattr(deps, "API_KEY", "test-secret-key-for-pytest")

    import sys

    class _BrokenRbac:
        def __getattr__(self, name):
            raise ImportError(f"api.rbac.{name} blocked in test fixture")

    monkeypatch.setitem(sys.modules, "api.rbac", _BrokenRbac())
    return "test-secret-key-for-pytest"


@pytest.fixture
def client(temp_db: Path, api_key: str) -> TestClient:
    import importlib

    import api.feature_flags as ff

    importlib.reload(ff)
    app = FastAPI()
    app.include_router(ff.router)
    return TestClient(app)


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key}


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)


def _production_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ENGINEERING_SERVICE_AUTH_DISABLED", "false")
    monkeypatch.setattr("api.dependencies.API_KEY", "test-secret-key")


# ---------------------------------------------------------------------------
# Safe defaults
# ---------------------------------------------------------------------------


class TestSafeDefaults:
    def test_every_registry_flag_fails_closed(self):
        """All security-sensitive defaults must be disabled (fail closed)."""
        for key, cfg in DEFAULT_FEATURE_FLAGS.items():
            assert cfg.get("enabled", True) is False, (
                f"Flag '{key}' must default to disabled (fail closed)"
            )

    def test_chat_first_ui_is_not_in_registry(self):
        """chat_first_ui (P10 rollout) must NOT be a registry default.

        Its activation is backend-controlled via the rollout file; P7d must
        not enable it prematurely and must not expose it as a plain toggle.
        """
        assert "chat_first_ui" not in DEFAULT_FEATURE_FLAGS

    def test_get_chat_first_ui_fails_closed(self, client: TestClient, auth_headers: dict):
        """chat_first_ui is not in the registry → GET must 404 (fail closed).

        The P6 UI gateway treats any failure as "flag unavailable → legacy
        UI", so a 404 here preserves the existing rollout semantics.
        """
        resp = client.get("/api/v1/feature-flags/chat_first_ui", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


class TestAuthorization:
    def test_unauthenticated_get_rejected_in_production(self, client: TestClient, monkeypatch):
        _production_env(monkeypatch)
        resp = client.get("/api/v1/feature-flags")
        assert resp.status_code in (401, 403)

    def test_unauthenticated_patch_rejected_in_production(self, client: TestClient, monkeypatch):
        _production_env(monkeypatch)
        resp = client.patch(
            "/api/v1/feature-flags/harmonic_analysis",
            json={"enabled": True},
        )
        assert resp.status_code in (401, 403)

    def test_wrong_api_key_patch_rejected_in_production(self, client: TestClient, monkeypatch):
        _production_env(monkeypatch)
        resp = client.patch(
            "/api/v1/feature-flags/harmonic_analysis",
            json={"enabled": True},
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code in (401, 403)

    def test_authorized_patch_accepted(self, client: TestClient, auth_headers: dict):
        resp = client.patch(
            "/api/v1/feature-flags/harmonic_analysis",
            json={"enabled": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["enabled"] is True


# ---------------------------------------------------------------------------
# Contract (registry allowlist + validation)
# ---------------------------------------------------------------------------


class TestContract:
    def test_get_unknown_flag_rejected(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/v1/feature-flags/totally_unknown_flag", headers=auth_headers)
        assert resp.status_code == 404

    def test_patch_unknown_flag_rejected(self, client: TestClient, auth_headers: dict):
        """The browser can never introduce arbitrary flag names."""
        resp = client.patch(
            "/api/v1/feature-flags/totally_unknown_flag",
            json={"enabled": True},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_patch_malformed_value_rejected(self, client: TestClient, auth_headers: dict):
        resp = client.patch(
            "/api/v1/feature-flags/harmonic_analysis",
            json={"enabled": "yes-please"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_patch_missing_field_rejected(self, client: TestClient, auth_headers: dict):
        resp = client.patch(
            "/api/v1/feature-flags/harmonic_analysis",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class TestAudit:
    def test_patch_emits_audit_record(
        self, client: TestClient, auth_headers: dict, caplog: pytest.LogCaptureFixture
    ):
        with caplog.at_level(logging.INFO, logger="audit"):
            resp = client.patch(
                "/api/v1/feature-flags/motor_starting",
                json={"enabled": True},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        audit_records = [
            r
            for r in caplog.records
            if r.name == "audit" and "feature_flag_toggled" in r.getMessage()
        ]
        assert audit_records, "PATCH must emit a feature_flag_toggled audit record"
        message = audit_records[-1].getMessage()
        assert "motor_starting" in message
        assert "old=False" in message
        assert "new=True" in message

    def test_audit_record_contains_no_secrets(
        self, client: TestClient, auth_headers: dict, caplog: pytest.LogCaptureFixture
    ):
        """The API key / any credential must never appear in audit output."""
        with caplog.at_level(logging.INFO):
            client.patch(
                "/api/v1/feature-flags/motor_starting",
                json={"enabled": True},
                headers=auth_headers,
            )
        assert "test-secret-key-for-pytest" not in caplog.text


# ---------------------------------------------------------------------------
# Environment precedence
# ---------------------------------------------------------------------------


class TestPrecedence:
    def test_production_honours_persisted_enabled_state(
        self, client: TestClient, monkeypatch, auth_headers: dict
    ):
        # Enable the flag (persisted), then evaluate in production env.
        client.patch(
            "/api/v1/feature-flags/optimal_power_flow",
            json={"enabled": True},
            headers=auth_headers,
        )
        monkeypatch.setenv("ENV", "production")
        resp = client.get("/api/v1/feature-flags/optimal_power_flow", headers=auth_headers)
        data = resp.json()["data"]
        assert data["enabled"] is True
        assert data["effective_enabled"] is True

    def test_production_honours_persisted_disabled_state(
        self, client: TestClient, monkeypatch, auth_headers: dict
    ):
        client.patch(
            "/api/v1/feature-flags/optimal_power_flow",
            json={"enabled": False},
            headers=auth_headers,
        )
        monkeypatch.setenv("ENV", "production")
        resp = client.get("/api/v1/feature-flags/optimal_power_flow", headers=auth_headers)
        data = resp.json()["data"]
        assert data["enabled"] is False
        assert data["effective_enabled"] is False

    def test_patch_persists_across_reload(self, client: TestClient, auth_headers: dict):
        """Toggles survive process restarts (JSON persistence contract)."""
        client.patch(
            "/api/v1/feature-flags/transient_stability",
            json={"enabled": True},
            headers=auth_headers,
        )
        from api.feature_flags import _load_flags

        assert _load_flags()["transient_stability"]["enabled"] is True
