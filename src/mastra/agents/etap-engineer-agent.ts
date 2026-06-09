import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { run_python } from '../tools/python-tool';
import { getSystemPrompt } from '../prompts';
import { getActiveModelConfig } from '../lib/model-config';

const promptContent = await getSystemPrompt('etap_engineer_agent');

export const etapEngineerAgent = new Agent({
  id: 'etap-engineer-agent',
  name: 'ETAP Engineering Agent',
  instructions: promptContent,
  model: getActiveModelConfig(),
  tools: { run_python },
  memory: new Memory(),
});
