# Digital Twin Calibration and Operational Limits

## Scope and Standards
- **Standard Frameworks**: ISO 23247 (Digital Twin Manufacturing Framework), IEC 63278 (Asset Administration Shell), IEC 61850 (Substation Automation & Telemetry).
- **Benchmark Classification**: `NONE` (Operational synchronization; no theoretical IEEE benchmark claim).
- **Status**: `PILOT` (Silent-Observer).

---

## Operational Characterization and Architectural Limits
1. **Silent-Observer Only**:
   - The Digital Twin engine runs exclusively in observation, telemetry tracking, and predictive drift assessment mode.
   - **Zero Actuation**: Under no circumstances does the engine write back to network models, execute automated breaker switching, or command generation setpoint modifications.
2. **Sampling Resolution & Delay**:
   - Polling and snapshot retention resolution is strictly bounded to **5 seconds**.
   - Sub-second / millisecond-level dynamic transient control is NOT supported.
3. **Data Freshness and Anti-Fabrication Gate**:
   - Telemetry data must be fresh (age $\le$ 30 seconds) and free of `BAD` quality flags.
   - If stale data (> 30s) or invalid telemetry quality is encountered, execution fails closed with `STALE_DATA`.
   - The engine strictly refuses to fabricate or interpolate synthetic measurements in live operational contexts.
4. **Human-in-the-Loop Requirement**:
   - When Model Deviation Index exceeds acceptable bounds ($\text{MDI} > 0.15$), the system emits advisory drift flags and calibration suggestions.
   - Physical model recalibration and engineering stamp require licensed professional engineer review.

---

## Metric Tolerances & Drift Classification
| Metric | Threshold | Classification | Action |
|---|---|---|---|
| MDI | $< 0.05$ | Synchronized | Nominal operational tracking |
| MDI | $0.05 \le \text{MDI} < 0.10$ | Minor Drift | Monitored |
| MDI | $0.10 \le \text{MDI} < 0.15$ | Moderate Drift | Advisory alert |
| MDI | $> 0.15$ | Significant Drift | Warning flag + Human calibration suggestion |
| Age | $> 30\text{ s}$ | Stale Telemetry | Immediate fail-closed (`STALE_DATA`) |

---

## Multi-Tenant Isolation
- Time-series and switching topology states are partitioned per tenant prefix (`f"{tenant_id}:"`).
- Cross-tenant queries return strictly empty structures, preventing cross-tenant telemetry exposure.
