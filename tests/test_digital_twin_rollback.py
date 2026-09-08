"""tests/test_digital_twin_rollback.py — Test rollback behavior on propagate_load_change failure (B8)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from digital_twin.digital_twin_core import ChangePropagationEngine
from digital_twin.event_bus import EventBus


class DummyBus:
    def __init__(self, bus_id: int, load_power: complex):
        self.bus_id = bus_id
        self.load_power = load_power


class DummySystem:
    def __init__(self, fail_build: bool = False):
        self.buses = {1: DummyBus(1, complex(10, 2))}
        self.Ybus_seq = {"1": "orig_ybus_matrix"}
        self.fail_build = fail_build

    def build_ybus(self, seq="1"):
        if self.fail_build:
            raise RuntimeError("Build Ybus matrix failed")
        self.Ybus_seq[seq] = "new_ybus_matrix"


class DummyDTState:
    def __init__(self, system):
        self.system = system

    def capture_snapshot(self, **kwargs):
        return MagicMock(validation_passed=True)

    def validate(self):
        return []

    def commit_snapshot(self, snapshot):
        return "v2"


def test_propagate_load_change_rollback_on_failure():
    system = DummySystem(fail_build=True)
    dt_state = DummyDTState(system)
    event_bus = EventBus()
    sync_engine = MagicMock()
    validation_gateway = MagicMock()

    dt_core = ChangePropagationEngine(
        dt_state=dt_state,
        event_bus=event_bus,
        sync_engine=sync_engine,
        validation_gateway=validation_gateway,
    )

    # Initial state
    assert system.buses[1].load_power == complex(10, 2)
    assert system.Ybus_seq["1"] == "orig_ybus_matrix"

    # Propagate with failure during build_ybus
    res = dt_core.propagate_load_change(bus_id="1", new_power=complex(99, 99))
    assert res["success"] is False
    assert "state rolled back" in res["error"]

    # State must be rolled back to original!
    assert system.buses[1].load_power == complex(10, 2)
    assert system.Ybus_seq["1"] == "orig_ybus_matrix"
