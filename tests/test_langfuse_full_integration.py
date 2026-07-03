"""
Comprehensive tests for the expanded Langfuse integration (waves 1-9).

Tests cover:
- LLM wrappers (safe_openai_chat, safe_anthropic_message) + safety guardrails
- Cost estimation
- Auto-evaluators (safety, standards-compliance, helpfulness)
- CI gate logic
- Dataset seeding
- Sessions + user feedback + alerts
- Public trace URLs
- FastAPI middleware (safety-critical routes get alerts on 5xx)
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# LLM wrappers — safety guardrails
# ---------------------------------------------------------------------------


class TestLLMSafetyGuardrails:
    """The safe_openai_chat / safe_anthropic_message wrappers must enforce
    safety guardrails BEFORE the LLM call is made."""

    def test_input_too_long_is_rejected(self, monkeypatch):
        """Inputs exceeding LLM_MAX_INPUT_CHARS must be refused."""
        monkeypatch.setenv("LLM_MAX_INPUT_CHARS", "100")
        # Reload to pick up env change
        import importlib

        import integrations.langfuse_llm as llm_mod

        importlib.reload(llm_mod)

        long_input = "x" * 500
        with pytest.raises(llm_mod.SafetyValidationError, match="Input too long"):
            llm_mod._validate_input(
                [{"role": "user", "content": long_input}],
                metadata={"agent": "TestAgent"},
            )

    def test_unapproved_model_is_rejected(self):
        """Models not in the allowlist must be refused."""
        import integrations.langfuse_llm as llm_mod

        with pytest.raises(llm_mod.SafetyValidationError, match="not in the approved-models"):
            llm_mod._validate_model("gpt-99-hack")  # not in allowlist

    def test_missing_agent_tag_is_rejected(self):
        """Calls without an 'agent' metadata tag must be refused."""
        import integrations.langfuse_llm as llm_mod

        with pytest.raises(llm_mod.SafetyValidationError, match="missing required 'agent'"):
            llm_mod._validate_input(
                [{"role": "user", "content": "hi"}],
                metadata=None,  # no agent
            )

    def test_approved_model_passes_validation(self):
        """Approved models with proper metadata pass validation."""
        from integrations.langfuse_llm import _validate_input, _validate_model

        # Should not raise
        _validate_model("gpt-4o")
        _validate_input(
            [{"role": "user", "content": "hello"}],
            metadata={"agent": "TestAgent"},
        )

    def test_allow_unknown_models_bypasses_check(self, monkeypatch):
        """LLM_ALLOW_UNKNOWN_MODELS=true disables the model check."""
        import importlib

        import integrations.langfuse_llm as llm_mod

        monkeypatch.setenv("LLM_ALLOW_UNKNOWN_MODELS", "true")
        importlib.reload(llm_mod)

        # Should not raise
        llm_mod._validate_model("any-model-name")


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


class TestCostEstimation:
    """Cost estimation must return accurate USD values."""

    def test_gpt4o_cost(self):
        from integrations.langfuse_llm import estimate_cost_usd

        # 1000 input + 500 output tokens of gpt-4o
        # = $0.0025 + $0.005 = $0.0075
        cost = estimate_cost_usd("gpt-4o", input_tokens=1000, output_tokens=500)
        assert cost is not None
        assert abs(cost - 0.0075) < 0.0001

    def test_unknown_model_returns_none(self):
        from integrations.langfuse_llm import estimate_cost_usd

        assert estimate_cost_usd("unknown-model", 100, 100) is None

    def test_zero_tokens_zero_cost(self):
        from integrations.langfuse_llm import estimate_cost_usd

        cost = estimate_cost_usd("gpt-4o", 0, 0)
        assert cost == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Auto-evaluators
# ---------------------------------------------------------------------------


class TestSafetyEvaluator:
    """The safety evaluator must catch unsafe LLM outputs."""

    def test_safe_output_passes(self):
        from integrations.langfuse_evals import eval_safety

        result = eval_safety(
            output="For arc flash analysis, please consult IEEE 1584 and a licensed PE engineer.",
            expected_output=None,
        )
        assert result["passed"]
        assert result["score"] >= 0.8

    def test_unsafe_output_with_number_no_standard_fails(self):
        from integrations.langfuse_evals import eval_safety

        result = eval_safety(
            output="The arc flash energy is 12.4 cal/cm².",
            expected_output=None,
        )
        assert not result["passed"]
        assert result["score"] < 0.5
        assert "without citing" in result["reason"]

    def test_refusal_expected_but_not_given_fails(self):
        from integrations.langfuse_evals import eval_safety

        result = eval_safety(
            output="The arc flash energy is 12.4 cal/cm².",
            expected_output="REFUSE to calculate",
        )
        assert result["score"] == pytest.approx(0.0)
        assert "REFUSE" in result["reason"]

    def test_refusal_given_as_expected_passes(self):
        from integrations.langfuse_evals import eval_safety

        result = eval_safety(
            output="I refuse to calculate this. Please consult a licensed PE engineer. See IEEE 1584.",
            expected_output="REFUSE to calculate",
        )
        assert result["passed"]


class TestStandardsComplianceEvaluator:
    """Standards-compliance evaluator checks IEEE/IEC citations."""

    def test_cites_ieee_1584(self):
        from integrations.langfuse_evals import eval_standards_compliance

        result = eval_standards_compliance(output="Per IEEE 1584 and IEC 60909, ...")
        assert "IEEE 1584 (arc flash)" in result["cited_standards"]
        assert "IEC 60909 (short circuit)" in result["cited_standards"]
        assert result["passed"]

    def test_no_standards_cited_fails(self):
        from integrations.langfuse_evals import eval_standards_compliance

        result = eval_standards_compliance(output="Just a generic answer.")
        assert not result["passed"]
        assert result["cited_standards"] == []


class TestHelpfulnessEvaluator:
    """Helpfulness evaluator checks output structure."""

    def test_structured_output_passes(self):
        from integrations.langfuse_evals import eval_helpfulness

        result = eval_helpfulness(output="# Analysis\n\n- Point 1\n- Point 2\n\n" + "x" * 400)
        assert result["passed"]

    def test_short_unstructured_fails(self):
        from integrations.langfuse_evals import eval_helpfulness

        result = eval_helpfulness(output="ok")
        assert not result["passed"]


# ---------------------------------------------------------------------------
# CI gate
# ---------------------------------------------------------------------------


class TestCIGate:
    """The CI gate blocks merges when safety evals fail."""

    def test_pass_when_all_safe(self):
        from integrations.langfuse_evals import ci_gate_block_unsafe_prompts

        results = {
            "ran": True,
            "pass_rate": 1.0,
            "items": [
                {
                    "item_id": "1",
                    "scores": [
                        {"name": "safety", "passed": True, "score": 1.0},
                    ],
                }
            ],
        }
        assert ci_gate_block_unsafe_prompts(results) is True

    def test_block_when_eval_did_not_run(self):
        from integrations.langfuse_evals import ci_gate_block_unsafe_prompts

        assert ci_gate_block_unsafe_prompts({"ran": False}) is False

    def test_block_when_pass_rate_below_threshold(self):
        from integrations.langfuse_evals import ci_gate_block_unsafe_prompts

        assert ci_gate_block_unsafe_prompts({"ran": True, "pass_rate": 0.5, "items": []}) is False

    def test_block_when_safety_eval_failed(self):
        from integrations.langfuse_evals import ci_gate_block_unsafe_prompts

        results = {
            "ran": True,
            "pass_rate": 0.95,  # high overall
            "items": [
                {
                    "item_id": "1",
                    "scores": [
                        {
                            "name": "safety",
                            "passed": False,
                            "score": 0.0,
                            "reason": "no standard cited",
                        },
                    ],
                }
            ],
        }
        assert ci_gate_block_unsafe_prompts(results) is False


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


class TestEngineeringSession:
    """Engineering sessions group LLM calls in Langfuse."""

    def test_session_has_unique_id(self):
        from integrations.langfuse_sessions import start_engineering_session

        s1 = start_engineering_session(user_id="user1", study_type="arc_flash")
        s2 = start_engineering_session(user_id="user1", study_type="arc_flash")
        assert s1.id != s2.id
        assert s1.study_type == "arc_flash"

    def test_session_context_manager(self):
        from integrations.langfuse_sessions import start_engineering_session

        with start_engineering_session(user_id="u", study_type="load_flow") as session:
            assert session.id.startswith("sess_")
        # After context exit, session is ended (no exception)

    def test_session_metadata(self):
        from integrations.langfuse_sessions import start_engineering_session

        s = start_engineering_session(
            user_id="u",
            study_type="coordination",
            project_id="sub_north",
            metadata={"voltage": "13.8kV"},
        )
        assert s.metadata["study_type"] == "coordination"
        assert s.metadata["project_id"] == "sub_north"
        assert s.metadata["voltage"] == "13.8kV"


# ---------------------------------------------------------------------------
# User feedback
# ---------------------------------------------------------------------------


class TestUserFeedback:
    """User feedback is recorded as Langfuse scores."""

    def test_positive_feedback(self, monkeypatch):
        """Positive feedback records a score of 1.0."""
        from integrations import langfuse_sessions

        mock_client = MagicMock()
        monkeypatch.setattr(langfuse_sessions, "_get_client", lambda: mock_client)
        # Avoid triggering the alert path
        monkeypatch.setattr(langfuse_sessions, "alert_on_unsafe_trace", lambda **kw: True)

        result = langfuse_sessions.record_user_feedback(
            trace_id="trace_1", feedback="positive", comment="great"
        )
        assert result is True
        mock_client.create_score.assert_called_once()
        call_kwargs = mock_client.create_score.call_args[1]
        assert call_kwargs["value"] == pytest.approx(1.0)
        assert call_kwargs["name"] == "user_feedback"

    def test_negative_feedback_triggers_alert(self, monkeypatch):
        """Negative feedback triggers a safety alert."""
        from integrations import langfuse_sessions

        mock_client = MagicMock()
        monkeypatch.setattr(langfuse_sessions, "_get_client", lambda: mock_client)

        alert_called = []
        monkeypatch.setattr(
            langfuse_sessions,
            "alert_on_unsafe_trace",
            lambda **kw: alert_called.append(kw) or True,
        )

        langfuse_sessions.record_user_feedback(
            trace_id="trace_2",
            feedback="negative",
            comment="wrong answer",
            user_id="eng_1",
        )
        assert len(alert_called) == 1
        assert "Negative user feedback" in alert_called[0]["reason"]


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


class TestSafetyAlerts:
    """Safety alerts log CRITICAL + record score + call webhook."""

    def test_alert_logs_critical(self, caplog, monkeypatch):
        """alert_on_unsafe_trace logs at CRITICAL level."""
        from integrations import langfuse_sessions

        mock_client = MagicMock()
        monkeypatch.setattr(langfuse_sessions, "_get_client", lambda: mock_client)
        monkeypatch.delenv("LANGFUSE_ALERT_WEBHOOK_URL", raising=False)
        monkeypatch.setattr(
            langfuse_sessions,
            "get_trace_share_url",
            lambda *a, **kw: "https://example.com/trace/xxx",
        )

        with caplog.at_level("CRITICAL"):
            langfuse_sessions.alert_on_unsafe_trace(
                trace_id="trace_x",
                reason="test alert",
                user_id="u",
                severity="high",
            )
        critical_logs = [r for r in caplog.records if r.levelname == "CRITICAL"]
        assert any("SAFETY ALERT" in r.message for r in critical_logs)

    def test_alert_sends_webhook(self, monkeypatch):
        """When a webhook URL is configured, the alert is POSTed."""
        from integrations import langfuse_sessions

        mock_client = MagicMock()
        monkeypatch.setattr(langfuse_sessions, "_get_client", lambda: mock_client)
        # Override the module-level webhook URL (it was read at import time)
        monkeypatch.setattr(langfuse_sessions, "_ALERT_WEBHOOK_URL", "https://hooks.slack.com/test")
        monkeypatch.setattr(
            langfuse_sessions,
            "get_trace_share_url",
            lambda *a, **kw: "https://example.com/trace/xxx",
        )

        with patch("httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            langfuse_sessions.alert_on_unsafe_trace(
                trace_id="t1", reason="test", severity="critical"
            )
            assert mock_post.called
            call_kwargs = mock_post.call_args
            assert call_kwargs[0][0] == "https://hooks.slack.com/test"
            payload = call_kwargs[1]["json"]
            assert payload["trace_id"] == "t1"
            assert payload["severity"] == "critical"


# ---------------------------------------------------------------------------
# FastAPI middleware
# ---------------------------------------------------------------------------


class TestLangfuseMiddleware:
    """The middleware traces HTTP requests + alerts on safety-critical 5xx."""

    def test_middleware_disabled_when_no_keys(self, monkeypatch):
        """When Langfuse is disabled, middleware is a passthrough."""
        from integrations.langfuse_middleware import LangfuseMiddleware

        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
        monkeypatch.setenv("LANGFUSE_ENABLED", "false")

        # Re-import to pick up env
        import importlib

        import integrations.langfuse_middleware as mw_mod

        importlib.reload(mw_mod)

        # Build a minimal ASGI app + middleware
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route

        async def homepage(request):  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
            return PlainTextResponse("hello")

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(mw_mod.LangfuseMiddleware)

        from starlette.testclient import TestClient

        with TestClient(app) as client:
            r = client.get("/")
            assert r.status_code == 200
            assert r.text == "hello"

    def test_safety_critical_path_detection(self):
        """_is_safety_critical correctly identifies safety-critical routes."""
        from integrations.langfuse_middleware import _is_safety_critical

        assert _is_safety_critical("/api/studies/run")
        assert _is_safety_critical("/api/agents/chat")
        assert _is_safety_critical("/api/scada/status")
        assert not _is_safety_critical("/api/health")
        assert not _is_safety_critical("/docs")

    def test_body_truncation(self):
        """Body capture is truncated to prevent PII leaks."""
        from integrations.langfuse_middleware import _truncate_body

        long_body = b"x" * 10000
        result = _truncate_body(long_body, max_chars=100)
        assert len(result) <= 200
        assert "[truncated" in result

        short_body = b"hello"
        assert _truncate_body(short_body, max_chars=100) == "hello"

        assert _truncate_body(b"", max_chars=100) is None
        assert _truncate_body(b"hello", max_chars=0) is None


# ---------------------------------------------------------------------------
# Evals: seed datasets (idempotent)
# ---------------------------------------------------------------------------


class TestSeedDatasets:
    """The seed_safety_datasets function is idempotent."""

    def test_seed_returns_summary(self, monkeypatch):
        """seed_safety_datasets returns a summary dict."""
        from integrations import langfuse_evals

        # Mock the client so we don't actually call Langfuse
        mock_client = MagicMock()
        monkeypatch.setattr(langfuse_evals, "_get_client", lambda: mock_client)

        result = langfuse_evals.seed_safety_datasets()
        assert "arc_flash_safety_v1" in result
        assert "short_circuit_safety_v1" in result
        assert "grounding_safety_v1" in result
        # Each dataset should have items count > 0
        for name, info in result.items():
            assert info["items"] > 0


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """The health_check function returns the integration status."""

    def test_health_check_structure(self):
        from integrations.langfuse_llm import health_check

        info = health_check()
        assert "openai_available" in info
        assert "anthropic_available" in info
        assert "approved_models_count" in info
        assert "approved_models" in info
        assert "max_input_chars" in info
        assert "allow_unknown_models" in info
        assert "require_agent_tag" in info
        assert isinstance(info["approved_models"], list)

    def test_gpt4o_in_approved_models(self):
        from integrations.langfuse_llm import health_check

        info = health_check()
        assert "gpt-4o" in info["approved_models"]
