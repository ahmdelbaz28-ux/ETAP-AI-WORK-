"""
Secure Python Executor
======================
P0 Security Control: Validates and executes Python code in a restricted environment.
Integrates with security_framework.py for AST-based validation.

Security Measures:
- Code passed via stdin (not CLI args) to prevent shell injection
- AST validation before execution
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from security.security_framework import get_audit_logger, get_validator
except ImportError:
    print(json.dumps({'error': 'Security framework not found', 'success': False}))
    sys.exit(1)

logger = logging.getLogger(__name__)

MAX_EXECUTION_TIME_SECONDS = 30
MAX_OUTPUT_LENGTH = 10000


def _timeout_handler(signum, frame):
    raise TimeoutError(f'Execution exceeded {MAX_EXECUTION_TIME_SECONDS} seconds')


def _read_code_from_stdin():
    try:
        code = sys.stdin.read()
        if not code or not code.strip():
            return None
        return code
    except Exception as e:
        logger.error(f'Failed to read code from stdin: {e}')
        return None


def main():
    code = _read_code_from_stdin()
    if code is None:
        print(json.dumps({'error': 'No code provided via stdin', 'success': False}))
        sys.exit(1)

    audit = get_audit_logger()
    validator = get_validator()

    if not validator.validate_python_code(code):
        audit.log_security_violation('agent_tool', 'Forbidden code pattern detected in Python tool', {'code_length': len(code)})
        print(json.dumps({
            'error': 'Security Violation: Forbidden code pattern or unauthorized import detected.',
            'success': False
        }))
        sys.exit(1)

    audit.log_action('agent_tool', 'execute_python', 'restricted_sandbox', True)

    import math
    safe_globals = {
        '__builtins__': {
            'abs': abs, 'all': all, 'any': any, 'bool': bool, 'dict': dict,
            'float': float, 'int': int, 'len': len, 'list': list, 'max': max,
            'min': min, 'pow': pow, 'print': print, 'range': range, 'round': round,
            'set': set, 'str': str, 'sum': sum, 'tuple': tuple, 'type': type,
            'complex': complex, 'Exception': Exception, 'ValueError': ValueError,
            'TypeError': TypeError, 'KeyError': KeyError, 'ImportError': ImportError,
            'RuntimeError': RuntimeError, 'StopIteration': StopIteration,
            'enumerate': enumerate, 'zip': zip, 'reversed': reversed, 'sorted': sorted,
            'map': map, 'filter': filter, 'isinstance': isinstance, 'issubclass': issubclass,
            'True': True, 'False': False, 'None': None,
            # `__import__` is exposed so the validator's allow-list (see
            # InputValidator.validate_python_code) is actually enforced at
            # execution time, not just at validation time. Every import the
            # executed code attempts is checked against `allowed_imports`
            # by the validator BEFORE this sandbox runs the code; an
            # unauthorized import never reaches `exec`.
            # __import__ is deliberately EXCLUDED from the sandbox.
            # All allowed modules must be pre-imported and injected into
            # safe_globals explicitly. This closes the sandbox-escape vector
            # where code could call __import__('os') to break out.
        },
        'json': json,
        'math': math,
        # Pre-imported safe modules (the only modules executable code can
        # access).  Adding a new module requires an explicit entry here.
        'numpy': __import__('numpy') if 'numpy' in sys.modules else None,
        'scipy': __import__('scipy') if 'scipy' in sys.modules else None,
    }

    try:
        import signal
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(MAX_EXECUTION_TIME_SECONDS)
    except (AttributeError, OSError) as sig_err:
        # Signal-based timeouts are POSIX/Unix-only.  On Windows or in
        # embedded contexts (e.g. notebooks) this will raise AttributeError;
        # OSError covers cases where the alarm limit is rejected.  We still
        # execute the code, but the wall-clock timeout is best-effort.
        logger.debug("SIGALRM not available (%s); execution timeout disabled", sig_err)

    try:
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            exec(code, safe_globals)

        output = f.getvalue()
        if len(output) > MAX_OUTPUT_LENGTH:
            output = output[:MAX_OUTPUT_LENGTH] + '\n... [output truncated]'

        try:
            import signal
            signal.alarm(0)
        except (AttributeError, OSError) as sig_err:
            logger.debug("Could not clear SIGALRM after success (%s)", sig_err)

        print(json.dumps({'success': True, 'output': output, 'error': None}))

    except TimeoutError as e:
        try:
            import signal
            signal.alarm(0)
        except (AttributeError, OSError) as sig_err:
            logger.debug("Could not clear SIGALRM after timeout (%s)", sig_err)
        print(json.dumps({'success': False, 'output': None, 'error': str(e), 'traceback': None}))

    except Exception as e:
        try:
            import signal
            signal.alarm(0)
        except (AttributeError, OSError) as sig_err:
            logger.debug("Could not clear SIGALRM after exception (%s)", sig_err)
        print(json.dumps({'success': False, 'output': None, 'error': str(e), 'traceback': traceback.format_exc()}))


if __name__ == '__main__':
    main()
