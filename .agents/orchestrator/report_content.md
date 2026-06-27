# Mastra Agent Review Report

This report presents a comprehensive review of the code quality, architecture, and performance of the Mastra (TypeScript) agents in the workspace, excluding security vulnerability scanning.

---

## 1. Executive Summary

We performed a thorough analysis of the 11 Mastra agents located under `src/mastra/agents/` and the supporting prompt-management/observability infrastructure under `src/mastra/`. 

The core findings are:
1. **Critical Startup Blocking**: The use of sequential top-level awaits to resolve system prompts, coupled with synchronous local filesystem fallback logic, creates a severe bottleneck that blocks module resolution and server startup.
2. **Registry Mapping Inconsistencies**: The agent keys in the `Mastra` instantiation are registered as camelCase, whereas the internal agent configurations use kebab-case IDs. This prevents lookups via `mastra.getAgent()` using the agents' official internal IDs.
3. **Weak Typing Practices**: Widespread usage of `as any` casts to bypass TypeScript compiler validations, reducing code maintainability and risk of runtime failures.
4. **Dead Code**: An entire language detection middleware is fully implemented but completely unused and unreferenced.

---

## 2. Actionable Improvements & Code Snippets

### Improvement 1: Eliminate Top-Level Await Startup Bottlenecks (Performance & Architecture)

**Observation:**
Every agent file (e.g. `src/mastra/agents/arcflash-agent.ts`, `src/mastra/agents/loadflow-agent.ts`) runs a top-level await `const promptContent = await getSystemPrompt(...)` to fetch system instructions during module initialization. Because `src/mastra/index.ts` statically imports all 11 agents, the entire server startup/module resolution phase is blocked sequentially until all 11 prompts are resolved. If LangWatch is slow or down, this leads to long boot delays or timeouts.

**Actionable Solution:**
Refactor the agent initialization to resolve prompts lazily. Initialize the Agent instance on first request or use a lazy getter function so that server startup is immediate and prompt fetching is deferred.

#### Code Comparison:

**Before:**
```typescript
// src/mastra/agents/arcflash-agent.ts
import { Agent } from "@mastra/core/agent";
import { Memory } from "@mastra/memory";
import { run_python } from "../tools/python-tool";
import { getSystemPrompt } from "../prompts";
import { getActiveModelConfig } from "../lib/model-config";

const promptContent = await getSystemPrompt("arcflash_agent_prompt");

export const arcFlashAgent = new Agent({
  id: 'arcflash-agent',
  name: 'Arc Flash Analysis Agent',
  instructions: promptContent,
  model: getActiveModelConfig() as any,
  tools: { run_python },
  memory: new Memory(),
});
```

**After (Lazy Initialization Getter):**
```typescript
// src/mastra/agents/arcflash-agent.ts
import { Agent } from "@mastra/core/agent";
import { Memory } from "@mastra/memory";
import { run_python } from "../tools/python-tool";
import { getSystemPrompt } from "../prompts";
import { getActiveModelConfig } from "../lib/model-config";

let arcFlashAgentInstance: Agent | null = null;

export async function getArcFlashAgent(): Promise<Agent> {
  if (!arcFlashAgentInstance) {
    const promptContent = await getSystemPrompt("arcflash_agent_prompt");
    arcFlashAgentInstance = new Agent({
      id: 'arcflash-agent',
      name: 'Arc Flash Analysis Agent',
      instructions: promptContent,
      model: getActiveModelConfig() as any,
      tools: { run_python },
      memory: new Memory(),
    });
  }
  return arcFlashAgentInstance;
}
```

---

### Improvement 2: Optimize and Asyncify File Access in Prompt Fetching (Performance)

**Observation:**
In `src/mastra/prompts.ts`, the fallback method `loadLocalPrompt` runs sequential synchronous operations (`fs.existsSync`, `fs.readFileSync`) to test multiple filename patterns. If a pattern is not found, it parses `prompts.json` from disk synchronously on *every single* prompt loading request. This blocks the single-threaded Node.js event loop.

**Actionable Solution:**
1. In-memory cache the contents of `prompts.json` upon first read.
2. Use asynchronous filesystem operations (`fs.promises`) to prevent event-loop blocking.
3. Fix the no-op regex pattern replacement `` `${handle.replace(/_/g, '_')}_agent.prompt.yaml` `` to target proper string cleanup.

#### Code Comparison:

**Before:**
```typescript
// src/mastra/prompts.ts
function loadLocalPrompt(handle: string): string | null {
  try {
    const promptsDir = path.join(process.cwd(), 'prompts');
    const possibleFiles = [
      `${handle}.yaml`,
      `${handle}.prompt.yaml`,
      `${handle.replace(/_/g, '_')}_agent.prompt.yaml`,
    ];
    for (const filename of possibleFiles) {
      const filePath = path.join(promptsDir, filename);
      if (fs.existsSync(filePath)) {
        const content = fs.readFileSync(filePath, 'utf-8');
        // ... parse and return
      }
    }
    // ... read and parse prompts.json from scratch synchronously
  } catch (e) { ... }
}
```

**After (Async, Cached, and Fixed Regex):**
```typescript
// src/mastra/prompts.ts
import { promises as fs } from 'fs';
import * as path from 'path';

let promptsJsonCache: Record<string, string> | null = null;

async function loadLocalPrompt(handle: string): Promise<string | null> {
  try {
    const promptsDir = path.join(process.cwd(), 'prompts');
    
    // Fixed pattern matching (replacing _prompt suffix or mapping underscores to hyphens)
    const normalizedHandle = handle.replace(/_prompt$/g, '');
    const possibleFiles = [
      `${handle}.yaml`,
      `${handle}.prompt.yaml`,
      `${normalizedHandle}_agent.prompt.yaml`,
    ];
    
    for (const filename of possibleFiles) {
      const filePath = path.join(promptsDir, filename);
      try {
        const content = await fs.readFile(filePath, 'utf-8');
        const parsed = parseSimpleYaml(content);
        const result = extractSystemContent(parsed);
        if (result) return result;
      } catch {
        // Continue to next file
      }
    }
    
    // Read and parse prompts.json once, cache in memory
    if (!promptsJsonCache) {
      const promptsJsonPath = path.join(process.cwd(), 'prompts.json');
      try {
        const fileContent = await fs.readFile(promptsJsonPath, 'utf-8');
        promptsJsonCache = JSON.parse(fileContent).prompts || {};
      } catch {
        promptsJsonCache = {};
      }
    }
    
    const promptPath = promptsJsonCache[handle];
    if (promptPath) {
      const actualPath = promptPath.startsWith('file:') ? promptPath.substring(5) : promptPath;
      const fullPath = path.join(process.cwd(), actualPath);
      try {
        const content = await fs.readFile(fullPath, 'utf-8');
        return extractSystemContent(parseSimpleYaml(content));
      } catch {
        // Fallback
      }
    }
    return null;
  } catch (e) {
    console.warn(`[Prompts] Error loading local prompt "${handle}":`, e);
    return null;
  }
}
```

---

### Improvement 3: Align Mastra Agent Registry Keys with Internal IDs (Architecture)

**Observation:**
In `src/mastra/index.ts`, agents are registered as camelCase keys:
```typescript
  agents: { 
    weatherAgent, 
    goalPlannerAgent, 
    // ...
  }
```
However, the internal Agent configuration specifies kebab-case `id` strings (e.g. `id: 'weather-agent'`). Mastra indexes registered agents by their dictionary keys. As a result, lookups using the internal IDs via `mastra.getAgent('weather-agent')` return `undefined`, forcing developers to use `mastra.getAgent('weatherAgent')`.

**Actionable Solution:**
Expose agents under dictionary keys that exactly match their internal kebab-case IDs.

#### Code Comparison:

**Before:**
```typescript
// src/mastra/index.ts
export const mastra = new Mastra({
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
    codeGuardAgent
  },
  // ...
});
```

**After:**
```typescript
// src/mastra/index.ts
export const mastra = new Mastra({
  agents: { 
    'weather-agent': weatherAgent, 
    'goal-planner-agent': goalPlannerAgent, 
    'motorstarting-agent': motorStartingAgent,
    'short-circuit-agent': shortCircuitAgent,
    'load-flow-agent': loadFlowAgent,
    'arcflash-agent': arcFlashAgent,
    'etap-engineer-agent': etapEngineerAgent,
    'etap-expert-agent': etapExpertAgent,
    'protection-agent': protectionAgent,
    'power-system-coordinator-agent': powerSystemCoordinatorAgent,
    'code-guard-agent': codeGuardAgent
  },
  // ...
});
```

---

### Improvement 4: Enforce Strong Typing & Eradicate Type Bypass `as any` (Quality & Robustness)

**Observation:**
All agent definitions coerce configurations or model fields via `as any`. For example, `model: getActiveModelConfig() as any` is used across all files. Bypassing compile-time checks hides configuration compatibility problems, meaning standard or model changes will only crash at runtime.

**Actionable Solution:**
Establish explicit TypeScript interface mappings or leverage typing packages from `@mastra/core/agent` to structure the agent configurations correctly.

#### Code Comparison:

**Before:**
```typescript
export const arcFlashAgent = new Agent({
  id: 'arcflash-agent',
  name: 'Arc Flash Analysis Agent',
  instructions: promptContent,
  model: getActiveModelConfig() as any, // type safety bypass
  tools: { run_python },
  memory: new Memory(),
});
```

**After:**
```typescript
import { AgentConfig } from "@mastra/core/agent";

const modelConfig = getActiveModelConfig();

export const arcFlashAgent = new Agent({
  id: 'arcflash-agent',
  name: 'Arc Flash Analysis Agent',
  instructions: promptContent,
  model: {
    provider: modelConfig.provider as 'openai' | 'anthropic', // specify valid providers
    name: modelConfig.name,
    toolChoice: modelConfig.toolChoice,
  },
  tools: { run_python },
  memory: new Memory(),
});
```

---

### Improvement 5: Cleanup Unused Language Detection Middleware (Maintainability)

**Observation:**
`src/mastra/middleware/language-detection.ts` contains a fully functional middleware block (`languageDetectionMiddleware`), but this file is never imported, exported, or used anywhere else in the repository.

**Actionable Solution:**
Either delete this unused file to minimize technical debt and reduce package bundle size, or explicitly register it in the appropriate request hooks/workflows if it is required.

---

## 3. Analysis Matrix

Below is a detailed architecture overview of the 11 Mastra TypeScript agents:

| Agent | Purpose | Primary Standard | Registry Key | Config ID | Tools |
|---|---|---|---|---|---|
| **Arc Flash** | Incident energy & PPE calculation | IEEE 1584 | `arcFlashAgent` | `'arcflash-agent'` | `run_python` |
| **Code Guard** | Static and runtime code guarding | guard-skills | `codeGuardAgent` | `'code-guard-agent'` | `run_python` |
| **ETAP Engineer** | Generic power-system study assistant | General | `etapEngineerAgent` | `'etap-engineer-agent'` | `run_python` |
| **ETAP Expert** | Specialized ETAP module expert | `skills/etap-expert` | `etapExpertAgent` | `'etap-expert-agent'` | `run_python` |
| **Goal Planner** | Breaks user objectives into tasks | General | `goalPlannerAgent` | `'goal-planner-agent'` | None |
| **Load Flow** | Voltage drop & power loss calculations | IEEE 3002.7 | `loadFlowAgent` | `'load-flow-agent'` | `run_python` |
| **Motor Starting** | Inrush current & voltage dip analysis | IEEE 399 | `motorStartingAgent` | `'motorstarting-agent'` | `run_python` |
| **Power Coordinator** | Router agent coordinating sub-agents | Routing | `powerSystemCoordinatorAgent` | `'power-system-coordinator-agent'` | Sub-agents |
| **Protection** | Relay coordination & selectivity analysis | IEC 60255 | `protectionAgent` | `'protection-agent'` | `run_python` |
| **Short Circuit** | Calculates fault currents | IEC 60909 | `shortCircuitAgent` | `'short-circuit-agent'` | `run_python` |
| **Weather** | Retrieval of meteorological forecasts | Weather data | `weatherAgent` | `'weather-agent'` | `weatherTool` |

---

## 4. Architectural & Performance Assessment

### Cold Start and Resolving Top-Level Imports
Since Node.js must run the top-level async functions for each imported file, and the entrypoint `src/mastra/index.ts` imports all 11 agents at the top-level, server startup blocks until all 11 agents have finished fetching their prompt content. This behavior results in:
1. Significant latency overhead on cold starts (estimated at 1.5s - 5s depending on API/Disk response speeds).
2. Fragile resilience: If a single prompt fails to load (due to disk I/O failure or LangWatch outage), the entire application registry fails to boot.

### Coordinator Routing Scopes
The `powerSystemCoordinatorAgent` acts as the router but only has 7 sub-agents registered:
```typescript
  agents: {
    loadFlowAgent,
    shortCircuitAgent,
    protectionAgent,
    motorStartingAgent,
    arcFlashAgent,
    etapEngineerAgent,
    goalPlannerAgent,
  }
```
This means `weatherAgent`, `codeGuardAgent`, and `etapExpertAgent` are omitted from the routing registry, so the coordinator cannot delegate tasks to them, causing silent routing failures for related queries.

---

## 5. Exclusions and Disclaimers
In compliance with the project guidelines:
- **No security vulnerability scanning was conducted.**
- **No credentials, tokens, or security flaws were scanned or analyzed.**
- This review focuses exclusively on code quality, performance, and architecture within the TypeScript Mastra runtime.
