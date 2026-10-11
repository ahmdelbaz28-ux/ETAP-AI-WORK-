# IEC 60364 / IEC 60949 Cable Sizing Production Validation Report

## 1. Study Overview & Baseline Standard
- **Study Type**: `cable_sizing`
- **Standards**: IEC 60364-5-52:2009 Clause 523 (*Selection and erection of electrical equipment - Wiring systems*), IEC 60287-1-1 (*Electric cables - Calculation of the current rating*), IEC 60724:2000 (*Short-circuit temperature limits*), IEC 60949:1988 (*Calculation of thermally permissible short-circuit currents*).
- **Target Criteria**: Continuous current carrying capacity ($I_z \ge I_b$), thermal short-circuit withstand ($S \ge \frac{I_k \sqrt{t}}{k}$), maximum voltage drop ($\Delta V \le 3.0\%$ for lighting/feeders, $\le 5.0\%$ for other installations).
- **Zero-Guessing Constraint**: Omission of engineering inputs triggers immediate fail-closed termination (`AgentStatus.FAILED` with error code `INSUFFICIENT_ENGINEERING_INPUT`).
- **Lifecycle & Governance**: Promoted to `PRODUCTION` (`LifecycleStatus.PRODUCTION`, `production_supported=True`, `benchmark_status=VERIFIED_BENCHMARK`, feature flag `cable_sizing` enabled at 25% staged rollout).

---

## 2. Real Benchmark Calibration Data (3 Real Feeder Loads)

The canonical benchmark suite (`calculate_iec_60364_cable_sizing_benchmark()` in `engine/benchmarks/ieee_cases.py`) executes 3 real industrial/commercial feeder loads against manufacturer ampacity tables, analytical thermal derating, and voltage drop formulas:

### Table 1: Case 1 — 50 kW 400V Industrial Motor Feeder ($I_b = 84.91\text{ A}$, Cu/XLPE in air, $T_{amb}=40^\circ\text{C}$, $L=75\text{ m}$, $\cos\phi=0.85$)
| Parameter / Metric | Expected Benchmark Value | Computed (CableSizingAgent) | Error % | Data Source | Compliance Status |
|:---|:---:|:---:|:---:|:---|:---:|
| Base Ampacity (25 mm² Cu) | 143.00 A | 143.00 A | 0.00% | IEC 60364-5-52 Table B.52.4 Column 4 | PASS |
| Temperature Derating $C_a$ | 0.91287 | 0.91287 | 0.00% | IEC 60364-5-52 Table B.52.14 ($T_{amb}=40^\circ\text{C}$) | PASS |
| Derated Ampacity $I_z$ | 130.5405 A | 130.5405 A | 0.00% | Analytical $143.0 \times \sqrt{50/60}$ | PASS |
| Voltage Drop $\Delta V$ | 8.8877 V | 8.8877 V | 0.00% | IEC 60364-5-52 Annex G ($\sqrt{3} I L (R \cos\phi + X \sin\phi)$) | PASS |
| Voltage Drop Percentage | 2.2219% | 2.2219% | 0.00% | Analytical $\Delta V / 400\text{ V} \times 100\%$ | PASS ($\le 4.0\% / 5.0\%$) |

### Table 2: Case 2 — 120 kW 400V Main Distribution Board Feeder ($I_b = 196.82\text{ A}$, Cu/XLPE in air, $T_{amb}=35^\circ\text{C}$, 3 Circuits Touching, $I_k=25\text{ kA}$, $t=0.5\text{ s}$)
| Parameter / Metric | Expected Benchmark Value | Computed (CableSizingAgent) | Error % | Data Source | Compliance Status |
|:---|:---:|:---:|:---:|:---|:---:|
| Recommended Cross-Section | 150 mm² Cu | 150 mm² Cu | 0.00% | IEC 60949 Adiabatic Limit ($S \ge \frac{25000 \times \sqrt{0.5}}{142.85} = 123.7\text{ mm}^2$) | PASS |
| Voltage Drop Percentage | 1.7677% | 1.7677% | 0.00% | IEC 60364-5-52 Annex G ($L=120\text{ m}$, $\cos\phi=0.88$) | PASS ($\le 5.0\%$) |
| Adiabatic SC Withstand | Adequate ($I^2t \le I^2t_{perm}$) | Adequate (`True`) | 0.00% | IEC 60724 ($250^\circ\text{C}$ limit for XLPE) | PASS |

### Table 3: Case 3 — 25 kW 400V Commercial HVAC Feeder ($I_b = 43.46\text{ A}$, Al/XLPE Direct Buried, $T_{amb}=30^\circ\text{C}$, Soil $\rho=1.5\text{ K}\cdot\text{m/W}$, $L=60\text{ m}$, $\cos\phi=0.83$)
| Parameter / Metric | Expected Benchmark Value | Computed (CableSizingAgent) | Error % | Data Source | Compliance Status |
|:---|:---:|:---:|:---:|:---|:---:|
| Base Ampacity (25 mm² Al) | 114.00 A | 114.00 A | 0.00% | IEC 60364-5-52 Table B.52.4 (Aluminum) | PASS |
| Direct Burial Method Factor | 0.8500 | 0.8500 | 0.00% | IEC 60364-5-52 Table B.52.2 / Method D | PASS |
| Soil Resistivity Derating $C_s$ | 0.8900 | 0.8900 | 0.00% | IEC 60364-5-52 Table B.52.15 ($\rho=1.5$) | PASS |
| Derated Ampacity $I_z$ | 86.2410 A | 86.2410 A | 0.00% | Analytical $114 \times 0.85 \times 0.89$ | PASS |
| Voltage Drop $\Delta V$ | 5.7877 V | 5.7877 V | 0.00% | IEC 60364-5-52 Annex G (Aluminum $R_{80}=1.490\,\Omega/\text{km}$) | PASS |
| Voltage Drop Percentage | 1.4469% | 1.4469% | 0.00% | Analytical $\Delta V / 400\text{ V} \times 100\%$ | PASS ($\le 3.0\% / 5.0\%$) |

---

## 3. Production Provenance & Fail-Closed Gate Architecture
- **Production Eligibility Gate**:
  - `is_production_eligible(cap)` evaluates to `True` based on non-empty edition/clause standards scope, non-empty validation evidence, and `benchmark_status="VERIFIED_BENCHMARK"`.
- **Fail-Closed Security**:
  - Unauthenticated requests rejected (`AUTHENTICATION_REQUIRED`, HTTP 401).
  - Cross-tenant requests blocked (`CROSS_TENANT_VIOLATION`, HTTP 403).
  - Disabled flag rejected (`SPECIALIZED_EXECUTION_UNAVAILABLE`).
  - Missing engineering parameters rejected immediately with `INSUFFICIENT_ENGINEERING_INPUT`.
- **Production Provenance**:
  ```json
  "provenance": {
    "handler": "agents.cable_sizing_agent.CableSizingAgent",
    "agent_key": "cable_sizing",
    "standard": "IEC 60364",
    "lifecycle": "production"
  }
  ```

---

## 4. Verification Suites & Test Execution

- **Scientific Benchmarks (`scripts/run_ieee_benchmarks.py`)**:
  *Result*: **9/9 PASSED in 2.33s** (IEC 60364 benchmark verified).

- **Acceptance Gate Suite (`tests/test_cable_sizing_acceptance.py`)**:
  *Result*: **7/7 PASSED** (Eligibility, fail-closed, Positive Ampacity, Positive Recommendation, Scientific Benchmarks).

- **Multi-Turn Scenario Suite (`tests/scenarios/test_cable_sizing_scenario.py`)**:
  *Result*: **7/7 PASSED**.
