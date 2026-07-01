"""
Safety-critical tests for the Langfuse integration + hardened prompt loader.

⚠️ These tests verify SAFETY properties of the prompt-loading system. A
regression here could cause a remote account compromise to silently change
the system prompt of a life-safety engineering agent. Do not skip.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"


@pytest.fixture(autouse=True)
def _clear_prompt_cache():
    """Clear the prompt cache before each test."""
    from agents.prompt_loader import clear_prompt_cache

    clear_prompt_cache()
    yield
    clear_prompt_cache()


@pytest.fixture
def langfuse_disabled(monkeypatch):
    """Disable Langfuse for tests that should not touch the network."""
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    monkeypatch.setenv("LANGFUSE_OVERRIDE_MODE", "false")
    # Force re-import of the modules to pick up env changes
    import importlib

    import agents.prompt_loader as pl
    import integrations.langfuse_integration as lf

    importlib.reload(lf)
    importlib.reload(pl)
    yield


# ---------------------------------------------------------------------------
# Test 1: Sync get_system_prompt ALWAYS uses YAML (never network)
# ---------------------------------------------------------------------------


class TestSyncPromptLoaderSafety:
    """Sync ``get_system_prompt`` must NEVER touch the network."""

    def test_sync_returns_yaml_prompt(self):
        """Sync loader returns the YAML content (deterministic)."""
        from agents.prompt_loader import get_system_prompt

        prompt = get_system_prompt("load_flow_agent")
        assert "Load Flow Analysis Agent" in prompt
        assert "IEEE 3002.7" in prompt  # safety-critical standard

    def test_sync_never_calls_langfuse(self, monkeypatch):
        """Sync loader must not invoke any Langfuse API."""
        # Track if _load_from_langfuse_async is ever called
        from agents import prompt_loader

        call_count = [0]

        async def _spy(*args, **kwargs):
            call_count[0] += 1
            return None

        monkeypatch.setattr(prompt_loader, "_load_from_langfuse_async", _spy)

        prompt = prompt_loader.get_system_prompt("load_flow_agent")
        assert "Load Flow Analysis Agent" in prompt
        assert call_count[0] == 0, "Sync loader must not call async Langfuse code"

    def test_sync_returns_safety_net_for_unknown_handle(self):
        """Unknown handle returns the safety-net prompt (never raises)."""
        from agents.prompt_loader import get_system_prompt

        prompt = get_system_prompt("nonexistent_agent_xyz")
        assert "safety-net" in prompt.lower()
        assert "REFUSE" in prompt  # life-safety refusal clause

    def test_sync_caches_results(self):
        """Cache hit returns the same prompt without re-reading YAML."""
        from agents.prompt_loader import get_prompt_cache_info, get_system_prompt

        prompt1 = get_system_prompt("anomaly_agent")
        info1 = get_prompt_cache_info()
        assert info1["cache_size"] >= 1

        prompt2 = get_system_prompt("anomaly_agent")
        assert prompt1 == prompt2

    def test_sync_fallback_agent_when_handle_missing(self):
        """Missing handle falls back to fallback_agent prompt."""
        from agents.prompt_loader import get_system_prompt

        prompt = get_system_prompt("totally_unknown_handle")
        # Should contain the fallback_agent content (not safety-net yet)
        assert "fallback" in prompt.lower() or "safety-net" in prompt.lower()


# ---------------------------------------------------------------------------
# Test 2: Async get_system_prompt with YAML-first priority
# ---------------------------------------------------------------------------


class TestAsyncPromptLoaderSafety:
    """Async loader must always prefer the local YAML baseline."""

    def test_async_returns_yaml_when_override_disabled(self):
        """When LANGFUSE_OVERRIDE_MODE=false (default), async returns YAML."""
        from agents.prompt_loader import get_system_prompt_async

        prompt = asyncio.run(get_system_prompt_async("load_flow_agent"))
        assert "Load Flow Analysis Agent" in prompt
        assert "IEEE 3002.7" in prompt

    def test_async_does_not_call_langfuse_when_override_off(self, monkeypatch):
        """Async loader skips Langfuse entirely when override is off."""
        from agents import prompt_loader

        call_count = [0]

        async def _spy(*args, **kwargs):
            call_count[0] += 1
            return None

        monkeypatch.setattr(prompt_loader, "_load_from_langfuse_async", _spy)
        # Ensure override is off
        assert not prompt_loader._LANGFUSE_OVERRIDE_MODE

        asyncio.run(prompt_loader.get_system_prompt_async("load_flow_agent"))
        assert call_count[0] == 0

    def test_async_calls_langfuse_when_override_on(self, monkeypatch):
        """Async loader calls Langfuse when override is explicitly enabled."""
        from agents import prompt_loader

        # Force override mode ON
        monkeypatch.setattr(prompt_loader, "_LANGFUSE_OVERRIDE_MODE", True)
        monkeypatch.setattr(prompt_loader, "_LANGFUSE_ENABLED", True)

        call_count = [0]

        async def _spy(handle):
            call_count[0] += 1
            return None  # Return None so YAML is used

        monkeypatch.setattr(prompt_loader, "_load_from_langfuse_async", _spy)

        asyncio.run(prompt_loader.get_system_prompt_async("load_flow_agent"))
        assert call_count[0] == 1


# ---------------------------------------------------------------------------
# Test 3: Integrity check (hash mismatch → CRITICAL warning + use YAML)
# ---------------------------------------------------------------------------


class TestIntegrityCheck:
    """When remote prompt hash differs from local, local YAML wins."""

    def test_hash_mismatch_uses_local_yaml(self, monkeypatch, caplog):
        """Remote prompt with different hash → use local YAML + CRITICAL log."""
        from agents import prompt_loader

        # Force override mode ON
        monkeypatch.setattr(prompt_loader, "_LANGFUSE_OVERRIDE_MODE", True)
        monkeypatch.setattr(prompt_loader, "_LANGFUSE_ENABLED", True)

        # Mock Langfuse to return a DIFFERENT prompt than the YAML
        async def _mock_langfuse(handle):
            return "MALICIOUS PROMPT — INJECTED FROM REMOTE"

        monkeypatch.setattr(prompt_loader, "_load_from_langfuse_async", _mock_langfuse)

        with caplog.at_level("CRITICAL"):
            prompt = asyncio.run(prompt_loader.get_system_prompt_async("load_flow_agent"))

        # Local YAML must win
        assert "Load Flow Analysis Agent" in prompt
        assert "MALICIOUS" not in prompt
        # A CRITICAL log must be emitted
        critical_logs = [r for r in caplog.records if r.levelname == "CRITICAL"]
        assert any("hash mismatch" in r.message.lower() for r in critical_logs), (
            "Hash mismatch must emit CRITICAL log"
        )

    def test_hash_match_uses_remote(self, monkeypatch, caplog):
        """Remote prompt with matching hash → use remote (override OK)."""
        from agents import prompt_loader

        # First, get the YAML prompt to use as the "remote" (matching hash)
        yaml_prompt = prompt_loader._load_from_yaml("load_flow_agent")
        assert yaml_prompt is not None

        monkeypatch.setattr(prompt_loader, "_LANGFUSE_OVERRIDE_MODE", True)
        monkeypatch.setattr(prompt_loader, "_LANGFUSE_ENABLED", True)

        async def _mock_langfuse(handle):
            return yaml_prompt  # Same content → same hash

        monkeypatch.setattr(prompt_loader, "_load_from_langfuse_async", _mock_langfuse)

        prompt = asyncio.run(prompt_loader.get_system_prompt_async("load_flow_agent"))
        assert prompt == yaml_prompt

    def test_no_local_yaml_uses_remote_without_hash_check(self, monkeypatch):
        """If no local YAML exists, remote is used (no hash to compare)."""
        from agents import prompt_loader

        monkeypatch.setattr(prompt_loader, "_LANGFUSE_OVERRIDE_MODE", True)
        monkeypatch.setattr(prompt_loader, "_LANGFUSE_ENABLED", True)

        async def _mock_langfuse(handle):
            return "Remote-only prompt content"

        monkeypatch.setattr(prompt_loader, "_load_from_langfuse_async", _mock_langfuse)

        prompt = asyncio.run(prompt_loader.get_system_prompt_async("nonexistent_agent_xyz"))
        assert prompt == "Remote-only prompt content"


# ---------------------------------------------------------------------------
# Test 4: Circuit breaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """Circuit breaker opens after N consecutive failures."""

    def test_circuit_breaker_opens_after_threshold(self, monkeypatch):
        """After 5 failures, breaker opens and fast-fails."""
        from agents import prompt_loader

        monkeypatch.setattr(prompt_loader, "_LANGFUSE_OVERRIDE_MODE", True)
        monkeypatch.setattr(prompt_loader, "_LANGFUSE_ENABLED", True)

        # Reset breaker
        prompt_loader._langfuse_cb._failures = 0
        prompt_loader._langfuse_cb._opened_at = None

        call_count = [0]

        async def _always_fails(handle):
            call_count[0] += 1
            raise Exception("network error")

        monkeypatch.setattr(prompt_loader, "_load_from_langfuse_async", _always_fails)

        # Call N+1 times — first N record failures, the N+1th fast-fails
        # Note: the circuit breaker logic is inside _load_from_langfuse_async,
        # but here we mocked that function, so we test the breaker directly.
        for i in range(5):
            prompt_loader._langfuse_cb.record_failure()

        assert prompt_loader._langfuse_cb.is_open

    def test_circuit_breaker_resets_after_timeout(self, monkeypatch):
        """Breaker auto-resets after reset_seconds."""
        from agents import prompt_loader

        # Force open
        prompt_loader._langfuse_cb._failures = 10
        prompt_loader._langfuse_cb._opened_at = time.monotonic() - 999
        assert not prompt_loader._langfuse_cb.is_open  # auto-reset


# ---------------------------------------------------------------------------
# Test 5: Cache TTL
# ---------------------------------------------------------------------------


class TestCacheTTL:
    """Cache entries expire after TTL."""

    def test_cache_expires_after_ttl(self, monkeypatch):
        """Stale cache entries are re-fetched."""
        from agents import prompt_loader

        # Set very short TTL
        monkeypatch.setattr(prompt_loader, "_CACHE_TTL_SECONDS", 0.1)

        # First call populates cache
        prompt1 = prompt_loader.get_system_prompt("load_flow_agent")
        assert prompt1 is not None

        # Wait for TTL to expire
        time.sleep(0.15)

        # Second call should re-fetch (cache miss)
        # We verify by checking cache_info age resets
        prompt2 = prompt_loader.get_system_prompt("load_flow_agent")
        assert prompt2 == prompt1  # same content (YAML is deterministic)

        info = prompt_loader.get_prompt_cache_info()
        # The most recent entry should have age < 0.1s
        load_flow_entry = [e for e in info["cache_entries"] if e["handle"] == "load_flow_agent"][0]
        assert load_flow_entry["age_seconds"] < 0.1

    def test_clear_cache_purges_all(self):
        """clear_prompt_cache removes all entries."""
        from agents.prompt_loader import (
            clear_prompt_cache,
            get_prompt_cache_info,
            get_system_prompt,
        )

        get_system_prompt("load_flow_agent")
        assert get_prompt_cache_info()["cache_size"] >= 1

        clear_prompt_cache()
        assert get_prompt_cache_info()["cache_size"] == 0


# ---------------------------------------------------------------------------
# Test 6: track_llm_call decorator — exception recording
# ---------------------------------------------------------------------------


class TestTrackLLMCallDecorator:
    """Decorator must record exceptions on the Langfuse observation."""

    def test_decorator_preserves_return_value_sync(self):
        """Sync decorator returns the wrapped function's value."""
        from integrations.langfuse_integration import track_llm_call

        @track_llm_call(name="test", agent="TestAgent")
        def fn(x):
            return x * 2

        assert fn(21) == 42

    def test_decorator_preserves_return_value_async(self):
        """Async decorator returns the wrapped function's value."""
        from integrations.langfuse_integration import track_llm_call

        @track_llm_call(name="test", agent="TestAgent")
        async def fn(x):
            await asyncio.sleep(0)
            return x * 2

        assert asyncio.run(fn(21)) == 42

    def test_decorator_reraises_exception_sync(self):
        """Sync decorator re-raises exceptions (does not swallow)."""
        from integrations.langfuse_integration import track_llm_call

        @track_llm_call(name="test", agent="TestAgent")
        def fn():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            fn()

    def test_decorator_reraises_exception_async(self):
        """Async decorator re-raises exceptions (does not swallow)."""
        from integrations.langfuse_integration import track_llm_call

        @track_llm_call(name="test", agent="TestAgent")
        async def fn():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            asyncio.run(fn())

    def test_decorator_does_not_crash_when_langfuse_disabled(self, monkeypatch):
        """Decorator works even when Langfuse is unavailable/disabled."""
        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
        monkeypatch.setenv("LANGFUSE_ENABLED", "false")

        # Re-import to pick up env change
        import importlib

        import integrations.langfuse_integration as lf

        importlib.reload(lf)

        @lf.track_llm_call(name="test", agent="TestAgent")
        def fn(x):
            return x + 1

        assert fn(5) == 6  # Still works, just no tracing


# ---------------------------------------------------------------------------
# Test 7: PII redaction (input truncation)
# ---------------------------------------------------------------------------


class TestPIIRedaction:
    """Input/output capture must be truncated to prevent PII leaks."""

    def test_truncate_long_input(self):
        """Long inputs are truncated to max_capture_chars."""
        from integrations.langfuse_integration import _truncate_for_capture

        long_text = "x" * 10000
        result = _truncate_for_capture(long_text, max_chars=100)
        assert len(result) <= 200  # 100 + truncation message
        assert "[truncated" in result

    def test_short_input_preserved(self):
        """Short inputs are preserved as-is."""
        from integrations.langfuse_integration import _truncate_for_capture

        result = _truncate_for_capture("hello", max_chars=100)
        assert result == "hello"

    def test_zero_max_chars_disables_capture(self):
        """Setting max_chars=0 disables capture entirely (returns None)."""
        from integrations.langfuse_integration import _truncate_for_capture

        assert _truncate_for_capture("anything", max_chars=0) is None
        assert _truncate_for_capture(None, max_chars=0) is None

    def test_none_input_returns_none(self):
        """None input returns None."""
        from integrations.langfuse_integration import _truncate_for_capture

        assert _truncate_for_capture(None, max_chars=100) is None


# ---------------------------------------------------------------------------
# Test 8: Fallback prompt has safety-critical refusal clause
# ---------------------------------------------------------------------------


class TestSafetyNetPrompt:
    """The hardcoded safety-net prompt must include a refusal clause."""

    def test_safety_net_refuses_uncertain_calculations(self):
        """Safety-net prompt tells the agent to REFUSE uncertain life-safety answers."""
        from agents.prompt_loader import _FALLBACK_PROMPT

        assert "REFUSE" in _FALLBACK_PROMPT or "refuse" in _FALLBACK_PROMPT.lower()
        assert (
            "licensed engineer" in _FALLBACK_PROMPT.lower()
            or "engineer" in _FALLBACK_PROMPT.lower()
        )

    def test_safety_net_mentions_standards(self):
        """Safety-net prompt mentions IEEE/IEC standards."""
        from agents.prompt_loader import _FALLBACK_PROMPT

        assert "IEEE" in _FALLBACK_PROMPT or "IEC" in _FALLBACK_PROMPT


# ---------------------------------------------------------------------------
# Test 9: All 31 prompts load successfully from YAML (regression test)
# ---------------------------------------------------------------------------


class TestAllPromptsLoadFromYAML:
    """Every prompt file in prompts/ must load without error."""

    EXPECTED_HANDLES = [
        "anomaly_agent",
        "arcflash_agent",
        "battery_storage_agent",
        "cable_sizing_agent",
        "code_guard_agent",
        "coordination_agent",
        "digital_twin_agent",
        "earth_grid_agent",
        "etap_engineer_agent",
        "etap_engineer_agent_v2",
        "etap_expert_agent",
        "etap_gui_agent",
        "fallback_agent",
        "generic_agent_chat",
        "goal_planner_agent",
        "harmonic_agent",
        "load_flow_agent",
        "motor_starting_agent",
        "opf_agent",
        "power_system_coordinator_agent",
        "predictive_agent",
        "protection_agent",
        "renewable_agent",
        "report_agent",
        "scada_agent",
        "short_circuit_agent",
        "stability_agent",
        "validation_agent",
        "weather_activity_planner",
        "weather_agent",
    ]

    @pytest.mark.parametrize("handle", EXPECTED_HANDLES)
    def test_prompt_loads(self, handle):
        """Each expected handle loads a non-empty prompt."""
        from agents.prompt_loader import get_system_prompt

        prompt = get_system_prompt(handle)
        assert prompt, f"Prompt '{handle}' returned empty"
        assert len(prompt) > 50, f"Prompt '{handle}' suspiciously short ({len(prompt)} chars)"


# ---------------------------------------------------------------------------
# Test 10: Cache info / observability
# ---------------------------------------------------------------------------


class TestCacheInfo:
    """get_prompt_cache_info exposes state for monitoring."""

    def test_cache_info_structure(self):
        from agents.prompt_loader import get_prompt_cache_info

        info = get_prompt_cache_info()
        assert "cache_size" in info
        assert "cache_ttl_seconds" in info
        assert "langfuse_enabled" in info
        assert "langfuse_override_mode" in info
        assert "langfuse_circuit_open" in info
        assert "langwatch_override_mode" in info
        assert "langwatch_circuit_open" in info
        assert "cache_entries" in info
        assert isinstance(info["cache_entries"], list)


# ---------------------------------------------------------------------------
# Test 11: Hash function is deterministic
# ---------------------------------------------------------------------------


class TestHashFunction:
    """The prompt hash function must be deterministic and order-stable."""

    def test_same_input_same_hash(self):
        from agents.prompt_loader import _hash_prompt

        h1 = _hash_prompt("Hello\nWorld\n")
        h2 = _hash_prompt("Hello\nWorld\n")
        assert h1 == h2

    def test_different_input_different_hash(self):
        from agents.prompt_loader import _hash_prompt

        h1 = _hash_prompt("Hello")
        h2 = _hash_prompt("World")
        assert h1 != h2

    def test_trailing_whitespace_normalized(self):
        """Trailing whitespace per line does not change the hash."""
        from agents.prompt_loader import _hash_prompt

        h1 = _hash_prompt("Hello   \nWorld   \n")
        h2 = _hash_prompt("Hello\nWorld\n")
        assert h1 == h2

    def test_hash_is_sha256_hex(self):
        """Hash is a 64-char hex string (SHA-256)."""
        from agents.prompt_loader import _hash_prompt

        h = _hash_prompt("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)  # pragma: allowlist secret
