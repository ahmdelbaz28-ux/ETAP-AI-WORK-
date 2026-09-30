"""M4.5 — Single provider/model policy point (G4).

Proves:
1. ``config/llm-provider-policy.json`` is valid and is the ONLY source the
   Python consumers read (chat_stream allow-list, model_router tiers).
2. Changing that one document changes the behaviour of **every** consumer:
   ``allowed_provider_ids``, ``resolve_model`` / ``ModelCascadeRouter``, and
   the reloaded ``api.chat_stream`` module.
3. A missing or malformed policy fails closed (``ProviderPolicyError``).
4. The ``use_model_cascade`` feature flag is gone and ``langfuse_llm`` no
   longer guards the router behind it.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import pytest

import integrations.provider_policy as provider_policy
from integrations.model_router import (
    ModelTier,
    policy_tier_models,
    resolve_model,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = REPO_ROOT / "config" / "llm-provider-policy.json"

_GEMINI_SHORT = "What is the nominal voltage?"  # < 80 chars ⇒ ECONOMY tier


@pytest.fixture(autouse=True)
def _reset_policy_cache():
    """Every test starts from a clean policy cache and ends with one."""
    provider_policy.invalidate_policy_cache()
    yield
    provider_policy.invalidate_policy_cache()
    os.environ.pop(provider_policy.POLICY_PATH_ENV, None)


def _load_committed() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _write_modified_policy(tmp_path: Path, mutate) -> Path:
    doc = _load_committed()
    mutate(doc)
    target = tmp_path / "llm-provider-policy.json"
    target.write_text(json.dumps(doc), encoding="utf-8")
    return target


# ─────────────────────────────────────────────────────────────────────────────
# 1. The committed document is valid and is what consumers read
# ─────────────────────────────────────────────────────────────────────────────

def test_committed_policy_is_valid():
    assert provider_policy.validate_provider_policy(_load_committed()) == []
    assert provider_policy.load_provider_policy(POLICY_PATH)["policy_id"] == "etap-llm-provider-policy"


def test_chat_stream_allow_list_is_policy_derived():
    from api import chat_stream

    assert provider_policy.allowed_provider_ids(
        "chat_stream", POLICY_PATH
    ) == chat_stream.SUPPORTED_PROVIDERS
    assert chat_stream.SUPPORTED_PROVIDERS == ("openai", "anthropic", "gemini")

    defaults = provider_policy.provider_defaults("chat_stream", POLICY_PATH)
    assert dict(chat_stream.PROVIDER_DEFAULT_BASE_URL) == {
        pid: d["base_url"] for pid, d in defaults.items()
    }
    assert dict(chat_stream.PROVIDER_DEFAULT_MODEL) == {
        pid: d["default_model"] for pid, d in defaults.items()
    }

    env_map = provider_policy.provider_env_map(POLICY_PATH)
    assert chat_stream.PROVIDER_API_KEY_ENV["openai"] == env_map["openai"]["api_key"]


def test_tier_models_come_from_policy():
    doc = _load_committed()
    assert policy_tier_models(ModelTier.ECONOMY) == doc["model_tiers"]["tier_1_economy"]
    assert policy_tier_models("tier_3_reasoning") == doc["model_tiers"]["tier_3_reasoning"]


def test_seed_constant_has_not_drifted_from_policy():
    """TIER_MODELS is documentation-only; it must mirror the policy."""
    from integrations.model_router import TIER_MODELS

    doc = _load_committed()
    for tier in ModelTier:
        assert list(TIER_MODELS[tier]) == doc["model_tiers"][tier.value], (
            f"TIER_MODELS[{tier.value}] drifted from config/llm-provider-policy.json"
        )


def test_cascade_flag_removed_and_langfuse_no_longer_guards_it():
    from api.feature_flags import DEFAULT_FEATURE_FLAGS

    assert "use_model_cascade" not in DEFAULT_FEATURE_FLAGS, (
        "M4.5 removed the use_model_cascade flag — policy is the control now"
    )

    source = (REPO_ROOT / "integrations" / "langfuse_llm.py").read_text(encoding="utf-8")
    assert "use_model_cascade" not in source
    assert "is_strict_feature_enabled" not in source
    assert "resolve_model(" in source


# ─────────────────────────────────────────────────────────────────────────────
# 2. THE G4 propagation test — one document, every consumer moves
# ─────────────────────────────────────────────────────────────────────────────

def test_changing_the_policy_document_changes_every_consumer(tmp_path, monkeypatch):
    """Edit config/llm-provider-policy.json (single point) ⇒ all consumers follow."""
    # ── Baseline behaviour ────────────────────────────────────────────────
    baseline_chat = provider_policy.allowed_provider_ids("chat_stream", POLICY_PATH)
    baseline_edge = provider_policy.allowed_provider_ids("edge_gateway", POLICY_PATH)
    baseline_model = resolve_model(_GEMINI_SHORT).model
    assert "gemini" in baseline_chat
    assert baseline_edge == tuple(
        p["id"] for p in _load_committed()["providers"] if "edge_gateway" in p["surfaces"]
    )

    # ── Mutate the SINGLE point ───────────────────────────────────────────
    def mutate(doc):
        # (a) drop the gemini provider from the chat surface entirely
        doc["providers"] = [
            p for p in doc["providers"] if not (p["id"] == "gemini" and "chat_stream" in p["surfaces"])
        ]
        # (b) change the economy tier's first choice
        doc["model_tiers"]["tier_1_economy"] = [
            "policy-chosen-model",
            "gpt-4o-mini",
        ]

    modified = _write_modified_policy(tmp_path, mutate)
    monkeypatch.setenv(provider_policy.POLICY_PATH_ENV, str(modified))
    provider_policy.invalidate_policy_cache()

    # ── Consumer A: derived allow-lists ───────────────────────────────────
    assert provider_policy.allowed_provider_ids("chat_stream") == ("openai", "anthropic")
    assert "gemini" not in provider_policy.allowed_provider_ids("chat_stream")
    assert provider_policy.allowed_provider_ids("edge_gateway") == baseline_edge

    # ── Consumer B: the model router decision ─────────────────────────────
    changed = resolve_model(_GEMINI_SHORT)
    assert changed is not None
    assert changed.model == "policy-chosen-model"
    assert changed.model != baseline_model
    assert policy_tier_models(ModelTier.ECONOMY)[0] == "policy-chosen-model"

    # ── Consumer C: the HTTP chat stream module (re-reads the policy) ─────
    from api import chat_stream

    importlib.reload(chat_stream)
    try:
        assert chat_stream.SUPPORTED_PROVIDERS == ("openai", "anthropic")
        assert "gemini" not in chat_stream.SUPPORTED_PROVIDERS
        assert "GEMINI_API_KEY" not in chat_stream.PROVIDER_API_KEY_ENV
        assert chat_stream.PROVIDER_DEFAULT_MODEL["openai"] == "gpt-4o-mini"
    finally:
        # Restore the committed policy for every later test.
        os.environ.pop(provider_policy.POLICY_PATH_ENV, None)
        provider_policy.invalidate_policy_cache()
        importlib.reload(chat_stream)

    assert baseline_chat == chat_stream.SUPPORTED_PROVIDERS


def test_disabling_cascade_in_the_policy_stops_re_routing(tmp_path, monkeypatch):
    """Policy `cascade.enabled=false` ⇒ resolve_model declines to decide."""
    assert resolve_model(_GEMINI_SHORT) is not None  # baseline: cascade on

    def mutate(doc):
        doc["cascade"]["enabled"] = False

    modified = _write_modified_policy(tmp_path, mutate)
    monkeypatch.setenv(provider_policy.POLICY_PATH_ENV, str(modified))
    provider_policy.invalidate_policy_cache()

    assert provider_policy.cascade_enabled() is False
    assert resolve_model(_GEMINI_SHORT) is None


# ─────────────────────────────────────────────────────────────────────────────
# 3. Fail-closed: no silent fallback to a hard-coded allow-list
# ─────────────────────────────────────────────────────────────────────────────

def test_missing_policy_fails_closed(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    with pytest.raises(provider_policy.ProviderPolicyError):
        provider_policy.load_provider_policy(missing, reload=True)

    provider_policy.invalidate_policy_cache()
    with pytest.raises(provider_policy.ProviderPolicyError):
        resolve_model(_GEMINI_SHORT, policy_path=str(missing))


def test_malformed_policy_fails_closed(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(provider_policy.ProviderPolicyError):
        provider_policy.load_provider_policy(bad, reload=True)


@pytest.mark.parametrize(
    "mutate,expected_fragment",
    [
        (lambda d: d.pop("providers"), "providers"),
        (lambda d: d["providers"].append(dict(d["providers"][0])), "duplicate provider id"),
        (lambda d: d["cascade"].update({"default_tier": "tier_9_unknown"}), "default_tier"),
        (lambda d: d.update({"model_tiers": {}}), "model_tiers"),
    ],
)
def test_invalid_policy_shape_fails_closed(tmp_path, mutate, expected_fragment):
    doc = _load_committed()
    mutate(doc)
    bad = tmp_path / "invalid.json"
    bad.write_text(json.dumps(doc), encoding="utf-8")

    problems = provider_policy.validate_provider_policy(doc)
    assert problems, "validator must reject the mutated policy"
    with pytest.raises(provider_policy.ProviderPolicyError) as excinfo:
        provider_policy.load_provider_policy(bad, reload=True)
    assert expected_fragment in str(excinfo.value)


def test_unknown_tier_is_rejected_without_hardcoded_backstop():
    """policy_tier_models must not silently fall back to TIER_MODELS."""
    with pytest.raises(provider_policy.ProviderPolicyError):
        policy_tier_models("tier_does_not_exist")

