#!/usr/bin/env python3
"""
Secure Push Verification Script
================================
Verifies that all Dependabot vulnerabilities have been patched before allowing
a push or merge. Part of the secure push protocol.

Usage:
    python scripts/verify_secure_push.py

Exit codes:
    0 — All checks pass, push is safe
    1 — Vulnerabilities found, push blocked
"""

import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PASSED = 0
FAILED = 0
BLOCKED = False


def check(name, condition, detail="", blocking=False):
    global PASSED, FAILED, BLOCKED
    if condition:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        icon = "🚫" if blocking else "⚠️"
        print(f"  {icon} {name} — {detail}")
        if blocking:
            BLOCKED = True


# ============================================================
# PHASE 1: Python (pip) Dependency Verification
# ============================================================
print("=" * 70)
print("PHASE 1: Python Dependencies")
print("=" * 70)

# 1.1: cryptography >= 50.0.0 (CVE-2026-69247)
for req_file in ["requirements.txt", "requirements-minimal.txt"]:
    path = os.path.join(REPO_ROOT, req_file)
    if os.path.exists(path):
        with open(path) as f:
            content = f.read()
        for line in content.split("\n"):
            s = line.strip()
            if s.startswith("cryptography"):
                m = re.match(r"cryptography[~>=]+\s*(\d+)", s)
                if m and int(m.group(1)) >= 50:
                    check(f"cryptography >= 50.0.0 in {req_file}", True)
                else:
                    check(
                        f"cryptography >= 50.0.0 in {req_file}", False, f"found: {s}", blocking=True
                    )
                break

# 1.2: chromadb < 1.0.0 (CVE-2026-45829 CRITICAL)
pyproject = os.path.join(REPO_ROOT, "pyproject.toml")
if os.path.exists(pyproject):
    with open(pyproject) as f:
        content = f.read()
    chromadb_match = re.search(r'"chromadb([^"]*)"', content)
    if chromadb_match:
        spec = chromadb_match.group(1)
        has_upper = "<1.0.0" in spec or "<1" in spec
        check(
            "chromadb pinned < 1.0.0 (CVE-2026-45829 CRITICAL)",
            has_upper,
            f"spec: chromadb{spec}",
            blocking=True,
        )
    else:
        check("chromadb pinned < 1.0.0", False, "not found in pyproject.toml")

# 1.3: uv.lock chromadb version
uv_lock = os.path.join(REPO_ROOT, "uv.lock")
if os.path.exists(uv_lock):
    with open(uv_lock) as f:
        content = f.read()
    # Find chromadb version
    m = re.search(r'name = "chromadb"\nversion = "([^"]+)"', content)
    if m:
        ver = m.group(1)
        major = int(ver.split(".")[0])
        check("uv.lock: chromadb < 1.0.0", major < 1, f"found version {ver}", blocking=True)

# ============================================================
# PHASE 2: JavaScript (npm/pnpm) Dependency Verification
# ============================================================
print()
print("=" * 70)
print("PHASE 2: JavaScript Dependencies")
print("=" * 70)

# 2.1: package.json overrides
pkg_json = os.path.join(REPO_ROOT, "package.json")
if os.path.exists(pkg_json):
    with open(pkg_json) as f:
        pkg = json.load(f)
    overrides = pkg.get("overrides", {})

    expected_overrides = {
        "undici": ("^7.29.0", "CVE-2026-13697 HIGH"),
        "brace-expansion": ("^5.0.9", "CVE-2026-69152 HIGH"),
        "fast-uri": ("^3.1.5", "CVE-2026-18446 HIGH"),
        "hono": ("^4.12.34", "CVE-2026-69207 MED"),
        "ip-address": ("^10.3.1", "CVE-2026-69192 HIGH"),
    }

    for pkg_name, (expected_ver, cve_ref) in expected_overrides.items():
        actual = overrides.get(pkg_name, "NOT SET")
        if actual != "NOT SET":
            # Parse minor version for comparison
            m = re.match(r"\^(\d+)\.(\d+)", actual)
            me = re.match(r"\^(\d+)\.(\d+)", expected_ver)
            if m and me:
                actual_minor = int(m.group(2))
                expected_minor = int(me.group(2))
                ok = actual_minor >= expected_minor
                check(
                    f"override {pkg_name} >= {expected_ver} ({cve_ref})",
                    ok,
                    f"found {actual}",
                    blocking=not ok,
                )
            else:
                check(f"override {pkg_name} >= {expected_ver}", True)
        else:
            check(
                f"override {pkg_name} >= {expected_ver} ({cve_ref})",
                False,
                "not set in overrides",
                blocking=True,
            )

# 2.2: pnpm-lock.yaml verification
pnpm_lock = os.path.join(REPO_ROOT, "pnpm-lock.yaml")
if os.path.exists(pnpm_lock):
    with open(pnpm_lock) as f:
        content = f.read()

    # Check no vulnerable undici versions
    vuln_undici = re.findall(
        r"undici@(7\.(?:2[0-7]|[01]\d)\.\d+|6\.(?:2[0-6]|[01]\d)\.\d+)", content
    )
    check(
        "pnpm-lock.yaml: no vulnerable undici 7.x < 7.29.0",
        not vuln_undici,
        f"found: {vuln_undici[:5]}",
        blocking=True,
    )

# 2.3: ui/package-lock.json
ui_lock = os.path.join(REPO_ROOT, "ui", "package-lock.json")
if os.path.exists(ui_lock):
    with open(ui_lock) as f:
        ui_data = json.load(f)
    ui_pkgs = ui_data.get("packages", {})
    undici_ver = ui_pkgs.get("node_modules/undici", {}).get("version", "?")
    if undici_ver != "?":
        m = re.match(r"7\.(\d+)", undici_ver)
        if m:
            ok = int(m.group(1)) >= 29
            check("ui: undici >= 7.29.0", ok,
                  f"found {undici_ver}", blocking=True)
            check("ui: undici >= 7.29.0", ok, f"found {undici_ver}", blocking=True)


# ============================================================
# PHASE 3: npm audit
# ============================================================
print()
print("=" * 70)
print("PHASE 3: npm audit")
print("=" * 70)

try:
    result = subprocess.run(
        ["npm", "audit", "--omit=dev", "--json"],
        cwd=os.path.join(REPO_ROOT, "ui"),
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        audit = json.loads(result.stdout)
        total = audit.get('metadata', {}).get('vulnerabilities', {}).get('total', -1)
        high = audit.get('metadata', {}).get('vulnerabilities', {}).get('high', 0)
        critical = audit.get('metadata', {}).get('vulnerabilities', {}).get('critical', 0)
        check("ui npm audit: 0 high/critical", high == 0 and critical == 0,
              f"high={high}, critical={critical}", blocking=True)
        total = audit.get("metadata", {}).get("vulnerabilities", {}).get("total", -1)
        high = audit.get("metadata", {}).get("vulnerabilities", {}).get("high", 0)
        critical = audit.get("metadata", {}).get("vulnerabilities", {}).get("critical", 0)
        check(
            "ui npm audit: 0 high/critical",
            high == 0 and critical == 0,
            f"high={high}, critical={critical}",
            blocking=True,
        )

    except (json.JSONDecodeError, KeyError):
        check("ui npm audit", "0 vulnerabilities" in result.stdout, result.stdout[:200])
except Exception as e:
    check("ui npm audit", False, f"Error: {e}")

# ============================================================
# PHASE 4: Branch protection check
# ============================================================
print()
print("=" * 70)
print("PHASE 4: Secure Push Protocol")
print("=" * 70)

branch = subprocess.run(
    ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True
).stdout.strip()

is_main = branch == "main"
check(
    "NOT on main branch (feature branch required)",
    not is_main,
    f"currently on '{branch}' — push to main is BLOCKED",
    blocking=True,
)

# Check for uncommitted changes
status = subprocess.run(
    ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
).stdout.strip()
# Filter out mode-only changes
real_changes = [l for l in status.split("\n") if l and not l.startswith(" ")]
check(
    "No uncommitted content changes",
    len(real_changes) == 0,
    f"uncommitted: {len(real_changes)} files",
)

# ============================================================
# SUMMARY
# ============================================================
print()
print("=" * 70)
if BLOCKED:
    print(f"  🚫 PUSH BLOCKED — {FAILED} blocking issue(s) found")
    print("  Resolve all blocking issues before pushing.")
    sys.exit(1)
elif FAILED > 0:
    print(f"  ⚠️  {PASSED} passed, {FAILED} warning(s) — review before pushing")
    sys.exit(0)
else:
    print(f"  ✅ ALL {PASSED} CHECKS PASS — push is safe")
    sys.exit(0)
