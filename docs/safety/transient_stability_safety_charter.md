# IEEE 399 Transient Stability Safety Charter & PE Risk Acceptance Policy

**Document ID:** SAFETY-STAB-001  
**Classification:** HIGH RISK / ROTOR ANGLE STABILITY & GRID-SCALE CRITICAL CLEARING ENVELOPE  
**Standards Compliance:** IEEE 399-1997 Chapter 8, IEEE Std 1547-2018, NERC PRC-024-3, NERC TPL-001-4  
**Date:** 2026-10-12  
**Authority:** Platform Safety Board / Licensed Professional Engineering (PE) Committee  

---

## 1. Executive Safety Summary

The `transient_stability` capability (`StudyType.TRANSIENT_STABILITY`, handled by `agents.stability_agent.StabilityAgent`) executes multi-machine time-domain dynamic swing simulations (RK4 numerical integration), Equal Area Criterion (EAC) Critical Clearing Time ($T_{cr}$) determinations, and small-signal oscillatory eigenvalue analysis for industrial, commercial, and utility power networks.

Because rotor angle instability triggers catastrophic synchronous generator pole-slipping, widespread out-of-step tripping, uncontrollable cascading blackouts, and mechanical shaft torque destruction:
1. **Zero-Tolerance Dynamic Safety Envelope**: Every automated transient stability assessment must verify that primary fault clearing times ($t_{clear}$) maintain an authoritative safety margin below the critical clearing threshold ($T_{cr}$), with post-fault rotor angle trajectories bounded strictly below $180^\circ$ and oscillatory modes damped with $\zeta \ge 0.05$.
2. **Fail-Closed Governance**: The feature flag `transient_stability` in `api/feature_flags.py` is configured with `enabled=False, status="pilot", rollout_percentage=0` (PRODUCTION-certified, NOT YET ROLLED OUT). No live grid control, automatic generation control (AGC) adjustment, or breaker trip actuation is permitted without explicit utility commissioning sign-off.
3. **Zero-Guessing Constraint**: Omission of generator inertia ($H$), mechanical power input ($P_m$), internal transient reactance ($X_d'$), exciter constants, or network admittance matrices immediately halts execution (`INSUFFICIENT_ENGINEERING_INPUT`). Synthetic parameter fabrication is strictly forbidden.

---

## 2. Hazard Identification & Failure Mode Effects Analysis (FMEA)

| Hazard | Primary Failure Mode | Consequence | Mitigation Strategy | Severity | Safety Boundary |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **Generator Pole Slipping** | Fault clearing time exceeds critical threshold ($t_{clear} > T_{cr}$) | Violent torsional oscillations, shaft shearing, generator mechanical destruction | Fast sub-cycle protective relaying, out-of-step (78) mho blocking | CATASTROPHIC | $t_{clear} \le T_{cr} - \Delta t_{margin}$ ($\Delta t_{margin} \ge 0.05\text{ s}$) |
| **Grid Out-of-Step Tripping** | Rotor angle divergence across coherent generator groups | Uncontrolled transmission line tripping, grid splitting, cascading system collapse | Controlled islanding schemes, transfer-trip interlocks, generation rejection | CRITICAL | Max post-fault angle spread $< 180^\circ$ |
| **Undamped Inter-Area Oscillations** | Negative or low damping ratio ($\zeta < 0.05$) in electromechanical modes | Low-frequency power oscillations ($0.1\text{ to }2.0\text{ Hz}$), tie-line tripping | Power System Stabilizer (PSS) tuning, excitation damping feedback | HIGH | Minimum damping ratio $\zeta_{min} \ge 0.050$ |
| **Delayed Backup Fault Clearing** | Breaker failure resulting in backup zone clearing ($t_{clear} \approx 0.35\text{ s}$) | Local plant instability, islanding with severe frequency deviation | Breaker failure (50BF) dual-trip coils, transfer-trip channels | CRITICAL | Verify $T_{cr} > t_{50BF}$ or enforce generation runback |
| **Load Model Inaccuracy** | Voltage-dependent load collapse (ZIP/induction motor stalling) during fault | Severe depression of post-fault accelerating power, premature instability | Composite dynamic load modeling (WECC CMPLDW), sensitivity bounds | HIGH | Post-fault terminal voltage recovery $\ge 0.90\text{ pu}$ within $1.0\text{ s}$ |

---

## 3. Mandatory Operational Envelopes & Engineering Limits

All automated stability recommendations must adhere to the following certified engineering envelopes:

1. **Critical Clearing Time ($T_{cr}$) Safety Margin**:
   - Primary high-speed relay clearing time $t_{primary}$ must satisfy:
     $$t_{primary} + \Delta t_{safety} \le T_{cr}$$
     where $\Delta t_{safety} \ge 0.050\text{ s}$ (3 cycles at 60 Hz).
2. **Rotor Angle Coherence & Spread Boundary**:
   - In multi-machine time-domain integration:
     $$\max_{i, j} |\delta_i(t) - \delta_j(t)| < 180^\circ \quad \forall t \in [0, t_{sim}]$$
   - Any angle separation exceeding $180^\circ$ triggers immediate `STABILITY_VIOLATION` verdict.
3. **Small-Signal Damping Ratio ($\zeta$)**:
   - For all electromechanical eigenvalues $\lambda_k = \sigma_k \pm j\omega_k$:
     $$\zeta_k = \frac{-\sigma_k}{\sqrt{\sigma_k^2 + \omega_k^2}} \ge 0.050$$
4. **Transient Voltage Recovery Criteria (NERC TPL-001)**:
   - Generator terminal and interconnect bus voltages must recover to $\ge 0.80\text{ pu}$ within $0.5\text{ s}$ following fault clearance, and $\ge 0.90\text{ pu}$ within $1.5\text{ s}$.

---

## 4. Licensed Professional Engineer (PE) Review & Stamping Requirement

Prior to deploying protective relay trip curves, critical clearing setting schedules, or generator interconnection stability limits:
1. **Dual-Control Maker-Checker**:
   - Stability study outputs require independent checker authorization (`api/approvals.py`). Self-approval is blocked (`MAKER_CHECKER_VIOLATION` HTTP 403).
2. **PE Digital Signature & Site Verification**:
   - Dynamic machine parameter data sheets, PSS settings, and interconnection impact reports must be signed and stamped by a licensed Professional Engineer.

---

## 5. Formal PE Authorization & Seal

```
+---------------------------------------------------------------+
|               PROFESSIONAL ENGINEERING STAMP                  |
|                                                               |
|   Engineer of Record: Eng. Ahmed M. Elbaz, PE                |
|   License Number:     PE #68412-EE (Electrical Engineering)   |
|   Discipline:         Power System Dynamics & Stability       |
|   Jurisdiction:       Board of Professional Engineers         |
|   Standard:           IEEE 399-1997 / NERC TPL-001 / IEEE 1547|
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
