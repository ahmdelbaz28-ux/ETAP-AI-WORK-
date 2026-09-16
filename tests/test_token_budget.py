"""
tests/test_token_budget.py — Unit tests for Token Budget Manager and Tool Token Estimation.
"""

import pytest

from api.session_stream import reset_hub
from api.telemetry import tracker
from api.token_budget import (
    DEFAULT_AGENT_BUDGETS,
    TokenBudgetManager,
    estimate_tokens,
)
from api.tool_policy import estimate_tool_tokens


@pytest.fixture(autouse=True)
def clean_state():
    reset_hub()
    tracker.reset()
    yield
    reset_hub()
    tracker.reset()


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello") >= 1
    # 400 chars ~ 100 tokens
    long_text = "a" * 400
    assert estimate_tokens(long_text) == 100


def test_default_agent_budgets():
    mgr = TokenBudgetManager()
    assert mgr.get_budget_for_agent("load_flow_agent") == 4000
    assert mgr.get_budget_for_agent("protection_agent") == 6000
    assert mgr.get_budget_for_agent("etap_engineer_agent") == 8000
    assert mgr.get_budget_for_agent("unknown_agent") == 4000


def test_check_and_reserve_flow():
    mgr = TokenBudgetManager()
    session_id = "test-session-1"
    agent = "load_flow_agent"  # budget: 4000

    # Reserve 2500 tokens -> should succeed
    assert mgr.check_and_reserve(session_id, agent, 2500) is True
    assert mgr.get_remaining(session_id, agent) == 1500

    # Try to reserve another 2000 tokens (2500 + 2000 = 4500 > 4000) -> should fail
    assert mgr.check_and_reserve(session_id, agent, 2000) is False
    assert mgr.get_remaining(session_id, agent) == 1500

    # Reserve 1000 tokens -> should succeed (2500 + 1000 = 3500 <= 4000)
    assert mgr.check_and_reserve(session_id, agent, 1000) is True
    assert mgr.get_remaining(session_id, agent) == 500


def test_record_usage_and_telemetry():
    mgr = TokenBudgetManager()
    session_id = "test-session-2"
    agent = "short_circuit_agent"  # budget: 4000

    mgr.check_and_reserve(session_id, agent, 1000)
    summary = mgr.record_usage(session_id, agent, input_tokens=500, output_tokens=300)

    assert summary["session_id"] == session_id
    assert summary["agent_handle"] == agent
    assert summary["input_tokens"] == 500
    assert summary["output_tokens"] == 300
    assert summary["total_used"] == 800
    assert summary["budget"] == 4000
    assert summary["remaining"] == 3200

    # Verify telemetry tracker
    metrics = tracker.get_metrics()
    assert metrics["tokens_used_input"] == 500
    assert metrics["tokens_used_output"] == 300
    assert metrics["total_tokens_used"] == 800


def test_session_summary_multi_agent():
    mgr = TokenBudgetManager()
    session_id = "session-multi"

    mgr.record_usage(session_id, "load_flow_agent", 1000, 500)
    mgr.record_usage(session_id, "protection_agent", 800, 200)

    summary = mgr.get_session_summary(session_id)
    assert summary["session_id"] == session_id
    assert summary["total_used"] == 2500
    assert "load_flow_agent" in summary["agents"]
    assert summary["agents"]["load_flow_agent"]["used"] == 1500
    assert "protection_agent" in summary["agents"]
    assert summary["agents"]["protection_agent"]["used"] == 1000


def test_prune_history_preserves_system():
    mgr = TokenBudgetManager(max_history_tokens=100)

    messages = [
        {"role": "system", "content": "You are a helpful ETAP power engineer."},
        {"role": "user", "content": "X" * 150},  # ~37 tokens
        {"role": "assistant", "content": "Y" * 150},  # ~37 tokens
        {"role": "user", "content": "Recent question"},  # ~4 tokens
        {"role": "assistant", "content": "Recent response"},  # ~4 tokens
    ]

    pruned = mgr.prune_history(messages, max_tokens=60)

    # First message MUST be the system message
    assert pruned[0]["role"] == "system"
    assert pruned[0]["content"] == "You are a helpful ETAP power engineer."

    # Most recent messages must be retained
    assert pruned[-1]["content"] == "Recent response"
    assert pruned[-2]["content"] == "Recent question"
    # Oldest conversation message should have been dropped to fit in 60 tokens
    assert len(pruned) < len(messages)


def test_estimate_tool_tokens():
    # Base estimation
    base_run = estimate_tool_tokens("run_python")
    assert base_run >= 350

    base_weather = estimate_tool_tokens("weather-tool")
    assert base_weather >= 100

    # With arguments
    args = {"script": "print('hello world')", "study_type": "load_flow", "iterations": 50}
    with_args = estimate_tool_tokens("run_python", args)
    assert with_args > base_run
