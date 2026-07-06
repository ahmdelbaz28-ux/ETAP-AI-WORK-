/**
 * Shared helpers for Mastra tool executors that spawn Python helper scripts.
 *
 * Centralises the security hardening that EVERY tool must apply:
 *   1. Spawn via `spawn('python', [script])` — never `exec` — to prevent
 *      shell injection.
 *   2. Pass untrusted input via stdin, never as a CLI arg.
 *   3. Override `PATH` with a vetted list of system directories so a
 *      poisoned parent `PATH` cannot make us exec a trojaned `python`.
 *      (SonarCloud typescript:S4036)
 *   4. Always set a hard timeout + max-output guard.
 *
 * Keeping this in one place avoids the duplication that SonarCloud flagged
 * between `powershell-tool.ts` and `python-tool.ts` (rule S4144 /
 * new_duplicated_lines_density).
 */

import { spawn, type ChildProcess } from 'node:child_process';

/**
 * Vetted list of system directories. We deliberately EXCLUDE any directory
 * a non-root user can write to (no `/usr/local/share`, no npm/yarn global
 * dirs, no `~/.local/bin`).
 *
 * If `python` is not resolvable inside this list, `spawn` will fail loudly
 * with ENOENT — which is exactly what we want (no silent fallback).
 */
export const SAFE_SYSTEM_PATH = [
  '/usr/local/bin',
  '/usr/bin',
  '/bin',
  '/usr/local/sbin',
  '/usr/sbin',
  '/sbin',
].join(':');

/**
 * Build a clean `env` for a spawned child process:
 *   - Copies the current `process.env` (so PATH-dependent binaries like
 *     `python`-linked shared libs still work).
 *   - DELETES `PATH` from the copy (SonarCloud typescript:S4036: the parent
 *     process's PATH could be poisoned by an attacker with write access to
 *     a non-vetted directory).
 *   - Sets our `SAFE_SYSTEM_PATH` as the only PATH the child sees.
 *   - Sets Python hardening flags (no .pyc, unbuffered output).
 *
 * Returns a fresh object — does NOT mutate `process.env`.
 */
export function buildSafeSpawnEnv(): Record<string, string> {
  // Object-spread + delete is the cleanest way to drop PATH without
  // triggering `void` operator (typescript:S3735) or unused-variable
  // (typescript:S1854) lints.
  const env: Record<string, string> = { ...process.env } as Record<string, string>;
  delete env.PATH;
  // NOSONAR — typescript:S4036: SAFE_SYSTEM_PATH is a compile-time constant
  // containing only vetted system directories (/usr/local/bin, /usr/bin, /bin,
  // /usr/local/sbin, /usr/sbin, /sbin). None of these are writable by non-root
  // users. We explicitly DELETE the parent PATH above and replace it with this
  // vetted list so a poisoned parent PATH cannot leak into the child process.
  env.PATH = SAFE_SYSTEM_PATH;  // NOSONAR — S4036: vetted system dirs only
  env.PYTHONDONTWRITEBYTECODE = '1';
  env.PYTHONUNBUFFERED = '1';
  return env;
}

/**
 * Spawn a Python helper script with all the security hardening applied.
 *
 * Caller is responsible for wiring up `stdin`/`stdout`/`stderr` handlers
 * on the returned `ChildProcess` (so each tool can implement its own
 * output truncation / timeout cleanup).
 */
export function spawnPythonSecure(
  scriptPath: string,
  opts: { timeoutMs: number },
): ChildProcess {
  // NOSONAR — typescript:S4036: the env passed to spawn is built by
  // buildSafeSpawnEnv() which replaces PATH with SAFE_SYSTEM_PATH (a
  // fixed list of root-owned system directories). See the comment on
  // `env.PATH = SAFE_SYSTEM_PATH` above for the full security rationale.
  return spawn('python', [scriptPath], {  // NOSONAR — S4036: env uses vetted SAFE_SYSTEM_PATH
    env: buildSafeSpawnEnv(),
    stdio: ['pipe', 'pipe', 'pipe'],
    timeout: opts.timeoutMs,
  });
}
