# Mastra agents Exploration and Analysis Report

## Observation

We conducted a read-only investigation of the 11 TypeScript agents and related infrastructure under the directory `c:\Users\Repair SC\Desktop\ETAP-AI-WORK--main\src\mastra\`. The following details were directly observed:

### 1. Individual Agent Configuration and Registry Mapping

Below is the mapping of all 11 TypeScript agents found in `src/mastra/agents/`:

| Agent File | Exported Variable | Internal ID | Prompt Handle | Tools | Standards / Docs | Schema (Zod) |
|---|---|---|---|---|---|---|
| `arcflash-agent.ts` | `arcFlashAgent` | `'arcflash-agent'` | `'arcflash_agent_prompt'` | `run_python` | IEEE 1584 | None |
| `code-guard-agent.ts` | `codeGuardAgent` | `'code-guard-agent'` | `'code_guard_agent'` | `run_python` | guard-skills | None |
| `etap-engineer-agent.ts` | `etapEngineerAgent` | `'etap-engineer-agent'` | `'etap_engineer_agent'` | `run_python` | - | None |
| `etap-expert-agent.ts` | `etapExpertAgent` | `'etap-expert-agent'` | `'etap_expert_agent'` | `run_python` | `skills/etap-expert.md` | None |
| `goal-planner-agent.ts` | `goalPlannerAgent` | `'goal-planner-agent'` | `'goal_planner_agent'` | None | - | `goalPlannerOutputSchema` |
| `loadflow-agent.ts` | `loadFlowAgent` | `'load-flow-agent'` | `'load_flow_agent'` | `run_python` | IEEE 3002.7 | None |
| `motorstarting-agent.ts` | `motorStartingAgent` | `'motorstarting-agent'` | `'motor_starting_agent'` | `run_python` | IEEE 399 | None |
| `power-system-coordinator-agent.ts` | `powerSystemCoordinatorAgent` | `'power-system-coordinator-agent'` | `'power_system_coordinator_agent'` | Sub-agents | - | None |
| `protection-agent.ts` | `protectionAgent` | `'protection-agent'` | `'protection_agent'` | `run_python` | IEC 60255 | None |
| `shortcircuit-agent.ts` | `shortCircuitAgent` | `'short-circuit-agent'` | `'short_circuit_agent'` | `run_python` | IEC 60909 | None |
| `weather-agent.ts` | `weatherAgent` | `'weather-agent'` | `'weather_agent'` | `weatherTool` | - | None |

*Note: In `src/mastra/agents/power-system-coordinator-agent.ts`, the coordinator registers the following sub-agents:*
```typescript
  agents: {
    loadFlowAgent,
    shortCircuitAgent,
    protectionAgent,
    motorStartingAgent,
    arcFlashAgent,
    etapEngineerAgent,
    goalPlannerAgent,
  },
```

---

### 2. Code Quality and Typing Observations

#### Top-level Awaits and lack of try/catch
Each of the 11 agent configuration files uses a top-level await to fetch the system prompt, as observed in `src/mastra/agents/arcflash-agent.ts` (lines 7-16):
```typescript
7: const promptContent = await getSystemPrompt("arcflash_agent_prompt");
8: 
9: export const arcFlashAgent = new Agent({
10:   id: 'arcflash-agent',
11:   name: 'Arc Flash Analysis Agent',
12:   instructions: promptContent,
13:   model: getActiveModelConfig() as any,
14:   tools: { run_python },
15:   memory: new Memory(),
16: });
```
No `try/catch` block surrounds `await getSystemPrompt(...)` inside the agent configuration files.

#### Type Coercion Bypass (`as any`)
- All 11 agents coerce the returned model config to `any` (e.g. `model: getActiveModelConfig() as any`).
- `src/mastra/agents/goal-planner-agent.ts` (line 32) coerces the entire configuration object to `any` during agent construction:
```typescript
32: } as any);
```

#### No-op Regex String Replacement
In `src/mastra/prompts.ts` (line 199), the following code is executed when loading local fallback prompts:
```typescript
199:       `${handle.replace(/_/g, '_')}_agent.prompt.yaml`,
```
This regex replaces underscores with underscores, resulting in a no-op string transformation.

---

### 3. Architectural and Routing Observations

#### Active Agent Registration Inconsistencies
In `src/mastra/index.ts` (lines 67-79), the agents are registered with camelCase keys:
```typescript
67:   agents: { 
68:     weatherAgent, 
69:     goalPlannerAgent, 
...
77:     powerSystemCoordinatorAgent,
78:     codeGuardAgent
79:   },
```
However, the internal agent configurations specify kebab-case ids (e.g. `id: 'weather-agent'` in `src/mastra/agents/weather-agent.ts` line 10). In Mastra, this mismatch causes `mastra.getAgent('weatherAgent')` to succeed, while `mastra.getAgent('weather-agent')` fails. This is demonstrated in `src/mastra/workflows/weather-workflow.ts` (line 107) which must use camelCase:
```typescript
107:     const agent = mastra?.getAgent('weatherAgent');
```

#### Coordinator Agent Routing Scoping
In `src/mastra/agents/power-system-coordinator-agent.ts` (lines 20-28), only 7 sub-agents are registered under the coordinator network. The following agents are omitted:
- `weatherAgent`
- `codeGuardAgent`
- `etapExpertAgent`

#### Dead Code: Unused Middleware
A complete language-detection middleware is implemented in `src/mastra/middleware/language-detection.ts`, starting with:
```typescript
335: export async function languageDetectionMiddleware(
```
No file under `src/mastra/` imports or references `languageDetectionMiddleware` or the `language-detection` module.

---

### 4. Performance and Filesystem Observations

#### Synchronous Blocking Filesystem Access
When `getSystemPrompt` falls back to loading local prompts in `src/mastra/prompts.ts` (lines 192-254):
- It tests up to three file name combinations sequentially.
- It performs `fs.existsSync` for each combination.
- If not found, it parses `prompts.json` on every invocation by executing:
```typescript
225:     const promptsJsonPath = path.join(process.cwd(), 'prompts.json');
226:     if (fs.existsSync(promptsJsonPath)) {
227:       const promptsJson = JSON.parse(fs.readFileSync(promptsJsonPath, 'utf-8'));
```
These calls are completely synchronous and block the single-threaded Node.js event loop on startup.

#### Cascading Module Imports
Because `src/mastra/index.ts` statically imports all agents, and `power-system-coordinator-agent.ts` statically imports its sub-agents, loading any single agent file causes all agent modules to be evaluated. This results in 11 sequential top-level await requests (either network calls to LangWatch or synchronous filesystem checks) when the server boots.

---

## Logic Chain

1. **Top-Level Await Blocks Startup**: Because each agent module invokes `await getSystemPrompt(...)` at its top-level namespace (Observation Section 2), and because `src/mastra/index.ts` statically imports all agents (Observation Section 4), the entire Node.js module resolution phase is blocked until all 11 prompts are loaded.
2. **Synchronous I/O Increases Latency**: The `loadLocalPrompt` function runs multiple `fs.existsSync` and `fs.readFileSync` calls synchronously (Observation Section 4). Since 11 agents are initialized sequentially, the process suffers from cumulative disk read overhead, which could lead to high startup latency or timeout failures in constrained/CI environments.
3. **Redundant Filesystem Access**: The `prompts.json` file is read and parsed from scratch via synchronous filesystem operations for every agent whose handle does not directly match the three fallback filename patterns (Observation Section 4).
4. **Key Resolution Inconsistency**: The camelCase keys in `Mastra({ agents })` conflict with kebab-case `id` strings in the agent configs (Observation Section 3). Since Mastra indexes the dev server routes and runtime lookups (`mastra.getAgent(...)`) by the dictionary key rather than the agent's internal ID, `getAgent(id)` will fail if the kebab-case ID is passed.
5. **Boilerplate and Bypassed Type Checks**: The use of `as any` (Observation Section 2) suppresses TypeScript compiler checks. This prevents the compiler from detecting version mismatches or invalid configurations (e.g. invalid `outputSchema` options).

---

## Caveats

- We investigated the TypeScript codebase statically. We did not test real-time failover latency of the LangWatch API when resolving prompts in a live deployed environment, but the code structure suggests it is sequential.
- Python-side calculation agents (e.g., `agents/orchestrator.py`, `stability_agent.py`) were not investigated in detail as they are outside the TypeScript/Mastra scope, though we verified they are separate runtimes.
- No security testing or vulnerability scanning was performed, in strict compliance with Task Constraint #5.

---

## Conclusion

The exploration and analysis of the 11 Mastra TypeScript agents successfully mapped their configurations, prompts, tools, and standards. 

Key architectural and performance issues identified include:
1. **Critical Startup Blocking**: 11 sequential top-level await prompt resolutions, exacerbated by synchronous local fallback filesystem operations, create a significant bottleneck during initialization.
2. **Key/Registry Mismatch**: Mismatches between camelCase registration keys and kebab-case internal IDs prevent consistent agent retrievals using internal IDs.
3. **Dead Code**: The language-detection middleware is fully implemented but completely unused.
4. **Weak Typing Practices**: Widespread usage of `as any` casts bypasses type safety checks.

---

## Verification Method

To verify these findings:
1. **Module Loading & Performance**:
   Run the test command:
   ```powershell
   npm run test
   ```
   *Result*: Shows that the TypeScript project builds and parses successfully, but does not benchmark the synchronous startup lag.
2. **Checking Top-Level Await Startup Blocking**:
   Inject a slow mock response or network delay in `src/mastra/prompts.ts` `getSystemPrompt` and start the server using `npm run dev`. Observe that the server startup is blocked until the slow mock resolves.
3. **Checking Key Retrieval Inconsistency**:
   In `tests/index.test.ts` or a new test script, attempt to invoke:
   ```typescript
   import { mastra } from '../src/mastra';
   const agent = mastra.getAgent('weather-agent');
   console.log(agent ? 'Found' : 'Not Found');
   ```
   *Result*: It will print `Not Found` because it was registered as `weatherAgent` instead of `weather-agent`.
