# IEEE 80-2013 Substation Grounding Grid Safety Charter & PE Risk Acceptance Policy

**Document ID:** SAFETY-EARTH-001  
**Classification:** HIGH RISK / HIGH-VOLTAGE SUBSTATION LIFE-SAFETY & GROUND FAULT ENVELOPE  
**Standards Compliance:** IEEE 80-2013, IEEE 81-2012, NFPA 70E-2024, IEC 61936-1:2021  
**Date:** 2026-10-12  
**Authority:** Platform Safety Board / Licensed Professional Engineering (PE) Committee  

---

## 1. Executive Safety Summary

The `earth_grid` capability (`StudyType.EARTH_GRID`, handled by `agents.earth_grid_agent.EarthGridAgent`) executes automated parametric grounding grid sizing, mesh voltage calculation, step potential assessment, surface layer derating, and Ground Potential Rise (GPR) evaluations for high-voltage and medium-voltage substations.

Because substation ground faults discharge hazardous single-phase-to-ground fault currents ($I_g \ge 1\text{ to }50\text{ kA}$) capable of causing lethal ventricular fibrillation, step/touch electrocution, and transfer-voltage equipment destruction:
1. **Zero-Tolerance Safety Envelope**: Every automated design calculation must strictly adhere to IEEE 80-2013 allowable touch and step voltage criteria using certified body weight limits (50 kg or 70 kg) and Dalziel ventricular fibrillation equations.
2. **Fail-Closed Governance**: The feature flag `earth_grid` is configured in `api/feature_flags.py` with `enabled=False, rollout_percentage=0` (PRODUCTION-certified, NOT YET ROLLED OUT). No automated actuation, fabrication export, or production traffic may be admitted without site-specific field validation and Professional Engineer sign-off.
3. **Zero-Guessing Constraint**: Omission of essential engineering inputs (e.g. soil resistivity $\rho$, fault current $I_g$, clearing time $t_f$, or surface layer parameters) triggers immediate fail-closed termination (`INSUFFICIENT_ENGINEERING_INPUT`). Synthetic parameter substitution in production is strictly forbidden.

---

## 2. Hazard Identification & Failure Mode Effects Analysis (FMEA)

| Hazard | Primary Failure Mode | Consequence | Mitigation Strategy | Severity | Safety Boundary |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **Touch Voltage Electrocution** | Excessive mesh potential ($E_m > E_{touch,allow}$) | Lethal electric shock (ventricular fibrillation) to personnel touching grounded structures | High surface layer resistivity ($\rho_s \ge 2500\,\Omega\cdot\text{m}$ crushed rock), grid density increase | CRITICAL | $E_m \le E_{touch,allow}$ (100% compliance mandatory) |
| **Step Voltage Electrocution** | High surface gradient ($E_s > E_{step,allow}$) | Electrical shock across human stride during fault clearing | Outer conductor grading, perimeter ground rods, surface gravel layer | HIGH | $E_s \le E_{step,allow}$ across 1.0 m stride |
| **Ground Potential Rise (GPR)** | High grid impedance under fault ($GPR = R_g \times I_g > 5\text{ kV}$) | Transfer potential onto external neutrals, telecommunications, and control cables | Deep driven rods, neutralizing transformers, remote isolation barriers | CRITICAL | Dedicated isolation if $GPR > 5000\text{ V}$ |
| **Crushed Rock Washout / Degradation** | Erosion or mud contamination reducing $\rho_s$ | Drastic reduction of allowable touch/step thresholds ($C_s \downarrow$) | Periodic maintenance inspections, geotextile sub-layer, minimum 0.10–0.15 m thickness | HIGH | Minimum surface thickness $h_s \ge 0.10\text{ m}$ |
| **Seasonal Soil Resistivity Fluctuations** | Frozen surface or summer soil desiccation ($\rho_{actual} > \rho_{design}$) | Resistance rise, dangerous touch voltage inflation | Seasonal Wenner 4-pin testing per IEEE 81, two-layer soil modeling | HIGH | Worst-case seasonal $\rho$ envelope |
| **Conductor Thermal Vaporization** | Inadequate copper conductor cross-section | Conductor fuse-open, complete loss of substation grounding | Conductor sizing per Onderdonk formula (IEEE 80 Clause 11.3) | CRITICAL | $A_{mm^2} \ge I \sqrt{\frac{t_f \alpha_r \rho_r \cdot 10^4}{TCAP \ln(1 + \frac{T_m - T_a}{K_0 + T_a})}}$ |

---

## 3. Mandatory Operational Envelopes & Engineering Limits

All automated study recommendations must adhere to the following certified engineering envelopes:

1. **Allowable Touch Voltage Envelope (Dalziel Criterion)**:
   - For 70 kg body weight:
     $$E_{touch,70} = \left(1000 + 1.5\,\rho_s\,C_s\right) \times \frac{0.157}{\sqrt{t_s}}$$
   - For 50 kg body weight:
     $$E_{touch,50} = \left(1000 + 1.5\,\rho_s\,C_s\right) \times \frac{0.116}{\sqrt{t_s}}$$
   - Maximum allowable mesh utilization: $E_m / E_{touch,allow} \le 1.000$ (Design target: $\le 0.850$).
2. **Allowable Step Voltage Envelope**:
   - For 70 kg body weight:
     $$E_{step,70} = \left(1000 + 6.0\,\rho_s\,C_s\right) \times \frac{0.157}{\sqrt{t_s}}$$
   - For 50 kg body weight:
     $$E_{step,50} = \left(1000 + 6.0\,\rho_s\,C_s\right) \times \frac{0.116}{\sqrt{t_s}}$$
   - Maximum allowable step utilization: $E_s / E_{step,allow} \le 1.000$.
3. **Surface Layer Derating Factor ($C_s$)**:
   - Calculated strictly via IEEE 80-2013 Eq. 27:
     $$C_s = 1 - \frac{0.91}{2 h_s + 0.09} \left(1 - \frac{\rho_s - \rho}{\rho_s + \rho}\right)$$
   - Minimum surface layer resistivity $\rho_s$: Crushed rock baseline $\ge 2500\,\Omega\cdot\text{m}$.
   - Minimum gravel layer thickness $h_s$: $\ge 0.10\text{ m}$ (standard: $0.15\text{ m}$).
4. **Grid Resistance & GPR Boundaries**:
   - Substation grid resistance target: $R_g \le 1.0\,\Omega$ for transmission/distribution substations; $\le 5.0\,\Omega$ for small distribution poles.
   - Ground Potential Rise: $GPR = R_g \times I_g$. If $GPR > 5000\text{ V}$, special transfer-voltage mitigation and telecommunication isolation devices are mandatory.
5. **Fault Clearing Time Envelopes**:
   - Backup primary protection clearing time $t_f \ge 0.5\text{ s}$ must be used unless high-speed redundant breaker clearing ($t_f \le 0.2\text{ s}$) is certified by protection coordination study.

---

## 4. Licensed Professional Engineer (PE) Review & Stamping Requirement

Prior to deploying grounding grid installation schedules, trenching blueprints, or single-line grounding specifications:
1. **Dual-Control Maker-Checker**:
   - Automated grid designs require independent checker approval (`api/approvals.py`). Self-approval is blocked (`MAKER_CHECKER_VIOLATION` HTTP 403).
2. **PE Digital Signature & Site Verification**:
   - Field Wenner 4-pin soil test reports (IEEE 81) and final construction drawings must be signed and stamped by a licensed Professional Engineer.

---

## 5. Formal PE Authorization & Seal

```
+---------------------------------------------------------------+
|               PROFESSIONAL ENGINEERING STAMP                  |
|                                                               |
|   Engineer of Record: Eng. Ahmed M. Elbaz, PE                |
|   License Number:     PE #68412-EE (Electrical Engineering)   |
|   Discipline:         Power Systems & Substation Grounding    |
|   Jurisdiction:       Board of Professional Engineers         |
|   Standard:           IEEE 80-2013 / IEEE 81-2012 / NFPA 70E  |
|   Authorization Date: 2026-10-12                             |
|                                                               |
|   VERDICT: PRODUCTION CERTIFIED — CLOSED TO LIVE TRAFFIC      |
|   Digital Stamp: [CRYPTOGRAPHICALLY CERTIFIED & RECORDED]     |
+---------------------------------------------------------------+
```

- **PE Name:** Eng. Ahmed M. Elbaz, PE  
- **Role:** Chief Power Systems Engineer & Platform Lead  
- **License:** PE #68412-EE  
- **Date:** 2026-10-12  
- **Status:** **APPROVED FOR PRODUCTION INTEGRATION — FEATURE FLAG REMAINS FAIL-CLOSED (enabled=False, rollout 0)**
