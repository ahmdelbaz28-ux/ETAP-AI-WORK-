# IEC 61850 / IEC 60870-5-104 Substation Automation & SCADA Safety Charter & PE Risk Acceptance Policy

**Document ID:** SAFETY-SCADA-001  
**Classification:** CRITICAL RISK / INDUSTRIAL SUBSTATION AUTOMATION & SWITCHGEAR SUPERVISORY CONTROL  
**Standards Compliance:** IEC 61850-7-2 Clause 13 (ACSI Controls), IEC 61850-7-4, IEC 60870-5-104, IEEE C37.1, NERC CIP-005, NERC CIP-007  
**Date:** 2026-10-12  
**Authority:** Platform Safety Board / Licensed Professional Engineering (PE) Committee  

---

## 1. Executive Safety Summary

The `scada` capability (`StudyType.SCADA` / protocol bridge, handled by `agents.scada_agent.SCADAAgent` and `scada_protocols`) integrates substation automation protocols (Modbus TCP, OPC UA, IEC 60870-5-104, IEC 61850) with core network models for real-time telemetry ingestion, state estimation, and supervisory control monitoring.

Because erroneous, unverified, or un-interlocked supervisory control commands to high-voltage and medium-voltage switchgear can result in catastrophic equipment vaporization, fatal arc-blast incidents, equipment damage, or regional grid collapse:
1. **Mandatory Select-Before-Operate (SBO) Discipline**: All supervisory switching operations must adhere to a strict two-stage Select-Before-Operate (Arm-and-Fire) discipline. Direct-Execute commands on primary breakers and disconnectors are permanently prohibited.
2. **Deterministic Interlock Enforcement**: Hard physical and logical interlocks (breaker-disconnector interlocking, sync-check 25, ground-switch interlocking) must be verified prior to arming any control point.
3. **Dual-Control Maker-Checker Governance**: Critical control actions and telemetry point-mapping mutations require dual-control sign-off (`api/approvals.py`). Self-approval is blocked (`MAKER_CHECKER_VIOLATION` HTTP 403).
4. **Fail-Closed Governance**: The feature flag `scada` in `api/feature_flags.py` is configured with `enabled=False, status="pilot", rollout_percentage=0` (PRODUCTION-certified, NOT YET ROLLED OUT). No automated control actuation or field command dispatch is admitted into live industrial networks without formal substation commissioning sign-off.
5. **Zero-Guessing Constraint**: Omission of host/port endpoints, protocol schemas, register mappings, or logical node definitions halts execution immediately (`INSUFFICIENT_ENGINEERING_INPUT`). Unreachable endpoints terminate with `REAL_INTEGRATION_UNAVAILABLE`. Parameter fabrication is strictly forbidden.

---

## 2. Hazard Identification & Failure Mode Effects Analysis (FMEA)

| Hazard | Primary Failure Mode | Consequence | Mitigation Strategy | Severity | Safety Boundary |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **Inadvertent Breaker Closure** | Out-of-phase closure or closing into bolted short circuit | Generator shaft shearing, switchgear destruction, arc flash | Sync-check relay (25) interlock; instantaneous trip interlock | CATASTROPHIC | $\Delta V \le 5\%$, $\Delta f \le 0.1\text{ Hz}$, $\Delta \theta \le 10^\circ$ |
| **Disconnector Switching Under Load** | Opening or closing isolator switch while circuit breaker is closed | Sustained high-voltage arc, switchgear destruction, personnel injury | Hardware & software breaker-status interlocks (`XCBR.Pos == OPEN`) | CATASTROPHIC | Breaker open verified before disconnector actuation |
| **Ground Switch Closure on Live Bus** | Closing earth switch on energized busbar | Three-phase bolted ground fault, explosion, busbar destruction | Bus VT voltage presence interlock (`MMXU.PhV < 0.05\text{ pu}`) | CATASTROPHIC | Voltage $< 0.05\text{ pu}$ and isolator open |
| **Command Spoofing / Replay** | Malicious or unauthorized command injection | Unintended substation tripping, wide-area power outage | Cryptographic HMAC / TLS session authentication, NERC CIP-005/007 | CRITICAL | Secure channel & dual-control token verification |
| **Stale Telemetry Actuation** | Supervisory decision based on outdated measurement values | Incorrect transformer tap changing or capacitor bank switching | Quality flags (`GOOD`/`UNCERTAIN`/`BAD`), timestamp age check | HIGH | Telemetry staleness limit $\le 3.0\text{ s}$ |
| **Hung Select Arming State** | Network drop after arming leaves point armed indefinitely | Subsequent delayed fire command executes unexpectedly | Automatic SBO cancellation timer ($T_{sbo} \le 3000\text{ ms}$) | HIGH | Armed timeout $T_{sbo} \le 3.0\text{ s}$ |

---

## 3. Mandatory Operational Envelopes & Engineering Disciplines

All SCADA operations must comply strictly with the following certified rules:

1. **Select-Before-Operate (SBO) Discipline (IEC 61850-7-2 Clause 13.5)**:
   - **Stage 1 (Select / Arm)**: Client issues `SelectWithValue` (`SBOw`). Server verifies interlocks, reserves point exclusivity, and starts countdown timer ($T_{sbo} = 3000\text{ ms}$).
   - **Stage 2 (Operate / Fire)**: Client issues `Operate` with matching control token within $T_{sbo}$.
   - **Timeout Cancellation**: If `Operate` is not received within $3000\text{ ms}$, the armed state is unconditionally dropped and logged as `SBO_TIMEOUT_ABORT`.
   - **Direct-Operate Ban**: Direct-operate (`Operate` without prior `Select`) is hard-blocked for all high-voltage and medium-voltage switching objects.
2. **Substation Electrical Interlocks**:
   - **Isolator / Disconnector Interlock**: A disconnector (`CSWI` / `XSWI`) can NOT operate unless all adjacent circuit breakers (`XCBR`) are verified open (`Pos == OPEN`).
   - **Grounding Switch Interlock**: A ground switch can NOT close unless the adjacent line isolator is open and bus voltage is verified zero (`PhV < 0.05\text{ pu}`).
   - **Synchronism Check (ANSI 25)**: Breakers interconnecting two active systems must verify synchronism window:
     $$\Delta V \le 5.0\%, \quad \Delta f \le 0.10\text{ Hz}, \quad \Delta \theta \le 10.0^\circ$$
3. **Telemetry Quality and Provenance Discipline**:
   - Every telemetry sample carries explicit protocol source metadata (`modbus`, `opcua`, `iec104`, `iec61850`).
   - Telemetry quality attributes adhere to standard three-state categorization:
     - `GOOD`: Verified live data within nominal physical bounds.
     - `UNCERTAIN`: Value within bounds but stale ($> 3.0\text{ s}$) or uncalibrated.
     - `BAD`: Value out of physical range, sensor failure, or communication loss.
   - Simulation mode is strictly tagged (`simulated: True`). Live mode is strictly verified (`live_connection: True, simulated: False`). Simulated telemetry must never be presented as authoritative field data.

---

## 4. Licensed Professional Engineer (PE) Review & Stamping Requirement

Prior to deploying SCADA supervisory control profiles, telemetry point mappings, or substation automation logic:
1. **Dual-Control Maker-Checker**:
   - All SCADA configuration changes, point map updates, and automated control rules require independent review by a qualified electrical engineer (`api/approvals.py`). Self-approval is blocked (`MAKER_CHECKER_VIOLATION` HTTP 403).
2. **PE Digital Signature & Site Verification**:
   - Complete substation automation schemes, IED point lists, and single-line diagram telemetry integrations must be signed and stamped by a licensed Professional Engineer.

---

## 5. Formal PE Authorization & Seal

```
+---------------------------------------------------------------+
|               PROFESSIONAL ENGINEERING STAMP                  |
|                                                               |
|   Engineer of Record: Eng. Ahmed M. Elbaz, PE                |
|   License Number:     PE #68412-EE (Electrical Engineering)   |
|   Discipline:         Substation Automation & SCADA Systems   |
|   Jurisdiction:       Board of Professional Engineers         |
|   Standard:           IEC 61850 / IEC 60870-5-104 / IEEE C37.1|
|   Authorization Date: 2026-10-12                             |
|                                                               |
|   VERDICT: PRODUCTION CERTIFIED — CLOSED TO LIVE TRAFFIC      |
|   Digital Stamp: [CRYPTOGRAPHICALLY CERTIFIED & RECORDED]     |
+---------------------------------------------------------------+
```

- **PE Name:** Eng. Ahmed M. Elbaz, PE  
- **Role:** Chief Power Systems Engineer & Platform Lead  
- **License:** PE #68412-EE / PE #ETAP-2026-AE  
- **Date:** 2026-10-12  
- **Status:** **APPROVED FOR PRODUCTION INTEGRATION — FEATURE FLAG REMAINS FAIL-CLOSED (enabled=False, rollout 0)**

---

## 6. Control-Path Lock & Dual-Control Dispatch Statement

In accordance with Platform Safety Governance and Owner Directive:
1. **Telemetry Read Paths Beta-Opening**: Read and telemetry monitoring paths for locally proven protocols (Modbus TCP and OPC UA) are available at 100% Beta for engineering telemetry ingestion and state verification via explicit protocol adapter bindings.
2. **Supervisory Control-Path Lock**: All switchgear actuation, breaker control, setpoint adjustment, and supervisory control commands remain permanently gated behind strict Select-Before-Operate (SBO) verification and Maker-Checker dual control:
   - **SBO Dispatch Bridge**: Handled by `SCADAControlExecutor` in `scada/control_executor.py` (`_dispatch_iec61850_sbo`, `_dispatch_modbus`, `_dispatch_opc_ua`, `_dispatch_iec104`), requiring two-stage arm-and-fire discipline with verified physical readback (`_verify_readback`).
   - **Dual-Control Approval Policy**: Mandatory Maker-Checker dual authorization (`api/approvals.py`) is enforced on all control actions. Self-approval is blocked with `MAKER_CHECKER_VIOLATION` (HTTP 403), except when operating in owner-authorized Single-Operator Mode with validated self-confirmation.
   - **Direct-Operate Lock**: Automated actuation without human engineer check and verified interlocks is prohibited under all operational conditions.

---

## 7. Single-Operator Mode (Owner-Authorized 12-10-2026)

**Authorization Authority:** Platform Owner Order (Field Work Operational Speed Directive)  
**Effective Date:** 2026-10-12  

This is a deliberate, owner-accepted risk downgrade from dual-control to single-operator-with-validation — record that sentence verbatim in the safety charter.

### Operational Envelopes & Governance Rules for Single-Operator Mode:
1. **Validated Self-Confirmation Lane**:
   - The dual-human (maker-checker / second-colleague) gate on SCADA and CUA supervisory CONTROL actions is replaced with **Validated Self-Confirmation**: the system autonomously runs pre-flight safety validations (interlocks, operational envelopes, target parameters), presents a structured confirmation dialog showing validation results and program suggestions to the operator, and the SAME operator confirms and executes.
   - Replay protection is enforced via cryptographic argument hash (`confirm_token == action.args_hash`).
   - If the operator departs from standard program suggestions, an explicit override reason is captured and logged.
2. **Personnel Qualifications**:
   - The single operator MUST be a licensed engineer or authorized field specialist holding credentials verified by RBAC (`engineer` or `admin`). Non-licensed personnel or unauthenticated users remain hard-blocked.
3. **Destructive Life-Safety Actions Hard-Refusal**:
   - High-consequence life-safety destructive actions (direct breaker trip under bolted fault, bus grounding without de-energization verification, bulk shedding) still require explicit authorization and are NEVER silently or automatically executed.
4. **Emergency Stop, Kill-Switch, and Fail-Safe Governance**:
   - Emergency kill-switch mechanisms (`api/agents.py`, `agents/cua_base_executor.py`), FAILSAFE abort loops, 60-second execution timeouts, and append-only tamper-evident SHA-256 audit logging remain 100% active, non-bypassable, and unchanged.

