---
title: "AhmedETAP Quick Start Guide"
version: "2.1.0"
last_updated: "2026-10-06"
maintainer: "Eng. Ahmed Elbaz / Platform Core Team"
---

# 🚀 AhmedETAP Platform — Quick Start Guide

**AhmedETAP Virtual Power System Engineering Platform v2.1.0**

[English](QUICKSTART.md) | [العربية](../QUICKSTART.ar.md)

---

## 📋 Table of Contents

- [1. Prerequisites](#1-prerequisites)
- [2. Installation & Setup](#2-installation--setup)
- [3. Running Your First Study](#3-running-your-first-study)
- [4. Step-by-Step Engineering Tutorials](#4-step-by-step-engineering-tutorials)
- [5. API Access & Programmatic Execution](#5-api-access--programmatic-execution)
- [6. Verification & Troubleshooting](#6-verification--troubleshooting)
- [7. Reference Links](#7-reference-links)

---

## 1. Prerequisites

- **Python**: 3.12 or 3.13 (64-bit)
- **Node.js**: 20+ (with `pnpm` or `npm`)
- **Git**: 2.30+
- **Docker & Docker Compose**: (Optional, for containerized deployments)

---

## 2. Installation & Setup

### Method 1: Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
   cd ETAP-AI-WORK-
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and configure JWT_SECRET_KEY and ENGINEERING_SERVICE_API_KEY
   ```

3. **Install Python dependencies:**
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Start the FastAPI backend:**
   ```bash
   uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Start the Chat-First v3.0 frontend:**
   ```bash
   cd ui
   pnpm install
   pnpm run dev
   # Open browser at http://localhost:5173
   ```

### Method 2: Docker Compose

```bash
git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
cd ETAP-AI-WORK-
docker compose up -d
# Access the platform at http://localhost:8000
```

---

## 3. Running Your First Study

### In-Chat Natural Language Query
Navigate to the ChatWorkspace UI at `http://localhost:5173` and type:
```text
Run load flow on the IEEE 9-bus WSCC test feeder with 0.001 MVA convergence tolerance.
```
The Coordinator Agent will parse your request, route it to the Load Flow Agent, execute the Newton-Raphson solver via `engine/dispatch.py`, and return structured bus voltages, loading percentages, and compliance tables.

---

## 4. Step-by-Step Engineering Tutorials

For deep-dive, industry-grade workflows with full sample input payloads and troubleshooting steps, explore our dedicated tutorials in [`TUTORIALS/`](TUTORIALS/):

1. **[Tutorial 01: Load-Flow $\rightarrow$ Short-Circuit $\rightarrow$ Protection Coordination](TUTORIALS/01_load_flow_short_circuit_protection.md)**  
   *Standards:* [IEEE 3002.7](GLOSSARY.md#ieee-30027), [IEC 60909](GLOSSARY.md#iec-60909), [IEC 60255](GLOSSARY.md#iec-60255).  
   *Scope:* Complete power flow simulation, symmetrical/asymmetrical fault current calculation ($I_k''$, $I_p$, $I_b$), and TCC relay grading with coordination time interval (CTI) verification.

2. **[Tutorial 02: Motor-Starting Voltage-Drop Analysis](TUTORIALS/02_motor_starting_voltage_drop.md)**  
   *Standards:* [IEEE 399](GLOSSARY.md#ieee-399), IEC 60034-12.  
   *Scope:* Direct-on-Line (DOL) vs. Soft-Starter acceleration simulation, bus voltage dip validation ($\Delta V \le 15\%$), and motor acceleration torque margins.

3. **[Tutorial 03: Arc-Flash Hazard Evaluation](TUTORIALS/03_arc_flash_hazard_evaluation.md)**  
   *Standards:* [IEEE 1584](GLOSSARY.md#ieee-1584), [NFPA 70E](GLOSSARY.md#ppe).  
   *Scope:* Full IEEE 1584-2018 empirical model with VCB/HCB electrode geometry, reduced arcing current evaluation, incident energy ($cal/cm^2$), and PPE category labeling.

---

## 5. API Access & Programmatic Execution

Submit a study directly via `curl`:
```bash
curl -X POST http://localhost:8000/api/v1/studies/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ENGINEERING_SERVICE_API_KEY" \
  -d '{
    "study_type": "load_flow",
    "parameters": {
      "system_id": "ieee_9bus",
      "max_iterations": 20,
      "tolerance": 0.001
    }
  }'
```

Refer to the [API Quick Reference Cheat-Sheet](API_QUICKREF.md) and the [Canonical API Reference](API_REFERENCE.md) for full endpoint specifications.

---

## 6. Verification & Troubleshooting

Run the platform diagnostic test suite:
```bash
pytest tests/ -q -k "test_health or test_load_flow or test_short_circuit"
```

If you encounter issues:
- Check backend connectivity at `http://localhost:8000/api/v1/health`.
- Consult the [Operations Runbook](OPERATIONS_RUNBOOK.md) and [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md).

---

## 7. Reference Links

- [Platform Glossary](GLOSSARY.md)
- [Canonical API Reference](API_REFERENCE.md)
- [API Quick Reference](API_QUICKREF.md)
- [Contributing Guidelines](../CONTRIBUTING.md)
- [Arabic Quick Start Guide](../QUICKSTART.ar.md)