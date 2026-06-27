import { defineConfig } from 'vitest/config';
import { withScenario } from '@langwatch/scenario/integrations/vitest/config';
import VitestReporter from '@langwatch/scenario/integrations/vitest/reporter';
import dotenv from 'dotenv';

dotenv.config();

// Scenario tests need live LLM provider credentials. They auto-skip
// individually when no provider is available (see helpers.test-types.ts).
// In CI without credentials, SKIP_LIVE_SCENARIO_TESTS is set so all
// scenario tests skip cleanly instead of failing.
const isCI = process.env.CI === 'true' || process.env.VITEST === 'true';
process.env.SKIP_LIVE_SCENARIO_TESTS = process.env.SKIP_LIVE_SCENARIO_TESTS || (isCI ? 'true' : 'false');

export default withScenario(defineConfig({
  test: {
    globals: true,
    environment: 'node',
    testTimeout: 180000,
    hookTimeout: 180000,
    fileParallelism: false, // mastra.duckdb is not concurrency-safe
    reporters: ['default', new VitestReporter()],
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/scenarios/**/*.test.ts'],
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '.kilo/**',
      '.testsprite/**',
    ],
  },
}));
