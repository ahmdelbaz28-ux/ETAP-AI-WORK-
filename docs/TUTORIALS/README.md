---
title: "AhmedETAP Engineering Tutorials"
version: "2.1.0"
last_updated: "2026-10-06"
maintainer: "Eng. Ahmed Elbaz / Platform Team"
---

# 📚 AhmedETAP Engineering Tutorials

Welcome to the **AhmedETAP Step-by-Step Engineering Tutorials**. These practical guides provide complete, reproducible workflows for running power systems simulations, standards compliance validations, and multi-agent studies.

---

## 🧭 Tutorial Index

| # | Tutorial | Primary Standards | Target System | Engineering Objectives |
| :-: | :--- | :--- | :--- | :--- |
| **01** | [**Load-Flow $\rightarrow$ Short-Circuit $\rightarrow$ Protection Coordination**](01_load_flow_short_circuit_protection.md) | IEEE 3002.7, IEC 60909, IEC 60255, IEEE 242 | 33kV/11kV/3.3kV Substation | Full sequential calculation pipeline: steady-state voltages, prospective fault currents ($I_k''$, $I_p$, $I_b$), and selective TCC relay curve grading. |
| **02** | [**Motor-Starting Voltage-Drop Analysis**](02_motor_starting_voltage_drop.md) | IEEE 399, IEC 60034-12 | 6.6 kV Medium-Voltage Induction Motor (2,500 kW) | Direct-on-Line (DOL) vs. Soft-Starter voltage sag assessment, busbar drop validation ($\Delta V \le 15\%$), and acceleration torque margin. |
| **03** | [**Arc-Flash Hazard Evaluation**](03_arc_flash_hazard_evaluation.md) | IEEE 1584-2018, NFPA 70E-2024 | 400V MCC & 11kV Switchgear | Two-stage IEEE 1584-2018 empirical model with VCB/HCB electrode geometry, reduced arcing current evaluation, PPE categorization, and boundary labeling. |

---

## 🛠️ Common Prerequisites & Environment Setup

All tutorials use the unified AhmedETAP Engineering Service REST API and Python multi-agent orchestration layer.

### 1. Launching the Engineering Service
```bash
# Start backend API service
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Authentication
Set your authorization header using an API Key or Bearer Token:
```bash
export AHMEDETAP_API_KEY="your-engineering-api-key"
```

### 3. Verification & Diagnostic Smoke Test
Before executing any study, check service health:
```bash
curl -s http://localhost:8000/api/v1/health | jq .
```
Expected output:
```json
{
  "status": "healthy",
  "engine": "ahmed_etap_core",
  "version": "2.1.0"
}
```

---

## 📖 Supporting References
- [API Reference Manual](../API_REFERENCE.md)
- [API Quick Reference Cheat-Sheet](../API_QUICKREF.md)
- [Platform Glossary](../GLOSSARY.md)
- [Documentation Standards](../DOCUMENTATION_STANDARDS.md)
