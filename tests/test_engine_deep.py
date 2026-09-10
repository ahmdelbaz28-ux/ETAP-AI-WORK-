"""
Deep Tests for PowerSystemEngine - engine/engine.py

Tests:
- Dependency injection constructor
- run_load_flow()
- run_fault_analysis() for all 4 fault types
- run_fault_analysis() error paths (invalid type, no solver)
- run_arc_flash() with VCB, invalid configs
- run_protection_coordination() with real config and missing config
- run_study() unified dispatcher for all study types
- run_study() error paths and missing required parameters
"""

from __future__ import annotations

import pytest

from core_model.bus import Bus
from core_model.generator import Generator
from core_model.line import Line
from core_model.load import Load
from core_model.system import System
from engine.engine import PowerSystemEngine


def _build_test_system():
    system = System()
    system.base_mva = 100.0

    b1 = Bus(bus_id=1, voltage_magnitude=1.05, bus_type="slack")
    b2 = Bus(bus_id=2, voltage_magnitude=1.0, bus_type="pq")
    b3 = Bus(bus_id=3, voltage_magnitude=1.0, bus_type="pq")

    system.add_bus(b1)
    system.add_bus(b2)
    system.add_bus(b3)

    gen = Generator(
        generator_id=1,
        bus=b1,
        impedance={"1": complex(0.01, 0.1), "2": complex(0.01, 0.1), "0": complex(0.01, 0.05)},
    )
    system.add_generator(gen)

    l1 = Line(
        line_id=1,
        from_bus=b1,
        to_bus=b2,
        z1=complex(0.02, 0.08),
        z2=complex(0.02, 0.08),
        z0=complex(0.04, 0.2),
    )
    l2 = Line(
        line_id=2,
        from_bus=b2,
        to_bus=b3,
        z1=complex(0.03, 0.12),
        z2=complex(0.03, 0.12),
        z0=complex(0.06, 0.3),
    )
    system.add_line(l1)
    system.add_line(l2)

    load = Load(load_id=1, bus=b3, load_power=complex(0.4, 0.2))
    system.add_load(load)

    return system


@pytest.fixture(name="engine")
def fixture_engine():
    system = _build_test_system()
    return PowerSystemEngine(system)


class TestEngineConstructor:
    def test_default_construction_no_system(self):
        eng = PowerSystemEngine()
        assert eng.system is None
        assert eng.load_flow_solver is None
        assert eng.arc_flash_engine is not None
        assert eng.coordination_engine is not None

    def test_construction_with_system(self, engine):
        assert engine.system is not None
        assert engine.load_flow_solver is not None


class TestEngineLoadFlow:
    def test_run_load_flow_converges(self, engine):
        res = engine.run_load_flow()
        assert res["converged"] is True
        assert 1 in res["bus_voltages"]
        assert 2 in res["bus_voltages"]
        assert 3 in res["bus_voltages"]
        assert res["Ybus"] is not None

    def test_run_study_load_flow(self, engine):
        res = engine.run_study("load_flow")
        assert res["converged"] is True


class TestEngineFaultAnalysis:
    @pytest.mark.parametrize(
        "fault_type",
        [
            "three_phase",
            "line_to_ground",
            "line_to_line",
            "double_line_to_ground",
        ],
    )
    def test_run_fault_analysis_types(self, engine, fault_type):
        res = engine.run_fault_analysis(fault_type=fault_type, bus_id=2)
        assert res is not None
        assert "fault_current" in res
        assert res["affected_bus_index"] >= 0

    def test_unsupported_fault_type_raises(self, engine):
        with pytest.raises(ValueError, match="Unsupported fault type"):
            engine.run_fault_analysis("high_impedance_arcing", bus_id=2)

    def test_fault_no_system_raises(self):
        eng = PowerSystemEngine()
        with pytest.raises(RuntimeError, match="No system model loaded"):
            eng.run_fault_analysis("three_phase", bus_id=1)

    def test_run_study_short_circuit(self, engine):
        res = engine.run_study("short_circuit", bus_id=2, fault_type="three_phase")
        assert res["fault_type"] == "three_phase"

    def test_run_study_short_circuit_missing_bus_raises(self, engine):
        with pytest.raises(ValueError, match="bus_id must be provided"):
            engine.run_study("short_circuit")


class TestEngineArcFlash:
    def test_run_arc_flash_standard(self, engine):
        res = engine.run_arc_flash(
            voltage_kv=0.48,
            bolted_fault_current_ka=25.0,
            arc_duration_sec=0.1,
            working_distance_mm=457.0,
            electrode_config="VCB",
            enclosure_type="box",
        )
        assert res["incident_energy_cal_per_cm2"] > 0
        assert res["arc_flash_boundary_mm"] > 0
        assert res["ppe_level"] in ("0", "1", "2", "3", "4", "DANGER")

    def test_run_arc_flash_invalid_electrode_raises(self, engine):
        with pytest.raises(ValueError, match="Invalid electrode_config"):
            engine.run_arc_flash(0.48, 25.0, 0.1, 457.0, electrode_config="XYZ")

    def test_run_arc_flash_invalid_enclosure_raises(self, engine):
        with pytest.raises(ValueError, match="Invalid enclosure_type"):
            engine.run_arc_flash(0.48, 25.0, 0.1, 457.0, enclosure_type="dome")

    def test_run_study_arc_flash(self, engine):
        res = engine.run_study(
            "arc_flash",
            voltage_kv=0.48,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.1,
            working_distance_mm=457.0,
        )
        assert res["incident_energy_cal_per_cm2"] > 0

    def test_run_study_arc_flash_missing_param_raises(self, engine):
        with pytest.raises(ValueError, match="arc_flash requires"):
            engine.run_study("arc_flash", voltage_kv=0.48)


class TestEngineCoordination:
    def test_run_protection_coordination_missing_config_returns_simulated(self, engine):
        res = engine.run_protection_coordination(
            upstream_relay_id=1,
            downstream_relay_id=2,
            fault_currents=[5.0, 10.0],
            relays_config=None,
        )
        assert res["all_coordinated"] is False
        assert res["is_simulated"] is True
        assert "error" in res

    def test_run_protection_coordination_valid_config(self, engine):
        config = {
            "upstream": {"tms": 0.3, "pickup_current_a": 100.0, "curve_type": "standard_inverse"},
            "downstream": {"tms": 0.1, "pickup_current_a": 100.0, "curve_type": "standard_inverse"},
        }
        res = engine.run_protection_coordination(
            upstream_relay_id=1,
            downstream_relay_id=2,
            fault_currents=[5.0, 10.0],
            relays_config=config,
        )
        assert res["is_simulated"] is False
        assert "all_coordinated" in res
        assert len(res["results"]) == 2

    def test_run_study_coordination_missing_kwargs_raises(self, engine):
        with pytest.raises(ValueError, match="must be provided"):
            engine.run_study("protection_coordination")


class TestEngineUnsupportedStudy:
    def test_unsupported_study_raises(self, engine):
        with pytest.raises(ValueError, match="Unsupported study type"):
            engine.run_study("quantum_superposition_study")
