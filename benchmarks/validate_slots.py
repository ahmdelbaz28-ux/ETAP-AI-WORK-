import math  # added for S1244 float-equality fix
"""Validate __slots__ addition to core_model classes.

Checks:
1. All 6 files compile
2. __slots__ defined correctly on each class
3. Memory savings vs dict-based objects
4. Basic instantiation and attribute access works
"""

import sys
sys.path.insert(0, '.')

import gc
import numpy as np

# ── 1. Syntax checks ──────────────────────────────────────────────────────
print("=" * 60)
print("1. SYNTAX / COMPILE CHECKS")
print("=" * 60)
files = [
    'core_model/bus.py',
    'core_model/line.py',
    'core_model/generator.py',
    'core_model/load.py',
    'core_model/transformer.py',
    'core_model/system.py',
]
import py_compile
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"  {f:40s} OK")
    except py_compile.PyCompileError as e:
        print(f"  {f:40s} FAIL: {e}")
        sys.exit(1)

# ── 2. Verify __slots__ definitions ────────────────────────────────────────
print("\n" + "=" * 60)
print("2. __slots__ VERIFICATION")
print("=" * 60)

from core_model.bus import Bus
from core_model.line import Line
from core_model.generator import Generator
from core_model.load import Load
from core_model.transformer import Transformer
from core_model.system import System

classes = [
    ('Bus', Bus, ('bus_id', 'voltage_magnitude', 'voltage_angle')),
    ('Line', Line, ('line_id', 'from_bus', 'to_bus', 'z1')),
    ('Generator', Generator, ('generator_id', 'bus', 'internal_voltage')),
    ('Load', Load, ('load_id', 'bus', 'load_power')),
    ('Transformer', Transformer, ('transformer_id', 'from_bus', 'to_bus')),
    ('System', System, ('base_mva', 'buses', 'lines')),
]
for name, cls, expected in classes:
    slots = getattr(cls, '__slots__', ())
    for attr in expected:
        assert attr in slots, f"{name} missing slot '{attr}'"
    # Verify instances do NOT have __dict__ (that's the whole point of __slots__)
    instance = cls.__new__(cls)
    assert not hasattr(instance, '__dict__'), f"{name} instance has __dict__ (should have only __slots__)"
    print(f"  {name:15s} __slots__ = {slots}")

# ── 3. Instantiation & attribute access ────────────────────────────────────
print("\n" + "=" * 60)
print("3. INSTANTIATION & ATTRIBUTE ACCESS")
print("=" * 60)

# Bus
b = Bus(1, voltage_magnitude=1.05, bus_type='slack')
assert b.bus_id == 1
assert math.isclose(b.voltage_magnitude, 1.05)
assert b.bus_type == 'slack'
assert abs(b.voltage - 1.05) < 1e-10
b.voltage = complex(0.95, 0.1)
expected_mag = abs(complex(0.95, 0.1))
assert abs(b.voltage_magnitude - expected_mag) < 1e-10
print(f"  Bus:           voltage_magnitude={b.voltage_magnitude}, bus_type={b.bus_type}")

# Line
l = Line(1, b, b, z1=complex(0.01, 0.05))
assert l.line_id == 1
assert l.z2 == l.z1  # defaults
print(f"  Line:          line_id={l.line_id}, z1={l.z1}")

# Generator
g = Generator(1, b, internal_voltage={'1': complex(1.0, 0)})
assert g.generator_id == 1
assert g.get_internal_voltage('1') == complex(1.0, 0)
print(f"  Generator:     generator_id={g.generator_id}, internal_voltage_keys={list(g.internal_voltage.keys())[:1]}")

# Load
ld = Load(1, b, load_power=complex(0.5, 0.2))
assert ld.load_id == 1
assert ld.load_power == complex(0.5, 0.2)
print(f"  Load:          load_id={ld.load_id}, load_power={ld.load_power}")

# Transformer
t = Transformer(1, b, b, z1=complex(0.01, 0.05), tap_ratio=1.05)
assert t.transformer_id == 1
assert math.isclose(t.tap_ratio, 1.05)
print(f"  Transformer:   transformer_id={t.transformer_id}, tap_ratio={t.tap_ratio}")

# System
s = System(base_mva=100.0)
s.add_bus(b)
s.add_line(l)
assert len(s.buses) == 1
assert len(s.lines) == 1
print(f"  System:        len(buses)={len(s.buses)}, base_mva={s.base_mva}")

print("\n  All instantiations & attribute accesses PASSED")

# ── 4. Memory savings ─────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("4. MEMORY SAVINGS MEASUREMENT")
print("=" * 60)

gc.collect()

def measure_memory(n=10000):
    """Create n instances and measure per-object overhead."""
    # Measure Bus
    gc.collect()
    buses = [Bus(i) for i in range(n)]
    gc.collect()
    # Use sys.getsizeof for one
    bus_size = sys.getsizeof(buses[0])
    del buses
    gc.collect()

    # Measure Line
    b_ref = Bus(0)
    gc.collect()
    lines = [Line(i, b_ref, b_ref) for i in range(n)]
    line_size = sys.getsizeof(lines[0])
    del lines
    gc.collect()

    # Measure Generator
    gens = [Generator(i, b_ref) for i in range(n)]
    gen_size = sys.getsizeof(gens[0])
    del gens
    gc.collect()

    # Measure Load
    loads = [Load(i, b_ref) for i in range(n)]
    load_size = sys.getsizeof(loads[0])
    del loads
    gc.collect()

    # Measure Transformer
    xfs = [Transformer(i, b_ref, b_ref) for i in range(n)]
    xf_size = sys.getsizeof(xfs[0])
    del xfs
    gc.collect()

    # Measure System
    sys_size = sys.getsizeof(System())

    return {
        'Bus': bus_size,
        'Line': line_size,
        'Generator': gen_size,
        'Load': load_size,
        'Transformer': xf_size,
        'System': sys_size,
    }

sizes = measure_memory(50000)
print(f"  {'Class':15s}  {'Bytes/obj':>10}  {'KB/10K':>10}  {'MB/100K':>10}")
print(f"  {'-'*15}  {'-'*10}  {'-'*10}  {'-'*10}")
for name, size in sizes.items():
    kb_10k = size * 10000 / 1024
    mb_100k = size * 100000 / 1024 / 1024
    print(f"  {name:15s}  {size:>10d}  {kb_10k:>9.1f}KB  {mb_100k:>9.2f}MB")

# ── 5. Total system memory estimate ───────────────────────────────────────
print("\n" + "=" * 60)
print("5. TOTAL MEMORY ESTIMATE (118-Bus System)")
print("=" * 60)

n_buses = 118
n_lines = 150
n_gens = 20
n_loads = 118
n_xfs = 50

total_slots = (
    sizes['Bus'] * n_buses +
    sizes['Line'] * n_lines +
    sizes['Generator'] * n_gens +
    sizes['Load'] * n_loads +
    sizes['Transformer'] * n_xfs +
    sizes['System']
)

# Compare with typical dict-based sizes (~56 bytes overhead per __dict__ entry)
# A typical empty dict is 72 bytes + 8 bytes per attribute
# For Bus with 11 attributes, dict overhead ≈ 72 + 11*8 = 160 bytes
# With __slots__, Bus is just the sum of slot references (8 bytes each on 64-bit)
# So savings ≈ 160 - (11*8) = 72 bytes per Bus
print(f"  {'Component':15s}  {'Count':>6}  {'Bytes':>8}  {'KB':>8}")
print(f"  {'-'*15}  {'-'*6}  {'-'*8}  {'-'*8}")
components = [
    ('Bus', n_buses, sizes['Bus']),
    ('Line', n_lines, sizes['Line']),
    ('Generator', n_gens, sizes['Generator']),
    ('Load', n_loads, sizes['Load']),
    ('Transformer', n_xfs, sizes['Transformer']),
    ('System', 1, sizes['System']),
]
for name, count, size in components:
    print(f"  {name:15s}  {count:>6d}  {size * count:>8d}  {size * count / 1024:>7.1f}")
print(f"  {'-'*15}  {'-'*6}  {'-'*8}  {'-'*8}")
print(f"  {'TOTAL':15s}  {'-':>6}  {total_slots:>8d}  {total_slots / 1024:>7.1f}")

# ── 6. Compare with dict-based equivalent ─────────────────────────────────
print("\n-- Comparison with dict-based objects --")
# A Python object __dict__ overhead is roughly: 56 (object header) + sizeof(dict)
# But the actual savings come from no per-instance __dict__ dict object.
# Typical dict overhead for 11-attrib object: ~72 (dict struct) + 11*8 (keys) ~ 160 bytes
# __slots__ eliminates the dict entirely.
est_dict_bus = sys.getsizeof({}) + 56 + 11 * 8  # dict overhead + object header + refs
est_slots_bus = sizes['Bus']
saving = est_dict_bus - est_slots_bus
print(f"  Estimated dict-based Bus: ~{est_dict_bus} bytes")
print(f"  Slots-based Bus:          {est_slots_bus} bytes")
print(f"  Per-object savings:       ~{saving} bytes ({saving/est_dict_bus*100:.0f}%)")
print(f"  Total savings (118-bus):  ~{saving * n_buses / 1024:.0f} KB")

print("\n✅ ALL VALIDATIONS PASSED")
