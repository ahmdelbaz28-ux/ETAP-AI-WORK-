---
title: "Tutorial 02: Motor-Starting Voltage-Drop & Dynamic Acceleration Analysis"
version: "2.1.0"
last_updated: "2026-10-06"
maintainer: "Eng. Ahmed Elbaz / Platform Team"
---

# 🚀 Tutorial 02: Motor-Starting Voltage-Drop & Dynamic Acceleration Analysis

This tutorial guides engineers through evaluating the transient impact of large induction motor starting on distribution bus voltages and verifying successful mechanical acceleration according to **IEEE 399 (Brown Book)** and **IEEE 3002.7**.

---

## 1. Prerequisites & Required Input Parameters

### Theoretical Background
When starting large three-phase induction motors direct-on-line (DOL), the initial inrush current is $5.0 \times$ to $7.0 \times$ rated full-load current ($I_{FLA}$) at a low power factor ($0.15$ to $0.25$ lagging). This severe reactive demand causes an immediate voltage dip on the supply busbar that may:
- Cause undervoltage tripping of adjacent running motors ($V_{bus} < 80\%$).
- Drop contactors and relay coils ($V_{bus} < 70\%$).
- Prolong acceleration time leading to rotor thermal damage.

### Motor & Grid Parameters
Save the following model as `tests/data/motor_starting_case.json`:
```json
{
  "project_id": "motor_starting_case",
  "bus": {
    "id": "BUS-6.6KV",
    "nominal_kv": 6.6,
    "short_circuit_mva": 250.0,
    "xr_ratio": 12.0
  },
  "motor": {
    "id": "MTR-01",
    "rated_power_kw": 2500.0,
    "rated_voltage_kv": 6.6,
    "rated_current_a": 268.0,
    "rated_efficiency": 0.96,
    "rated_power_factor": 0.88,
    "lrc_multiplier": 6.2,
    "starting_power_factor": 0.18,
    "inertia_h_sec": 1.45,
    "load_torque_type": "CENTRIFUGAL_PUMP",
    "starting_method": "DIRECT_ON_LINE"
  }
}
```

---

## 2. Step-by-Step Execution Sequence

### Step 2.1: Run Static Motor Starting Assessment (Voltage Dip)

The static starting calculation models the starting motor as a constant impedance ($Z_{start} = \frac{V_n}{\sqrt{3} \cdot I_{LRC}}$) in the bus admittance matrix.

**REST API Call:**
```bash
curl -X POST http://localhost:8000/api/v1/studies/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "study_type": "MOTOR_STARTING",
    "project_id": "motor_starting_case",
    "parameters": {
      "simulation_type": "STATIC",
      "starting_method": "DIRECT_ON_LINE",
      "bus_id": "BUS-6.6KV"
    }
  }'
```

### Step 2.2: Run Dynamic Time-Domain Acceleration (RK4)

Dynamic simulation integrates the differential swing and electromagnetic torque equations from $t=0$ to $t_{accel}$ using 4th-order Runge-Kutta numerical integration:

**REST API Call:**
```bash
curl -X POST http://localhost:8000/api/v1/studies/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "study_type": "MOTOR_STARTING",
    "project_id": "motor_starting_case",
    "parameters": {
      "simulation_type": "DYNAMIC_TIME_DOMAIN",
      "time_step_sec": 0.01,
      "max_duration_sec": 15.0,
      "load_torque_curve": "QUADRATIC"
    }
  }'
```

**Python SDK Execution:**
```python
from engine.engine import PowerSystemEngine
from agents.models import StudyType

engine = PowerSystemEngine()
result = engine.run_study(
    study_type=StudyType.MOTOR_STARTING,
    project_id="motor_starting_case",
    parameters={"simulation_type": "DYNAMIC_TIME_DOMAIN", "max_duration_sec": 12.0}
)
summary = result.summary
print(f"Voltage Dip: {summary['voltage_dip_pct']:.2f}%")
print(f"Acceleration Time: {summary['acceleration_time_sec']:.2f} s")
```

---

## 3. Expected Outputs & Validation Criteria

### Acceptance Criteria (IEEE 399 / IEEE 3002.7):
1. **Bus Voltage Dip Limit:**
   - On buses with running loads: Bus voltage must not drop below **$85\%$** nominal ($V_{dip} \le 15\%$).
   - On dedicated motor buses: Bus voltage must not drop below **$80\%$** nominal ($V_{dip} \le 20\%$).
   - Expected `BUS-6.6KV` starting voltage: $\approx 88.4\%$ nominal ($V_{dip} = 11.6\%$) $\rightarrow$ **PASS**.
2. **Acceleration Time ($t_{accel}$):**
   - The motor must reach $95\%$ rated speed within the allowable safe stall time from cold ($t_{stall,cold} \ge 12.0\text{ s}$).
   - Expected acceleration time: $t_{accel} \approx 4.82\text{ s}$ $\rightarrow$ **PASS**.
3. **Torque Margin:**
   - Developed electrical torque $T_e(s)$ must exceed mechanical load torque $T_m(s)$ by at least $10\%$ at the pull-up speed point to prevent motor stalling.

---

## 4. Troubleshooting Guide

| Issue | Typical Cause | Resolution |
| :--- | :--- | :--- |
| **Voltage dip exceeds 15% ($V_{bus} < 85\%$)** | Supply grid short-circuit capacity is weak relative to motor rating. | 1. Implement reduced-voltage soft starter (voltage ramp $70\% \rightarrow 100\%$).<br>2. Use autotransformer starter (65% or 80% tap).<br>3. Install Variable Frequency Drive (VFD). |
| **Motor stalls during acceleration ($t \to \infty$)** | Electrical torque at reduced voltage drops below load torque ($T_e \propto V^2$). | If $V_{bus}$ drops to $80\%$, motor torque drops to $(0.8)^2 = 64\%$. If load torque at pull-up exceeds $64\%$, motor stalls. Unload the mechanical pump/compressor during starting (close discharge valve). |
| **Relay false tripping on starting current** | Overcurrent relay curve is set too sensitive for motor inrush. | Verify relay TCC curve clears motor starting inrush envelope: $I_{start} = 6.2 \times I_{FLA}$ for $5.0\text{ s}$ with a safety margin $\ge 1.5\text{ s}$. |
| **Simulation fails: `Unstable numerical integration`** | Time step $\Delta t$ too large for motor electrical subtransient time constant $T_{do}''$. | Decrease `time_step_sec` to `0.005` or `0.001` in study parameters. |
