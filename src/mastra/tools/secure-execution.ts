/**
 * secure-execution.ts — Sandboxed Script Execution Service
 * ========================================================
 * Deep module providing hardened script execution across python, node,
 * and powershell runtimes.
 *
 * Implements the Port-Adapter pattern (LauncherPort):
 * - External Seam: `run`, `runPython`, `runNode`, `runPowershell`
 * - Internal Port: `LauncherPort`
 * - Production Adapter: `SpawnLauncherAdapter` (spawn without shell, vetted PATH, stdin transport)
 * - Test Adapter: `InMemoryLauncherAdapter` (deterministic in-memory execution)
 */

import { spawnSecure } from './_spawn-helpers';

export type Kind = 'python' | 'node' | 'powershell';

export interface RunOpts {
  timeoutMs?: number;
  maxOutputLength?: number;
  allowedExitCodes?: number[];
  taskId?: string;
  studyType?: string;
  launcher?: LauncherPort;
}

export interface RunResult {
  output: string;
  truncated: boolean;
  exitCode: number;
}

export interface LaunchSpec {
  binary: 'python' | 'node';
  scriptPath: string;
  stdinPayload: string;
  timeoutMs: number;
}

export interface RawLaunchResult {
  stdout: string;
  stderr: string;
  exitCode: number | null;
  timedOut: boolean;
}

export interface LauncherPort {
  launch(spec: LaunchSpec): Promise<RawLaunchResult>;
}

interface RuntimePolicy {
  binary: 'python' | 'node';
  scriptPath: string;
  defaultTimeoutMs: number;
  defaultAllowedExitCodes: number[];
  displayName: string;
}

const RUNTIME_POLICIES: Record<Kind, RuntimePolicy> = {
  python: {
    binary: 'python',
    scriptPath: 'security/secure_executor.py',
    defaultTimeoutMs: 30000,
    defaultAllowedExitCodes: [0],
    displayName: 'secure Python executor',
  },
  node: {
    binary: 'node',
    scriptPath: 'security/secure_node_executor.cjs',
    defaultTimeoutMs: 6000,
    defaultAllowedExitCodes: [0, 3],
    displayName: 'Node sandbox',
  },
  powershell: {
    binary: 'python',
    scriptPath: 'security/secure_powershell_executor.py',
    defaultTimeoutMs: 30000,
    defaultAllowedExitCodes: [0],
    displayName: 'secure PowerShell executor',
  },
};

/**
 * Production adapter spawning real sub-processes with vetted PATH and stdin isolation.
 */
export class SpawnLauncherAdapter implements LauncherPort {
  async launch(spec: LaunchSpec): Promise<RawLaunchResult> {
    return new Promise<RawLaunchResult>((resolve, reject) => {
      let timedOut = false;
      const child = spawnSecure(spec.binary, spec.scriptPath, { timeoutMs: spec.timeoutMs });

      const stdoutStream = child.stdout;
      const stderrStream = child.stderr;

      if (!stdoutStream || !stderrStream) {
        reject(new Error(`Failed to get stdio streams for ${spec.binary}`));
        return;
      }

      let stdout = '';
      let stderr = '';

      stdoutStream.on('data', (data: Buffer) => {
        stdout += data.toString();
      });

      stderrStream.on('data', (data: Buffer) => {
        stderr += data.toString();
      });

      child.on('error', (err: Error & { code?: string }) => {
        if (err.code === 'ETIMEDOUT' || err.message.includes('timeout')) {
          timedOut = true;
        } else {
          reject(err);
        }
      });

      child.on('close', (exitCode: number | null, signal: NodeJS.Signals | null) => {
        if (signal === 'SIGTERM' || signal === 'SIGKILL') {
          timedOut = true;
        }
        resolve({
          stdout,
          stderr,
          exitCode,
          timedOut,
        });
      });

      const stdinStream = child.stdin;
      if (stdinStream) {
        stdinStream.write(spec.stdinPayload);
        stdinStream.end();
      } else {
        reject(new Error(`Failed to get stdin stream for ${spec.binary}`));
      }
    });
  }
}

export type CannedEnvelope = {
  success: boolean;
  output?: string;
  error?: string;
  error_type?: string;
};

/**
 * Test adapter allowing simulated executions with zero subprocess overhead.
 */
export class InMemoryLauncherAdapter implements LauncherPort {
  public launches: LaunchSpec[] = [];
  private handler: (spec: LaunchSpec) => Promise<RawLaunchResult> | RawLaunchResult;

  constructor(
    handlerOrResult?:
      | Partial<RawLaunchResult>
      | CannedEnvelope
      | ((spec: LaunchSpec) => Promise<RawLaunchResult> | RawLaunchResult),
  ) {
    if (typeof handlerOrResult === 'function') {
      this.handler = handlerOrResult;
    } else if (handlerOrResult && 'success' in handlerOrResult) {
      this.handler = () => ({
        stdout: JSON.stringify(handlerOrResult),
        stderr: '',
        exitCode: handlerOrResult.success ? 0 : 1,
        timedOut: false,
      });
    } else {
      const partial = handlerOrResult || {};
      this.handler = () => ({
        stdout: partial.stdout ?? '{"success":true,"output":""}',
        stderr: partial.stderr ?? '',
        exitCode: partial.exitCode ?? 0,
        timedOut: partial.timedOut ?? false,
      });
    }
  }

  setResult(result: Partial<RawLaunchResult> | CannedEnvelope): void {
    if ('success' in result) {
      this.handler = () => ({
        stdout: JSON.stringify(result),
        stderr: '',
        exitCode: result.success ? 0 : 1,
        timedOut: false,
      });
    } else {
      this.handler = () => ({
        stdout: result.stdout ?? '{"success":true,"output":""}',
        stderr: result.stderr ?? '',
        exitCode: result.exitCode ?? 0,
        timedOut: result.timedOut ?? false,
      });
    }
  }

  setHandler(handler: (spec: LaunchSpec) => Promise<RawLaunchResult> | RawLaunchResult): void {
    this.handler = handler;
  }

  async launch(spec: LaunchSpec): Promise<RawLaunchResult> {
    this.launches.push(spec);
    return this.handler(spec);
  }
}

let defaultLauncher: LauncherPort = new SpawnLauncherAdapter();

export function getDefaultLauncher(): LauncherPort {
  return defaultLauncher;
}

export function setDefaultLauncher(launcher: LauncherPort): void {
  defaultLauncher = launcher;
}

interface ExecutionEnvelope {
  success: boolean;
  output?: string;
  error?: string;
  error_type?: string;
}

function parseEnvelope(stdout?: string): ExecutionEnvelope | null {
  const trimmed = stdout?.trim();
  if (!trimmed) return null;
  try {
    const parsed = JSON.parse(trimmed);
    if (parsed && typeof parsed === 'object' && typeof parsed.success === 'boolean') {
      return parsed as ExecutionEnvelope;
    }
  } catch {
    return null;
  }
  return null;
}

function checkExitCode(
  raw: { exitCode: number | null; stderr?: string },
  allowedExitCodes: number[],
  displayName: string,
): void {
  if (raw.exitCode !== null && !allowedExitCodes.includes(raw.exitCode)) {
    const errMessage = raw.stderr?.trim() || `Process exited with code ${raw.exitCode}`;
    throw new Error(`${displayName} failed: ${errMessage}`);
  }
}

function handleEnvelopeResult(
  envelope: ExecutionEnvelope,
  raw: { exitCode: number | null; stderr?: string },
  policy: RuntimePolicy,
  allowedExitCodes: number[],
  maxOutputLength: number,
): RunResult {
  if (envelope.success) {
    checkExitCode(raw, allowedExitCodes, policy.displayName);
    const rawOutput = envelope.output || '';
    if (rawOutput.length > maxOutputLength) {
      return {
        output: rawOutput.substring(0, maxOutputLength) + '\n... [output truncated]',
        truncated: true,
        exitCode: raw.exitCode ?? 0,
      };
    }
    return {
      output: rawOutput,
      truncated: false,
      exitCode: raw.exitCode ?? 0,
    };
  }

  const errType = envelope.error_type ? ` [${envelope.error_type}]` : '';
  throw new Error(
    `${policy.displayName} error${errType}: ${envelope.error || 'Execution failed without specific error message'}`,
  );
}

/**
 * Core sandboxed execution function applying all security policies:
 * - Runtime allow-listing
 * - Hard execution timeout
 * - Output length capping
 * - JSON envelope decoding
 * - Exit code enforcement
 */
export async function run(req: { kind: Kind; code: string; opts?: RunOpts }): Promise<RunResult> {
  const policy = RUNTIME_POLICIES[req.kind];
  if (!policy) {
    throw new Error(`Unsupported script execution kind: ${String(req.kind)}`);
  }

  const timeoutMs = req.opts?.timeoutMs ?? policy.defaultTimeoutMs;
  const maxOutputLength = req.opts?.maxOutputLength ?? 10000;
  const allowedExitCodes = req.opts?.allowedExitCodes ?? policy.defaultAllowedExitCodes;
  const launcher = req.opts?.launcher ?? defaultLauncher;

  const raw = await launcher.launch({
    binary: policy.binary,
    scriptPath: policy.scriptPath,
    stdinPayload: req.code,
    timeoutMs,
  });

  if (raw.timedOut) {
    throw new Error(`${policy.displayName} timed out after ${timeoutMs}ms`);
  }

  const envelope = parseEnvelope(raw.stdout);
  if (envelope) {
    return handleEnvelopeResult(envelope, raw, policy, allowedExitCodes, maxOutputLength);
  }

  // Non-envelope failure: check exit code
  checkExitCode(raw, allowedExitCodes, policy.displayName);

  // Exit code was allowed, but stdout was missing or not a valid envelope
  throw new Error(`Failed to parse executor response: ${raw.stdout}`);
}

export async function runPython(code: string, opts?: RunOpts): Promise<RunResult> {
  return run({ kind: 'python', code, opts });
}

export async function runNode(code: string, opts?: RunOpts): Promise<RunResult> {
  return run({ kind: 'node', code, opts });
}

export async function runPowershell(command: string, opts?: RunOpts): Promise<RunResult> {
  return run({ kind: 'powershell', code: command, opts });
}
