import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { run_python } from '../tools/python-tool';
import { getSystemPrompt } from '../prompts';
import { getActiveModelConfig } from '../lib/model-config';

const promptContent = await getSystemPrompt('motor_starting_agent');

export const motorStartingAgent = new Agent({
  id: 'motorstarting-agent',
  name: 'Motor Starting Analysis Agent',
  instructions: promptContent,
  model: getActiveModelConfig() as any,
  tools: { run_python },
  // ARCHITECTURE AUDIT FIX (F-06): Memory configured with TTL and limits
  memory: new Memory({
    maxMessages: 30,
    ttl: 3600, // 1 hour for engineering sessions
  } as any),
});
