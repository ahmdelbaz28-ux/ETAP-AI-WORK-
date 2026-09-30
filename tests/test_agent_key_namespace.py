"""M4.2 — Canonical agent-key namespace + prompt-handle sync tests.

Proves:
  1. The live registry is exactly CANONICAL_AGENT_KEYS ∪ AGENT_KEY_ALIASES.
  2. validate_agent_keys() fails fast on smuggled keys and missing mandatory keys.
  3. Aliases never collide with canonical keys and always target canonical keys.
  4. predictive/anomaly are context-bound — never StudyType members (M4.4 guard).
  5. Every Python ``prompt_handle`` and TS ``promptHandle`` resolves inside
     ``prompts.json`` (single cross-boundary contract, extension-not-replacement).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from agents.registry import (
    AGENT_KEY_ALIASES,
    CANONICAL_AGENT_KEYS,
    CONTEXT_BOUND_AGENT_KEYS,
    MANDATORY_AGENT_KEYS,
    all_registered_keys,
    create_agent_registry,
    resolve_agent_key,
    validate_agent_keys,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# ── 1. Namespace shape ───────────────────────────────────────────────────────

def test_canonical_and_alias_counts():
    """Live fact: 27 canonical + 3 aliases = 30 registered keys."""
    assert len(CANONICAL_AGENT_KEYS) == 27
    assert len(AGENT_KEY_ALIASES) == 3
    assert len(all_registered_keys()) == 30
    assert len(MANDATORY_AGENT_KEYS) == 8


def test_live_registry_matches_canonical_namespace():
    agents = create_agent_registry()
    assert set(agents) == all_registered_keys()
    assert validate_agent_keys(agents) == []


def test_aliases_disjoint_from_canonical_and_resolve():
    assert not (set(AGENT_KEY_ALIASES) & CANONICAL_AGENT_KEYS), (
        "alias names must not collide with canonical keys"
    )
    for alias, target in AGENT_KEY_ALIASES.items():
        assert target in CANONICAL_AGENT_KEYS, f"{alias} -> {target} not canonical"
        assert resolve_agent_key(alias) == target
    assert resolve_agent_key("load_flow") == "load_flow"


# ── 2. Fail-fast validation ──────────────────────────────────────────────────

def test_smuggled_key_is_detected():
    agents = create_agent_registry()
    problems = validate_agent_keys(dict(agents, evil_agent=None))
    assert problems, "an unregistered key must be reported"
    assert "evil_agent" in problems[0]


def test_missing_mandatory_key_is_detected():
    agents = create_agent_registry()
    agents.pop("load_flow")
    problems = validate_agent_keys(agents)
    assert any("load_flow" in p for p in problems)


def test_registry_construction_fails_fast_on_corruption(monkeypatch):
    """A namespace violation must raise at construction, not at dispatch."""
    import agents.registry as registry_mod

    real_validate = registry_mod.validate_agent_keys
    monkeypatch.setattr(
        registry_mod,
        "validate_agent_keys",
        lambda keys, **kw: ["injected namespace violation"],
    )
    try:
        try:
            registry_mod.create_agent_registry()
        except registry_mod.AgentRegistryError as exc:
            assert "injected namespace violation" in str(exc)
        else:
            raise AssertionError("AgentRegistryError not raised")
    finally:
        monkeypatch.setattr(registry_mod, "validate_agent_keys", real_validate)


# ── 3. Context-bound capabilities are never StudyType members (M4.4) ────────

def test_context_bound_keys_never_registered_as_study_type():
    from agents.models import StudyType

    study_members = {s.value for s in StudyType}
    leaked = CONTEXT_BOUND_AGENT_KEYS & study_members
    assert not leaked, f"context-bound capabilities leaked into StudyType: {leaked}"


# ── 4. Prompt-handle sync across the Python ↔ TS ↔ prompts.json boundary ─────

def _prompts_json_handles() -> set[str]:
    data = json.loads((REPO_ROOT / "prompts.json").read_text(encoding="utf-8"))
    handles = set(data["prompts"])
    # Descriptive aliases (value is prose, not a handle) are not bindings.
    return handles


def test_python_prompt_handles_resolve_in_prompts_json():
    handles = _prompts_json_handles()
    agents = create_agent_registry()
    missing = sorted(
        {
            getattr(agent, "prompt_handle", None)
            for agent in agents.values()
            if getattr(agent, "prompt_handle", None)
            and getattr(agent, "prompt_handle", None) not in handles
        }
    )
    assert missing == [], f"Python prompt_handle(s) not in prompts.json: {missing}"


def test_ts_prompt_handles_resolve_in_prompts_json():
    handles = _prompts_json_handles()
    ts_source = (REPO_ROOT / "src" / "core" / "agents.ts").read_text(encoding="utf-8")
    ts_handles = set(re.findall(r"promptHandle:\s*'([^']+)'", ts_source))
    assert ts_handles, "expected promptHandle entries in src/core/agents.ts"
    missing = sorted(ts_handles - handles)
    assert missing == [], f"TS promptHandle(s) not in prompts.json: {missing}"
