#!/usr/bin/env python3
"""
Security scanner to detect hardcoded secrets before commit.
Run: python scripts/security_scan.py

Exclusions (intentional, audited):
  - Test files: tests/**, *_test.py, test_*.py, acp_runtime/tests/**
    These legitimately use weak passwords (e.g. "password123") to verify
    that the auth module correctly rejects them.
  - Blocklist/security fixtures: security/security_framework.py,
    api/auth.py, api/security_audit.py — these DEFINE the blocklist.
  - docker-compose.yml: GRAFANA_ADMIN_PASSWORD has a safe default
    ("admin") that is always overridden by env vars in production.
  - Inline annotations: lines containing "# pragma: allowlist secret"
    or "# security: intentional" are skipped.
"""

import os
import re
import sys

SECRET_PATTERNS = [
    (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
    (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret"),
    (r'api[_-]?key\s*=\s*["\'][^"\']{16,}["\']', "Hardcoded API key"),
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI-style key"),
    (r"ghp_[a-zA-Z0-9]{30,}", "GitHub PAT"),
    (r"admin123|password123|123456", "Weak default password"),
]

EXCLUDED_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "output", "dist"}
EXCLUDED_FILES = {".env.example", "security_scan.py", "README.md", "SECURITY.md"}

# Files where weak passwords / test secrets are intentional and audited.
# Each entry is a path relative to repo root.
EXCLUDED_PATHS = {
    # Test fixtures — must use weak passwords to verify blocklist logic
    "tests/unit_tests.py",
    "tests/test_auth_api.py",
    "acp_runtime/tests/test_integration.py",
    # Security fixtures — these files DEFINE the blocklist
    "security/security_framework.py",
    "security/mfa.py",
    "api/auth.py",
    "api/security_audit.py",
    # Setup scripts — uses a clearly-marked test password for smoke tests
    "run_complete_setup.py",
    # Docker compose — has safe default that's always overridden in prod
    "docker-compose.yml",
}

# Inline annotations that mark a line as intentionally containing a test secret
ALLOWLIST_MARKERS = ("# pragma: allowlist secret", "# security: intentional", "# nosec")


def scan_file(filepath):
    issues = []
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            content = f.read()
            for i, line in enumerate(content.split("\n"), 1):
                # Skip lines with allowlist annotation
                if any(marker in line for marker in ALLOWLIST_MARKERS):
                    continue
                for pattern, desc in SECRET_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        if any(x in line for x in ["os.environ", "getenv", "get("]):
                            continue
                        if "example" in line.lower() or "placeholder" in line.lower():
                            continue
                        issues.append(f"{filepath}:{i} | {desc}: {line.strip()[:60]}")
    except Exception:
        pass
    return issues


def main():
    all_issues = []
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for f in files:
            if f in EXCLUDED_FILES:
                continue
            if f.endswith((".py", ".yml", ".yaml", ".json", ".env", ".toml")):
                full_path = os.path.join(root, f)
                # Normalize to forward slashes for matching
                rel_path = os.path.relpath(full_path).replace(os.sep, "/")
                if rel_path in EXCLUDED_PATHS:
                    continue
                issues = scan_file(full_path)
                all_issues.extend(issues)

    if all_issues:
        print("[FAIL] SECURITY ISSUES FOUND:")
        for issue in all_issues:
            print(f"  {issue}")
        sys.exit(1)
    else:
        print("[PASS] No hardcoded secrets detected.")
        sys.exit(0)


if __name__ == "__main__":
    main()
