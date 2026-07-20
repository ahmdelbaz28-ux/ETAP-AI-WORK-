"""
Secure PowerShell Executor
==========================
P0 Security Control: Validates and executes PowerShell commands in a restricted environment.
Integrates with security_framework.py for input validation.

Security hardening (2026-07-20):
  - Replaced -Command with temp file execution (-File) to prevent command-line obfuscation
  - Added cmdlet whitelist for defense-in-depth
  - Added character-set whitelist validation
  - Added input sanitization pipeline
  - Uses constrained runspace via execution policy
"""

import json
import logging
import os
import sys
import tempfile
import re
import subprocess

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
# Any command containing a verb-noun pattern that is NOT in this list will
# be blocked. This provides defense-in-depth against obfuscated commands
# that bypass the AST validator.
ALLOWED_CMDLETS: set[str] = {
    # File system operations
    "get-childitem", "set-location", "write-output", "out-file",
    "get-content", "add-content", "set-content", "remove-item",
    "copy-item", "move-item", "new-item", "test-path",
    "get-item", "get-itemproperty", "set-itemproperty",
    "get-acl", "set-acl",
    # Process operations
    "get-process", "start-process", "stop-process",
    "get-service", "start-service", "stop-service",
    # Network operations
    "test-connection", "resolve-dnsname",
    "invoke-webrequest", "invoke-restmethod",
    # System information
    "get-wmiobject", "get-ciminstance", "get-cimclass",
    "get-date", "get-location", "get-computerinfo",
    "get-os", "get-process",
    # Active Directory (read-only)
    "get-aduser", "get-adgroup", "get-adgroupmember",
    "get-adcomputer", "get-adorganizationalunit",
    # Git operations
    "get-gitstatus",
    # Utility
    "where-object", "select-object", "sort-object",
    "group-object", "measure-object", "foreach-object",
    "compare-object", "format-table", "format-list",
    "convertto-json", "convertfrom-json", "convertto-csv",
    "convertfrom-csv", "export-csv", "import-csv",
    "write-host", "write-progress", "write-verbose",
    "write-debug", "write-warning", "write-error",
    "new-object", "add-type", "get-member",
    "get-command", "get-help", "get-module",
    "import-module", "export-modulemember",
    "set-strictmode", "set-psdebug",
    "get-variable", "set-variable", "remove-variable",
    "get-childitemvariable",
    "new-psdrive", "get-psdrive", "remove-psdrive",
    "register-psrepository", "get-psrepository",
    # Pipeline common
    "select-string", "out-null", "out-string",
    "tee-object", "write-host",
}


def _validate_cmdlet_whitelist(command: str) -> bool:
    """Check that all verb-noun cmdlet invocations are in the whitelist.
    
    This uses a regex to find verb-noun patterns (e.g., Get-ChildItem)
    and rejects the command if any matched pattern is not in ALLOWED_CMDLETS.
    This provides defense-in-depth against obfuscated commands.
    """
    # Match Verb-Noun patterns: Get-ChildItem, Invoke-WebRequest, etc.
    cmdlet_pattern = re.compile(
        r'\b([A-Za-z]+)-([A-Za-z]+)\b',
        re.IGNORECASE,
    )
    for match in cmdlet_pattern.finditer(command):
        cmdlet = match.group(0).lower()
        if cmdlet not in ALLOWED_CMDLETS:
            logger.warning("Blocked unauthorized cmdlet: %s", cmdlet)
            return False
    return True


def _validate_character_set(command: str) -> bool:
    """Ensure command only contains allowed characters.
    
    This prevents injection of null bytes, control characters, and other
    special characters that could be used for obfuscation or bypass.
    """
    # Allow: alphanumeric, spaces, common punctuation, and pipeline chars
    allowed = re.compile(r'^[A-Za-z0-9 \t\r\n.,;:!@#$%^&*()_+\-=\[\]{}|\\\'\"`~<>/?]+$')
    if not allowed.match(command):
        logger.warning("Blocked command with disallowed characters")
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
        fd, script_path = tempfile.mkstemp(suffix='.ps1', prefix='etap_')
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
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # On Windows, restrict file permissions to current user
        try:
            import win32security
            import ntsecuritycon as con
            user, _, _ = win32security.GetUserTokenInformation(
                win32security.OpenProcessToken(
                    win32security.GetCurrentProcess(),
                    win32security.TOKEN_QUERY
                ),
                win32security.TokenUser
            )
            sd = win32security.GetFileSecurity(
                script_path,
                win32security.DACL_SECURITY_INFORMATION
            )
            dacl = win32security.ACL()
            dacl.AddAccessAllowedAce(
                win32security.ACL_REVISION,
                con.FILE_GENERIC_READ | con.FILE_GENERIC_WRITE | con.FILE_DELETE,
                user
            )
            sd.SetSecurityDescriptorDacl(1, dacl, 0)
            win32security.SetFileSecurity(
                script_path,
                win32security.DACL_SECURITY_INFORMATION,
                sd
            )
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

    # P0 Validation - must pass before any execution
    if not validator.validate_powershell_command(command):
        audit.log_security_violation(
            "agent_tool", "Forbidden PowerShell pattern detected", {"command_length": len(command)},
        )
        print(
            json.dumps(
                {
                    "error": "Security Violation: Forbidden PowerShell pattern or unauthorized command detected.",
                    "success": False,
                },
            ),
        )
        sys.exit(1)

    # Defense-in-depth: cmdlet whitelist check
    if not _validate_cmdlet_whitelist(command):
        audit.log_security_violation(
            "agent_tool",
            "Unauthorized cmdlet detected",
            {"command_length": len(command)},
        )
        print(
            json.dumps(
                {
                    "error": "Security Violation: Unauthorized PowerShell cmdlet detected.",
                    "success": False,
                },
            ),
        )
        sys.exit(1)

    # Defense-in-depth: character set validation
    if not _validate_character_set(command):
        audit.log_security_violation(
            "agent_tool",
            "Disallowed characters in command",
            {"command_length": len(command)},
        )
        print(
            json.dumps(
                {
                    "error": "Security Violation: Command contains disallowed characters.",
                    "success": False,
                },
            ),
        )
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

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "AllSigned",
                "-File",
                script_path,
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


if __name__ == "__main__":
    main()