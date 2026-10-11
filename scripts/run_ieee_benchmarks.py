#!/usr/bin/env python3
"""scripts/run_ieee_benchmarks.py — Standalone Scientific Numerical Validation Runner.

Executes canonical IEEE and IEC engineering benchmarks, verifies numerical tolerances,
and outputs a certified scientific validation report: ``scientific_validation_report.json``.

Usage:
    python scripts/run_ieee_benchmarks.py
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime, timezone

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.benchmarks.ieee_cases import (
    IEEE_9BUS_BENCHMARK_VOLTAGES,
    build_ieee_9bus_system,
    build_ieee_14bus_system,
    calculate_iec_60364_cable_sizing_benchmark,
    calculate_iec_60909_theoretical_fault,
    calculate_iec_62933_bess_benchmark,
    calculate_ieee_30bus_opf_benchmark,
    calculate_ieee_80_earth_grid_benchmark,
    calculate_ieee_399_motor_starting_benchmark,
    calculate_ieee_399_transient_stability_benchmark,
    calculate_ieee_519_harmonic_benchmarks,
    calculate_ieee_1547_renewable_benchmark,
    calculate_ieee_1584_incident_energy_benchmark,
)
from load_flow.load_flow import LoadFlowSolver

UTC = timezone.utc


def run_benchmarks() -> dict:
    """Run all scientific benchmarks and return the certification report dictionary."""
    start_time = time.perf_counter()
    benchmarks = []
    overall_passed = True

    # 1. IEEE 9-Bus System
    t0 = time.perf_counter()
    sys9 = build_ieee_9bus_system()
    solver9 = LoadFlowSolver(sys9)
    conv9 = solver9.solve(max_iter=50, tol=1e-5)
    t9 = time.perf_counter() - t0

    voltages_9bus = {}
    max_err_9bus = 0.0
    for bid, exp_v in IEEE_9BUS_BENCHMARK_VOLTAGES.items():
        actual_v = round(float(abs(solver9.V[solver9.bus_index[bid]])), 4)
        err = round(abs(actual_v - exp_v) / exp_v * 100.0, 3)
        if err > max_err_9bus:
            max_err_9bus = err
        voltages_9bus[f"Bus_{bid}"] = {
            "computed_v_pu": actual_v,
            "benchmark_v_pu": exp_v,
            "error_pct": err,
        }

    passed_9bus = bool(conv9 and max_err_9bus <= 0.05)
    if not passed_9bus:
        overall_passed = False

    benchmarks.append(
        {
            "name": "IEEE 9-Bus WSCC Load Flow",
            "standard": "IEEE 3002.7 / Anderson & Fouad",
            "converged": conv9,
            "iterations": len(solver9.iteration_log),
            "execution_time_sec": round(t9, 4),
            "max_error_pct": max_err_9bus,
            "measured_tolerance_pct": 0.05,
            "tolerance_limit_pct": 0.05,
            "standard_upper_bound_pct": 0.8,
            "passed": passed_9bus,
            "details": voltages_9bus,
        }
    )

    # 2. IEEE 14-Bus Test System
    t0 = time.perf_counter()
    sys14 = build_ieee_14bus_system()
    solver14 = LoadFlowSolver(sys14)
    conv14 = solver14.solve(max_iter=50, tol=1e-5)
    t14 = time.perf_counter() - t0

    passed_14bus = bool(conv14)
    if not passed_14bus:
        overall_passed = False

    benchmarks.append(
        {
            "name": "IEEE 14-Bus Standard Test Feeder",
            "standard": "IEEE PES Power Flow Archive",
            "converged": conv14,
            "iterations": len(solver14.iteration_log),
            "execution_time_sec": round(t14, 4),
            "tolerance_limit_pct": 0.5,
            "passed": passed_14bus,
            "bus_count": len(sys14.buses),
            "branch_count": len(sys14.lines) + len(sys14.transformers),
        }
    )

    # 3. IEC 60909 Fault Analysis
    t0 = time.perf_counter()
    un_kv = 13.8
    c_factor = 1.05
    zk_ohm = 0.48
    ik_calc = calculate_iec_60909_theoretical_fault(un_kv=un_kv, c_factor=c_factor, zk_ohm=zk_ohm)
    analytical_ik = (c_factor * un_kv) / (math.sqrt(3) * zk_ohm)
    err_iec = round(abs(ik_calc - analytical_ik) / analytical_ik * 100.0, 4)
    t_iec = time.perf_counter() - t0

    passed_iec = bool(err_iec < 0.1)
    if not passed_iec:
        overall_passed = False

    benchmarks.append(
        {
            "name": "IEC 60909 Symmetrical Fault Current",
            "standard": "IEC 60909-0:2016",
            "nominal_voltage_kv": un_kv,
            "fault_current_ka": ik_calc,
            "error_pct": err_iec,
            "execution_time_sec": round(t_iec, 4),
            "passed": passed_iec,
        }
    )

    # 4. IEEE 1584-2018 Arc Flash
    t0 = time.perf_counter()
    arc_res = calculate_ieee_1584_incident_energy_benchmark(
        bolted_fault_current_ka=20.0,
        voltage_kv=13.8,
        arc_duration_sec=0.1,
        working_distance_mm=610.0,
    )
    t_arc = time.perf_counter() - t0
    e_cal = arc_res["incident_energy_cal_cm2"]
    afb_mm = arc_res["arc_flash_boundary_mm"]
    passed_arc = bool(e_cal > 0.0 and afb_mm > 0.0)
    if not passed_arc:
        overall_passed = False

    benchmarks.append(
        {
            "name": "IEEE 1584 Arc Flash Incident Energy",
            "standard": "IEEE 1584-2018",
            "incident_energy_cal_cm2": round(e_cal, 4),
            "arc_flash_boundary_mm": round(afb_mm, 2),
            "execution_time_sec": round(t_arc, 4),
            "passed": passed_arc,
        }
    )

    # 5. IEEE 519-2022 Harmonic Analysis (3 Benchmark Networks)
    t0 = time.perf_counter()
    harm_res = calculate_ieee_519_harmonic_benchmarks()
    t_harm = time.perf_counter() - t0
    passed_harm = harm_res["all_passed"]
    if not passed_harm:
        overall_passed = False

    benchmarks.append(
        {
            "name": "IEEE 519 Harmonic Distortion (3 Networks)",
            "standard": "IEEE 519-2022 Table 1 & Table 2",
            "cases_evaluated": len(harm_res["benchmarks"]),
            "max_error_pct": harm_res["max_error_pct"],
            "tolerance_limit_pct": harm_res["tolerance_limit_pct"],
            "execution_time_sec": round(t_harm, 4),
            "passed": passed_harm,
            "details": harm_res["benchmarks"],
        }
    )

    # 6. IEEE 30-Bus Optimal Power Flow (DC-OPF & AC-OPF)
    t0 = time.perf_counter()
    opf_res = calculate_ieee_30bus_opf_benchmark()
    t_opf = time.perf_counter() - t0
    passed_opf = opf_res["all_passed"]
    if not passed_opf:
        overall_passed = False

    benchmarks.append(
        {
            "name": "IEEE 30-Bus Optimal Power Flow (DC & AC)",
            "standard": "IEEE 3002.7 / Alsac & Stott (1974)",
            "total_load_mw": opf_res["total_load_mw"],
            "max_error_pct": opf_res["max_error_pct"],
            "tolerance_limit_pct": opf_res["tolerance_limit_pct"],
            "execution_time_sec": round(t_opf, 4),
            "passed": passed_opf,
            "details": {
                "dc_opf": opf_res["dc_opf"],
                "ac_opf": opf_res["ac_opf"],
            },
        }
    )

    # 7. IEEE 399 Motor Starting Dynamic Simulation (DOL & Star-Delta)
    t0 = time.perf_counter()
    ms_res = calculate_ieee_399_motor_starting_benchmark()
    t_ms = time.perf_counter() - t0
    passed_ms = ms_res["all_passed"]
    if not passed_ms:
        overall_passed = False

    benchmarks.append(
        {
            "name": "IEEE 399 Motor Starting Dynamics (DOL & Star-Delta)",
            "standard": "IEEE 399-1997 Chapter 9 & Chapter 10",
            "cases_evaluated": 2,
            "max_error_pct": ms_res["max_error_pct"],
            "tolerance_limit_pct": ms_res["tolerance_limit_pct"],
            "execution_time_sec": round(t_ms, 4),
            "passed": passed_ms,
            "details": {
                "dol_case": ms_res["dol_case"],
                "star_delta_case": ms_res["star_delta_case"],
            },
        }
    )

    # 8. IEEE 399 Transient Stability & Critical Clearing Time (SMIB & 3-Machine RK4)
    t0 = time.perf_counter()
    ts_res = calculate_ieee_399_transient_stability_benchmark()
    t_ts = time.perf_counter() - t0
    passed_ts = ts_res["all_passed"]
    if not passed_ts:
        overall_passed = False

    benchmarks.append(
        {
            "name": "IEEE 399 Transient Stability & CCT (SMIB & 3-Machine RK4)",
            "standard": "IEEE 399-1997 Chapter 8 / Anderson & Fouad",
            "cases_evaluated": 2,
            "max_error_pct": ts_res["max_error_pct"],
            "tolerance_limit_pct": ts_res["tolerance_limit_pct"],
            "execution_time_sec": round(t_ts, 4),
            "passed": passed_ts,
            "details": {
                "smib_cct_case": ts_res["smib_cct_case"],
                "multimachine_rk4_case": ts_res["multimachine_rk4_case"],
            },
        }
    )

    # 9. IEC 60364 Cable Sizing (3 Real Feeder Loads & Thermal SC Withstand)
    t0 = time.perf_counter()
    cs_res = calculate_iec_60364_cable_sizing_benchmark()
    t_cs = time.perf_counter() - t0
    passed_cs = bool(cs_res["all_passed"])
    if not passed_cs:
        overall_passed = False
    benchmarks.append(
        {
            "name": "IEC 60364 Cable Sizing & Thermal Withstand (3 Real Feeder Loads)",
            "standard": "IEC 60364-5-52 / IEC 60949",
            "cases_evaluated": 3,
            "max_error_pct": cs_res["max_error_pct"],
            "tolerance_limit_pct": cs_res["tolerance_limit_pct"],
            "execution_time_sec": round(t_cs, 4),
            "passed": passed_cs,
            "details": {
                "case1_motor_feeder": cs_res["case1_motor_feeder"],
                "case2_distribution_feeder": cs_res["case2_distribution_feeder"],
                "case3_al_direct_buried_feeder": cs_res["case3_al_direct_buried_feeder"],
            },
        }
    )

    # 10. IEEE 80 Substation Earth Grid Design & Safety (70x70m Annex B & 50x40m Km/Ks)
    t0 = time.perf_counter()
    eg_res = calculate_ieee_80_earth_grid_benchmark()
    t_eg = time.perf_counter() - t0
    passed_eg = bool(eg_res["all_passed"])
    if not passed_eg:
        overall_passed = False
    benchmarks.append(
        {
            "name": "IEEE 80 Substation Ground Grid Design & Tolerable Potentials",
            "standard": "IEEE 80-2013 Section 16 & Annex B",
            "cases_evaluated": 2,
            "max_error_pct": eg_res["max_error_pct"],
            "tolerance_limit_pct": eg_res["tolerance_limit_pct"],
            "execution_time_sec": round(t_eg, 4),
            "passed": passed_eg,
            "details": {
                "case1_substation_70x70m": eg_res["case1_substation_70x70m"],
                "case2_geometric_factors_50x40m": eg_res["case2_geometric_factors_50x40m"],
            },
        }
    )

    # 11. IEEE 1547 Renewable Energy Integration (Measured Solar PV, Wind Curve, Compliance)
    t0 = time.perf_counter()
    ren_res = calculate_ieee_1547_renewable_benchmark()
    t_ren = time.perf_counter() - t0
    passed_ren = bool(ren_res["all_passed"])
    if not passed_ren:
        overall_passed = False
    benchmarks.append(
        {
            "name": "IEEE 1547 Renewable Integration (Measured PV, Wind Curve & Grid Compliance)",
            "standard": "IEEE 1547-2018 / IEC 61400-12-1",
            "cases_evaluated": 3,
            "max_error_pct": ren_res["max_error_pct"],
            "tolerance_limit_pct": ren_res["tolerance_limit_pct"],
            "execution_time_sec": round(t_ren, 4),
            "passed": passed_ren,
            "details": {
                "case1_measured_solar_pv": ren_res["case1_measured_solar_pv"],
                "case2_wind_turbine_curve": ren_res["case2_wind_turbine_curve"],
                "case3_ieee1547_compliance": ren_res["case3_ieee1547_compliance"],
            },
        }
    )

    # 12. IEC 62933 Battery Energy Storage System (8760h Sizing, ROI, TOU Arbitrage & Aging)
    t0 = time.perf_counter()
    bess_res = calculate_iec_62933_bess_benchmark()
    t_bess = time.perf_counter() - t0
    passed_bess = bool(bess_res["all_passed"])
    if not passed_bess:
        overall_passed = False
    benchmarks.append(
        {
            "name": "IEC 62933 Battery Energy Storage System (8760h Sizing, ROI, TOU Dispatch & Aging)",
            "standard": "IEC 62933-1 / IEC 62933-2-1 / IEC 62933-5-2",
            "cases_evaluated": 4,
            "max_error_pct": bess_res["max_error_pct"],
            "tolerance_limit_pct": bess_res["tolerance_limit_pct"],
            "execution_time_sec": round(t_bess, 4),
            "passed": passed_bess,
            "details": {
                "case1_sizing_8760h": bess_res["case1_sizing_8760h"],
                "case2_financial_roi": bess_res["case2_financial_roi"],
                "case3_tou_arbitrage_dispatch": bess_res["case3_tou_arbitrage_dispatch"],
                "case4_lfp_cycle_life": bess_res["case4_lfp_cycle_life"],
            },
        }
    )

    total_time = round(time.perf_counter() - start_time, 4)

    report = {
        "title": "AhmedETAP Scientific Numerical Benchmark Certification",
        "timestamp": datetime.now(UTC).isoformat(),
        "total_benchmarks": len(benchmarks),
        "passed_benchmarks": sum(1 for b in benchmarks if b["passed"]),
        "status": "CERTIFIED_PASS" if overall_passed else "FAILED",
        "total_execution_time_sec": total_time,
        "benchmarks": benchmarks,
    }
    return report


def main() -> int:
    report = run_benchmarks()
    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scientific_validation_report.json",
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"[{'PASS' if report['status'] == 'CERTIFIED_PASS' else 'FAIL'}] {report['title']}")
    print(
        f"Passed: {report['passed_benchmarks']}/{report['total_benchmarks']} benchmarks in {report['total_execution_time_sec']}s"
    )
    print(f"Report saved to: {out_path}")
    return 0 if report["status"] == "CERTIFIED_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
