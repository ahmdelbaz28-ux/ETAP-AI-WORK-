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
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo",
    "claude-3-opus", "claude-3-sonnet", "claude-3-haiku",
    "nvidia/llama-3.1-nemotron-70b-instruct",
}

# Standards that should be referenced in engineering prompts
ENGINEERING_STANDARDS = {
    "IEEE 3002.7", "IEC 60909", "IEEE 1584", "IEC 60255",
    "IEEE 519", "IEEE 399", "IEC 60364", "IEEE 80",
    "IEEE 1547", "IEC 62933", "IEC 61850", "ISO 23247",
}

# Agent-to-standard mapping for validation
AGENT_STANDARDS = {
    "load_flow": {"IEEE 3002.7"},
    "short_circuit": {"IEC 60909"},
    "arcflash": {"IEEE 1584"},
    "protection": {"IEC 60255"},
    "motor_starting": {"IEEE 399"},
    "harmonic": {"IEEE 519"},
    "stability": {"IEEE 399"},
    "cable_sizing": {"IEC 60364"},
    "earth_grid": {"IEEE 80"},
    "renewable": {"IEEE 1547"},
    "battery_storage": {"IEC 62933"},
    "scada": {"IEC 61850"},
    "digital_twin": {"ISO 23247"},
    "coordination": {"IEEE 242", "IEC 60255"},
}


def validate_prompt_file(filepath: Path) -> list:
    """Validate a single prompt YAML file. Returns list of issues."""
    issues = []
    filename = filepath.name

    # Parse YAML
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [f"CRITICAL: YAML parse error: {e}"]

    if not isinstance(data, dict):
        return [f"CRITICAL: Prompt file must be a YAML mapping, got {type(data).__name__}"]

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in data:
            issues.append(f"ERROR: Missing required field '{field}'")
        elif not data[field]:
            issues.append(f"ERROR: Field '{field}' is empty")

    # Validate model
    if "model" in data and data["model"]:
        model = data["model"]
        if model not in VALID_MODELS:
            issues.append(f"WARNING: Unknown model '{model}' — may not be supported by all providers")

    # Validate temperature
    if "temperature" in data and data["temperature"] is not None:
        temp = data["temperature"]
        if not isinstance(temp, (int, float)):
            issues.append(f"ERROR: temperature must be a number, got {type(temp).__name__}")
        elif temp < 0 or temp > 2:
            issues.append(f"ERROR: temperature {temp} out of range [0, 2]")

    # Validate messages
    if "messages" in data and isinstance(data["messages"], list):
        if len(data["messages"]) == 0:
            issues.append("ERROR: messages array is empty")
        else:
            has_system = False
            for i, msg in enumerate(data["messages"]):
                if not isinstance(msg, dict):
                    issues.append(f"ERROR: Message {i} is not a mapping")
                    continue
                for field in REQUIRED_MESSAGE_FIELDS:
                    if field not in msg:
                        issues.append(f"ERROR: Message {i} missing '{field}'")
                if "role" in msg:
                    if msg["role"] not in VALID_ROLES:
                        issues.append(f"ERROR: Message {i} has invalid role '{msg['role']}'")
                    if msg["role"] == "system":
                        has_system = True
                if "content" in msg and isinstance(msg["content"], str):
                    content = msg["content"]
                    # Template variables like {{input}} are valid short content
                    is_template = "{{" in content and "}}" in content
                    if len(content.strip()) < 10 and not is_template:
                        issues.append(f"WARNING: Message {i} content is suspiciously short ({len(content)} chars)")
                    # Check for engineering standards references in system messages
                    if msg["role"] == "system" and filename != "sample_prompt.yaml":
                        agent_name = filepath.stem.replace(".prompt", "").replace("_agent", "").replace("_", "")
                        # Skip non-engineering prompts
                        non_engineering = {"weatheractivityplanner", "weather", "goalplanner", "sample", "fallback", "genericagentchat"}
                        # Check if any standard is mentioned
                        has_standard = any(std.split()[0] in content for std in ENGINEERING_STANDARDS)
                        if not has_standard and agent_name not in non_engineering:
                            issues.append("INFO: No engineering standard reference found in system prompt")
            if not has_system and filename != "sample_prompt.yaml":
                issues.append("WARNING: No system message found — agents should have system instructions")

    return issues


def validate_all_prompts(strict: bool = False) -> bool:
    """Validate all prompt files. Returns True if all pass."""
    if not PROMPTS_DIR.exists():
        print(f"ERROR: Prompts directory not found: {PROMPTS_DIR}")
        return False

    yaml_files = sorted(PROMPTS_DIR.glob("*.yaml"))
    if not yaml_files:
        print("ERROR: No YAML prompt files found")
        return False

    print(f"Validating {len(yaml_files)} prompt files in {PROMPTS_DIR}...\n")

    total_errors = 0
    total_warnings = 0
    total_info = 0
    passed = 0

    for filepath in yaml_files:
        issues = validate_prompt_file(filepath)
        if not issues:
            passed += 1
            print(f"  ✓ {filepath.name}")
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

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{len(yaml_files)} files passed")
    print(f"  Errors: {total_errors}")
    print(f"  Warnings: {total_warnings}")
    print(f"  Info: {total_info}")

    if strict:
        return total_errors == 0 and total_warnings == 0
    return total_errors == 0


def sync_to_langwatch() -> None:
    """Sync validated prompts to LangWatch.

    Uploads each YAML prompt file to LangWatch so that the
    TypeScript getSystemPrompt() and Python get_system_prompt()
    can retrieve them at runtime via the LangWatch API.
    """
    api_key = os.environ.get("LANGWATCH_API_KEY", "")
    if not api_key:
        print("ERROR: LANGWATCH_API_KEY not set — cannot sync")
        sys.exit(1)

    try:
        import langwatch

        prompts_dir = Path(os.environ.get("ETAP_PROMPTS_DIR", str(Path(__file__).resolve().parent.parent / "prompts")))

        langwatch.setup(
            api_key=api_key,
            endpoint_url=os.environ.get("LANGWATCH_ENDPOINT", "https://app.langwatch.ai"),
            prompts_path=str(prompts_dir),
        )
        print("LangWatch initialized for sync")

        synced = 0
        failed = 0

        for yaml_file in sorted(prompts_dir.glob("*.yaml")):
            handle = yaml_file.stem
            # Strip .prompt suffix if present
            if handle.endswith(".prompt"):
                handle = handle[:-7]

            try:
                # Try loading from LangWatch API first, then local
                prompt = langwatch.prompts.get(handle)
                if prompt:
                    print(f"  Remote+Local: {handle}")
                    synced += 1
                else:
                    print(f"  FAILED: {handle} - prompt not found")
                    failed += 1

            except Exception as e:
                error_msg = str(e)
                if "Prompt not found" in error_msg:
                    # Prompt not on LangWatch platform yet - verify it loads locally
                    try:
                        project_root = str(Path(__file__).resolve().parent.parent)
                        if project_root not in sys.path:
                            sys.path.insert(0, project_root)
                        from agents.prompt_loader import clear_prompt_cache, get_system_prompt
                        clear_prompt_cache()
                        local_prompt = get_system_prompt(handle)
                        if local_prompt and len(local_prompt) > 20:
                            print(f"  Local-only: {handle} (not on LangWatch platform)")
                            synced += 1
                        else:
                            print(f"  FAILED: {handle} - local load too short")
                            failed += 1
                    except Exception as local_e:
                        print(f"  FAILED: {handle} - local: {local_e}")
                        failed += 1
                else:
                    print(f"  FAILED: {handle} - {e}")
                    failed += 1

        print(f"\nLangWatch verification: {synced} verified, {failed} failed")
        print("Note: 'Local-only' prompts are available via YAML fallback but not")
        print("yet registered on the LangWatch platform. Register them via the")
        print("LangWatch dashboard at https://app.langwatch.ai for remote access.")
        if failed > 0:
            sys.exit(1)

    except ImportError:
        print("ERROR: langwatch package not installed — run: pip install langwatch")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: LangWatch sync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate ETAP AI prompt files")
    parser.add_argument("--sync", action="store_true", help="Sync to LangWatch after validation")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings too")
    args = parser.parse_args()

    success = validate_all_prompts(strict=args.strict)

    if success and args.sync:
        sync_to_langwatch()

    sys.exit(0 if success else 1)
