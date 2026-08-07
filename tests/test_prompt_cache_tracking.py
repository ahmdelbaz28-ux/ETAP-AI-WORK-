"""Unit tests for prompt-cache tracking + Anthropic cache_control injection.

P0 token-economy fix: ensure the LLM gateway (a) captures cached_tokens
from OpenAI/Anthropic responses, (b) injects ``cache_control: ephemeral``
on the last Anthropic system message, and (c) exposes a snapshot() that
correctly aggregates savings across calls.

These tests do NOT make real LLM calls — they use ``unittest.mock`` to
fake the OpenAI / Anthropic SDK responses.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from integrations.langfuse_llm import (
    PROMPT_CACHE_STATS,
    PromptCacheStats,
    _extract_anthropic_cached_tokens,
    _extract_openai_cached_tokens,
    _inject_anthropic_cache_control,
)


# ─── _inject_anthropic_cache_control ─────────────────────────────────────


class TestInjectAnthropicCacheControl:
    """The Anthropic cache_control injector is the heart of P0."""

    def test_no_system_message_returns_input_unchanged(self):
        """GIVEN messages with no system role
        WHEN injector is called
        THEN the list is returned as-is (no mutation, same length).
        """
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        out = _inject_anthropic_cache_control(msgs)
        assert out == msgs
        assert out is not msgs  # new list, original untouched
        assert len(out) == 2

    def test_empty_messages_returns_empty(self):
        assert _inject_anthropic_cache_control([]) == []

    def test_string_content_system_gets_wrapped_with_cache_control(self):
        """GIVEN a system message with string content
        WHEN injector is called
        THEN content becomes a list with one block tagged cache_control.
        """
        msgs = [
            {"role": "system", "content": "You are an engineer."},
            {"role": "user", "content": "calc the voltage"},
        ]
        out = _inject_anthropic_cache_control(msgs)
        sys_msg = out[0]
        assert sys_msg["role"] == "system"
        assert isinstance(sys_msg["content"], list)
        assert len(sys_msg["content"]) == 1
        block = sys_msg["content"][0]
        assert block["text"] == "You are an engineer."
        assert block["cache_control"] == {"type": "ephemeral"}

    def test_list_content_system_tags_last_block(self):
        """GIVEN a system message with multiple content blocks
        WHEN injector is called
        THEN only the LAST block gets cache_control.
        """
        msgs = [
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": "rules part 1"},
                    {"type": "text", "text": "rules part 2"},
                    {"type": "text", "text": "rules part 3"},
                ],
            },
            {"role": "user", "content": "go"},
        ]
        out = _inject_anthropic_cache_control(msgs)
        blocks = out[0]["content"]
        assert "cache_control" not in blocks[0]
        assert "cache_control" not in blocks[1]
        assert blocks[2]["cache_control"] == {"type": "ephemeral"}

    def test_existing_cache_control_is_not_overwritten(self):
        """GIVEN a system message whose last block already has cache_control
        WHEN injector is called
        THEN the existing cache_control is preserved (idempotent).
        """
        existing_cc = {"type": "ephemeral", "ttl": "1h"}
        msgs = [
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": "x", "cache_control": existing_cc},
                ],
            },
        ]
        out = _inject_anthropic_cache_control(msgs)
        assert out[0]["content"][0]["cache_control"] == existing_cc

    def test_multiple_system_messages_only_last_gets_tagged(self):
        """GIVEN multiple system messages
        WHEN injector is called
        THEN only the LAST system message gets the cache_control tag.
        """
        msgs = [
            {"role": "system", "content": "first system"},
            {"role": "user", "content": "hi"},
            {"role": "system", "content": "second system"},
            {"role": "user", "content": "again"},
        ]
        out = _inject_anthropic_cache_control(msgs)
        assert "cache_control" not in out[0]["content"][0]
        assert out[2]["content"][0]["cache_control"] == {"type": "ephemeral"}

    def test_original_messages_not_mutated(self):
        """GIVEN caller messages
        WHEN injector is called
        THEN the caller's original list and dicts are NOT mutated.
        """
        original = [
            {"role": "system", "content": "original"},
            {"role": "user", "content": "msg"},
        ]
        original_sys_content = original[0]["content"]
        _ = _inject_anthropic_cache_control(original)
        assert original[0]["content"] == original_sys_content
        assert isinstance(original[0]["content"], str)


# ─── _extract_openai_cached_tokens ───────────────────────────────────────


class TestExtractOpenaiCachedTokens:
    """Robustness of OpenAI usage parsing."""

    def test_none_usage_returns_zero(self):
        assert _extract_openai_cached_tokens(None) == 0

    def test_no_prompt_tokens_details_returns_zero(self):
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=10)
        assert _extract_openai_cached_tokens(usage) == 0

    def test_with_cached_tokens(self):
        usage = SimpleNamespace(
            prompt_tokens=200,
            completion_tokens=50,
            prompt_tokens_details=SimpleNamespace(cached_tokens=150),
        )
        assert _extract_openai_cached_tokens(usage) == 150

    def test_with_none_cached_tokens(self):
        usage = SimpleNamespace(
            prompt_tokens=200,
            prompt_tokens_details=SimpleNamespace(cached_tokens=None),
        )
        assert _extract_openai_cached_tokens(usage) == 0

    def test_with_dict_usage(self):
        # Some SDKs return dicts instead of objects.
        usage = {"prompt_tokens": 200, "prompt_tokens_details": {"cached_tokens": 80}}
        # dict-like access via getattr won't work; the function should
        # fall back to 0 gracefully.
        assert _extract_openai_cached_tokens(usage) == 0


# ─── _extract_anthropic_cached_tokens ────────────────────────────────────


class TestExtractAnthropicCachedTokens:
    def test_none_returns_zero(self):
        assert _extract_anthropic_cached_tokens(None) == 0

    def test_with_cache_read_input_tokens(self):
        usage = SimpleNamespace(
            input_tokens=100,
            output_tokens=10,
            cache_read_input_tokens=80,
        )
        assert _extract_anthropic_cached_tokens(usage) == 80

    def test_with_none_returns_zero(self):
        usage = SimpleNamespace(
            input_tokens=100,
            cache_read_input_tokens=None,
        )
        assert _extract_anthropic_cached_tokens(usage) == 0


# ─── PromptCacheStats ────────────────────────────────────────────────────


class TestPromptCacheStats:
    """The stats aggregator that drives token-economy dashboards."""

    def setup_method(self):
        PROMPT_CACHE_STATS.reset()

    def teardown_method(self):
        PROMPT_CACHE_STATS.reset()

    def test_empty_snapshot(self):
        snap = PROMPT_CACHE_STATS.snapshot()
        assert snap["call_count"] == 0
        assert snap["total_input_tokens"] == 0
        assert snap["total_cached_tokens"] == 0
        assert snap["total_output_tokens"] == 0
        assert snap["total_billed_input_tokens"] == 0
        assert snap["cache_hit_ratio"] == 0.0

    def test_record_one_call(self):
        PROMPT_CACHE_STATS.record(
            provider="openai",
            model="gpt-4o",
            agent="LoadFlowAgent",
            input_tokens=1000,
            cached_tokens=600,
            output_tokens=200,
        )
        snap = PROMPT_CACHE_STATS.snapshot()
        assert snap["call_count"] == 1
        assert snap["total_input_tokens"] == 1000
        assert snap["total_cached_tokens"] == 600
        assert snap["total_output_tokens"] == 200
        assert snap["total_billed_input_tokens"] == 400
        assert snap["cache_hit_ratio"] == 0.6

    def test_record_multiple_calls_aggregates(self):
        PROMPT_CACHE_STATS.record(
            provider="openai", model="gpt-4o", agent="A",
            input_tokens=1000, cached_tokens=600, output_tokens=200,
        )
        PROMPT_CACHE_STATS.record(
            provider="anthropic", model="claude-3-5-sonnet-20241022", agent="B",
            input_tokens=2000, cached_tokens=1500, output_tokens=400,
        )
        snap = PROMPT_CACHE_STATS.snapshot()
        assert snap["call_count"] == 2
        assert snap["total_input_tokens"] == 3000
        assert snap["total_cached_tokens"] == 2100
        assert snap["total_output_tokens"] == 600
        assert snap["total_billed_input_tokens"] == 900
        assert snap["cache_hit_ratio"] == 0.7

    def test_reset_clears(self):
        PROMPT_CACHE_STATS.record(
            provider="openai", model="gpt-4o", agent="A",
            input_tokens=100, cached_tokens=0, output_tokens=10,
        )
        assert PROMPT_CACHE_STATS.snapshot()["call_count"] == 1
        PROMPT_CACHE_STATS.reset()
        assert PROMPT_CACHE_STATS.snapshot()["call_count"] == 0

    def test_zero_input_does_not_divide_by_zero(self):
        PROMPT_CACHE_STATS.record(
            provider="openai", model="gpt-4o", agent="A",
            input_tokens=0, cached_tokens=0, output_tokens=0,
        )
        snap = PROMPT_CACHE_STATS.snapshot()
        assert snap["cache_hit_ratio"] == 0.0

    def test_independent_instance_is_isolated(self):
        """GIVEN a fresh PromptCacheStats instance
        WHEN records are added to it
        THEN the global PROMPT_CACHE_STATS is NOT affected.
        """
        local = PromptCacheStats()
        local.record(
            provider="openai", model="gpt-4o", agent="X",
            input_tokens=999, cached_tokens=999, output_tokens=999,
        )
        # Global should still be empty (reset in setup_method).
        assert PROMPT_CACHE_STATS.snapshot()["call_count"] == 0
        assert local.snapshot()["call_count"] == 1


# ─── Integration: safe_openai_chat records usage ─────────────────────────


class TestSafeOpenAiChatRecordsCacheStats:
    """The wrapper must record usage from the OpenAI response."""

    def setup_method(self):
        PROMPT_CACHE_STATS.reset()

    def teardown_method(self):
        PROMPT_CACHE_STATS.reset()

    def test_safe_openai_chat_records_cached_tokens(self, monkeypatch):
        """GIVEN a fake OpenAI response with cached_tokens=800
        WHEN safe_openai_chat is called
        THEN PROMPT_CACHE_STATS.snapshot() shows 1 call with 800 cached.
        """
        from integrations import langfuse_llm as llm

        # Build a fake response that mimics openai.chat.completions.create output
        fake_usage = SimpleNamespace(
            prompt_tokens=1200,
            completion_tokens=300,
            prompt_tokens_details=SimpleNamespace(cached_tokens=800),
        )
        fake_response = SimpleNamespace(usage=fake_usage)

        # Mock the OpenAI client
        fake_openai = MagicMock()
        fake_openai.chat.completions.create.return_value = fake_response

        # Allow any model (we're not testing the allowlist here)
        monkeypatch.setenv("LLM_ALLOW_UNKNOWN_MODELS", "true")
        monkeypatch.setenv("LLM_REQUIRE_AGENT_TAG", "false")
        # Reload the module-level config so the env vars take effect
        import importlib
        importlib.reload(llm)

        with patch.object(llm, "openai", fake_openai):
            response = llm.safe_openai_chat(
                model="gpt-4o",
                messages=[{"role": "user", "content": "test"}],
                metadata={"agent": "TestAgent"},
            )

        assert response is fake_response
        snap = llm.PROMPT_CACHE_STATS.snapshot()
        assert snap["call_count"] == 1
        assert snap["total_input_tokens"] == 1200
        assert snap["total_cached_tokens"] == 800
        assert snap["total_output_tokens"] == 300
        assert snap["total_billed_input_tokens"] == 400
        assert snap["calls"][0]["agent"] == "TestAgent"
        assert snap["calls"][0]["provider"] == "openai"


# ─── Integration: safe_anthropic_message injects cache_control ────────────


class TestSafeAnthropicMessageInjectsCacheControl:
    """The Anthropic path must inject cache_control AND record usage."""

    def setup_method(self):
        PROMPT_CACHE_STATS.reset()

    def teardown_method(self):
        PROMPT_CACHE_STATS.reset()

    def test_safe_anthropic_message_injects_cache_control_and_records(
        self, monkeypatch
    ):
        """GIVEN a long system message
        WHEN safe_anthropic_message is called
        THEN the messages sent to anthropic.messages.create include a
        cache_control block, AND PROMPT_CACHE_STATS records the response.
        """
        from integrations import langfuse_llm as llm

        # Build a fake Anthropic response
        fake_usage = SimpleNamespace(
            input_tokens=1500,
            output_tokens=200,
            cache_read_input_tokens=1200,
        )
        fake_response = SimpleNamespace(usage=fake_usage)

        fake_anthropic = MagicMock()
        fake_anthropic.messages.create.return_value = fake_response

        monkeypatch.setenv("LLM_ALLOW_UNKNOWN_MODELS", "true")
        monkeypatch.setenv("LLM_REQUIRE_AGENT_TAG", "false")
        import importlib
        importlib.reload(llm)

        original_messages = [
            {"role": "system", "content": "You are an electrical engineer."},
            {"role": "user", "content": "Compute the arc flash energy."},
        ]

        with patch.object(llm, "anthropic", fake_anthropic):
            response = llm.safe_anthropic_message(
                model="claude-3-5-sonnet-20241022",
                messages=original_messages,
                metadata={"agent": "ArcFlashAgent"},
            )

        assert response is fake_response

        # Verify the messages passed to Anthropic had cache_control injected
        call_args = fake_anthropic.messages.create.call_args
        sent_messages = call_args.kwargs["messages"]
        sys_msg = sent_messages[0]
        assert isinstance(sys_msg["content"], list)
        assert sys_msg["content"][0]["cache_control"] == {"type": "ephemeral"}

        # Verify original messages were NOT mutated
        assert isinstance(original_messages[0]["content"], str)

        # Verify stats were recorded
        snap = llm.PROMPT_CACHE_STATS.snapshot()
        assert snap["call_count"] == 1
        assert snap["total_cached_tokens"] == 1200
        assert snap["calls"][0]["provider"] == "anthropic"
        assert snap["calls"][0]["agent"] == "ArcFlashAgent"
