import { z } from 'zod';

import { Agent } from '@mastra/core/agent';
import { createAgent } from '../lib/agent-factory';
import { run_python } from '../tools/python-tool';
import { weatherTool } from '../tools/weather-tool';

// ---------------------------------------------------------------------------
// Standard agents — share the same boilerplate (tools={run_python}, standard
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
    tools: { run_python },
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

// Power System Coordinator — no tools, no memory, has sub-agents + network options.
const powerSystemCoordinatorAgent = await createAgent({
  id: 'power-system-coordinator-agent',
  name: 'Power System Coordinator Agent',
  promptHandle: 'power_system_coordinator_agent',
  noMemory: true,
  subAgents: {
    loadFlowAgent,
    shortCircuitAgent,
    protectionAgent,
    motorStartingAgent,
    arcFlashAgent,
    etapEngineerAgent,
    goalPlannerAgent,
  },
  defaultNetworkOptions: {
    maxSteps: 7,
    routing: {
      additionalInstructions:
        'Prefer the narrowest specialist agent that can safely answer the user request. If a sub-agent returns a successful result, exit immediately. If 3 consecutive failures occur, exit with error.',
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
};
