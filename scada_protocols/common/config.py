"""
scada_protocols.common.config
=============================
Typed YAML configuration loader for SCADA protocol adapters.

Why a typed loader:
- The repo's existing config patterns rely on ``os.environ.get`` scattered
  through modules. For multi-protocol orchestration we want a single schema
  with explicit validation so a bad config fails fast at startup rather than
  silently degrading to simulation.
- The loader is pure-Python (PyYAML only) and produces dataclasses that the
  manager and adapter factories consume.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from scada_protocols.common.base import AdapterRole


# ---------------------------------------------------------------------------
# Per-protocol config dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ModbusConfig:
    """Modbus TCP adapter config.

    A single adapter can run a server (slave) on one TCP port and a list of
    clients (masters) targeting remote slaves. The bridge ingests data from
    each client poll cycle.
    """

    enabled: bool = True
    role: AdapterRole = AdapterRole.BOTH
    server_host: str = "0.0.0.0"
    server_port: int = 5020
    server_unit_id: int = 1
    # Each entry: {name, host, port, unit_id, scan_rate_ms, registers: [...]}
    clients: List[Dict[str, Any]] = field(default_factory=list)
    # Register map entries: {name, element_id, measurement_type, address, scale, offset, unit}
    register_map: List[Dict[str, Any]] = field(default_factory=list)
    scan_rate_ms: int = 1000


@dataclass
class OpcUaConfig:
    """OPC UA adapter config."""

    enabled: bool = True
    role: AdapterRole = AdapterRole.BOTH
    server_endpoint: str = "opc.tcp://0.0.0.0:4840/etap/server"
    server_name: str = "AhmedETAP.OPCUA.Server"
    server_namespace: int = 3
    # Client endpoints to poll
    clients: List[Dict[str, Any]] = field(default_factory=list)
    # Node map: {node_id, element_id, measurement_type, browse_name}
    node_map: List[Dict[str, Any]] = field(default_factory=list)
    security_mode: str = "None"  # None | Sign | SignAndEncrypt
    security_policy: str = "None"  # None | Basic256 | Basic256Sha256 | Aes128/256
    publish_interval_ms: int = 1000


@dataclass
class Iec104Config:
    """IEC 60870-5-104 adapter config.

    IEC 104 uses the notion of common address (CA) + information object address
    (IOA) to address a single point. We map (ca, ioa) -> (element_id, type).
    """

    enabled: bool = True
    role: AdapterRole = AdapterRole.BOTH
    server_bind_ip: str = "0.0.0.0"
    server_port: int = 2404
    common_address: int = 1
    # Client connections: {name, host, port, common_address}
    clients: List[Dict[str, Any]] = field(default_factory=list)
    # Point map: {ca, ioa, element_id, measurement_type, type_id, cot}
    point_map: List[Dict[str, Any]] = field(default_factory=list)
    # 104 protocol parameters (t0/t1/t2/t3 in seconds, k/w in frames)
    t1_sec: float = 15.0
    t2_sec: float = 10.0
    t3_sec: float = 20.0
    k_frames: int = 12
    w_frames: int = 8


@dataclass
class SCADAProtocolsConfig:
    """Top-level config wrapping all three protocols plus shared options."""

    modbus: ModbusConfig = field(default_factory=ModbusConfig)
    opcua: OpcUaConfig = field(default_factory=OpcUaConfig)
    iec104: Iec104Config = field(default_factory=Iec104Config)
    # When True, a failure to import a protocol library is fatal at start().
    # When False (default), the manager logs a warning and skips the adapter.
    strict_lib_check: bool = False
    # Default quality to assign when the protocol doesn't carry one.
    default_quality: str = "good"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class ConfigError(ValueError):
    """Raised when a YAML config is structurally invalid."""


def _coerce_role(value: Any) -> AdapterRole:
    if isinstance(value, AdapterRole):
        return value
    if not isinstance(value, str):
        raise ConfigError(f"role must be a string, got {type(value).__name__}")
    try:
        return AdapterRole(value.lower())
    except ValueError as exc:
        raise ConfigError(
            f"invalid role {value!r}; must be one of {[r.value for r in AdapterRole]}"
        ) from exc


def _build_modbus(raw: Dict[str, Any]) -> ModbusConfig:
    if not isinstance(raw, dict):
        raise ConfigError("modbus section must be a mapping")
    cfg = ModbusConfig(
        enabled=bool(raw.get("enabled", True)),
        role=_coerce_role(raw.get("role", AdapterRole.BOTH)),
        server_host=str(raw.get("server_host", "0.0.0.0")),
        server_port=int(raw.get("server_port", 5020)),
        server_unit_id=int(raw.get("server_unit_id", 1)),
        clients=list(raw.get("clients", []) or []),
        register_map=list(raw.get("register_map", []) or []),
        scan_rate_ms=int(raw.get("scan_rate_ms", 1000)),
    )
    # Validate register_map entries have required keys
    for i, entry in enumerate(cfg.register_map):
        for key in ("name", "element_id", "measurement_type", "address"):
            if key not in entry:
                raise ConfigError(
                    f"modbus.register_map[{i}] missing required key {key!r}"
                )
    return cfg


def _build_opcua(raw: Dict[str, Any]) -> OpcUaConfig:
    if not isinstance(raw, dict):
        raise ConfigError("opcua section must be a mapping")
    cfg = OpcUaConfig(
        enabled=bool(raw.get("enabled", True)),
        role=_coerce_role(raw.get("role", AdapterRole.BOTH)),
        server_endpoint=str(raw.get("server_endpoint", "opc.tcp://0.0.0.0:4840/etap/server")),
        server_name=str(raw.get("server_name", "AhmedETAP.OPCUA.Server")),
        server_namespace=int(raw.get("server_namespace", 3)),
        clients=list(raw.get("clients", []) or []),
        node_map=list(raw.get("node_map", []) or []),
        security_mode=str(raw.get("security_mode", "None")),
        security_policy=str(raw.get("security_policy", "None")),
        publish_interval_ms=int(raw.get("publish_interval_ms", 1000)),
    )
    for i, entry in enumerate(cfg.node_map):
        for key in ("node_id", "element_id", "measurement_type"):
            if key not in entry:
                raise ConfigError(
                    f"opcua.node_map[{i}] missing required key {key!r}"
                )
    return cfg


def _build_iec104(raw: Dict[str, Any]) -> Iec104Config:
    if not isinstance(raw, dict):
        raise ConfigError("iec104 section must be a mapping")
    cfg = Iec104Config(
        enabled=bool(raw.get("enabled", True)),
        role=_coerce_role(raw.get("role", AdapterRole.BOTH)),
        server_bind_ip=str(raw.get("server_bind_ip", "0.0.0.0")),
        server_port=int(raw.get("server_port", 2404)),
        common_address=int(raw.get("common_address", 1)),
        clients=list(raw.get("clients", []) or []),
        point_map=list(raw.get("point_map", []) or []),
        t1_sec=float(raw.get("t1_sec", 15.0)),
        t2_sec=float(raw.get("t2_sec", 10.0)),
        t3_sec=float(raw.get("t3_sec", 20.0)),
        k_frames=int(raw.get("k_frames", 12)),
        w_frames=int(raw.get("w_frames", 8)),
    )
    for i, entry in enumerate(cfg.point_map):
        for key in ("ca", "ioa", "element_id", "measurement_type"):
            if key not in entry:
                raise ConfigError(
                    f"iec104.point_map[{i}] missing required key {key!r}"
                )
    return cfg


def load_config(path: Optional[str] = None) -> SCADAProtocolsConfig:
    """Load config from a YAML file path.

    If ``path`` is None, look at ``SCADA_PROTOCOLS_CONFIG`` env var.
    If still absent, return defaults (all protocols enabled, no clients/points).
    """
    if path is None:
        path = os.environ.get("SCADA_PROTOCOLS_CONFIG")

    if not path:
        return SCADAProtocolsConfig()

    p = Path(path)
    if not p.exists():
        raise ConfigError(f"config file not found: {path}")

    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML parse error in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("config root must be a mapping")

    return SCADAProtocolsConfig(
        modbus=_build_modbus(raw.get("modbus", {}) or {}),
        opcua=_build_opcua(raw.get("opcua", {}) or {}),
        iec104=_build_iec104(raw.get("iec104", {}) or {}),
        strict_lib_check=bool(raw.get("strict_lib_check", False)),
        default_quality=str(raw.get("default_quality", "good")),
    )


def load_config_from_dict(raw: Dict[str, Any]) -> SCADAProtocolsConfig:
    """Build config from an already-parsed dict (used by tests)."""
    if not isinstance(raw, dict):
        raise ConfigError("config root must be a mapping")
    return SCADAProtocolsConfig(
        modbus=_build_modbus(raw.get("modbus", {}) or {}),
        opcua=_build_opcua(raw.get("opcua", {}) or {}),
        iec104=_build_iec104(raw.get("iec104", {}) or {}),
        strict_lib_check=bool(raw.get("strict_lib_check", False)),
        default_quality=str(raw.get("default_quality", "good")),
    )


__all__ = [
    "ModbusConfig",
    "OpcUaConfig",
    "Iec104Config",
    "SCADAProtocolsConfig",
    "ConfigError",
    "load_config",
    "load_config_from_dict",
]
