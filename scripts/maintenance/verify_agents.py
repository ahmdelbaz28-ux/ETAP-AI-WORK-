from __future__ import annotations

#!/usr/bin/env python3
"""
Verification script to check that agents have proper structure and implementations.
This runs static analysis to verify agents are correctly implemented.
"""

import ast
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _check_inherits_base(agent_class: ast.ClassDef) -> list[str]:
    """Check if an agent class inherits from BaseAgent."""
    for base in agent_class.bases:
        is_base = (
            isinstance(base, ast.Name) and base.id == "BaseAgent"
            or isinstance(base, ast.Attribute) and base.attr == "BaseAgent"
        )
        if is_base:
            return []
    return [f"Class {agent_class.name} doesn't inherit from BaseAgent"]


def _check_prompt_handle(agent_class: ast.ClassDef) -> list[str]:
    """Check if an agent class has a prompt_handle assignment."""
    for item in agent_class.body:
        if isinstance(item, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "prompt_handle" for t in item.targets):
                return []
        elif (
            isinstance(item, ast.AnnAssign)
            and isinstance(item.target, ast.Name)
            and item.target.id == "prompt_handle"
        ):
            return []
    return [f"Class {agent_class.name} doesn't have prompt_handle attribute"]


def _check_required_methods(agent_class: ast.ClassDef) -> list[str]:
    """Check if an agent class has __init__ and execute methods."""
    methods = {
        item.name
        for item in agent_class.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    issues = []
    if "__init__" not in methods:
        issues.append(f"Class {agent_class.name} doesn't have __init__ method")
    if "execute" not in methods:
        issues.append(f"Class {agent_class.name} doesn't have execute method")
    return issues


def _check_agent_class(agent_class: ast.ClassDef, filepath: str) -> list[str]:
    """Run all checks on a single agent class."""
    issues = []
    issues.extend(_check_inherits_base(agent_class))
    issues.extend(_check_prompt_handle(agent_class))
    issues.extend(_check_required_methods(agent_class))
    return issues


def check_agent_class_structure(filepath: str) -> list[str]:
    """Check if an agent file has a properly structured agent class."""
    issues = []

    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        # Find all class definitions that end with 'Agent'
        agent_classes = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name.endswith("Agent")
        ]

        if not agent_classes:
            issues.append(f"No class ending with 'Agent' found in {filepath}")
            return issues

        for agent_class in agent_classes:
            issues.extend(_check_agent_class(agent_class, filepath))

    except SyntaxError as e:
        issues.append(f"Syntax error in {filepath}: {str(e)}")
    except Exception as e:
        issues.append(f"Error processing {filepath}: {str(e)}")

    return issues


def verify_all_agents():
    """Verify all agent files have proper structure."""
    print("Verifying agent file structures...\n")

    agent_dir = os.path.join(os.path.dirname(__file__), "agents")
    agent_files = [f for f in os.listdir(agent_dir) if f.endswith("_agent.py")]

    all_issues = {}

    for agent_file in agent_files:
        filepath = os.path.join(agent_dir, agent_file)
        print(f"Verifying {agent_file}...")

        issues = check_agent_class_structure(filepath)
        if issues:
            all_issues[agent_file] = issues
            for issue in issues:
                print(f"  [FAIL] {issue}")
        else:
            print("  [OK] Structure OK")
        print()

    return all_issues


def verify_orchestrator_agents():
    """Verify that the orchestrator properly registers all agents."""
    print("Verifying orchestrator agent registration...\n")

    orchestrator_file = os.path.join(os.path.dirname(__file__), "agents", "orchestrator.py")

    issues = []

    try:
        with open(orchestrator_file, encoding="utf-8") as f:
            content = f.read()

        # Check for the main agent classes
        required_agents = [
            "LoadFlowAgent",
            "ShortCircuitAgent",
            "HarmonicAnalysisAgent",
            "OptimalPowerFlowAgent",
            "ProtectionCoordinationAgent",
            "ETAPExecutionAgent",
            "ValidationAgent",
            "ReportGenerationAgent",
        ]

        for agent in required_agents:
            if f"class {agent}" not in content:
                issues.append(f"Required agent class {agent} not found in orchestrator.py")
            else:
                print(f"[OK] {agent} found in orchestrator")

        # Check for ALL_AGENT_CLASSES list in agents/__init__.py
        init_file = os.path.join(os.path.dirname(__file__), "agents", "__init__.py")
        try:
            with open(init_file, encoding="utf-8") as f_init:
                init_content = f_init.read()

            if "ALL_AGENT_CLASSES" not in init_content:
                issues.append("ALL_AGENT_CLASSES not found in agents/__init__.py")
            else:
                print("[OK] ALL_AGENT_CLASSES found in agents/__init__.py")

            # Check for STUDY_TYPE_AGENT_MAP
            if "STUDY_TYPE_AGENT_MAP" not in init_content:
                issues.append("STUDY_TYPE_AGENT_MAP not found in agents/__init__.py")
            else:
                print("[OK] STUDY_TYPE_AGENT_MAP found in agents/__init__.py")
        except Exception as e:
            issues.append(f"Error reading agents/__init__.py: {str(e)}")

    except Exception as e:
        issues.append(f"Error reading orchestrator.py: {str(e)}")

    if issues:
        for issue in issues:
            print(f"[FAIL] {issue}")
    else:
        print("[OK] All orchestrator checks passed")

    return issues


def main():
    """Main verification function."""
    print("Agent Verification Script")
    print("=" * 50)

    # Verify individual agent structures
    agent_issues = verify_all_agents()

    # Verify orchestrator
    print("=" * 50)
    orchestrator_issues = verify_orchestrator_agents()

    # Summary
    print("\n" + "=" * 50)
    print("VERIFICATION SUMMARY")
    print("=" * 50)

    total_agent_issues = sum(len(issues) for issues in agent_issues.values())
    print(f"Agent structure issues: {total_agent_issues}")

    print(f"Orchestrator issues: {len(orchestrator_issues)}")

    all_issues = total_agent_issues + len(orchestrator_issues)

    if all_issues == 0:
        print("\n[SUCCESS] All agents verified successfully!")
        print("\nNote: Actual execution requires dependencies like numpy, scipy, etc.")
        print("Install with: pip install numpy scipy pandas matplotlib")
        return True
    else:
        print(f"\n[WARN] Found {all_issues} issues that need to be addressed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
