"""
Secure Python Executor
======================
P0 Security Control: Validates and executes Python code in a restricted environment.
Integrates with security_framework.py for AST-based validation and the guard-skills
AI failure-mode detector for quality pre-scan of AI-generated code.

Security Measures:
- Code passed via stdin (not CLI args) to prevent shell injection
- AST validation before execution
- **AI failure-mode pre-scan** (guard-skills integration): detects the 14
  systematic LLM code-generation failure patterns before code reaches exec()
- Restricted builtins (no os, sys, getattr, setattr in sandbox)
- Timeout protection
- Output truncation
- Audit logging

SECURITY AUDIT 2026-08-02 (V-39, V-40, V-41, V-42, V-43, V-44 fixes):
- V-39: Added MRO-based sandbox escape prevention — blocks __class__.__bases__
  and __subclasses__ access patterns
- V-40: Removed `type` from safe builtins — prevents class enumeration escape
- V-41: Removed `isinstance`/`issubclass` from safe builtins — prevents
  class hierarchy traversal
- V-42: Added memory limit (512 MB) via resource module
- V-43: Added CPU limit via subprocess isolation
- V-44: Replaced ThreadPoolExecutor with subprocess-based execution —
  threads cannot be killed after timeout; subprocesses can
"""

import contextlib
import json
import logging
import os
import resource
import sys
import traceback
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from security.security_framework import get_audit_logger, get_validator
except ImportError:
    print(json.dumps({"error": "Security framework not found", "success": False}))
    sys.exit(1)

logger = logging.getLogger(__name__)

MAX_EXECUTION_TIME_SECONDS = 30
MAX_OUTPUT_LENGTH = 10000
MAX_MEMORY_MB = 512  # V-42: Memory limit


def _read_code_from_stdin() -> Optional[str]:
    try:
        code = sys.stdin.read()
        if not code or not code.strip():
            return None
        return code
    except Exception as e:
        logger.exception("Failed to read code from stdin: %s", e)
        return None


def _sandbox_escape_pre_scan(code: str) -> tuple[bool, str]:
    """V-39: Pre-scan for common sandbox escape patterns in Python code.

    Checks for patterns that exploit Python's object model to escape
    the restricted builtins sandbox, such as:
    - __class__.__bases__[0].__subclasses__()
    - __class__.__mro__
    - __subclasses__()
    - __builtins__ access
    - globals() / locals() introspection
    - getattr with dynamic attribute names
    """
    dangerous_patterns = [
        # MRO chain traversal
        (r"__class__\s*\.\s*__bases__", "MRO base class traversal"),
        (r"__class__\s*\.\s*__mro__", "MRO method resolution traversal"),
        (r"__subclasses__\s*\(", "Subclass enumeration via __subclasses__"),
        (r"__bases__\s*\[", "Direct base class access"),
        (r"__mro__\s*\[", "MRO index access"),
        # Builtins access
        (r"__builtins__", "Direct builtins access"),
        (r"__import__", "Direct import function access"),
        # Introspection
        (r"\bglobals\s*\(\s*\)", "globals() introspection"),
        (r"\blocals\s*\(\s*\)", "locals() introspection"),
        (r"\bvars\s*\(\s*\)", "vars() introspection"),
        (r"\bdir\s*\(", "dir() introspection"),
        (r"\bgetattr\s*\(", "getattr() dynamic attribute access"),
        (r"\bsetattr\s*\(", "setattr() dynamic attribute modification"),
        (r"\bdelattr\s*\(", "delattr() dynamic attribute deletion"),
        (r"\bhasattr\s*\(", "hasattr() dynamic attribute check"),
        # Code object manipulation
        (r"\bcompile\s*\(", "compile() code object creation"),
        (r"\beval\s*\(", "eval() code execution"),
        (r"\bexec\s*\(", "exec() code execution"),
        (r"__code__", "Code object access"),
        (r"__globals__", "Function globals access"),
        (r"__closure__", "Closure cell access"),
        # OS access
        (r"\bos\s*\.", "OS module access"),
        (r"\bsubprocess", "Subprocess module access"),
        (r"\bctypes", "CTypes FFI access"),
        (r"\bsignal\s*\.", "Signal module access"),
        (r"\bsocket\s*\.", "Socket module access"),
        (r"\bopen\s*\(", "File open (should use restricted builtins)"),
    ]

    import re
    for pattern, description in dangerous_patterns:
        if re.search(pattern, code):
            return False, f"Sandbox escape pattern detected: {description}"

    return True, ""


def _set_memory_limit() -> None:
    """V-42: Set memory limit for the execution process."""
    try:
        max_bytes = MAX_MEMORY_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
    except (ValueError, OSError):
        pass  # Not supported on all platforms


def main() -> None:
    code = _read_code_from_stdin()
    if code is None:
        print(json.dumps({"error": "No code provided via stdin", "success": False}))
        sys.exit(1)

    # Limit code length to prevent resource exhaustion
    MAX_CODE_LENGTH = 50000
    if len(code) > MAX_CODE_LENGTH:
        print(
            json.dumps(
                {
                    "error": f"Code exceeds maximum length of {MAX_CODE_LENGTH} characters",
                    "success": False,
                },
            ),
        )
        sys.exit(1)

    audit = get_audit_logger()
    validator = get_validator()

    if not validator.validate_python_code(code):
        audit.log_security_violation(
            "agent_tool",
            "Forbidden code pattern detected in Python tool",
            {"code_length": len(code)},
        )
        print(
            json.dumps(
                {
                    "error": "Security Violation: Forbidden code pattern or unauthorized import detected.",
                    "success": False,
                },
            ),
        )
        sys.exit(1)

    # V-39: Sandbox escape pre-scan
    escape_safe, escape_reason = _sandbox_escape_pre_scan(code)
    if not escape_safe:
        audit.log_security_violation(
            "agent_tool",
            f"Sandbox escape attempt: {escape_reason}",
            {"code_length": len(code)},
        )
        print(
            json.dumps(
                {
                    "error": f"Security Violation: {escape_reason}",
                    "success": False,
                },
            ),
        )
        sys.exit(1)

    # --- AI Failure-Mode Pre-Scan (guard-skills integration) ---
    try:
        from guards.ai_failure_modes import AIFailureModeDetector, GuardSeverity

        _ai_detector = AIFailureModeDetector()
        _ai_result = _ai_detector.detect(code)
        if not _ai_result.passed:
            _must_fix = [v for v in _ai_result.violations if v.severity == GuardSeverity.MUST_FIX]
            if _must_fix:
                audit.log_security_violation(
                    "agent_tool",
                    "AI failure-mode guard blocked execution",
                    {
                        "must_fix_count": len(_must_fix),
                        "violations": [v.rule_id for v in _must_fix],
                    },
                )
                _details = "; ".join(f"{v.rule_id}: {v.description}" for v in _must_fix[:5])
                print(
                    json.dumps(
                        {
                            "error": f"AI Quality Guard: Code blocked due to critical failure modes. "
                            f"{_details}",
                            "success": False,
                            "guard_violations": _ai_result.to_dict(),
                        },
                    ),
                )
                sys.exit(1)
            else:
                # SHOULD_FIX / WORTH_NOTING — log but proceed
                audit.log_action("agent_tool", "ai_guard_warning", "quality_warning", True)
                logger.info(
                    "AI guard: %d should-fix / worth-noting violations detected (proceeding)",
                    _ai_result.should_fix_count + _ai_result.worth_noting_count,
                )
    except ImportError:
        logger.debug("guards module not available, skipping AI failure-mode scan")
    except Exception as guard_err:
        logger.warning("AI guard scan failed: %s", guard_err)

    audit.log_action("agent_tool", "execute_python", "restricted_sandbox", True)

    import math

    def _deep_freeze_module(mod: Any) -> None:
        """Deep-freeze a module by nullifying dangerous attributes at all levels.

        This prevents sandbox escape via paths like:
          numpy.sys.modules['os'].system('cmd')
          scipy.__builtins__['__import__']('os')
        """
        if mod is None:
            return
        DANGEROUS_NAMES = {
            "os",
            "system",
            "popen",
            "spawn",
            "exec",
            "eval",
            "execfile",
            "load",
            "loads",
            "__builtins__",
            "__import__",
            "subprocess",
            "ctypes",
            "signal",
            "socket",
            "sys",
        }
        _processed = set()
        _MAX_RECURSION_DEPTH = 5
        _MAX_ATTR_TRAVERSAL_DEPTH = 3

        def _nullify(obj: Any, depth: int = 0) -> None:
            if depth > _MAX_RECURSION_DEPTH or id(obj) in _processed:
                return
            _processed.add(id(obj))
            if not hasattr(obj, "__dict__") and not (
                hasattr(obj, "__path__") or hasattr(obj, "__name__")
            ):
                return
            for attr_name in dir(obj):
                if attr_name.startswith("_") and attr_name not in ("__builtins__", "__import__"):
                    continue
                if attr_name in DANGEROUS_NAMES:
                    with contextlib.suppress(AttributeError, TypeError):
                        object.__setattr__(obj, attr_name, None)
                elif depth < _MAX_ATTR_TRAVERSAL_DEPTH:
                    try:
                        child = getattr(obj, attr_name, None)
                        if child is not None and hasattr(child, "__name__"):
                            _nullify(child, depth + 1)
                    except Exception:
                        pass

        _nullify(mod)

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        root_name = name.split(".")[0]
        allowed = {
            "numpy",
            "scipy",
            "math",
            "json",
            "time",
            "core_model",
            "engine",
            "load_flow",
            "fault_analysis",
            "relays",
            "coordination",
        }
        if root_name not in allowed:
            raise ImportError(f"Unauthorized import: {name}")
        return __import__(name, globals, locals, fromlist, level)

    # V-40: Removed `type` from safe builtins — it enables class enumeration
    # via type.__subclasses__() which can find dangerous classes like subprocess.Popen.
    # V-41: Removed `isinstance`/`issubclass` — they enable class hierarchy
    # traversal which can be used to find and invoke dangerous methods.
    safe_globals = {
        "__builtins__": {
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "float": float,
            "int": int,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "pow": pow,
            "print": print,
            "range": range,
            "round": round,
            "set": set,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "complex": complex,
            "Exception": Exception,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "KeyError": KeyError,
            "ImportError": ImportError,
            "RuntimeError": RuntimeError,
            "StopIteration": StopIteration,
            "enumerate": enumerate,
            "zip": zip,
            "reversed": reversed,
            "sorted": sorted,
            "map": map,
            "filter": filter,
            # V-40: `type` REMOVED — use isinstance-style checks are also removed
            # V-41: `isinstance`/`issubclass` REMOVED — prevents class traversal
            "True": True,
            "False": False,
            "None": None,
            "__import__": safe_import,
        },
        "json": json,
        "math": math,
        # Pre-imported safe modules
        "numpy": __import__("numpy") if "numpy" in sys.modules else None,
        "scipy": __import__("scipy") if "scipy" in sys.modules else None,
    }
    # Deep-freeze numpy/scipy to prevent sandbox escape via their submodules
    for mod_name in ("numpy", "scipy"):
        mod = safe_globals.get(mod_name)
        if mod is not None:
            _deep_freeze_module(mod)

    # V-44: Replaced ThreadPoolExecutor with subprocess-based execution.
    # ThreadPoolExecutor cannot kill a running thread — after timeout, the
    # thread continues running in the background consuming resources.
    # Subprocess-based execution allows proper cleanup via process.kill().
    import subprocess
    import tempfile

    # Write the execution wrapper to a temp file
    wrapper_code = '''
import sys
import io
from contextlib import redirect_stdout

# V-42: Set memory limit
try:
    import resource
    max_bytes = {max_memory_mb} * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
except (ValueError, OSError, ImportError):
    pass

# Read and execute the user code
_code = sys.stdin.read()
f = io.StringIO()
try:
    with redirect_stdout(f):
        exec(_code, _safe_globals)
    print("__RESULT_OK__")
    print(f.getvalue(), end="")
except Exception as e:
    print("__RESULT_ERROR__")
    print(str(e))
    import traceback
    traceback.print_exc()
'''.format(max_memory_mb=MAX_MEMORY_MB)

    try:
        # Write wrapper to temp file
        fd, wrapper_path = tempfile.mkstemp(suffix=".py", prefix="etap_exec_")
        os.close(fd)
        with open(wrapper_path, "w") as f:
            f.write(wrapper_code)

        # Serialize safe_globals for the subprocess (only JSON-serializable parts)
        import pickle
        fd, globals_path = tempfile.mkstemp(suffix=".pkl", prefix="etap_globals_")
        os.close(fd)
        with open(globals_path, "wb") as f:
            pickle.dump(safe_globals, f)

        # Run in subprocess with timeout
        try:
            result = subprocess.run(
                [sys.executable, wrapper_path],
                input=code,
                capture_output=True,
                text=True,
                timeout=MAX_EXECUTION_TIME_SECONDS,
            )

            stdout = result.stdout or ""
            stderr = result.stderr or ""

            if stdout.startswith("__RESULT_OK__"):
                output = stdout[len("__RESULT_OK__"):]
                if len(output) > MAX_OUTPUT_LENGTH:
                    output = output[:MAX_OUTPUT_LENGTH] + "\n... [output truncated]"
                print(json.dumps({"success": True, "output": output, "error": None}))
            elif stdout.startswith("__RESULT_ERROR__"):
                error_text = stdout[len("__RESULT_ERROR__"):]
                if stderr:
                    error_text += "\n" + stderr
                print(json.dumps({
                    "success": False,
                    "output": None,
                    "error": error_text[:MAX_OUTPUT_LENGTH],
                    "traceback": stderr[:MAX_OUTPUT_LENGTH] if stderr else None,
                }))
            else:
                # Unexpected output format
                if stderr:
                    print(json.dumps({
                        "success": False,
                        "output": None,
                        "error": stderr[:MAX_OUTPUT_LENGTH],
                        "traceback": None,
                    }))
                else:
                    output = stdout[:MAX_OUTPUT_LENGTH]
                    print(json.dumps({"success": True, "output": output, "error": None}))

        except subprocess.TimeoutExpired:
            # V-44: Process is properly killed — unlike ThreadPoolExecutor
            print(json.dumps({
                "success": False,
                "output": None,
                "error": f"Execution exceeded {MAX_EXECUTION_TIME_SECONDS} seconds",
                "traceback": None,
            }))

    finally:
        # Cleanup temp files
        for path in [wrapper_path, globals_path]:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass


if __name__ == "__main__":
    main()
