# Generative Design Safety Charter & PE Risk Acceptance Policy

**Document ID:** SAFETY-GD-001  
**Classification:** HIGH RISK / RESTRICTED SCAFFOLD  
**Standard Compliance:** IEEE 141, IEEE 242, IEC 62271, IEC 60076, IEC 60364  
**Date:** 2026-10-07  
**Authority:** Platform Safety Board / Licensed Professional Engineering (PE) Committee  

---

## 1. Executive Safety Summary

The `generative_design` capability (`StudyType.GENERATIVE_DESIGN`) performs parametric synthesis of substation topologies, single-line diagrams (SLD), transformer ratings, and protection scheme allocations.

Due to the critical life-safety, arc flash, and equipment damage risks inherent in automated electrical infrastructure generation:
1. **Scaffold Status**: `generative_design` is currently an unvalidated parametric scaffold (Commit `7617d30be`). It does not modify production topologies directly.
2. **Fail-Closed Gate**: The feature flag `generative_design` is set to `enabled=False` by default in `api/feature_flags.py`. All execution attempts without explicit override fail closed (`AgentStatus.FAILED` with `reason="flag_disabled"`).
3. **Strict Gate Enforcement**: The capability must NEVER be bypassed using mock flags in production. It is protected by `is_strict_feature_enabled("generative_design")`.

---

## 2. Licensed Professional Engineer (PE) Review Requirement

Prior to activating this capability for any customer tenant or production environment, the following conditions are legally and technically mandatory:

1. **Dual-Control Maker-Checker**:
   - Every generated single-line topology must undergo mandatory secondary engineering review (`api/approvals.py`).
   - Self-approval by the generating user/agent is permanently blocked (`MAKER_CHECKER_VIOLATION` HTTP 403).
2. **Digital PE Stamp Mandate**:
   - Generated topologies cannot be exported for fabrication or utility interconnect without a cryptographic digital signature from a licensed Professional Engineer (`api/pe_stamp.py`).
   - Non-authoritative runs are strictly refused by the stamping engine (`CANNOT_CERTIFY_NON_AUTHORITATIVE`).
3. **Physical Protection Coordination Cross-Check**:
   - All synthesized transformer and feeder ratings must be back-tested against deterministic IEC 60909 short-circuit breaking capacity and IEEE 1584 incident energy calculations.

---

## 3. Risk Assessment Matrix

| Hazard | Consequence | Mitigation Strategy | Severity | Enforcement |
| :--- | :--- | :--- | :---: | :--- |
| **Undersized Switchgear** | Catastrophic breaker failure / Arc flash explosion | Enforce IEC 62271 breaking capacity assertions | CRITICAL | Programmatic assertion |
| **Inadequate Protection Clearance** | Unselective fault tripping / Blackout | Require IEC 60255 selectivity margin >= 300ms | HIGH | EngineeringAssertionLayer |
| **Unverified Topology Drift** | Incompatible substation bus configurations | Fail closed if topology missing required bus data | HIGH | Pre-solver validation |
| **Hallucinatory Generation** | Fabricated impedance or thermal constants | Zero-guessing rule strictly active (no default values) | CRITICAL | Schema validation |

---

## 4. Formal Risk Acceptance Sign-Off

Activation in any staging or production environment requires written sign-off from the Lead Electrical Engineer:

- **Approving Authority**: Eng. Ahmed Elbaz (Platform Chief Engineer)
- **Role**: Lead Systems Architect & Platform Core Team Lead
- **Status**: CONDITIONAL APPROVAL FOR ISOLATED TESTING ONLY — PRODUCTION AUTOMATION FORBIDDEN
