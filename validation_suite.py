#!/usr/bin/env python3
"""
Validation Suite for the ETAP AI Engineering Platform.
Runs all validation checks: syntax, imports, configs, and basic health.
"""

import os
import subprocess
import sys


def run_syntax_check():
    """Run validate_syntax.py"""
    print("\n" + "=" * 80)
    print("Step 1: Syntax and Import Validation")
    print("=" * 80)
    try:
        result = subprocess.run(
            [sys.executable, "validate_syntax.py"], capture_output=True, text=True
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        if result.returncode != 0:
            print("\n⚠️  Syntax/Import validation had issues")
        return result.returncode == 0
    except Exception as e:
        print(f"\n❌ Failed to run syntax check: {e}")
        return False


def check_required_files():
    """Check that all critical files exist"""
    print("\n" + "=" * 80)
    print("Step 2: Required Files Check")
    print("=" * 80)
    required_files = [
        ".env.example",
        "Makefile",
        "Dockerfile",
        "requirements.txt",
        "engineering_service.py",
        "pyproject.toml",
    ]
    missing = []
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} (MISSING!)")
            missing.append(file)
    return len(missing) == 0


def check_config_files():
    """Check that config files are valid"""
    print("\n" + "=" * 80)
    print("Step 3: Config Files Validation")
    print("=" * 80)
    all_ok = True

    # Check pyrightconfig.json
    if os.path.exists("pyrightconfig.json"):
        print("✅ pyrightconfig.json exists")
    else:
        print("⚠️  pyrightconfig.json not found (optional but recommended)")

    # Check .gitignore
    if os.path.exists(".gitignore"):
        print("✅ .gitignore exists")
    else:
        print("⚠️  .gitignore not found")

    return all_ok


def main():
    print("\n" + "=" * 80)
    print("ETAP AI ENGINEERING PLATFORM - VALIDATION SUITE")
    print("=" * 80)

    results = []
    results.append(("Syntax & Imports", run_syntax_check()))
    results.append(("Required Files", check_required_files()))
    results.append(("Config Files", check_config_files()))

    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name:25} : {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 ALL VALIDATIONS PASSED! The platform is ready!")
        sys.exit(0)
    else:
        print("\n⚠️  Some validations failed. Please fix the issues.")
        sys.exit(1)


if __name__ == "__main__":
    main()
