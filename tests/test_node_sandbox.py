"""
test_node_sandbox.py — Tests for the Node.js secure sandbox executor.

Covers three layers:
1. Pre-execution AST validation (forbidden patterns blocked before V8 isolate).
2. Sandbox execution (code runs, captures stdout, returns JSON).
3. Sandbox escape attempts (require, process, import — all blocked).

These tests do NOT require isolated-vm to be installed — they verify the
validation logic (which is the first line of defense). Tests that need
the actual V8 isolate are marked with @pytest.mark.skipif when isolated-vm
is unavailable.

Run:
    pytest tests/test_node_sandbox.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = Path(__file__).resolve().parent.parent
EXECUTOR_PATH = REPO_ROOT / "security" / "secure_node_executor.js"

# Skip all tests if `node` is not on PATH — the sandbox cannot run without it.
NODE_AVAILABLE = shutil.which("node") is not None


pytestmark = pytest.mark.skipif(
    not NODE_AVAILABLE,
    reason="Node.js not installed — skipping Node sandbox tests",
)


# ---------------------------------------------------------------------------
# Helper: run code in the sandbox
# ---------------------------------------------------------------------------


def run_sandbox(code: str, timeout: int = 10) -> dict:
    """Run JavaScript code in the Node sandbox executor.

    Returns the parsed JSON result dict from the executor.
    The executor writes a single JSON line to stdout on completion.
    """
    env = os.environ.copy()
    # Match the env scrubbing done by _spawn-helpers.ts in production
    env["NODE_TIMEOUT_MS"] = "3000"
    env["NODE_MEMORY_LIMIT_MB"] = "32"

    proc = subprocess.run(
        ["node", str(EXECUTOR_PATH)],
        input=code,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=str(REPO_ROOT),
    )

    # The executor writes JSON to stdout on success and stderr on early failures
    if proc.stdout.strip():
        try:
            return json.loads(proc.stdout.strip().splitlines()[-1])
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": f"Non-JSON output: {proc.stdout[:200]}",
                "error_type": "parse_error",
                "returncode": proc.returncode,
            }
    if proc.stderr.strip():
        try:
            return json.loads(proc.stderr.strip().splitlines()[-1])
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": proc.stderr[:500],
                "error_type": "stderr",
                "returncode": proc.returncode,
            }
    return {
        "success": False,
        "error": f"Empty output (exit {proc.returncode})",
        "error_type": "empty",
    }


# ---------------------------------------------------------------------------
# Layer 1: Pre-execution validation (no isolated-vm required)
# ---------------------------------------------------------------------------


class TestCodeValidation:
    """Forbidden code patterns are blocked before any V8 isolate is created."""

    def test_empty_code_rejected(self) -> None:
        result = run_sandbox("")
        assert result["success"] is False
        assert "Empty code" in result["error"] or "validation" in result.get("error_type", "")

    def test_whitespace_only_code_rejected(self) -> None:
        result = run_sandbox("   \n\t  \n")
        assert result["success"] is False

    def test_require_call_blocked(self) -> None:
        result = run_sandbox("const fs = require('fs'); fs.readFileSync('/etc/passwd');")
        assert result["success"] is False
        assert (
            "require" in result["error"].lower()
            or "validation" in result.get("error_type", "").lower()
        )

    def test_esm_import_blocked(self) -> None:
        result = run_sandbox("import fs from 'fs'; fs.readFileSync('/etc/passwd');")
        assert result["success"] is False

    def test_dynamic_import_blocked(self) -> None:
        result = run_sandbox("const fs = await import('fs');")
        assert result["success"] is False

    def test_process_access_blocked(self) -> None:
        result = run_sandbox("console.log(process.env)")
        assert result["success"] is False
        assert (
            "process" in result["error"].lower()
            or "validation" in result.get("error_type", "").lower()
        )

    def test_eval_blocked(self) -> None:
        result = run_sandbox("eval('console.log(1)')")
        assert result["success"] is False

    def test_function_constructor_blocked(self) -> None:
        result = run_sandbox("const f = new Function('return 1'); f();")
        assert result["success"] is False

    def test_global_access_blocked(self) -> None:
        result = run_sandbox("globalThis.process.exit(0)")
        assert result["success"] is False

    def test_dunder_dirname_blocked(self) -> None:
        result = run_sandbox("console.log(__dirname)")
        assert result["success"] is False

    def test_node_builtins_blocked(self) -> None:
        """fs, child_process, net, http — all blocked by name."""
        for module in ["fs", "child_process", "net", "http", "https", "os"]:
            result = run_sandbox(f"const x = require('{module}');")
            assert result["success"] is False, f"{module} should be blocked"

    def test_oversized_code_rejected(self) -> None:
        """Code longer than NODE_MAX_CODE_LENGTH is rejected."""
        env_backup = os.environ.get("NODE_MAX_CODE_LENGTH")
        os.environ["NODE_MAX_CODE_LENGTH"] = "100"
        try:
            long_code = "console.log(1);\n" * 20  # ~280 chars, > 100 limit
            result = run_sandbox(long_code)
            assert result["success"] is False
            assert "exceeds" in result["error"].lower() or "length" in result["error"].lower()
        finally:
            if env_backup is None:
                os.environ.pop("NODE_MAX_CODE_LENGTH", None)
            else:
                os.environ["NODE_MAX_CODE_LENGTH"] = env_backup


# ---------------------------------------------------------------------------
# Layer 2: Sandbox execution (requires isolated-vm)
# ---------------------------------------------------------------------------


# Detect whether isolated-vm is installed by checking if a simple script runs.
# If isolated-vm is missing, the executor exits with code 6 and a clear error.
def _isolated_vm_available() -> bool:
    """Check if isolated-vm is installed by running a no-op script."""
    result = run_sandbox("1+1")
    if result.get("error_type") == "dependency_missing":
        return False
    # If validation passed but execution succeeded or failed at runtime,
    # isolated-vm is installed.
    return result.get("error_type") != "dependency_missing"


ISOLATED_VM_AVAILABLE = _isolated_vm_available()


@pytest.mark.skipif(
    not ISOLATED_VM_AVAILABLE,
    reason="isolated-vm not installed — skipping execution tests",
)
class TestSandboxExecution:
    """Basic JavaScript execution works in the sandbox."""

    def test_simple_arithmetic(self) -> None:
        result = run_sandbox("console.log(1 + 2)")
        assert result["success"] is True
        assert "3" in result["output"]

    def test_console_log_string(self) -> None:
        result = run_sandbox("console.log('hello world')")
        assert result["success"] is True
        assert "hello world" in result["output"]

    def test_json_parse_and_stringify(self) -> None:
        code = """
        const obj = JSON.parse('{"name": "test", "value": 42}');
        console.log(JSON.stringify(obj));
        """
        result = run_sandbox(code)
        assert result["success"] is True
        assert '"name": "test"' in result["output"]
        assert '"value": 42' in result["output"]

    def test_array_operations(self) -> None:
        code = """
        const arr = [1, 2, 3, 4, 5];
        console.log(arr.map(x => x * 2).reduce((a, b) => a + b, 0));
        """
        result = run_sandbox(code)
        assert result["success"] is True
        assert "30" in result["output"]  # (2+4+6+8+10) = 30

    def test_math_functions(self) -> None:
        code = """
        console.log(Math.max(1, 2, 3));
        console.log(Math.floor(3.7));
        console.log(Math.PI.toFixed(2));
        """
        result = run_sandbox(code)
        assert result["success"] is True
        output = result["output"]
        assert "3" in output  # Math.max(1,2,3)
        assert "3" in output  # Math.floor(3.7)
        assert "3.14" in output  # Math.PI.toFixed(2)

    def test_string_manipulation(self) -> None:
        code = """
        const s = 'Hello, World!';
        console.log(s.toUpperCase());
        console.log(s.split(', ').length);
        console.log(s.replace('World', 'Sandbox'));
        """
        result = run_sandbox(code)
        assert result["success"] is True
        assert "HELLO, WORLD!" in result["output"]
        assert "2" in result["output"]
        assert "Hello, Sandbox!" in result["output"]

    def test_promise_await(self) -> None:
        """Async code (Promise) is supported."""
        code = """
        Promise.resolve(42).then(v => console.log(v));
        """
        result = run_sandbox(code)
        assert result["success"] is True
        assert "42" in result["output"]

    def test_output_truncation(self) -> None:
        """Outputs longer than NODE_MAX_OUTPUT_LENGTH are truncated."""
        env_backup = os.environ.get("NODE_MAX_OUTPUT_LENGTH")
        os.environ["NODE_MAX_OUTPUT_LENGTH"] = "50"
        try:
            code = "console.log('x'.repeat(200));"
            result = run_sandbox(code)
            assert result["success"] is True
            assert "truncated" in result["output"].lower()
        finally:
            if env_backup is None:
                os.environ.pop("NODE_MAX_OUTPUT_LENGTH", None)
            else:
                os.environ["NODE_MAX_OUTPUT_LENGTH"] = env_backup


# ---------------------------------------------------------------------------
# Layer 3: Sandbox escape attempts (defense in depth)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not ISOLATED_VM_AVAILABLE,
    reason="isolated-vm not installed — skipping escape-attempt tests",
)
class TestSandboxEscapes:
    """Common sandbox-escape vectors are blocked at validation layer."""

    def test_require_fs_blocked(self) -> None:
        result = run_sandbox("require('fs').readFileSync('/etc/passwd')")
        assert result["success"] is False

    def test_require_child_process_blocked(self) -> None:
        result = run_sandbox("require('child_process').execSync('whoami')")
        assert result["success"] is False

    def test_process_env_access_blocked(self) -> None:
        result = run_sandbox("console.log(process.env.HOME)")
        assert result["success"] is False

    def test_process_exit_blocked(self) -> None:
        result = run_sandbox("process.exit(0)")
        assert result["success"] is False

    def test_global_this_process_blocked(self) -> None:
        result = run_sandbox("globalThis.process.exit(0)")
        assert result["success"] is False

    def test_eval_blocked(self) -> None:
        result = run_sandbox("eval('1+1')")
        assert result["success"] is False

    def test_function_constructor_blocked(self) -> None:
        result = run_sandbox("new Function('return process')()()")
        assert result["success"] is False

    def test_infinite_loop_times_out(self) -> None:
        """Infinite loops are terminated by the V8 isolate timeout."""
        result = run_sandbox("while(true) {}")
        # Either validation blocks it, or it runs and times out
        assert result["success"] is False
        # Should NOT hang — subprocess timeout in run_sandbox handles edge case

    def test_memory_bomb_throws(self) -> None:
        """Memory exhaustion is caught by the V8 isolate memory limit."""
        code = """
        let arr = [];
        while(true) { arr.push(new Array(1000000)); }
        """
        result = run_sandbox(code, timeout=15)
        assert result["success"] is False
        # Should be OOM or timeout, not success


# ---------------------------------------------------------------------------
# Layer 4: Error reporting
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not ISOLATED_VM_AVAILABLE,
    reason="isolated-vm not installed — skipping error-reporting tests",
)
class TestErrorReporting:
    """Runtime errors in sandbox code are reported clearly."""

    def test_undefined_variable_throws(self) -> None:
        result = run_sandbox("console.log(undefinedVar)")
        assert result["success"] is False
        assert "defined" in result["error"].lower() or "reference" in result["error"].lower()

    def test_syntax_error_throws(self) -> None:
        result = run_sandbox("const x = ;")
        assert result["success"] is False
        # Could be validation error or runtime SyntaxError
        assert (
            "syntax" in result["error"].lower()
            or "Unexpected" in result["error"]
            or "validation" in result.get("error_type", "")
        )

    def test_type_error_throws(self) -> None:
        result = run_sandbox("null.foo")
        assert result["success"] is False
        assert (
            "null" in result["error"].lower()
            or "type" in result["error"].lower()
            or "property" in result["error"].lower()
        )

    def test_thrown_error_message_captured(self) -> None:
        result = run_sandbox("throw new Error('custom error message')")
        assert result["success"] is False
        assert "custom error message" in result["error"] or "Error" in result["error"]
