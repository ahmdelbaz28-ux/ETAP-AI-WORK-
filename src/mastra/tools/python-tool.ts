import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { executeSecureScript } from './_spawn-helpers';

const PYTHON_TIMEOUT_MS = 30000; // 30 second timeout

export const run_python = createTool({
  id: 'run-python',
  description:
    'Run validated Python code for engineering calculations. All code is audited and validated against security policies.',
  inputSchema: z.object({
    code: z.string().describe('The Python code to execute'),
  }),
  execute: async ({ code }: { code: string }) => {
    return executeSecureScript({
      binary: 'python',
      scriptPath: 'security/secure_executor.py',
      inputData: code,
      timeoutMs: PYTHON_TIMEOUT_MS,
      toolDisplayName: 'secure Python executor',
    });
  },
});
