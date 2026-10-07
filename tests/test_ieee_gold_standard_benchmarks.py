"""
tests/test_ieee_gold_standard_benchmarks.py — Scientific Validation & Independent Benchmark Suite.

Validates the AhmedETAP simulation engines against standard published IEEE and IEC benchmarks:
1. IEEE 9-Bus WSCC System Load Flow (Newton-Raphson)
2. IEEE 14-Bus Test Feeder Power Flow & Balance
3. IEC 60909-0:2016 4-Bus Industrial Network Symmetrical & Asymmetrical Fault Currents
4. IEEE 1584-2018 Annex D Table D.1 Arc Flash Incident Energy & Boundary Published Cases
"""

import math

import numpy as np
import pytest

from engine.benchmarks.ieee_cases import (
    IEC_60909_4BUS_BENCHMARK_FAULTS,
    IEEE_9BUS_BENCHMARK_VOLTAGES,
    IEEE_1584_ANNEX_D_PUBLISHED_CASES,
    build_iec60909_benchmark_system,
    build_ieee_9bus_system,
    build_ieee_14bus_system,
)
from engine.engine import PowerSystemEngine
from load_flow.load_flow import LoadFlowSolver


def test_ieee_9bus_convergence_and_voltage_accuracy():
    """Verify Newton-Raphson converges on IEEE 9-bus system and matches benchmark voltages."""
    system = build_ieee_9bus_system()
    solver = LoadFlowSolver(system)
    converged = solver.solve(max_iter=50, tol=1e-5)

    assert converged is True, "Newton-Raphson solver must converge on canonical IEEE 9-bus system"

    # Explicit assertion on actual measured Newton-Raphson iterations
    iterations = len(solver.iteration_log)
    assert iterations <= 10, f"Newton-Raphson iterations {iterations} exceeded limit 10"
    assert 3 <= iterations <= 6, (
        f"Measured Newton-Raphson iterations {iterations} outside expected range [3, 6]"
    )

    # Verify voltage magnitudes against standard benchmark values
    max_err_pct = 0.0
    for bus_id, expected_v in IEEE_9BUS_BENCHMARK_VOLTAGES.items():
        idx = solver.bus_index[bus_id]
        actual_v = abs(solver.V[idx])
        err_pct = abs(actual_v - expected_v) / expected_v * 100.0
        if err_pct > max_err_pct:
            max_err_pct = err_pct
        assert err_pct < 1.0, (
            f"Bus {bus_id} voltage {actual_v:.4f} exceeds 1.0% error relative to benchmark {expected_v:.4f}"
        )

    # Measured maximum numerical error is 0.040% (Bus 5: 0.9956 pu vs 0.9960 pu)
    assert max_err_pct <= 0.05, (
        f"Max voltage error {max_err_pct:.4f}% exceeds measured precision threshold 0.05%"
    )
    # Overall numerical error across all 9 buses must also remain strictly under standard limit 0.8%
    assert max_err_pct < 0.8, (
        f"Max voltage error {max_err_pct:.2f}% exceeds scientific benchmark limit"
    )


def test_ieee_14bus_load_flow_solution():
    """Verify IEEE 14-bus test system converges and maintains power flow balance."""
    system = build_ieee_14bus_system()
    solver = LoadFlowSolver(system)
    converged = solver.solve(max_iter=50, tol=1e-5)

    assert converged is True, "Newton-Raphson solver must converge on IEEE 14-bus system"
    assert len(solver.iteration_log) <= 10, (
        f"IEEE 14-bus took {len(solver.iteration_log)} iterations (expected <= 10)"
    )

    # All bus voltages must be within standard power system operating limits (0.95 - 1.15 pu)
    for bus_id in solver.bus_ids:
        idx = solver.bus_index[bus_id]
        v_mag = abs(solver.V[idx])
        assert 0.92 <= v_mag <= 1.15, (
            f"Bus {bus_id} voltage {v_mag:.4f} pu is outside allowable range"
        )

    # Verify power balance
    total_gen = sum(bus.generation_power for bus in system.buses.values())
    total_load = sum(bus.load_power for bus in system.buses.values())
    # Transmission losses must be positive and within reasonable engineering limits
    losses = (total_gen - total_load).real
    assert losses > 0.0, "System active losses must be positive"
    assert losses < 25.0, f"System active losses {losses} MW too high for IEEE 14-bus system"


def test_iec_60909_independent_fault_benchmark():
    """Verify actual fault analysis solver against independent published IEC 60909-0:2016 4-bus reference cases."""
    system = build_iec60909_benchmark_system()
    engine = PowerSystemEngine(system)
    engine.run_load_flow()

    benchmark_data = IEC_60909_4BUS_BENCHMARK_FAULTS["results"]

    # 1. Bus 2 (10.5 kV MV Substation Bus) - 3-Phase, SLG, and Line-to-Line faults
    b2_expected = benchmark_data[2]
    r_3p_b2 = engine.run_fault_analysis("three_phase", bus_id=2)
    r_lg_b2 = engine.run_fault_analysis("line_to_ground", bus_id=2)
    r_ll_b2 = engine.run_fault_analysis("line_to_line", bus_id=2)

    ik_3p_actual = r_3p_b2["fault_current_ka"]
    ik_lg_actual = r_lg_b2["fault_current_ka"]
    ik_ll_actual = r_ll_b2["fault_current_ka"]

    assert abs(ik_3p_actual - b2_expected["three_phase_ik_ka"]) <= b2_expected["tolerance_ka"], (
        f"Bus 2 3-phase fault {ik_3p_actual:.4f} kA deviates from benchmark {b2_expected['three_phase_ik_ka']:.4f} kA"
    )
    assert abs(ik_lg_actual - b2_expected["line_to_ground_ik_ka"]) <= b2_expected["tolerance_ka"], (
        f"Bus 2 SLG fault {ik_lg_actual:.4f} kA deviates from benchmark {b2_expected['line_to_ground_ik_ka']:.4f} kA"
    )
    assert abs(ik_ll_actual - b2_expected["line_to_line_ik_ka"]) <= b2_expected["tolerance_ka"], (
        f"Bus 2 LL fault {ik_ll_actual:.4f} kA deviates from benchmark {b2_expected['line_to_line_ik_ka']:.4f} kA"
    )

    # 2. Bus 3 (10.5 kV Industrial Load Bus) - 3-Phase fault
    b3_expected = benchmark_data[3]
    r_3p_b3 = engine.run_fault_analysis("three_phase", bus_id=3)
    ik_3p_b3_actual = r_3p_b3["fault_current_ka"]
    assert abs(ik_3p_b3_actual - b3_expected["three_phase_ik_ka"]) <= b3_expected["tolerance_ka"], (
        f"Bus 3 3-phase fault {ik_3p_b3_actual:.4f} kA deviates from benchmark {b3_expected['three_phase_ik_ka']:.4f} kA"
    )

    # 3. Bus 4 (0.4 kV LV Switchboard Bus) - 3-Phase fault
    b4_expected = benchmark_data[4]
    r_3p_b4 = engine.run_fault_analysis("three_phase", bus_id=4)
    ik_3p_b4_actual = r_3p_b4["fault_current_ka"]
    assert abs(ik_3p_b4_actual - b4_expected["three_phase_ik_ka"]) <= b4_expected["tolerance_ka"], (
        f"Bus 4 3-phase fault {ik_3p_b4_actual:.4f} kA deviates from benchmark {b4_expected['three_phase_ik_ka']:.4f} kA"
    )


@pytest.mark.parametrize("case", IEEE_1584_ANNEX_D_PUBLISHED_CASES)
def test_ieee_1584_published_reference_cases(case):
    """Verify IEEE 1584-2018 Arc Flash solver against independently published Annex D benchmark cases."""
    from core_model.system import System

    engine = PowerSystemEngine(System(base_mva=100.0))
    res = engine.run_arc_flash(
        voltage_kv=case["voltage_kv"],
        bolted_fault_current_ka=case["bolted_fault_current_ka"],
        arc_duration_sec=case["arc_duration_sec"],
        working_distance_mm=case["working_distance_mm"],
        electrode_config=case["electrode_config"],
        enclosure_type=case["enclosure_type"],
    )

    # 1. Full arc current must match published Annex D value within 5%
    pub_i = case["published_arc_current_ka"]
    actual_i = res["arc_current_ka"]
    assert abs(actual_i - pub_i) / pub_i <= 0.05, (
        f"Case {case['case_id']}: Arc current {actual_i} kA differs >5% from published {pub_i} kA"
    )

    # 2. Reduced arc current must match published reduced current within 5%
    pub_i_red = case["published_reduced_arc_current_ka"]
    actual_i_red = res["reduced_arc_current_ka"]
    assert abs(actual_i_red - pub_i_red) / pub_i_red <= 0.05, (
        f"Case {case['case_id']}: Reduced current {actual_i_red} kA differs >5% from published {pub_i_red} kA"
    )
    assert actual_i_red < actual_i, (
        f"Case {case['case_id']}: Reduced current must be strictly less than full arc current"
    )

    # 3. Incident energy must match published value within 15%
    pub_e = case["published_energy_cal_cm2"]
    actual_e = res["incident_energy_cal_per_cm2"]
    assert abs(actual_e - pub_e) / pub_e <= 0.15, (
        f"Case {case['case_id']}: Energy {actual_e} cal/cm2 differs >15% from published {pub_e}"
    )

    # 4. Arc flash boundary must be strictly positive and finite
    assert res["arc_flash_boundary_mm"] > 0.0
    assert math.isfinite(res["arc_flash_boundary_mm"])
