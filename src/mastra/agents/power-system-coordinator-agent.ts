import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { getSystemPrompt } from '../prompts';
import { getActiveModelConfig } from '../lib/model-config';
import { arcFlashAgent } from './arcflash-agent';
import { etapEngineerAgent } from './etap-engineer-agent';
import { goalPlannerAgent } from './goal-planner-agent';
import { loadFlowAgent } from './loadflow-agent';
import { motorStartingAgent } from './motorstarting-agent';
import { protectionAgent } from './protection-agent';
import { shortCircuitAgent } from './shortcircuit-agent';

const promptContent = await getSystemPrompt('power_system_coordinator_agent');

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
