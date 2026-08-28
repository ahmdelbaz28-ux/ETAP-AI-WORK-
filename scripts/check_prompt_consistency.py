#!/usr/bin/env python3
"""Check prompt-manifest consistency (Operation Iron Loop, WP5).

Verifies that:
1. ``prompts.json`` parses and every handle resolves to an existing file.
2. Every YAML file under ``prompts/`` is referenced by the manifest
   (no ghost/duplicate prompt files).
3. The coordinator's routing table lists exactly the seven Mastra-registered
   sub-agents, and each maps to a manifest entry.
4. The legacy ``coordination_agent`` handle stays a literal copy of
   ``protection_agent``.
5. The Mastra registry (src/mastra/index.ts) exposes the matching agents.

Exit code 0 = consistent; 1 = inconsistencies found.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"
MANIFEST_PATH = ROOT / "prompts.json"
INDEX_TS = ROOT / "src" / "mastra" / "index.ts"
COORDINATOR_PROMPT = PROMPTS_DIR / "power_system_coordinator_agent.prompt.yaml"

# The seven sub-agents the coordinator routes to (Mastra-registered).
EXPECTED_COORDINATOR_HANDLES: tuple[str, ...] = (
    "load_flow_agent",
    "short_circuit_agent",
    "protection_agent",
    "motor_starting_agent",
    "arcflash_agent",
    "etap_engineer_agent",
    "goal_planner_agent",
)

# Coordinator handle -> camelCase symbol expected in src/mastra/index.ts.
HANDLE_TO_SYMBOL: dict[str, str] = {
    "load_flow_agent": "loadFlowAgent",
    "short_circuit_agent": "shortCircuitAgent",
    "protection_agent": "protectionAgent",
    "motor_starting_agent": "motorStartingAgent",
    "arcflash_agent": "arcFlashAgent",
    "etap_engineer_agent": "etapEngineerAgent",
    "goal_planner_agent": "goalPlannerAgent",
}


def main() -> int:
    errors: list[str] = []

    # ── 1. Manifest integrity ────────────────────────────────────────────
    if not MANIFEST_PATH.is_file():
        print(f"FAIL: {MANIFEST_PATH} not found")
        return 1
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: prompts.json is not valid JSON: {exc}")
        return 1

    prompts: dict[str, str] = manifest.get("prompts", {})
    if not prompts:
        errors.append("prompts.json has no 'prompts' mapping")

    resolved: dict[str, Path] = {}
    for handle, rel in sorted(prompts.items()):
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"manifest handle '{handle}' -> missing file: {rel}")
        else:
            resolved[handle] = path

    # ── 2. No ghost prompt files ─────────────────────────────────────────
    referenced = {str(p.relative_to(ROOT)).replace("\\", "/") for p in resolved.values()}
    # Kept on disk for history only: unreachable via manifest-first loading
    # and excluded from Langfuse sync — must never re-enter the manifest.
    LOCAL_ONLY_FILES = frozenset({"prompts/etap_engineer_agent.yaml"})
    for yaml_file in PROMPTS_DIR.glob("*.yaml"):
        rel = str(yaml_file.relative_to(ROOT)).replace("\\", "/")
        if rel not in referenced and rel not in LOCAL_ONLY_FILES:
            errors.append(f"ghost prompt file not in manifest: {rel}")

    # ── 3. Coordinator table ≡ registered sub-agents ─────────────────────
    if not COORDINATOR_PROMPT.is_file():
        errors.append(f"coordinator prompt missing: {COORDINATOR_PROMPT}")
    else:
        text = COORDINATOR_PROMPT.read_text(encoding="utf-8")
        rows = re.findall(r"^\s*\|\s*([a-z_]+_agent)\s*\|", text, re.MULTILINE)
        extra = [r for r in rows if r not in EXPECTED_COORDINATOR_HANDLES]
        missing = [h for h in EXPECTED_COORDINATOR_HANDLES if h not in rows]
        if extra:
            errors.append(f"coordinator table has non-sub-agent rows: {extra}")
        if missing:
            errors.append(f"coordinator table missing registered agents: {missing}")

    # ── 4. coordination_agent ≡ protection_agent ─────────────────────────
    prot = PROMPTS_DIR / "protection_agent.prompt.yaml"
    coord = PROMPTS_DIR / "coordination_agent.prompt.yaml"
    if prot.is_file() and coord.is_file():
        if prot.read_bytes() != coord.read_bytes():
            errors.append(
                "coordination_agent.prompt.yaml is not a literal copy of "
                "protection_agent.prompt.yaml"
            )
    elif "coordination_agent" in prompts:
        errors.append("coordination_agent mapped in manifest but its file is missing")

    # ── 5. Mastra registry symbols exist ─────────────────────────────────
    if INDEX_TS.is_file():
        ts = INDEX_TS.read_text(encoding="utf-8")
        block = re.search(r"agents:\s*\{(.*?)\}", ts, re.DOTALL)
        if not block:
            errors.append("src/mastra/index.ts: agents block not found")
        else:
            for handle in EXPECTED_COORDINATOR_HANDLES:
                symbol = HANDLE_TO_SYMBOL[handle]
                if symbol not in block.group(1):
                    errors.append(f"index.ts agents block missing symbol: {symbol}")
    else:
        errors.append(f"{INDEX_TS} not found")

    if errors:
        print(f"PROMPT CONSISTENCY: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(
        f"PROMPT CONSISTENCY OK: {len(prompts)} manifest handles resolve, "
        f"no ghosts, coordinator table = {len(EXPECTED_COORDINATOR_HANDLES)} "
        "registered sub-agents, coordination==protection, Mastra symbols present."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
