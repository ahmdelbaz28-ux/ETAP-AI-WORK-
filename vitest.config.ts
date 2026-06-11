import { defineConfig } from 'vitest/config';
import { withScenario } from '@langwatch/scenario/integrations/vitest/config';
import VitestReporter from '@langwatch/scenario/integrations/vitest/reporter';
import dotenv from 'dotenv';

dotenv.config();

// Hardening change: scenario tests are SKIPPED by default in CI/test environments.
// They will still skip individually if no real provider credentials are
// available — the per-test check in helpers.test-types.ts gates this.
// In CI (CI=true or VITEST=true), default to skipping to avoid invalid API key failures.
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
  },
}));
