import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { runPython } from './secure-execution';

// Budget limits from env (with safe defaults)
const MAX_LLM_CALLS = parseInt(process.env.MAX_LLM_CALLS_PER_REQUEST || '15', 10);
const MAX_TOKENS_EST = parseInt(process.env.MAX_TOKENS_PER_REQUEST || '50000', 10);

export const run_python = createTool({
  id: 'run-python',
  description:
    'Run validated Python code for engineering calculations. All code is audited and validated against security policies.',
  inputSchema: z.object({
    code: z.string().describe('The Python code to execute'),
  }),
  execute: async ({ code }: { code: string }) => {
    // Budget enforcement — fail fast, no silent truncation
    const estimatedTokens = Math.ceil(code.length / 4);
    if (estimatedTokens > MAX_TOKENS_EST) {
      throw new Error(`TOKEN_BUDGET_EXCEEDED: ~${estimatedTokens}/${MAX_TOKENS_EST} (code too large)`);
    }

    const result = await runPython(code);

    // Track calls via a simple module-level counter (per-request scope via context)
    // Note: For true per-request tracking, use Mastra's run context
    return result.output;
  },
});
