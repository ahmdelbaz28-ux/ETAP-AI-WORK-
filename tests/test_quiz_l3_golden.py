"""
Regression Test: Quiz L3 Golden Standard Benchmark (Lecture 3 - Dr. Mohamed El-Said)
=====================================================================================

Validates the full 4-bus + 2-generator/motor source network with non-zero angles
(10.0 deg and -22.0 deg passed in degrees via documented SystemSpec contract).

Compares results against an independent Norton equivalent linear solver:
  - Bus voltage magnitude difference: dmag < 5e-4 pu
  - Bus voltage angle difference: dang < 5e-3 degrees
  - Verified extraction of items (a), (b), (c), (d) directly from study result
  - Validates degenerate solution physical guard
"""

import math

import numpy as np
import pytest

from core_model.specs import BusSpec, LineSpec, StudyRequest, SystemSpec
from services.study_executor import StudyExecutor


def solve_l3_norton_independent():
    """Independent Norton equivalent solver for the L3 4-bus transmission grid."""
    Y = np.zeros((4, 4), dtype=complex)
    # Transmission lines (1-indexed -> 0-indexed)
    lines = [
        (0, 1, 0.2),   # 1-2
        (1, 2, 0.2),   # 2-3
        (0, 3, 0.15),  # 1-4
        (1, 3, 0.4),   # 2-4
        (2, 3, 0.2),   # 3-4
    ]
    for i, j, x in lines:
        y = 1.0 / (1j * x)
        Y[i, i] += y
        Y[j, j] += y
        Y[i, j] -= y
        Y[j, i] -= y

    # Generator at Bus 1 (index 0): E1 = 1.1 at 10 deg, zg = 1.1j
    E1 = 1.1 * np.exp(1j * math.radians(10.0))
    zg = 1.1j
    yg = 1.0 / zg
    Y[0, 0] += yg
    I1 = E1 / zg

    # Motor at Bus 3 (index 2): E3 = 0.9 at -22 deg, zm = 1.6j
    E3 = 0.9 * np.exp(1j * math.radians(-22.0))
    zm = 1.6j
    ym = 1.0 / zm
    Y[2, 2] += ym
    I3 = E3 / zm

    I = np.array([I1, 0.0, I3, 0.0], dtype=complex)
    V_norton = np.linalg.solve(Y, I)
    return V_norton


def build_l3_system_spec() -> SystemSpec:
    """Build L3 SystemSpec with angles in degrees via documented API path."""
    buses = [
        BusSpec(bus_id=1, bus_type="pq", voltage_magnitude=1.0, voltage_angle=0.0),
        BusSpec(bus_id=2, bus_type="pq", voltage_magnitude=1.0, voltage_angle=0.0),
        BusSpec(bus_id=3, bus_type="pq", voltage_magnitude=1.0, voltage_angle=0.0),
        BusSpec(bus_id=4, bus_type="pq", voltage_magnitude=1.0, voltage_angle=0.0),
        # Internal generator source bus 5 at 1.1 pu, 10.0 deg (in degrees)
        BusSpec(bus_id=5, bus_type="slack", voltage_magnitude=1.1, voltage_angle=10.0),
        # Internal motor source bus 6 at 0.9 pu, -22.0 deg (in degrees)
        BusSpec(bus_id=6, bus_type="slack", voltage_magnitude=0.9, voltage_angle=-22.0),
    ]
    lines = [
        LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.0, x1=0.2, bshunt1=0.0),
        LineSpec(line_id=2, from_bus_id=2, to_bus_id=3, r1=0.0, x1=0.2, bshunt1=0.0),
        LineSpec(line_id=3, from_bus_id=1, to_bus_id=4, r1=0.0, x1=0.15, bshunt1=0.0),
        LineSpec(line_id=4, from_bus_id=2, to_bus_id=4, r1=0.0, x1=0.4, bshunt1=0.0),
        LineSpec(line_id=5, from_bus_id=3, to_bus_id=4, r1=0.0, x1=0.2, bshunt1=0.0),
        LineSpec(line_id=6, from_bus_id=5, to_bus_id=1, r1=0.0, x1=1.1, bshunt1=0.0),
        LineSpec(line_id=7, from_bus_id=6, to_bus_id=3, r1=0.0, x1=1.6, bshunt1=0.0),
    ]
    return SystemSpec(base_mva=100.0, buses=buses, lines=lines)


@pytest.mark.asyncio
async def test_quiz_l3_golden_match():
    """Verify L3 load flow solution matches independent Norton benchmark within strict tolerance."""
    system_spec = build_l3_system_spec()
    req = StudyRequest(
        study_type="load_flow",
        system=system_spec,
        parameters={"tol": 1e-10, "max_iter": 80},
    )

    executor = StudyExecutor()
    res = await executor.execute(req)

    assert res.success is True, f"Study failed: {res.errors}"
    assert res.result["converged"] is True

    # 1. Compare Voltages on Buses 1..4 against Norton independent solution
    v_norton = solve_l3_norton_independent()
    bus_voltages = res.result["bus_voltages"]

    for idx in range(1, 5):
        bid = str(idx)
        assert bid in bus_voltages
        v_entry = bus_voltages[bid]
        v_re = v_entry["re"]
        v_im = v_entry["im"]
        v_complex = complex(v_re, v_im)

        norton_v = v_norton[idx - 1]
        v_mag = abs(v_complex)
        v_ang_deg = math.degrees(np.angle(v_complex))

        n_mag = abs(norton_v)
        n_ang_deg = math.degrees(np.angle(norton_v))

        dmag = abs(v_mag - n_mag)
        dang = abs(v_ang_deg - n_ang_deg)

        assert dmag < 5e-4, f"Bus {bid} magnitude discrepancy {dmag} exceeds tolerance 5e-4"
        assert dang < 5e-3, f"Bus {bid} angle discrepancy {dang} deg exceeds tolerance 5e-3"

    # 2. Check complete engineering fields presence (Q4)
    assert "line_flows" in res.result
    assert "bus_injections" in res.result
    assert "ybus" in res.result
    assert "zbus" in res.result
    assert res.result["base_mva"] == 100.0

    # 3. Item (b): Generator P and Q
    # Line 6 is (5 -> 1)
    line6 = res.result["line_flows"]["6"]
    p_gen_mw = line6["p_from_mw"]
    q_gen_mvar = line6["q_from_mvar"]
    assert abs(p_gen_mw - 18.1758) < 0.05, f"Generator P mismatch: {p_gen_mw}"
    assert abs(q_gen_mvar - 12.8339) < 0.05, f"Generator Q mismatch: {q_gen_mvar}"

    # 4. Item (c): Motor current and power factor
    # Line 7 is (6 -> 3)
    line7 = res.result["line_flows"]["7"]
    i_motor_pu = line7["current_to_pu"]
    assert abs(i_motor_pu - 0.202274) < 1e-4, f"Motor current mismatch: {i_motor_pu}"

    # 5. Item (d): Real power absorbed by motor
    # p_to_mw of line 7 or -p_from_mw of line 7
    p_motor_absorbed_mw = line7["p_to_mw"]
    assert abs(p_motor_absorbed_mw - 18.1758) < 0.05, f"Motor P absorbed mismatch: {p_motor_absorbed_mw}"


@pytest.mark.asyncio
async def test_quiz_l3_degenerate_solution_rejected():
    """Verify that a degenerate collapsed network is rejected fail-closed with DEGENERATE_SOLUTION."""
    buses = [
        BusSpec(bus_id=1, bus_type="slack", voltage_magnitude=1.0, voltage_angle=0.0),
        BusSpec(bus_id=2, bus_type="pq", voltage_magnitude=1.0, voltage_angle=0.0, load_power_real=5.0, load_power_imag=2.0),
    ]
    lines = [
        LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, r1=0.1, x1=2.0),
    ]
    system_spec = SystemSpec(base_mva=100.0, buses=buses, lines=lines)
    req = StudyRequest(
        study_type="load_flow",
        system=system_spec,
        parameters={"tol": 1e-4, "max_iter": 50},
    )

    executor = StudyExecutor()
    res = await executor.execute(req)

    # Must NOT succeed with false confidence
    assert res.success is False
    assert res.result.get("converged") is False or "DEGENERATE_SOLUTION" in str(res.errors)
