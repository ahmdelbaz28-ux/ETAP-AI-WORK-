"""
Secure PowerShell Executor
==========================
P0 Security Control: Validates and executes PowerShell commands in a restricted environment.
Integrates with security_framework.py for input validation.
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from security.security_framework import get_audit_logger, get_validator
except ImportError:
    print(json.dumps({"error": "Security framework not found", "success": False}))
    sys.exit(1)

logger = logging.getLogger(__name__)

POWERSHELL_TIMEOUT_MS = 30000
MAX_OUTPUT_LENGTH = 10000


def _read_command_from_stdin():
    """Read PowerShell command from stdin to prevent shell injection."""
    try:
        command = sys.stdin.read()
        if not command or not command.strip():
            return None
        return command.strip()
    except Exception as e:
        logger.error(f"Failed to read command from stdin: {e}")
        return None


def main():
    command = _read_command_from_stdin()
    if command is None:
        print(json.dumps({"error": "No command provided via stdin", "success": False}))
        sys.exit(1)

    # Limit command length to prevent resource exhaustion
    MAX_COMMAND_LENGTH = 10000
    if len(command) > MAX_COMMAND_LENGTH:
        print(
            json.dumps(
                {
                    "error": f"Command exceeds maximum length of {MAX_COMMAND_LENGTH} characters",
                    "success": False,
                }
            )
        )
        sys.exit(1)

    audit = get_audit_logger()
    validator = get_validator()

    # P0 Validation - must pass before any execution
    if not validator.validate_powershell_command(command):
        audit.log_security_violation(
            "agent_tool", "Forbidden PowerShell pattern detected", {"command_length": len(command)}
        )
        print(
            json.dumps(
                {
                    "error": "Security Violation: Forbidden PowerShell pattern or unauthorized command detected.",
                    "success": False,
                }
            )
        )
        sys.exit(1)

    audit.log_action("agent_tool", "execute_powershell", "restricted_sandbox", True)

    # Execute validated command
    # Security: Use -ExecutionPolicy AllSigned instead of Restricted for defense-in-depth.
    # -NoProfile prevents profile scripts from running (potential attack vector).
    # -NonInteractive prevents interactive prompts.
    # WARNING: -Command mode still allows obfuscated commands. The AST validator
    # above is the primary defense. For maximum security, consider using a
    # constrained runspace or whitelisted cmdlet approach instead.
    import subprocess

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "AllSigned",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=POWERSHELL_TIMEOUT_MS / 1000,
        )

        output = result.stdout or ""
        if len(output) > MAX_OUTPUT_LENGTH:
            output = output[:MAX_OUTPUT_LENGTH] + "\n... [output truncated]"

        if result.returncode != 0:
            err_message = result.stderr or f"Process exited with code {result.returncode}"
            # Sanitize Windows paths from error messages to prevent information
            # leakage. The regex matches drive-letter paths like C:\Users\foo
            # and UNC paths like \\server\share. The previous regex
            # r"[A-Z]:\[^\s]+" was buggy: the single backslash before [^\s]
            # was interpreted as an escape for '[', not a literal backslash,
            # so it never matched any real Windows path.
            import re

            # Match: drive letter, colon, backslash, non-whitespace chars
            # Also match UNC paths: \\server\share
            path_pattern = re.compile(r'(?:[A-Za-z]:\\[^\s"\']+|\\\\[^\s"\\]+\\[^\s"\']+)')
            err_message = path_pattern.sub("[path]", err_message)
            print(json.dumps({"success": False, "output": None, "error": err_message}))
        else:
            print(json.dumps({"success": True, "output": output, "error": None}))

    except subprocess.TimeoutExpired:
        print(
            json.dumps(
                {"success": False, "output": None, "error": "PowerShell execution timed out"}
            )
        )

    except Exception as e:
        print(json.dumps({"success": False, "output": None, "error": str(e)}))


if __name__ == "__main__":
    main()
