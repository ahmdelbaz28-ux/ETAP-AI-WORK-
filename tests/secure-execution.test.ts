import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  run,
  runPython,
  runNode,
  runPowershell,
  InMemoryLauncherAdapter,
  setDefaultLauncher,
  SpawnLauncherAdapter,
} from '../src/mastra/tools/secure-execution';
import { run_python } from '../src/mastra/tools/python-tool';
import { run_node } from '../src/mastra/tools/node-tool';
import { run_powershell } from '../src/mastra/tools/powershell-tool';

describe('Secure Execution Module (Port-Adapter)', () => {
  let inMemoryLauncher: InMemoryLauncherAdapter;

  beforeEach(() => {
    inMemoryLauncher = new InMemoryLauncherAdapter();
    setDefaultLauncher(inMemoryLauncher);
  });

  afterEach(() => {
    setDefaultLauncher(new SpawnLauncherAdapter());
  });

  it('executes python code and returns envelope output', async () => {
    inMemoryLauncher.setResult({
      success: true,
      output: '42.0',
    });

    const result = await runPython('print(42.0)');
    expect(result.output).toBe('42.0');
    expect(result.truncated).toBe(false);
    expect(result.exitCode).toBe(0);

    expect(inMemoryLauncher.launches).toHaveLength(1);
    expect(inMemoryLauncher.launches[0].binary).toBe('python');
    expect(inMemoryLauncher.launches[0].scriptPath).toBe('security/secure_executor.py');
    expect(inMemoryLauncher.launches[0].stdinPayload).toBe('print(42.0)');
  });

  it('truncates output when exceeding maxOutputLength', async () => {
    const longString = 'A'.repeat(150);
    inMemoryLauncher.setResult({
      success: true,
      output: longString,
    });

    const result = await runPython('print("A" * 150)', { maxOutputLength: 100 });
    expect(result.truncated).toBe(true);
    expect(result.output.length).toBeLessThan(longString.length);
    expect(result.output).toContain('... [output truncated]');
  });

  it('throws structured error with error_type when execution fails', async () => {
    inMemoryLauncher.setResult({
      success: false,
      error: 'Security policy violation: import os is blocked',
      error_type: 'SECURITY_VIOLATION',
    });

    await expect(runPython('import os')).rejects.toThrow(
      'secure Python executor error [SECURITY_VIOLATION]: Security policy violation: import os is blocked',
    );
  });

  it('accepts allowed exit codes like exit code 3 for Node isolate error', async () => {
    inMemoryLauncher.setHandler(() => ({
      stdout: JSON.stringify({
        success: false,
        error: 'RangeError: Maximum call stack size exceeded',
        error_type: 'RANGE_ERROR',
      }),
      stderr: '',
      exitCode: 3,
      timedOut: false,
    }));

    await expect(runNode('function f() { f(); } f();')).rejects.toThrow(
      'Node sandbox error [RANGE_ERROR]: RangeError: Maximum call stack size exceeded',
    );
  });

  it('rejects unexpected non-zero exit codes with stderr', async () => {
    inMemoryLauncher.setHandler(() => ({
      stdout: '',
      stderr: 'Fatal: segfault in sandbox',
      exitCode: 139,
      timedOut: false,
    }));

    await expect(runPython('bad code')).rejects.toThrow(
      'secure Python executor failed: Fatal: segfault in sandbox',
    );
  });

  it('handles execution timeouts', async () => {
    inMemoryLauncher.setHandler(() => ({
      stdout: '',
      stderr: '',
      exitCode: null,
      timedOut: true,
    }));

    await expect(runPython('while True: pass', { timeoutMs: 500 })).rejects.toThrow(
      'secure Python executor timed out after 500ms',
    );
  });

  it('throws on non-JSON stdout from script', async () => {
    inMemoryLauncher.setHandler(() => ({
      stdout: 'Internal Python traceback syntax error',
      stderr: '',
      exitCode: 0,
      timedOut: false,
    }));

    await expect(runPython('print(1)')).rejects.toThrow(
      'Failed to parse executor response: Internal Python traceback syntax error',
    );
  });

  it('correctly maps runPowershell to python binary and powershell executor script', async () => {
    inMemoryLauncher.setResult({
      success: true,
      output: 'powershell-result',
    });

    const result = await runPowershell('Get-Service');
    expect(result.output).toBe('powershell-result');
    expect(inMemoryLauncher.launches[0].binary).toBe('python');
    expect(inMemoryLauncher.launches[0].scriptPath).toBe('security/secure_powershell_executor.py');
    expect(inMemoryLauncher.launches[0].stdinPayload).toBe('Get-Service');
  });

  describe('Mastra Tool Wrappers', () => {
    it('run_python tool delegates to runPython and returns string output', async () => {
      inMemoryLauncher.setResult({
        success: true,
        output: 'tool-output',
      });

      const output = await run_python.execute!({ code: 'x = 1' }, {} as any);
      expect(output).toBe('tool-output');
    });

    it('run_node tool delegates to runNode and returns string output', async () => {
      inMemoryLauncher.setResult({
        success: true,
        output: 'node-result',
      });

      const output = await run_node.execute!({ code: 'Math.max(1, 2)' }, {} as any);
      expect(output).toBe('node-result');
      expect(inMemoryLauncher.launches[0].binary).toBe('node');
      expect(inMemoryLauncher.launches[0].scriptPath).toBe('security/secure_node_executor.cjs');
    });

    it('run_powershell tool delegates to runPowershell and returns string output', async () => {
      inMemoryLauncher.setResult({
        success: true,
        output: 'ps-result',
      });

      const output = await run_powershell.execute!({ command: 'Get-Process' }, {} as any);
      expect(output).toBe('ps-result');
    });
  });
});
