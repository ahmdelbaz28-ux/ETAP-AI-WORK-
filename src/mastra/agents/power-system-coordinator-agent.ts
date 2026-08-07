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
  // ARCHITECTURE AUDIT FIX (F-06): Memory now configured with TTL and limits
  // to prevent unbounded growth and cross-session contamination.
  // maxSteps reduced from 10 to 7 with explicit early-exit guidance.
  memory: new Memory({
    // Maximum conversation turns before auto-truncation
    maxMessages: 50,
    // Time-to-live for memory entries (in seconds) — 1 hour for engineering sessions
    ttl: 3600,
  }),
  defaultNetworkOptions: {
    maxSteps: 7, // F-11: Reduced from 10 — bounded repair loop
    routing: {
      additionalInstructions: 'Prefer the narrowest specialist agent that can safely answer the user request. If a sub-agent returns a successful result, exit immediately. If 3 consecutive failures occur, exit with error.',

  memory: new Memory(),
  defaultNetworkOptions: {
    maxSteps: 10,
    routing: {
      additionalInstructions: 'Prefer the narrowest specialist agent that can safely answer the user request.',
    },
  },
});
