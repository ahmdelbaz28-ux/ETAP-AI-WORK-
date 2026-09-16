import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { runPython } from './secure-execution';

// Budget limits from env (with safe defaults)
const MAX_LLM_CALLS = parseInt(process.env.MAX_LLM_CALLS_PER_REQUEST || '15', 10);
const MAX_TOKENS_EST = parseInt(process.env.MAX_TOKENS_PER_REQUEST || '50000', 10);

// Request context key for tracking tool calls per request
const TOOL_CALL_COUNT_KEY = 'etap:tool_call_count';

export const run_python = createTool({
  id: 'run-python',
  description:
    'Run validated Python code for engineering calculations. All code is audited and validated against security policies.',
  inputSchema: z.object({
    code: z.string().describe('The Python code to execute'),
  }),
  execute: async ({ code }: { code: string }, context?: any) => {
    // 1. Token budget enforcement — fail fast
    const estimatedTokens = Math.ceil(code.length / 4);
    if (estimatedTokens > MAX_TOKENS_EST) {
      throw new Error(`TOKEN_BUDGET_EXCEEDED: ~${estimatedTokens}/${MAX_TOKENS_EST} (code too large)`);
    }

    // 2. Per-request tool call counter via requestContext
    let nextCalls = 1;
    const requestContext = context?.requestContext;
    if (requestContext) {
      const currentCalls =
        typeof requestContext.get === 'function'
          ? (requestContext.get(TOOL_CALL_COUNT_KEY) as number) || 0
          : ((requestContext as Record<string, unknown>)[TOOL_CALL_COUNT_KEY] as number) || 0;
      nextCalls = currentCalls + 1;

      if (nextCalls > MAX_LLM_CALLS) {
        throw new Error(
          `TOOL_CALL_BUDGET_EXCEEDED: ${nextCalls}/${MAX_LLM_CALLS} tool calls in this request. ` +
          'Narrow your question or split into multiple requests.'
        );
      }

      // Increment counter for subsequent tool calls in this request
      if (typeof requestContext.set === 'function') {
        requestContext.set(TOOL_CALL_COUNT_KEY, nextCalls);
      } else {
        (requestContext as Record<string, unknown>)[TOOL_CALL_COUNT_KEY] = nextCalls;
      }
    }

    // 3. Execute with observability
    const runFn = async () => runPython(code);
    const result = context?.observe?.span
      ? await context.observe.span('run_python', runFn, {
          estimatedTokens,
          callNumber: nextCalls,
          maxCalls: MAX_LLM_CALLS,
        })
      : await runFn();

    return result.output;
  },
});
