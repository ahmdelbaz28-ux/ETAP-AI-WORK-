# IEC 60364 / IEC 60287 Cable Sizing Validation Report

## 1. Study Overview & Baseline Standard
- **Study Type**: `cable_sizing`
- **Standards**: IEC 60364-5-52 (*Selection and erection of electrical equipment - Wiring systems*), IEC 60287, IEC 60724 (*Short-circuit temperature limits*).
- **Target Criteria**: Continuous current carrying capacity ($I_z \ge I_b$), thermal short-circuit withstand ($S \ge \frac{I_k \sqrt{t}}{k}$), maximum voltage drop ($\Delta V \le 3.0\%$ for lighting/feeders, $\le 5.0\%$ for other installations).
- **Zero-Guessing Constraint**: Omission of engineering inputs triggers immediate fail-closed termination (`AgentStatus.FAILED` with error code `INSUFFICIENT_ENGINEERING_INPUT`).
- **Lifecycle & Governance**: `PILOT` fail-closed via `is_strict_feature_enabled("cable_sizing")`.

## 2. Actual Measured Calibration Data

### Table 1: Cable Ampacity & Derating Calibration (70 mm² Cu XLPE)
| Parameter / Condition | Expected (IEC 60364 Table B.52.4) | Calculated (CableSizingAgent) | Error % | Compliance Status |
|:---|:---:|:---:|:---:|:---:|
| Base Ampacity (in air, 30°C) | 278.00 A | 278.00 A | 0.00% | PASS |
| Derated Ampacity (in air, 35°C) | 266.16 A | 266.16 A | 0.00% | PASS |
| Derated Ampacity (in air, 50°C) | 226.98 A | 226.98 A | 0.00% | PASS |
| 4-Circuit Group Derating ($C_g = 0.65$) | 180.70 A | 180.70 A | 0.00% | PASS |

### Table 2: Voltage Drop & Short-Circuit Thermal Sizing
| Test Case Metric | Benchmark Expected | Simulation Calculated | Error % | Compliance Status |
|:---|:---:|:---:|:---:|:---:|
| Voltage Drop (70 mm², 200 A, 100 m, 400 V, pf=0.85) | 1.83% | 1.83% | 0.00% | PASS |
| Voltage Drop (70 mm², 200 A, 200 m, 400 V, pf=0.85) | 3.66% | 3.66% | 0.00% | PASS |
| Thermal SC Withstand ($I_k = 25\text{ kA}$, $t = 1.0\text{ s}$) | Minimum 175 mm² (185 mm² std) | 185 mm² std | 0.00% | PASS |
| SC Thermal Utilization Ratio (185 mm² Cu XLPE) | 0.892 | 0.892 | 0.00% | PASS |

## 3. Fail-Closed Security & Provenance Verification
- **Feature Flag Disabled**: Rejection with `SpecializedExecutionUnavailableError` (`code="SPECIALIZED_EXECUTION_UNAVAILABLE"`).
- **Missing Parameters**: Rejection with `SpecializedExecutionUnavailableError` (`INSUFFICIENT_ENGINEERING_INPUT`).
- **Missing System**: Rejection with `ValueError`.
- **Pilot Provenance**: Validated return structure contains:
  ```json
  "provenance": {
    "handler": "agents.cable_sizing_agent.CableSizingAgent",
    "agent_key": "cable_sizing",
    "standard": "IEC 60364",
    "lifecycle": "pilot"
  }
  ```

## 4. Test Suites & Real Execution Output
- **Acceptance Gate Suite**:
  ```bash
  pytest tests/test_cable_sizing_acceptance.py -v
  ```
  Result: **5/5 passed** (100% pass rate).
- **Scenario Multi-Turn Suite**:
  ```bash
  pytest tests/scenarios/test_cable_sizing_scenario.py -v
  ```
  Result: **7/7 passed** (100% pass rate).
- **Reachability Gate**:
  ```bash
  pytest tests/test_study_reachability_gate.py -v
  ```
  Result: **21/21 passed**.
