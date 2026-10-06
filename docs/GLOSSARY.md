---
title: "AhmedETAP — Engineering Glossary & Terminology Index"
version: "2.1.0"
last_updated: "2026-10-06"
maintainer: "Eng. Ahmed Elbaz / Platform Team"
---

# 📖 AhmedETAP Engineering Glossary & Terminology Index

This glossary defines standard industry engineering abbreviations, international electrical codes, and platform-specific terminology used across the AhmedETAP platform and its technical documentation.

## Table of Contents
- [Section 1: Abbreviations & Standards](#section-1-abbreviations--standards)
  - [International Standards (IEC & IEEE)](#international-standards-iec--ieee)
  - [Power Systems & Operational Technology (OT)](#power-systems--operational-technology-ot)
  - [Artificial Intelligence & Software Architecture](#artificial-intelligence--software-architecture)
- [Section 2: Platform-Specific Terms](#section-2-platform-specific-terms)
  - [Core Platform Concepts](#core-platform-concepts)
  - [Security, Safeguards & Orchestration](#security-safeguards--orchestration)

---

## Section 1: Abbreviations & Standards

### International Standards (IEC & IEEE)

#### IEC 60909
International standard governing short-circuit current calculations in three-phase AC systems. AhmedETAP implements driving-point impedance matrix formulation, calculating initial symmetrical fault current ($I_k''$), peak making current ($i_p$), and thermal equivalent current ($I_{th}$) without parameter guessing.

#### IEC 60255
International standard series specifying requirements for measuring relays and protection equipment, including inverse-time characteristics, trip grading, and directional overcurrent selectivity curves.

#### IEC 61850
International communication standard for electrical substation automation systems. AhmedETAP's SCADA agent parses and maps Logical Nodes (LN), data objects (DO), and GOOSE/MMS communication profiles to real-time Digital Twin states.

#### IEC 60364
International standard for low-voltage electrical installations, covering conductor ampacity selection, continuous thermal derating factors, and permissible voltage-drop limits under load.

#### IEC 62271
High-voltage switchgear and controlgear standard governing circuit breaker breaking capacity, short-time withstand current, transient recovery voltage (TRV), and making current ratings.

#### IEC 60076
Power transformers standard covering temperature rise, loss evaluation, impedance tolerances, short-circuit withstand capabilities, and tapping range parameters.

#### IEC 62933
Standard specifying planning, design, and integration of electrical energy storage (EES) and battery storage systems (BESS) into utility grids.

#### IEC 61363
Standard for electrical installations on ships and offshore drilling units, accounting for AC generator subtransient decrement and excitation system dynamics during short circuits.

#### IEC 61660
Standard for calculating short-circuit currents in DC auxiliary installations, battery banks, and rectifiers in power stations and industrial substations.

#### IEC 62351
Power systems management and information exchange standard covering end-to-end data integrity, role-based access control, and cryptographic authentication across SCADA and IEC 61850 protocols.

#### IEEE 1584
IEEE Guide for Performing Arc-Flash Hazard Calculations (2018 revision). Determines incident energy ($cal/cm^2$), arc-flash protection boundary (AFB), working distance, and required Personal Protective Equipment (PPE) categories using empirical enclosure configurations (VCB, VCBB, HCB, VOA, HOA).

#### IEEE 399
Known as the IEEE "Brown Book" — Recommended Practice for Industrial and Commercial Power Systems Analysis. Standard reference for dynamic motor starting, voltage dip assessment, and transient stability simulation.

#### IEEE 3002.7
IEEE Recommended Practice for Conducting Load Flow Studies in Industrial and Commercial Power Systems. Specifies Newton-Raphson and Fast-Decoupled convergence tolerances, bus classifications (Slack, PV, PQ), and voltage profile criteria.

#### IEEE 519
Standard for Harmonic Control in Electric Power Systems. Sets limits on Total Harmonic Distortion ($THD_V$, $THD_I$) and Total Demand Distortion (TDD) at the Point of Common Coupling (PCC).

#### IEEE 80
IEEE Guide for Safety in AC Substation Grounding. Governs human safety limits for touch voltage ($E_{touch}$) and step voltage ($E_{step}$) using surface layer resistivity and fault duration criteria.

#### IEEE 141
Known as the IEEE "Red Book" — Recommended Practice for Electric Power Distribution for Industrial Plants. Guides substation topology synthesis, transformer sizing, and system reliability architecture.

#### IEEE 242
Known as the IEEE "Buff Book" — Recommended Practice for Protection and Coordination of Industrial and Commercial Power Systems. Standard reference for time-current curve (TCC) coordination time intervals (CTI).

#### IEEE 1547
Standard for Interconnection and Interoperability of Distributed Energy Resources (DER) with Associated Electric Power Systems Interfaces. Defines voltage and frequency ride-through curves and anti-islanding trip times.

---

### Power Systems & Operational Technology (OT)

#### SCADA
**Supervisory Control and Data Acquisition.** An industrial automation control system architecture used to monitor and collect real-time data from field sensors, RTUs, and IEDs, transmitting setpoints and status to central operators.

#### ADMS
**Advanced Distribution Management System.** An enterprise software platform integrating distribution SCADA, outage management (OMS), and distribution management (DMS) with automated Volt/VAR optimization and fault location, isolation, and service restoration (FLISR).

#### BESS
**Battery Energy Storage System.** Electrochemical energy storage installations (e.g. Lithium-iron-phosphate or flow batteries) modeled with round-trip efficiency, state of charge (SoC), C-rate, and bi-directional inverter dispatch.

#### DER
**Distributed Energy Resources.** Small-to-medium scale generation or storage units connected directly to the distribution system or customer premises, such as rooftop solar PV, wind turbines, and microturbines.

#### SLD
**Single-Line Diagram.** A simplified notation for a three-phase power system where electrical elements (generators, buses, lines, transformers, circuit breakers) are represented by standardized single-line graphic symbols.

#### RTU
**Remote Terminal Unit.** A microprocessor-controlled electronic device in substations that interfaces field sensors and actuators to a distributed control system or SCADA master.

#### OPF
**Optimal Power Flow.** A mathematical optimization framework that adjusts controllable system variables (generator dispatch, transformer taps, capacitor banks) to minimize generation cost or transmission losses subject to physical grid constraints.

#### GIS
**Geographic Information System.** A geospatial system designed to capture, store, analyze, and manage geographical distribution assets, overhead lines, underground cables, and substation boundaries (compatible with PostGIS, ArcGIS Pro, and QGIS).

#### CTI
**Coordination Time Interval.** The intentional time delay (typically 0.20s to 0.40s) maintained between adjacent downstream and upstream protective devices on a Time-Current Characteristic (TCC) curve to guarantee selective isolation of faulted sections.

#### PPE
**Personal Protective Equipment.** Specialized protective gear (rated in $cal/cm^2$) worn by electrical workers based on calculated incident energy to mitigate arc-flash burn injuries (Categories 1 through 4 under NFPA 70E).

---

### Artificial Intelligence & Software Architecture

#### Mastra
A TypeScript-based agentic framework running in Node.js runtime (`src/mastra/agents/`) that provides structured LLM orchestration, semantic routing, tool execution boundaries, and human-in-the-loop workflows.

#### Goal Planner
A specialized meta-agent (`goal-planner-agent`) that ingests complex natural language engineering objectives and translates them into structured, prioritized task lists executed sequentially by specialist agents.

#### CUA
**Computer-Use Agent.** An agentic automation system that interacts with graphical user interfaces (desktop ETAP, browser apps) via mouse movement, clicks, and keystrokes equipped with emergency kill-switch safeguards.

#### OTel
**OpenTelemetry.** An open-source observability framework comprising APIs, SDKs, and tools to instrument, generate, and export telemetry data (traces, metrics, logs) to platforms like Jaeger and Prometheus.

#### Model2Vec
A lightweight, high-speed sentence embedding architecture utilized by AhmedETAP's RAG system for local semantic indexing and retrieval of engineering standards with sub-millisecond latency.

#### RAG
**Retrieval-Augmented Generation.** An AI architectural pattern that retrieves relevant normative text, clause definitions, and equipment datasheets from dense vector databases to ground LLM reasoning in verified engineering facts.

---

## Section 2: Platform-Specific Terms

### Core Platform Concepts

#### ETAP Expert Skill
A 4,400+ line deterministic power engineering knowledge base loaded at startup (`skills/etap-expert.md`). Operates under a mandatory 6-step workflow (PARSE $\rightarrow$ SEARCH $\rightarrow$ VALIDATE $\rightarrow$ SIMULATE $\rightarrow$ FORMAT $\rightarrow$ QA) with zero parameter guessing.

#### StudyType
A canonical enumeration defined in `agents/models.py` representing 17 verified engineering calculation modules:
`LOAD_FLOW`, `SHORT_CIRCUIT`, `ARC_FLASH`, `HARMONIC_ANALYSIS`, `OPTIMAL_POWER_FLOW`, `PROTECTION_COORDINATION`, `MOTOR_STARTING`, `TRANSIENT_STABILITY`, `CABLE_SIZING`, `EARTH_GRID`, `RENEWABLE`, `BATTERY_STORAGE`, `SCADA`, `ETAP_GUI`, `GENERATIVE_DESIGN`, `ETAP_EXPERT`, `AHMED_ETAP`.

#### Agent Handle
A unique canonical identifier string (e.g. `load_flow_agent`, `short_circuit_agent`, `etap_engineer_agent`) used by the orchestrator and API dispatchers to bind requests to specific execution logic and system prompts.

#### Prompt Manifest
The `prompts.json` configuration file at repo root. Enforces the **manifest-first fallback system** by binding agent handles to pinned local YAML prompt definitions and remote observability versions (Langfuse).

#### ChiefEngineeringOrchestrator
The central Python orchestrator (`agents/orchestrator.py`) responsible for task decomposition, calculation engine dispatch, result aggregation, first-principles validation, and engineering deliverable synthesis.

#### Digital Twin Core
The real-time synchronized digital replica of the physical power system network (`digital_twin/digital_twin_core.py`), maintaining dynamic state, topology bus-branch graphs, and event bus telemetry.

---

### Security, Safeguards & Orchestration

#### Maker-Checker / Dual-Control
A governance security mechanism requiring two distinct authorized users (a "Maker" who drafts an action and an independent "Checker" who verifies and signs off) before applying non-reversible physical topology modifications or breaker operations (enforced via HTTP 403 `MAKER_CHECKER_VIOLATION`).

#### Code Guard
A deterministic static and runtime security boundary (`security/agent_safety.py`, `src/mastra/tools/secure-execution.ts`) that validates executable payloads against prohibited AST patterns, filesystem operations, and unauthorized network traffic.

#### Hard Denied
A fail-closed HTTP 403 security response emitted immediately when an agent or client attempts to invoke high-risk system access tools (such as `powershell-tool` or arbitrary `node-tool` shell executions).

#### Circuit Breaker
A resilient operational pattern that monitors outbound external calls (e.g., Akamai edge, Supabase, Langfuse). Automatically transitions from Closed $\rightarrow$ Open state upon successive timeouts to isolate downstream failures and prevent cascading latency.

#### Zero-Guesswork Principle
AhmedETAP's foundational engineering constraint: **AI agents must never hallucinate or invent electrical parameters**. Every impedance, $X/R$ ratio, transformer vector group, and relay setting must originate from user input, project single-line diagrams, or explicit standard tables with documented clause references.
