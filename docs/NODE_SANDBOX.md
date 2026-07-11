# Node.js Secure Sandbox

> **One-line summary:** AI agents can now run JavaScript code in a hardened V8
> isolate — same security posture as the existing Python sandbox, but for JS.

---

## Why we added it

The platform already had a Python AST sandbox (`security/secure_executor.py`)
that lets AI agents run validated Python code for engineering calculations.
However, several workflows naturally produce JavaScript/TypeScript code:

- **JSON transformation** — agents transforming large API responses
- **String manipulation** — agents processing documentation/indexed content
- **Math calculations** — agents doing quick numeric work that's simpler in JS
- **Browser-side validation** — agents writing client-side checks before
  injecting them into the React UI

Before this PR, agents had to round-trip JS code through Python (via
`json.dumps` + `eval` patterns), which is awkward and loses type fidelity.
The Node sandbox lets agents execute JS natively.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Mastra AI Agent (TypeScript runtime)                            │
│                                                                  │
│  src/mastra/tools/node-tool.ts                                   │
│    ↓ spawns via spawnSecure('node', ...)                         │
│    ↓ (hardened PATH, env scrub, stdin-only input, timeout)       │
└────────────────────────────┬─────────────────────────────────────┘
                             │ stdin: JS source code
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  security/secure_node_executor.cjs  (separate Node process)      │
│                                                                  │
│  1. Read code from stdin                                         │
│  2. Pre-execution validation (regex-based forbidden patterns)    │
│  3. Create isolated-vm Isolate (separate V8 heap)                │
│  4. Inject vetted globals (Math, JSON, Array, console)           │
│  5. Run code with timeout + memory limit                         │
│  6. Capture stdout, return JSON result                           │
└──────────────────────────────────────────────────────────────────┘
```

---

## Security model

### Defense in depth (3 layers)

| Layer | What it does | Where |
|:---|:---|:---|
| **1. Pre-execution validation** | Regex-based block of `require`, `import`, `process`, `eval`, `new Function`, Node built-in module names | `secure_node_executor.cjs:validateCode()` |
| **2. V8 isolate** | Separate V8 heap with its own builtins, no access to host `process` / `require` / `global` | `isolated-vm` library |
| **3. Vetted globals only** | Sandbox sees only Math, JSON, Array, Object, String, Number, Date, RegExp, Map, Set, Promise, console — nothing else | `ALLOWED_GLOBALS` constant |

### Why `isolated-vm` (not `node:vm` or `vm2`)?

| Option | Status | Why |
|:---|:---|:---|
| `node:vm` | ❌ Not a security mechanism | [Node.js docs](https://nodejs.org/api/vm.html) explicitly warn: "Do not use it to run untrusted code." Same V8 isolate as host — trivial to escape via Prototype Pollution, Promise tricks, or Error stack walking. |
| `vm2` | ❌ Deprecated | 12 known sandbox-escape vulnerabilities (CVSS up to 10.0). Maintainer abandoned the project in 2024. |
| **`isolated-vm`** | ✅ Recommended | Native V8 isolates with separate heaps. Sandbox escape requires a V8 kernel bug (much harder than vm/vm2 escapes). Actively maintained. |
| Riza | Alternative | Modern WASM-based option. Worth evaluating in the future, but `isolated-vm` has broader adoption. |

### Resource limits

| Resource | Default | Env var |
|:---|:---|:---|
| CPU timeout | 5000ms | `NODE_TIMEOUT_MS` |
| Memory limit | 64MB | `NODE_MEMORY_LIMIT_MB` |
| Max code length | 50,000 chars | `NODE_MAX_CODE_LENGTH` |
| Max output length | 10,000 chars | `NODE_MAX_OUTPUT_LENGTH` |

The timeout and memory limit are enforced at the **V8 isolate level** —
infinite loops and memory bombs are terminated by V8 itself, not by
the host process polling.

---

## What's allowed in the sandbox

| Available | Notes |
|:---|:---|
| `Math` | All Math methods (`Math.max`, `Math.floor`, `Math.PI`, etc.) |
| `JSON` | `JSON.parse`, `JSON.stringify` |
| `Array`, `Object`, `String`, `Number`, `Boolean` | All standard methods |
| `Date`, `RegExp` | Construction + methods |
| `Error`, `Map`, `Set`, `WeakMap`, `WeakSet` | Standard collections |
| `Promise`, `Symbol` | Async + symbols |
| `parseInt`, `parseFloat`, `isNaN`, `isFinite` | Numeric helpers |
| `console.log`, `console.error`, `console.warn`, `console.info` | Output channels (captured) |

### What's NOT allowed

| Blocked | Reason |
|:---|:---|
| `require()` | Module loading → file system access |
| `import` / `import()` | ESM module loading → file system access |
| `process` | Host env, exit, argv → escape vector |
| `globalThis` / `global` | Host globals → escape vector |
| `eval`, `new Function()` | Dynamic code execution → escape vector |
| `__dirname`, `__filename` | File system paths → escape vector |
| `child_process`, `fs`, `net`, `http`, `https`, `os`, `dns` | Node built-in modules → I/O |
| `setTimeout`, `setInterval` | Timer access → resource exhaustion / escape |
| `Buffer` | Binary I/O → escape vector |
| `fetch`, `XMLHttpRequest`, `WebSocket` | Network I/O |
| `crypto` | Host crypto → escape vector |

---

## Usage examples

### From an AI agent (via Mastra tool)

```typescript
// In an agent's tool call:
const result = await run_node.execute({
  code: `
    const data = JSON.parse('${jsonString}');
    const sum = data.values.reduce((a, b) => a + b, 0);
    console.log(JSON.stringify({ sum, count: data.values.length }));
  `,
});
```

### From CLI (manual testing)

```bash
# Simple math
echo 'console.log(1 + 2)' | node security/secure_node_executor.cjs

# JSON transformation
echo '
  const input = {"items": [1, 2, 3, 4, 5]};
  const output = {
    total: input.items.reduce((a, b) => a + b, 0),
    average: input.items.reduce((a, b) => a + b, 0) / input.items.length
  };
  console.log(JSON.stringify(output, null, 2));
' | node security/secure_node_executor.cjs

# Will be blocked:
echo "require('fs').readFileSync('/etc/passwd')" | node security/secure_node_executor.cjs
# → {"success":false,"error":"Security Violation: require() is not allowed..."}
```

---

## Comparison with Python sandbox

| Aspect | Python sandbox | Node sandbox |
|:---|:---|:---|
| File | `security/secure_executor.py` | `security/secure_node_executor.cjs` |
| Mastra tool | `src/mastra/tools/python-tool.ts` | `src/mastra/tools/node-tool.ts` |
| Validation | AST-based (Python `ast` module) | Regex-based (defense in depth) |
| Isolation | Restricted builtins + allowed modules | `isolated-vm` V8 isolate |
| Timeout | 30s | 5s |
| Memory | Process-level | 64MB V8 isolate limit |
| Allowed modules | `numpy`, `scipy`, `math`, `json`, `time`, `core_model`, `engine`, `load_flow`, etc. | None (pure JS builtins only) |

The Python sandbox allows domain-specific modules (engineering calculation
engines). The Node sandbox is **pure-JS only** — no domain modules — because
all engineering calculations live in Python.

---

## Installation

### Local development

`isolated-vm` is NOT in `package.json` dependencies because it's a native
module (C++ binding to V8) and requires build tools that may not be
available on all environments (CI runners, HF Spaces, etc.). The sandbox
degrades gracefully — if `isolated-vm` is missing, it returns a clear
error message instead of crashing:

```json
{
  "success": false,
  "error": "isolated-vm not installed. Run: npm install isolated-vm...",
  "error_type": "dependency_missing"
}
```

To enable the Node sandbox locally:

```bash
# Install build tools (Linux)
sudo apt-get install -y build-essential python3

# Install isolated-vm
npm install isolated-vm
```

### Compatibility

| isolated-vm version | Node.js version | Status |
|:---:|:---:|:---|
| 5.0.x | Node 18, 20 | ✅ works on CI (Node 20) |
| 6.x | Node 22+ | ✅ |
| 7.0.x | Node 22+ | ✅ works locally (Node 22/24); ❌ fails on Node 20 (CI) |

If you're on Node 22+, use `isolated-vm@7.0.0`. If you're on Node 18-20,
use `isolated-vm@5.0.1`.

### HF Space deployment

The HF Space runs Python-only FastAPI. The Node sandbox is **not needed**
on HF Space — it's only used by Mastra agents in the dev environment.

### Dev container

The `.devcontainer/devcontainer.json` installs Node 22 LTS. To enable
the Node sandbox inside the dev container:

```bash
npm install isolated-vm@7.0.0
```

This requires `build-essential` and `python3` (for `node-gyp`), both
already installed in the devcontainer.

---

## Testing

```bash
# Run all Node sandbox tests
pytest tests/test_node_sandbox.py -v

# Run only validation tests (no isolated-vm required)
pytest tests/test_node_sandbox.py::TestCodeValidation -v

# Run execution tests (requires isolated-vm)
pytest tests/test_node_sandbox.py::TestSandboxExecution -v

# Run escape-attempt tests
pytest tests/test_node_sandbox.py::TestSandboxEscapes -v
```

Tests are auto-skipped if `node` is not on PATH or `isolated-vm` is not
installed — they don't block CI on environments where Node sandboxing
isn't available.

---

## Operational notes

### Audit logging

The Node sandbox does NOT currently log to the same audit log as the Python
sandbox (`security/security_framework.py:get_audit_logger()`). This is a
known gap tracked as a follow-up. For now, the spawn helper
(`_spawn-helpers.ts:spawnSecure`) is the only audit trail (via the Mastra
tool's `execute()` log).

### Performance

| Metric | Value |
|:---|:---|
| Cold start (V8 isolate creation) | ~50-80ms |
| Warm execution (after isolate ready) | ~5-10ms per KB of code |
| Memory overhead per isolate | ~8MB baseline + sandbox usage |

For comparison, the Python sandbox cold-start is ~300-400ms (Python
interpreter + module imports). The Node sandbox is ~5x faster to start.

### Limitations

| Limitation | Workaround |
|:---|:---|
| No `async/await` at top level | Wrap in `(async () => { ... })()` |
| No `setTimeout` / `setInterval` | Use `Promise` + manual timeout |
| No `fetch` / network | Pre-fetch data in the agent, pass as input |
| No file I/O | Pre-load files in the agent, pass as input |
| No `Buffer` | Use `String` + `JSON.parse` for binary-as-text |

---

## Future enhancements

1. **Audit logging integration** — wire `secure_node_executor.cjs` to the
   Python audit logger via a small HTTP bridge or shared log file.
2. **TypeScript support** — currently JS only. Could add `ts-node` or
   `swc` for TS transpilation before sandbox execution.
3. **Module whitelist** — allow specific vetted modules (e.g. a
   `etap-math` module with engineering functions) to be `import`-ed.
4. **Snapshot + restore** — `isolated-vm` supports snapshotting a warm
   isolate to disk for ~10x faster cold starts.
5. **WebAssembly modules** — `isolated-vm` supports `WASM` compilation
   in the sandbox. Could enable agents to run pre-compiled WASM modules
   for performance-critical paths.

---

## References

- [Node.js `vm` module warning](https://nodejs.org/api/vm.html#vm-executing-javascript)
- [`isolated-vm` documentation](https://github.com/laverdet/isolated-vm)
- [`vm2` deprecation notice](https://github.com/patriksimek/vm2#status)
- [Python sandbox reference](../../security/secure_executor.py)
- [Mastra tool wrapper](../../src/mastra/tools/node-tool.ts)
- [Spawn helper](../../src/mastra/tools/_spawn-helpers.ts)
