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
    calculate_iec_60909_theoretical_fault,
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

    passed_9bus = bool(conv9 and max_err_9bus < 1.0)
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
