import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { run_python } from '../tools/python-tool';
import { getSystemPrompt } from '../prompts';
import { getActiveModelConfig } from '../lib/model-config';

const promptContent = await getSystemPrompt('short_circuit_agent');

export const shortCircuitAgent = new Agent({
  id: 'short-circuit-agent',
  name: 'Short Circuit Analysis Agent',
  instructions: promptContent,
  model: getActiveModelConfig(),
  tools: { run_python },
  memory: new Memory(),
});
