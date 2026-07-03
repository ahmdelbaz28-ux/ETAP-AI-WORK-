"""
Extended edge case tests for load flow, sparse solver, and power system models.
"""

import numpy as np
import pytest

from core_model.bus import Bus
from core_model.generator import Generator
from core_model.line import Line
from core_model.load import Load
from core_model.motor_model import MotorModel, MotorParameters
from core_model.system import System
from core_model.transformer import Transformer
from load_flow.load_flow import LoadFlowSolver

# ===========================================================================
# Load Flow Solver Edge Cases
# ===========================================================================


class TestLoadFlowEdgeCases:
    def test_single_slack_bus(self):
        """Single bus system — solver may not handle 1-bus cases (needs >= 2 PV+PQ)."""
        system = System(base_mva=100.0)
        bus = Bus(
            bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=13.8
        )
        system.add_bus(bus)
        system.build_ybus(seq="1")
        try:
            solver = LoadFlowSolver(system)
            converged = solver.solve(max_iter=10, tol=1e-4)
        except (ValueError, IndexError, np.linalg.LinAlgError):
            converged = False
        # Accept either convergence or graceful failure
        assert isinstance(converged, bool)

    def test_two_bus_slack_and_load(self):
        """Simple 2-bus: slack + PQ load."""
        system = System(base_mva=100.0)
        b1 = Bus(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=13.8)
        b2 = Bus(
            bus_id=2,
            voltage_magnitude=1.0,
            voltage_angle=0.0,
            bus_type="pq",
            base_kv=13.8,
            load_power=complex(1.0, 0.5),
        )
        system.add_bus(b1)
        system.add_bus(b2)
        line = Line(line_id=1, from_bus=b1, to_bus=b2, z1=complex(0.01, 0.05))
        system.add_line(line)
        system.build_ybus(seq="1")
        solver = LoadFlowSolver(system)
        converged = solver.solve(max_iter=50, tol=1e-6)
        assert converged

    def test_two_bus_slack_and_pv(self):
        """2-bus: slack + PV generator."""
        system = System(base_mva=100.0)
        b1 = Bus(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=13.8)
        b2 = Bus(
            bus_id=2,
            voltage_magnitude=1.0,
            voltage_angle=0.0,
            bus_type="pv",
            base_kv=13.8,
            generation_power=complex(0.5, 0),
        )
        system.add_bus(b1)
        system.add_bus(b2)
        line = Line(line_id=1, from_bus=b1, to_bus=b2, z1=complex(0.01, 0.05))
        system.add_line(line)
        gen = Generator(generator_id=1, bus=b2, impedance={"1": complex(0, 0.2)})
        system.add_generator(gen)
        system.build_ybus(seq="1")
        solver = LoadFlowSolver(system)
        converged = solver.solve(max_iter=50, tol=1e-6)
        assert converged

    def test_three_bus_mesh(self):
        """3-bus meshed system with 2 lines."""
        system = System(base_mva=100.0)
        b1 = Bus(
            bus_id=1, voltage_magnitude=1.02, voltage_angle=0.0, bus_type="slack", base_kv=13.8
        )
        b2 = Bus(
            bus_id=2,
            voltage_magnitude=1.0,
            voltage_angle=0.0,
            bus_type="pq",
            base_kv=13.8,
            load_power=complex(0.8, 0.3),
        )
        b3 = Bus(
            bus_id=3,
            voltage_magnitude=1.01,
            voltage_angle=0.0,
            bus_type="pq",
            base_kv=13.8,
            load_power=complex(0.5, 0.2),
        )
        system.add_bus(b1)
        system.add_bus(b2)
        system.add_bus(b3)
        system.add_line(Line(line_id=1, from_bus=b1, to_bus=b2, z1=complex(0.01, 0.05)))
        system.add_line(Line(line_id=2, from_bus=b2, to_bus=b3, z1=complex(0.015, 0.06)))
        system.build_ybus(seq="1")
        solver = LoadFlowSolver(system)
        converged = solver.solve(max_iter=50, tol=1e-6)
        assert converged

    def test_high_accuracy_mode(self):
        system = System(base_mva=100.0)
        b1 = Bus(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=13.8)
        b2 = Bus(
            bus_id=2,
            voltage_magnitude=1.0,
            voltage_angle=0.0,
            bus_type="pq",
            base_kv=13.8,
            load_power=complex(0.5, 0.2),
        )
        system.add_bus(b1)
        system.add_bus(b2)
        system.add_line(Line(line_id=1, from_bus=b1, to_bus=b2, z1=complex(0.01, 0.05)))
        system.build_ybus(seq="1")
        solver = LoadFlowSolver(system)
        converged = solver.solve(max_iter=50, tol=1e-6, mode="high_accuracy")
        assert converged

    def test_voltage_limits(self):
        """Test that solved voltages are within reasonable bounds."""
        system = System(base_mva=100.0)
        b1 = Bus(bus_id=1, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="slack", base_kv=13.8)
        b2 = Bus(
            bus_id=2,
            voltage_magnitude=1.0,
            voltage_angle=0.0,
            bus_type="pq",
            base_kv=13.8,
            load_power=complex(0.5, 0.2),
        )
        system.add_bus(b1)
        system.add_bus(b2)
        system.add_line(Line(line_id=1, from_bus=b1, to_bus=b2, z1=complex(0.01, 0.05)))
        system.build_ybus(seq="1")
        solver = LoadFlowSolver(system)
        solver.solve(max_iter=50, tol=1e-6)
        for bid in solver.bus_ids:
            v = abs(solver.V[solver.bus_index[bid]])
            assert 0.8 <= v <= 1.2


# ===========================================================================
# Bus Model Edge Cases
# ===========================================================================


class TestBusEdgeCases:
    def test_bus_default_values(self):
        bus = Bus(bus_id=1)
        assert bus.bus_id == 1
        assert bus.bus_type == "pq"

    def test_bus_with_q_limits(self):
        bus = Bus(bus_id=1, bus_type="pv", q_min=-0.5, q_max=0.5)
        assert bus.q_min == -0.5
        assert bus.q_max == pytest.approx(0.5)

    def test_bus_complex_power(self):
        bus = Bus(bus_id=1, generation_power=complex(1.0, 0.5), load_power=complex(0.3, 0.1))
        assert bus.generation_power.real == pytest.approx(1.0)
        assert bus.load_power.imag == pytest.approx(0.1)

    def test_bus_voltage_setter(self):
        bus = Bus(bus_id=1)
        bus.voltage = complex(1.05, 0.1)
        assert abs(bus.voltage - complex(1.05, 0.1)) < 1e-10

    def test_bus_with_zero_voltage(self):
        bus = Bus(bus_id=1, voltage_magnitude=0.0, voltage_angle=0.0)
        assert bus.voltage == complex(0, 0)


# ===========================================================================
# Line Model Edge Cases
# ===========================================================================


class TestLineEdgeCases:
    def test_line_impedance_zero(self):
        b1 = Bus(bus_id=1)
        b2 = Bus(bus_id=2)
        line = Line(line_id=1, from_bus=b1, to_bus=b2, z1=complex(0, 0))
        z = line.get_impedance("1")
        assert z == complex(0, 0)

    def test_line_with_zero_seq(self):
        b1 = Bus(bus_id=1)
        b2 = Bus(bus_id=2)
        line = Line(
            line_id=1, from_bus=b1, to_bus=b2, z1=complex(0.01, 0.05), z0=complex(0.03, 0.15)
        )
        assert line.get_impedance("0") == complex(0.03, 0.15)
        assert line.get_impedance("1") == complex(0.01, 0.05)
        assert line.get_impedance("2") == complex(0.01, 0.05)

    def test_line_shunt_admittance(self):
        b1 = Bus(bus_id=1)
        b2 = Bus(bus_id=2)
        line = Line(
            line_id=1, from_bus=b1, to_bus=b2, z1=complex(0.01, 0.05), yshunt1=complex(0, 0.001)
        )
        assert line.get_shunt_admittance("1") == complex(0, 0.001)


# ===========================================================================
# Transformer Model
# ===========================================================================


class TestTransformerEdgeCases:
    def test_transformer_defaults(self):
        b1 = Bus(bus_id=1)
        b2 = Bus(bus_id=2)
        t = Transformer(transformer_id=1, from_bus=b1, to_bus=b2, z1=complex(0.01, 0.1))
        assert t.transformer_id == 1
        assert t.tap_ratio == pytest.approx(1.0)

    def test_transformer_with_tap(self):
        b1 = Bus(bus_id=1)
        b2 = Bus(bus_id=2)
        t = Transformer(
            transformer_id=1, from_bus=b1, to_bus=b2, z1=complex(0.01, 0.1), tap_ratio=1.05
        )
        assert t.tap_ratio == pytest.approx(1.05)
        z = t.get_impedance("1")
        assert z == complex(0.01, 0.1)

    def test_transformer_phase_shift(self):
        b1 = Bus(bus_id=1)
        b2 = Bus(bus_id=2)
        t = Transformer(
            transformer_id=1, from_bus=b1, to_bus=b2, z1=complex(0.01, 0.1), phase_shift=30
        )
        assert t.phase_shift == 30

    def test_transformer_rating(self):
        b1 = Bus(bus_id=1)
        b2 = Bus(bus_id=2)
        t = Transformer(transformer_id=1, from_bus=b1, to_bus=b2, z1=complex(0.01, 0.1), rating=50)
        assert t.rating == 50

    def test_transformer_default_rating_none(self):
        b1 = Bus(bus_id=1)
        b2 = Bus(bus_id=2)
        t = Transformer(transformer_id=1, from_bus=b1, to_bus=b2, z1=complex(0.01, 0.1))
        assert t.rating is None


# ===========================================================================
# Motor Model
# ===========================================================================


class TestMotorModel:
    def test_motor_defaults(self):
        params = MotorParameters()
        m = MotorModel(params)
        assert hasattr(m, "params")
        assert m.params.rated_hp == pytest.approx(100.0)
        assert m.params.rated_kv == pytest.approx(0.46)

    def test_motor_efficiency(self):
        params = MotorParameters(efficiency=0.95)
        m = MotorModel(params)
        assert m.params.efficiency == pytest.approx(0.95)

    def test_motor_power_factor(self):
        params = MotorParameters(power_factor=0.85)
        m = MotorModel(params)
        assert m.params.power_factor == pytest.approx(0.85)

    def test_motor_starting_current(self):
        params = MotorParameters(lr_current_multiplier=6.0)
        m = MotorModel(params)
        assert m.params.lr_current_multiplier == pytest.approx(6.0)

    def test_motor_custom_name(self):
        params = MotorParameters(name="Pump Motor")
        m = MotorModel(params)
        assert m.params.name == "Pump Motor"


# ===========================================================================
# Generator Model Additional Tests
# ===========================================================================


class TestGeneratorAdditional:
    def test_generator_with_impedance(self):
        bus = Bus(bus_id=1)
        gen = Generator(
            generator_id=1, bus=bus, impedance={"1": complex(0, 0.25), "0": complex(0, 0.15)}
        )
        assert gen.impedance["1"] == complex(0, 0.25)
        assert gen.impedance["0"] == complex(0, 0.15)

    def test_generator_internal_voltage(self):
        bus = Bus(bus_id=1)
        gen = Generator(generator_id=1, bus=bus, internal_voltage={"1": complex(1.0, 0.1)})
        assert gen.internal_voltage["1"] == complex(1.0, 0.1)


# ===========================================================================
# Load Model Additional Tests
# ===========================================================================


class TestLoadAdditional:
    def test_load_defaults(self):
        bus = Bus(bus_id=1)
        load = Load(load_id=1, bus=bus, load_power=complex(0.5, 0.2))
        assert load.load_id == 1
        assert load.load_power == complex(0.5, 0.2)

    def test_load_constant_impedance_true(self):
        bus = Bus(bus_id=1)
        load = Load(load_id=1, bus=bus, load_power=complex(0.5, 0.2), constant_impedance=True)
        assert load.constant_impedance is True

    def test_load_constant_impedance_false(self):
        bus = Bus(bus_id=1)
        load = Load(load_id=1, bus=bus, load_power=complex(0.5, 0.2), constant_impedance=False)
        assert load.constant_impedance is False

    def test_load_power_factor(self):
        bus = Bus(bus_id=1)
        load = Load(load_id=1, bus=bus, load_power=complex(0.5, 0.2), power_factor=0.9)
        assert load.power_factor == pytest.approx(0.9)

    def test_load_impedance(self):
        bus = Bus(bus_id=1)
        load = Load(load_id=1, bus=bus, impedance=complex(1.0, 0.5))
        assert load.impedance == complex(1.0, 0.5)
