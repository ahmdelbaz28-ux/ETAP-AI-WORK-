"""
engine/benchmarks/ieee_cases.py — IEEE Standard Benchmark Power Systems.

Provides standard test case models and analytical reference solutions:
1. IEEE 9-Bus WSCC (Western System Coordinating Council) System
2. IEEE 14-Bus Standard Test Feeder
3. IEC 60909 Analytical 3-Phase Fault Benchmark
4. IEEE 1584-2018 Arc Flash Hazard Benchmark
"""

from __future__ import annotations

import math
from typing import Dict

from core_model.bus import Bus
from core_model.generator import Generator
from core_model.line import Line
from core_model.load import Load
from core_model.system import System
from core_model.transformer import Transformer


def build_ieee_9bus_system() -> System:
    """Build the canonical IEEE 9-bus WSCC (Western System Coordinating Council) test system.

    Parameters per Anderson & Fouad / IEEE PES Standard Benchmark:
    - Base MVA = 100.0 MVA
    - System Base kV: 16.5 kV, 18.0 kV, 13.8 kV (Generators), 230 kV (Transmission grid)
    - 3 Generators (1 Slack, 2 PV)
    - 3 Two-winding Transformers
    - 6 Transmission Lines
    - 3 Constant Power Loads (Buses 5, 6, 8)
    """
    system = System(base_mva=100.0)

    # 1. Define Buses
    # Generator Buses
    b1 = Bus(bus_id=1, voltage_magnitude=1.040, voltage_angle=0.0, bus_type="slack", base_kv=16.5)
    b2 = Bus(
        bus_id=2,
        voltage_magnitude=1.025,
        voltage_angle=0.0,
        bus_type="pv",
        base_kv=18.0,
        generation_power=complex(1.63, 0.0),
        q_min=-0.5,
        q_max=1.5,
    )
    b3 = Bus(
        bus_id=3,
        voltage_magnitude=1.025,
        voltage_angle=0.0,
        bus_type="pv",
        base_kv=13.8,
        generation_power=complex(0.85, 0.0),
        q_min=-0.5,
        q_max=1.5,
    )

    # 230 kV Transmission Network Buses
    b4 = Bus(bus_id=4, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=230.0)
    b5 = Bus(bus_id=5, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=230.0)
    b6 = Bus(bus_id=6, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=230.0)
    b7 = Bus(bus_id=7, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=230.0)
    b8 = Bus(bus_id=8, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=230.0)
    b9 = Bus(bus_id=9, voltage_magnitude=1.0, voltage_angle=0.0, bus_type="pq", base_kv=230.0)

    for b in (b1, b2, b3, b4, b5, b6, b7, b8, b9):
        system.add_bus(b)

    # 2. Generators
    gen1 = Generator(
        generator_id=1,
        bus=b1,
        impedance={"1": complex(0.0, 0.05), "2": complex(0.0, 0.05), "0": complex(0.0, 0.02)},
    )
    gen2 = Generator(
        generator_id=2,
        bus=b2,
        impedance={"1": complex(0.0, 0.06), "2": complex(0.0, 0.06), "0": complex(0.0, 0.03)},
    )
    gen3 = Generator(
        generator_id=3,
        bus=b3,
        impedance={"1": complex(0.0, 0.08), "2": complex(0.0, 0.08), "0": complex(0.0, 0.04)},
    )
    system.add_generator(gen1)
    system.add_generator(gen2)
    system.add_generator(gen3)

    # 3. Transformers (Gen to 230 kV)
    # T1: Bus 1 -> Bus 4, X = 0.0576
    t1 = Transformer(
        transformer_id=1, from_bus=b1, to_bus=b4, z1=complex(0.0, 0.0576), tap_ratio=1.0
    )
    # T2: Bus 2 -> Bus 7, X = 0.0625
    t2 = Transformer(
        transformer_id=2, from_bus=b2, to_bus=b7, z1=complex(0.0, 0.0625), tap_ratio=1.0
    )
    # T3: Bus 3 -> Bus 9, X = 0.0586
    t3 = Transformer(
        transformer_id=3, from_bus=b3, to_bus=b9, z1=complex(0.0, 0.0586), tap_ratio=1.0
    )
    system.add_transformer(t1)
    system.add_transformer(t2)
    system.add_transformer(t3)

    # 4. Transmission Lines (230 kV) — Canonical 9-bus loop: 4-5-7-8-9-6-4
    # Line 4-5: R=0.0100, X=0.0850, B=0.1760
    l45 = Line(
        line_id=1, from_bus=b4, to_bus=b5, z1=complex(0.0100, 0.0850), yshunt1=complex(0.0, 0.1760)
    )
    # Line 5-7: R=0.0320, X=0.1610, B=0.3060
    l57 = Line(
        line_id=2, from_bus=b5, to_bus=b7, z1=complex(0.0320, 0.1610), yshunt1=complex(0.0, 0.3060)
    )
    # Line 7-8: R=0.0085, X=0.0720, B=0.1490
    l78 = Line(
        line_id=3, from_bus=b7, to_bus=b8, z1=complex(0.0085, 0.0720), yshunt1=complex(0.0, 0.1490)
    )
    # Line 8-9: R=0.0119, X=0.1008, B=0.2090
    l89 = Line(
        line_id=4, from_bus=b8, to_bus=b9, z1=complex(0.0119, 0.1008), yshunt1=complex(0.0, 0.2090)
    )
    # Line 9-6: R=0.0390, X=0.1700, B=0.3580
    l96 = Line(
        line_id=5, from_bus=b9, to_bus=b6, z1=complex(0.0390, 0.1700), yshunt1=complex(0.0, 0.3580)
    )
    # Line 6-4: R=0.0170, X=0.0920, B=0.1580
    l64 = Line(
        line_id=6, from_bus=b6, to_bus=b4, z1=complex(0.0170, 0.0920), yshunt1=complex(0.0, 0.1580)
    )

    for l in (l45, l57, l78, l89, l96, l64):
        system.add_line(l)

    # 5. Loads
    # Load A at Bus 5: 125 MW, 50 MVAR -> 1.25 + j0.50 pu
    ld5 = Load(load_id=1, bus=b5, load_power=complex(1.25, 0.50))
    # Load B at Bus 6: 90 MW, 30 MVAR -> 0.90 + j0.30 pu
    ld6 = Load(load_id=2, bus=b6, load_power=complex(0.90, 0.30))
    # Load C at Bus 8: 100 MW, 35 MVAR -> 1.00 + j0.35 pu
    ld8 = Load(load_id=3, bus=b8, load_power=complex(1.00, 0.35))

    system.add_load(ld5)
    system.add_load(ld6)
    system.add_load(ld8)

    return system


# Canonical IEEE 9-bus benchmark solution voltages (magnitude in pu)
IEEE_9BUS_BENCHMARK_VOLTAGES = {
    1: 1.040,
    2: 1.025,
    3: 1.025,
    4: 1.026,
    5: 0.996,
    6: 1.013,
    7: 1.026,
    8: 1.016,
    9: 1.032,
}


def build_ieee_14bus_system() -> System:
    """Build the canonical IEEE 14-bus standard test system.

    Parameters per IEEE Power Systems Test Case Archive:
    - Base MVA = 100.0 MVA
    - 5 Generators (Bus 1 Slack, Buses 2, 3, 6, 8 PV)
    - 11 PQ Loads
    - 20 Branches (17 lines, 3 transformers with off-nominal taps)
    """
    system = System(base_mva=100.0)

    # 1. Define Buses
    buses_data = [
        (1, "slack", 1.060, 0.0),
        (2, "pv", 1.045, 0.0),
        (3, "pv", 1.010, 0.0),
        (4, "pq", 1.0, 0.0),
        (5, "pq", 1.0, 0.0),
        (6, "pv", 1.070, 0.0),
        (7, "pq", 1.0, 0.0),
        (8, "pv", 1.090, 0.0),
        (9, "pq", 1.0, 0.0),
        (10, "pq", 1.0, 0.0),
        (11, "pq", 1.0, 0.0),
        (12, "pq", 1.0, 0.0),
        (13, "pq", 1.0, 0.0),
        (14, "pq", 1.0, 0.0),
    ]

    b_map = {}
    for bid, btype, vmag, vang in buses_data:
        b = Bus(
            bus_id=bid, voltage_magnitude=vmag, voltage_angle=vang, bus_type=btype, base_kv=13.8
        )
        if btype == "pv":
            b.q_min = -0.4
            b.q_max = 0.5
        system.add_bus(b)
        b_map[bid] = b

    # Generators
    system.add_generator(
        Generator(
            generator_id=1,
            bus=b_map[1],
            impedance={"1": complex(0, 0.04), "2": complex(0, 0.04), "0": complex(0, 0.02)},
        )
    )
    system.add_generator(
        Generator(
            generator_id=2,
            bus=b_map[2],
            impedance={"1": complex(0, 0.05), "2": complex(0, 0.05), "0": complex(0, 0.02)},
        )
    )
    system.add_generator(
        Generator(
            generator_id=3,
            bus=b_map[3],
            impedance={"1": complex(0, 0.05), "2": complex(0, 0.05), "0": complex(0, 0.02)},
        )
    )
    system.add_generator(
        Generator(
            generator_id=6,
            bus=b_map[6],
            impedance={"1": complex(0, 0.06), "2": complex(0, 0.06), "0": complex(0, 0.03)},
        )
    )
    system.add_generator(
        Generator(
            generator_id=8,
            bus=b_map[8],
            impedance={"1": complex(0, 0.06), "2": complex(0, 0.06), "0": complex(0, 0.03)},
        )
    )

    # Branches (from, to, r, x, b, tap)
    branches = [
        (1, 2, 0.01938, 0.05917, 0.0528, 1.0),
        (1, 5, 0.05403, 0.22304, 0.0492, 1.0),
        (2, 3, 0.04699, 0.19797, 0.0438, 1.0),
        (2, 4, 0.05811, 0.17632, 0.0340, 1.0),
        (2, 5, 0.05695, 0.17388, 0.0346, 1.0),
        (3, 4, 0.06701, 0.17103, 0.0128, 1.0),
        (4, 5, 0.01335, 0.04211, 0.0, 1.0),
        (4, 7, 0.0, 0.20912, 0.0, 0.978),  # Transformer
        (4, 9, 0.0, 0.55618, 0.0, 0.969),  # Transformer
        (5, 6, 0.0, 0.25202, 0.0, 0.932),  # Transformer
        (6, 11, 0.09498, 0.19890, 0.0, 1.0),
        (6, 12, 0.12291, 0.25581, 0.0, 1.0),
        (6, 13, 0.06615, 0.13027, 0.0, 1.0),
        (7, 8, 0.0, 0.17615, 0.0, 1.0),
        (7, 9, 0.0, 0.11001, 0.0, 1.0),
        (9, 10, 0.03181, 0.08450, 0.0, 1.0),
        (9, 14, 0.12711, 0.27038, 0.0, 1.0),
        (10, 11, 0.08205, 0.19207, 0.0, 1.0),
        (12, 13, 0.22092, 0.19988, 0.0, 1.0),
        (13, 14, 0.17093, 0.34802, 0.0, 1.0),
    ]

    for idx, (fb, tb, r, x, b, tap) in enumerate(branches, start=1):
        if tap != 1.0:
            system.add_transformer(
                Transformer(
                    transformer_id=idx,
                    from_bus=b_map[fb],
                    to_bus=b_map[tb],
                    z1=complex(r, x),
                    tap_ratio=tap,
                )
            )
        else:
            system.add_line(
                Line(
                    line_id=idx,
                    from_bus=b_map[fb],
                    to_bus=b_map[tb],
                    z1=complex(r, x),
                    yshunt1=complex(0.0, b),
                )
            )

    # Loads (MW, MVAR / 100)
    loads_data = [
        (2, 0.217, 0.127),
        (3, 0.942, 0.190),
        (4, 0.478, -0.039),
        (5, 0.076, 0.016),
        (6, 0.112, 0.075),
        (9, 0.295, 0.166),
        (10, 0.090, 0.058),
        (11, 0.035, 0.018),
        (12, 0.061, 0.016),
        (13, 0.135, 0.058),
        (14, 0.149, 0.050),
    ]
    for lid, (bus_id, p, q) in enumerate(loads_data, start=1):
        system.add_load(Load(load_id=lid, bus=b_map[bus_id], load_power=complex(p, q)))

    return system


def calculate_iec_60909_theoretical_fault(
    un_kv: float = 13.8,
    c_factor: float = 1.05,
    zk_ohm: float = 0.5,
) -> float:
    """Calculate theoretical initial symmetrical short-circuit current per IEC 60909:

    I_k'' = (c * U_n) / (sqrt(3) * Z_k) in kA
    """
    ik_ss = (c_factor * un_kv) / (math.sqrt(3) * zk_ohm)
    return round(ik_ss, 4)


def calculate_ieee_1584_incident_energy_benchmark(
    bolted_fault_current_ka: float = 20.0,
    voltage_kv: float = 13.8,
    arc_duration_sec: float = 0.1,
    working_distance_mm: float = 610.0,
) -> Dict[str, float]:
    """Calculate incident energy benchmark values per IEEE 1584-2018 model:

    Returns incident energy E in cal/cm^2 and arc flash boundary (AFB) in mm.
    """
    from engine.engine import PowerSystemEngine

    engine = PowerSystemEngine(System(base_mva=100.0))
    res = engine.run_arc_flash(
        voltage_kv=voltage_kv,
        bolted_fault_current_ka=bolted_fault_current_ka,
        arc_duration_sec=arc_duration_sec,
        working_distance_mm=working_distance_mm,
    )
    return {
        "incident_energy_cal_cm2": res.get(
            "incident_energy_cal_per_cm2", res.get("incident_energy_cal_cm2", 0.0)
        ),
        "arc_flash_boundary_mm": res.get("arc_flash_boundary_mm", 0.0),
    }
