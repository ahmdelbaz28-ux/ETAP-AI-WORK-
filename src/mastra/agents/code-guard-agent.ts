import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { run_python } from '../tools/python-tool';
import { getSystemPrompt } from '../prompts';
import { getActiveModelConfig } from '../lib/model-config';

/**
 * Code Guard Agent — AI-Powered Code Quality Review
 *
 * Integrates the guard-skills quality gates (github.com/amElnagdy/guard-skills)
 * into the ETAP agent system. Reviews AI-generated code against:
 *   - 14 AI-specific failure modes (catch-all swallowing, hardcoded success, etc.)
 *   - 23 clean-code imperatives (SOLID, DRY/KISS/YAGNI, function length, etc.)
 *   - 9 universal testing rules + 3 LLM-specific rules
 *   - 10 documentation accuracy rules
 *
 * This agent uses the run_python tool to invoke the guards module
 * on the Engineering Service for AST-based analysis that cannot be
 * done purely via LLM reasoning.
 */
const promptContent = await getSystemPrompt('code_guard_agent');

export const codeGuardAgent = new Agent({
  id: 'code-guard-agent',
  name: 'Code Guard Agent',
  instructions: promptContent,
  model: getActiveModelConfig(),
  tools: { run_python },
  memory: new Memory(),
});
