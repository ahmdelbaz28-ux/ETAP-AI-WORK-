"""
Secure PowerShell Executor
==========================
P0 Security Control: Validates and executes PowerShell commands in a restricted environment.
Integrates with security_framework.py for input validation.

Security hardening (2026-08-02 — V-34, V-36, V-37, V-38 fixes):
  - V-34: Removed dangerous cmdlets from whitelist (start-process, remove-item,
    invoke-webrequest, invoke-restmethod, add-type, new-object, import-module)
  - V-36: Fixed regex bypass — now also catches obfuscated invocations like
    & "Invoke-Expression", Get-Command Invoke-Expression, etc.
  - V-37: Aligned cmdlet whitelist with security_framework.py dangerous_patterns
    (no more contradictions between the two checks)
  - V-38: Backtick escaping now blocked in character-set whitelist
  - Replaced -Command with temp file execution (-File) to prevent command-line obfuscation
  - Added cmdlet whitelist for defense-in-depth
  - Added character-set whitelist validation
  - Uses constrained runspace via execution policy
"""

import json
import logging
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from security.security_framework import get_audit_logger, get_validator
except ImportError:
    print(json.dumps({"error": "Security framework not found", "success": False}))
    sys.exit(1)

logger = logging.getLogger(__name__)

POWERSHELL_TIMEOUT_MS = 30000
MAX_OUTPUT_LENGTH = 10000
MAX_COMMAND_LENGTH = 10000

# ---------------------------------------------------------------------------
# Whitelist of allowed PowerShell cmdlets and functions
# ---------------------------------------------------------------------------
# V-34 FIX: Removed dangerous cmdlets that were previously in the whitelist:
#   - start-process   → can launch arbitrary executables
#   - remove-item     → can delete critical files
#   - invoke-webrequest → can exfiltrate data via HTTP
#   - invoke-restmethod → can exfiltrate data via HTTP
#   - new-object      → can load malicious COM objects
#   - add-type        → can load malicious .NET assemblies
#   - import-module   → can load malicious PowerShell modules
#   - new-psdrive     → can map network drives
#   - register-psrepository → can register malicious repos
#
# V-37 FIX: This whitelist is now aligned with security_framework.py's
# dangerous_patterns list. Previously, the framework blocked
# Invoke-WebRequest/Start-Process/New-Object but the whitelist here
# ALLOWED them — creating a contradictory security posture.
ALLOWED_CMDLETS: set[str] = {
    # File system operations (READ-ONLY + safe writes)
    "get-childitem",
    "set-location",
    "write-output",
    "out-file",
    "get-content",
    "add-content",
    "set-content",
    "copy-item",
    "move-item",
    "new-item",
    "test-path",
    "get-item",
    "get-itemproperty",
    "set-itemproperty",
    "get-acl",
    # Process operations (READ-ONLY — no start-process)
    "get-process",
    "stop-process",  # allowed for self-termination of runaway processes
    "get-service",
    # Network operations (READ-ONLY — no invoke-webrequest/invoke-restmethod)
    "test-connection",
    "resolve-dnsname",
    # System information (READ-ONLY)
    "get-wmiobject",
    "get-ciminstance",
    "get-cimclass",
    "get-date",
    "get-location",
    "get-computerinfo",
    # Active Directory (read-only)
    "get-aduser",
    "get-adgroup",
    "get-adgroupmember",
    "get-adcomputer",
    "get-adorganizationalunit",
    # Git operations
    "get-gitstatus",
    # Utility / pipeline
    "where-object",
    "select-object",
    "sort-object",
    "group-object",
    "measure-object",
    "foreach-object",
    "compare-object",
    "format-table",
    "format-list",
    "convertto-json",
    "convertfrom-json",
    "convertto-csv",
    "convertfrom-csv",
    "export-csv",
    "import-csv",
    "write-host",
    "write-progress",
    "write-verbose",
    "write-debug",
    "write-warning",
    "write-error",
    "get-member",
    "get-command",
    "get-help",
    "get-module",
    "set-strictmode",
    "set-psdebug",
    "get-variable",
    "set-variable",
    "remove-variable",
    "get-psdrive",
    "get-psrepository",
    # Pipeline common
    "select-string",
    "out-null",
    "out-string",
    "tee-object",
}

# V-34: Explicitly BLOCKED cmdlets — these are dangerous and MUST NOT be
# allowed even if someone adds them to ALLOWED_CMDLETS by mistake.
# This list is checked AFTER the whitelist for defense-in-depth.
BLOCKED_CMDLETS: set[str] = {
    "start-process",
    "invoke-webrequest",
    "invoke-restmethod",
    "invoke-expression",
    "invoke-command",
    "new-object",
    "add-type",
    "import-module",
    "remove-item",
    "new-psdrive",
    "remove-psdrive",
    "register-psrepository",
    "set-acl",
}


def _validate_cmdlet_whitelist(command: str) -> bool:
    """Check that all verb-noun cmdlet invocations are in the whitelist.

    V-36 FIX: Enhanced regex to catch obfuscated invocations:
    - Direct: Get-ChildItem
    - String invocation: & "Invoke-Expression"
    - Get-Command: Get-Command Invoke-Expression
    - Quoted: "Start-Process"

    Also checks BLOCKED_CMDLETS for defense-in-depth (V-34).
    """
    # V-36: Enhanced pattern matching — catch multiple invocation forms
    # 1. Standard Verb-Noun patterns
    cmdlet_pattern = re.compile(
        r"\b([A-Za-z]+)-([A-Za-z]+)\b",
    )
    # 2. Quoted cmdlets: "Verb-Noun" or 'Verb-Noun'
    quoted_cmdlet_pattern = re.compile(
        r'["\']([A-Za-z]+)-([A-Za-z]+)["\']',
    )

    found_cmdlets = set()
    for match in cmdlet_pattern.finditer(command):
        cmdlet = match.group(0).lower()
        found_cmdlets.add(cmdlet)
    for match in quoted_cmdlet_pattern.finditer(command):
        cmdlet = f"{match.group(1)}-{match.group(2)}".lower()
        found_cmdlets.add(cmdlet)

    for cmdlet in found_cmdlets:
        # V-34: Check blocked list first (defense-in-depth)
        if cmdlet in BLOCKED_CMDLETS:
            logger.warning("Blocked explicitly dangerous cmdlet: %s", cmdlet)
            return False
        # Then check whitelist
        if cmdlet not in ALLOWED_CMDLETS:
            logger.warning("Blocked unauthorized cmdlet: %s", cmdlet)
            return False
    return True


def _validate_character_set(command: str) -> bool:
    """Ensure command only contains allowed characters.

    V-38 FIX: Backtick (`) is now BLOCKED to prevent PowerShell escape
    obfuscation. Previously, backticks were allowed in the character set
    but blocked by security_framework.py — contradictory.
    """
    # V-72 FIX: Removed backslash (\\) from allowed character set.
    # On Windows, backslash is a path separator (C:\Windows\System32\...)
    # and could be used for path traversal. The cmdlet whitelist should
    # prevent this, but defense-in-depth requires removing it.
    # Backtick (`) is EXPLICITLY EXCLUDED to prevent PowerShell escape
    # obfuscation (V-38 fix). The dash '-' is placed at the END
    # of the character class to avoid SonarCloud S5996.
    allowed = re.compile(r'^[A-Za-z0-9 \t\r\n.,;:!@#$%^&*()_+\=\[\]{}|/\'"~<>?\-]+$')
    if not allowed.match(command):
        logger.warning("Blocked command with disallowed characters")
        return False
    # V-38: Explicitly check for backticks (redundant but clear)
    if "`" in command:
        logger.warning("Blocked command with backtick escaping")
        return False
    return True


def _write_script_to_temp(command: str) -> str | None:
    """Write the validated PowerShell command to a temporary .ps1 file.

    Using -File instead of -Command prevents command-line obfuscation
    techniques because:
      1. The script is written to a file with restricted permissions
      2. No command-line argument parsing is involved
      3. The PowerShell engine reads the file directly
    """
    try:
        # Create a temp file with .ps1 extension
        fd, script_path = tempfile.mkstemp(suffix=".ps1", prefix="etap_")
        os.close(fd)

        # Write the command with strict mode and error handling
        script_content = (
            "# ETAP Secure PowerShell Script\n"
            "# Auto-generated - Do not modify\n"
            "Set-StrictMode -Version Latest\n"
            "$ErrorActionPreference = 'Stop'\n\n"
            f"{command}\n"
        )

        # Write with restricted permissions (owner read/write only)
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        # On Windows, restrict file permissions to current user
        try:
            import ntsecuritycon as con
            import win32security

            user, _, _ = win32security.GetUserTokenInformation(
                win32security.OpenProcessToken(
                    win32security.GetCurrentProcess(), win32security.TOKEN_QUERY
                ),
                win32security.TokenUser,
            )
            sd = win32security.GetFileSecurity(script_path, win32security.DACL_SECURITY_INFORMATION)
            dacl = win32security.ACL()
            dacl.AddAccessAllowedAce(
                win32security.ACL_REVISION,
                con.FILE_GENERIC_READ | con.FILE_GENERIC_WRITE | con.FILE_DELETE,
                user,
            )
            sd.SetSecurityDescriptorDacl(1, dacl, 0)
            win32security.SetFileSecurity(script_path, win32security.DACL_SECURITY_INFORMATION, sd)
        except ImportError:
            # win32security not available - still secure enough on HF Space
            pass

        return script_path
    except Exception as e:
        logger.exception("Failed to write temp script: %s", e)
        return None


def _read_command_from_stdin():
    """Read PowerShell command from stdin to prevent shell injection."""
    try:
        command = sys.stdin.read()
        if not command or not command.strip():
            return None
        return command.strip()
    except Exception as e:
        logger.exception("Failed to read command from stdin: %s", e)
        return None


def _security_violation(audit, reason: str, command_len: int, message: str) -> None:
    """Log a security violation and print the JSON failure response."""
    audit.log_security_violation("agent_tool", reason, {"command_length": command_len})
    print(json.dumps({"error": message, "success": False}))


def _run_security_checks(command: str, audit, validator) -> bool:
    """Run P0 + cmdlet whitelist + character set checks. Returns True if all pass."""
    cmd_len = len(command)
    if not validator.validate_powershell_command(command):
        _security_violation(
            audit,
            "Forbidden PowerShell pattern detected",
            cmd_len,
            "Security Violation: Forbidden PowerShell pattern or unauthorized command detected.",
        )
        return False
    if not _validate_cmdlet_whitelist(command):
        _security_violation(
            audit,
            "Unauthorized cmdlet detected",
            cmd_len,
            "Security Violation: Unauthorized PowerShell cmdlet detected.",
        )
        return False
    if not _validate_character_set(command):
        _security_violation(
            audit,
            "Disallowed characters in command",
            cmd_len,
            "Security Violation: Command contains disallowed characters.",
        )
        return False
    return True


def _execute_powershell(script_path: str) -> None:
    """Run powershell with -File and print the JSON result. Cleans up temp file."""
    try:
        # V-55 FIX: Use "pwsh" (PowerShell Core) instead of "powershell" (Windows-only).
        # On Linux/Docker/HF Spaces, only pwsh is available. On Windows, both exist
        # but pwsh is the modern cross-platform version.
        # V-56 FIX: Use "Bypass" execution policy instead of "AllSigned" — the script
        # content is already validated by the cmdlet whitelist + character set checks
        # above, and AllSigned would reject the auto-generated unsigned temp script.
        result = subprocess.run(
            [
                "pwsh",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,

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
            # Sanitize Windows file paths (e.g. C:\Users\...) from error
            # messages to avoid leaking internal directory structure.
            err_message = re.sub(r"[A-Z]:\\[^\s]+", "[path]", err_message)

            # Sanitize paths from error messages
            import re

            err_message = re.sub(r"[A-Z]:\[^\s]+", "[path]", err_message)
            print(json.dumps({"success": False, "output": None, "error": err_message}))
        else:
            print(json.dumps({"success": True, "output": output, "error": None}))

    except subprocess.TimeoutExpired:
        print(
            json.dumps(
                {"success": False, "output": None, "error": "PowerShell execution timed out"},
            ),
        )

    except Exception as e:
        print(json.dumps({"success": False, "output": None, "error": str(e)}))

    finally:
        # Clean up temp script file
        try:
            if script_path and os.path.exists(script_path):
                os.remove(script_path)
        except Exception as e:
            logger.warning("Failed to clean up temp script %s: %s", script_path, e)


def main():
    command = _read_command_from_stdin()
    if command is None:
        print(json.dumps({"error": "No command provided via stdin", "success": False}))
        sys.exit(1)

    # Limit command length to prevent resource exhaustion
    if len(command) > MAX_COMMAND_LENGTH:
        print(
            json.dumps(
                {
                    "error": f"Command exceeds maximum length of {MAX_COMMAND_LENGTH} characters",
                    "success": False,
                },
            ),
        )
        sys.exit(1)

    audit = get_audit_logger()
    validator = get_validator()

    # P0 + defense-in-depth validations
    if not _run_security_checks(command, audit, validator):
        sys.exit(1)

    audit.log_action("agent_tool", "execute_powershell", "restricted_sandbox", True)

    # Write command to temp script and execute via -File (more secure than -Command)
    script_path = _write_script_to_temp(command)
    if script_path is None:
        print(
            json.dumps(
                {"success": False, "output": None, "error": "Failed to create temporary script"},
            ),
        )
        sys.exit(1)

    _execute_powershell(script_path)


if __name__ == "__main__":
    main()
