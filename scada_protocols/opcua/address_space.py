"""
scada_protocols.opcua.address_space
====================================
Build an OPC UA address space from the platform's electrical model.

The address space mirrors the structure of ``core_model.system.System``:
- One folder per bus (``ns=<ns>;s=Bus_<id>``)
- One variable per measurement type (Voltage / ActivePower / ...)
- Optional transformer / line / generator folders

This module is independent of ``asyncua`` so it can be unit-tested in
isolation. ``OpcUaServerAdapter`` consumes the produced ``AddressSpacePlan``
and turns it into actual UA nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class UAVariable:
    """One leaf variable in the address space."""

    browse_name: str
    node_id_hint: str  # e.g. "BUS1.Voltage"
    measurement_type: str
    element_id: str
    initial_value: float = 0.0
    unit: str = ""
    description: str = ""


@dataclass
class UAFolder:
    browse_name: str
    node_id_hint: str
    description: str = ""
    variables: List[UAVariable] = field(default_factory=list)


@dataclass
class AddressSpacePlan:
    namespace: int
    folders: List[UAFolder] = field(default_factory=list)
    root_name: str = "AhmedETAP"

    def all_variables(self) -> List[UAVariable]:
        out: List[UAVariable] = []
        for folder in self.folders:
            out.extend(folder.variables)
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "namespace": self.namespace,
            "root_name": self.root_name,
            "folders": [
                {
                    "browse_name": f.browse_name,
                    "node_id_hint": f.node_id_hint,
                    "description": f.description,
                    "variables": [v.__dict__ for v in f.variables],
                }
                for f in self.folders
            ],
        }


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


# Default measurement types to expose per asset class.
_BUS_MEASUREMENTS = [
    ("Voltage", "voltage_magnitude", "p.u.", "Bus voltage magnitude"),
    ("VoltageAngle", "voltage_angle", "deg", "Bus voltage angle"),
    ("Frequency", "frequency", "Hz", "Bus frequency"),
    ("ActivePower", "active_power", "MW", "Net active power injection"),
    ("ReactivePower", "reactive_power", "MVar", "Net reactive power injection"),
]

_LINE_MEASUREMENTS = [
    ("Current", "current_magnitude", "A", "Line current magnitude"),
    ("ActivePower", "active_power", "MW", "Line active power flow"),
    ("ReactivePower", "reactive_power", "MVar", "Line reactive power flow"),
]

_TRANSFORMER_MEASUREMENTS = [
    ("TapPosition", "tap_position", "step", "Transformer tap position"),
    ("ActivePower", "active_power", "MW", "Transformer active power flow"),
    ("ReactivePower", "reactive_power", "MVar", "Transformer reactive power flow"),
]

_SWITCH_MEASUREMENTS = [
    ("Status", "breaker_status", "0/1", "Switch status (0=open, 1=closed)"),
]


def _safe_node_id_hint(prefix: str, name: str) -> str:
    # OPC UA node id hints should be filesystem-ish safe.
    safe = "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in str(name))
    return f"{prefix}.{safe}"


def build_plan_from_node_map(
    node_map: List[Dict[str, Any]],
    namespace: int = 3,
) -> AddressSpacePlan:
    """Build an address space from the YAML ``opcua.node_map`` list.

    Each node_map entry must have ``node_id``, ``element_id``, ``measurement_type``
    (see ``OpcUaConfig``). Optional fields: ``browse_name``, ``unit``,
    ``description``, ``initial_value``, ``folder``.
    """
    plan = AddressSpacePlan(namespace=namespace)
    folders_by_name: Dict[str, UAFolder] = {}

    for raw in node_map:
        folder_name = str(raw.get("folder", "Measurements"))
        folder = folders_by_name.get(folder_name)
        if folder is None:
            folder = UAFolder(
                browse_name=folder_name,
                node_id_hint=_safe_node_id_hint("Folder", folder_name),
                description=f"{folder_name} variables",
            )
            folders_by_name[folder_name] = folder
            plan.folders.append(folder)

        var = UAVariable(
            browse_name=str(raw.get("browse_name", raw["node_id"])),
            node_id_hint=str(raw["node_id"]),
            measurement_type=str(raw["measurement_type"]),
            element_id=str(raw["element_id"]),
            initial_value=float(raw.get("initial_value", 0.0)),
            unit=str(raw.get("unit", "")),
            description=str(raw.get("description", "")),
        )
        folder.variables.append(var)

    return plan


def build_plan_from_system(
    system: Any,
    namespace: int = 3,
) -> AddressSpacePlan:
    """Build an address space from a ``core_model.system.System`` instance.

    This is the auto-discovery path: when no explicit ``node_map`` is provided
    in the YAML config, the OPC UA server introspects the platform's electrical
    model and exposes one variable per bus/line/transformer measurement.
    """
    plan = AddressSpacePlan(namespace=namespace)

    # Buses
    buses = list(getattr(system, "buses", []) or [])
    if buses:
        folder = UAFolder(
            browse_name="Buses",
            node_id_hint="Folder.Buses",
            description="Per-bus measurements",
        )
        for bus in buses:
            bus_id = str(getattr(bus, "bus_id", getattr(bus, "id", "")))
            for bn, mtype, unit, desc in _BUS_MEASUREMENTS:
                folder.variables.append(
                    UAVariable(
                        browse_name=f"{bus_id}.{bn}",
                        node_id_hint=_safe_node_id_hint("Bus", f"{bus_id}.{bn}"),
                        measurement_type=mtype,
                        element_id=bus_id,
                        initial_value=0.0,
                        unit=unit,
                        description=f"{bn} of {bus_id} — {desc}",
                    )
                )
        plan.folders.append(folder)

    # Lines
    lines = list(getattr(system, "lines", []) or [])
    if lines:
        folder = UAFolder(
            browse_name="Lines",
            node_id_hint="Folder.Lines",
            description="Per-line measurements",
        )
        for line in lines:
            line_id = str(getattr(line, "line_id", getattr(line, "id", "")))
            for bn, mtype, unit, desc in _LINE_MEASUREMENTS:
                folder.variables.append(
                    UAVariable(
                        browse_name=f"{line_id}.{bn}",
                        node_id_hint=_safe_node_id_hint("Line", f"{line_id}.{bn}"),
                        measurement_type=mtype,
                        element_id=line_id,
                        initial_value=0.0,
                        unit=unit,
                        description=f"{bn} of {line_id} — {desc}",
                    )
                )
        plan.folders.append(folder)

    # Transformers
    transformers = list(getattr(system, "transformers", []) or [])
    if transformers:
        folder = UAFolder(
            browse_name="Transformers",
            node_id_hint="Folder.Transformers",
            description="Per-transformer measurements",
        )
        for tx in transformers:
            tx_id = str(getattr(tx, "transformer_id", getattr(tx, "id", "")))
            for bn, mtype, unit, desc in _TRANSFORMER_MEASUREMENTS:
                folder.variables.append(
                    UAVariable(
                        browse_name=f"{tx_id}.{bn}",
                        node_id_hint=_safe_node_id_hint("Tx", f"{tx_id}.{bn}"),
                        measurement_type=mtype,
                        element_id=tx_id,
                        initial_value=0.0,
                        unit=unit,
                        description=f"{bn} of {tx_id} — {desc}",
                    )
                )
        plan.folders.append(folder)

    # Switches
    switches = list(getattr(system, "switches", []) or [])
    if switches:
        folder = UAFolder(
            browse_name="Switches",
            node_id_hint="Folder.Switches",
            description="Per-switch status",
        )
        for sw in switches:
            sw_id = str(getattr(sw, "device_id", getattr(sw, "id", "")))
            for bn, mtype, unit, desc in _SWITCH_MEASUREMENTS:
                folder.variables.append(
                    UAVariable(
                        browse_name=f"{sw_id}.{bn}",
                        node_id_hint=_safe_node_id_hint("Sw", f"{sw_id}.{bn}"),
                        measurement_type=mtype,
                        element_id=sw_id,
                        initial_value=0.0,
                        unit=unit,
                        description=f"{bn} of {sw_id} — {desc}",
                    )
                )
        plan.folders.append(folder)

    return plan


__all__ = [
    "UAVariable",
    "UAFolder",
    "AddressSpacePlan",
    "build_plan_from_node_map",
    "build_plan_from_system",
]
