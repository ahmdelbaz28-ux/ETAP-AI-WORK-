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
import { spawnSecure } from './_spawn-helpers';

const NODE_TIMEOUT_MS = 5000; // 5 second hard timeout (V8 isolate level)
const MAX_OUTPUT_LENGTH = 10000; // Maximum output length in characters

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
    return new Promise<string>((resolve, reject) => {
      const secureExecutorPath = 'security/secure_node_executor.cjs';

      // Spawn a Node.js helper that runs the user code under a V8 isolate
      // (isolated-vm). All hardening (PATH override, stdin-only input,
      // hard timeout) lives in `spawnSecure` — see `_spawn-helpers.ts`.
      const child = spawnSecure('node', secureExecutorPath, {
        timeoutMs: NODE_TIMEOUT_MS + 1000, // 1s grace for the executor to report timeout cleanly
      });

      const stdoutStream = child.stdout;
      const stderrStream = child.stderr;

      if (!stdoutStream || !stderrStream) {
        reject(new Error('Failed to get stdio streams from sandbox'));
        return;
      }

      let stdout = '';
      let stderr = '';

      stdoutStream.on('data', (data: Buffer) => {
        stdout += data.toString();
      });

      stderrStream.on('data', (data: Buffer) => {
        stderr += data.toString();
      });

      child.on('error', (err: Error) => {
        reject(new Error(`Failed to start secure Node executor: ${err.message}`));
      });

      child.on('close', (exitCode: number) => {
        if (exitCode !== 0 && exitCode !== 3) {
          // exit 3 = sandbox caught a runtime error (still returns JSON)
          // other non-zero = setup failure
          const errMessage = stderr?.trim() || `Process exited with code ${exitCode}`;
          reject(new Error(`Node execution failed: ${errMessage}`));
          return;
        }

        try {
          const response = JSON.parse(stdout.trim());
          if (response.success) {
            const output = response.output || '';
            const finalOutput =
              output.length > MAX_OUTPUT_LENGTH
                ? output.substring(0, MAX_OUTPUT_LENGTH) + '\n... [output truncated]'
                : output;
            resolve(finalOutput);
          } else {
            const errType = response.error_type ? ` [${response.error_type}]` : '';
            reject(new Error(`Node sandbox error${errType}: ${response.error || 'unknown'}`));
          }
        } catch (parseError) {
          const parseErrMsg = parseError instanceof Error ? ` (${parseError.message})` : '';
          reject(new Error(`Failed to parse Node executor response: ${stdout}${parseErrMsg}`));
        }
      });

      // Pass code via stdin instead of CLI arguments (prevents shell injection)
      const stdinStream = child.stdin;
      if (stdinStream) {
        stdinStream.write(code);
        stdinStream.end();
      } else {
        reject(new Error('Failed to get stdin stream from sandbox'));
      }
    });
  },
});
