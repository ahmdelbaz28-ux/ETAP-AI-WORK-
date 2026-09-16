# Prompt: Implement Per-Request Call Counter in python-tool.ts

## Objective
Complete the missing `MAX_LLM_CALLS` enforcement in `src/mastra/tools/python-tool.ts` by implementing a real per-request call counter using Mastra's `requestContext` (available via the tool execution context).

## Current State
- `MAX_LLM_CALLS` env var is read (default 15)
- Token budget enforcement (`MAX_TOKENS_EST`) works correctly
- Call counter is only a comment: `// Track calls via a simple module-level counter... Note: For true per-request tracking, use Mastra's run context`

## Required Changes

### File: `src/mastra/tools/python-tool.ts`

Replace the entire file with this implementation:

```typescript
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
  execute: async ({ code }, context) => {
    // 1. Token budget enforcement — fail fast
    const estimatedTokens = Math.ceil(code.length / 4);
    if (estimatedTokens > MAX_TOKENS_EST) {
      throw new Error(`TOKEN_BUDGET_EXCEEDED: ~${estimatedTokens}/${MAX_TOKENS_EST} (code too large)`);
    }

    // 2. Per-request tool call counter via requestContext
    const requestContext = context.requestContext;
    const currentCalls = (requestContext.get(TOOL_CALL_COUNT_KEY) as number) || 0;
    const nextCalls = currentCalls + 1;

    if (nextCalls > MAX_LLM_CALLS) {
      throw new Error(
        `TOOL_CALL_BUDGET_EXCEEDED: ${nextCalls}/${MAX_LLM_CALLS} tool calls in this request. ` +
        'Narrow your question or split into multiple requests.'
      );
    }

    // Increment counter for subsequent tool calls in this request
    requestContext.set(TOOL_CALL_COUNT_KEY, nextCalls);

    // 3. Execute with observability
    const result = await context.observe.span('run_python', async () => {
      return runPython(code);
    }, {
      estimatedTokens,
      callNumber: nextCalls,
      maxCalls: MAX_LLM_CALLS,
    });

    return result.output;
  },
});
```

## Verification Steps

1. **TypeCheck**: Run `npm run typecheck` in project root — must pass with 0 errors
2. **Scenario Tests**: Run `pnpm test:scenarios` — all 29 tests must pass
3. **Manual Test**: In chat, ask a question that triggers multiple `run-python` calls (e.g., "Run load flow, then short circuit, then arc flash for the same system") — should fail fast after 15 calls with clear error message

## Acceptance Criteria
- ✅ `MAX_LLM_CALLS` enforced per-request (not global)
- ✅ Counter resets for each new user request
- ✅ Clear error message when limit exceeded
- ✅ Works with Mastra's `requestContext` (no module-level state)
- ✅ Observability span includes call metadata
- ✅ All existing tests pass