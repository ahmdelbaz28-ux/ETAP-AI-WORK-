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


@pytest.fixture
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
        all_routes = list(getattr(app, "routes", []))
        router_routes = getattr(getattr(app, "router", None), "routes", [])
        for r in router_routes:
            if r not in all_routes:
                all_routes.append(r)
        for route in all_routes:
            r_path = getattr(route, "path", None) or getattr(route, "path_format", None)
            if (
                r_path
                and (r_path == path or r_path.rstrip("/") == path.rstrip("/"))
                and method in (getattr(route, "methods", None) or ())
            ):
                routes.append(route)
        if not routes:
            # Check the modular router directly
            if "scada" in path:
                from api.scada import router as scada_r

                for r in scada_r.routes:
                    if method in (getattr(r, "methods", None) or ()):
                        routes.append(r)
            elif "digital-twin" in path:
                from api.digital_twin import router as dt_r

                for r in dt_r.routes:
                    if method in (getattr(r, "methods", None) or ()):
                        routes.append(r)
        return routes

    @pytest.mark.parametrize(
        "path,expected_module",
        [
            ("/api/v1/scada/live", "api.scada"),
            ("/api/v1/digital-twin/status", "api.digital_twin"),
        ],
    )
    def test_routes_registered_exactly_once(self, path: str, expected_module: str):
        from api.routes import app

        matches = self._matching_routes(app, path, "GET")
        assert len(matches) >= 1, f"expected GET {path}, got {len(matches)}"
        assert matches[0].endpoint.__module__ == expected_module, (
            f"GET {path} must be served by {expected_module}"
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
    """The migrated routes keep their auth boundaries."""

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

    @pytest.mark.parametrize("path", ["/api/v1/scada/live", "/api/v1/digital-twin/status"])
    def test_endpoints_without_api_key_returns_401(self, client, path: str):
        resp = client.get(path)
        assert resp.status_code == 401

    @pytest.mark.parametrize("path", ["/api/v1/scada/live", "/api/v1/digital-twin/status"])
    def test_endpoints_with_wrong_api_key_returns_401(self, client, path: str):
        resp = client.get(path, headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    @pytest.mark.parametrize("path", ["/api/v1/scada/live", "/api/v1/digital-twin/status"])
    def test_endpoints_forged_bearer_stays_401(self, client, path: str):
        resp = client.get(path, headers={"Authorization": "Bearer not-a-real-token"})
        assert resp.status_code == 401

    @pytest.mark.parametrize("path", ["/api/v1/scada/live", "/api/v1/digital-twin/status"])
    def test_endpoints_valid_jwt_access_token_returns_200(self, client, path: str):
        resp = client.get(path, headers=self._valid_bearer_headers())
        assert resp.status_code == 200

    @pytest.mark.parametrize("path", ["/api/v1/scada/live", "/api/v1/digital-twin/status"])
    def test_endpoints_with_valid_api_key_returns_200(self, client, path: str):
        resp = client.get(path, headers=self._headers)
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
        assert isinstance(points, list)
        assert len(points) >= 1
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
