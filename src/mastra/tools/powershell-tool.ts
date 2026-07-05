import { createTool } from '@mastra/core/tools';
import { spawn } from 'node:child_process';
import { z } from 'zod';

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

      // Use spawn to pass command via stdin (prevents shell injection).
      // SonarCloud S4036: explicitly sanitize PATH to only well-known system
      // directories so a malicious user can't shadow `python` with a trojan.
      const safePath = ['/usr/local/bin', '/usr/bin', '/bin', '/usr/local/sbin', '/usr/sbin', '/sbin']
        .filter((p) => process.env.PATH?.includes(p))
        .join(':');
      const child = spawn('python', [secureExecutorPath], {
        env: {
          ...process.env,
          // Override PATH with only vetted system directories
          PATH: safePath || process.env.PATH,
          PYTHONDONTWRITEBYTECODE: '1',
          PYTHONUNBUFFERED: '1',
        },
        stdio: ['pipe', 'pipe', 'pipe'],
        timeout: POWERSHELL_TIMEOUT_MS,
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
              resolve(output.substring(0, MAX_OUTPUT_LENGTH) + '\n... [output truncated]');
            } else {
              resolve(output);
            }
          } else {
            reject(new Error(response.error || 'Execution failed without specific error message'));
          }
        } catch (parseError) {
          reject(new Error(`Failed to parse executor response: ${stdout}${parseError instanceof Error ? ` (${parseError.message})` : ''}`));
        }
      });

      // Pass command via stdin instead of CLI arguments (prevents shell injection)
      child.stdin.write(command);
      child.stdin.end();
    });
  }
});
