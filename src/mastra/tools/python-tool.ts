import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { runPython } from './secure-execution';

export const run_python = createTool({
  id: 'run-python',
  description:
    'Run validated Python code for engineering calculations. All code is audited and validated against security policies.',
  inputSchema: z.object({
    code: z.string().describe('The Python code to execute'),
  }),
  execute: async ({ code }: { code: string }) => {
    const result = await runPython(code);
    return result.output;
  },
});
