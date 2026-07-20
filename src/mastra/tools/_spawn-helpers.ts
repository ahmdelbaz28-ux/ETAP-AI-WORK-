/**
 * Shared helpers for Mastra tool executors that spawn helper scripts.
 *
 * Centralises the security hardening that EVERY tool must apply:
 *   1. Spawn via `spawn(binary, [script])` — never `exec` — to prevent
 *      shell injection.
 *   2. Pass untrusted input via stdin, never as a CLI arg.
 *   3. Override `PATH` with a vetted list of system directories so a
 *      poisoned parent `PATH` cannot make us exec a trojaned binary.
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
 * If the target binary is not resolvable inside this list, `spawn` will
 * fail loudly with ENOENT — which is exactly what we want (no silent
 * fallback).
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
 *   - Sets Python hardening flags (no .pyc, unbuffered output) — harmless
 *     for non-Python children.
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
 * Spawn a helper script with all the security hardening applied.
 *
 * Generic version: caller specifies which binary (`python`, `node`, etc.)
 * to invoke. The PATH and env hardening is identical for any language.
 *
 * Caller is responsible for wiring up `stdin`/`stdout`/`stderr` handlers
 * on the returned `ChildProcess` (so each tool can implement its own
 * output truncation / timeout cleanup).
 *
 * @param binary - executable to run (`python`, `node`, `bash`, etc.)
 * @param scriptPath - path to the helper script
 * @param opts.timeoutMs - hard kill timeout for the child process
 */
export function spawnSecure(
  binary: string,
  scriptPath: string,
  opts: { timeoutMs: number },
): ChildProcess {
  // NOSONAR — typescript:S4036: the env passed to spawn is built by
  // buildSafeSpawnEnv() which replaces PATH with SAFE_SYSTEM_PATH (a
  // fixed list of root-owned system directories). See the comment on
  // `env.PATH = SAFE_SYSTEM_PATH` above for the full security rationale.
  return spawn(binary, [scriptPath], {  // NOSONAR — S4036: env uses vetted SAFE_SYSTEM_PATH
    env: buildSafeSpawnEnv(),
    stdio: ['pipe', 'pipe', 'pipe'],
    timeout: opts.timeoutMs,
  });
}

/**
 * Spawn a Python helper script with all the security hardening applied.
 *
 * Backwards-compatible wrapper around `spawnSecure('python', ...)`.
 * Existing callers (python-tool.ts, powershell-tool.ts) do not need to change.
 *
 * Caller is responsible for wiring up `stdin`/`stdout`/`stderr` handlers
 * on the returned `ChildProcess` (so each tool can implement its own
 * output truncation / timeout cleanup).
 *
 * @deprecated prefer `spawnSecure('python', ...)` for new code.
 */
export function spawnPythonSecure(
  scriptPath: string,
  opts: { timeoutMs: number },
): ChildProcess {
  return spawnSecure('python', scriptPath, opts);
}
