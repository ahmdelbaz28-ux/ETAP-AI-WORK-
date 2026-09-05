/**
 * node-tool.ts — Mastra tool for running JavaScript code in a secure
 * V8 sandbox.
 *
 * Mirrors the security posture of `python-tool.ts` (which spawns
 * `security/secure_executor.py`) by spawning `security/secure_node_executor.js`
 * with the same hardened spawn helper (`spawnSecure('node', ...)`).
 *
 * The actual sandboxing is performed by `isolated-vm` (separate V8 isolate),
 * NOT by node:vm (which is not a security mechanism per Node.js docs).
 *
 * See `docs/NODE_SANDBOX.md` for the full security model.
 */

import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { executeSecureScript } from './_spawn-helpers';

const NODE_TIMEOUT_MS = 5000; // 5 second hard timeout (V8 isolate level)

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
    return executeSecureScript({
      binary: 'node',
      scriptPath: 'security/secure_node_executor.cjs',
      inputData: code,
      timeoutMs: NODE_TIMEOUT_MS + 1000,
      toolDisplayName: 'Node sandbox',
      allowedExitCodes: [0, 3],
    });
  },
});
