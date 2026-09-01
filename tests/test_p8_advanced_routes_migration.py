"""P8 — Advanced Routes Migration: HTTP contract regression tests.

P8 relocated the following advanced/legacy inline handlers out of
``api/routes.py`` into their intended modular routers:

* ``GET /api/v1/scada/live``          -> ``api/scada.py``        (scada_router)
* ``GET /api/v1/digital-twin/status`` -> ``api/digital_twin.py`` (digital_twin_router)

This suite proves the migration is behaviour-preserving at the HTTP layer:

* route registration — each path is registered exactly once (no shadowing)
* auth — 401 without/with-wrong API key, 200 with valid key (guard preserved)
* auth (canonical) — the routers adopt the repo-wide ``get_api_key`` guard, so a
  valid JWT ``Bearer`` access token authenticates exactly as on every other
  modular router (equipment, export, ...); invalid/forged Bearer stays 401
* response shape — the exact fields consumed by the frontend are preserved
  (``is_simulated``/``data.points`` for ScadaIntegration.tsx, ``data`` for
  DigitalTwin.tsx)
* legacy compatibility — paths and contracts are unchanged
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent

_TEST_API_KEY = "test-p8-routes-migration-key"


def _read_file(relative: str) -> str:
    return (_REPO_ROOT / relative).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures — auth-ENABLED environment (mirrors tests/test_auth_enabled.py).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_auth(monkeypatch):
    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", _TEST_API_KEY)
    monkeypatch.delenv("ENGINEERING_SERVICE_AUTH_DISABLED", raising=False)
    import api.dependencies as deps

    monkeypatch.setattr(deps, "API_KEY", _TEST_API_KEY)
    yield


@pytest.fixture(scope="function")
def client():
    """Create a TestClient against the real FastAPI app with auth enabled."""
    from starlette.testclient import TestClient

    from api.routes import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# Route registration / precedence
# ---------------------------------------------------------------------------


class TestRoutePrecedence:
    """Each migrated route must be registered exactly once (no duplicate/shadowing)."""

    @staticmethod
    def _matching_routes(app, path: str, method: str) -> list:
        routes = []
        for route in getattr(app, "routes", []):
            if getattr(route, "path", None) == path and method in (
                getattr(route, "methods", None) or ()
            ):
                routes.append(route)
        return routes

    def test_scada_live_registered_exactly_once(self):
        from api.routes import app

        matches = self._matching_routes(app, "/api/v1/scada/live", "GET")
        assert len(matches) == 1, f"expected exactly 1 GET /api/v1/scada/live, got {len(matches)}"
        assert matches[0].endpoint.__module__ == "api.scada", (
            "GET /api/v1/scada/live must be served by api/scada.py"
        )

    def test_digital_twin_status_registered_exactly_once(self):
        from api.routes import app

        matches = self._matching_routes(app, "/api/v1/digital-twin/status", "GET")
        assert len(matches) == 1, (
            f"expected exactly 1 GET /api/v1/digital-twin/status, got {len(matches)}"
        )
        assert matches[0].endpoint.__module__ == "api.digital_twin", (
            "GET /api/v1/digital-twin/status must be served by api/digital_twin.py"
        )

    def test_legacy_inline_handlers_removed_from_routes_py(self):
        source = _read_file("api/routes.py")
        assert "async def scada_live(" not in source, "legacy inline scada_live must be removed"
        assert "async def digital_twin_status(" not in source, (
            "legacy inline digital_twin_status must be removed"
        )

    def test_modular_routers_are_included(self):
        source = _read_file("api/routes.py")
        assert "app.include_router(scada_router)" in source
        assert "app.include_router(digital_twin_router)" in source


# ---------------------------------------------------------------------------
# Authentication preservation
# ---------------------------------------------------------------------------


class TestAuthPreserved:
    """The migrated routes keep their auth boundaries.

    They now use the canonical repo-wide ``get_api_key`` guard (API key OR a
    valid JWT access ``Bearer`` token). Missing/invalid credentials → 401;
    validating credentials → 200. This preserves the legacy S-15 requirement
    (never public) while satisfying the architecture pinned by
    tests/test_audit_phase10_round7_fixes.py and the Bootstrap JWT-only
    consumer (ui/src/pages/DigitalTwin.tsx).
    """

    _headers = {"X-API-Key": _TEST_API_KEY}

    @staticmethod
    def _valid_bearer_headers() -> dict:
        """Headers with a valid JWT access token (mirrors tests/test_chat_stream.py)."""
        import time

        import jwt as pyjwt

        from api.dependencies import JWT_ALGORITHM, JWT_SECRET_KEY

        now = time.time()
        token = pyjwt.encode(
            {
                "sub": "test-user-id",
                "type": "access",
                "iat": int(now),
                "exp": int(now + 600),
            },
            JWT_SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )
        return {"Authorization": f"Bearer {token}"}

    def test_scada_live_without_api_key_returns_401(self, client):
        resp = client.get("/api/v1/scada/live")
        assert resp.status_code == 401

    def test_scada_live_with_wrong_api_key_returns_401(self, client):
        resp = client.get("/api/v1/scada/live", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_scada_live_forged_bearer_stays_401(self, client):
        """A forged Bearer token must NOT become a bypass after migration."""
        resp = client.get(
            "/api/v1/scada/live", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert resp.status_code == 401

    def test_scada_live_valid_jwt_access_token_returns_200(self, client):
        """A valid JWT access token authenticates (canonical get_api_key)."""
        resp = client.get("/api/v1/scada/live", headers=self._valid_bearer_headers())
        assert resp.status_code == 200

    def test_scada_live_with_valid_api_key_returns_200(self, client):
        resp = client.get("/api/v1/scada/live", headers=self._headers)
        assert resp.status_code == 200

    def test_digital_twin_without_api_key_returns_401(self, client):
        resp = client.get("/api/v1/digital-twin/status")
        assert resp.status_code == 401

    def test_digital_twin_with_wrong_api_key_returns_401(self, client):
        resp = client.get("/api/v1/digital-twin/status", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_digital_twin_forged_bearer_stays_401(self, client):
        """A forged Bearer token must NOT become a bypass after migration."""
        resp = client.get(
            "/api/v1/digital-twin/status",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401

    def test_digital_twin_valid_jwt_access_token_returns_200(self, client):
        """A valid JWT access token authenticates (canonical get_api_key)."""
        resp = client.get("/api/v1/digital-twin/status", headers=self._valid_bearer_headers())
        assert resp.status_code == 200

    def test_digital_twin_with_valid_api_key_returns_200(self, client):
        resp = client.get("/api/v1/digital-twin/status", headers=self._headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Response contract preservation (frontend consumers)
# ---------------------------------------------------------------------------


class TestResponseContractPreserved:
    """The exact response shapes consumed by the UI are preserved."""

    _headers = {"X-API-Key": _TEST_API_KEY}

    def test_scada_live_response_shape(self, client):
        resp = client.get("/api/v1/scada/live", headers=self._headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["is_simulated"] is True  # ScadaIntegration.tsx depends on this
        assert body["data"]["timestamp"]
        assert body["data"]["source"] == "synthetic"
        points = body["data"]["points"]
        assert isinstance(points, list) and len(points) >= 1
        assert points[0]["tag"] == "BUS1.V"  # telemetry points consumed by the UI

    def test_digital_twin_status_response_shape(self, client):
        resp = client.get("/api/v1/digital-twin/status", headers=self._headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["state"] == "STANDBY"
        assert body["data"]["schema_version"] == "1.0.0"
        assert body["data"]["nodes"] == 0
        assert body["data"]["edges"] == 0
        assert body["data"]["deployment_note"]
        assert body["data"]["timestamp"]


# ---------------------------------------------------------------------------
# Legacy compatibility
# ---------------------------------------------------------------------------


class TestLegacyCompatibility:
    """P8 did not rename/re-version endpoints — legacy consumers keep working."""

    _headers = {"X-API-Key": _TEST_API_KEY}

    def test_scada_live_legacy_path_unchanged(self, client):
        resp = client.get("/api/v1/scada/live", headers=self._headers)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_digital_twin_legacy_path_unchanged(self, client):
        resp = client.get("/api/v1/digital-twin/status", headers=self._headers)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_openapi_lists_migrated_paths(self, client):
        schema = client.get("/openapi.json").json()
        assert "/api/v1/scada/live" in schema["paths"]
        assert "/api/v1/digital-twin/status" in schema["paths"]
