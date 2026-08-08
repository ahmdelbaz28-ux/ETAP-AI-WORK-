"""Tests for scada_protocols.wiring — additive integration into FastAPI."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scada_protocols.common.config import SCADAProtocolsConfig
from scada_protocols.wiring import get_wired_manager, wire_into_app
import scada_protocols.wiring as _wiring_mod


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the module-level singleton between tests."""
    saved = _wiring_mod._WIRED_MANAGER
    _wiring_mod._WIRED_MANAGER = None
    yield
    if saved is not None:
        try:
            saved.stop()
        except Exception:
            pass
    _wiring_mod._WIRED_MANAGER = saved


def _make_disabled_config() -> SCADAProtocolsConfig:
    cfg = SCADAProtocolsConfig()
    cfg.modbus.enabled = False
    cfg.opcua.enabled = False
    cfg.iec104.enabled = False
    return cfg


def test_wire_into_app_mounts_router_and_starts_manager():
    app = FastAPI()
    # Use a config with all protocols disabled so no sockets are opened.
    cfg = _make_disabled_config()
    # Patch load_config to return our test config.
    from scada_protocols.wiring import wire_into_app as _wire
    from scada_protocols import wiring as _w
    from scada_protocols.common import config as _cfg_mod

    original_load = _cfg_mod.load_config
    _cfg_mod.load_config = lambda *a, **kw: cfg
    _w.load_config = _cfg_mod.load_config
    try:
        mgr = _wire(app, autostart=True)
        # Manager should be started.
        assert mgr.is_started() is True
        # Router should be mounted.
        client = TestClient(app)
        r = client.get("/api/v1/scada/protocols/status")
        assert r.status_code == 200
        data = r.json()
        assert data["manager_registered"] is True
        assert data["started"] is True
    finally:
        _cfg_mod.load_config = original_load
        _w.load_config = original_load
        mgr.stop()


def test_wire_into_app_idempotent():
    app = FastAPI()
    cfg = _make_disabled_config()
    from scada_protocols import wiring as _w
    from scada_protocols.common import config as _cfg_mod

    original_load = _cfg_mod.load_config
    _cfg_mod.load_config = lambda *a, **kw: cfg
    _w.load_config = _cfg_mod.load_config
    try:
        mgr1 = wire_into_app(app, autostart=False)
        mgr2 = wire_into_app(app, autostart=False)
        assert mgr1 is mgr2, "second wire_into_app should return the same manager"
    finally:
        _cfg_mod.load_config = original_load
        _w.load_config = original_load


def test_get_wired_manager_returns_none_before_wiring():
    assert get_wired_manager() is None


def test_libraries_endpoint_works_through_wiring():
    app = FastAPI()
    cfg = _make_disabled_config()
    from scada_protocols import wiring as _w
    from scada_protocols.common import config as _cfg_mod

    original_load = _cfg_mod.load_config
    _cfg_mod.load_config = lambda *a, **kw: cfg
    _w.load_config = _cfg_mod.load_config
    try:
        wire_into_app(app, autostart=True)
        client = TestClient(app)
        r = client.get("/api/v1/scada/protocols/libraries")
        assert r.status_code == 200
        data = r.json()
        assert set(data.keys()) == {"modbus_tcp", "opc_ua", "iec_104"}
    finally:
        _cfg_mod.load_config = original_load
        _w.load_config = original_load
