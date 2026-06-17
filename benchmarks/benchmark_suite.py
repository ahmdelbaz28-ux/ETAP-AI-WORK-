"""
Benchmark Suite — AhmedETAP
===============================================
Runs 6 benchmarks covering the performance analysis findings.

Usage:
    python benchmarks/benchmark_suite.py [--quick]

Output:
    Prints a structured report to stdout.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Imports ────────────────────────────────────────────────────────────────
from engine.cache_manager import CacheStrategy, CalculationCache
from engine.sparse_solver import (
    SparseYBus,
    _build_dense_jacobian,
)
from load_flow.load_flow_solver_fixed import LoadFlowSolver

# ── Config ─────────────────────────────────────────────────────────────────

QUICK_MODE = "--quick" in sys.argv
IEEE_SIZES = [14, 30, 57] if QUICK_MODE else [14, 30, 57, 118]


# ═══════════════════════════════════════════════════════════════════════════
#  Benchmark 1: Jacobian build time — analytical vs finite-difference
# ═══════════════════════════════════════════════════════════════════════════

def benchmark_1_jacobian() -> Dict[str, Any]:
    """Compare analytical vs finite-difference Jacobian speed and accuracy."""
    print("\n" + "=" * 72)
    print("BENCHMARK 1: Jacobian Build -- Analytical vs Finite-Difference")
    print("=" * 72)

    results: Dict[str, Any] = {"systems": []}

    for n in IEEE_SIZES:
        buses, branches = SparseYBus._generate_synthetic_system(n)
        ybus = SparseYBus().build_sparse_ybus(buses, branches).toarray()
        pv = [i for i, b in enumerate(buses) if b.bus_type == "pv"]
        pq = [i for i, b in enumerate(buses) if b.bus_type == "pq"]
        n_pv = len(pv)
        n_pq = len(pq)
        n_uk = n_pv + 2 * n_pq

        V = np.array(
            [b.voltage_magnitude * np.exp(1j * b.voltage_angle) for b in buses],
            dtype=complex,
        )

        # ── Analytical Jacobian ──
        t0 = time.perf_counter()
        n_trials = 20 if QUICK_MODE else 100
        for _ in range(n_trials):
            J_ana = _build_dense_jacobian(V, ybus, pv, pq, n_uk)
            # Trigger PV→PQ switching simulation by adding a small perturbation
            V_test = V * (1.0 + 1e-8 * np.random.randn(len(V)))
            _ = _build_dense_jacobian(V_test, ybus, pv, pq, n_uk)
        t_ana = (time.perf_counter() - t0) / (n_trials * 2) * 1000  # ms

        # ── Finite-Difference Jacobian ──
        eps_theta = 1e-6
        eps_v = 1e-6

        def _fd_jacobian(V_trial):
            I = ybus @ V_trial
            S = V_trial * np.conj(I)
            dP = S.real
            dQ = S.imag
            m = np.zeros(n_uk)
            for k, i in enumerate(pv):
                m[k] = dP[i]
            for k, i in enumerate(pq):
                m[n_pv + k] = dP[i]
            for k, i in enumerate(pq):
                m[n_pv + n_pq + k] = dQ[i]
            return m

        base_m = _fd_jacobian(V)

        t0 = time.perf_counter()
        for _ in range(n_trials):
            J_fd = np.zeros((n_uk, n_uk))
            for col_k, i in enumerate(pv + pq):
                V_trial = V.copy()
                th = np.angle(V_trial[i])
                V_trial[i] = abs(V_trial[i]) * np.exp(1j * (th + eps_theta))
                J_fd[:, col_k] = (_fd_jacobian(V_trial) - base_m) / eps_theta
            for k, i in enumerate(pq):
                col_k = n_pv + n_pq + k
                V_trial = V.copy()
                vm = abs(V_trial[i])
                V_trial[i] = (vm + eps_v) * np.exp(1j * np.angle(V_trial[i]))
                J_fd[:, col_k] = (_fd_jacobian(V_trial) - base_m) / eps_v
        t_fd = (time.perf_counter() - t0) / n_trials * 1000  # ms

        # Compare
        diff = np.abs(J_ana - J_fd)
        max_diff = float(np.max(diff))
        mean_diff = float(np.mean(diff))

        entry = {
            "n_buses": n,
            "n_unknowns": n_uk,
            "analytical_ms": round(t_ana, 3),
            "fd_ms": round(t_fd, 3),
            "speedup": round(t_fd / t_ana, 2) if t_ana > 0 else None,
            "max_diff": f"{max_diff:.2e}",
            "mean_diff": f"{mean_diff:.2e}",
        }
        results["systems"].append(entry)

        print(f"  n={n:3d}  unknowns={n_uk:3d}  "
              f"analytical={t_ana:8.3f}ms  "
              f"FD={t_fd:8.3f}ms  "
              f"speedup={entry['speedup']:>5.1f}x  "
              f"|ana-FD|_max={max_diff:.2e}")

    return results


# ═══════════════════════════════════════════════════════════════════════════
#  Benchmark 2: Load flow solver — iterations & switching
# ═══════════════════════════════════════════════════════════════════════════

def benchmark_2_load_flow_solver() -> Dict[str, Any]:
    """Track iterations, Jacobian builds, and PV→PQ switches."""
    print("\n" + "=" * 72)
    print("BENCHMARK 2: Load Flow Solver -- Iterations and PV->PQ switching")
    print("=" * 72)

    results: Dict[str, Any] = {"systems": []}

    for n in IEEE_SIZES:
        buses, branches = SparseYBus._generate_synthetic_system(n)

        # Build a System object
        from core_model.bus import Bus
        from core_model.generator import Generator
        from core_model.line import Line
        from core_model.system import System

        sys_model = System(base_mva=100.0)
        bus_map = {}

        for b in buses:
            bus = Bus(
                bus_id=b.bus_id,
                voltage_magnitude=b.voltage_magnitude,
                voltage_angle=b.voltage_angle,
                load_power=complex(b.p_load, b.q_load),
                generation_power=complex(b.p_generation, b.q_generation),
                bus_type=b.bus_type,
                q_min=b.q_min,
                q_max=b.q_max,
            )
            sys_model.add_bus(bus)
            bus_map[b.bus_id] = bus

        for br in branches:
            line = Line(
                line_id=len(sys_model.lines) + 1,
                from_bus=bus_map[br.from_bus],
                to_bus=bus_map[br.to_bus],
                z1=br.impedance,
                z0=br.impedance,
                yshunt1=br.shunt_admittance,
                yshunt0=br.shunt_admittance,
            )
            sys_model.add_line(line)

        # Add generators at PV buses
        for b in buses:
            if b.bus_type == "pv":
                gen = Generator(
                    generator_id=b.bus_id,
                    bus=bus_map[b.bus_id],
                    internal_voltage={'1': complex(1.0, 0)},
                    impedance={'1': complex(0, 0.2)},
                )
                sys_model.add_generator(gen)

        sys_model.build_ybus(seq='1')

        # Solve with analytical Jacobian
        solver = LoadFlowSolver(sys_model)
        t0 = time.perf_counter()
        converged = solver.solve(max_iter=100, tol=1e-6)
        t_elapsed = time.perf_counter() - t0

        n_iter = len(solver.iteration_log)
        n_pv_switches = len(solver.switching_log)
        final_mis = solver.iteration_log[-1]["max_mismatch"] if solver.iteration_log else 0

        entry = {
            "n_buses": n,
            "converged": converged,
            "iterations": n_iter,
            "pv_pq_switches": n_pv_switches,
            "final_mismatch": f"{final_mis:.2e}",
            "time_sec": round(t_elapsed, 4),
            "ms_per_iter": round(t_elapsed / max(n_iter, 1) * 1000, 2),
        }
        results["systems"].append(entry)

        print(f"  n={n:3d}  converged={converged}  "
              f"iterations={n_iter:3d}  "
              f"PV→PQ={n_pv_switches}  "
              f"final_mismatch={final_mis:.2e}  "
              f"time={t_elapsed:.3f}s  "
              f"{entry['ms_per_iter']:.2f}ms/iter")

    return results


# ═══════════════════════════════════════════════════════════════════════════
#  Benchmark 3: Zbus computation — dense inversion vs LU factorization
# ═══════════════════════════════════════════════════════════════════════════

def benchmark_3_zbus() -> Dict[str, Any]:
    """Compare dense inversion vs LU factorization for Zbus computation."""
    print("\n" + "=" * 72)
    print("BENCHMARK 3: Zbus Computation -- Dense Inversion vs LU Factorisation")
    print("=" * 72)

    results: Dict[str, Any] = {"systems": []}

    try:
        from scipy.linalg import lu_factor, lu_solve
        HAS_SCIPY = True
    except ImportError:
        HAS_SCIPY = False
        print("  [scipy not available — LU benchmark skipped]")

    for n in IEEE_SIZES:
        # Create random Ybus
        np.random.seed(42)
        Y = np.random.randn(n, n) + 1j * np.random.randn(n, n)
        Y = Y @ Y.conj().T + np.eye(n) * 0.1  # Positive definite-ish
        np.fill_diagonal(Y, np.sum(np.abs(Y), axis=1) + 10)  # Diagonally dominant

        # ── Dense inversion ──
        t0 = time.perf_counter()
        Z_inv = np.linalg.inv(Y)
        t_dense = (time.perf_counter() - t0) * 1000  # ms

        # Verify accuracy: Z @ Y ≈ I
        accuracy_inv = float(np.max(np.abs(Z_inv @ Y - np.eye(n))))

        # ── LU factorisation ──
        t_lu = None
        accuracy_lu = None
        if HAS_SCIPY:
            # Factor once, then solve for each column (like Thevenin impedance)
            t0 = time.perf_counter()
            lu, piv = lu_factor(Y)
            t_factor = (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            Z_lu = np.zeros_like(Y)
            for k in range(n):
                e_k = np.zeros(n, dtype=complex)
                e_k[k] = 1.0
                Z_lu[:, k] = lu_solve((lu, piv), e_k)
            t_solve = (time.perf_counter() - t0) * 1000
            t_lu = round(t_factor + t_solve, 3)
            accuracy_lu = float(np.max(np.abs(Z_lu @ Y - np.eye(n))))

        entry = {
            "n_buses": n,
            "dense_inv_ms": round(t_dense, 2),
            "lu_total_ms": t_lu,
            "lu_factor_ms": round(t_factor, 2) if HAS_SCIPY else None,
            "lu_solve_ms": round(t_solve, 2) if HAS_SCIPY else None,
            "speedup": round(t_dense / t_lu, 2) if t_lu else None,
            "accuracy_dense": f"{accuracy_inv:.2e}",
            "accuracy_lu": f"{accuracy_lu:.2e}" if accuracy_lu else None,
            "memory_dense_mb": round(n * n * 16 / 1024 / 1024, 3),
        }
        results["systems"].append(entry)

        speedup_str = f"  speedup={entry['speedup']:.1f}x" if entry['speedup'] else ""
        print(f"  n={n:3d}  dense_inv={t_dense:9.2f}ms  "
              f"LU_total={t_lu or 0:9.2f}ms{speedup_str}"
              f"  |ZY-I|={accuracy_inv:.2e}")

    return results


# ═══════════════════════════════════════════════════════════════════════════
#  Benchmark 4: Cache hit rate simulation
# ═══════════════════════════════════════════════════════════════════════════

def benchmark_4_cache() -> Dict[str, Any]:
    """Simulate cache hit/miss with Zipfian workload (80/20 pattern)."""
    print("\n" + "=" * 72)
    print("BENCHMARK 4: Cache Hit Rate Simulation")
    print("=" * 72)

    results: Dict[str, Any] = {"scenarios": []}
    scenarios = [
        {"name": "LRU 50MB max_size", "max_mb": 50, "strategy": CacheStrategy.LRU},
        {"name": "LRU 200MB max_size", "max_mb": 200, "strategy": CacheStrategy.LRU},
        {"name": "LFU 50MB max_size", "max_mb": 50, "strategy": CacheStrategy.LFU},
    ]

    for sc in scenarios:
        cache = CalculationCache(
            max_size_mb=sc["max_mb"],
            strategy=sc["strategy"],
            default_ttl_seconds=3600,
        )

        # Simulate Zipfian popularity: 1000 unique keys, ~1KB values
        n_keys = 1000
        n_requests = 50000
        key_size = 1024  # bytes per value
        values = ["x" * key_size for _ in range(n_keys)]

        # Zipf-like: key 0 is most popular, key N-1 is least
        weights = np.array([1.0 / (k + 1) for k in range(n_keys)])
        weights /= weights.sum()

        # Warmup: set all keys
        for k in range(n_keys):
            cache.set(f"key:{k}", values[k], ttl_seconds=3600)

        t0 = time.perf_counter()
        rng = np.random.default_rng(42)
        selected = rng.choice(n_keys, size=n_requests, p=weights)
        for k in selected:
            cache.get(f"key:{k}")
        t_elapsed = time.perf_counter() - t0

        stats = cache.get_stats()
        ops_per_sec = n_requests / t_elapsed / 1000

        entry = {
            "scenario": sc["name"],
            "max_size_mb": sc["max_mb"],
            "strategy": sc["strategy"].value,
            "hit_rate_pct": stats["hit_rate"],
            "hits": stats["hits"],
            "misses": stats["misses"],
            "entries": stats["entries"],
            "size_mb": stats["size_mb"],
            "utilization_pct": stats["memory_usage"],
            "throughput_kops": round(ops_per_sec, 1),
        }
        results["scenarios"].append(entry)

        print(f"  {sc['name']:30s}  "
              f"hit_rate={entry['hit_rate_pct']:5.1f}%  "
              f"entries={entry['entries']:5d}  "
              f"size={entry['size_mb']:6.2f}MB  "
              f"util={entry['utilization_pct']:5.1f}%  "
              f"throughput={entry['throughput_kops']:5.1f}K ops/s")

    return results


# ═══════════════════════════════════════════════════════════════════════════
#  Benchmark 5: Native study latency distribution
# ═══════════════════════════════════════════════════════════════════════════

def benchmark_5_study_latency() -> Dict[str, Any]:
    """Measure P50/P95/P99 latency for native studies."""
    print("\n" + "=" * 72)
    print("BENCHMARK 5: Native Study Latency Distribution")
    print("=" * 72)

    results: Dict[str, Any] = {"studies": []}

    for n in IEEE_SIZES:
        buses, branches = SparseYBus._generate_synthetic_system(n)

        from core_model.bus import Bus
        from core_model.generator import Generator
        from core_model.line import Line
        from core_model.system import System

        sys_model = System(base_mva=100.0)
        bus_map = {}
        for b in buses:
            bus = Bus(
                bus_id=b.bus_id, voltage_magnitude=b.voltage_magnitude,
                voltage_angle=b.voltage_angle,
                load_power=complex(b.p_load, b.q_load),
                generation_power=complex(b.p_generation, b.q_generation),
                bus_type=b.bus_type, q_min=b.q_min, q_max=b.q_max,
            )
            sys_model.add_bus(bus)
            bus_map[b.bus_id] = bus
        for br in branches:
            line = Line(
                line_id=len(sys_model.lines) + 1,
                from_bus=bus_map[br.from_bus], to_bus=bus_map[br.to_bus],
                z1=br.impedance, z0=br.impedance,
                yshunt1=br.shunt_admittance, yshunt0=br.shunt_admittance,
            )
            sys_model.add_line(line)
        for b in buses:
            if b.bus_type == "pv":
                gen = Generator(generator_id=b.bus_id, bus=bus_map[b.bus_id], internal_voltage={'1': complex(1.0, 0)}, impedance={'1': complex(0, 0.2)})
                sys_model.add_generator(gen)

        sys_model.build_ybus(seq='1')
        sys_model.build_sequence_networks(for_fault=True)

        from engine.engine import PowerSystemEngine

        n_runs = 5 if QUICK_MODE else 10
        lf_latencies: List[float] = []
        fault_latencies: List[float] = []

        for run in range(n_runs):
            engine = PowerSystemEngine(sys_model)

            # Load flow
            t0 = time.perf_counter()
            result = engine.run_load_flow()
            lf_latencies.append(time.perf_counter() - t0)

            # Fault analysis
            fault_bus = list(sys_model.buses.keys())[0]
            t0 = time.perf_counter()
            engine.run_fault_analysis("three_phase", fault_bus)
            fault_latencies.append(time.perf_counter() - t0)

        def percentile(data: List[float], p: float) -> float:
            return float(np.percentile(data, p))

        entry = {
            "n_buses": n,
            "load_flow_ms_p50": round(percentile(lf_latencies, 50) * 1000, 2),
            "load_flow_ms_p95": round(percentile(lf_latencies, 95) * 1000, 2),
            "load_flow_ms_p99": round(percentile(lf_latencies, 99) * 1000, 2),
            "fault_ms_p50": round(percentile(fault_latencies, 50) * 1000, 2),
            "fault_ms_p95": round(percentile(fault_latencies, 95) * 1000, 2),
            "fault_ms_p99": round(percentile(fault_latencies, 99) * 1000, 2),
        }
        results["studies"].append(entry)

        print(f"  n={n:3d}  "
              f"LF P50={entry['load_flow_ms_p50']:6.1f}ms  "
              f"P95={entry['load_flow_ms_p95']:6.1f}ms  "
              f"P99={entry['load_flow_ms_p99']:6.1f}ms  |  "
              f"Fault P50={entry['fault_ms_p50']:6.1f}ms  "
              f"P95={entry['fault_ms_p95']:6.1f}ms  "
              f"P99={entry['fault_ms_p99']:6.1f}ms")

    return results


# ═══════════════════════════════════════════════════════════════════════════
#  Benchmark 6: Concurrent request throughput
# ═══════════════════════════════════════════════════════════════════════════

def benchmark_6_concurrent() -> Dict[str, Any]:
    """Measure throughput under concurrent load using thread pools."""
    print("\n" + "=" * 72)
    print("BENCHMARK 6: Concurrent Throughput")
    print("=" * 72)

    results: Dict[str, Any] = {"scenarios": []}

    # Build a single 30-bus system for all concurrent runs
    n_buses = 14 if QUICK_MODE else 30
    buses, branches = SparseYBus._generate_synthetic_system(n_buses)

    from core_model.bus import Bus
    from core_model.generator import Generator
    from core_model.line import Line
    from core_model.system import System

    sys_model = System(base_mva=100.0)
    bus_map = {}
    for b in buses:
        bus = Bus(
            bus_id=b.bus_id, voltage_magnitude=b.voltage_magnitude,
            voltage_angle=b.voltage_angle,
            load_power=complex(b.p_load, b.q_load),
            generation_power=complex(b.p_generation, b.q_generation),
            bus_type=b.bus_type, q_min=b.q_min, q_max=b.q_max,
        )
        sys_model.add_bus(bus)
        bus_map[b.bus_id] = bus
    for br in branches:
        line = Line(
            line_id=len(sys_model.lines) + 1,
            from_bus=bus_map[br.from_bus], to_bus=bus_map[br.to_bus],
            z1=br.impedance, z0=br.impedance,
            yshunt1=br.shunt_admittance, yshunt0=br.shunt_admittance,
        )
        sys_model.add_line(line)
    for b in buses:
        if b.bus_type == "pv":
            gen = Generator(generator_id=b.bus_id, bus=bus_map[b.bus_id], internal_voltage={'1': complex(1.0, 0)}, impedance={'1': complex(0, 0.2)})
            sys_model.add_generator(gen)
    sys_model.build_ybus(seq='1')

    # Pre-create engine once; each thread creates its own engine
    engine_class = None
    from engine.engine import PowerSystemEngine
    engine_class = PowerSystemEngine

    concurrency_levels = [4, 8] if QUICK_MODE else [2, 4, 8, 16]
    n_requests = 200 if QUICK_MODE else 500

    for n_workers in concurrency_levels:
        results_list: List[float] = []
        lock = threading.Lock()

        def worker():
            # Each thread creates its own engine
            engine = engine_class(sys_model)
            t0 = time.perf_counter()
            engine.run_load_flow()
            elapsed = time.perf_counter() - t0
            with lock:
                results_list.append(elapsed)

        t0 = time.perf_counter()
        threads = []
        for _ in range(n_workers):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        total_time = time.perf_counter() - t0

        latencies = np.array(results_list) * 1000  # ms
        throughput = n_workers / total_time

        entry = {
            "n_workers": n_workers,
            "n_requests": n_workers,
            "total_time_sec": round(total_time, 3),
            "throughput_req_per_sec": round(throughput, 1),
            "latency_ms_p50": round(float(np.percentile(latencies, 50)), 2),
            "latency_ms_p95": round(float(np.percentile(latencies, 95)), 2),
            "latency_ms_p99": round(float(np.percentile(latencies, 99)), 2),
        }
        results["scenarios"].append(entry)

        print(f"  workers={n_workers:2d}  "
              f"total={total_time:.3f}s  "
              f"throughput={throughput:5.1f} req/s  "
              f"P50={entry['latency_ms_p50']:7.2f}ms  "
              f"P95={entry['latency_ms_p95']:7.2f}ms  "
              f"P99={entry['latency_ms_p99']:7.2f}ms")

    return results


# ═══════════════════════════════════════════════════════════════════════════
#  Report generator
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class BenchmarkReport:
    jacobian: Dict[str, Any] = field(default_factory=dict)
    load_flow: Dict[str, Any] = field(default_factory=dict)
    zbus: Dict[str, Any] = field(default_factory=dict)
    cache: Dict[str, Any] = field(default_factory=dict)
    latency: Dict[str, Any] = field(default_factory=dict)
    concurrent: Dict[str, Any] = field(default_factory=dict)

    def print_summary(self) -> None:
        print("\n\n" + "#" * 72)
        print("#  BENCHMARK SUMMARY REPORT")
        print("#" * 72)

        # B1: Jacobian
        if self.jacobian:
            print("\n-- 1. Jacobian Build Time -------------------------------")
            print(f"  {'Buses':>5}  {'Analytical':>10}  {'FD':>10}  {'Speedup':>8}  {'|diff|_max':>12}")
            for s in self.jacobian.get("systems", []):
                print(f"  {s['n_buses']:5d}  {s['analytical_ms']:>10.3f}ms  "
                      f"{s['fd_ms']:>10.3f}ms  "
                      f"{s.get('speedup','N/A'):>8}  {s['max_diff']:>12}")

        # B2: Load flow
        if self.load_flow:
            print("\n-- 2. Load Flow Solver -----------------------------------")
            print(f"  {'Buses':>5}  {'Converged':>10}  {'Iters':>6}  {'PV→PQ':>6}  "
                  f"{'Final|m|':>10}  {'Time':>8}")
            for s in self.load_flow.get("systems", []):
                print(f"  {s['n_buses']:5d}  {str(s['converged']):>10}  "
                      f"{s['iterations']:6d}  {s['pv_pq_switches']:6d}  "
                      f"{s['final_mismatch']:>10}  {s['time_sec']:>8.3f}s")

        # B3: Zbus
        if self.zbus:
            print("\n-- 3. Zbus Computation -----------------------------------")
            print(f"  {'Buses':>5}  {'Dense Inv':>10}  {'LU Total':>10}  "
                  f"{'Speedup':>8}  {'Mem Dense':>10}")
            for s in self.zbus.get("systems", []):
                lu_str = f"{s['lu_total_ms']:>10.1f}ms" if s['lu_total_ms'] else "  N/A     "
                spd_str = f"{s.get('speedup','N/A'):>8}"
                print(f"  {s['n_buses']:5d}  {s['dense_inv_ms']:>10.1f}ms  "
                      f"{lu_str}  {spd_str}  "
                      f"{s['memory_dense_mb']:>10.2f}MB")

        # B4: Cache
        if self.cache:
            print("\n-- 4. Cache Hit Rate -------------------------------------")
            print(f"  {'Scenario':30s}  {'Hit Rate':>9}  {'Entries':>8}  "
                  f"{'Size':>8}  {'Util':>6}  {'Throughput':>11}")
            for s in self.cache.get("scenarios", []):
                print(f"  {s['scenario']:30s}  {s['hit_rate_pct']:>8.1f}%  "
                      f"{s['entries']:>8d}  {s['size_mb']:>8.2f}MB  "
                      f"{s['utilization_pct']:>5.1f}%  "
                      f"{s['throughput_kops']:>8.1f}K/s")

        # B5: Latency
        if self.latency:
            print("\n-- 5. Study Latency Distribution -------------------------")
            print(f"  {'Buses':>5}  {'LF P50':>8}  {'LF P95':>8}  {'LF P99':>8}  |"
                  f"  {'Fault P50':>8}  {'Fault P95':>8}  {'Fault P99':>8}")
            for s in self.latency.get("studies", []):
                print(f"  {s['n_buses']:5d}  {s['load_flow_ms_p50']:>7.1f}ms  "
                      f"{s['load_flow_ms_p95']:>7.1f}ms  {s['load_flow_ms_p99']:>7.1f}ms  |"
                      f"  {s['fault_ms_p50']:>7.1f}ms  {s['fault_ms_p95']:>7.1f}ms  "
                      f"{s['fault_ms_p99']:>7.1f}ms")

        # B6: Concurrent
        if self.concurrent:
            print("\n-- 6. Concurrent Throughput ------------------------------")
            print(f"  {'Workers':>8}  {'Total':>8}  {'Throughput':>10}  "
                  f"{'P50':>8}  {'P95':>8}  {'P99':>8}")
            for s in self.concurrent.get("scenarios", []):
                print(f"  {s['n_workers']:>8d}  {s['total_time_sec']:>8.3f}s  "
                      f"{s['throughput_req_per_sec']:>8.1f} req/s  "
                      f"{s['latency_ms_p50']:>7.1f}ms  {s['latency_ms_p95']:>7.1f}ms  "
                      f"{s['latency_ms_p99']:>7.1f}ms")

        # Recommendations
        print("\n-- Key Recommendations ------------------------------------")
        jac = self.jacobian.get("systems", [])
        if jac:
            avg_spd = np.mean([s.get("speedup", 0) or 0 for s in jac])
            print(f"  • Analytical Jacobian: ~{avg_spd:.0f}x faster than FD across all sizes")

        zb = self.zbus.get("systems", [])
        if zb:
            avg_zspd = np.mean([s.get("speedup", 0) or 0 for s in zb if s.get("speedup")])
            print(f"  • LU factorisation: ~{avg_zspd:.0f}x faster than dense inversion for Zbus")

        ca = self.cache.get("scenarios", [])
        if ca:
            best_hit = max(s["hit_rate_pct"] for s in ca)
            print(f"  • Cache hit rate: {best_hit:.1f}% best case (Zipfian workload)")


# ═══════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    print("+" + "-" * 70 + "+")
    print("|  AhmedETAP -- Benchmark Suite")
    print(f"|  Mode: {'QUICK' if QUICK_MODE else 'FULL'}")
    print(f"|  System sizes: {IEEE_SIZES}")
    print("+" + "-" * 70 + "+")

    report = BenchmarkReport()

    try:
        report.jacobian = benchmark_1_jacobian()
    except Exception as e:
        print(f"  [B1 ERROR: {e}]")
        import traceback; traceback.print_exc()

    try:
        report.load_flow = benchmark_2_load_flow_solver()
    except Exception as e:
        print(f"  [B2 ERROR: {e}]")
        import traceback; traceback.print_exc()

    try:
        report.zbus = benchmark_3_zbus()
    except Exception as e:
        print(f"  [B3 ERROR: {e}]")
        import traceback; traceback.print_exc()

    try:
        report.cache = benchmark_4_cache()
    except Exception as e:
        print(f"  [B4 ERROR: {e}]")
        import traceback; traceback.print_exc()

    try:
        report.latency = benchmark_5_study_latency()
    except Exception as e:
        print(f"  [B5 ERROR: {e}]")
        import traceback; traceback.print_exc()

    try:
        report.concurrent = benchmark_6_concurrent()
    except Exception as e:
        print(f"  [B6 ERROR: {e}]")
        import traceback; traceback.print_exc()

    report.print_summary()

    # Save JSON report
    report_path = "benchmarks/benchmark-report.json"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        json.dump({
            "jacobian": report.jacobian,
            "load_flow": report.load_flow,
            "zbus": report.zbus,
            "cache": report.cache,
            "latency": report.latency,
            "concurrent": report.concurrent,
        }, f, indent=2, default=str)
    print(f"\n  Report saved to {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
