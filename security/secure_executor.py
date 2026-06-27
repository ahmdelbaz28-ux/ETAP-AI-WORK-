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
"""

import json
import logging
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from security.security_framework import get_audit_logger, get_validator
except ImportError:
    print(json.dumps({"error": "Security framework not found", "success": False}))
    sys.exit(1)

logger = logging.getLogger(__name__)

MAX_EXECUTION_TIME_SECONDS = 30
MAX_OUTPUT_LENGTH = 10000


def _read_code_from_stdin():
    try:
        code = sys.stdin.read()
        if not code or not code.strip():
            return None
        return code
    except Exception as e:
        logger.error(f"Failed to read code from stdin: {e}")
        return None


def main():
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
                }
            )
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
                }
            )
        )
        sys.exit(1)

    # --- AI Failure-Mode Pre-Scan (guard-skills integration) ---
    # Run the AI failure-mode detector on the submitted code.  MUST_FIX
    # violations (e.g., catch-all error swallowing, hardcoded success
    # returns) block execution.  SHOULD_FIX violations are logged but
    # do not block — they serve as quality feedback to the calling agent.
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
                        }
                    )
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
        # guards module not available — skip guard scan gracefully
        logger.debug("guards module not available, skipping AI failure-mode scan")
    except Exception as guard_err:
        # Guard scan itself must never block execution on error
        logger.warning("AI guard scan failed: %s", guard_err)

    audit.log_action("agent_tool", "execute_python", "restricted_sandbox", True)

    import math

    def _deep_freeze_module(mod):
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

        def _nullify(obj, depth=0):
            if depth > 5 or id(obj) in _processed:
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
                    try:
                        object.__setattr__(obj, attr_name, None)
                    except (AttributeError, TypeError):
                        pass
                elif depth < 3:
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
            "type": type,
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
            "isinstance": isinstance,
            "issubclass": issubclass,
            "True": True,
            "False": False,
            "None": None,
            "__import__": safe_import,
        },
        "json": json,
        "math": math,
        # Pre-imported safe modules (the only modules executable code can
        # access).  Adding a new module requires an explicit entry here.
        "numpy": __import__("numpy") if "numpy" in sys.modules else None,
        "scipy": __import__("scipy") if "scipy" in sys.modules else None,
    }
    # Deep-freeze numpy/scipy to prevent sandbox escape via their submodules
    for mod_name in ("numpy", "scipy"):
        mod = safe_globals.get(mod_name)
        if mod is not None:
            _deep_freeze_module(mod)

    def _exec_target(_code: str, _globals: dict):
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        try:
            with redirect_stdout(f):
                exec(_code, _globals)
            return {"ok": True, "output": f.getvalue(), "error": None, "traceback": None}
        except Exception as e:
            return {
                "ok": False,
                "output": None,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }

    # Cross-platform timeout enforcement (replaces signal.SIGALRM)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_exec_target, code, safe_globals)
            result = future.result(timeout=MAX_EXECUTION_TIME_SECONDS)
    except FutureTimeoutError:
        print(
            json.dumps(
                {
                    "success": False,
                    "output": None,
                    "error": f"Execution exceeded {MAX_EXECUTION_TIME_SECONDS} seconds",
                    "traceback": None,
                }
            )
        )
        return

    if result.get("ok"):
        output = result.get("output") or ""
        if len(output) > MAX_OUTPUT_LENGTH:
            output = output[:MAX_OUTPUT_LENGTH] + "\n... [output truncated]"
        print(json.dumps({"success": True, "output": output, "error": None}))
    else:
        print(
            json.dumps(
                {
                    "success": False,
                    "output": None,
                    "error": result.get("error"),
                    "traceback": result.get("traceback"),
                }
            )
        )


if __name__ == "__main__":
    main()
