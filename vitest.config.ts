import { defineConfig } from 'vitest/config';
import { withScenario } from '@langwatch/scenario/integrations/vitest/config';
import VitestReporter from '@langwatch/scenario/integrations/vitest/reporter';
import dotenv from 'dotenv';

dotenv.config();

// Force skip live LLM scenario tests in CI/test environments unless explicitly enabled
process.env.SKIP_LIVE_SCENARIO_TESTS = process.env.SKIP_LIVE_SCENARIO_TESTS || 'true';

export default withScenario(defineConfig({
  test: {
    globals: true,
    environment: 'node',
    testTimeout: 180000,
    hookTimeout: 180000,
    fileParallelism: false,  // mastra.duckdb is not concurrency-safe; restore parallelism after upstream fix
    reporters: ['default', new VitestReporter()],
    setupFiles: ['./tests/setup.ts'],
  },
}));
