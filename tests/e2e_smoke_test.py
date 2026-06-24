"""
End-to-end smoke tests for the AhmedETAP Engineering Platform.

These tests validate core CLI entry points and file presence without
touching production data or external services.
"""

import os
import subprocess
import sys


def run_command(cmd, timeout=90):
    """Run a command and return the CompletedProcess."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class TestValidationSuiteCLI:
    """Smoke tests for the engineering validation suite CLI."""

    def test_validation_suite_cli_passes(self):
        """GIVEN the validation_suite.py script is available
        WHEN it is executed via python3
        THEN it exits with code 0 and reports all tests passing.
        """
        result = run_command([sys.executable, "scripts/dev/validation_suite.py"])

        assert result.returncode == 0, (
            f"validation_suite.py failed with return code {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        assert "VALIDATION SUMMARY" in result.stdout
        assert "Passed:" in result.stdout

    def test_syntax_validation_cli_passes(self):
        """GIVEN the validate_syntax.py script is available
        WHEN it is executed via python3
        THEN it exits with code 0 and reports all files valid.
        """
        result = run_command([sys.executable, "validate_syntax.py"])

        assert result.returncode == 0, (
            f"validate_syntax.py failed with return code {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        assert "STATUS: ALL PYTHON FILES PASS SYNTAX VALIDATION" in result.stdout


class TestDockerComposePresence:
    """Smoke tests for Docker Compose file availability."""

    def test_docker_compose_file_is_present(self):
        """GIVEN the repository root
        WHEN checking for docker-compose.yml
        THEN the file exists and is a non-empty YAML file.
        """
        compose_path = os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml")
        compose_path = os.path.abspath(compose_path)

        assert os.path.isfile(compose_path), f"docker-compose.yml not found at {compose_path}"
        assert os.path.getsize(compose_path) > 0, "docker-compose.yml is empty"
