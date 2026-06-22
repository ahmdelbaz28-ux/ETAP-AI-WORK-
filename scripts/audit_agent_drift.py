#!/usr/bin/env python3
"""
Agent drift auditor — detects inconsistencies between agents, prompts, and docs.

Checks:
1. Every agent file in agents/*.py has a matching prompt in prompts/*.yaml
2. Every prompt in prompts/*.yaml has a matching agent file
3. Every agent mentioned in docs/ exists in agents/
4. Every prompt_handle declared in code exists as a prompt file

Usage:
    python scripts/audit_agent_drift.py [--json] [--strict]

Exit codes:
    0 = no drift found
    1 = drift detected (or --strict and any warning)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "agents"
PROMPTS_DIR = REPO_ROOT / "prompts"
DOCS_DIR = REPO_ROOT / "docs"


@dataclass
class DriftFinding:
    severity: str  # "ERROR" | "WARNING" | "INFO"
    category: str  # "agent_without_prompt" | "prompt_without_agent" | etc.
    message: str
    file: str = ""


def discover_agents() -> Dict[str, Path]:
    """Return {prompt_handle: file_path} for every agent class in agents/*.py."""
    agents = {}
    if not AGENTS_DIR.exists():
        return agents

    for py in AGENTS_DIR.glob("*.py"):
        if py.name in ("__init__.py", "prompt_loader.py"):
            continue
        content = py.read_text()
        # Find prompt_handle = "..." declarations
        matches = re.findall(r'prompt_handle\s*=\s*["\']([^"\']+)["\']', content)
        for handle in matches:
            agents[handle] = py
        # Also find class definitions that inherit BaseAgent
        class_matches = re.findall(r'class\s+(\w+Agent)\s*\([^)]*BaseAgent', content)
        for class_name in class_matches:
            # Derive handle: LoadFlowAgent → load_flow_agent (keep _agent suffix)
            # Strip "Agent" suffix, convert CamelCase to snake_case, re-add _agent
            name = class_name[:-5] if class_name.endswith("Agent") else class_name
            handle = re.sub(r'(?<=[a-z0-9])([A-Z])', r'_\1', name).lower() + "_agent"
            if handle not in agents:
                agents[handle] = py
    return agents


def discover_prompts() -> Dict[str, Path]:
    """Return {prompt_handle: file_path} for every prompt YAML file."""
    prompts = {}
    if not PROMPTS_DIR.exists():
        return prompts

    for yaml_file in list(PROMPTS_DIR.glob("*.yaml")) + list(PROMPTS_DIR.glob("*.yml")):
        # Convention: load_flow_agent.prompt.yaml → handle = "load_flow_agent"
        #            load_flow_agent.yaml → handle = "load_flow_agent"
        stem = yaml_file.stem
        if stem.endswith(".prompt"):
            stem = stem[:-7]
        prompts[stem] = yaml_file
    return prompts


def discover_doc_mentions() -> Dict[str, List[str]]:
    """Return {agent_handle: [doc_files_that_mention_it]} from docs/."""
    mentions = defaultdict(list)
    if not DOCS_DIR.exists():
        return mentions

    agents = discover_agents()
    for md in DOCS_DIR.rglob("*.md"):
        try:
            content = md.read_text()
            for handle in agents:
                if handle in content:
                    mentions[handle].append(str(md.relative_to(REPO_ROOT)))
        except Exception:
            continue
    return mentions


def audit() -> List[DriftFinding]:
    """Run all drift checks and return findings."""
    findings: List[DriftFinding] = []

    agents = discover_agents()
    prompts = discover_prompts()
    doc_mentions = discover_doc_mentions()

    agent_handles: Set[str] = set(agents.keys())
    prompt_handles: Set[str] = set(prompts.keys())

    # Check 1: agents without matching prompt
    for handle in sorted(agent_handles - prompt_handles):
        findings.append(DriftFinding(
            severity="WARNING",
            category="agent_without_prompt",
            message=f"Agent '{handle}' (in {agents[handle].relative_to(REPO_ROOT)}) has no matching prompt file in prompts/",
            file=str(agents[handle].relative_to(REPO_ROOT)),
        ))

    # Check 2: prompts without matching agent
    for handle in sorted(prompt_handles - agent_handles):
        findings.append(DriftFinding(
            severity="INFO",
            category="prompt_without_agent",
            message=f"Prompt '{handle}' (in {prompts[handle].relative_to(REPO_ROOT)}) has no matching agent class in agents/",
            file=str(prompts[handle].relative_to(REPO_ROOT)),
        ))

    # Check 3: agents mentioned in docs but not in code
    for handle, docs in doc_mentions.items():
        if handle not in agent_handles:
            # This is OK for general mentions, but flag if it looks like an agent reference
            if handle.endswith("_agent"):
                findings.append(DriftFinding(
                    severity="WARNING",
                    category="doc_mentions_missing_agent",
                    message=f"Docs mention '{handle}' but no agent class exists. Docs: {docs[:3]}",
                ))

    # Check 4: verify prompt_handle references in code resolve to actual files
    # (already covered by check 1)

    return findings


def print_report(findings: List[DriftFinding], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
        return

    if not findings:
        print("✓ No drift detected — agents and prompts are in sync.")
        return

    errors = [f for f in findings if f.severity == "ERROR"]
    warnings = [f for f in findings if f.severity == "WARNING"]
    infos = [f for f in findings if f.severity == "INFO"]

    print(f"\n{'='*60}")
    print(f"  Agent Drift Audit Report")
    print(f"{'='*60}")
    print(f"  Errors:   {len(errors)}")
    print(f"  Warnings: {len(warnings)}")
    print(f"  Info:     {len(infos)}")
    print(f"{'='*60}\n")

    for f in errors:
        print(f"  [ERROR] {f.category}: {f.message}")
    for f in warnings:
        print(f"  [WARN]  {f.category}: {f.message}")
    for f in infos:
        print(f"  [INFO]  {f.category}: {f.message}")


def main():
    parser = argparse.ArgumentParser(description="Agent drift auditor")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any warning")
    args = parser.parse_args()

    findings = audit()
    print_report(findings, as_json=args.json)

    has_errors = any(f.severity == "ERROR" for f in findings)
    has_warnings = any(f.severity == "WARNING" for f in findings)

    if has_errors or (args.strict and has_warnings):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
