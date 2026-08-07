# Agent Architecture Patterns — ETAP AI

> **Source:** Adapted from harness's `agent-design-patterns.md` (6 patterns).
> **Application:** This doc classifies each ETAP workflow into one of 6 patterns
> to make the system's coordination structure explicit.

## The 6 Patterns

| Pattern | When to use | ETAP example |
|---------|-------------|--------------|
| **Pipeline** | Sequential dependent tasks | Load flow → Report → Export |
| **Fan-out/Fan-in** | Parallel independent tasks → merge | Comprehensive study (load flow + short circuit + arc flash in parallel → unified report) |
| **Expert Pool** | Route to specialist by input type | `orchestrator.py` dispatching to the right study agent |
| **Producer-Reviewer** | Generation + quality review | Agent generates result → `ValidationAgent` verifies compliance |
| **Supervisor** | Central agent with dynamic task distribution | `GoalPlannerAgent` decomposing a goal into sub-tasks |
| **Hierarchical Delegation** | Top-down recursive delegation | `power_system_coordinator` → `loadflow-agent` → sub-tasks |

## ETAP Agent Inventory (Python)

### Agents defined in `agents/orchestrator.py` (12 classes)

| Class | prompt_handle | Pattern | Role |
|-------|---------------|---------|------|
| `BaseAgent` | (abstract) | — | Base class, loads prompt via `prompt_loader.py` |
| `LoadFlowAgent` | `load_flow_agent` | Expert Pool member | Newton-Raphson / Fast Decoupled / DC power flow |
| `ShortCircuitAgent` | `short_circuit_agent` | Expert Pool member | IEC 60909 fault analysis |
| `HarmonicAnalysisAgent` | `harmonic_analysis_agent` | Expert Pool member | IEEE 519 compliance |
| `OptimalPowerFlowAgent` | `optimal_power_flow_agent` | Expert Pool member | AC/DC OPF |
| `ProtectionCoordinationAgent` | `protection_coordination_agent` | Expert Pool member | IEC 60255 relay coordination |
| `ETAPExecutionAgent` | `etapexecution_agent` | Pipeline stage | COM automation interface to ETAP |
| `ValidationAgent` | `validation_agent` | Producer-Reviewer (reviewer) | Results verification + compliance checking |
| `ReportGenerationAgent` | `report_generation_agent` | Pipeline stage (final) | PDF/DOCX/XLSX report generation |

### Agents defined in separate files (13 classes)

| File | Class | prompt_handle | Pattern |
|------|-------|---------------|---------|
| `anomaly_agent.py` | `AnomalyAgent` | `anomaly_agent` | Expert Pool member |
| `arc_flash_agent.py` | `ArcFlashAgent` | `arc_flash_agent` | Expert Pool member |
| `battery_storage_agent.py` | `BatteryStorageAgent` | `battery_storage_agent` | Expert Pool member |
| `cable_sizing_agent.py` | `CableSizingAgent` | `cable_sizing_agent` | Expert Pool member |
| `code_guard_agent.py` | `CodeGuardAgent` | `code_guard_agent` | Producer-Reviewer (reviewer) |
| `coordination_agent.py` | `CoordinationAgent` | `coordination_agent` | Expert Pool member |
| `digital_twin_agent.py` | `DigitalTwinAgent` | `digital_twin_agent` | Expert Pool member |
| `earth_grid_agent.py` | `EarthGridAgent` | `earth_grid_agent` | Expert Pool member |
| `goal_planner_agent.py` | `GoalPlannerAgent` | `goal_planner_agent` | **Supervisor** |
| `motor_starting_agent.py` | `MotorStartingAgent` | `motor_starting_agent` | Expert Pool member |
| `predictive_agent.py` | `PredictiveAgent` | `predictive_agent` | Expert Pool member |
| `renewable_agent.py` | `RenewableAgent` | `renewable_agent` | Expert Pool member |
| `scada_agent.py` | `SCADAAgent` | `scada_agent` | Expert Pool member |
| `stability_agent.py` | `StabilityAgent` | `stability_agent` | Expert Pool member |
| `weather_agent.py` | `WeatherAgent` | `weather_agent` | Expert Pool member |

### TypeScript agents (`src/mastra/agents/*.ts`)

| File | Agent | Pattern |
|------|-------|---------|
| `loadflow-agent.ts` | LoadFlow | Expert Pool member (TS mirror of Python) |
| `shortcircuit-agent.ts` | ShortCircuit | Expert Pool member |
| `arcflash-agent.ts` | ArcFlash | Expert Pool member |
| `weather-agent.ts` | Weather | Expert Pool member |
| `motorstarting-agent.ts` | MotorStarting | Expert Pool member |
| `protection-agent.ts` | Protection | Expert Pool member |
| `etap-engineer-agent.ts` | ETAP Engineer | Pipeline stage |
| `code-guard-agent.ts` | Code Guard | Producer-Reviewer |
| `goal-planner-agent.ts` | Goal Planner | **Supervisor** |
| `power-system-coordinator-agent.ts` | Power System Coordinator | **Hierarchical Delegation** |

## Pattern Application in ETAP Workflows

### 1. Pipeline: Comprehensive Study → Report

```
User Request
    ↓
[Orchestrator] — dispatches study
    ↓
[Study Agent] (e.g. LoadFlowAgent) — executes
    ↓
[ValidationAgent] — verifies compliance
    ↓
[ReportGenerationAgent] — generates PDF
    ↓
User receives report
```

### 2. Fan-out/Fan-in: Multi-Study Comprehensive Analysis

```
User: "Analyze this system comprehensively"
    ↓
[GoalPlannerAgent] — decomposes into 3 parallel studies
    ↓
    ├── [LoadFlowAgent] ──────────┐
    ├── [ShortCircuitAgent] ──────┼── [ValidationAgent] ── [ReportGenerationAgent]
    └── [ArcFlashAgent] ──────────┘
```

### 3. Expert Pool: Single Study Dispatch

```
User: "Run load flow on this system"
    ↓
[Orchestrator] — routes to LoadFlowAgent (expert pool member)
    ↓
[LoadFlowAgent] — executes
```

### 4. Producer-Reviewer: Code Guard

```
User: "Generate Python code for X"
    ↓
[LLM] — produces code
    ↓
[CodeGuardAgent] — reviews for safety + correctness
    ↓
Approved or rejected
```

### 5. Supervisor: Goal Planner

```
User: "Optimize this power system for cost"
    ↓
[GoalPlannerAgent] — decomposes into sub-goals
    ├── "Run OPF" → [OptimalPowerFlowAgent]
    ├── "Check constraints" → [ValidationAgent]
    └── "Generate report" → [ReportGenerationAgent]
```

### 6. Hierarchical Delegation: Power System Coordinator

```
User: "Full system analysis"
    ↓
[PowerSystemCoordinatorAgent] — top-level coordinator
    ├── [LoadFlowAgent] — may delegate to sub-tasks
    ├── [ShortCircuitAgent] — may delegate to sub-tasks
    └── [ProtectionCoordinationAgent] — may delegate to relay-specific analysis
```

## How to Use This Doc

- **When adding a new agent:** classify it into one of the 6 patterns and document here
- **When debugging a workflow:** identify the pattern to understand the data flow
- **When reviewing architecture:** verify the pattern matches the actual coordination logic
- **Drift detection:** `scripts/audit_agent_drift.py` uses this inventory to detect missing prompts/agents

## References

- Original patterns: harness `references/agent-design-patterns.md` (read-only, not copied)
- ETAP orchestrator: `agents/orchestrator.py` (1859 lines)
- Prompt system: `agents/prompt_loader.py` (3-tier fallback: LangWatch → YAML → hardcoded)
