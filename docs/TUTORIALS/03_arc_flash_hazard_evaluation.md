---
title: "Tutorial 03: Arc-Flash Hazard Evaluation under IEEE 1584-2018 and NFPA 70E"
version: "2.1.0"
last_updated: "2026-10-06"
maintainer: "Eng. Ahmed Elbaz / Platform Team"
---

# ⚡ Tutorial 03: Arc-Flash Hazard Evaluation (IEEE 1584-2018 & NFPA 70E)

This tutorial provides an end-to-end practical engineering guide to evaluating arc-flash hazards across low-voltage and medium-voltage industrial switchboards using AhmedETAP. The calculation engine implements the complete two-stage empirical model of **IEEE Std 1584-2018** (incorporating five electrode configurations) and classifies personal protective equipment (PPE) requirements in compliance with **NFPA 70E-2024**.

---

## 📋 Table of Contents

- [1. Prerequisites & Required Input Files](#1-prerequisites--required-input-files)
- [2. Step-by-Step Execution Sequence](#2-step-by-step-execution-sequence)
  - [Step 2.1: Run Arc-Flash Analysis via REST API](#step-21-run-arc-flash-analysis-via-rest-api)
  - [Step 2.2: Evaluate Arcing Current Variation](#step-22-evaluate-arcing-current-variation-100-vs-85--reduced)
- [3. Expected Outputs & Validation Criteria](#3-expected-outputs--validation-criteria)
- [4. Troubleshooting & Remediation](#4-troubleshooting--remediation)
- [5. Next Steps](#5-next-steps)

---

## 1. Prerequisites & Required Input Files

### System Requirements
- AhmedETAP API server running at `http://localhost:8000` (or Docker/Kubernetes cluster).
- User authentication token or API key (`X-API-Key`).
- Valid short-circuit study results (`bolted_fault_current_ka`, $X/R$ ratio) and protection trip clearance time ($T_{arc}$).

### Input Parameters for IEEE 1584-2018
IEEE Std 1584-2018 requires geometric enclosure parameters and electrode orientations:
1. **Electrode Configuration:**
   - `VCB`: Vertical conductors inside a metal box.
   - `VCBB`: Vertical conductors terminated in an insulating barrier inside a metal box.
   - `HCB`: Horizontal conductors inside a metal box (typically yields the highest incident energy).
   - `VOA`: Vertical conductors in open air.
   - `HOA`: Horizontal conductors in open air.
2. **Bus Gap ($G$):** Conductor spacing in mm (typically 13 mm for LV MCC, 25–32 mm for LV switchgear, 152 mm for 11 kV switchgear).
3. **Working Distance ($D$):** Distance from the prospective arc point to the worker's face/torso (typically 457 mm / 18 in for LV, 610 mm / 24 in for 400V/690V switchgear, 914 mm / 36 in for MV).
4. **Enclosure Dimensions:** Height ($H$), Width ($W$), Depth ($D_e$) in mm.
5. **Operating Voltage ($V_{sys}$):** Nominal system voltage (range 208 V to 15,000 V).
6. **Bolted 3-Phase Fault Current ($I_{bf}$):** Symmetrical RMS fault current in kA (range 0.5 kA to 106 kA).
7. **Arcing Duration ($t_{arc}$):** Clearing time in seconds determined by upstream protective relay/breaker characteristic curve.

### Input JSON Payload
Save the following input configuration as `tests/data/arcflash_switchgear_tutorial.json`:

```json
{
  "project_id": "industrial_plant_mcc_af",
  "study_type": "ARC_FLASH",
  "standard": "IEEE_1584_2018",
  "equipment": [
    {
      "bus_id": "MCC-400V-01",
      "voltage_kv": 0.40,
      "bolted_fault_current_ka": 28.5,
      "xr_ratio": 4.2,
      "electrode_config": "VCB",
      "bus_gap_mm": 25.0,
      "working_distance_mm": 457.0,
      "enclosure": {
        "height_mm": 508.0,
        "width_mm": 508.0,
        "depth_mm": 508.0
      },
      "upstream_protective_device": {
        "device_id": "ACB-INCOMER-01",
        "trip_time_sec": 0.12,
        "current_limiting": false
      }
    },
    {
      "bus_id": "SWG-11KV-01",
      "voltage_kv": 11.0,
      "bolted_fault_current_ka": 18.2,
      "xr_ratio": 12.0,
      "electrode_config": "HCB",
      "bus_gap_mm": 152.0,
      "working_distance_mm": 914.0,
      "enclosure": {
        "height_mm": 1143.0,
        "width_mm": 762.0,
        "depth_mm": 762.0
      },
      "upstream_protective_device": {
        "device_id": "RELAY-50_51-MV01",
        "trip_time_sec": 0.28,
        "current_limiting": false
      }
    }
  ]
}
```

---

## 2. Step-by-Step Execution Sequence

### Step 2.1: Run Arc-Flash Analysis via REST API

Execute the calculation by submitting the payload to the study execution endpoint:

```bash
curl -X POST "http://localhost:8000/api/v1/studies/run" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AHMEDETAP_API_KEY" \
  -d @tests/data/arcflash_switchgear_tutorial.json
```

Or invoke the Python specialist agent directly in an interactive shell or script:

```python
from agents.orchestrator import ChiefEngineeringOrchestrator
from agents.models import StudyRequest, StudyType

orchestrator = ChiefEngineeringOrchestrator()
request = StudyRequest(
    project_id="industrial_plant_mcc_af",
    study_type=StudyType.ARC_FLASH,
    parameters={
        "standard": "IEEE_1584_2018",
        "equipment_id": "MCC-400V-01",
        "voltage_kv": 0.40,
        "bolted_fault_current_ka": 28.5,
        "electrode_config": "VCB",
        "bus_gap_mm": 25.0,
        "working_distance_mm": 457.0,
        "enclosure_width_mm": 508.0,
        "enclosure_height_mm": 508.0,
        "enclosure_depth_mm": 508.0,
        "trip_time_sec": 0.12,
    }
)
result = orchestrator.execute(request)
print("Incident Energy (cal/cm2):", result.data["incident_energy_cal_cm2"])
print("Arc Flash Boundary (mm):", result.data["arc_flash_boundary_mm"])
print("PPE Category:", result.data["ppe_category"])
```

### Step 2.2: Evaluate Arcing Current Variation (100% vs 85% / Reduced)
IEEE 1584-2018 specifies that calculations must evaluate both:
1. Maximum arcing current $I_{arc}$ at nominal clearing time.
2. Reduced arcing current $I_{arc,min}$ (arcing current variation correction factor), because a lower current may result in a substantially longer clearing time on an inverse-time relay curve ($51$), producing **higher** incident energy.

AhmedETAP automatically evaluates both cases and reports the **worst-case** energy and boundary.

---

## 3. Expected Outputs & Validation Criteria

### Output Response Example
```json
{
  "status": "COMPLETED",
  "study_type": "ARC_FLASH",
  "standard": "IEEE_1584_2018",
  "results": [
    {
      "bus_id": "MCC-400V-01",
      "voltage_kv": 0.40,
      "arcing_current_ka": 20.45,
      "reduced_arcing_current_ka": 17.38,
      "clearing_time_sec": 0.12,
      "incident_energy_cal_cm2": 4.82,
      "arc_flash_boundary_mm": 1185.0,
      "arc_flash_boundary_in": 46.6,
      "nfpa_70e_category": "Category 2",
      "ppe_description": "Arc-rated clothing minimum 8 cal/cm², arc-rated face shield or hood, leather gloves, safety glasses, hearing protection.",
      "limited_approach_boundary_mm": 1000.0,
      "restricted_approach_boundary_mm": 300.0,
      "worst_case_condition": "Nominal Arcing Current"
    },
    {
      "bus_id": "SWG-11KV-01",
      "voltage_kv": 11.0,
      "arcing_current_ka": 15.62,
      "reduced_arcing_current_ka": 14.15,
      "clearing_time_sec": 0.28,
      "incident_energy_cal_cm2": 18.74,
      "arc_flash_boundary_mm": 3410.0,
      "arc_flash_boundary_in": 134.2,
      "nfpa_70e_category": "Category 3",
      "ppe_description": "Arc flash suit minimum 25 cal/cm², arc flash hood, safety glasses, hearing protection, leather protector gloves.",
      "limited_approach_boundary_mm": 1500.0,
      "restricted_approach_boundary_mm": 700.0,
      "worst_case_condition": "Reduced Arcing Current (Longer Relay Time)"
    }
  ]
}
```

### Engineering Acceptance Criteria
1. **Incident Energy Cutoff Thresholds (NFPA 70E-2024):**
   - $\le 1.2\text{ cal/cm}^2$: Category 0 / Non-arc rated non-melting natural fiber.
   - $> 1.2\text{ and } \le 4\text{ cal/cm}^2$: Category 1 (Min 4 cal/cm² rating).
   - $> 4\text{ and } \le 8\text{ cal/cm}^2$: Category 2 (Min 8 cal/cm² rating).
   - $> 8\text{ and } \le 25\text{ cal/cm}^2$: Category 3 (Min 25 cal/cm² rating).
   - $> 25\text{ and } \le 40\text{ cal/cm}^2$: Category 4 (Min 40 cal/cm² rating).
   - $> 40\text{ cal/cm}^2$: **DANGEROUS — NO PPE PERMITTED**. Energized work strictly prohibited until upstream mitigation (maintenance switch or optical arc sensor) lowers energy.
2. **2-Second Rule Cap (IEEE 1584 Clause B.2):**
   - If upstream protection clearing time exceeds 2.0 seconds, incident energy may be capped at 2.0 seconds provided personnel have unobstructed egress routes.
3. **Electrode Configuration Impact:**
   - Confirm that for switchgear with horizontal conductors (`HCB`), incident energy is substantially higher (typically $2\times$ to $3\times$ higher than `VCB`) because the plasma blast is directed horizontally toward the worker.

---

## 4. Troubleshooting & Remediation

| Issue Observed | Root Cause | Engineering Remediation |
| :--- | :--- | :--- |
| **Incident energy exceeds 40 cal/cm² (Dangerous)** | Relay trip time too slow ($t > 0.8\text{ s}$) due to coordination delay. | 1. Enable **Arc Flash Reduction Maintenance System (ARMS)** on incomer breaker (bypasses intentional time delay to achieve $< 50\text{ ms}$ instantaneous trip during maintenance).<br>2. Add optical light-detection arc flash relays.<br>3. Install zone-selective interlocking (ZSI). |
| **Reduced arcing current yields higher energy** | Reduced arcing current fell into the inverse-time pickup knee of standard IEC normal inverse curve. | AhmedETAP automatically identifies this condition. Review relay pickup $I_s$ to ensure reduced arcing current exceeds $2.5 \times I_s$, forcing instantaneous or short-time definite trip. |
| **Input Error: `Invalid electrode configuration`** | Missing or non-standard configuration string. | Valid IEEE 1584-2018 configurations are strictly: `VCB`, `VCBB`, `HCB`, `VOA`, `HOA`. Enclosed switchgear typically uses `VCB` (incoming cable compartment) or `HCB` (busbar compartment). |
| **Calculated boundary is 0 mm** | Bolted fault current below 500 A threshold or voltage $< 208\text{ V}$ where sustained arcing does not occur. | Verify transformer rating and source impedance; IEEE 1584-2018 notes that circuits under 240 V fed by transformers smaller than 125 kVA seldom sustain arc flash. |

---

## 5. Next Steps
- Export arc-flash equipment warning labels conforming to **ANSI Z535** and NFPA 70E Clause 130.5(H) via `POST /api/v1/reports/arc-flash-labels`.
- Link protection coordination curves from [Tutorial 01: Load-Flow to Protection](01_load_flow_short_circuit_protection.md) to automatically ingest calculated clearing times.
- Refer to [Platform Glossary](../GLOSSARY.md#ieee-1584) for standard definitions and terms.
