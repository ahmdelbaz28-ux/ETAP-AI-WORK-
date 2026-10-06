import { z } from 'zod';

import { createTool } from '@mastra/core/tools';
import { Agent } from '@mastra/core/agent';
import { createAgent } from '../lib/agent-factory';
import { run_python } from '../tools/python-tool';
import { weatherTool } from '../tools/weather-tool';

/**
 * Canonical tool for submitting authoritative engineering study requests.
 * Enforces the Phase 9 AI architecture:
 *   User Intent -> AI Interpretation -> ExecutionPlan -> Capability Selection
 *     -> Canonical ExecutionRequest -> Canonical ExecutionOrchestrator
 *
 * Mastra agents MUST use this tool (and never run_python) for authoritative
 * engineering calculations (Load Flow, Short Circuit, Arc Flash, Relay Coordination).
 */
const request_canonical_execution = createTool({
  id: 'request-canonical-execution',
  description:
    'Submit an authoritative engineering execution request to the canonical ExecutionOrchestrator. ' +
    'Mastra agents MUST use this tool instead of run_python for authoritative power-system calculations ' +
    '(e.g., Load Flow, Short Circuit, Arc Flash, Protection Coordination, Motor Starting). ' +
    'Constructs a canonical ExecutionRequest with capability_id, system model, parameters, and provenance.',
  inputSchema: z.object({
    capability_id: z.string().describe(
      'Canonical capability or study type (e.g. LOAD_FLOW, SHORT_CIRCUIT, ARC_FLASH, PROTECTION_COORDINATION, MOTOR_STARTING)',
    ),
    goal: z.string().describe('The user goal or engineering objective for this study'),
    parameters: z.record(z.any()).optional().describe('Study parameters (e.g. max_iterations, tolerance, fault_type)'),
    system: z.record(z.any()).optional().describe('Power-system model dictionary (base_mva, buses, lines)'),
    source: z
      .object({
        kind: z.enum(['user_input', 'project_data', 'computed', 'standard']),
        ref: z.string().optional(),
      })
      .optional()
      .describe('Engineering provenance metadata for inputs'),
  }),
  execute: async (
    {
      capability_id,
      goal,
      parameters,
      system,
      source,
    }: {
      capability_id: string;
      goal: string;
      parameters?: Record<string, any>;
      system?: Record<string, any>;
      source?: { kind: string; ref?: string };
    },
    context?: any,
  ) => {
    const backendUrl = process.env.ENGINEERING_API_URL || 'http://localhost:8000';
    const planPayload = {
      tool: 'canonical_orchestrator',
      args: {
        capability_id,
        goal,
        parameters: parameters || {},
        system: system || {},
      },
      source: source || { kind: 'user_input', ref: 'mastra_agent_request' },
      session_id: context?.requestContext?.get?.('session_id') || undefined,
      tenant_id: context?.requestContext?.get?.('tenant_id') || undefined,
    };

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    const authHeader =
      context?.requestContext?.get?.('authorization') ||
      process.env.SERVICE_JWT ||
      process.env.ENGINEERING_API_KEY;
    if (authHeader) {
      if (authHeader.startsWith('Bearer ') || authHeader.startsWith('bearer ')) {
        headers['Authorization'] = authHeader;
      } else {
        headers['Authorization'] = `Bearer ${authHeader}`;
      }
    }

    let planData: any;
    try {
      const planResp = await fetch(`${backendUrl}/api/v1/agent-exec/plan`, {
        method: 'POST',
        headers,
        body: JSON.stringify(planPayload),
      });
      if (!planResp.ok) {
        const errorText = await planResp.text().catch(() => '');
        return {
          status: 'failed',
          success: false,
          error: `Plan phase rejected by gateway (${planResp.status}): ${errorText.slice(0, 300)}`,
          gateway: 'canonical_execution_orchestrator',
        };
      }
      planData = await planResp.json();
    } catch (networkErr: any) {
      return {
        status: 'unavailable',
        success: false,
        error: `Canonical execution gateway unreachable: ${networkErr?.message || networkErr}`,
        gateway: 'canonical_execution_orchestrator',
      };
    }

    if (planData.decision === 'auto_approved') {
      const idempotencyKey =
        context?.requestContext?.get?.('idempotency_key') ||
        `mastra_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

      const execHeaders: Record<string, string> = {
        ...headers,
        'Idempotency-Key': idempotencyKey,
      };

      try {
        const execResp = await fetch(`${backendUrl}/api/v1/agent-exec/execute`, {
          method: 'POST',
          headers: execHeaders,
          body: JSON.stringify({ plan_id: planData.plan_id }),
        });
        if (!execResp.ok) {
          const errorText = await execResp.text().catch(() => '');
          return {
            status: 'failed',
            success: false,
            error: `Execution phase rejected by gateway (${execResp.status}): ${errorText.slice(0, 300)}`,
            plan_id: planData.plan_id,
            gateway: 'canonical_execution_orchestrator',
          };
        }
        const execResult: any = await execResp.json();
        return {
          status:
            execResult?.data?.status ||
            (execResult?.success === false ? 'failed' : 'completed'),
          success: execResult?.success !== false,
          gateway: 'canonical_execution_orchestrator',
          plan_id: planData.plan_id,
          execution_id: execResult?.data?.execution_id,
          result: execResult?.data?.result || execResult,
        };
      } catch (networkErr: any) {
        return {
          status: 'unavailable',
          success: false,
          error: `Canonical execution gateway unreachable during execution: ${networkErr?.message || networkErr}`,
          plan_id: planData.plan_id,
          gateway: 'canonical_execution_orchestrator',
        };
      }
    }

    return {
      status: 'pending_approval',
      success: false,
      requires_approval: true,
      decision: planData.decision,
      reason: planData.reason,
      plan_id: planData.plan_id,
      gateway: 'canonical_execution_orchestrator',
      message: 'Plan requires human or maker-checker approval before canonical execution.',
    };
  },
});

// ---------------------------------------------------------------------------
// Standard agents — share the same boilerplate (tools={run_python, request_canonical_execution}, standard
// memory). Adding a new standard agent = append one entry to the array.
// ---------------------------------------------------------------------------

const standardAgentConfigs: Array<{
  id: string;
  name: string;
  promptHandle: string;
}> = [
  { id: 'load-flow-agent', name: 'Load Flow Analysis Agent', promptHandle: 'load_flow_agent' },
  { id: 'short-circuit-agent', name: 'Short Circuit Analysis Agent', promptHandle: 'short_circuit_agent' },
  { id: 'arcflash-agent', name: 'Arc Flash Analysis Agent', promptHandle: 'arcflash_agent_prompt' },
  { id: 'protection-agent', name: 'Protection Coordination Agent', promptHandle: 'protection_agent' },
  { id: 'motorstarting-agent', name: 'Motor Starting Analysis Agent', promptHandle: 'motor_starting_agent' },
  { id: 'etap-engineer-agent', name: 'ETAP Engineering Agent', promptHandle: 'etap_engineer_agent' },
  { id: 'etap-expert-agent', name: 'ETAP Expert Skill Agent', promptHandle: 'etap_expert_agent' },
  { id: 'code-guard-agent', name: 'Code Guard Agent', promptHandle: 'code_guard_agent' },
];

const created: Record<string, Agent> = {};
for (const cfg of standardAgentConfigs) {
  created[cfg.id] = await createAgent({
    ...cfg,
    tools: {
      run_python,
      request_canonical_execution,
    },
  });
}

const loadFlowAgent = created['load-flow-agent'];
const shortCircuitAgent = created['short-circuit-agent'];
const arcFlashAgent = created['arcflash-agent'];
const protectionAgent = created['protection-agent'];
const motorStartingAgent = created['motorstarting-agent'];
const etapEngineerAgent = created['etap-engineer-agent'];
const etapExpertAgent = created['etap-expert-agent'];
const codeGuardAgent = created['code-guard-agent'];

// Goal Planner — no tools, no memory, but has an output schema.
const goalPlannerOutputSchema = z.object({
  problem_understanding: z.string(),
  tasks: z.array(
    z.object({
      name: z.string(),
      estimated_duration_hours: z.number(),
      priority: z.string(),
      dependencies: z.array(z.string()).optional(),
      notes: z.string().optional(),
    }),
  ),
  prioritization_logic: z.string(),
  daily_plan: z.array(z.string()),
  risks: z.array(z.string()),
  recommendations: z.array(z.string()),
});

const goalPlannerAgent = await createAgent({
  id: 'goal-planner-agent',
  name: 'Goal Planner Agent',
  promptHandle: 'goal_planner_agent',
  outputSchema: goalPlannerOutputSchema,
  noMemory: true,
});

// Weather Agent — uses weatherTool instead of run_python, standard memory.
const weatherAgent = await createAgent({
  id: 'weather-agent',
  name: 'Weather Agent',
  promptHandle: 'weather_agent',
  tools: { weatherTool },
});

// Power System Coordinator — has sub-agents, 12 maxSteps, memory, and resilient routing options.
const powerSystemCoordinatorAgent = await createAgent({
  id: 'power-system-coordinator-agent',
  name: 'Power System Coordinator Agent',
  promptHandle: 'power_system_coordinator_agent',
  memory: { maxMessages: 30, ttl: 3600 },
  subAgents: {
    loadFlowAgent,
    shortCircuitAgent,
    protectionAgent,
    motorStartingAgent,
    arcFlashAgent,
    etapEngineerAgent,
    goalPlannerAgent,
    weatherAgent,
    etapExpertAgent,
    codeGuardAgent,
  },
  defaultNetworkOptions: {
    maxSteps: 12,
    routing: {
      additionalInstructions: `
Prefer the narrowest specialist agent that can safely answer the user request. 
On ambiguity or unfamiliar terms, attempt domain synonyms first, then ask at most one clarifying question, then fall back safely. 
If a sub-agent returns a successful result, exit immediately. 
If 3 consecutive failures occur, exit with error.
BUDGET AWARENESS: Track tool calls. If >10 calls without final answer, ask user to narrow scope or split question.

CANONICAL ARCHITECTURE ENFORCEMENT (Phase 9 & 10):
The architecture is strictly:
  User Intent -> AI Interpretation -> ExecutionPlan -> Capability Selection -> Canonical ExecutionRequest -> Canonical ExecutionOrchestrator
NOT:
  User -> LLM -> agent.execute() -> engineering result

AGENTS ROLE:
- Reason, interpret intent, select capability from the canonical registry, construct parameters, coordinate specialized agents.
- For authoritative studies (Load Flow, Short Circuit, Arc Flash, Relay Coordination, Motor Starting), build an ExecutionPlan and dispatch via request_canonical_execution.
- NEVER calculate authoritative engineering studies directly in Python (no solving load flow, short circuit, arc flash in run_python).
- run_python is strictly advisory-only for intermediate assistance (scratchpad math, unit conversion, formatting).
- Review intermediate results from the canonical ExecutionOrchestrator and explain results to the user.
`.trim(),
    },
  },
});

export {
  loadFlowAgent,
  shortCircuitAgent,
  arcFlashAgent,
  protectionAgent,
  motorStartingAgent,
  etapEngineerAgent,
  etapExpertAgent,
  codeGuardAgent,
  goalPlannerAgent,
  weatherAgent,
  powerSystemCoordinatorAgent,
  request_canonical_execution,
};
