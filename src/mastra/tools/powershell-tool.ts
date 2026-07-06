import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { spawnPythonSecure } from './_spawn-helpers';

const POWERSHELL_TIMEOUT_MS = 30000; // 30 second timeout
const MAX_OUTPUT_LENGTH = 10000; // Maximum output length in characters

export const run_powershell = createTool({
  id: 'run-powershell',
  description: 'Run safe PowerShell commands for engineering data retrieval and system queries. Only read-only and data-processing commands are permitted. All commands are validated against security policies before execution.',
  inputSchema: z.object({
    command: z.string().describe('The PowerShell command to execute (read-only commands only)'),
  }),
  execute: async ({ command }: { command: string }) => {
    return new Promise<string>((resolve, reject) => {
      const secureExecutorPath = 'security/secure_powershell_executor.py';

      // Spawn a Python helper that runs the PowerShell command under a
      // security policy. All hardening (PATH override, no .pyc, stdin-only
      // input, hard timeout) lives in `spawnPythonSecure` — see
      // `_spawn-helpers.ts` for the security rationale.
      const child = spawnPythonSecure(secureExecutorPath, {
        timeoutMs: POWERSHELL_TIMEOUT_MS,
      });

      let stdout = '';
      let stderr = '';

      child.stdout.on('data', (data: Buffer) => {
        stdout += data.toString();
      });

      child.stderr.on('data', (data: Buffer) => {
        stderr += data.toString();
      });

      child.on('error', (err) => {
        reject(new Error(`Failed to start secure PowerShell executor: ${err.message}`));
      });

      child.on('close', (exitCode) => {
        if (exitCode !== 0) {
          const errMessage = stderr?.trim() || `Process exited with code ${exitCode}`;
          reject(new Error(`PowerShell execution failed: ${errMessage}`));
          return;
        }

        try {
          const response = JSON.parse(stdout.trim());
          if (response.success) {
            const output = response.output || '';
            if (output.length > MAX_OUTPUT_LENGTH) {
              resolve(output.substring(0, MAX_OUTPUT_LENGTH) + '\n... [output truncated]');  // NOSONAR — typescript:S4624: false positive — string concatenation, not nested template literal
            } else {
              resolve(output);
            }
          } else {
            reject(new Error(response.error || 'Execution failed without specific error message'));
          }
        } catch (parseError) {
          // SonarCloud typescript:S4624: extracted the nested template literal
          // into a separate variable to keep the error message readable.
          const parseErrMsg = parseError instanceof Error ? ` (${parseError.message})` : '';
          reject(new Error(`Failed to parse executor response: ${stdout}${parseErrMsg}`));
        }
      });

      // Pass command via stdin instead of CLI arguments (prevents shell injection)
      child.stdin.write(command);
      child.stdin.end();
    });
  }
});
