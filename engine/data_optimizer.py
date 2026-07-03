"""Memory-efficient data structures and optimization for large power system models."""

from __future__ import annotations

import gc
import logging
import math
import sys
import time
from contextlib import contextmanager

import numpy as np

logger = logging.getLogger(__name__)
from collections.abc import Callable
from typing import Any

from scipy.sparse import coo_matrix, csc_matrix, csr_matrix, issparse
from scipy.sparse.linalg import splu

from core_model.bus import Bus
from core_model.system import System


class SparseMatrixManager:
    """Efficient matrix operations for large systems using scipy.sparse."""

    def __init__(self, size_threshold: int = 100):
        self.size_threshold = size_threshold

    def to_sparse(self, dense: np.ndarray, fmt: str = "csr") -> Any:
        if dense.shape[0] <= self.size_threshold:
            return dense
        f = fmt.lower()
        if f == "csr":
            return csr_matrix(dense)
        if f == "csc":
            return csc_matrix(dense)
        if f == "coo":
            return coo_matrix(dense)
        raise ValueError(f"Unsupported sparse format: {fmt}")

    def to_dense(self, mat: Any) -> np.ndarray:
        return mat.toarray() if issparse(mat) else np.asarray(mat)
  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    def build_sparse_ybus(self, system: System, seq: str = "1") -> csr_matrix:  # NOSONAR — S3776: cognitive complexity; refactoring sprint
        bids = sorted(system.buses.keys())
        n = len(bids)
        bi = {b: i for i, b in enumerate(bids)}
        rows, cols, data = [], [], []
        for line in system.lines:
            i, j = bi[line.from_bus.bus_id], bi[line.to_bus.bus_id]
            z = line.get_impedance(seq)
            y = 1.0 / z if z else 0
            ys = line.get_shunt_admittance(seq) / 2.0
            rows += [i, j, i, j]
            cols += [i, j, j, i]
            data += [y + ys, y + ys, -y, -y]
        for xf in system.transformers:
            i, j = bi[xf.from_bus.bus_id], bi[xf.to_bus.bus_id]
            z = xf.get_impedance(seq)
            y = 1.0 / z if z else 0
            ys = xf.get_shunt_admittance(seq) / 2.0
            if not math.isclose(xf.tap_ratio, 1.0) or not math.isclose(xf.phase_shift, 0.0):
                a = xf.tap_ratio * np.exp(1j * xf.phase_shift)
                rows += [i, j, i, j]
                cols += [i, j, j, i]
                data += [y / abs(a) ** 2 + ys / 2.0, y + ys / 2.0, -y / np.conj(a), -y / a]
            else:
                rows += [i, j, i, j]
                cols += [i, j, j, i]
                data += [y + ys, y + ys, -y, -y]
        if seq != "1" or system._include_gen_impedance_pos:
            for gen in system.generators:
                i = bi[gen.bus.bus_id]
                zg = gen.get_impedance(seq)
                if zg and zg != 0j:
                    rows.append(i), cols.append(i), data.append(1.0 / zg)
        for load in system.loads:
            i = bi[load.bus.bus_id]
            if load.constant_impedance:
                zl = load.get_impedance(seq)
                if zl and zl != 0j and abs(zl) < 1e8:
                    rows.append(i), cols.append(i), data.append(1.0 / zl)
        return coo_matrix((data, (rows, cols)), shape=(n, n), dtype=complex).tocsr()
  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    def sparse_lu_solve(self, A: Any, b: np.ndarray) -> np.ndarray:  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
        if not issparse(A):
            A = csr_matrix(A)
        if A.shape[0] <= self.size_threshold:
            return np.linalg.solve(A.toarray(), b)
        return splu(A).solve(b)
  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    def sparse_factored_solve(self, A_factor: Any, b: np.ndarray) -> np.ndarray:  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
        return A_factor.solve(b)

    def estimate_memory_savings(self, dense_size: int, sparse_size: int) -> dict[str, Any]:
        if dense_size == 0:
            return {
                "dense_bytes": 0,
                "sparse_bytes": 0,
                "ratio": 1.0,
                "saved_bytes": 0,
                "saved_mb": 0.0,
                "percent_saved": 0.0,
            }
        saved = max(0, dense_size - sparse_size)
        return {
            "dense_bytes": dense_size,
            "sparse_bytes": sparse_size,
            "ratio": dense_size / sparse_size if sparse_size else float("inf"),
            "saved_bytes": saved,
            "saved_mb": saved / 1048576,
            "percent_saved": (1 - sparse_size / dense_size) * 100,
        }


BUS_DTYPE = np.dtype(
    [
        ("bus_id", np.int64),
        ("vmag", np.float64),
        ("vang", np.float64),
        ("pL", np.float64),
        ("qL", np.float64),
        ("pG", np.float64),
        ("qG", np.float64),
        ("kv", np.float64),
        ("bt", np.int8),
        ("qmin", np.float64),
        ("qmax", np.float64),
        ("vms", np.float64),
    ],
)
BTYPE_MAP = {"slack": 0, "pv": 1, "pq": 2}
BTYPE_REV = {0: "slack", 1: "pv", 2: "pq"}


class MemoryOptimizedSystem:
    """Memory-efficient system with __slots__. Uses ndarray for >=100 buses, dict otherwise."""

    __slots__ = (
        "base_mva",
        "bus_count",
        "lines",
        "transformers",
        "generators",
        "loads",
        "Ybus_seq",
        "_inc_gen_z",
        "_use_arr",
        "_ids",
        "_vmag",
        "_vang",
        "_pL",
        "_qL",
        "_pG",
        "_qG",
        "_kv",
        "_bt",
        "_qmin",
        "_qmax",
        "_vms",
        "_buses",
        "_sm",
    )
    THRESH = 100

    def __init__(self, original: System | None = None):
        self.base_mva = 100.0
        self.bus_count = 0
        self.lines = []
        self.transformers = []
        self.generators = []
        self.loads = []  # NOSONAR — S116: standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        self.Ybus_seq = {}
        self._inc_gen_z = False
        self._use_arr = False
        self._ids = self._vmag = self._vang = None  # NOSONAR — S116: standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        self._pL = self._qL = self._pG = self._qG = None
        self._kv = self._bt = self._qmin = self._qmax = self._vms = None
        self._buses = None
        self._sm = SparseMatrixManager()
        if original is not None:
            self.from_system(original)

    def from_system(self, system: System) -> MemoryOptimizedSystem:
        self.base_mva = system.base_mva
        self.lines = list(system.lines)
        self.transformers = list(system.transformers)
        self.generators = list(system.generators)
        self.loads = list(system.loads)
        self._inc_gen_z = system._include_gen_impedance_pos
        self.Ybus_seq = dict(system.Ybus_seq)
        n = len(system.buses)
        self.bus_count = n
        if n < self.THRESH:
            self._use_arr, self._buses = False, dict(system.buses)
            return self
        self._use_arr, self._buses = True, None
        bids = sorted(system.buses.keys())
        a = np.empty(n, dtype=BUS_DTYPE)
        for i, bid in enumerate(bids):
            b = system.buses[bid]
            a[i] = (
                bid,
                b.voltage_magnitude,
                b.voltage_angle,
                b.load_power.real,
                b.load_power.imag,
                b.generation_power.real,
                b.generation_power.imag,
                b.base_kv if b.base_kv else np.nan,
                BTYPE_MAP.get(b.bus_type, 2),
                b.q_min,
                b.q_max,
                b.voltage_magnitude_scheduled
                if b.voltage_magnitude_scheduled is not None
                else np.nan,
            )
        for attr, f in [
            ("_ids", "bus_id"),
            ("_vmag", "vmag"),
            ("_vang", "vang"),
            ("_pL", "pL"),
            ("_qL", "qL"),
            ("_pG", "pG"),
            ("_qG", "qG"),
            ("_kv", "kv"),
            ("_bt", "bt"),
            ("_qmin", "qmin"),
            ("_qmax", "qmax"),
            ("_vms", "vms"),
        ]:
            setattr(self, attr, a[f])
        for k in list(self.Ybus_seq.keys()):
            yb = self.Ybus_seq[k]
            if isinstance(yb, np.ndarray) and yb.shape[0] >= self.THRESH:
                self.Ybus_seq[k] = self._sm.to_sparse(yb)
        return self

    def _b_idx(self, bid: int) -> int:
        idx = np.where(self._ids == bid)[0]  # NOSONAR — S6729: np.where with single arg; kept for readability
        if len(idx) == 0:
            raise KeyError(f"Bus {bid} not found")
        return int(idx[0])

    def get_bus_data(self, bus_id: int) -> dict[str, Any]:
        if not self._use_arr:
            b = self._buses[bus_id]
            return {
                "bus_id": b.bus_id,
                "voltage_magnitude": b.voltage_magnitude,
                "voltage_angle": b.voltage_angle,
                "voltage": b.voltage,
                "load_power": b.load_power,
                "generation_power": b.generation_power,
                "base_kv": b.base_kv,
                "bus_type": b.bus_type,
                "q_min": b.q_min,
                "q_max": b.q_max,
            }
        i = self._b_idx(bus_id)
        return {
            "bus_id": int(self._ids[i]),
            "voltage_magnitude": float(self._vmag[i]),
            "voltage_angle": float(self._vang[i]),
            "voltage": self._vmag[i] * np.exp(1j * self._vang[i]),
            "load_power": complex(float(self._pL[i]), float(self._qL[i])),
            "generation_power": complex(float(self._pG[i]), float(self._qG[i])),
            "base_kv": None if np.isnan(self._kv[i]) else float(self._kv[i]),
            "bus_type": BTYPE_REV.get(int(self._bt[i]), "pq"),
            "q_min": float(self._qmin[i]),
            "q_max": float(self._qmax[i]),
        }

    def get_all_bus_voltages(self) -> np.ndarray:
        if not self._use_arr:
            bids = sorted(self._buses.keys())
            return np.array([self._buses[b].voltage for b in bids], dtype=complex)
        return self._vmag * np.exp(1j * self._vang)

    def get_ybus(self, seq: str = "1") -> Any:
        if seq not in self.Ybus_seq:
            self.Ybus_seq[seq] = self._sm.build_sparse_ybus(self.to_system(), seq)
        return self.Ybus_seq[seq]
  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    def to_system(self) -> System:  # NOSONAR — S3776: cognitive complexity; refactoring sprint
        s = System(base_mva=self.base_mva)
        if self._use_arr:
            for i in range(self.bus_count):
                bus = Bus(
                    bus_id=int(self._ids[i]),
                    voltage_magnitude=float(self._vmag[i]),
                    voltage_angle=float(self._vang[i]),
                    load_power=complex(float(self._pL[i]), float(self._qL[i])),
                    generation_power=complex(float(self._pG[i]), float(self._qG[i])),
                    base_kv=None if np.isnan(self._kv[i]) else float(self._kv[i]),
                    bus_type=BTYPE_REV.get(int(self._bt[i]), "pq"),
                    q_min=float(self._qmin[i]),
                    q_max=float(self._qmax[i]),
                )
                if not np.isnan(self._vms[i]):
                    bus.voltage_magnitude_scheduled = float(self._vms[i])
                s.add_bus(bus)
        else:
            for b in self._buses.values():
                s.add_bus(b)
        for item in self.lines:
            s.add_line(item)
        for item in self.transformers:
            s.add_transformer(item)
        for item in self.generators:
            s.add_generator(item)
        for item in self.loads:
            s.add_load(item)
        s._include_gen_impedance_pos = self._inc_gen_z
        for k, yb in self.Ybus_seq.items():
            s.Ybus_seq[k] = yb.toarray() if issparse(yb) else yb
        return s

    def get_bus_count(self) -> int:
        return self.bus_count

    def estimate_memory_usage(self) -> dict[str, Any]:
        base = sys.getsizeof(self)
        if self._use_arr:
            bus_mem = sum(
                getattr(self, a).nbytes
                for a in [
                    "_ids",
                    "_vmag",
                    "_vang",
                    "_pL",
                    "_qL",
                    "_pG",
                    "_qG",
                    "_kv",
                    "_bt",
                    "_qmin",
                    "_qmax",
                    "_vms",
                ]
                if getattr(self, a) is not None
            )
        else:
            bus_mem = sum(sys.getsizeof(b) for b in (self._buses or {}).values())
            bus_mem += sys.getsizeof(self._buses or {})
        extra = sum(
            sum(sys.getsizeof(x) for x in lst)
            for lst in [self.lines, self.transformers, self.generators, self.loads]
        )
        ym = 0
        for yb in self.Ybus_seq.values():
            if issparse(yb):
                ym += yb.data.nbytes + yb.indices.nbytes + yb.indptr.nbytes
            elif isinstance(yb, np.ndarray):
                ym += yb.nbytes
        total = base + bus_mem + extra + ym
        return {
            "total_bytes": total,
            "total_mb": total / 1048576,
            "bus_data_bytes": bus_mem,
            "ybus_bytes": ym,
            "storage_mode": "array" if self._use_arr else "dict",
        }


class BatchProcessor:
    """Process large systems in batches to manage memory usage."""

    def __init__(self, batch_size: int = 1000):
        self.batch_size = batch_size
        self._stats = {
            "total_items": 0,
            "num_batches": 0,
            "batch_sizes": [],
            "batch_times": [],
            "total_time": 0.0,
        }

    def process_buses(self, buses: dict | list, fn: Callable) -> list[Any]:
        return self._batch_process(
            list(buses.items()) if isinstance(buses, dict) else list(buses), fn,
        )

    def process_lines(self, lines: list, fn: Callable) -> list[Any]:
        return self._batch_process(list(lines), fn)

    def process_faults(
        self, buses: dict | list, ftypes: list[str], fn: Callable,
    ) -> list[Any]:
        items = list(buses.items()) if isinstance(buses, dict) else list(buses)
        return self._batch_process([(b, ft) for b in items for ft in ftypes], fn)

    def _batch_process(self, items: list, fn: Callable) -> list[Any]:
        results, n = [], len(items)
        s = self._stats
        s.update(total_items=n, num_batches=0)
        s["batch_sizes"].clear()
        s["batch_times"].clear()
        t0 = time.perf_counter()
        for i in range(0, n, self.batch_size):
            batch = items[i : i + self.batch_size]
            t1 = time.perf_counter()
            br = fn(batch)
            results.extend(br if isinstance(br, list) else [br])
            s["num_batches"] += 1
            s["batch_sizes"].append(len(batch))
            s["batch_times"].append(time.perf_counter() - t1)
        s["total_time"] = time.perf_counter() - t0
        return results

    def get_batch_statistics(self) -> dict[str, Any]:
        s = dict(self._stats)
        t, sz = s["batch_times"], s["batch_sizes"]
        s.update(
            avg_batch_time=float(np.mean(t)) if t else 0.0,
            max_batch_time=float(max(t)) if t else 0.0,
            min_batch_time=float(min(t)) if t else 0.0,
            avg_batch_size=float(np.mean(sz)) if sz else 0.0,
            throughput=s["total_items"] / s["total_time"] if s["total_time"] > 0 else 0.0,
        )
        return s


class DataCompressor:
    """Efficient data storage through numerical compression."""

    def __init__(self):
        self._orig = self._comp = 0

    def compress_results(self, results: dict[str, Any], precision: int = 6) -> dict[str, Any]:
        comp = {}
        self._orig = self._comp = 0
        for key, value in results.items():
            v = np.asarray(value)
            self._orig += v.nbytes
            if np.issubdtype(v.dtype, np.floating):
                comp[key] = np.round(v, decimals=precision).astype(np.float32)
            elif np.issubdtype(v.dtype, np.complexfloating):
                r = np.round(v, decimals=precision)
                c64 = np.empty(r.shape, dtype=np.complex64)
                c64.real, c64.imag = r.real.astype(np.float32), r.imag.astype(np.float32)
                comp[key] = c64
            else:
                # Copy the array to avoid sharing the reference with the
                # caller's data (np.asarray returns the same object when the
                # input is already a numpy array).
                comp[key] = v.copy() if isinstance(value, np.ndarray) else v
            self._comp += comp[key].nbytes if hasattr(comp[key], "nbytes") else v.nbytes
        comp["_precision"] = precision
        return comp

    def decompress_results(self, compressed: dict[str, Any]) -> dict[str, Any]:
        # _precision is intentionally stripped from the restored dict (it's
        # metadata about the compression, not a restorable array).
        restored = {}
        for k, v in compressed.items():
            if k == "_precision":
                continue
            v = np.asarray(v)
            if v.dtype == np.complex64:
                restored[k] = v.astype(np.complex128)
            elif v.dtype == np.float32:
                restored[k] = v.astype(np.float64)
            else:
                # Copy to avoid leaking the internal reference from the
                # compressed dict back to the caller.
                restored[k] = v.copy() if isinstance(v, np.ndarray) else v
        return restored

    def compress_system_state(self, system: System | MemoryOptimizedSystem) -> dict[str, Any]:
        s = system.to_system() if isinstance(system, MemoryOptimizedSystem) else system
        bids = sorted(s.buses.keys())
        vmag = np.array([s.buses[b].voltage_magnitude for b in bids], dtype=np.float32)
        vang = np.array([s.buses[b].voltage_angle for b in bids], dtype=np.float32)
        btypes = [s.buses[b].bus_type for b in bids]
        comp = {
            "base_mva": np.float32(system.base_mva),
            "bus_count": len(bids),
            "bus_ids": np.array(bids, dtype=np.int32),
            "bus_vmag": vmag,
            "bus_vang": vang,
            "bus_types": btypes,
            "lines": [
                {
                    "id": l.line_id,
                    "fr": l.from_bus.bus_id,
                    "to": l.to_bus.bus_id,
                    "z1r": l.z1.real,
                    "z1i": l.z1.imag,
                }
                for l in s.lines
            ],
            "transformers": [
                {
                    "id": t.transformer_id,
                    "fr": t.from_bus.bus_id,
                    "to": t.to_bus.bus_id,
                    "z1r": t.z1.real,
                    "z1i": t.z1.imag,
                    "tap": t.tap_ratio,
                    "ph": t.phase_shift,
                }
                for t in s.transformers
            ],
            "generators": [
                {
                    "id": g.generator_id,
                    "bus": g.bus.bus_id,
                    "v1r": g.internal_voltage.get("1", 0j).real,
                    "v1i": g.internal_voltage.get("1", 0j).imag,
                }
                for g in s.generators
            ],
        }
        self._orig = int(vmag.nbytes * 8 + vang.nbytes * 8 + sys.getsizeof(btypes) * 4)
        self._comp = int(vmag.nbytes + vang.nbytes + sys.getsizeof(btypes))
        return comp

    def decompress_system_state(self, compressed: dict[str, Any]) -> System:
        s = System(base_mva=float(compressed["base_mva"]))
        for i, bid in enumerate(compressed["bus_ids"]):
            s.add_bus(
                Bus(
                    bus_id=int(bid),
                    voltage_magnitude=float(compressed["bus_vmag"][i]),
                    voltage_angle=float(compressed["bus_vang"][i]),
                    bus_type=str(compressed["bus_types"][i]),
                ),
            )
        from core_model.generator import Generator
        from core_model.line import Line
        from core_model.transformer import Transformer

        for ld in compressed.get("lines", []):
            s.add_line(
                Line(
                    ld["id"], s.buses[ld["fr"]], s.buses[ld["to"]], z1=complex(ld["z1r"], ld["z1i"]),
                ),
            )
        for td in compressed.get("transformers", []):
            s.add_transformer(
                Transformer(
                    td["id"],
                    s.buses[td["fr"]],
                    s.buses[td["to"]],
                    z1=complex(td["z1r"], td["z1i"]),
                    tap_ratio=td["tap"],
                    phase_shift=td["ph"],
                ),
            )
        for gd in compressed.get("generators", []):
            s.add_generator(
                Generator(
                    gd["id"],
                    s.buses[gd["bus"]],
                    internal_voltage={"1": complex(gd["v1r"], gd["v1i"]), "2": 0j, "0": 0j},
                ),
            )
        return s

    def get_compression_ratio(self) -> dict[str, Any]:
        if self._orig == 0:
            return {"original_bytes": 0, "compressed_bytes": 0, "ratio": 1.0, "percent_saved": 0.0}
        return {
            "original_bytes": self._orig,
            "compressed_bytes": self._comp,
            "ratio": self._orig / self._comp if self._comp else float("inf"),
            "saved_bytes": self._orig - self._comp,
            "percent_saved": (1 - self._comp / self._orig) * 100,
        }


class PerformanceProfiler:
    """Profile and optimize computational performance."""

    def __init__(self):
        self._profiles = []

    def profile_function(self, fn: Callable, *args: Any, **kwargs: Any) -> dict[str, Any]:
        gc_was = gc.isenabled()
        gc.disable()
        has_tm = False
        try:
            import tracemalloc

            tracemalloc.start()
            has_tm = True
        except ImportError:
            logger.debug("tracemalloc not available; profiling without memory tracing")
        mb = self._get_mem()
        t0 = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - t0
            ma = self._get_mem()
            if has_tm:
                tracemalloc.stop()
            if gc_was:
                gc.enable()
        p = {
            "function": fn.__name__,
            "elapsed_seconds": elapsed,
            "memory_before_mb": mb,
            "memory_after_mb": ma,
            "memory_delta_mb": ma - mb,
            "result_type": type(result).__name__,
        }
        self._profiles.append(p)
        return p

    @contextmanager
    def profile_memory(self):
        try:
            import tracemalloc

            tracemalloc.start()
        except ImportError:
            logger.debug("tracemalloc not available; memory profiling skipped")
        before = self._get_mem()
        try:
            yield
        finally:
            after = self._get_mem()
            details = []
            try:
                import tracemalloc

                top = tracemalloc.take_snapshot().statistics("lineno")[:5]
                details = [(str(s.traceback)[:100], s.size) for s in top]
                tracemalloc.stop()
            except Exception:
                logger.debug("tracemalloc snapshot failed; memory profile details unavailable")
            self._profiles.append(
                {
                    "function": "memory_block",
                    "memory_before_mb": before,
                    "memory_after_mb": after,
                    "memory_delta_mb": after - before,
                    "tracemalloc_top": details,
                },
            )

    def _get_mem(self) -> float:
        try:
            import psutil

            return psutil.Process().memory_info().rss / 1048576
        except ImportError:
            logger.debug("psutil not available for memory measurement")
        try:
            import tracemalloc

            return sum(s.size for s in tracemalloc.take_snapshot().statistics("lineno")) / 1048576
        except Exception:
            return 0.0

    def get_profile_report(self) -> list[dict[str, Any]]:
        return list(self._profiles)

    def suggest_optimizations(self, profile_data: dict[str, Any] | None = None) -> list[str]:
        d = profile_data or (self._profiles[-1] if self._profiles else {})
        sug = []
        e, m = d.get("elapsed_seconds", 0), d.get("memory_delta_mb", 0)
        if e > 10:
            sug.append(f"'{d.get('function', '?')}' took {e:.1f}s. Use SparseMatrixManager.")
        if e > 60:
            sug.append("Over 60s. Use BatchProcessor.")
        if m > 500:
            sug.append(f"Memory +{m:.1f}MB. Use MemoryOptimizedSystem.")
        if m > 1000:
            sug.append("Over 1GB. Use DataCompressor for caching.")
        return sug or ["No significant optimization opportunities detected."]


class LargeSystemAdapter:
    """Adapts calculation engines for large power system models."""

    def __init__(self, system: System | MemoryOptimizedSystem, memory_limit_mb: int = 1024):
        self.memory_limit_mb = memory_limit_mb
        self.optimized_system = (
            MemoryOptimizedSystem(system) if isinstance(system, System) else system
        )
        self.sparse_manager = SparseMatrixManager()
        self.batch_processor = BatchProcessor()
        self._n = self.optimized_system.get_bus_count()
        self._large, self._xl = self._n >= 1000, self._n >= 10000

    def run_load_flow_optimized(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        p = params or {}
        Y = self.sparse_manager.build_sparse_ybus(
            self.optimized_system.to_system(), p.get("seq", "1"),
        )
        r = {
            "Ybus": Y,
            "Ybus_format": "sparse_csr",
            "bus_count": self._n,
            "memory_limit_mb": self.memory_limit_mb,
        }
        if self._large:
            r.update(
                LU_factor=splu(Y),
                solver="sparse_lu",
                initial_mismatch=Y.dot(self.optimized_system.get_all_bus_voltages())
                if self._n <= 5000
                else np.zeros(self._n, dtype=complex),
            )
        else:
            r.update(solver="dense", initial_voltages=self.optimized_system.get_all_bus_voltages())
        r["system_type"] = "xl" if self._xl else ("large" if self._large else "normal")  # NOSONAR — S3358: nested conditional; extract to named variable (tech debt)
        return r
  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    def run_fault_analysis_optimized(  # NOSONAR — S3776: cognitive complexity; refactoring sprint
        self, params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        p = params or {}
        sys_o = self.optimized_system.to_system()
        sys_o.build_sequence_networks(for_fault=True)
        sm = self.sparse_manager
        Y1, Y2, Y0 = [sm.build_sparse_ybus(sys_o, s) for s in ("1", "2", "0")]
        r = {"Ybus_pos": Y1, "Ybus_neg": Y2, "Ybus_zero": Y0}
        if self._large:
            r["Zbus_pos"] = sm.sparse_lu_solve(Y1, np.eye(self._n, dtype=complex))
            r["thevenin_method"] = "sparse_lu_complete" if self._xl else "sparse_lu"
        else:
            r["Zbus_pos"] = np.linalg.inv(Y1.toarray())
            r["thevenin_method"] = "dense_inverse"
        fb = p.get("fault_buses")
        if fb is not None:
            bl = list(fb.keys()) if isinstance(fb, dict) else list(fb)

            def ab(batch):
                br = []
                for e in batch:
                    bid, ft = (e[0], e[1]) if isinstance(e, tuple) else (e, "3ph")
                    zt = (
                        float(abs(r["Zbus_pos"][bid - 1, bid - 1]))
                        if isinstance(r.get("Zbus_pos"), np.ndarray)
                        else 1.0
                    )
                    br.append({"bus": bid, "fault_type": ft, "thevenin_impedance": zt})
                return br

            r["fault_analyses"] = self.batch_processor._batch_process(
                [(b, ft) for b in bl for ft in p.get("fault_types", ["3ph", "slg", "ll", "llg"])],
                ab,
            )
        return r

    def get_optimization_strategy(self) -> dict[str, Any]:
        n = self._n
        if n >= 10000:
            flags = {
                "use_sparse": True,
                "use_array_storage": True,
                "use_batch_processing": True,
                "use_compression": True,
                "need_memory_monitoring": True,
            }
            recs = [
                "Use SparseMatrixManager for all matrix operations.",  # NOSONAR — S1192: intentional repetition (audit constant)
                "Use MemoryOptimizedSystem array storage.",  # NOSONAR — S1192: string duplication; extract constant (tech debt)
                "Use BatchProcessor for fault analysis.",
                "Use DataCompressor for caching as float32/complex64.",
                "Consider iterative solvers (GMRES, BiCGSTAB).",
            ]
        elif n >= 1000:
            flags = {
                "use_sparse": True,
                "use_array_storage": True,
                "use_batch_processing": n > 5000,
                "use_compression": True,
                "need_memory_monitoring": n > 3000,
            }
            recs = [
                "Use SparseMatrixManager for Ybus.",
                "Use MemoryOptimizedSystem array storage.",
                "Use DataCompressor for result caching.",
            ]
        elif n >= 100:
            flags = {
                "use_sparse": True,
                "use_array_storage": True,
                "use_batch_processing": False,
                "use_compression": False,
                "need_memory_monitoring": False,
            }
            recs = ["Use SparseMatrixManager for Ybus.", "Use MemoryOptimizedSystem array storage."]
        else:
            flags = dict.fromkeys(
                [
                    "use_sparse",
                    "use_array_storage",
                    "use_batch_processing",
                    "use_compression",
                    "need_memory_monitoring",
                ],
                False,
            )
            recs = [
                "Small system. Standard System class is sufficient.",
                "Dense operations preferred.",
            ]
        return {
            "bus_count": n,
            "is_large": self._large,
            "is_xl": self._xl,
            "flags": flags,
            "recommendations": recs,
            "preferred_solver": "sparse_lu" if n >= 100 else "dense",
            "suggested_batch_size": min(10000, max(100, n // 10)),
        }
