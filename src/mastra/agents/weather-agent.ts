import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { weatherTool } from '../tools/weather-tool';
import { getSystemPrompt } from '../prompts';
import { getActiveModelConfig } from '../lib/model-config';

const promptContent = await getSystemPrompt('weather_agent');

export const weatherAgent = new Agent({
  id: 'weather-agent',
  name: 'Weather Agent',
  instructions: promptContent,
  model: getActiveModelConfig() as any,
  tools: { weatherTool },
  // ARCHITECTURE AUDIT FIX (F-06): Memory configured with TTL and limits
  memory: new Memory({
    maxMessages: 30,
    ttl: 3600, // 1 hour for engineering sessions
  }),
});
