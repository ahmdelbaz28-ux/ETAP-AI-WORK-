"""Tests for scada_protocols.opcua.address_space — pure data, no asyncua."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scada_protocols.opcua.address_space import (
    build_plan_from_node_map,
    build_plan_from_system,
)


class TestBuildFromNodeMap:
    def test_empty(self) -> None:
        plan = build_plan_from_node_map([], namespace=3)
        assert plan.namespace == 3
        assert plan.folders == []

    def test_single_entry_default_folder(self) -> None:
        plan = build_plan_from_node_map(
            [
                {
                    "node_id": "ns=3;s=BUS1.V",
                    "element_id": "BUS-1",
                    "measurement_type": "voltage_magnitude",
                    "browse_name": "BUS1.Voltage",
                    "unit": "p.u.",
                    "description": "Bus 1 voltage",
                }
            ]
        )
        assert len(plan.folders) == 1
        folder = plan.folders[0]
        assert folder.browse_name == "Measurements"
        assert len(folder.variables) == 1
        v = folder.variables[0]
        assert v.node_id_hint == "ns=3;s=BUS1.V"
        assert v.element_id == "BUS-1"
        assert v.measurement_type == "voltage_magnitude"
        assert v.unit == "p.u."

    def test_groups_by_folder(self) -> None:
        plan = build_plan_from_node_map(
            [
                {
                    "node_id": "ns=3;s=B1.V",
                    "element_id": "B1",
                    "measurement_type": "v",
                    "folder": "Buses",
                },
                {
                    "node_id": "ns=3;s=L1.I",
                    "element_id": "L1",
                    "measurement_type": "i",
                    "folder": "Lines",
                },
                {
                    "node_id": "ns=3;s=B2.V",
                    "element_id": "B2",
                    "measurement_type": "v",
                    "folder": "Buses",
                },
            ]
        )
        folder_names = [f.browse_name for f in plan.folders]
        assert folder_names == ["Buses", "Lines"]
        buses = plan.folders[0]
        assert len(buses.variables) == 2


# ---------------------------------------------------------------------------
# Fake system object to test build_plan_from_system
# ---------------------------------------------------------------------------


@dataclass
class _FakeBus:
    bus_id: str


@dataclass
class _FakeLine:
    line_id: str


@dataclass
class _FakeTx:
    transformer_id: str


@dataclass
class _FakeSwitch:
    device_id: str


@dataclass
class _FakeSystem:
    buses: list
    lines: list
    transformers: list
    switches: list


class TestBuildFromSystem:
    def test_empty_system(self) -> None:
        sys_obj = _FakeSystem(buses=[], lines=[], transformers=[], switches=[])
        plan = build_plan_from_system(sys_obj, namespace=3)
        assert plan.folders == []

    def test_buses_only(self) -> None:
        sys_obj = _FakeSystem(
            buses=[_FakeBus("BUS-1"), _FakeBus("BUS-2")],
            lines=[],
            transformers=[],
            switches=[],
        )
        plan = build_plan_from_system(sys_obj, namespace=3)
        assert len(plan.folders) == 1
        folder = plan.folders[0]
        assert folder.browse_name == "Buses"
        # 5 measurement types per bus (Voltage, VoltageAngle, Frequency, ActivePower, ReactivePower)
        assert len(folder.variables) == 10
        # Check we have entries for both buses.
        elem_ids = {v.element_id for v in folder.variables}
        assert elem_ids == {"BUS-1", "BUS-2"}

    def test_full_system(self) -> None:
        sys_obj = _FakeSystem(
            buses=[_FakeBus("BUS-1")],
            lines=[_FakeLine("LINE-1")],
            transformers=[_FakeTx("TX-1")],
            switches=[_FakeSwitch("SW-1")],
        )
        plan = build_plan_from_system(sys_obj, namespace=5)
        assert plan.namespace == 5
        folder_names = [f.browse_name for f in plan.folders]
        assert folder_names == ["Buses", "Lines", "Transformers", "Switches"]

    def test_all_variables_helper(self) -> None:
        sys_obj = _FakeSystem(
            buses=[_FakeBus("B1")], lines=[], transformers=[], switches=[]
        )
        plan = build_plan_from_system(sys_obj)
        all_vars = plan.all_variables()
        assert len(all_vars) == 5  # 5 measurement types per bus

    def test_plan_to_dict(self) -> None:
        plan = build_plan_from_node_map(
            [
                {
                    "node_id": "ns=3;s=x",
                    "element_id": "B",
                    "measurement_type": "v",
                }
            ]
        )
        d = plan.to_dict()
        assert d["namespace"] == 3
        assert d["root_name"] == "AhmedETAP"
        assert len(d["folders"]) == 1
        assert d["folders"][0]["variables"][0]["element_id"] == "B"


class TestUAVariableSanitise:
    def test_unsafe_chars_in_node_id_hint_via_system(self) -> None:
        @dataclass
        class B:
            bus_id: str

        @dataclass
        class S:
            buses: list
            lines: list
            transformers: list
            switches: list

        sys_obj = S(buses=[B("Bus With Spaces!")], lines=[], transformers=[], switches=[])
        plan = build_plan_from_system(sys_obj)
        for v in plan.all_variables():
            assert " " not in v.node_id_hint
            assert "!" not in v.node_id_hint
