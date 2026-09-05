/**
 * node-tool.ts — Mastra tool for running JavaScript code in a secure
 * V8 sandbox.
 *
 * Delegates to `secure-execution.ts:runNode`.
 * The actual sandboxing is performed by `isolated-vm` (separate V8 isolate).
 */

import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { runNode } from './secure-execution';

export const run_node = createTool({
  id: 'run-node',
  description:
    'Run validated JavaScript code in an isolated V8 sandbox. ' +
    'Use for JSON transformation, math calculations, and string manipulation. ' +
    'No I/O, no network, no filesystem, no require/import — only pure JS builtins (Math, JSON, Array, etc.).',
  inputSchema: z.object({
    code: z.string().describe('The JavaScript code to execute'),
  }),
  execute: async ({ code }: { code: string }) => {
    const result = await runNode(code);
    return result.output;
  },
});
