import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { executeSecureScript } from './_spawn-helpers';

const POWERSHELL_TIMEOUT_MS = 30000; // 30 second timeout

export const run_powershell = createTool({
  id: 'run-powershell',
  description:
    'Run safe PowerShell commands for engineering data retrieval and system queries. Only read-only and data-processing commands are permitted. All commands are validated against security policies before execution.',
  inputSchema: z.object({
    command: z.string().describe('The PowerShell command to execute (read-only commands only)'),
  }),
  execute: async ({ command }: { command: string }) => {
    return executeSecureScript({
      binary: 'python',
      scriptPath: 'security/secure_powershell_executor.py',
      inputData: command,
      timeoutMs: POWERSHELL_TIMEOUT_MS,
      toolDisplayName: 'secure PowerShell executor',
    });
  },
});
