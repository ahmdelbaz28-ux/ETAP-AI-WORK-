"""Tests for scada_protocols.api — FastAPI router (no live sockets)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scada_protocols.api import build_router, set_manager
from scada_protocols.common.config import SCADAProtocolsConfig
from scada_protocols.manager import SCADAProtocolManager


@pytest.fixture
def app_with_router():
    cfg = SCADAProtocolsConfig()
    cfg.modbus.enabled = False
    cfg.opcua.enabled = False
    cfg.iec104.enabled = False
    mgr = SCADAProtocolManager(config=cfg)
    set_manager(mgr)
    app = FastAPI()
    app.include_router(build_router(), prefix="/api/v1/scada/protocols")
    yield app, mgr
    mgr.stop()


def test_libraries_endpoint(app_with_router):
    app, _ = app_with_router
    client = TestClient(app)
    r = client.get("/api/v1/scada/protocols/libraries")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"modbus_tcp", "opc_ua", "iec_104"}


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
    set_manager(None)
    app = FastAPI()
    app.include_router(build_router(), prefix="/api/v1/scada/protocols")
    client = TestClient(app)
    r = client.post("/api/v1/scada/protocols/modbus_tcp/start")
    assert r.status_code == 503
