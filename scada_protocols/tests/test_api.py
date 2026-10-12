"""Tests for scada_protocols.api — FastAPI router (no live sockets)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api.dependencies import CurrentUser, get_api_key, get_current_user_from_header
from scada_protocols.api import build_router, set_manager
from scada_protocols.common.config import SCADAProtocolsConfig
from scada_protocols.manager import SCADAProtocolManager


def _mock_admin_user() -> CurrentUser:
    return CurrentUser(
        user_id="admin_user_1",
        username="admin",
        email="admin@substation.ot",
        role="admin",
        tenant_id="tenant_substation_north",
    )


@pytest.fixture
def app_with_router():
    cfg = SCADAProtocolsConfig()
    cfg.modbus.enabled = False
    cfg.opcua.enabled = False
    cfg.iec104.enabled = False
    cfg.iec61850.enabled = False
    mgr = SCADAProtocolManager(config=cfg)
    set_manager(mgr)
    app = FastAPI()
    app.include_router(build_router(), prefix="/api/v1/scada/protocols")
    app.dependency_overrides[get_api_key] = lambda: "test-api-key"
    app.dependency_overrides[get_current_user_from_header] = _mock_admin_user
    yield app, mgr
    mgr.stop()


def test_libraries_endpoint(app_with_router):
    app, _ = app_with_router
    client = TestClient(app)
    r = client.get("/api/v1/scada/protocols/libraries")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"modbus_tcp", "opc_ua", "iec_104", "iec_61850"}


def test_status_endpoint_with_manager(app_with_router):
    app, _ = app_with_router
    client = TestClient(app)
    r = client.get("/api/v1/scada/protocols/status")
    assert r.status_code == 200
    data = r.json()
    assert data["manager_registered"] is True or "started" in data
    assert data["started"] is False


def test_status_endpoint_without_manager():
    set_manager(None)
    app = FastAPI()
    app.include_router(build_router(), prefix="/api/v1/scada/protocols")
    app.dependency_overrides[get_api_key] = lambda: "test-api-key"
    app.dependency_overrides[get_current_user_from_header] = _mock_admin_user
    client = TestClient(app)
    r = client.get("/api/v1/scada/protocols/status")
    assert r.status_code == 200
    data = r.json()
    assert data["manager_registered"] is False


def test_list_adapters_empty(app_with_router):
    app, _ = app_with_router
    client = TestClient(app)
    r = client.get("/api/v1/scada/protocols/adapters")
    assert r.status_code == 200
    assert r.json() == []


def test_start_stop_endpoints(app_with_router):
    """Authenticated admin starts and stops SCADA protocol manager (200 OK)."""
    app, mgr = app_with_router
    client = TestClient(app)
    r = client.post("/api/v1/scada/protocols/start")
    assert r.status_code == 200
    assert r.json()["started"] is True
    r = client.post("/api/v1/scada/protocols/stop")
    assert r.status_code == 200
    assert r.json()["started"] is False


def test_protocol_status_unknown_protocol(app_with_router):
    app, _ = app_with_router
    client = TestClient(app)
    r = client.get("/api/v1/scada/protocols/unknown_protocol/status")
    assert r.status_code == 400


def test_protocol_status_not_configured(app_with_router):
    app, _ = app_with_router
    client = TestClient(app)
    r = client.get("/api/v1/scada/protocols/modbus_tcp/status")
    # All protocols disabled in this fixture.
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is False


def test_protocol_start_without_manager():
    """Authenticated request when no manager is registered returns 503 Service Unavailable."""
    set_manager(None)
    app = FastAPI()
    app.include_router(build_router(), prefix="/api/v1/scada/protocols")
    app.dependency_overrides[get_api_key] = lambda: "test-api-key"
    app.dependency_overrides[get_current_user_from_header] = _mock_admin_user
    client = TestClient(app)
    r = client.post("/api/v1/scada/protocols/modbus_tcp/start")
    assert r.status_code == 503


def test_unauthenticated_request_returns_401():
    """Security gate: requests without API key / authentication are rejected with 401."""
    app = FastAPI()
    app.include_router(build_router(), prefix="/api/v1/scada/protocols")
    client = TestClient(app)
    r_read = client.get("/api/v1/scada/protocols/libraries")
    assert r_read.status_code == 401
    r_mutating = client.post("/api/v1/scada/protocols/start")
    assert r_mutating.status_code == 401
