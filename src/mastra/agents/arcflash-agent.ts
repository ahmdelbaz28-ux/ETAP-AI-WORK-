import { Agent } from "@mastra/core/agent";
import { Memory } from "@mastra/memory";
import { run_python } from "../tools/python-tool";
import { getSystemPrompt } from "../prompts";
import { getActiveModelConfig } from "../lib/model-config";

const promptContent = await getSystemPrompt("arcflash_agent_prompt");

export const arcFlashAgent = new Agent({
  id: 'arc-flash-agent',
  name: 'Arc Flash Analysis Agent',
  instructions: promptContent,
  model: getActiveModelConfig(),
  tools: { run_python },
  memory: new Memory(),
});
