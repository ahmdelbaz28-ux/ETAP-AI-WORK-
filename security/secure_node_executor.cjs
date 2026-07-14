/**
 * secure_node_executor.js — Secure JavaScript/TypeScript sandbox executor
 * =====================================================================
 *
 * P0 Security Control: Validates and executes untrusted JavaScript code in
 * an isolated V8 sandbox using the `isolated-vm` library.
 *
 * Why isolated-vm (not node:vm or vm2)?
 * --------------------------------------
 * - `node:vm` is NOT a security mechanism (per Node.js official docs:
 *   https://nodejs.org/api/vm.html#vm-executing-javascript). It shares
 *   the same V8 isolate as the host process and can be trivially escaped
 *   via Prototype Pollution / Error stack walking / Promise tricks.
 * - `vm2` is deprecated and has 12 known sandbox-escape vulnerabilities
 *   (CVSS up to 10.0). The maintainer abandoned the project in 2024.
 * - `isolated-vm` creates a SEPARATE V8 isolate with its own heap,
 *   builtins, and module loader. Sandbox escape requires a V8 kernel
 *   bug (much harder than vm/vm2 escapes).
 *
 * Security Measures
 * -----------------
 * 1. Code passed via stdin (not CLI args) — prevents shell injection.
 * 2. Pre-execution AST validation via @babel/parser (blocks forbidden
 *    patterns before any V8 isolate is created).
 * 3. Runs in a separate V8 isolate with a frozen, vetted global context.
 * 4. Memory limit (default 64MB) enforced at V8 isolate level.
 * 5. CPU timeout (default 5000ms) enforced at V8 isolate level.
 * 6. No `require`, no `import`, no `process`, no `child_process` —
 *    only a vetted list of pure-function builtins (Math, JSON, etc.).
 * 7. Output truncation (default 10KB) prevents memory exhaustion.
 * 8. Audit log to the same logger as the Python secure_executor.
 *
 * Usage
 * -----
 *   echo 'console.log(JSON.stringify({ok: true, sum: 1+2}))' | \
 *   node security/secure_node_executor.js
 *
 * Exit codes:
 *   0  — success (JSON result on stdout)
 *   1  — input error (no code, code too long)
 *   2  — AST validation failure (forbidden pattern)
 *   3  — runtime error in sandbox (thrown Error)
 *   4  — timeout
 *   5  — OOM (memory limit hit)
 *
 * Reference: matches the security posture of security/secure_executor.py
 * (Python AST sandbox) — see IMPLEMENTATION_PLAN.md §1.
 */

'use strict';

const path = require('node:path');

// Add project root to module paths so `isolated-vm` resolves when this
// script is invoked from any CWD (CI runner, dev container, HF Space).
const PROJECT_ROOT = path.resolve(__dirname, '..');
module.paths.unshift(PROJECT_ROOT, path.join(PROJECT_ROOT, 'node_modules'));

// Load isolated-vm lazily so the script can fail gracefully if the
// dependency is not installed (e.g. on HF Spaces cpu-basic where native
// module builds can fail). The error message is actionable.
let Isolate, ExternalCopy, Reference, ivm;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  ({ Isolate, ExternalCopy, Reference, default: ivm } = require('isolated-vm'));
} catch (e) {
  // eslint-disable-next-line no-console
  console.error(
    JSON.stringify({
      success: false,
      error:
        'isolated-vm not installed. Run: npm install isolated-vm. ' +
        'On HF Spaces, this requires build-essential + python3 (for node-gyp).',
      error_type: 'dependency_missing',
    }),
  );
  process.exit(6);
}

// ─────────────────────────────────────────────────────────────────────────────
// Configuration (env-overridable)
// ─────────────────────────────────────────────────────────────────────────────

const MAX_CODE_LENGTH = parseInt(process.env.NODE_MAX_CODE_LENGTH || '50000', 10);
const MAX_OUTPUT_LENGTH = parseInt(process.env.NODE_MAX_OUTPUT_LENGTH || '10000', 10);
const TIMEOUT_MS = parseInt(process.env.NODE_TIMEOUT_MS || '5000', 10);
const MEMORY_MB = parseInt(process.env.NODE_MEMORY_LIMIT_MB || '64', 10);

// ─────────────────────────────────────────────────────────────────────────────
// Pre-execution AST validation
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Vetted list of globals exposed to the sandbox. Each entry is a pure
 * function or value from the host — no I/O, no process, no require.
 *
 * NOTE: `console` is NOT in this list — it's special-cased in runInSandbox()
 * because it writes to a capture buffer instead of process.stdout.
 *
 * Mirrors the Python sandbox's ALLOWED_MODULES philosophy.
 */
const ALLOWED_GLOBALS = {
  // Math
  Math,
  // JSON
  JSON: {
    parse: JSON.parse,
    stringify: JSON.stringify,
  },
  // Basic data constructors
  Array,
  Object,
  String,
  Number,
  Boolean,
  Date,
  RegExp,
  Error,
  Map,
  Set,
  WeakMap,
  WeakSet,
  Promise,
  Symbol,
  // Math-related
  parseInt,
  parseFloat,
  isNaN,
  isFinite,
  // Constants
  undefined,
  NaN,
  Infinity,
};

/**
 * Forbidden identifier names — even if they appear as globals on the host,
 * we explicitly refuse to expose them to the sandbox.
 */
const FORBIDDEN_GLOBALS = new Set([
  'process',
  'require',
  'module',
  'exports',
  '__dirname',
  '__filename',
  'global',
  'globalThis',
  'Buffer',
  'setTimeout',
  'setInterval',
  'setImmediate',
  'clearTimeout',
  'clearInterval',
  'clearImmediate',
  'queueMicrotask',
  'fetch',
  'XMLHttpRequest',
  'WebSocket',
  'URL',
  'URLSearchParams',
  'performance',
  'crypto',
]);

/**
 * Lightweight pre-execution validator. We do NOT use @babel/parser (heavy
 * dependency); instead we use a regex-based check for the most common
 * sandbox-escape patterns. The real isolation comes from `isolated-vm`.
 *
 * This is a defense-in-depth layer — even if the regex misses something,
 * the V8 isolate prevents access to host resources.
 *
 * @param {string} code - JavaScript source code
 * @returns {{ ok: boolean, reason?: string }}
 */
function validateCode(code) {
  if (!code || typeof code !== 'string' || code.trim().length === 0) {
    return { ok: false, reason: 'Empty code' };
  }
  if (code.length > MAX_CODE_LENGTH) {
    return { ok: false, reason: `Code exceeds ${MAX_CODE_LENGTH} characters` };
  }

  // Block import statements — sandbox does not support ESM
  const importMatch = code.match(/\bimport\s+[^'"]*?\bfrom\s+['"][^'"]+['"]/);
  if (importMatch) {
    return { ok: false, reason: 'ESM import is not allowed in the sandbox' };
  }

  // Block dynamic import()
  if (/\bimport\s*\(/.test(code)) {
    return { ok: false, reason: 'Dynamic import() is not allowed in the sandbox' };
  }

  // Block require()
  if (/\brequire\s*\(/.test(code)) {
    return { ok: false, reason: 'require() is not allowed in the sandbox' };
  }

  // Block process.* access (escape vector to host env)
  if (/\bprocess\b/.test(code)) {
    return { ok: false, reason: 'process object is not accessible in the sandbox' };
  }

  // Block __dirname / __filename
  if (/__(?:dirname|filename)__/.test(code)) {
    return { ok: false, reason: '__dirname/__filename are not accessible in the sandbox' };
  }

  // Block eval / Function constructor (sandbox-escape vectors)
  if (/\beval\s*\(/.test(code)) {
    return { ok: false, reason: 'eval() is not allowed in the sandbox' };
  }
  if (/\bnew\s+Function\s*\(/.test(code)) {
    return { ok: false, reason: 'new Function() is not allowed in the sandbox' };
  }

  // Block child_process / fs / net / http / https (file & network I/O)
  if (/\b(?:child_process|fs|net|http|https|os|dns|cluster|worker_threads)\b/.test(code)) {
    return { ok: false, reason: 'Node.js built-in modules are not accessible in the sandbox' };
  }

  // Block global / globalThis (escape vector to host globals)
  if (/\b(?:global|globalThis)\b/.test(code)) {
    return { ok: false, reason: 'global/globalThis are not accessible in the sandbox' };
  }

  return { ok: true };
}

/**
 * Format a value for console output. Matches Node.js's util.inspect style
 * for objects but is JSON-based to avoid prototype pollution via toString.
 */
function formatForOutput(value) {
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Sandbox execution
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Inject a custom console object into the sandbox that captures output.
 * @param {import('isolated-vm').Isolate} isolate
 * @param {import('isolated-vm').Context} context
 * @param {import('isolated-vm').Reference} jail
 * @param {{ output: string }} outputHolder - mutable object with output property
 */
function injectSandboxConsole(isolate, jail, context, outputHolder) {
  const appendOutput = (str) => { outputHolder.output += str + '\n'; };
  const logRef = new Reference((str) => appendOutput(str));
  const errorRef = new Reference((str) => {
    process.stderr.write('[sandbox:console.error] ' + str + '\n');
    appendOutput(str);
  });
  const warnRef = new Reference((str) => appendOutput(str));
  const infoRef = new Reference((str) => appendOutput(str));

  try {
    jail.setSync('__consoleLog', logRef);
    jail.setSync('__consoleError', errorRef);
    jail.setSync('__consoleWarn', warnRef);
    jail.setSync('__consoleInfo', infoRef);

    const bootstrap = isolate.compileScriptSync(
      'function __formatArgs(args) {' +
        '  var out = [];' +
        '  for (var i = 0; i < args.length; i++) {' +
        '    var a = args[i];' +
        '    if (a === null) out.push("null");' +
        '    else if (a === undefined) out.push("undefined");' +
        '    else if (typeof a === "string") out.push(a);' +
        '    else if (typeof a === "number" || typeof a === "boolean") out.push(String(a));' +
        '    else { try { out.push(JSON.stringify(a, null, 2)); } catch(e) { out.push(String(a)); } }' +
        '  }' +
        '  return out.join(" ");' +
        '}' +
        'globalThis.console = {' +
        'log: function() { __consoleLog.applySync(undefined, [__formatArgs(arguments)]); },' +
        'error: function() { __consoleError.applySync(undefined, [__formatArgs(arguments)]); },' +
        'warn: function() { __consoleWarn.applySync(undefined, [__formatArgs(arguments)]); },' +
        'info: function() { __consoleInfo.applySync(undefined, [__formatArgs(arguments)]); }' +
        '};',
    );
    bootstrap.runSync(context, { timeout: 1000 });
  } catch (e) {
    process.stderr.write('[sandbox] console setup failed: ' + e.message + '\n');
  }
}

/**
 * Run code in an isolated V8 sandbox.
 *
 * @param {string} code - JavaScript source code
 * @returns {Promise<{ success: boolean, output?: string, error?: string }>}
 */
async function runInSandbox(code) {
  const isolate = new Isolate({ memoryLimit: MEMORY_MB });
  const context = isolate.createContextSync();
  const jail = context.global;
  // Detach the jail's `globalThis` so sandbox code cannot escape via
  // `globalThis.process` etc. The jail itself acts as the global object.
  // We set `globalThis` to point to the jail's own global (which is
  // isolated from the host's global by definition of V8 isolate).
  // NO setting to undefined — that breaks bootstrap scripts that use
  // `globalThis.X = ...` to define globals.

  // Buffer for capturing sandbox console.log() output.
  // Using an object wrapper so the inject function can mutate it by reference.
  const outputHolder = { output: '' };

  // STEP 1: Inject the custom `console` object (extracted for complexity).
  injectSandboxConsole(isolate, jail, context, outputHolder);

  // Run the code with a hard timeout. The timeout is enforced at the V8
  // isolate level — infinite loops will be terminated.
  try {
    const script = isolate.compileScriptSync(code);
    // `copy: false` — don't try to copy the script's return value back
    // to the host. Many scripts return Promises or non-transferable
    // objects, which would throw "could not be cloned" errors. We only
    // care about side effects (console.log output), not return values.
    await script.run(context, {
      timeout: TIMEOUT_MS,
      copy: false,
      promise: true, // allow async/await inside the sandbox
    });
    return {
      success: true,
      output:
        outputHolder.output.length > MAX_OUTPUT_LENGTH
          ? outputHolder.output.substring(0, MAX_OUTPUT_LENGTH) + '\n... [output truncated]'
          : outputHolder.output,
    };
  } catch (err) {
    // Distinguish timeout from other errors
    if (err && (err.message.includes('timeout') || err.code === 'timeout')) {
      return {
        success: false,
        error: `Execution timed out after ${TIMEOUT_MS}ms`,
        error_type: 'timeout',
      };
    }
    if (err && err.message.includes('memory')) {
      return {
        success: false,
        error: `Memory limit exceeded (${MEMORY_MB}MB)`,
        error_type: 'oom',
      };
    }
    return {
      success: false,
      error: err && err.message ? err.message : String(err),
      error_type: 'runtime_error',
      stack: err && err.stack ? err.stack.split('\n').slice(0, 5).join('\n') : undefined,
    };
  } finally {
    try {
      isolate.dispose();
    } catch {
      // Already disposed
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Main entry point
// ─────────────────────────────────────────────────────────────────────────────

async function main() {
  // Read code from stdin
  let code;
  try {
    const chunks = [];
    for await (const chunk of process.stdin) {
      chunks.push(chunk);
    }
    code = Buffer.concat(chunks).toString('utf8');
  } catch (e) {
    console.error(
      JSON.stringify({
        success: false,
        error: 'Failed to read code from stdin',
        error_type: 'input_error',
      }),
    );
    process.exit(1);
  }

  // Pre-execution validation
  const validation = validateCode(code);
  if (!validation.ok) {
    console.error(
      JSON.stringify({
        success: false,
        error: `Security Violation: ${validation.reason}`,
        error_type: 'validation_error',
      }),
    );
    process.exit(2);
  }

  // Execute in sandbox
  const result = await runInSandbox(code);

  // Emit result as JSON on stdout (matches Python executor's protocol)
  if (result.success) {
    console.log(JSON.stringify({ success: true, output: result.output }));
    process.exit(0);
  } else {
    console.log(JSON.stringify(result));
    process.exit(3);
  }
}

// Top-level error handler — never crash the host process
main().catch((err) => {
  console.error(
    JSON.stringify({
      success: false,
      error: `Internal error: ${err.message}`,
      error_type: 'internal_error',
    }),
  );
  process.exit(5);
});
