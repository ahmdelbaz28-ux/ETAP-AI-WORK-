#!/usr/bin/env python3
"""
Main demonstration script for the power_protection_system.
Creates a 3-bus power system, runs load flow, short circuit, and protection coordination.
"""

import os
import sys

# Add the current directory to the path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib.pyplot as plt
import numpy as np

from core_model.bus import Bus
from core_model.generator import Generator
from core_model.line import Line
from core_model.load import Load
from core_model.system import System
from engine.engine import PowerSystemEngine
from relays.relay import OvercurrentRelay


def create_3bus_system():
    """
    Create a simple 3-bus power system.
    Bus 1: Slack bus (generator)
    Bus 2: PV bus (generator)
    Bus 3: PQ bus (load)
    """
    # Create system
    system = System(base_mva=100.0)

    # Create buses
    bus1 = Bus(bus_id=1, voltage_magnitude=1.05, voltage_angle=0.0, bus_type='slack')
    bus2 = Bus(bus_id=2, voltage_magnitude=1.0, voltage_angle=0.0, bus_type='pv')
    bus3 = Bus(bus_id=3, voltage_magnitude=1.0, voltage_angle=0.0, bus_type='pq')
    system.add_bus(bus1)
    system.add_bus(bus2)
    system.add_bus(bus3)

    # Create generators
    gen1 = Generator(generator_id=1, bus=bus1,
                     internal_voltage={'1': complex(1.05, 0), '2': complex(0,0), '0': complex(0,0)},
                     impedance={'1': complex(0.0, 0.2), '2': complex(0,0.2), '0': complex(0,0.1)})
    gen2 = Generator(generator_id=2, bus=bus2,
                     internal_voltage={'1': complex(1.0, 0), '2': complex(0,0), '0': complex(0,0)},
                     impedance={'1': complex(0.0, 0.15), '2': complex(0,0.15), '0': complex(0,0.05)})
    system.add_generator(gen1)
    system.add_generator(gen2)

    # Set generation power on buses for load flow
    # Bus 1 (Slack): generation is determined by the solver, set initial estimate
    bus1.generation_power = complex(0.0, 0.0)
    # Bus 2 (PV): scheduled generation of 0.5 pu (50 MW on 100 MVA base)
    bus2.generation_power = complex(0.5, 0.0)

    # Create load (Load constructor automatically adds load_power to bus)
    load1 = Load(load_id=1, bus=bus3, load_power=complex(0.8, 0.3))  # 80 MW, 30 MVar
    system.add_load(load1)

    # Create lines and transformers
    # Line between bus1 and bus2
    line12 = Line(line_id=1, from_bus=bus1, to_bus=bus2,
                  z1=complex(0.01, 0.05), z2=complex(0.01, 0.05), z0=complex(0.03, 0.15),
                  yshunt1=complex(0, 0.02), yshunt2=complex(0, 0.02), yshunt0=complex(0, 0.06))
    # Line between bus2 and bus3
    line23 = Line(line_id=2, from_bus=bus2, to_bus=bus3,
                  z1=complex(0.015, 0.06), z2=complex(0.015, 0.06), z0=complex(0.045, 0.18),
                  yshunt1=complex(0, 0.02), yshunt2=complex(0, 0.02), yshunt0=complex(0, 0.06))
    # Transformer between bus2 and bus3 (optional, we already have a line)
    # For simplicity, we'll just use lines.

    system.add_line(line12)
    system.add_line(line23)

    return system

def main():
    print("=" * 60)
    print("Power Protection System Demonstration")
    print("=" * 60)

    # Enable auto-correct for non-English input (used by normalize_input for CLI args)
    _auto_correct = os.getenv('AUTO_CORRECT_LANGUAGE', 'true').lower() == 'true'

    # Normalize any user input (if applicable)
    # For CLI arguments, you can wrap them with normalize_input
    # Example: user_input = normalize_input(user_input, auto_correct)

    # Create the 3-bus system
    system = create_3bus_system()
    print(f"Created system: {system}")

    # Create the engine
    engine = PowerSystemEngine(system)

    # 1. Run Load Flow Analysis
    print("\n1. Running Load Flow Analysis...")
    lf_result = engine.run_load_flow()
    print(f"   Converged: {lf_result['converged']}")
    if lf_result['converged']:
        print("   Bus Voltages:")
        for bid, v in lf_result['bus_voltages'].items():
            print(f"     Bus {bid}: {abs(v):.4f} angle {np.angle(v, deg=True):.2f}° pu")
    else:
        print("   Load flow did not converge.")

    # 2. Run Short Circuit Analysis at Bus 2
    print("\n2. Running Short Circuit Analysis at Bus 2...")
    fault_types = ['three_phase', 'line_to_ground', 'line_to_line', 'double_line_to_ground']
    for fault_type in fault_types:
        try:
            fault_result = engine.run_fault_analysis(fault_type, bus_id=2)
            print(f"   {fault_type.replace('_', ' ').title()}:")
            if 'fault_current' in fault_result:
                If = fault_result['fault_current']
                print(f"     Fault Current: {abs(If):.4f} angle {np.angle(If, deg=True):.2f}° pu")
            elif 'fault_current_b' in fault_result:
                Ib = fault_result['fault_current_b']
                Ic = fault_result['fault_current_c']
                print(f"     Fault Current B: {abs(Ib):.4f} angle {np.angle(Ib, deg=True):.2f}° pu")
                print(f"     Fault Current C: {abs(Ic):.4f} angle {np.angle(Ic, deg=True):.2f}° pu")
            print(f"     Affected Bus Index: {fault_result.get('affected_bus_index', 'N/A')}")
        except Exception as e:
            print(f"   Error in {fault_type}: {e}")

    # 3. Run Protection Coordination Check
    print("\n3. Running Protection Coordination Check...")
    # Define two overcurrent relays: one upstream (near bus1) and one downstream (near bus3)
    # We'll simulate fault currents for a range of values.
    fault_currents = [2.0, 5.0, 10.0, 20.0, 50.0]  # in per unit (must be > Ip=1.0)
    coord_result = engine.run_protection_coordination(
        upstream_relay_id=1,
        downstream_relay_id=2,
        fault_currents=fault_currents
    )
    print(f"   All faults coordinated: {coord_result['all_coordinated']}")
    for i, res in enumerate(coord_result['results']):
        print(f"     Fault Current {fault_currents[i]:.1f} pu: "
              f"Upstream={res['upstream_time']:.3f}s, "
              f"Downstream={res['downstream_time']:.3f}s, "
              f"Margin={res['margin']:.3f}s, "
              f"Coordinated={res['coordinated']}")

    # 4. Generate a simple report
    print("\n4. Generating Engineering Report...")
    report_lines = []
    report_lines.append("Power System Engineering Report")
    report_lines.append("=" * 40)
    report_lines.append(f"System Base MVA: {system.base_mva} MVA")
    report_lines.append(f"Number of Buses: {len(system.buses)}")
    report_lines.append(f"Number of Lines: {len(system.lines)}")
    report_lines.append(f"Number of Transformers: {len(system.transformers)}")
    report_lines.append(f"Number of Generators: {len(system.generators)}")
    report_lines.append(f"Number of Loads: {len(system.loads)}")
    report_lines.append("")
    report_lines.append("Load Flow Results:")
    report_lines.append(f"  Converged: {lf_result['converged']}")
    if lf_result['converged']:
        for bid, v in lf_result['bus_voltages'].items():
             report_lines.append(f"  Bus {bid}: {abs(v):.4f} angle {np.angle(v, deg=True):.2f}° pu")
    report_lines.append("")
    report_lines.append("Fault Analysis at Bus 2:")
    for fault_type in fault_types:
        try:
            fault_result = engine.run_fault_analysis(fault_type, bus_id=2)
            if 'fault_current' in fault_result:
                If = fault_result['fault_current']
                report_lines.append(f"  {fault_type.replace('_', ' ').title()}: {abs(If):.4f} angle {np.angle(If, deg=True):.2f}° pu")
            else:
                report_lines.append(f"  {fault_type.replace('_', ' ').title()}: See details above")
        except Exception:
            report_lines.append(f"  {fault_type.replace('_', ' ').title()}: Error")
    report_lines.append("")
    report_lines.append("Protection Coordination:")
    report_lines.append(f"  All Faults Coordinated: {coord_result['all_coordinated']}")
    for i, res in enumerate(coord_result['results']):
        report_lines.append(f"  If={fault_currents[i]:.1f} pu: T_up={res['upstream_time']:.3f}s, T_down={res['downstream_time']:.3f}s, Margin={res['margin']:.3f}s")

    report_text = "\n".join(report_lines)
    print(report_text)

    # Save report to file
    with open('power_system_report.txt', 'w') as f:
        f.write(report_text)
    print("\nReport saved to 'power_system_report.txt'")

    # 5. Create some visualizations
    print("\n5. Creating Visualizations...")
    # Create relays for TCC plot
    relay1 = OvercurrentRelay(relay_id=1, name='Relay1 (Bus1)', TMS=0.1, Ip=1.0)
    relay2 = OvercurrentRelay(relay_id=2, name='Relay2 (Bus2)', TMS=0.2, Ip=1.0)
    relay3 = OvercurrentRelay(relay_id=3, name='Relay3 (Bus3)', TMS=0.3, Ip=1.0)
    # Plot TCC curves
    fig1 = engine.visualize_tcc([relay1, relay2, relay3], current_range=(0.5, 20))
    fig1.savefig('tcc_curves.png', dpi=150, bbox_inches='tight')
    plt.close(fig1)
    # Plot coordination margin
    fig2 = engine.visualize_coordination(relay1, relay2, [0.5, 1, 2, 5, 10, 20])
    fig2.savefig('coordination_margin.png', dpi=150, bbox_inches='tight')
    plt.close(fig2)
    print("   Saved TCC curves to 'tcc_curves.png'")
    print("   Saved coordination margin to 'coordination_margin.png'")

    print("\n" + "=" * 60)
    print("Demonstration Complete")
    print("=" * 60)

if __name__ == "__main__":
    main()
