#!/usr/bin/env python3
"""
Security scanner to detect hardcoded secrets before commit.
Run: python scripts/security_scan.py
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


def scan_file(filepath):
    issues = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            for i, line in enumerate(content.split("\n"), 1):
                for pattern, desc in SECRET_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        if any(x in line for x in ["os.environ", "getenv", "get("]):
                            continue
                        if "example" in line.lower() or "placeholder" in line.lower():
                            continue
                        issues.append(f"{filepath}:{i} | {desc}: {line.strip()[:60]}")
    except:
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
                issues = scan_file(os.path.join(root, f))
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
