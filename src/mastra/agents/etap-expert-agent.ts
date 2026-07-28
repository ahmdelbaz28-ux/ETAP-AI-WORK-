import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { run_python } from '../tools/python-tool';
import { getSystemPrompt } from '../prompts';
import { getActiveModelConfig } from '../lib/model-config';

const promptContent = await getSystemPrompt('etap_expert_agent');

/**
 * ETAP Expert Skill Agent (Mastra / TypeScript side)
 *
 * This agent is the LLM-powered counterpart of the Python-side ETAPExpertAgent
 * (agents/etap_expert_agent.py). It uses the skill knowledge base
 * (skills/etap-expert.md, 4,400+ lines) as its system prompt and follows
 * the mandatory 6-step workflow with Format A/B/C/D responses.
 *
 * Routing: the Python orchestrator handles study_type="etap_expert" directly
 * via the rule-based classifier (no LLM call needed for deterministic cases).
 * This Mastra agent is invoked when the user wants a free-form chat experience
 * via /api/v1/agents/etap-expert/chat (TS-side gateway).
 *
 * Knowledge base: skills/etap-expert.md
 * System prompt:  skills/etap-ai-agent-system-prompt.md + prompts/etap_expert_agent.prompt.yaml
 */
export const etapExpertAgent = new Agent({
  id: 'etap-expert-agent',
  name: 'ETAP Expert Skill Agent',
  instructions: promptContent,
  model: getActiveModelConfig() as any,
  tools: { run_python },
  memory: new Memory(),
});
