"""Tests for scada_protocols.manager — orchestration + library probes."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scada_protocols.common.base import (
    ProtocolType,
    probe_all,
)
from scada_protocols.common.config import SCADAProtocolsConfig
from scada_protocols.manager import SCADAProtocolManager


class TestManagerConstruction:
    def test_default_config_no_libs_required(self) -> None:
        """Manager must build even if no protocol is enabled."""
        cfg = SCADAProtocolsConfig()
        cfg.modbus.enabled = False
        cfg.opcua.enabled = False
        cfg.iec104.enabled = False
        mgr = SCADAProtocolManager(config=cfg)
        assert mgr.is_started() is False
        assert mgr.list_adapters() == []

    def test_strict_lib_check_raises_on_missing(self) -> None:
        """When strict_lib_check is True and a protocol is enabled but its
        library is unavailable, the manager construction raises RuntimeError.
        """
        from scada_protocols.manager import SCADAProtocolManager as _M

        # Monkey-patch probe_all to return all-unavailable before construction.
        from scada_protocols.common import base as _base

        def _fake_probe():
            return {
                "modbus_tcp": {"available": False, "info": "mocked unavailable"},
                "opc_ua": {"available": False, "info": "mocked unavailable"},
                "iec_104": {"available": False, "info": "mocked unavailable"},
            }

        original = _base.probe_all
        _base.probe_all = _fake_probe
        # Also patch the manager module's reference (it imports probe_all by name).
        from scada_protocols import manager as _mgr_mod
        _mgr_mod.probe_all = _fake_probe
        try:
            cfg = SCADAProtocolsConfig()
            cfg.strict_lib_check = True
            cfg.modbus.enabled = True  # need at least one enabled to trigger
            with pytest.raises(RuntimeError):
                _M(config=cfg)
        finally:
            _base.probe_all = original
            _mgr_mod.probe_all = original

    def test_status_returns_expected_shape(self) -> None:
        cfg = SCADAProtocolsConfig()
        cfg.modbus.enabled = False
        cfg.opcua.enabled = False
        cfg.iec104.enabled = False
        mgr = SCADAProtocolManager(config=cfg)
        s = mgr.status()
        assert "started" in s
        assert "libraries" in s
        assert "adapters" in s
        assert "bridge" in s
        assert "config" in s
        assert s["started"] is False

    def test_libraries_probed(self) -> None:
        """The manager should have probed all three libraries at construction."""
        cfg = SCADAProtocolsConfig()
        cfg.modbus.enabled = False
        cfg.opcua.enabled = False
        cfg.iec104.enabled = False
        mgr = SCADAProtocolManager(config=cfg)
        # All three keys present.
        assert set(mgr._library_status.keys()) == {"modbus_tcp", "opc_ua", "iec_104"}


class TestManagerLifecycle:
    def test_start_stop_with_no_adapters(self) -> None:
        cfg = SCADAProtocolsConfig()
        cfg.modbus.enabled = False
        cfg.opcua.enabled = False
        cfg.iec104.enabled = False
        mgr = SCADAProtocolManager(config=cfg)
        mgr.start()
        assert mgr.is_started() is True
        mgr.stop()
        assert mgr.is_started() is False

    def test_double_start_is_idempotent(self) -> None:
        cfg = SCADAProtocolsConfig()
        cfg.modbus.enabled = False
        cfg.opcua.enabled = False
        cfg.iec104.enabled = False
        mgr = SCADAProtocolManager(config=cfg)
        mgr.start()
        mgr.start()  # should not raise
        assert mgr.is_started() is True
        mgr.stop()

    def test_double_stop_is_idempotent(self) -> None:
        cfg = SCADAProtocolsConfig()
        cfg.modbus.enabled = False
        cfg.opcua.enabled = False
        cfg.iec104.enabled = False
        mgr = SCADAProtocolManager(config=cfg)
        mgr.stop()  # should not raise even before start
        mgr.stop()


class TestManagerWithLibraries:
    """When libraries ARE present, adapters get built."""

    def test_adapters_built_when_libs_available(self) -> None:
        libs = probe_all()
        cfg = SCADAProtocolsConfig()
        # Keep defaults (all enabled, role=both)
        mgr = SCADAProtocolManager(config=cfg)
        # We don't start them (would open sockets). Just verify construction.
        for ptype in (ProtocolType.MODBUS_TCP, ProtocolType.OPC_UA, ProtocolType.IEC_104):
            adapter = mgr.get_adapter(ptype)
            lib_key = ptype.value
            if libs.get(lib_key, {}).get("available"):
                assert adapter is not None, f"{ptype} adapter should be built"
            # If lib not available, adapter should be None (skipped silently).
