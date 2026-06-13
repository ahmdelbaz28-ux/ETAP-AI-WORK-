"""Tests for engineering_service.py — FastAPI endpoints."""


import uuid

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app():
    from engineering_service import app
    return app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    async def test_health_returns_200(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_health_returns_status_healthy(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert data["status"] == "healthy"

    async def test_health_contains_version(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert "version" in data

    async def test_health_response_has_trace_id_header(self, client):
        resp = await client.get("/health")
        assert "x-trace-id" in resp.headers

    async def test_health_preserves_provided_trace_id(self, client):
        trace_id = str(uuid.uuid4())
        resp = await client.get("/health", headers={"x-trace-id": trace_id})
        assert resp.headers["x-trace-id"] == trace_id


class TestReadyEndpoint:
    async def test_ready_returns_200(self, client):
        resp = await client.get("/ready")
        assert resp.status_code == 200

    async def test_ready_returns_true(self, client):
        resp = await client.get("/ready")
        data = resp.json()
        assert data["ready"] is True


class TestMetricsEndpoint:
    async def test_metrics_returns_200(self, client):
        resp = await client.get("/metrics")
        assert resp.status_code == 200

    async def test_metrics_contains_expected_keys(self, client):
        resp = await client.get("/metrics")
        data = resp.json()
        for key in ("requests_total", "requests_success", "requests_failed", "avg_execution_time_ms"):
            assert key in data

    async def test_metrics_values_are_non_negative(self, client):
        resp = await client.get("/metrics")
        data = resp.json()
        assert data["requests_total"] >= 0
        assert data["requests_success"] >= 0


class TestStudyRunEndpoint:
    async def test_study_run_returns_200(self, client):
        resp = await client.post("/api/v1/studies/run", json={"study_type": "load_flow"})
        assert resp.status_code == 200

    async def test_study_run_returns_json_with_trace_id(self, client):
        resp = await client.post("/api/v1/studies/run", json={"study_type": "load_flow"})
        data = resp.json()
        assert "trace_id" in data
        assert data["success"] is False

    async def test_study_run_with_invalid_type_returns_422(self, client):
        resp = await client.post("/api/v1/studies/run", json={"study_type": "invalid"})
        assert resp.status_code == 422


class TestSystemValidateEndpoint:
    async def test_system_validate_returns_200(self, client):
        resp = await client.post("/api/v1/system/validate", json={})
        assert resp.status_code == 200

    async def test_system_validate_with_data(self, client):
        payload = {
            "system": {
                "buses": [{"id": "BUS1", "nominal_kv": 13.8}],
                "lines": [],
                "transformers": [],
                "generators": [],
                "loads": [],
            }
        }
        resp = await client.post("/api/v1/system/validate", json=payload)
        assert resp.status_code == 200


class TestCORS:
    async def test_cors_headers_present(self, client):
        resp = await client.options(
            "/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" in resp.headers
