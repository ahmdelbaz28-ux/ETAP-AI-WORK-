"""Tests for scada_protocols.common (config + bridge + base)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure the project root is on sys.path so ``scada_protocols`` imports.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scada_protocols.common.base import (
    AdapterRole,
    AdapterState,
    ProtocolAdapter,
    ProtocolType,
    probe_all,
)
from scada_protocols.common.bridge import SCADAProtocolBridge, make_callback
from scada_protocols.common.config import (
    ConfigError,
    SCADAProtocolsConfig,
    load_config,
    load_config_from_dict,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestConfig:
    def test_defaults(self) -> None:
        cfg = SCADAProtocolsConfig()
        assert cfg.modbus.enabled is True
        assert cfg.opcua.enabled is True
        assert cfg.iec104.enabled is True
        assert cfg.modbus.role == AdapterRole.BOTH
        assert cfg.opcua.role == AdapterRole.BOTH
        assert cfg.iec104.role == AdapterRole.BOTH

    def test_load_from_dict_minimal(self) -> None:
        cfg = load_config_from_dict({})
        assert cfg.modbus.enabled is True
        assert cfg.opcua.enabled is True
        assert cfg.iec104.enabled is True

    def test_load_from_dict_with_role(self) -> None:
        cfg = load_config_from_dict(
            {
                "modbus": {"role": "server"},
                "opcua": {"role": "client"},
                "iec104": {"role": "both"},
            }
        )
        assert cfg.modbus.role == AdapterRole.SERVER
        assert cfg.opcua.role == AdapterRole.CLIENT
        assert cfg.iec104.role == AdapterRole.BOTH

    def test_load_from_dict_invalid_role_raises(self) -> None:
        with pytest.raises(ConfigError):
            load_config_from_dict({"modbus": {"role": "slave"}})

    def test_load_from_dict_register_map_validation(self) -> None:
        with pytest.raises(ConfigError):
            load_config_from_dict(
                {
                    "modbus": {
                        "register_map": [
                            {"name": "x", "element_id": "B", "address": 0},
                            # missing measurement_type
                        ]
                    }
                }
            )

    def test_load_from_dict_opcua_node_map_validation(self) -> None:
        with pytest.raises(ConfigError):
            load_config_from_dict(
                {
                    "opcua": {
                        "node_map": [
                            {"node_id": "ns=3;s=x", "element_id": "B"},
                            # missing measurement_type
                        ]
                    }
                }
            )

    def test_load_from_dict_iec104_point_map_validation(self) -> None:
        with pytest.raises(ConfigError):
            load_config_from_dict(
                {
                    "iec104": {
                        "point_map": [
                            {"ca": 1, "ioa": 1, "element_id": "B"},
                            # missing measurement_type
                        ]
                    }
                }
            )

    def test_load_config_from_yaml_file(self) -> None:
        yaml_text = """
        modbus:
          enabled: true
          role: server
          server_port: 5021
          register_map:
            - name: "BUS1_V"
              element_id: "BUS-1"
              measurement_type: "voltage_magnitude"
              address: 0
              data_type: "float32"
        opcua:
          enabled: false
        iec104:
          enabled: true
          role: client
          point_map:
            - ca: 1
              ioa: 1001
              element_id: "BUS-1"
              measurement_type: "voltage_magnitude"
              type_id: "M_ME_NC_1"
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as tmp:
            tmp.write(yaml_text)
            tmp_path = tmp.name
        try:
            cfg = load_config(tmp_path)
            assert cfg.modbus.enabled is True
            assert cfg.modbus.role == AdapterRole.SERVER
            assert cfg.modbus.server_port == 5021
            assert len(cfg.modbus.register_map) == 1
            assert cfg.opcua.enabled is False
            assert cfg.iec104.role == AdapterRole.CLIENT
            assert len(cfg.iec104.point_map) == 1
        finally:
            os.unlink(tmp_path)

    def test_load_config_missing_file_returns_defaults(self) -> None:
        # No path and no env var -> defaults.
        old = os.environ.pop("SCADA_PROTOCOLS_CONFIG", None)
        try:
            cfg = load_config(None)
            assert cfg.modbus.enabled is True
        finally:
            if old is not None:
                os.environ["SCADA_PROTOCOLS_CONFIG"] = old

    def test_load_config_nonexistent_path_raises(self) -> None:
        with pytest.raises(ConfigError):
            load_config("/tmp/definitely-does-not-exist-12345.yaml")


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class TestBridge:
    def test_ingest_without_targets_logs_only(self) -> None:
        """When no SCADADatabase/EventBus are wired, ingest returns False
        but still updates stats. When the AhmedETAP modules ARE importable
        (e.g. when running from inside the repo), ingest returns True.
        Either way, stats must be updated.
        """
        bridge = SCADAProtocolBridge()
        bridge.ingest(
            "BUS-1",
            "voltage_magnitude",
            1.05,
            quality="good",
            source="test",
        )
        # The return value depends on whether SCADADatabase was importable;
        # we don't assert it. We DO assert stats were updated.
        stats = bridge.stats
        assert stats.total_ingested == 1
        assert stats.by_protocol.get("test") == 1
        assert stats.by_type.get("VOLTAGE_MAGNITUDE") == 1
        assert stats.by_quality.get("GOOD") == 1

    def test_ingest_handles_quality_aliases(self) -> None:
        bridge = SCADAProtocolBridge()
        for q_in, expected in (
            ("good", "GOOD"),
            ("OK", "GOOD"),
            ("Bad", "INVALID"),
            ("UNCERTAIN", "QUESTIONABLE"),
            ("stale", "MISSING"),
        ):
            bridge.ingest("B1", "v", 1.0, quality=q_in, source="t")
            assert bridge.stats.by_quality.get(expected, 0) >= 1

    def test_ingest_handles_measurement_type_aliases(self) -> None:
        bridge = SCADAProtocolBridge()
        for t_in, expected in (
            ("v", "VOLTAGE_MAGNITUDE"),
            ("vmag", "VOLTAGE_MAGNITUDE"),
            ("P", "ACTIVE_POWER"),
            ("MW", "ACTIVE_POWER"),
            ("freq", "FREQUENCY"),
            ("hz", "FREQUENCY"),
        ):
            bridge.ingest("B1", t_in, 1.0, source="t")
            assert bridge.stats.by_type.get(expected, 0) >= 1

    def test_make_callback_round_trip(self) -> None:
        bridge = SCADAProtocolBridge()
        cb = make_callback(bridge)
        cb("BUS-1", "voltage_magnitude", 1.0, "good", "modbus:test")
        assert bridge.stats.total_ingested == 1
        assert bridge.stats.last_element_id == "BUS-1"

    def test_callback_swallows_errors(self) -> None:
        """The bridge callback must NEVER raise into the protocol loop."""

        def boom(*a, **kw):
            raise RuntimeError("simulated bridge failure")

        # Replace ingest with a boom
        bridge = SCADAProtocolBridge()
        bridge.ingest = boom  # type: ignore
        cb = make_callback(bridge)
        cb("B1", "v", 1.0, "good", "test")  # must not raise


# ---------------------------------------------------------------------------
# Adapter base
# ---------------------------------------------------------------------------


class _DummyAdapter(ProtocolAdapter):
    protocol = ProtocolType.MODBUS_TCP
    supports_server = True
    supports_client = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._started_server = False
        self._started_client = False

    def start_server(self) -> None:
        self._started_server = True

    def stop_server(self) -> None:
        self._started_server = False

    def start_client(self) -> None:
        self._started_client = True

    def stop_client(self) -> None:
        self._started_client = False

    def health_check(self) -> bool:
        return self._started_server or self._started_client


class TestAdapterBase:
    def test_starts_only_server_when_role_is_server(self) -> None:
        a = _DummyAdapter(role=AdapterRole.SERVER)
        a.start()
        assert a.state == AdapterState.RUNNING
        assert a._started_server
        assert not a._started_client

    def test_starts_only_client_when_role_is_client(self) -> None:
        a = _DummyAdapter(role=AdapterRole.CLIENT)
        a.start()
        assert a._started_client
        assert not a._started_server

    def test_starts_both(self) -> None:
        a = _DummyAdapter(role=AdapterRole.BOTH)
        a.start()
        assert a._started_server
        assert a._started_client

    def test_ingest_calls_callback(self) -> None:
        calls = []

        def cb(elem, mtype, val, q, src):
            calls.append((elem, mtype, val, q, src))

        a = _DummyAdapter(role=AdapterRole.CLIENT, on_measurement=cb)
        a._ingest("B1", "v", 1.05, "good", "test")
        assert calls == [("B1", "v", 1.05, "good", "test")]
        assert a.metric.points_ingested == 1

    def test_ingest_swallows_callback_errors(self) -> None:
        def cb(*a, **kw):
            raise RuntimeError("boom")

        a = _DummyAdapter(role=AdapterRole.CLIENT, on_measurement=cb)
        a._ingest("B1", "v", 1.05, "good", "test")  # must not raise
        assert a.metric.points_ingested == 1
        assert a.metric.errors >= 1

    def test_describe_and_metric(self) -> None:
        a = _DummyAdapter(role=AdapterRole.BOTH)
        d = a.describe()
        assert d["protocol"] == "modbus_tcp"
        assert d["role"] == "both"
        assert d["state"] == "stopped"
        m = a.metric.to_dict()
        assert m["protocol"] == "modbus_tcp"


# ---------------------------------------------------------------------------
# Library probes
# ---------------------------------------------------------------------------


class TestProbes:
    def test_probe_all_returns_three_protocols(self) -> None:
        result = probe_all()
        assert set(result.keys()) == {"modbus_tcp", "opc_ua", "iec_104"}
        for v in result.values():
            assert "available" in v
            assert "info" in v
