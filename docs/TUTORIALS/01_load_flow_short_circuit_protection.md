---
title: "Tutorial 01: Load-Flow to Short-Circuit to Protection Coordination Workflow"
version: "2.1.0"
last_updated: "2026-10-06"
maintainer: "Eng. Ahmed Elbaz / Platform Team"
---

# 튜 Tutorial 01: Load-Flow $\rightarrow$ Short-Circuit $\rightarrow$ Protection Coordination

This tutorial walks through an end-to-end industrial power engineering study workflow across three chained modules:
1. **Load Flow Analysis** (IEEE 3002.7 / Newton-Raphson) to establish steady-state voltage profiles and nominal currents.
2. **Short-Circuit Calculation** (IEC 60909) to compute maximum and minimum prospective fault currents across all busbars.
3. **Protection Coordination** (IEC 60255 / IEEE 242) to configure time-current characteristic (TCC) relay curves and guarantee selective tripping.

---

## 📋 Table of Contents

- [1. Prerequisites & Required Input Files](#1-prerequisites--required-input-files)
- [2. Step-by-Step Execution Sequence](#2-step-by-step-execution-sequence)
  - [Step 2.1: Run Steady-State Load Flow](#step-21-run-steady-state-load-flow-ieee-30027)
  - [Step 2.2: Compute Maximum Fault Currents](#step-22-compute-maximum-fault-currents-iec-60909)
  - [Step 2.3: Verify Protection Grading](#step-23-verify-protection-grading-iec-60255)
- [3. Expected Outputs & Validation Criteria](#3-expected-outputs--validation-criteria)
- [4. Troubleshooting & Remediation](#4-troubleshooting--remediation)
- [5. Summary & Next Steps](#5-summary--next-steps)

---

## 1. Prerequisites & Required Input Files

### System Requirements
- AhmedETAP platform running locally at `http://localhost:8000` or production URL.
- Python 3.12+ (or Node.js 22+ for CLI/Mastra).
- Valid JWT token or API key (`X-API-Key`).

### Input Network Model
We use a standard 33kV/11kV/3.3kV industrial distribution substation single-line diagram (`substation_alpha.json`):
- **Grid Infeed:** 33 kV, 500 MVA short-circuit capacity, $X/R = 10$.
- **Transformer T1:** 20 MVA, 33/11 kV, $Z = 8.5\%$, Dyn11.
- **Switchboard 11kV:** Main Incomer CB, Bus-Tie, Feeder to 3.3kV Transformer T2 (5 MVA, 11/3.3 kV, $Z = 6.0\%$).
- **Loads:** 12 MVA total connected load on 11kV bus; 3.5 MW induction motor on 3.3kV bus.

Save the following file as `tests/data/substation_tutorial.json`:
```json
{
  "project_id": "substation_tutorial",
  "system": {
    "base_mva": 100.0,
    "buses": [
      {"id": "BUS-33KV", "vn_kv": 33.0, "type": "SLACK", "v_mag_pu": 1.0, "v_ang_deg": 0.0},
      {"id": "BUS-11KV", "vn_kv": 11.0, "type": "PQ", "pl_mw": 12.0, "ql_mvar": 4.5},
      {"id": "BUS-3.3KV", "vn_kv": 3.3, "type": "PQ", "pl_mw": 3.5, "ql_mvar": 1.2}
    ],
    "transformers": [
      {"id": "T1", "from_bus": "BUS-33KV", "to_bus": "BUS-11KV", "s_mva": 20.0, "v_pri_kv": 33.0, "v_sec_kv": 11.0, "z_pct": 8.5, "xr_ratio": 15.0},
      {"id": "T2", "from_bus": "BUS-11KV", "to_bus": "BUS-3.3KV", "s_mva": 5.0, "v_pri_kv": 11.0, "v_sec_kv": 3.3, "z_pct": 6.0, "xr_ratio": 10.0}
    ]
  }
}
```

---

## 2. Step-by-Step Execution Sequence

### Step 2.1: Run Steady-State Load Flow (IEEE 3002.7)

Execute the study via the REST API or Python orchestrator:

**REST API Call:**
```bash
curl -X POST http://localhost:8000/api/v1/studies/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "study_type": "LOAD_FLOW",
    "project_id": "substation_tutorial",
    "parameters": {
      "method": "NEWTON_RAPHSON",
      "max_iterations": 25,
      "tolerance": 0.0001,
      "acceleration_factor": 1.0
    }
  }'
```

**Python SDK Execution:**
```python
from engine.engine import PowerSystemEngine
from agents.models import StudyRequest, StudyType

engine = PowerSystemEngine()
result = engine.run_study(
    study_type=StudyType.LOAD_FLOW,
    project_id="substation_tutorial",
    parameters={"method": "NEWTON_RAPHSON", "tolerance": 1e-4}
)
print(f"Converged in {result.summary['iterations']} iterations.")
print("Bus Voltages:", result.summary["bus_voltages"])
```

### Step 2.2: Compute Maximum Fault Current (IEC 60909)

Use the steady-state voltages to initialize the IEC 60909 impedance network and calculate short-circuit currents at `BUS-11KV` and `BUS-3.3KV`:

**REST API Call:**
```bash
curl -X POST http://localhost:8000/api/v1/studies/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "study_type": "SHORT_CIRCUIT",
    "project_id": "substation_tutorial",
    "parameters": {
      "standard": "IEC_60909",
      "fault_type": "3PHASE",
      "c_factor": 1.10,
      "target_buses": ["BUS-11KV", "BUS-3.3KV"]
    }
  }'
```

### Step 2.3: Verify Protection Relay Coordination (IEC 60255)

Grade upstream Incomer Relay `RELAY-T1` against downstream Feeder Relay `RELAY-T2`:

**REST API Call:**
```bash
curl -X POST http://localhost:8000/api/v1/studies/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "study_type": "PROTECTION_COORDINATION",
    "project_id": "substation_tutorial",
    "parameters": {
      "standard": "IEC_60255",
      "curve_type": "STANDARD_INVERSE",
      "pairs": [
        {
          "upstream_relay": "RELAY-T1",
          "downstream_relay": "RELAY-T2",
          "fault_bus": "BUS-3.3KV",
          "min_cti_seconds": 0.30
        }
      ]
    }
  }'
```

---

## 3. Expected Outputs & Validation Criteria

### Load Flow Acceptance Criteria:
- **Convergence:** Algorithm must converge within $\le 6$ iterations.
- **Voltage Limits:** All bus voltages must remain within $[0.95, 1.05]$ p.u.
  - Expected `BUS-11KV`: $\approx 0.982$ p.u.
  - Expected `BUS-3.3KV`: $\approx 0.965$ p.u.
- **Line/Transformer Loading:** Neither transformer must exceed $100\%$ rated MVA.
  - T1 Loading: $\approx 78.5\%$ (15.7 MVA).
  - T2 Loading: $\approx 74.0\%$ (3.7 MVA).

### Short-Circuit Acceptance Criteria (IEC 60909):
- **`BUS-11KV` Initial Symmetrical Short-Circuit Current ($I_k''$):** $\approx 12.35$ kA.
- **`BUS-11KV` Peak Making Current ($i_p$):** $\approx 31.5$ kA ($X/R \approx 14$).
- **`BUS-3.3KV` Initial Symmetrical Short-Circuit Current ($I_k''$):** $\approx 14.6$ kA.

### Protection Coordination Criteria:
- **Coordination Time Interval (CTI):** Margin between `RELAY-T1` and `RELAY-T2` must be $\ge 0.30\text{ s}$ across the full fault current range up to $I_{k,\max}''$.
- **Trip Discrimination:** At $I_{fault} = 14.6\text{ kA}$ on `BUS-3.3KV`:
  - `RELAY-T2` (Downstream): Trips at $t_1 = 0.12\text{ s}$.
  - `RELAY-T1` (Upstream Incomer): Operates at $t_2 = 0.45\text{ s}$.
  - Margin $\Delta t = 0.33\text{ s} \ge 0.30\text{ s}$ (**PASS**).

---

## 4. Troubleshooting Guide

| Issue | Typical Cause | Resolution |
| :--- | :--- | :--- |
| **Load flow diverges (`Max iterations exceeded`)** | Unrealistic load on high impedance, or missing Slack bus. | Verify one bus has `"type": "SLACK"`. Increase `max_iterations: 50`. Check transformer $Z_{pct}$ decimal formatting. |
| **Bus voltage $< 0.90$ p.u.** | Excessive reactive power demand or undersized transformer. | Add power-factor correction capacitor bank at `BUS-11KV` or adjust transformer tap changer ($+2.5\%$). |
| **Short-circuit current exceeds switchgear rating** | System fault level too high for standard 25kA breaker. | Consider current-limiting reactor or select 31.5kA / 40kA rated switchgear under IEC 62271. |
| **Protection selectivity overlap ($\Delta t < 0.25\text{s}$)** | Downstream Time Multiplier Setting (TMS) set too high. | Reduce downstream TMS or switch upstream curve to Very Inverse (`IEC_VERY_INVERSE`) to steepen grading slope. |
