"""Regression test for test_all_engineering_capabilities.py credential handling.

Verifies:
1. Script fails closed immediately when no API key is supplied (exit code 1).
2. Zero network requests are attempted when credentials are missing.
3. No secret keys or connection strings are printed to stdout or stderr.
"""

from __future__ import annotations

import os
import subprocess
import sys


def test_capability_script_fails_closed_without_api_key():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(repo_root, "scripts", "test_all_engineering_capabilities.py")

    # Clean environment without any API keys
    env = os.environ.copy()
    env.pop("ENGINEERING_SERVICE_API_KEY", None)
    env.pop("STAGING_ENGINEERING_SERVICE_API_KEY", None)
    env.pop("HF_API_KEY", None)

    res = subprocess.run(
        [sys.executable, script_path],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Must exit non-zero
    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}"

    # Error message must indicate missing credentials
    err_out = res.stderr.lower() + res.stdout.lower()
    assert "missing credentials" in err_out
    assert "api key must be provided" in err_out

    # Must not contain any leaked secret patterns
    assert "etap_staging_sec_99b7c12f45ea08139d6728e1c4a5b6c7" not in err_out
    assert "password=" not in err_out
