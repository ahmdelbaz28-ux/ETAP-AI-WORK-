import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import type { ZodType } from 'zod';
import { getSystemPrompt } from '../prompts';
import { getActiveModelConfig } from '../lib/model-config';
import { run_python } from '../tools/python-tool';

export interface AgentConfig {
  id: string;
  name: string;
  promptHandle: string;
  tools?: Record<string, unknown>;
  outputSchema?: ZodType;
  memory?: { maxMessages: number; ttl: number };
  subAgents?: Record<string, Agent>;
  defaultNetworkOptions?: Record<string, unknown>;
  noMemory?: boolean;
}

const DEFAULT_MEMORY = { maxMessages: 30, ttl: 3600 };

export async function createAgent(config: AgentConfig): Promise<Agent> {
  const promptContent = await getSystemPrompt(config.promptHandle);

  const agentConfig: Record<string, unknown> = {
    id: config.id,
    name: config.name,
    instructions: promptContent,
    model: getActiveModelConfig() as any,
  };

  if (config.tools) {
    agentConfig.tools = config.tools;
  }

  if (config.outputSchema) {
    agentConfig.outputSchema = config.outputSchema;
  }

  if (!config.noMemory) {
    const mem = config.memory ?? DEFAULT_MEMORY;
    agentConfig.memory = new Memory(mem as any);
  }

  if (config.subAgents) {
    agentConfig.agents = config.subAgents;
  }

  if (config.defaultNetworkOptions) {
    agentConfig.defaultNetworkOptions = config.defaultNetworkOptions;
  }

  return new Agent(agentConfig as any);
}
