#!/usr/bin/env python3
"""
scripts/check_env_docs.py — Guard checking that all environment variables accessed
in codebase are documented in .env.example.

Ensures fail-closed documentation parity so operators are never surprised by
undocumented production environment variables or configuration switches.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Set

# Ensure safe console output on Windows encodings (e.g. cp1256)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories to scan for environment variable lookups across all production units
SCAN_DIRS = [
    REPO_ROOT / "api",
    REPO_ROOT / "core",
    REPO_ROOT / "services",
    REPO_ROOT / "hf-space",
    REPO_ROOT / "integrations",
    REPO_ROOT / "agents",
    REPO_ROOT / "engine",
    REPO_ROOT / "etap_integration",
    REPO_ROOT / "gis_integration",
    REPO_ROOT / "scada",
    REPO_ROOT / "scada_protocols",
    REPO_ROOT / "security",
    REPO_ROOT / "worker",
    REPO_ROOT / "reporting",
    REPO_ROOT / "knowledge",
    REPO_ROOT / "utils",
    REPO_ROOT / "scripts",
    REPO_ROOT / "deploy",
    REPO_ROOT / "ai_context_engine",
    REPO_ROOT / "skills",
]

# Explicit directory exclusion set
EXCLUDE_PARTS = {"scratch", "tests", "demos", ".git", "node_modules", "venv", ".venv", "__pycache__"}

# Standard runtime / CI / system / platform variables exempt from .env.example
ALLOWLIST = {
    # System / OS / Display
    "PATH",
    "HOME",
    "PYTHONPATH",
    "TEMP",
    "TMP",
    "TERM",
    "PWD",
    "LANG",
    "SHELL",
    "USER",
    "USERNAME",
    "SYSTEMROOT",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    # Runner / Process Concurrency
    "WEB_CONCURRENCY",
    "WORKERS",
    "PLAYWRIGHT_BROWSERS_PATH",
    "USE_TORCH",
    "USE_TF",
    # CI / GitHub Actions & PR Context
    "CI",
    "GITHUB_ACTIONS",
    "GITHUB_REPOSITORY",
    "GITHUB_REF",
    "GITHUB_SHA",
    "GITHUB_RUN_ID",
    "GITHUB_RUN_NUMBER",
    "GITHUB_WORKFLOW",
    "GITHUB_EVENT_NAME",
    "GITHUB_EVENT_PATH",
    "RUNNER_TEMP",
    "RUNNER_TOOL_CACHE",
    "GH_TOKEN",
    "PR_HEAD_REPO",
    "PR_HEAD_SHA",
    "PR_NUMBER",
    # Platform deployment metadata
    "SPACE_ID",
    "SPACE_REPO_NAME",
    "SPACE_AUTHOR_NAME",
    "HF_SPACE_ID",
    "HF_COMMIT_SHA",
    "COMMIT_SHA",
    "DEPLOY_SHA",
    "VERCEL",
    "VERCEL_ENV",
    "VERCEL_URL",
    "VERCEL_GIT_COMMIT_SHA",
    "DYNO",
    "KUBERNETES_SERVICE_HOST",
    # Test harnesses
    "PYTEST_CURRENT_TEST",
    "COVERAGE_PROCESS_START",
    "TESTING",
    "ENV",  # Standard alias for ENVIRONMENT
    # Local tooling / manual scripts (single-purpose developer utilities)
    "UPTIMEROBOT_API_KEY",
    "DAYTONA_API_TOKEN",
    "DAYTONA_API_URL",
    "DAYTONA_SERVER_URL",
    "SONAR_PROJECT_KEY",
    "E2E_USER_PASSWORD",
    "LOCUST_TEST_PASSWORD",
    "LOCUST_TEST_USERNAME",
    "SMOKE_BASE_URL",
    "SMOKE_UI_URL",
    "STAGING_BASE_URL",
    "PRODUCTION_URL",
}

ENV_LOOKUP_PATTERN = re.compile(
    r'(?:os\.getenv|os\.environ\.get|os\.environ\[)\s*\(\s*["\']([A-Z0-9_]{3,})["\']'
    r'|os\.environ\[\s*["\']([A-Z0-9_]{3,})["\']'
)


def get_documented_vars(env_example_path: Path) -> Set[str]:
    """Extract all documented variables in .env.example and .env.staging.example (active or commented)."""
    if not env_example_path.exists():
        print(f"ERROR: {env_example_path} does not exist!")
        sys.exit(1)

    documented = set()
    sources = [env_example_path]
    staging_example = env_example_path.parent / ".env.staging.example"
    if staging_example.exists():
        sources.append(staging_example)

    for source in sources:
        with open(source, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Match active VAR=val or commented # VAR=val
                m = re.match(r"^(?:#\s*)?([A-Z0-9_]{3,})=", line)
                if m:
                    documented.add(m.group(1))
    return documented


def find_code_env_vars() -> Set[str]:
    """Scan Python files across all production directories and root *.py for environment variable lookups."""
    code_vars = set()
    files_to_scan = []

    for directory in SCAN_DIRS:
        if not directory.exists():
            continue
        for path in directory.rglob("*.py"):
            if not any(part in path.parts for part in EXCLUDE_PARTS):
                files_to_scan.append(path)

    # Include root-level python files (e.g. engineering_service.py, compat.py, etc.)
    for path in REPO_ROOT.glob("*.py"):
        if not any(part in path.parts for part in EXCLUDE_PARTS):
            files_to_scan.append(path)

    for path in files_to_scan:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            for match in ENV_LOOKUP_PATTERN.finditer(content):
                var_name = match.group(1) or match.group(2)
                if var_name:
                    code_vars.add(var_name)
        except Exception as exc:
            print(f"Warning: Failed reading {path}: {exc}")

    return code_vars


def main() -> int:
    env_example_file = REPO_ROOT / ".env.example"
    documented = get_documented_vars(env_example_file)
    used_vars = find_code_env_vars()

    # Filter out standard system allowlist
    missing = {v for v in used_vars if v not in documented and v not in ALLOWLIST}

    print("=" * 70)
    print("ENVIRONMENT VARIABLE DOCUMENTATION CHECK (.env.example)")
    print("=" * 70)
    print(f"Total environment variables found in code: {len(used_vars)}")
    print(f"Total documented in .env.example:          {len(documented)}")
    print(f"Allowlisted system / runtime / tooling:   {len(ALLOWLIST)}")

    if missing:
        print(f"\n❌ FAILED: Found {len(missing)} environment variables accessed in code")
        print("   but NOT documented in .env.example:")
        for var in sorted(missing):
            print(f"   - {var}")
        print("\nPlease document them in .env.example with descriptive comments and defaults.")
        return 1

    print("\n✅ SUCCESS: All environment variables accessed in code are documented in .env.example!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
