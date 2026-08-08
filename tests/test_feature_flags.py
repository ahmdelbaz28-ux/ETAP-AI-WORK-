"""Tests for api/feature_flags.py — TASK-9 backend router.

Verifies:
- GET /api/v1/feature-flags returns all 4 default flags
- GET /api/v1/feature-flags/{key} returns single flag
- GET /api/v1/feature-flags/{unknown} returns 404
- PATCH /api/v1/feature-flags/{key} toggles enabled state
- PATCH persists to a JSON file so changes survive re-instantiation
- In development env, effective_enabled is always True (dev override)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.feature_flags import (
    DEFAULT_FEATURE_FLAGS,
    _db_path,
    _load_flags,
    _save_flags,
)
from api.feature_flags import (
    router as feature_flags_router,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point FEATURE_FLAGS_PATH at a temp file so tests don't clobber real config."""
    db = tmp_path / ".feature-flags.json"
    monkeypatch.setenv("FEATURE_FLAGS_PATH", str(db))
    return db


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Set ENGINEERING_SERVICE_API_KEY so get_api_key accepts the test header.

    Also forces ``api.rbac.require_permission`` to be unavailable so the
    feature_flags router falls back to ``get_api_key`` (API-key auth) —
    this matches the deployment mode where RBAC DB is not configured and
    the platform relies on API keys for admin endpoints. In production
    with RBAC enabled, the router uses ``require_permission`` instead.
    """
    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "test-secret-key-for-pytest")
    # Also patch the module-level API_KEY (read at import time in
    # api/dependencies.py) so production-mode tests see the configured key.
    import api.dependencies as deps

    monkeypatch.setattr(deps, "API_KEY", "test-secret-key-for-pytest")

    # Block import of api.rbac.require_permission so _require_permission()
    # falls back to get_api_key. We do this by injecting a broken module
    # into sys.modules BEFORE the router is imported.
    import sys

    class _BrokenRbac:
        def __getattr__(self, name):
            raise ImportError(f"api.rbac.{name} blocked in test fixture")

    monkeypatch.setitem(sys.modules, "api.rbac", _BrokenRbac())

    return "test-secret-key-for-pytest"


@pytest.fixture
def client(temp_db: Path, api_key: str) -> TestClient:
    """Build a minimal FastAPI app with only the feature_flags router.

    The fixture sets ENGINEERING_SERVICE_API_KEY=api_key so the get_api_key
    fallback (used when rbac.require_permission cannot bind a DB session)
    accepts requests carrying ``X-API-Key: <api_key>``.
    """
    # Re-import feature_flags so _require_permission picks up the
    # blocked api.rbac module and falls back to get_api_key.
    import importlib

    import api.feature_flags as ff

    importlib.reload(ff)
    app = FastAPI()
    app.include_router(ff.router)
    return TestClient(app)


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    """Return headers carrying the test API key for authenticated requests."""
    return {"X-API-Key": api_key}


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch):
    """Ensure ENV/APP_ENV are unset by default for predictable test behaviour."""
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)


# ---------------------------------------------------------------------------
# GET /api/v1/feature-flags
# ---------------------------------------------------------------------------


class TestListFeatureFlags:
    def test_returns_all_four_default_flags(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/v1/feature-flags", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["total"] == 4
        keys = {f["key"] for f in body["data"]}
        assert keys == set(DEFAULT_FEATURE_FLAGS.keys())

    def test_unauthenticated_request_rejected(self, client: TestClient, monkeypatch):
        """Endpoints MUST require auth in production — no X-API-Key header → 401.

        In development env, get_api_key() allows requests without a key (legacy
        behaviour for local dev). We test the production path by setting
        ENV=production so the dev bypass is disabled.
        """
        monkeypatch.setenv("ENV", "production")
        resp = client.get("/api/v1/feature-flags")
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 without auth in production, got {resp.status_code}. "
            "Feature-flags endpoints MUST require authentication in production."
        )

    def test_invalid_api_key_rejected(self, client: TestClient, monkeypatch):
        """Wrong X-API-Key value → 401 in production."""
        monkeypatch.setenv("ENV", "production")
        resp = client.get(
            "/api/v1/feature-flags",
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code in (401, 403)

    def test_includes_effective_enabled_field(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/v1/feature-flags", headers=auth_headers)
        for flag in resp.json()["data"]:
            assert "effective_enabled" in flag
            assert isinstance(flag["effective_enabled"], bool)

    def test_dev_env_forces_effective_true(self, client: TestClient, monkeypatch, auth_headers: dict):
        monkeypatch.setenv("ENV", "development")
        resp = client.get("/api/v1/feature-flags", headers=auth_headers)
        for flag in resp.json()["data"]:
            assert flag["effective_enabled"] is True, (
                f"Dev env should force effective_enabled=True for {flag['key']}"
            )

    def test_prod_env_respects_disabled_state(self, client: TestClient, monkeypatch, auth_headers: dict):
        monkeypatch.setenv("ENV", "production")
        resp = client.get("/api/v1/feature-flags", headers=auth_headers)
        for flag in resp.json()["data"]:
            # All defaults are disabled, so effective should be False in prod
            assert flag["effective_enabled"] is False


# ---------------------------------------------------------------------------
# GET /api/v1/feature-flags/{key}
# ---------------------------------------------------------------------------


class TestGetSingleFlag:
    def test_returns_single_flag(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/v1/feature-flags/harmonic_analysis", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["key"] == "harmonic_analysis"
        assert data["status"] == "beta"

    def test_unknown_flag_returns_404(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/v1/feature-flags/nonexistent_flag", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/feature-flags/{key}
# ---------------------------------------------------------------------------


class TestPatchFeatureFlag:
    def test_toggle_persists_to_disk(self, client: TestClient, temp_db: Path, auth_headers: dict):
        # Initially disabled (default)
        resp = client.patch(
            "/api/v1/feature-flags/harmonic_analysis",
            json={"enabled": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["enabled"] is True
        assert data["previous_enabled"] is False

        # File on disk should now reflect the new state
        assert temp_db.exists(), "PATCH did not persist to disk"
        saved = json.loads(temp_db.read_text())
        assert saved["harmonic_analysis"]["enabled"] is True

    def test_toggle_survives_reload(self, client: TestClient, temp_db: Path, auth_headers: dict):
        # Toggle ON
        client.patch(
            "/api/v1/feature-flags/motor_starting",
            json={"enabled": True},
            headers=auth_headers,
        )
        # Reload from disk via _load_flags
        flags = _load_flags()
        assert flags["motor_starting"]["enabled"] is True

    def test_patch_unknown_flag_returns_404(self, client: TestClient, auth_headers: dict):
        resp = client.patch(
            "/api/v1/feature-flags/nonexistent_flag",
            json={"enabled": True},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_patch_in_dev_env_reports_effective_true_even_if_disabled(
        self, client: TestClient, monkeypatch, auth_headers: dict
    ):
        monkeypatch.setenv("ENV", "development")
        # Disable the flag (persisted)
        resp = client.patch(
            "/api/v1/feature-flags/transient_stability",
            json={"enabled": False},
            headers=auth_headers,
        )
        data = resp.json()["data"]
        assert data["enabled"] is False  # persisted value
        assert data["effective_enabled"] is True  # dev override


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_is_feature_enabled_dev_env_always_true(self, monkeypatch):
        monkeypatch.setenv("ENV", "development")
        from api.feature_flags import is_feature_enabled

        # Even an unknown flag is True in dev
        assert is_feature_enabled("unknown_thing") is True

    def test_is_feature_enabled_prod_unknown_flag_is_true(self, monkeypatch):
        # Unknown flags default to enabled (fail-open for non-flagged studies)
        monkeypatch.setenv("ENV", "production")
        from api.feature_flags import is_feature_enabled

        assert is_feature_enabled("not_in_dict") is True

    def test_get_disabled_studies_dev_returns_empty(self, monkeypatch):
        monkeypatch.setenv("ENV", "test")
        from api.feature_flags import get_disabled_studies

        assert get_disabled_studies() == []

    def test_save_and_load_round_trip(self, temp_db: Path):
        flags = _load_flags()
        flags["harmonic_analysis"]["enabled"] = True
        _save_flags(flags)
        reloaded = _load_flags()
        assert reloaded["harmonic_analysis"]["enabled"] is True

    def test_load_flags_handles_missing_file(self, tmp_path: Path, monkeypatch):
        # Point at a non-existent file — should fall back to defaults
        monkeypatch.setenv("FEATURE_FLAGS_PATH", str(tmp_path / "missing.json"))
        flags = _load_flags()
        assert set(flags.keys()) == set(DEFAULT_FEATURE_FLAGS.keys())

    def test_load_flags_handles_corrupt_json(self, tmp_path: Path, monkeypatch):
        bad = tmp_path / "bad.json"
        bad.write_text("not valid json {{{")
        monkeypatch.setenv("FEATURE_FLAGS_PATH", str(bad))
        flags = _load_flags()
        # Should fall back to defaults, not raise
        assert set(flags.keys()) == set(DEFAULT_FEATURE_FLAGS.keys())
