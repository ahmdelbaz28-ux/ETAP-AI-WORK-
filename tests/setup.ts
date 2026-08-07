<<<<<<< HEAD
import { existsSync, unlinkSync } from 'node:fs';
=======
import { existsSync, unlinkSync } from 'fs';
>>>>>>> origin/fix/scenario-tests-properly

// Clean up any orphaned duckdb lock files and stale db from previous test runs
const files = ['mastra.duckdb-shm', 'mastra.duckdb-wal', 'mastra.duckdb'];
for (const f of files) {
  if (existsSync(f)) {
    try {
      unlinkSync(f);
    } catch {
      // ignore cleanup errors
    }
  }
}
