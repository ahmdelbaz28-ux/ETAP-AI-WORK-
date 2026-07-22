# Agent Architecture: Python & Mastra TypeScript Systems

> **Document version:** 2026-03-04
> **Project:** AhmedETAP — AI-Powered Power Systems Engineering Platform

---

## Table of Contents

1. [Overview](#1-overview)
2. [Python Agent System (`agents/`)](#2-python-agent-system-agents)
3. [Mastra TypeScript Agent System (`src/mastra/`)](#3-mastra-typescript-agent-system-srcmastra)
4. [Decision Matrix](#4-decision-matrix)
5. [Communication Between Systems](#5-communication-between-systems)
6. [Adding a New Agent](#6-adding-a-new-agent)

---

## 1. Overview

AhmedETAP runs **two parallel agent systems** that coexist within the same monorepo:

| Aspect | Python Agent System | Mastra TypeScript Agent System |
|---|---|---|
| **Location** | `agents/` | `src/mastra/` |
| **Language** | Python (async) | TypeScript (Node.js) |
| **Framework** | Custom (`BaseAgent` + `ChiefEngineeringOrchestrator`) | Mastra Core (`@mastra/core/agent`) |
| **Primary role** | Deterministic computation, numerical analysis, orchestration | LLM-powered conversation, tool use, networked agent routing |
| **API surface** | FastAPI (`/api/v1/studies/run`, `/api/v1/agents/`) | Next.js API routes (`/api/v1/agents/*/chat`) |
| **Prompt management** | Shared `prompts/` YAML + LangWatch | Shared `prompts/` YAML + LangWatch |
| **Requires LLM?** | No — most agents are purely computational | Yes — every agent is LLM-driven |

### Why two systems?

The two systems exist because they solve fundamentally different problems:

- **Python agents** perform **deterministic engineering calculations** (Newton-Raphson load flow, IEC 60909 short-circuit analysis, IEEE 519 harmonic compliance, relay coordination). These computations require NumPy, domain-specific solvers, and direct access to the power system model. They must produce **bit-exact, reproducible results** — an LLM cannot replace a Newton-Raphson solver.

- **Mastra TypeScript agents** provide **conversational AI** experiences. They interpret natural-language user requests, decide which specialist to route to, and use LLM reasoning to explain results, suggest corrective actions, and guide non-expert users through complex engineering workflows. They also serve as the **web-facing gateway** for the chat UI.

Both systems share the same prompt management layer (`prompts/*.yaml` + LangWatch API) and the same domain knowledge, ensuring consistent behavior regardless of which system handles a request.

---

## 2. Python Agent System (`agents/`)

### 2.1 When to Use

Use the Python agent system when you need to:

- Run **numerical power-system computations** (load flow, short circuit, harmonics, OPF, protection coordination)
- Execute **deterministic, standards-based analysis** that must produce reproducible results
- Orchestrate **multi-step engineering workflows** with dependencies between studies
- Perform **validation and compliance checking** against IEEE/IEC standards
- Generate **engineering reports** (PDF/DOCX/XLSX)
- Interact with **ETAP via COM automation** (Windows) or remote API
- Handle requests via the **FastAPI REST API** (`/api/v1/studies/run`)

### 2.2 Architecture

```
agents/
├── __init__.py
├── orchestrator.py              # BaseAgent, all core agents, ChiefEngineeringOrchestrator
├── prompt_loader.py             # 3-tier prompt loading (LangWatch → YAML → fallback)
├── etap_expert_agent.py         # Rule-based ETAP expert (Format A/B/C/D)
├── etap_gui_agent.py            # Computer Use Agent for desktop apps
├── code_guard_agent.py          # Automated code quality review
├── arc_flash_agent.py           # Standalone arc flash analysis
├── goal_planner_agent.py        # Goal decomposition
├── weather_agent.py             # Weather data agent
├── motor_starting_agent.py      # Motor starting analysis
├── cable_sizing_agent.py        # Cable sizing calculations
├── earth_grid_agent.py          # Earth grid design agent
├── stability_agent.py           # Transient stability analysis
├── coordination_agent.py        # Protection coordination
├── predictive_agent.py          # Predictive maintenance
├── renewable_agent.py           # Renewable energy integration
├── battery_storage_agent.py     # Battery storage analysis
├── digital_twin_agent.py        # Digital twin agent
├── scada_agent.py               # SCADA integration
├── anomaly_agent.py             # Anomaly detection
```

### 2.3 Core Classes

#### `BaseAgent` (abstract base)

Every Python agent inherits from `BaseAgent`, which provides:

- **Prompt integration:** Each agent declares a `prompt_handle` (e.g., `"load_flow_agent"`) that maps to a YAML prompt file. If not set, the handle is derived from the class name via CamelCase → snake_case conversion.
- **3-tier prompt loading:** LangWatch API → local YAML → hardcoded fallback.
- **Lifecycle tracking:** `AgentStatus` enum (`IDLE`, `RUNNING`, `COMPLETED`, `FAILED`, `VALIDATING`).
- **Execution logging:** Structured log entries with timestamps.
- **Tracing:** `@trace_operation` decorator for observability.

```python
class BaseAgent:
    prompt_handle: str = ""  # Override in subclass

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.status = AgentStatus.IDLE
        self._load_prompt()  # Loads from LangWatch / YAML / fallback

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Override in subclass. Default returns FAILED."""
        ...

    def validate_result(self, result: AgentResult) -> bool:
        """Override for domain-specific validation."""
        ...
```

#### `EngineeringTask` and `AgentResult`

```python
@dataclass
class EngineeringTask:
    task_id: str
    description: str
    study_types: List[StudyType]
    parameters: Dict[str, Any]
    priority: int = 1
    status: AgentStatus = AgentStatus.IDLE
    results: List[AgentResult] = field(default_factory=list)

@dataclass
class AgentResult:
    agent_name: str
    study_type: StudyType
    status: AgentStatus
    data: Dict[str, Any]
    validation_status: bool = False
    validation_errors: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
```

#### `ChiefEngineeringOrchestrator`

The orchestrator registers all agents and coordinates multi-step workflows:

```python
class ChiefEngineeringOrchestrator:
    prompt_handle = "power_system_coordinator_agent"

    def __init__(self):
        self.agents = {
            "load_flow":     LoadFlowAgent(),
            "short_circuit": ShortCircuitAgent(),
            "harmonic":      HarmonicAnalysisAgent(),
            "opf":           OptimalPowerFlowAgent(),
            "protection":    ProtectionCoordinationAgent(),
            "etap_execution": ETAPExecutionAgent(),
            "validation":    ValidationAgent(),
            "report":        ReportGenerationAgent(),
            "code_guard":    CodeGuardAgent(),        # optional
            "etap_expert":   ETAPExpertAgent(),        # optional
            "etap_gui":      ETAPGUIAgent(),           # optional
        }

    async def execute_autonomous_workflow(self, user_goal, system_data, parameters):
        """Parse goal → determine studies → execute with dependencies → validate."""
        ...
```

**Workflow execution phases:**

1. **Goal parsing** — keyword-based mapping from natural language to `StudyType` list.
2. **Phase 1** — Run load flow first (dependency for other studies).
3. **Phase 2** — Run independent studies in parallel via `asyncio.gather`.
4. **Phase 3** — Final validation pass across all results.
5. **Phase 3.5** — Code guard review (if source code was provided).

### 2.4 Built-in Core Agents

| Agent | Prompt Handle | Study Type | Standards |
|---|---|---|---|
| `LoadFlowAgent` | `load_flow_agent` | `LOAD_FLOW` | — |
| `ShortCircuitAgent` | `short_circuit_agent` | `SHORT_CIRCUIT` | IEC 60909-0:2016 |
| `HarmonicAnalysisAgent` | `harmonic_agent` | `HARMONIC_ANALYSIS` | IEEE 519-2022 |
| `OptimalPowerFlowAgent` | `opf_agent` | `OPTIMAL_POWER_FLOW` | — |
| `ProtectionCoordinationAgent` | `protection_agent` | `PROTECTION_COORDINATION` | IEC 60255 |
| `ETAPExecutionAgent` | `etap_engineer_agent` | ETAP COM/API | — |
| `ValidationAgent` | `validation_agent` | Cross-cutting | IEEE/IEC |
| `ReportGenerationAgent` | `report_agent` | Cross-cutting | — |

### 2.5 API Entry Points

The Python agents are exposed through FastAPI:

- **`POST /api/v1/studies/run`** — Execute a power system study (dispatches to the appropriate agent via `_run_native_study()` or the orchestrator).
- **`GET /api/v1/agents/info`** — Returns metadata for all registered agents including prompt status.
- **`POST /api/v1/agents/etap-expert/chat`** — Direct access to the ETAP Expert skill agent.

The `_run_native_study()` function in `api/studies.py` routes requests:

```python
def _run_native_study(study_type, system, parameters):
    if study_type == "etap_expert":
        agent = ETAPExpertAgent()
        return agent.answer(parameters["question"])
    if study_type == "etap_gui":
        agent = ETAPGUIAgent()
        return agent.answer(parameters["question"])
    # Numerical studies delegate to PowerSystemEngine
    engine = PowerSystemEngine(system)
    if study_type == "load_flow":
        return engine.run_load_flow()
    ...
```

### 2.6 Prompt Loading (Python side)

`agents/prompt_loader.py` mirrors the TypeScript `getSystemPrompt()` with the same 3-tier fallback:

1. **In-memory cache** (prevents redundant I/O and API calls)
2. **LangWatch API** (if `LANGWATCH_API_KEY` is set and `DEPLOYMENT_VERIFICATION != "true"`)
3. **Local YAML** (`prompts/{handle}.yaml` or `prompts/{handle}.prompt.yaml`)
4. **Fallback agent prompt** (`prompts/fallback_agent.prompt.yaml`)
5. **Hardcoded safety-net** — generic engineering assistant string

---

## 3. Mastra TypeScript Agent System (`src/mastra/`)

### 3.1 When to Use

Use the Mastra agent system when you need to:

- Provide **conversational AI** interfaces (chat, multi-turn dialogue)
- Route user requests to the **most appropriate specialist agent** via LLM reasoning
- Execute **Python code dynamically** via the `run_python` tool for ad-hoc calculations
- Serve agent capabilities through the **Next.js web UI**
- Leverage **Mastra's built-in memory, storage, and observability** (LibSQL, DuckDB, Pino logging)
- Build **networked agent topologies** (coordinator → specialist routing)

### 3.2 Architecture

```
src/mastra/
├── index.ts                              # Mastra instance (agents, workflows, storage, observability)
├── prompts.ts                            # 3-tier prompt loading (LangWatch → YAML → fallback)
├── utils.ts                              # Shared utilities
├── lib/
│   ├── model-config.ts                   # OpenAI model resolution & provider testing
│   └── logger.ts                         # Logging utilities
├── middleware/
│   └── language-detection.ts             # Request language detection
├── types/
│   └── goal-planner.ts                   # TypeScript types for goal planner
├── agents/
│   ├── etap-expert-agent.ts              # ETAP Expert Skill Agent
│   ├── etap-engineer-agent.ts            # ETAP Engineering Agent
│   ├── power-system-coordinator-agent.ts # Coordinator (routes to specialists)
│   ├── loadflow-agent.ts                 # Load Flow specialist
│   ├── shortcircuit-agent.ts             # Short Circuit specialist
│   ├── arcflash-agent.ts                 # Arc Flash specialist
│   ├── motorstarting-agent.ts            # Motor Starting specialist
│   ├── protection-agent.ts               # Protection specialist
│   ├── goal-planner-agent.ts             # Goal decomposition
│   ├── code-guard-agent.ts               # Code quality review
│   └── weather-agent.ts                  # Weather data agent
├── tools/
│   ├── python-tool.ts                    # Run validated Python code via secure_executor.py
│   ├── powershell-tool.ts                # Run safe PowerShell commands
│   ├── weather-tool.ts                   # Weather API integration
│   └── provider-settings-tool.ts         # LLM provider configuration
└── workflows/
    └── weather-workflow.ts               # Mastra workflow example
```

### 3.3 Mastra Instance Configuration

`src/mastra/index.ts` creates the central Mastra instance:

```typescript
export const mastra = new Mastra({
  workflows: { weatherWorkflow },
  agents: {
    weatherAgent,
    goalPlannerAgent,
    motorStartingAgent,
    shortCircuitAgent,
    loadFlowAgent,
    arcFlashAgent,
    etapEngineerAgent,
    etapExpertAgent,
    protectionAgent,
    powerSystemCoordinatorAgent,
    codeGuardAgent,
  },
  storage: new MastraCompositeStore({
    id: 'composite-storage',
    default: new LibSQLStore({ url: 'file:./mastra.db' }),
    domains: { observability: observabilityStoreProxy },  // DuckDB (lazy)
  }),
  logger: new PinoLogger({ name: 'Mastra', level: 'info' }),
  observability: new Observability({
    configs: {
      default: {
        serviceName: 'mastra',
        exporters: [
          new MastraStorageExporter(),
          new MastraPlatformExporter(),
        ],
        spanOutputProcessors: [new SensitiveDataFilter()],
      },
    },
  }),
});
```

The provider configuration is in `mastra.config.ts`:

```typescript
export default {
  dir: './src/mastra',
  providers: [{
    id: 'openai',
    client: createOpenAI({
      apiKey: process.env.OPENAI_API_KEY,
      baseURL: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
    }),
    model: process.env.OPENAI_MODEL_ID || 'gpt-4o',
  }],
};
```

### 3.4 Agent Pattern

Every Mastra agent follows the same pattern:

```typescript
import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { run_python } from '../tools/python-tool';
import { getSystemPrompt } from '../prompts';
import { getActiveModelConfig } from '../lib/model-config';

const promptContent = await getSystemPrompt('load_flow_agent');

export const loadFlowAgent = new Agent({
  id: 'load-flow-agent',
  name: 'Load Flow Analysis Agent',
  instructions: promptContent,
  model: getActiveModelConfig() as any,
  tools: { run_python },       // Optional: agents can have tools
  memory: new Memory(),        // Built-in conversation memory
});
```

Key observations:
- **`instructions`** — Loaded from the same shared prompt system as Python agents.
- **`model`** — Resolved from `getActiveModelConfig()` which reads `OPENAI_MODEL_ID` (default: `gpt-4o`).
- **`tools`** — Agents can be given tools like `run_python` for dynamic code execution.
- **`memory`** — Mastra's built-in `Memory` class provides multi-turn conversation support.
- **`agents`** — The coordinator agent can reference sub-agents for routing (see below).

### 3.5 Coordinator Agent (Networked Routing)

The `powerSystemCoordinatorAgent` is the Mastra-side counterpart of the Python `ChiefEngineeringOrchestrator`. It uses Mastra's **agent network** feature to route user requests to the most appropriate specialist:

```typescript
export const powerSystemCoordinatorAgent = new Agent({
  id: 'power-system-coordinator-agent',
  name: 'Power System Coordinator Agent',
  instructions: promptContent,
  model: getActiveModelConfig() as any,
  agents: {
    loadFlowAgent,
    shortCircuitAgent,
    protectionAgent,
    motorStartingAgent,
    arcFlashAgent,
    etapEngineerAgent,
    goalPlannerAgent,
  },
  memory: new Memory(),
  defaultNetworkOptions: {
    maxSteps: 10,
    routing: {
      additionalInstructions:
        'Prefer the narrowest specialist agent that can safely answer the user request.',
    },
  },
});
```

When a user sends a message to the coordinator, the LLM decides which specialist agent to delegate to — without requiring manual routing logic.

### 3.6 Tools

Mastra agents can execute actions through tools:

#### `run_python` — Execute Python code

```typescript
export const run_python = createTool({
  id: 'run-python',
  description: 'Run validated Python code for engineering calculations.',
  inputSchema: z.object({ code: z.string() }),
  execute: async ({ code }) => {
    // Spawns: python security/secure_executor.py
    // Code is passed via stdin (prevents shell injection)
    // Output is JSON-parsed with success/error handling
    // Timeout: 30s, max output: 10,000 chars
  },
});
```

This tool is the **primary bridge** from the Mastra LLM agents to the Python computational layer. The LLM can generate Python code to perform calculations that would be unreliable if done purely through text generation.

#### `run_powershell` — Execute read-only PowerShell commands

Similar pattern to `run_python`, but for Windows-specific operations like querying ETAP via COM.

### 3.7 Prompt Loading (TypeScript side)

`src/mastra/prompts.ts` implements the same 3-tier fallback as the Python side:

1. **LangWatch API** — `langwatch.prompts.get(handle)` (if `LANGWATCH_API_KEY` is set)
2. **Local YAML** — Custom YAML parser reads `prompts/{handle}.yaml` or `prompts/{handle}.prompt.yaml`
3. **Fallback agent** — Tries `prompts/fallback_agent.prompt.yaml`
4. **Hardcoded safety-net** — Returns a generic engineering assistant string

```typescript
export async function getSystemPrompt(handle: string): Promise<string> {
  // 1. Try LangWatch
  if (process.env.DEPLOYMENT_VERIFICATION !== 'true') {
    const prompt = await langwatch.prompts.get(handle);
    if (prompt) return extractContent(prompt);
  }
  // 2. Try local YAML
  const localPrompt = loadLocalPrompt(handle);
  if (localPrompt) return localPrompt;
  // 3. Fallback agent prompt
  const fallbackPrompt = loadLocalPrompt('fallback_agent');
  if (fallbackPrompt) return fallbackPrompt;
  // 4. Hardcoded default
  return 'You are a safety-net fallback AI assistant...';
}
```

---

## 4. Decision Matrix

Use this table to decide which agent system is appropriate for a given task:

| Criteria | Python Agent System | Mastra TypeScript Agent System |
|---|---|---|
| **Numerical computation** (load flow, fault analysis, harmonics) | ✅ Primary | ❌ Not suitable |
| **Deterministic, reproducible results** | ✅ Required | ❌ LLM output is non-deterministic |
| **Standards compliance checking** (IEEE/IEC) | ✅ Built-in | ⚠️ Can interpret, not compute |
| **Conversational AI / chat interface** | ❌ Not designed for this | ✅ Primary |
| **Multi-turn dialogue** | ❌ No memory | ✅ Built-in `Memory` |
| **Natural language understanding** | ❌ Rule-based only | ✅ LLM-powered |
| **Request routing to specialists** | ⚠️ Keyword-based | ✅ LLM-powered network routing |
| **Web UI integration** | ⚠️ Via FastAPI only | ✅ Native Next.js integration |
| **Autonomous multi-step workflows** | ✅ Orchestrator handles dependencies | ⚠️ Limited to LLM chain-of-thought |
| **ETAP COM automation** | ✅ Direct integration | ⚠️ Via `run_powershell` tool |
| **Offline / no LLM API required** | ✅ Works offline | ❌ Requires LLM API key |
| **Ad-hoc code execution** | ❌ Not designed for this | ✅ Via `run_python` tool |
| **Observability / tracing** | ✅ `@trace_operation` | ✅ Mastra built-in (DuckDB + OpenTelemetry) |
| **Prompt management** | ✅ Shared system | ✅ Shared system |
| **Testing ease** | ✅ Deterministic = easy to test | ⚠️ LLM output = harder to assert |

### Quick Decision Flowchart

```
Does the task require numerical computation?
  └─ YES → Python Agent System
  └─ NO → Does it require conversational AI / natural language?
        └─ YES → Mastra TypeScript Agent System
        └─ NO → Does it need multi-step orchestration with dependencies?
              └─ YES → Python Agent System (ChiefEngineeringOrchestrator)
              └─ NO → Does it need web UI / chat interface?
                    └─ YES → Mastra TypeScript Agent System
                    └─ NO → Either system may work; prefer the simpler option
```

---

## 5. Communication Between Systems

The two agent systems are **not directly coupled** — they communicate through well-defined boundaries:

### 5.1 Shared Prompt Layer

Both systems read from the same `prompts/*.yaml` files and the same LangWatch API. This ensures that whether a user interacts through the Python API or the Mastra chat UI, the agent's behavior is guided by the same system prompt.

```
prompts/
├── load_flow_agent.prompt.yaml          ← Read by both Python & Mastra
├── short_circuit_agent.prompt.yaml      ← Read by both
├── harmonic_agent.prompt.yaml           ← Read by both
├── protection_agent.prompt.yaml         ← Read by both
├── etap_expert_agent.prompt.yaml        ← Read by both
├── etap_engineer_agent_v2.yaml        ← Read by both (handle: etap_engineer_agent)
├── power_system_coordinator_agent.yaml  ← Read by both
├── code_guard_agent.prompt.yaml         ← Read by both
├── fallback_agent.prompt.yaml           ← Read by both
└── ... (30+ prompt files)
```

### 5.2 `run_python` Tool Bridge

The **primary runtime bridge** from Mastra to Python is the `run_python` tool. When a Mastra LLM agent needs to perform a calculation, it generates Python code and executes it through the secure executor:

```
User (chat UI)
  → Mastra Agent (TypeScript)
    → LLM decides to use run_python tool
      → spawns: python security/secure_executor.py
        → Python code executes
          → Results returned as string
    → LLM interprets results and responds to user
```

**Security:** Code is passed via `stdin` (not CLI args) to prevent shell injection. The `secure_executor.py` validates code against security policies before execution. Output is truncated at 10,000 characters and execution times out at 30 seconds.

### 5.3 `run_powershell` Tool Bridge

Similar to `run_python`, but for Windows-specific operations:

```
Mastra Agent → run_powershell → python security/secure_powershell_executor.py → PowerShell command
```

### 5.4 API-Level Integration

The FastAPI backend serves both systems:

- **Python agents** are called directly via `POST /api/v1/studies/run` with `study_type` and parameters.
- **Mastra agents** are exposed via Next.js API routes at `/api/v1/agents/{agent-id}/chat`, which internally call the Mastra agent's `.generate()` or `.stream()` methods.

A client (web UI, external API consumer) chooses which endpoint to call based on the nature of the request.

### 5.5 No Direct Agent-to-Agent Calls

There is **no direct agent-to-agent calling** between the Python and Mastra systems at runtime. Each system operates independently:

- Python agents call other Python agents through the `ChiefEngineeringOrchestrator`.
- Mastra agents call other Mastra agents through the coordinator's `agents` network.

The only cross-system communication happens at the **tool level** (`run_python`, `run_powershell`) where the Mastra agent spawns a Python subprocess.

---

## 6. Adding a New Agent

### 6.1 Adding a Python Agent

**Step 1: Create the agent class**

Create a new file `agents/my_new_agent.py`:

```python
"""My New Agent — Description of what it does."""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    BaseAgent,
    EngineeringTask,
    StudyType,
)
from core.tracing import trace_operation

logger = logging.getLogger("agent.my_new")


class MyNewAgent(BaseAgent):
    """My New Agent.

    Prompt Handle: my_new_agent

    Capabilities:
    - Describe what this agent computes
    - Reference applicable standards
    """

    prompt_handle = "my_new_agent"

    def __init__(self):
        super().__init__("MyNewAgent")
        # Initialize agent-specific parameters

    @trace_operation(
        "MyNewAgent.execute",
        attributes={"component": "orchestrator", "study_type": "my_new"},
    )
    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Execute the analysis."""
        start_time = datetime.now(timezone.utc)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting analysis for task {task.task_id}")

            # --- Your computation logic here ---
            result_data = {"key": "value"}

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,  # Choose appropriate StudyType
                status=AgentStatus.COMPLETED,
                data=result_data,
            )

            result.validation_status = self.validate_result(result)
            result.execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            return result

        except Exception as e:
            self.log_execution(f"Analysis failed: {e}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    def validate_result(self, result: AgentResult) -> bool:
        """Validate results against standards."""
        # Add domain-specific checks
        return super().validate_result(result)
```

**Step 2: Create the prompt file**

Create `prompts/my_new_agent.prompt.yaml`:

```yaml
model: gpt-4o
temperature: 0.2
messages:
  - role: system
    content: |
      You are the My New Agent for power systems engineering.
      Your role is to [describe purpose].
      Standards: [list applicable standards].
      When analyzing results, always check [validation criteria].
```

**Step 3: Register with the orchestrator**

In `agents/orchestrator.py`, add the agent to `ChiefEngineeringOrchestrator.__init__()`:

```python
from agents.my_new_agent import MyNewAgent

class ChiefEngineeringOrchestrator:
    def __init__(self):
        self.agents = {
            # ... existing agents ...
            "my_new": MyNewAgent(),
        }
```

**Step 4: (Optional) Add API route**

In `api/studies.py`, add a dispatch case in `_run_native_study()`:

```python
if study_type == "my_new":
    return engine.run_my_new_analysis(parameters)
```

**Step 5: (Optional) Add to `StudyType` enum**

In `agents/orchestrator.py`:

```python
class StudyType(Enum):
    # ... existing types ...
    MY_NEW = "my_new"
```

---

### 6.2 Adding a Mastra TypeScript Agent

**Step 1: Create the agent file**

Create `src/mastra/agents/my-new-agent.ts`:

```typescript
import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { run_python } from '../tools/python-tool';
import { getSystemPrompt } from '../prompts';
import { getActiveModelConfig } from '../lib/model-config';

const promptContent = await getSystemPrompt('my_new_agent');

export const myNewAgent = new Agent({
  id: 'my-new-agent',
  name: 'My New Agent',
  instructions: promptContent,
  model: getActiveModelConfig() as any,
  tools: { run_python },  // Include tools the agent needs
  memory: new Memory(),
});
```

**Step 2: Create the prompt file**

Use the same `prompts/my_new_agent.prompt.yaml` created for the Python agent (shared prompt layer).

**Step 3: Register with the Mastra instance**

In `src/mastra/index.ts`:

```typescript
import { myNewAgent } from './agents/my-new-agent';

export const mastra = new Mastra({
  agents: {
    // ... existing agents ...
    myNewAgent,
  },
  // ...
});
```

**Step 4: (Optional) Add to the coordinator's network**

If the agent should be routable from the coordinator, add it to the `agents` property in `power-system-coordinator-agent.ts`:

```typescript
import { myNewAgent } from './my-new-agent';

export const powerSystemCoordinatorAgent = new Agent({
  // ...
  agents: {
    // ... existing agents ...
    myNewAgent,
  },
  // ...
});
```

**Step 5: (Optional) Add an API route**

Create a Next.js API route at `src/app/api/v1/agents/my-new-agent/chat/route.ts` to expose the agent via HTTP.

---

### 6.3 Checklist: Adding an Agent to Both Systems

If the new agent should be available in both the Python and Mastra systems:

- [ ] Create `agents/my_new_agent.py` (Python agent class)
- [ ] Create `src/mastra/agents/my-new-agent.ts` (Mastra agent definition)
- [ ] Create `prompts/my_new_agent.prompt.yaml` (shared prompt — one file serves both)
- [ ] Register Python agent in `ChiefEngineeringOrchestrator.__init__()`
- [ ] Register Mastra agent in `src/mastra/index.ts`
- [ ] Add to coordinator agent's network (Mastra) if needed
- [ ] Add dispatch case in `api/studies.py` if needed
- [ ] Add `StudyType` enum value if needed
- [ ] Upload prompt to LangWatch (if using managed prompts)
- [ ] Write tests for both the Python and Mastra versions
- [ ] Update this documentation

---

## Appendix: File Reference Summary

| File | System | Purpose |
|---|---|---|
| `agents/orchestrator.py` | Python | `BaseAgent`, core agents, `ChiefEngineeringOrchestrator` |
| `agents/prompt_loader.py` | Python | 3-tier prompt loading (mirrors TS implementation) |
| `agents/etap_expert_agent.py` | Python | Rule-based ETAP expert (no LLM required) |
| `src/mastra/index.ts` | Mastra | Central Mastra instance with agents, storage, observability |
| `src/mastra/prompts.ts` | Mastra | 3-tier prompt loading (mirrors Python implementation) |
| `src/mastra/agents/*.ts` | Mastra | Individual agent definitions |
| `src/mastra/tools/python-tool.ts` | Mastra | Bridge: execute Python code from Mastra agents |
| `src/mastra/tools/powershell-tool.ts` | Mastra | Bridge: execute PowerShell from Mastra agents |
| `src/mastra/lib/model-config.ts` | Mastra | OpenAI model resolution and provider testing |
| `mastra.config.ts` | Mastra | Mastra framework configuration (provider, directory) |
| `prompts/*.yaml` | Shared | Prompt definitions used by both systems |
| `api/studies.py` | Python | FastAPI routes for study execution |
| `api/agents.py` | Python | FastAPI routes for agent information and ETAP expert chat |
