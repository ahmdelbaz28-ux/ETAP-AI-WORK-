# AhmedETAP Trust & Engineering Integrity Charter
**Document Ref: TC-2026-V1**  
**Core Invariant: Engineering Honesty > Aesthetics**

---

## 1. Principles of Engineering Trust

Power system engineering governs physical infrastructure where errors carry life-safety, equipment damage, and cascading blackout risks. AhmedETAP is constructed around an unyielding engineering philosophy:

1. **Zero Mock Fallbacks / Zero Synthetic Data**: No calculation output shown to an engineer may ever be fabricated or mocked. When a calculation fails, the system fails closed with transparent error reporting rather than presenting plausible-looking synthetic data.
2. **Proven Empirical Veracity**: Every engineering claim cited in the platform is backed by deterministic automated tests against published reference benchmarks (IEEE 3002.7, IEC 60909, IEEE 1584, etc.).
3. **Traceability & Attribution**: Every result links to its computation source, input parameters, timestamp, and standard version.

---

## 2. MathGuard Scope & Dual-Runtime Isolation

AhmedETAP maintains strict segregation between language model reasoning and numerical mathematics:

```
[ User / Engineer ] 
         │
         ▼
[ Mastra TypeScript Orchestrator ]  <─── Strict Tool Policies & Dual-Control Guards
         │
         │ Dispatches structured JSON parameters
         ▼
[ Python MathGuard Numerical Core ]  <─── Deterministic Solvers (Newton-Raphson, IEC 60909, IEEE 1584)
         │
         ▼
[ Cryptographic PE Stamp & Validation ]
```

### MathGuard Invariants:
- **Zero Hallucination in Math**: Large Language Models NEVER perform electrical calculations directly. They parse user intent, structure inputs, and delegate exclusively to verified Python numerical engines.
- **Strict Parameter Validation**: If an electrical parameter is missing (e.g. conductor gap, fault duration, bus impedance), the system prompts the engineer for clarification instead of guessing.

---

## 3. Professional Engineer (PE) Stamp Workflow

Regulated electrical studies (Load Flow, Short Circuit, Arc Flash, Protection Coordination) support the PE Stamp certification pipeline defined in [`api/pe_stamp.py`](file:///c:/Users/EWS-01/Desktop/etap/api/pe_stamp.py).

### Integrity Features:
- **Deterministic SHA-256 Digest**: Computes a cryptographic checksum of the complete input topology and numerical results.
- **Engineer Metadata**: Binds the report to licensed engineer credentials, license ID, jurisdiction, and date.
- **Compliance Statement**: Attests strict adherence to governing standards:
  > *"Calculations executed in strict conformance with IEEE Std 3002.7, IEC 60909:2016, IEEE 1584-2018, and NFPA 70E standards."*
- **Tamper Evidence**: Any subsequent modification of calculation parameters or outputs invalidates the digital stamp.

---

## 4. Fail-Closed Security Policy

To safeguard operational networks and proprietary industrial assets, the platform operates under strict fail-closed security gates:

1. **Provenance Enforcement**: Tool executions require explicit provenance metadata (`source: user_input | project_data | computed | standard`). Tool invocations lacking verified source provenance are rejected with `HTTP 422 Unprocessable Entity`.
2. **Permanent Denial of Dangerous Tools**: System shell executions (`powershell-tool`, `node-tool`, arbitrary command execution) are permanently blocked (`HTTP 403 HARD_DENIED`).
3. **Dual-Control Maker-Checker**: High-consequence operational mutations (breaker trip configurations, relay setting modifications, live SCADA commands) require dual-operator authorization before execution (`HTTP 403 MAKER_CHECKER_VIOLATION` if single-party approved).
4. **Tenant Isolation**: Multi-tenant data segregation is strictly enforced via cryptographic project-level tenant tagging (`tenant_id`). Cross-tenant access is structurally impossible.

---

## 5. Security & Responsible Disclosure

For full security policy details, vulnerability reporting protocols, and secrets rotation audit history, refer to:
- [`SECURITY.md`](file:///c:/Users/EWS-01/Desktop/etap/SECURITY.md)
