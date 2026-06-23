import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { run_python } from '../tools/python-tool';
import { getSystemPrompt } from '../prompts';
import { getActiveModelConfig } from '../lib/model-config';

const promptContent = await getSystemPrompt('load_flow_agent');

export const loadFlowAgent = new Agent({
  id: 'load-flow-agent',
  name: 'Load Flow Analysis Agent',
  instructions: promptContent,
  model: getActiveModelConfig() as any,
  tools: { run_python },
  memory: new Memory(),
});
