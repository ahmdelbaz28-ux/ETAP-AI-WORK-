import { createTool } from '@mastra/core/tools';
import { spawn } from 'node:child_process';
import { z } from 'zod';

const PYTHON_TIMEOUT_MS = 30000; // 30 second timeout
const MAX_OUTPUT_LENGTH = 10000; // Maximum output length in characters

export const run_python = createTool({
  id: 'run-python',
  description: 'Run validated Python code for engineering calculations. All code is audited and validated against security policies.',
  inputSchema: z.object({
    code: z.string().describe('The Python code to execute'),
  }),
  execute: async ({ code }: { code: string }) => {
    return new Promise<string>((resolve, reject) => {
      const secureExecutorPath = 'security/secure_executor.py';

      // Use spawn instead of execFile to pass code via stdin (prevents shell injection).
      // SonarCloud tssecurity:S4036: PATH is hardcoded to a fixed list of
      // vetted system directories — we explicitly EXCLUDE process.env.PATH
      // from the spawned env so a poisoned parent PATH cannot leak in.
      const SAFE_PATH = [
        '/usr/local/bin',
        '/usr/bin',
        '/bin',
        '/usr/local/sbin',
        '/usr/sbin',
        '/sbin',
      ].join(':');
      // Build a clean env WITHOUT PATH first, then set our vetted PATH.
      const { PATH: _drop, ...cleanEnv } = process.env;
      void _drop;
      const child = spawn('python', [secureExecutorPath], {
        env: {
          ...cleanEnv,
          PATH: SAFE_PATH,
          PYTHONDONTWRITEBYTECODE: '1',
          PYTHONUNBUFFERED: '1',
        },
        stdio: ['pipe', 'pipe', 'pipe'],
        timeout: PYTHON_TIMEOUT_MS,
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
        reject(new Error(`Failed to start secure executor: ${err.message}`));
      });

      child.on('close', (exitCode) => {
        if (exitCode !== 0) {
          const errMessage = stderr?.trim() || `Process exited with code ${exitCode}`;
          reject(new Error(`Python execution failed: ${errMessage}`));
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
          // SonarCloud typescript:S4624: extracted nested template literal
          // into a separate variable for readability.
          const parseErrMsg = parseError instanceof Error ? ` (${parseError.message})` : '';
          reject(new Error(`Failed to parse executor response: ${stdout}${parseErrMsg}`));
        }
      });

      // Pass code via stdin instead of CLI arguments (prevents shell injection)
      child.stdin.write(code);
      child.stdin.end();
    });
  }
});
