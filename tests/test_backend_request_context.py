"""Tests for backend/request_context.py — Correlation ID middleware."""

import uuid

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from backend.request_context import CorrelationIdMiddleware


async def dummy_endpoint(request: Request):
    return JSONResponse({"correlation_id": request.state.correlation_id})


async def headers_endpoint(request: Request):
    return JSONResponse({
        "correlation_id": request.state.correlation_id,
        "all_headers": dict(request.headers),
    })


@pytest.fixture
def app():
    middleware = [Middleware(CorrelationIdMiddleware)]
    routes = [
        Route("/test", endpoint=dummy_endpoint),
        Route("/headers", endpoint=headers_endpoint),
    ]
    return Starlette(routes=routes, middleware=middleware)


@pytest.fixture
def client(app):
    return TestClient(app)


class TestCorrelationIdMiddleware:
    def test_generates_correlation_id_when_missing(self, client):
        resp = client.get("/test")
        assert resp.status_code == 200
        data = resp.json()
        cid = data["correlation_id"]
        assert cid is not None
        assert len(cid) > 0
        assert uuid.UUID(cid)

    def test_preserves_existing_correlation_id(self, client):
        existing_cid = str(uuid.uuid4())
        resp = client.get("/test", headers={"X-Correlation-ID": existing_cid})
        assert resp.status_code == 200
        data = resp.json()
        assert data["correlation_id"] == existing_cid

    def test_response_contains_correlation_id_header(self, client):
        resp = client.get("/test")
        assert resp.status_code == 200
        assert "X-Correlation-ID" in resp.headers
        cid = resp.headers["X-Correlation-ID"]
        assert uuid.UUID(cid)

    def test_response_reflects_provided_correlation_id(self, client):
        existing_cid = str(uuid.uuid4())
        resp = client.get("/test", headers={"X-Correlation-ID": existing_cid})
        assert resp.status_code == 200
        assert resp.headers["X-Correlation-ID"] == existing_cid

    def test_each_request_gets_unique_id(self, client):
        resp1 = client.get("/test")
        resp2 = client.get("/test")
        assert resp1.headers["X-Correlation-ID"] != resp2.headers["X-Correlation-ID"]

    def test_correlation_id_accessible_via_request_state(self, client):
        existing_cid = str(uuid.uuid4())
        resp = client.get("/headers", headers={"X-Correlation-ID": existing_cid})
        assert resp.status_code == 200
        data = resp.json()
        assert data["correlation_id"] == existing_cid
