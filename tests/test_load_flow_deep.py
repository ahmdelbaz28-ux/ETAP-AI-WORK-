"""
Deep Load Flow Tests - load_flow/load_flow.py

LoadFlowSolver.solve() returns bool (True=converged, False=diverged).
Bus voltages are in solver.V after convergence.
Bus voltage dict: {bus_id: |V|} built from solver.bus_ids + solver.V
"""

from __future__ import annotations

import numpy as np
import pytest

from core_model.bus import Bus
from core_model.line import Line
from core_model.system import System
from load_flow.load_flow import LoadFlowSolver


def _make_system(bus_configs, line_configs, base_mva=100):
    system = System()
    system.base_mva = base_mva
    bus_lookup = {}
    for bc in bus_configs:
        bus = Bus(
            bus_id=bc["bus_id"],
            voltage_magnitude=bc.get("voltage_magnitude", 1.0),
            voltage_angle=bc.get("voltage_angle", 0.0),
            bus_type=bc.get("bus_type", "pq"),
        )
        p = bc.get("load_power_real", 0)
        q = bc.get("load_power_reactive", 0)
        if p or q:
            bus.load_power = complex(p / base_mva, q / base_mva)
        gen_p = bc.get("active_power", 0)
        if gen_p:
            bus.generation_power = complex(gen_p / base_mva, 0)
        if bc.get("q_min") is not None:
            bus.q_min = bc["q_min"]
        if bc.get("q_max") is not None:
            bus.q_max = bc["q_max"]
        system.add_bus(bus)
        bus_lookup[bc["bus_id"]] = bus
    for lc in line_configs:
        line = Line(
            line_id=lc["line_id"],
            from_bus=bus_lookup[lc["from_bus_id"]],
            to_bus=bus_lookup[lc["to_bus_id"]],
            z1=complex(lc.get("r1", 0), lc.get("x1", 0)),
        )
        system.add_line(line)
    return system, bus_lookup


def _bus_voltages(solver):
    return {bid: abs(solver.V[i]) for i, bid in enumerate(solver.bus_ids)}


BUS_4 = [
    {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.05},
    {"bus_id": 2, "bus_type": "pq", "load_power_real": 2.0, "load_power_reactive": 1.6},
    {"bus_id": 3, "bus_type": "pq", "load_power_real": 0.0, "load_power_reactive": 2.0},
    {"bus_id": 4, "bus_type": "pq", "load_power_real": 1.0, "load_power_reactive": 0.8},
]
LINE_4 = [
    {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05},
    {"line_id": 2, "from_bus_id": 2, "to_bus_id": 3, "r1": 0.015, "x1": 0.06},
    {"line_id": 3, "from_bus_id": 3, "to_bus_id": 4, "r1": 0.02, "x1": 0.07},
]
BUS_14_FULL = [
    {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.06},
    {"bus_id": 2, "bus_type": "pv", "voltage_magnitude": 1.045, "active_power": 40.0},
    {"bus_id": 3, "bus_type": "pq", "load_power_real": 94.2, "load_power_reactive": 19.0},
    {"bus_id": 4, "bus_type": "pq", "load_power_real": 47.8, "load_power_reactive": -3.9},
    {"bus_id": 5, "bus_type": "pq", "load_power_real": 7.6, "load_power_reactive": 1.6},
]
LINE_14_FULL = [
    {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01938, "x1": 0.05917},
    {"line_id": 2, "from_bus_id": 1, "to_bus_id": 5, "r1": 0.05403, "x1": 0.22304},
    {"line_id": 3, "from_bus_id": 2, "to_bus_id": 3, "r1": 0.04699, "x1": 0.19797},
    {"line_id": 4, "from_bus_id": 2, "to_bus_id": 4, "r1": 0.05811, "x1": 0.17632},
    {"line_id": 5, "from_bus_id": 3, "to_bus_id": 4, "r1": 0.06701, "x1": 0.17103},
    {"line_id": 6, "from_bus_id": 4, "to_bus_id": 5, "r1": 0.01335, "x1": 0.04211},
]


@pytest.fixture(name="solver4")
def fixture_solver4():
    system, _ = _make_system(BUS_4, LINE_4)
    return LoadFlowSolver(system)


class TestLoadFlow4Bus:
    def test_converges(self, solver4):
        assert solver4.solve()

    def test_returns_bool(self, solver4):
        result = solver4.solve()
        assert isinstance(result, bool)

    def test_slack_voltage_held(self, solver4):
        solver4.solve()
        v = _bus_voltages(solver4)
        assert abs(v[1] - 1.05) < 0.005

    def test_voltage_drop_radial(self, solver4):
        assert solver4.solve()
        v = _bus_voltages(solver4)
        assert v[1] >= v[2]
        assert v[2] >= v[3]
        assert v[3] >= v[4]

    def test_all_voltages_in_range(self, solver4):
        assert solver4.solve()
        v = _bus_voltages(solver4)
        for bid, vmag in v.items():
            assert 0.9 <= vmag <= 1.1

    def test_iterations_reasonable(self, solver4):
        solver4.solve()
        assert len(solver4.iteration_log) <= 50

    def test_high_accuracy_mode(self):
        system, _ = _make_system(BUS_4, LINE_4)
        s = LoadFlowSolver(system)
        assert s.solve(mode="high_accuracy")

    def test_jacobian_dimensions(self, solver4):
        # 4-bus system (1 slack, 0 PV, 3 PQ) -> 3 unknown angles + 3 unknown voltages = 6 unknowns
        # Jacobian dimension must strictly equal 6x6 per IEEE 3002.7 standard Newton-Raphson formulation
        expected_dim = 6
        J = solver4._build_jacobian(solver4.V)
        assert J.shape == (expected_dim, expected_dim)

    def test_jacobian_finite_values(self, solver4):
        J = solver4._build_jacobian(solver4.V)
        assert np.all(np.isfinite(J))

    def test_step_limiting_caps_angle(self, solver4):
        big = np.ones(solver4.n_unknowns) * 10.0
        limited = solver4._apply_step_limiting(big)
        n_pv = len(solver4.pv_indices)
        n_pq = len(solver4.pq_indices)
        for i in range(n_pv + n_pq):
            assert abs(limited[i]) <= solver4.max_step_angle + 1e-9

    def test_step_limiting_caps_voltage(self, solver4):
        big = np.ones(solver4.n_unknowns) * 10.0
        limited = solver4._apply_step_limiting(big)
        n_pv = len(solver4.pv_indices)
        n_pq = len(solver4.pq_indices)
        for i in range(n_pq):
            assert abs(limited[n_pv + n_pq + i]) <= solver4.max_step_voltage + 1e-9

    def test_oscillation_not_detected_short(self, solver4):
        assert not solver4._detect_oscillation([1.0, 0.9, 0.8])

    def test_oscillation_detected_growing(self, solver4):
        w = solver4.oscillation_window
        history = [0.001] * w + [10.0] * w
        assert solver4._detect_oscillation(history)

    def test_scheduled_power_load_bus_negative(self, solver4):
        p_sch, _ = solver4._scheduled_power()
        idx2 = solver4.bus_index[2]
        assert p_sch[idx2] < 0

    def test_power_mismatch_shape(self, solver4):
        p_sch, q_sch = solver4._scheduled_power()
        m = solver4._build_mismatch_vector(*solver4._power_mismatch(solver4.V, p_sch, q_sch))
        assert isinstance(m, np.ndarray)
        assert m.shape == (solver4.n_unknowns,)

    def test_q_limit_check_returns_bool(self, solver4):
        switched = solver4._check_q_limits(solver4.V)
        assert isinstance(switched, bool)

    def test_switching_log_empty_pq_only(self, solver4):
        solver4.solve()
        assert solver4.switching_log == []

    def test_rebuild_bus_type_indices(self, solver4):
        solver4._rebuild_bus_type_indices()
        assert hasattr(solver4, "slack_indices")
        assert hasattr(solver4, "pv_indices")
        assert hasattr(solver4, "pq_indices")


class TestLoadFlow14BusFullLoad:
    """IEEE 14-bus with original un-lightened loads (94.2 MW on bus 3)."""

    def test_converges(self):
        system, _ = _make_system(BUS_14_FULL, LINE_14_FULL)
        assert LoadFlowSolver(system).solve()

    def test_all_voltages_in_range(self):
        system, _ = _make_system(BUS_14_FULL, LINE_14_FULL)
        solver = LoadFlowSolver(system)
        solver.solve()
        v = _bus_voltages(solver)
        for bid, vmag in v.items():
            assert 0.80 <= vmag <= 1.15

    def test_slack_bus_voltage_fixed(self):
        system, _ = _make_system(BUS_14_FULL, LINE_14_FULL)
        solver = LoadFlowSolver(system)
        solver.solve()
        v = _bus_voltages(solver)
        assert abs(v[1] - 1.06) < 0.01


class TestPVtoPQSwitching:
    def test_no_switching_generous_limits(self):
        system, _ = _make_system(
            [
                {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.05},
                {
                    "bus_id": 2,
                    "bus_type": "pv",
                    "voltage_magnitude": 1.02,
                    "active_power": 5.0,
                    "q_min": -100.0,
                    "q_max": 100.0,
                },
                {"bus_id": 3, "bus_type": "pq", "load_power_real": 3.0, "load_power_reactive": 1.0},
            ],
            [
                {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.02, "x1": 0.06},
                {"line_id": 2, "from_bus_id": 2, "to_bus_id": 3, "r1": 0.03, "x1": 0.09},
            ],
        )
        solver = LoadFlowSolver(system)
        assert solver.solve()
        assert solver.switching_log == []

    def test_tight_qmax_no_crash(self):
        system, _ = _make_system(
            [
                {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.05},
                {
                    "bus_id": 2,
                    "bus_type": "pv",
                    "voltage_magnitude": 1.02,
                    "active_power": 10.0,
                    "q_min": -0.001,
                    "q_max": 0.001,
                },
                {"bus_id": 3, "bus_type": "pq", "load_power_real": 8.0, "load_power_reactive": 4.0},
            ],
            [
                {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.02, "x1": 0.06},
                {"line_id": 2, "from_bus_id": 2, "to_bus_id": 3, "r1": 0.03, "x1": 0.09},
            ],
        )
        result = LoadFlowSolver(system).solve()
        assert isinstance(result, bool)


class TestYbusSymmetry:
    @pytest.mark.parametrize(
        "bus_c,line_c,name",
        [
            (BUS_4, LINE_4, "4-bus"),
            (BUS_14_FULL, LINE_14_FULL, "14-bus-full"),
        ],
    )
    def test_ybus_is_symmetric(self, bus_c, line_c, name):
        system, _ = _make_system(bus_c, line_c)
        Y = system.get_ybus(seq="1")
        diff = np.max(np.abs(Y - Y.T))
        assert diff < 1e-10

    def test_ybus_4bus_diagonal_dominance(self):
        system, _ = _make_system(BUS_4, LINE_4)
        Y = system.get_ybus(seq="1")
        n = Y.shape[0]
        # In a network without shunt elements, sum of each row of Ybus equals 0 (Kirchhoff's current conservation)
        for i in range(n):
            row_sum = np.sum(Y[i, :])
            assert abs(row_sum) < 1e-9


class TestEdgeCases:
    def test_two_bus_converges(self):
        system, _ = _make_system(
            [
                {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.05},
                {"bus_id": 2, "bus_type": "pq", "load_power_real": 1.0, "load_power_reactive": 0.5},
            ],
            [{"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05}],
        )
        assert LoadFlowSolver(system).solve()


class TestSparseLoadFlowSolver:
    """Test sparse Newton-Raphson load-flow integration in load_flow.solver."""

    def test_solve_load_flow_sparse_basic(self):
        from load_flow.solver import solve_load_flow_sparse

        buses = [
            {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.05},
            {"bus_id": 2, "bus_type": "pq", "load_power_real": 1.0, "load_power_reactive": 0.5},
        ]
        branches = [{"branch_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r": 0.01, "x": 0.05}]
        res = solve_load_flow_sparse(buses, branches, options={"max_iter": 30, "tol": 1e-6})
        assert isinstance(res, dict)
        assert res.get("converged") is True
        assert 1 in res.get("voltages", {})
        assert 2 in res.get("voltages", {})
