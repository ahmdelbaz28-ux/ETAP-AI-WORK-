import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { run_python } from '../tools/python-tool';
import { getSystemPrompt } from '../prompts';
import { getActiveModelConfig } from '../lib/model-config';

const promptContent = await getSystemPrompt('protection_agent');

export const protectionAgent = new Agent({
  id: 'protection-coordination-agent',
  name: 'Protection Coordination Agent',
  instructions: promptContent,
  model: getActiveModelConfig(),
  tools: { run_python },
  memory: new Memory(),
});
