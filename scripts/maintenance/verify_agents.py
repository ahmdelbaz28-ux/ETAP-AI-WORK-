#!/usr/bin/env python3
"""
scripts/maintenance/verify_agents.py — Authoritative Agent Registry & Handler Verification (M1.6).

Verifies at startup and in Meta-CI:
1. All canonical agents in agents.registry are dynamically importable and constructible.
2. Every agent inherits from BaseAgent.
3. Every agent exposes a valid prompt_handle matching prompts.json.
4. Every agent implements required interfaces (__init__, execute).
5. Provides fail-fast execution wired into core/bootstrap.py lifespan.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("agents.verify")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def verify_agent_registry(fail_loudly: bool = False) -> bool:
    """Dynamically import and verify all registered agents and handlers (M1.6 fail-fast).

    Parameters
    ----------
    fail_loudly : bool
        If True, raises RuntimeError immediately upon encountering any invariant violation.

    Returns
    -------
    bool
        True if all agents are verified, False otherwise.
    """
    errors: list[str] = []

    # 1. Load prompts.json handles
    prompts_path = REPO_ROOT / "prompts.json"
    known_prompt_handles: set[str] = set()
    if prompts_path.exists():
        try:
            with open(prompts_path, encoding="utf-8") as pf:
                pdata = json.load(pf)
                known_prompt_handles = set(pdata.get("prompts", {}).keys())
        except Exception as exc:
            errors.append(f"Failed to parse prompts.json: {exc}")
    else:
        errors.append(f"prompts.json not found at {prompts_path}")

    # 2. Verify BaseAgent import
    try:
        from agents.base import BaseAgent
    except Exception as exc:
        msg = f"Cannot import BaseAgent: {exc}"
        if fail_loudly:
            raise RuntimeError(msg) from exc
        errors.append(msg)
        return False

    # 3. Import canonical agent registry
    try:
        from agents.registry import create_agent_registry, get_study_type_mapping
        study_map = get_study_type_mapping()
        agents = create_agent_registry()
    except Exception as exc:
        msg = f"Cannot load agent registry: {exc}"
        if fail_loudly:
            raise RuntimeError(msg) from exc
        errors.append(msg)
        return False

    # 4. Dynamically verify each registered agent instance
    for agent_key, ag in sorted(agents.items()):
        cls = ag.__class__

        # Verify inheritance
        if not isinstance(ag, BaseAgent):
            errors.append(f"Agent '{agent_key}' ({cls.__name__}) does not inherit from BaseAgent")

        # Verify prompt_handle attribute
        ph = getattr(ag, "prompt_handle", None)
        if not ph or not isinstance(ph, str):
            errors.append(f"Agent '{agent_key}' ({cls.__name__}) missing valid prompt_handle")
        elif known_prompt_handles and ph not in known_prompt_handles:
            errors.append(f"Agent '{agent_key}' ({cls.__name__}) prompt_handle '{ph}' not in prompts.json")

        # Verify required methods
        if not callable(getattr(ag, "execute", None)):
            errors.append(f"Agent '{agent_key}' ({cls.__name__}) does not implement callable 'execute'")

    # 5. Check study_type_mapping coverage
    for study_val, target_agent_key in sorted(study_map.items()):
        if target_agent_key not in agents:
            errors.append(f"Study mapping '{study_val}' targets unregistered agent key '{target_agent_key}'")

    if errors:
        for err in errors:
            logger.error("[FAIL] %s", err)
            sys.stderr.write(f"  ❌ {err}\n")
        if fail_loudly:
            raise RuntimeError(f"M1.6 Agent Registry Verification FAILED with {len(errors)} error(s):\n" + "\n".join(errors))
        return False

    return True


def main() -> int:
    """CLI runner for verify_agents script."""
    print("=" * 60)
    print("AhmedETAP M1.6 Agent Registry Dynamic Verification")
    print("=" * 60)

    try:
        success = verify_agent_registry(fail_loudly=False)
        if success:
            print("\n[SUCCESS] All agents and handlers dynamically verified against canonical registry.")
            return 0
        else:
            print("\n[BLOCKED] Agent registry verification failed.")
            return 1
    except Exception as exc:
        print(f"\n[FATAL] Verification exception: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
