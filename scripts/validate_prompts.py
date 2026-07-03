#!/usr/bin/env python3
"""LangWatch Prompt Validation Script.

Validates all YAML prompt files in the prompts/ directory and optionally
syncs them to LangWatch for remote prompt management.

Usage:
    python3 scripts/validate_prompts.py [--sync] [--strict]

Options:
    --sync    Push validated prompts to LangWatch
    --strict  Fail on warnings (not just errors)
"""

import os
import sys
from pathlib import Path

import yaml

# Project root
ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"

# Required fields in each prompt YAML
REQUIRED_FIELDS = ["model", "temperature", "messages"]
REQUIRED_MESSAGE_FIELDS = ["role", "content"]

# Valid roles
VALID_ROLES = {"system", "user", "assistant"}

# Valid model names
VALID_MODELS = {
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
    "claude-3-opus",
    "claude-3-sonnet",
    "claude-3-haiku",
    "nvidia/llama-3.1-nemotron-70b-instruct",
}

# Standards that should be referenced in engineering prompts
ENGINEERING_STANDARDS = {
    "IEEE 3002.7",
    "IEC 60909",
    "IEEE 1584",
    "IEC 60255",
    "IEEE C37",
    "NEC Article 250",
    "IEEE 519",
    "IEC 61000",
    "IEEE 1547",
    "IEC 61400",
    "IEC 61850",
    "IEEE 693",
    "IEC 60076",
    "IEEE 1110",
    "IEEE 1159",
    "IEC 60364",
    "IEC 62305",
    "IEEE 739",
    "IEEE 141",
    "IEEE 242",
    "IEEE 399",
    "IEEE 446",
    "IEC 62271",
    "IEC 60529",
    "IEEE 738",
    "IEC 60287",
    "IEEE 80",
    "IEEE 81",
    "IEEE 142",
    "IEEE 1100",
    "IEEE 493",
    "IEC 60034",
    "IEEE 841",
    "NEMA MG-1",
    "IEC 60038",
}


def validate_prompt_file(filepath: Path, _strict: bool = False) -> tuple[bool, list[str]]:
    """
    Validate a single YAML prompt file.

    Returns (passed, list_of_issues).
    """
    issues: list[str] = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        return False, [f"CRITICAL: Cannot read file: {e}"]

    # Check non-empty
    if not content.strip():
        issues.append("CRITICAL: File is empty")

    # Parse YAML
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as e:
        issues.append(f"CRITICAL: YAML parse error: {e}")
        return False, issues

    if not isinstance(parsed, dict):
        issues.append("CRITICAL: Root element must be a dictionary")
        return False, issues

    # Check required top-level fields
    for field in REQUIRED_FIELDS:
        if field not in parsed:
            issues.append(f"ERROR: Missing required field '{field}'")

    # Validate model name if present
    model = parsed.get("model", "")
    if model and model not in VALID_MODELS:
        issues.append(
            f"WARNING: Model '{model}' not in known valid list ({', '.join(sorted(VALID_MODELS))})",
        )

    # Validate temperature range if present
    temp = parsed.get("temperature")
    if temp is not None:
        try:
            t = float(temp)
            if t < 0.0 or t > 2.0:
                issues.append(f"WARNING: Temperature {t} outside typical range [0.0, 2.0]")
        except (ValueError, TypeError):
            issues.append(f"WARNING: Temperature '{temp}' is not a valid number")

    # Validate messages
    messages = parsed.get("messages", [])
    if not isinstance(messages, list):
        issues.append("ERROR: 'messages' must be a list")
    else:
        has_system = False
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                issues.append(f"ERROR: Message at index {i} is not a dictionary")
                continue
            for field in REQUIRED_MESSAGE_FIELDS:
                if field not in msg:
                    issues.append(f"ERROR: Message at index {i} missing required field '{field}'")
            role = msg.get("role", "")
            if role not in VALID_ROLES:
                issues.append(f"WARNING: Message at index {i} has unknown role '{role}'")
            if role == "system":
                has_system = True
        if not has_system:
            issues.append(
                "WARNING: No system message found — agents should have system instructions",
            )

    # Check for engineering standards references in system messages
    if has_system:
        found_standards = set()
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "system":
                content_str = str(msg.get("content", ""))
                for std in ENGINEERING_STANDARDS:
                    if std.lower() in content_str.lower():
                        found_standards.add(std)
        if not found_standards and filepath.name != "sample_prompt.yaml":
            issues.append("INFO: No engineering standard reference found in system prompt")

    # Check for excessive token length (rough estimate)
    total_chars = len(content)
    if total_chars > 10000:
        issues.append(f"INFO: Large prompt ({total_chars} chars, ~{total_chars // 4} tokens)")

    return len(
        [i for i in issues if i.startswith("CRITICAL:") or i.startswith("ERROR:")],
    ) == 0, issues


def validate_all_prompts(strict: bool = False) -> bool:
    """Validate all YAML prompt files in the prompts directory."""
    yaml_files = sorted(PROMPTS_DIR.glob("*.yaml"))
    if not yaml_files:
        print(f"ERROR: No prompt files found in {PROMPTS_DIR}")
        return False

    print(f"Validating {len(yaml_files)} prompt files in {PROMPTS_DIR}...\n")

    passed = 0
    total_errors = 0
    total_warnings = 0
    total_info = 0

    for filepath in yaml_files:
        success, issues = validate_prompt_file(filepath, strict=strict)

        if success and not issues:
            print(f"  ✓ {filepath.name}")
            passed += 1
        else:
            print(f"  ✗ {filepath.name}")
            for issue in issues:
                prefix = "    "
                if issue.startswith("CRITICAL:") or issue.startswith("ERROR:"):
                    total_errors += 1
                    print(f"{prefix}❌ {issue}")
                elif issue.startswith("WARNING:"):
                    total_warnings += 1
                    print(f"{prefix}⚠️  {issue}")
                elif issue.startswith("INFO:"):
                    total_info += 1
                    print(f"{prefix}ℹ️  {issue}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{len(yaml_files)} files passed")
    print(f"  Errors: {total_errors}")
    print(f"  Warnings: {total_warnings}")
    print(f"  Info: {total_info}")

    if strict:
        return total_errors == 0 and total_warnings == 0
    return total_errors == 0


def sync_to_langwatch() -> None:
    """Delegate to the standalone sync_to_langwatch.py script."""
    sync_script = Path(__file__).resolve().parent / "sync_to_langwatch.py"
    if not sync_script.is_file():
        print("ERROR: sync_to_langwatch.py not found alongside validate_prompts.py")
        sys.exit(1)

    import subprocess

    result = subprocess.run(
        [sys.executable, str(sync_script)],
        env={**os.environ},
        capture_output=False,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate AhmedETAP prompt files")
    parser.add_argument("--sync", action="store_true", help="Sync to LangWatch after validation")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings too")
    args = parser.parse_args()

    success = validate_all_prompts(strict=args.strict)

    if success and args.sync:
        sync_to_langwatch()

    sys.exit(0 if success else 1)
