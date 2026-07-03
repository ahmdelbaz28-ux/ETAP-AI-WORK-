"""
Profile StateStore memory usage under load with 118-bus snapshots.

Measures:
1. Single snapshot memory footprint (bus states, GIS assets, switches, results)
2. Memory growth at 1, 10, 100, 500, 1000 snapshots
3. Deep copy overhead of get_current()
4. JSON serialization size vs in-memory size
5. Total projected memory at default max_versions=1000
"""

import sys
sys.path.insert(0, '.')

import time
import gc
import numpy as np

# ── Build 118-bus snapshot data ────────────────────────────────────────────

def _make_118_snapshot(version: int, variation: float = 0.01):
    """Create a realistic 118-bus StateSnapshot with GIS + SCADA + sim data."""
    from digital_twin.state_store import (
        StateSnapshot, BusState, SwitchState, TopologyState,
        GISAssetState, SimulationResults,
    )

    n_buses = 118
    n_switches = n_buses * 2
    n_gis_assets = n_buses * 3  # bus + line + transformer per electrical node

    # Electrical state
    bus_states = {}
    for i in range(n_buses):
        bid = f"BUS_{i:04d}"
        vm = 1.0 + variation * np.sin(i)
        va = 0.0 + variation * np.cos(i * 0.5) * 0.1
        bus_states[bid] = BusState(
            bus_id=bid,
            voltage_magnitude=round(vm + version * 0.0001, 6),
            voltage_angle=round(va, 6),
            load_power=complex(round(0.5 + 0.3 * np.sin(i * 0.3), 4),
                               round(0.2 + 0.1 * np.cos(i * 0.3), 4)),
            generation_power=complex(round(0.3 + 0.2 * np.sin(i * 0.5), 4),
                                     round(0.1 + 0.05 * np.cos(i * 0.5), 4)),
            bus_type="pq" if i > 8 else ("pv" if i > 0 else "slack"),  # NOSONAR — S3358: nested conditional; extract to named variable (tech debt)
        )

    # Switch states
    switch_states = {}
    for i in range(n_switches):
        sid = f"SW_{i:04d}"
        switch_states[sid] = SwitchState(
            switch_id=sid,
            is_closed=(i % 7 != 0),  # ~86% closed
            from_bus=f"BUS_{i % n_buses:04d}",
            to_bus=f"BUS_{(i + 1) % n_buses:04d}",
            trip_count=i % 5,
        )

    # Topology
    topology = TopologyState(
        connected_components=[["BUS_%04d" % j for j in range(0, n_buses, 3)]],
        energized_buses=[f"BUS_{i:04d}" for i in range(n_buses) if i % 5 != 0],
        de_energized_buses=[f"BUS_{i:04d}" for i in range(n_buses) if i % 5 == 0],
        section_buses={f"SECT_{k:02d}": [f"BUS_{i:04d}" for i in range(k * 5, min((k + 1) * 5, n_buses))]
                        for k in range((n_buses + 4) // 5)},
    )

    # GIS assets
    gis_assets = {}
    for i in range(n_gis_assets):
        aid = f"GIS_{i:05d}"
        gis_assets[aid] = GISAssetState(
            asset_id=aid,
            asset_type=["substation", "line", "transformer"][i % 3],
            electrical_id=f"BUS_{(i // 3) % n_buses:04d}",
            latitude=40.0 + 0.01 * (i % 100),
            longitude=-74.0 + 0.01 * (i % 100),
            zone_id=f"ZONE_{(i // 50) + 1}",
        )

    # Simulation results
    sim_results = SimulationResults(
        load_flow_converged=True,
        load_flow_iterations=4 + (version % 3),
        load_flow_bus_voltages={f"BUS_{i:04d}": complex(1.0 + 0.01 * np.sin(i), 0.01 * np.cos(i))
                                 for i in range(n_buses)},
        state_estimation_converged=True,
        state_estimation_bad_data=version % 10,
        fault_currents={f"BUS_{i:04d}": complex(5.0 + np.random.uniform(-1, 1), 2.0 + np.random.uniform(-0.5, 0.5))  # NOSONAR — S6711: numpy.random.Generator migration; API change required
                         for i in range(min(20, n_buses))},
        arc_flash_incident_energy={f"BUS_{i:04d}": round(1.0 + 0.5 * np.sin(i * 0.7), 3)
                                    for i in range(n_buses)},
        protection_coordination_ok=True,
    )

    snapshot = StateSnapshot(
        version=version,
        timestamp=time.time(),
        simulation_time=version * 0.1,
        gis_assets=gis_assets,
        gis_zones={f"ZONE_{z}": f"Zone {z} Description" for z in range(1, 5)},
        bus_states=bus_states,
        ybus_shape=(n_buses, n_buses),
        ybus_checksum=hash(version),
        switch_states=switch_states,
        topology=topology,
        scada_measurement_count=n_buses * 4,
        simulation_results=sim_results,
        validation_passed=True,
        validation_errors=[],
        source_event=f"simulation_step_{version}",
        correlation_id=f"corr_{version:06x}",
    )
    return snapshot


# ── Memory measurement helpers ─────────────────────────────────────────────

def get_rss_mb():
    """Get current process RSS in MB."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0

def measure_size(obj, _label=""):
    """Rough size estimate using sys.getsizeof recursively."""
    seen = set()
    def _size(o):
        if id(o) in seen:
            return 0
        seen.add(id(o))
        s = sys.getsizeof(o)
        if isinstance(o, dict):
            s += sum(_size(k) + _size(v) for k, v in o.items())
        elif isinstance(o, (list, tuple, set)):
            s += sum(_size(x) for x in o)
        elif hasattr(o, '__dict__'):
            s += _size(o.__dict__)
        elif hasattr(o, '__slots__'):
            s += sum(_size(getattr(o, slot, None)) for slot in o.__slots__ if hasattr(o, slot))
        return s
    return _size(obj)


# ── Measurements ───────────────────────────────────────────────────────────

print("=" * 72)
print("  StateStore Memory Profile — 118-Bus System")
print("=" * 72)

results = {}

# 1. Single snapshot memory
print("\n-- 1. Single Snapshot Memory Footprint ----------------------------")
snap = _make_118_snapshot(0)

# Object-level breakdown
from digital_twin.state_store import StateSnapshot, BusState, SwitchState, GISAssetState

snap_bytes = measure_size(snap)
bus_state_size = measure_size(BusState("BUS_TEST"))
switch_state_size = measure_size(SwitchState("SW_TEST"))
gis_asset_size = measure_size(GISAssetState("GIS_TEST"))

print(f"  BusState per bus:      {bus_state_size / 1024:.1f} KB")
print(f"  SwitchState per switch: {switch_state_size / 1024:.1f} KB")
print(f"  GISAssetState per asset: {gis_asset_size / 1024:.1f} KB")
print(f"  Snapshot (118 buses, 236 switches, 354 GIS):    {snap_bytes / 1024:.1f} KB")
print(f"  Snapshot JSON (to_dict):                        {len(snap.to_json()) / 1024:.1f} KB")

results["single_snapshot_size_kb"] = round(snap_bytes / 1024, 1)
results["single_snapshot_json_kb"] = round(len(snap.to_json()) / 1024, 1)

# 2. Memory growth with StateStore
print("\n-- 2. Memory Growth vs Snapshots ---------------------------------")

from digital_twin.state_store import StateStore

# Warm up garbage collector
gc.collect()

store = StateStore(max_versions=1000)
baseline_rss = get_rss_mb()

checkpoints = [1, 10, 100, 250, 500, 1000]
growth_results = []
last_rss = baseline_rss

for target in checkpoints:
    # Commit up to target
    current = store.get_current_version()
    for v in range(current + 1, target + 1):
        snap = _make_118_snapshot(v)
        store.commit(snap)

    gc.collect()
    time.sleep(0.1)
    current_rss = get_rss_mb()
    delta = current_rss - baseline_rss

    stats = store.get_statistics()
    growth_results.append({
        "snapshots": target,
        "rss_mb": round(current_rss, 2),
        "delta_mb": round(delta, 2),
        "delta_per_snapshot_kb": round(delta * 1024 / target, 1),
    })
    print(f"  {target:5d} snapshots | RSS={current_rss:7.2f} MB | delta={delta:7.2f} MB | {delta * 1024 / target:6.1f} KB/snap")

results["growth"] = growth_results
results["growth_per_snapshot_kb"] = round(
    growth_results[-1]["delta_mb"] * 1024 / checkpoints[-1], 1
)

# 3. Deep copy overhead of get_current()
print("\n-- 3. get_current() Deep Copy Overhead ---------------------------")

n_trials = 100
t0 = time.perf_counter()
for _ in range(n_trials):
    snap_copy = store.get_current()
t_copy = (time.perf_counter() - t0) / n_trials * 1000  # ms per copy

print(f"  get_current() avg: {t_copy:.3f} ms (n={n_trials})")
results["get_current_ms"] = round(t_copy, 3)

# 4. RSS at max_versions=1000 (current value) vs recommended values
print("\n-- 4. Projected Memory at Various max_versions --------------------")

per_snap_mb = growth_results[-1]["delta_mb"] / checkpoints[-1]
projections = []
for max_v in [50, 100, 250, 500, 1000]:
    projected_rss = per_snap_mb * max_v
    projections.append({
        "max_versions": max_v,
        "projected_rss_mb": round(projected_rss, 1),
        "projected_json_mb": round(snap_bytes * max_v / 1024 / 1024, 1),
    })
    print(f"  max_versions={max_v:5d} | projected RSS={projected_rss:6.1f} MB | JSON equivalent={snap_bytes * max_v / 1024 / 1024:.1f} MB")

results["projections"] = projections

# 5. Diff computation overhead
print("\n-- 5. Diff Computation Overhead ----------------------------------")

n_trials = 50
t0 = time.perf_counter()
for _ in range(n_trials):
    store.diff(1, store.get_current_version())
t_diff = (time.perf_counter() - t0) / n_trials * 1000
print(f"  diff(v1, v{store.get_current_version()}) avg: {t_diff:.3f} ms (n={n_trials})")
results["diff_ms"] = round(t_diff, 3)

# Cleanup
del store
gc.collect()

# ── Summary ────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("  SUMMARY")
print("=" * 72)
print(f"  Single 118-bus snapshot:                  {snap_bytes / 1024:>8.1f} KB in memory")
print(f"  Single 118-bus snapshot:                  {len(snap.to_json()) / 1024:>8.1f} KB as JSON")
print(f"  Memory per snapshot (RSS delta):          {growth_results[-1]['delta_per_snapshot_kb']:>8.1f} KB")
print(f"  get_current() deep copy:                  {t_copy:>8.3f} ms")
print(f"  diff(v1, v1000):                          {t_diff:>8.3f} ms")
print(f"  Projected at max_versions=1000:           {projections[-1]['projected_rss_mb']:>8.1f} MB")
print(f"  Projected at max_versions=100:            {projections[1]['projected_rss_mb']:>8.1f} MB")
print()
print("  Recommendation: Reduce max_versions from 1000 to 100")
print(f"  Savings at 100 versions: {projections[-1]['projected_rss_mb'] - projections[1]['projected_rss_mb']:.0f} MB RSS")
