<<<<<<< HEAD
import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { run_python } from '../tools/python-tool';
import { getSystemPrompt } from '../prompts';
import { getActiveModelConfig } from '../lib/model-config';

const promptContent = await getSystemPrompt('arcflash_agent_prompt');
=======
import { Agent } from "@mastra/core/agent";
import { Memory } from "@mastra/memory";
import { run_python } from "../tools/python-tool";
import { getSystemPrompt } from "../prompts";
import { getActiveModelConfig } from "../lib/model-config";

const promptContent = await getSystemPrompt("arcflash_agent_prompt");
>>>>>>> origin/fix/scenario-tests-properly

export const arcFlashAgent = new Agent({
  id: 'arcflash-agent',
  name: 'Arc Flash Analysis Agent',
  instructions: promptContent,
  model: getActiveModelConfig() as any,
  tools: { run_python },
<<<<<<< HEAD
  // ARCHITECTURE AUDIT FIX (F-06): Memory configured with TTL and limits
  memory: new Memory({
    maxMessages: 30,
    ttl: 3600, // 1 hour for engineering sessions
  }),
=======
  memory: new Memory(),
>>>>>>> origin/fix/scenario-tests-properly
});
