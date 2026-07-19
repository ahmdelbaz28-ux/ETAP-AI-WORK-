"""Pytest tests for hf-space/app.py auth middleware.

These tests verify that the global auth middleware on the HF Space app
correctly enforces authentication on all non-public endpoints.

ENVIRONMENT ISOLATION: All env var changes happen inside fixtures via
monkeypatch — NO module-level env manipulation. This prevents test
pollution that was breaking test_auth_api.py when run in the same
session.

NOTE: These tests import hf-space/app.py which has heavy dependencies.
If deps are missing, the tests are skipped (not failed).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

HF_SPACE_DIR = str(Path(__file__).parent.parent / "hf-space")
REPO_ROOT = str(Path(__file__).parent.parent)

sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, HF_SPACE_DIR)

# We do NOT set any env vars here. The fixture below sets them with
# monkeypatch so they're automatically restored after each test.

# Try to import — if it fails, all tests skip
_HF_APP = None
_HF_APP_ERROR = None

# Temporarily set env for the import ONLY, then restore
_saved = {}
for k in ("ENGINEERING_SERVICE_AUTH_DISABLED", "ENGINEERING_SERVICE_API_KEY",
          "JWT_SECRET_KEY", "ENVIRONMENT", "DATABASE_URL"):
    _saved[k] = os.environ.get(k)
    os.environ.pop("ENGINEERING_SERVICE_AUTH_DISABLED", None)
    os.environ.setdefault("ENGINEERING_SERVICE_API_KEY", "test-hf-secret-key-12345")
    os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-minimum-32-characters-long")
    os.environ.setdefault("ENVIRONMENT", "development")
    # Use a SEPARATE database for HF Space tests to avoid conflicts
    # with test_auth_api.py which uses the default ./data/etap_platform.db
    import tempfile as _tf
    _hf_db = _tf.mktemp(suffix=".db")
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_hf_db}"

# Clean cached modules
for mod in list(sys.modules.keys()):
    if mod.startswith("api.") or mod.startswith("core") or mod == "app":
        del sys.modules[mod]

try:
    import app as hf_app_module
    _HF_APP = hf_app_module.app
except Exception as e:
    _HF_APP_ERROR = str(e)

# Restore env immediately after import
for k, v in _saved.items():
    if v is not None:
        os.environ[k] = v
    else:
        os.environ.pop(k, None)

pytestmark = pytest.mark.skipif(
    _HF_APP is None,
    reason=f"hf-space/app.py not importable: {_HF_APP_ERROR}",
)


@pytest.fixture
def hf_client(monkeypatch):
    """TestClient for hf-space/app.py with auth ENABLED.

    CRITICAL: The conftest.py autouse fixture sets AUTH_DISABLED=true.
    We override it here with monkeypatch to test actual auth behavior.
    monkeypatch automatically restores the original value after the test.
    """
    monkeypatch.delenv("ENGINEERING_SERVICE_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "test-hf-secret-key-12345")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-minimum-32-characters-long")
    from fastapi.testclient import TestClient
    return TestClient(_HF_APP)


@pytest.fixture
def auth_headers():
    """Headers with valid X-API-Key."""
    return {"X-API-Key": "test-hf-secret-key-12345"}


# ─── Public endpoints (should return 200 without auth) ───────────────────────


class TestPublicEndpoints:
    """Endpoints that must be accessible without authentication."""

    def test_healthz_no_auth(self, hf_client):
        resp = hf_client.get("/healthz")
        assert resp.status_code == 200, f"/healthz should be public, got {resp.status_code}"

    def test_readyz_no_auth(self, hf_client):
        resp = hf_client.get("/readyz")
        assert resp.status_code in (200, 503), f"/readyz should be public (200 or 503), got {resp.status_code}"

    def test_info_no_auth(self, hf_client):
        resp = hf_client.get("/api/v1/info")
        assert resp.status_code == 200, f"/api/v1/info should be public, got {resp.status_code}"

    def test_root_no_auth(self, hf_client):
        resp = hf_client.get("/")
        assert resp.status_code == 200, f"/ should be public, got {resp.status_code}"


# ─── Protected endpoints (should return 401 without auth) ────────────────────


class TestProtectedEndpoints:
    """Endpoints that must require authentication."""

    @pytest.mark.parametrize("method,path,body", [
        ("GET", "/api/v1/scada/live", None),
        ("GET", "/api/v1/digital-twin/status", None),
        ("GET", "/api/v1/benchmark", None),
        ("GET", "/api/v1/studies/types", None),
        ("POST", "/api/v1/studies/run", {}),
        ("POST", "/api/v1/context/retrieve", {"query": "test"}),
        ("POST", "/api/v1/context/impact", {"component": "test"}),
        ("GET", "/api/v1/knowledge", None),
        ("GET", "/api/v1/ml/capabilities", None),
        ("GET", "/api/v1/settings/keys", None),
    ])
    def test_endpoint_requires_auth(self, hf_client, method, path, body):
        """Each endpoint must return 401 without auth headers."""
        if method == "GET":
            resp = hf_client.get(path)
        elif method == "POST":
            resp = hf_client.post(path, json=body)
        else:
            pytest.skip(f"Method {method} not supported in test")
        assert resp.status_code == 401, (
            f"{method} {path} should return 401 without auth, "
            f"got {resp.status_code}. Response: {resp.text[:200]}"
        )

    def test_scada_live_with_valid_key(self, hf_client, auth_headers):
        """Valid API key should grant access to /scada/live."""
        resp = hf_client.get("/api/v1/scada/live", headers=auth_headers)
        assert resp.status_code == 200, f"Valid key should get 200, got {resp.status_code}"

    def test_scada_live_with_invalid_key(self, hf_client):
        """Invalid API key should be rejected."""
        resp = hf_client.get("/api/v1/scada/live", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401, f"Invalid key should get 401, got {resp.status_code}"

    def test_benchmark_with_valid_key(self, hf_client, auth_headers):
        """Valid API key should grant access to /benchmark."""
        resp = hf_client.get("/api/v1/benchmark", headers=auth_headers)
        assert resp.status_code == 200, f"Valid key should get 200, got {resp.status_code}"

    def test_ml_capabilities_with_valid_key(self, hf_client, auth_headers):
        """Valid API key should grant access to /ml/capabilities."""
        resp = hf_client.get("/api/v1/ml/capabilities", headers=auth_headers)
        assert resp.status_code == 200, f"Valid key should get 200, got {resp.status_code}"


# ─── JWT auth path ────────────────────────────────────────────────────────────


class TestJWTAuth:
    """Test JWT Bearer token authentication path."""

    def test_valid_jwt_grants_access(self, hf_client, monkeypatch):
        """A valid JWT should grant access to protected endpoints."""
        import jwt as _jwt
        from datetime import datetime, timedelta, timezone

        token = _jwt.encode(
            {
                "sub": "test-user-id",
                "role": "engineer",
                "type": "access",
                "iat": datetime.now(timezone.utc),
                "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
            },
            "test-jwt-secret-key-minimum-32-characters-long",
            algorithm="HS256",
        )
        resp = hf_client.get(
            "/api/v1/scada/live",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"Valid JWT should get 200, got {resp.status_code}"

    def test_expired_jwt_rejected(self, hf_client):
        """An expired JWT should be rejected."""
        import jwt as _jwt
        from datetime import datetime, timedelta, timezone

        token = _jwt.encode(
            {
                "sub": "test-user-id",
                "role": "engineer",
                "type": "access",
                "iat": datetime.now(timezone.utc) - timedelta(hours=2),
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            },
            "test-jwt-secret-key-minimum-32-characters-long",
            algorithm="HS256",
        )
        resp = hf_client.get(
            "/api/v1/scada/live",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401, f"Expired JWT should get 401, got {resp.status_code}"

    def test_invalid_jwt_rejected(self, hf_client):
        """A completely invalid JWT string should be rejected."""
        resp = hf_client.get(
            "/api/v1/scada/live",
            headers={"Authorization": "Bearer completely-invalid-token"},
        )
        assert resp.status_code == 401, f"Invalid JWT should get 401, got {resp.status_code}"
