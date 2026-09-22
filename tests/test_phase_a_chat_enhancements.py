"""Tests for Phase A chat enhancements: system prompt injection, Langfuse tracing, and token budget pruning."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from agents.prompt_loader import _FALLBACK_PROMPT, get_system_prompt
from api.chat_stream import ChatMessageIn, ProviderConfig, _chat_event_stream
from api.token_budget import budget_manager, estimate_tokens


@pytest.mark.asyncio
async def test_chat_system_prompt_injection_flag_enabled():
    """Verify that when chat_system_prompt is True, etap_engineer_agent system prompt is injected at index 0."""
    messages = [ChatMessageIn(role="user", content="What is the short circuit level at Bus 1?")]
    cfg = ProviderConfig(id="openai", model="gpt-4o", api_key="sk-test", base_url="https://api.openai.com/v1")

    captured_body = []

    async def fake_adapter(client, provider_cfg, body):
        captured_body.extend(body)
        yield "token1"

    with patch.dict(os.environ, {"FEATURE_FLAG_CHAT_SYSTEM_PROMPT": "1"}):
        with patch.dict("api.chat_stream._UPSTREAM_ADAPTERS", {"openai": fake_adapter}):
            with patch("api.chat_stream._build_http_client") as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock()
                mock_client.return_value.__aexit__ = AsyncMock()

                events = [ev async for ev in _chat_event_stream("sess-1", messages, cfg)]

    assert len(captured_body) >= 2
    assert captured_body[0]["role"] == "system"
    expected_prompt = get_system_prompt("etap_engineer_agent")
    assert captured_body[0]["content"] == expected_prompt
    assert captured_body[1]["content"] == "What is the short circuit level at Bus 1?"


@pytest.mark.asyncio
async def test_chat_system_prompt_flag_disabled_preserves_plain_messages():
    """Verify that when chat_system_prompt is False, no system prompt is injected."""
    messages = [ChatMessageIn(role="user", content="Hello")]
    cfg = ProviderConfig(id="openai", model="gpt-4o", api_key="sk-test", base_url="https://api.openai.com/v1")

    captured_body = []

    async def fake_adapter(client, provider_cfg, body):
        captured_body.extend(body)
        yield "hi"

    with patch.dict(os.environ, {"FEATURE_FLAG_CHAT_SYSTEM_PROMPT": "0"}):
        with patch.dict("api.chat_stream._UPSTREAM_ADAPTERS", {"openai": fake_adapter}):
            with patch("api.chat_stream._build_http_client") as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock()
                mock_client.return_value.__aexit__ = AsyncMock()

                events = [ev async for ev in _chat_event_stream("sess-2", messages, cfg)]

    assert len(captured_body) == 1
    assert captured_body[0]["role"] == "user"
    assert captured_body[0]["content"] == "Hello"


def test_history_pruning_keeps_100_plus_messages_within_budget():
    """Verify that 100+ messages are pruned to stay under 8000 token limit while preserving recent messages."""
    # Create 120 messages
    messages = []
    messages.append({"role": "system", "content": "You are ETAP Engineer Agent."})
    for i in range(1, 121):
        role = "user" if i % 2 != 0 else "assistant"
        content = f"Message {i}: Detailed engineering query or response discussing substation components and fault impedance at line {i}."
        messages.append({"role": role, "content": content})

    pruned = budget_manager.prune_history(messages, max_tokens=8000, keep_system=True)
    total_tokens = sum(estimate_tokens(m["content"]) for m in pruned)

    assert total_tokens <= 8000
    assert pruned[0]["role"] == "system"
    assert pruned[0]["content"] == "You are ETAP Engineer Agent."
    # The most recent message must be preserved
    assert pruned[-1]["content"] == messages[-1]["content"]


def test_fallback_prompt_content():
    """Ensure safety-net fallback prompt contains mandatory refusal directive."""
    assert "REFUSE to give a numerical answer" in _FALLBACK_PROMPT


@pytest.mark.asyncio
async def test_chat_structured_backend_validation_success():
    """When chat_structured is enabled and response is valid EngineerAnswer JSON, done event has structured=True."""
    import json
    messages = [ChatMessageIn(role="user", content="Perform short circuit evaluation")]
    cfg = ProviderConfig(id="openai", model="gpt-4o", api_key="sk-test", base_url="https://api.openai.com/v1")

    valid_json_answer = json.dumps({
        "title": "Bus 1 Short Circuit",
        "summary": "Verified compliance",
        "status": "complete",
        "study_type": "SHORT_CIRCUIT",
        "findings": [],
        "parameters": {"ik_initial_ka": 25.0},
        "standards_referenced": ["IEC 60909"],
        "recommendations": [],
        "confidence": 0.95,
    })

    async def fake_adapter(client, provider_cfg, body):
        yield valid_json_answer

    with patch.dict(os.environ, {"FEATURE_FLAG_CHAT_STRUCTURED": "1"}):
        with patch.dict("api.chat_stream._UPSTREAM_ADAPTERS", {"openai": fake_adapter}):
            with patch("api.chat_stream._build_http_client") as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock()
                mock_client.return_value.__aexit__ = AsyncMock()

                events = [ev async for ev in _chat_event_stream("sess-struct-1", messages, cfg)]

    done_event = next(ev for ev in events if ev.startswith("event: done"))
    assert '"structured": true' in done_event or '"structured":true' in done_event


@pytest.mark.asyncio
async def test_chat_structured_backend_validation_free_text_non_fatal():
    """When chat_structured is enabled and response is free text, stream succeeds with structured=False."""
    messages = [ChatMessageIn(role="user", content="Hello")]
    cfg = ProviderConfig(id="openai", model="gpt-4o", api_key="sk-test", base_url="https://api.openai.com/v1")

    async def fake_adapter(client, provider_cfg, body):
        yield "This is a free text answer without JSON format."

    with patch.dict(os.environ, {"FEATURE_FLAG_CHAT_STRUCTURED": "1"}):
        with patch.dict("api.chat_stream._UPSTREAM_ADAPTERS", {"openai": fake_adapter}):
            with patch("api.chat_stream._build_http_client") as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock()
                mock_client.return_value.__aexit__ = AsyncMock()

                events = [ev async for ev in _chat_event_stream("sess-struct-2", messages, cfg)]

    done_event = next(ev for ev in events if ev.startswith("event: done"))
    assert '"structured": false' in done_event or '"structured":false' in done_event
    assert "structured_errors" in done_event


@pytest.mark.asyncio
async def test_chat_structured_flag_disabled_omits_field():
    """When chat_structured is disabled, done event does not contain structured key."""
    messages = [ChatMessageIn(role="user", content="Hello")]
    cfg = ProviderConfig(id="openai", model="gpt-4o", api_key="sk-test", base_url="https://api.openai.com/v1")

    async def fake_adapter(client, provider_cfg, body):
        yield "Regular answer"

    with patch.dict(os.environ, {"FEATURE_FLAG_CHAT_STRUCTURED": "0"}):
        with patch.dict("api.chat_stream._UPSTREAM_ADAPTERS", {"openai": fake_adapter}):
            with patch("api.chat_stream._build_http_client") as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock()
                mock_client.return_value.__aexit__ = AsyncMock()

                events = [ev async for ev in _chat_event_stream("sess-struct-3", messages, cfg)]

    done_event = next(ev for ev in events if ev.startswith("event: done"))
    assert "structured" not in done_event


@pytest.mark.asyncio
async def test_langfuse_output_gating_privacy():
    """When langfuse_output_capture is disabled, output passed to tracker is redacted with zero response text."""
    from unittest.mock import MagicMock

    messages = [ChatMessageIn(role="user", content="Query")]
    cfg = ProviderConfig(id="openai", model="gpt-4o", api_key="sk-test", base_url="https://api.openai.com/v1")

    secret_response = "TOP_SECRET_ENGINEERING_ANSWER_12345"

    async def fake_adapter(client, provider_cfg, body):
        yield secret_response

    mock_obs = MagicMock()

    class FakeCM:
        def __enter__(self):
            return mock_obs

        def __exit__(self, *args):
            pass

    # 1) When langfuse_output_capture is disabled (default), zero response content logged
    with patch.dict(os.environ, {"FEATURE_FLAG_LANGFUSE_OUTPUT_CAPTURE": "0"}):
        with patch.dict("api.chat_stream._UPSTREAM_ADAPTERS", {"openai": fake_adapter}):
            with patch("api.chat_stream._build_http_client") as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock()
                mock_client.return_value.__aexit__ = AsyncMock()
                with patch("integrations.langfuse_integration.langfuse_tracker.get_context_manager", return_value=FakeCM()):
                    _ = [ev async for ev in _chat_event_stream("sess-lf-1", messages, cfg)]

    mock_obs.update.assert_called_once()
    called_output = mock_obs.update.call_args.kwargs.get("output", "")
    assert secret_response not in called_output
    assert "[REDACTED: langfuse_output_capture=disabled" in called_output

    # 2) When langfuse_output_capture is enabled, response text is passed
    mock_obs.reset_mock()
    with patch.dict(os.environ, {"FEATURE_FLAG_LANGFUSE_OUTPUT_CAPTURE": "1"}):
        with patch.dict("api.chat_stream._UPSTREAM_ADAPTERS", {"openai": fake_adapter}):
            with patch("api.chat_stream._build_http_client") as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock()
                mock_client.return_value.__aexit__ = AsyncMock()
                with patch("integrations.langfuse_integration.langfuse_tracker.get_context_manager", return_value=FakeCM()):
                    _ = [ev async for ev in _chat_event_stream("sess-lf-2", messages, cfg)]

    mock_obs.update.assert_called_once()
    called_output_enabled = mock_obs.update.call_args.kwargs.get("output", "")
    assert secret_response in called_output_enabled

