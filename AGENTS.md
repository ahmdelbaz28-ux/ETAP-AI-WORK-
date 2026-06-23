# AGENTS.md — AhmedETAP Agent Reference

This document describes every AI agent in the AhmedETAP, their capabilities, standards compliance, and the prompt loading system.

---

## Agent Architecture

The platform uses a **dual-runtime architecture**:

1. **Mastra (TypeScript) Agents** — LLM-powered agents running in the Node.js runtime, handling user interaction, tool orchestration, and specialist routing.
2. **Python Agents** — Computation-focused agents in the Python runtime, executing validated power-system calculations (Newton-Raphson, IEC 60909, IEEE 1584, etc.).

The **Engineering Service API** bridges both runtimes: Mastra agents call `POST /api/v1/studies/run` which dispatches to the appropriate Python agent.

---

## Prompt Management System

All agent prompts are managed through a **3-tier fallback system**:

| Priority | Source | Configuration |
|----------|--------|---------------|
| 1 (highest) | **LangWatch API** | `LANGWATCH_API_KEY` env var, remote prompt versioning |
| 2 | **Local YAML files** | `prompts/*.yaml` — offline fallback |
| 3 (lowest) | **Default prompt** | Generic engineering assistant prompt in `src/mastra/prompts.ts` |

### Prompt File Structure

Each prompt YAML follows this schema:
```yaml
model: gpt-4o
temperature: 0.2
messages:
  - role: system
    content: |
      Detailed system instructions...
  - role: user
    content: "{{input}}"
```

### Available Prompt Files

| File | Agent | Temperature |
|------|-------|-------------|
| `etap_engineer_agent.yaml` | ETAP Engineer | 0.2 |
| `etap_engineer_agent_v2.yaml` | ETAP Engineer v2 | 0.2 |
| `load_flow_agent.prompt.yaml` | Load Flow | 0.2 |
| `short_circuit_agent.prompt.yaml` | Short Circuit | 0.2 |
| `arcflash_agent_prompt.prompt.yaml` | Arc Flash | 0.7 |
| `protection_agent.prompt.yaml` | Protection | 0.2 |
| `motor_starting_agent.prompt.yaml` | Motor Starting | 0.2 |
| `power_system_coordinator_agent.prompt.yaml` | Coordinator | 0.2 |
| `goal_planner_agent.yaml` | Goal Planner | 0.7 |
| `weather_agent.prompt.yaml` | Weather | 0.2 |
| `stability_agent.prompt.yaml` | Stability | 0.2 |
| `cable_sizing_agent.prompt.yaml` | Cable Sizing | 0.2 |
| `earth_grid_agent.prompt.yaml` | Earth Grid | 0.2 |
| `renewable_agent.prompt.yaml` | Renewable | 0.2 |
| `battery_storage_agent.prompt.yaml` | BESS | 0.2 |
| `scada_agent.prompt.yaml` | SCADA | 0.2 |
| `digital_twin_agent.prompt.yaml` | Digital Twin | 0.2 |
| `harmonic_agent.prompt.yaml` | Harmonic | 0.2 |
| `opf_agent.prompt.yaml` | OPF | 0.2 |
| `validation_agent.prompt.yaml` | Validation | 0.2 |
| `anomaly_agent.prompt.yaml` | Anomaly | 0.2 |
| `report_agent.prompt.yaml` | Report | 0.3 |
| `coordination_agent.prompt.yaml` | Coordination | 0.2 |
| `predictive_agent.prompt.yaml` | Predictive | 0.2 |

---

## Mastra (TypeScript) Agents

### 1. ETAP Engineer Agent (`etap-engineer-agent`)
- **File**: `src/mastra/agents/etap-engineer-agent.ts`
- **Prompt**: `etap_engineer_agent` (LangWatch) / `etap_engineer_agent.yaml` (local)
- **Tools**: `run_python`
- **Purpose**: General-purpose ETAP study assistant. Handles MV network analysis, protection coordination, arc flash queries.
- **Key Constraint**: MUST NOT guess values — all parameters must be provided by the user or extracted from ETAP project data.

### 2. Power System Coordinator Agent (`power-system-coordinator-agent`)
- **File**: `src/mastra/agents/power-system-coordinator-agent.ts`
- **Prompt**: `power_system_coordinator_agent` (LangWatch) / `power_system_coordinator_agent.prompt.yaml` (local)
- **Tools**: None (network agent — routes to sub-agents)
- **Sub-agents**: loadFlowAgent, shortCircuitAgent, protectionAgent, motorStartingAgent, arcFlashAgent, etapEngineerAgent, goalPlannerAgent
- **Purpose**: Triage and routing. Analyzes user requests and delegates to the appropriate specialist agent.
- **Routing Strategy**: Prefers the narrowest specialist that can safely answer the request.

### 3. Load Flow Agent (`load-flow-agent`)
- **File**: `src/mastra/agents/loadflow-agent.ts`
- **Prompt**: `load_flow_agent` (LangWatch) / `load_flow_agent.prompt.yaml` (local)
- **Tools**: `run_python`
- **Standard**: IEEE 3002.7
- **Purpose**: Newton-Raphson load flow analysis, voltage profile assessment, power loss calculation.
- **Key Constraint**: Flags overloaded lines and out-of-range voltages. Never guesses impedance values.

### 4. Short Circuit Agent (`short-circuit-agent`)
- **File**: `src/mastra/agents/shortcircuit-agent.ts`
- **Prompt**: `short_circuit_agent` (LangWatch) / `short_circuit_agent.prompt.yaml` (local)
- **Tools**: `run_python`
- **Standard**: IEC 60909
- **Purpose**: Fault current analysis (3-phase, SLG, LL, LLG), equipment rating verification.
- **Key Constraint**: Never guesses system impedances.

### 5. Arc Flash Agent (`arcflash-agent`)
- **File**: `src/mastra/agents/arcflash-agent.ts`
- **Prompt**: `arcflash_agent` (LangWatch) / `arcflash_agent_prompt.prompt.yaml` (local)
- **Tools**: `run_python`
- **Standard**: IEEE 1584
- **Purpose**: Incident energy calculation, arc flash boundary, PPE category determination.
- **Key Constraint**: MUST use Python tool for all calculations — no manual estimates.

### 6. Protection Agent (`protection-agent`)
- **File**: `src/mastra/agents/protection-agent.ts`
- **Prompt**: `protection_agent` (LangWatch) / `protection_agent.prompt.yaml` (local)
- **Tools**: `run_python`
- **Standard**: IEC 60255
- **Purpose**: Relay coordination, time-current curve analysis, protection selectivity verification.
- **Key Constraint**: Never guesses relay curve characteristics.

### 7. Motor Starting Agent (`motorstarting-agent`)
- **File**: `src/mastra/agents/motorstarting-agent.ts`
- **Prompt**: `motor_starting_agent` (LangWatch) / `motor_starting_agent.prompt.yaml` (local)
- **Tools**: `run_python`
- **Standard**: IEEE 399
- **Purpose**: Motor starting current analysis, voltage dip assessment, acceleration risk evaluation.
- **Key Constraint**: Must evaluate voltage dip impact on adjacent loads.

### 8. Goal Planner Agent (`goal-planner-agent`)
- **File**: `src/mastra/agents/goal-planner-agent.ts`
- **Prompt**: `goal_planner_agent` (LangWatch) / `goal_planner_agent.yaml` (local)
- **Tools**: None (structured output via Zod schema)
- **Purpose**: Converts free-form user objectives into structured, prioritized task lists for specialist agents.

### 9. Weather Agent (`weather-agent`)
- **File**: `src/mastra/agents/weather-agent.ts`
- **Prompt**: `weather_agent` (LangWatch) / `weather_agent.prompt.yaml` (local)
- **Tools**: `weatherTool`
- **Purpose**: Weather data retrieval for renewable energy planning and outdoor work scheduling.

---

## Python Agents

All Python agents inherit from `BaseAgent` in `agents/orchestrator.py`.

### 10. Load Flow Agent (`LoadFlowAgent`)
- **File**: `agents/orchestrator.py`
- **StudyType**: `LOAD_FLOW`
- **Standard**: IEEE 3002.7
- **Engine**: Newton-Raphson solver (`load_flow/load_flow.py`)

### 11. Short Circuit Agent (`ShortCircuitAgent`)
- **File**: `agents/orchestrator.py`
- **StudyType**: `SHORT_CIRCUIT`
- **Standard**: IEC 60909
- **Engine**: `fault_analysis/fault.py`

### 12. Harmonic Analysis Agent (`HarmonicAnalysisAgent`)
- **File**: `agents/orchestrator.py`
- **StudyType**: `HARMONIC_ANALYSIS`
- **Standard**: IEEE 519
- **Engine**: `fault_analysis/harmonic_analysis.py`

### 13. Optimal Power Flow Agent (`OptimalPowerFlowAgent`)
- **File**: `agents/orchestrator.py`
- **StudyType**: `OPTIMAL_POWER_FLOW`
- **Engine**: `load_flow/optimal_power_flow.py`

### 14. Protection Coordination Agent (`ProtectionCoordinationAgent`)
- **File**: `agents/orchestrator.py`
- **StudyType**: `PROTECTION_COORDINATION`
- **Standard**: IEC 60255
- **Engine**: `coordination/coordination.py`

### 15. ETAP Execution Agent (`ETAPExecutionAgent`)
- **File**: `agents/orchestrator.py`
- **Engine**: `etap_integration/etap_com.py` (Windows-only COM automation)

### 16. Validation Agent (`ValidationAgent`)
- **File**: `agents/orchestrator.py`
- **Purpose**: Cross-checks results against first principles and standards compliance.

### 17. Report Generation Agent (`ReportGenerationAgent`)
- **File**: `agents/orchestrator.py`
- **Purpose**: PDF/DOCX/XLSX report compilation from study results.

### 18. Stability Agent (`StabilityAgent`)
- **File**: `agents/stability_agent.py`
- **StudyType**: `TRANSIENT_STABILITY`
- **Standard**: IEEE 399
- **Methods**: Swing equation (RK4), eigenvalue analysis, critical clearing time

### 19. Cable Sizing Agent (`CableSizingAgent`)
- **File**: `agents/cable_sizing_agent.py`
- **Standard**: IEC 60364
- **Methods**: Ampacity calculation, voltage drop verification

### 20. Earth Grid Agent (`EarthGridAgent`)
- **File**: `agents/earth_grid_agent.py`
- **Standard**: IEEE 80
- **Methods**: Mesh/step/touch voltage calculation

### 21. Renewable Energy Agent (`RenewableAgent`)
- **File**: `agents/renewable_agent.py`
- **Standard**: IEEE 1547
- **Methods**: Solar PV & wind integration analysis

### 22. Battery Storage Agent (`BatteryStorageAgent`)
- **File**: `agents/battery_storage_agent.py`
- **Standard**: IEC 62933
- **Methods**: BESS sizing & dispatch optimization

### 23. SCADA Agent (`SCADAAgent`)
- **File**: `agents/scada_agent.py`
- **Standard**: IEC 61850
- **Methods**: Real-time data model mapping, state estimation

### 24. ETAP Expert Skill Agent (`ETAPExpertAgent`)
- **File**: `agents/etap_expert_agent.py`
- **Skill knowledge base**: `skills/etap-expert.md` (4,400+ lines, loaded once at startup)
- **System prompt**: `skills/etap-ai-agent-system-prompt.md` + `prompts/etap_expert_agent.prompt.yaml`
- **Prompt Handle**: `etap_expert_agent`
- **Study Type**: `etap_expert` (callable via `POST /api/v1/studies/run`)
- **Workflow**: Mandatory 6-step process (PARSE → SEARCH → VALIDATE → SIMULATE → FORMAT → QA)
- **Response Formats**:
  - **Format A** (Complete): `✅ REQUEST ANALYSIS: COMPLETE` + INTERNAL SIMULATION + ETAP STEPS + VALIDATION
  - **Format B** (Incomplete): `⚠️ REQUEST ANALYSIS: INCOMPLETE` + 1-3 clarifying questions
  - **Format C** (Wrong): `❌ REQUEST ANALYSIS: INCORRECT APPROACH` + correction + education
  - **Format D** (ADMS/DER): `🔷 ADMS REQUEST ANALYSIS` + operational context + actions
- **Classification**: Rule-based, deterministic (no external LLM required)
- **Coverage**: All ETAP modules — Load Flow, Short Circuit, Arc Flash, Protection, ADMS, GIS, Renewables, Transients, Industrial, API
- **Standards**: IEEE 80/141/242/399/519/1547/1584, IEC 60909/61363/61660/61850/62351, NEC, NFPA 70E
- **Test Suite**: `tests/test_etap_expert_skill.py` (22 tests covering all 4 formats + workflow)

---

## Orchestrator

### Chief Engineering Orchestrator
- **File**: `agents/orchestrator.py`
- **Class**: `ChiefEngineeringOrchestrator`
- **Responsibilities**:
  - Task decomposition
  - Agent selection based on study type
  - Result aggregation
  - Validation pipeline execution
  - Error recovery

---

## Adding a New Agent

1. **Create prompt YAML**: Add `prompts/<agent_name>.prompt.yaml` with system instructions, standard references, and constraints
2. **Register in LangWatch**: Upload prompt to LangWatch with matching handle
3. **Create Mastra agent**: Add `src/mastra/agents/<name>-agent.ts` following existing patterns
4. **Create Python agent**: Add class in `agents/` inheriting from `BaseAgent`
5. **Add to coordinator**: Register in `power-system-coordinator-agent.ts` (if LLM-routed) or in `ChiefEngineeringOrchestrator` (if computation-only)
6. **Add scenario test**: Create `tests/scenarios/test_<name>_scenario.py`
7. **Update AGENTS.md**: Document the new agent here

---

## Observability

All agent interactions are traced through **LangWatch**:
- **API Key**: `LANGWATCH_API_KEY` environment variable
- **Endpoint**: `LANGWATCH_ENDPOINT` (default: `https://app.langwatch.ai`)
- **Integration**: `engineering_service.py` initializes LangWatch at startup
- **Prompt Versioning**: LangWatch manages prompt versions with rollback capability
