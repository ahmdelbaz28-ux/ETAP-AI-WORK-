# IEC 60909-0:2016 Short Circuit Validation Report

## 1. Study Overview
- **Study Type**: short_circuit
- **Standard**: IEC 60909-0:2016 (Short-circuit currents in three-phase a.c. systems)
- **Target Metrics**: Initial symmetrical fault current (Ik''), Peak current (ip), Symmetrical breaking current (Ib), Steady-state current (Ik).
- **Benchmark System**: IEC 60909 4-Bus Reference Industrial Distribution Network.
- **Test Harness**: engine/benchmarks/ieee_cases.py, tests/test_ieee_gold_standard_benchmarks.py

## 2. Calibration Results
- **Drift Tolerance**: Hard assertion delta <= 1e-6 kA against verified reference case.
- **Verification Status**: CERTIFIED PASS.
