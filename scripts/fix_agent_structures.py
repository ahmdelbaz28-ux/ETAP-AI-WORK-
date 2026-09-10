#!/usr/bin/env python3
"""
Script to identify and fix agent structural issues.
This focuses on structural problems that could cause agents to fail.
"""

import ast
import os
import sys
from typing import List

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_agent_file_structure(filepath: str) -> List[str]:
    """Check an agent file for structural issues."""
    issues = []

    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        # Parse the file as AST
        tree = ast.parse(content)

        # Check for common issues
        for node in ast.walk(tree):
            # Check for numpy imports without proper handling
            if isinstance(node, ast.ImportFrom) and node.module == "numpy":
                issues.append(f"Direct import of numpy: {ast.unparse(node)}")
            elif isinstance(node, ast.Import) and any(
                alias.name == "numpy" for alias in node.names
            ):
                issues.append(f"Direct import of numpy: {ast.unparse(node)}")

            # Check for other problematic imports
            if isinstance(node, ast.ImportFrom) and node.module and "load_flow" in node.module:
                # This is expected, but let's make sure it's handled properly
                pass

        # Look for specific agent patterns that might be problematic
        if "import numpy as np" in content:
            # Check if there are any try/except blocks around numpy-dependent code
            lines = content.split("\n")
            numpy_import_line = -1
            for i, line in enumerate(lines):
                if "import numpy as np" in line:
                    numpy_import_line = i
                    break

            # Check if numpy is used in try/catch blocks later
            numpy_usage_found = False
            for line in lines:
                if "np." in line and not line.strip().startswith("#"):
                    numpy_usage_found = True
                    break

            if numpy_usage_found and numpy_import_line != -1:
                # Check if there's proper error handling
                # For now, just warn about the issue
                issues.append(
                    f"File {filepath} uses numpy without proper error handling in some contexts"
                )

        return issues

    except SyntaxError as e:
        issues.append(f"Syntax error in {filepath}: {str(e)}")
        return issues
    except Exception as e:
        issues.append(f"Error processing {filepath}: {str(e)}")
        return issues


def fix_prompt_handles():
    """Check and fix prompt handles to match available prompt files."""
    print("Checking agent prompt handles...")

    # Get list of available prompt files
    prompt_dir = os.path.join(os.path.dirname(__file__), "prompts")
    if not os.path.exists(prompt_dir):
        print(f"Prompt directory not found: {prompt_dir}")
        return

    prompt_files = os.listdir(prompt_dir)
    available_handles = []

    for file in prompt_files:
        if file.endswith(".yaml") or file.endswith(".prompt.yaml"):
            # Extract handle from filename
            if file.endswith(".prompt.yaml"):
                handle = file[:-12]  # Remove '.prompt.yaml'
            elif file.endswith(".yaml"):
                handle = file[:-5]  # Remove '.yaml'
            else:
                continue
            available_handles.append(handle)

    print(f"Available prompt handles: {available_handles}")

    # Check each agent file for correct prompt handles
    agent_dir = os.path.join(os.path.dirname(__file__), "agents")
    agent_files = [f for f in os.listdir(agent_dir) if f.endswith("_agent.py")]

    for agent_file in agent_files:
        filepath = os.path.join(agent_dir, agent_file)
        try:
            with open(filepath, encoding="utf-8") as f:
                content = f.read()

            # Look for prompt_handle assignments
            if "prompt_handle =" in content:
                lines = content.split("\n")
                for _i, line in enumerate(lines):
                    if "prompt_handle =" in line:
                        # Extract the handle value
                        parts = line.split("=")
                        if len(parts) > 1:
                            handle_value = parts[1].strip().strip("\"'")
                            if handle_value not in available_handles:
                                print(
                                    f"⚠️  {agent_file} has prompt_handle '{handle_value}' which is not available"
                                )
                            else:
                                print(f"✅ {agent_file} has valid prompt_handle '{handle_value}'")

        except Exception as e:
            print(f"❌ Error reading {agent_file}: {str(e)}")


def analyze_agent_issues():
    """Analyze common issues in agent files."""
    print("Analyzing agent file structures...\n")

    agent_dir = os.path.join(os.path.dirname(__file__), "agents")
    agent_files = [f for f in os.listdir(agent_dir) if f.endswith("_agent.py")]

    all_issues = {}

    for agent_file in agent_files:
        filepath = os.path.join(agent_dir, agent_file)
        print(f"Checking {agent_file}...")

        issues = check_agent_file_structure(filepath)
        if issues:
            all_issues[agent_file] = issues
            for issue in issues:
                print(f"  ❌ {issue}")
        else:
            print("  ✅ No structural issues found")
        print()

    return all_issues


def main():
    """Main function to run agent structure analysis and fixes."""
    print("Agent Structure Analysis and Fixes\n")

    # Analyze agent structures
    issues = analyze_agent_issues()

    # Check prompt handles
    print("\n" + "=" * 50)
    print("PROMPT HANDLE ANALYSIS")
    print("=" * 50)
    fix_prompt_handles()

    # Summary
    print("\nSummary:")
    print(f"- Found {len(issues)} agent files with structural issues")
    if issues:
        print("Files that need attention:")
        for agent_file, agent_issues in issues.items():
            print(f"  - {agent_file}: {len(agent_issues)} issues")

    print("\nNote: Many agents depend on numpy and other scientific libraries.")
    print("To run agents successfully, install dependencies with:")
    print("  pip install numpy scipy pandas matplotlib")

    return len(issues) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
