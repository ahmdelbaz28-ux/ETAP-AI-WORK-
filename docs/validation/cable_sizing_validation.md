# IEC 60364 / IEC 60287 Cable Sizing Validation Report

## 1. Study Overview
- **Study Type**: cable_sizing
- **Standards**: IEC 60364-5-52 (Wiring systems selection) and IEC 60287 (Electric cables - Calculation of the current rating)
- **Target Criteria**: Continuous ampacity derating (temperature, grouping, soil resistivity), max voltage drop <= 3.0% (feeders) / 5.0% (branch), short-circuit thermal withstand (adiabatic formula).
- **Test Harness**: tests/scenarios/test_cable_sizing_scenario.py

## 2. Calibration Results & Benchmarks
- **Verification Status**: CERTIFIED PASS (7/7 tests passed).
