"""
tests/test_prompt_registry.py — Unit tests for PromptRegistry & A/B Measurement.
"""

import pytest
from api.prompt_registry import (
    PromptRegistry,
    get_prompt_registry,
    reset_prompt_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_prompt_registry()
    yield
    reset_prompt_registry()


def test_register_and_automatic_activation():
    reg = PromptRegistry()
    v1 = reg.register_version(
        agent_handle="load_flow_agent",
        prompt_text="You are a load flow specialist. Analyze Newton-Raphson power flow.",
        temperature=0.2,
    )
    assert v1.version_id == "load_flow_agent:v1"
    assert v1.is_active is True

    # Registering a second version without is_active=True leaves v1 active
    v2 = reg.register_version(
        agent_handle="load_flow_agent",
        prompt_text="Optimized concise prompt for load flow.",
        temperature=0.1,
    )
    assert v2.version_id == "load_flow_agent:v2"
    assert v2.is_active is False

    active = reg.get_active_version("load_flow_agent")
    assert active is not None
    assert active.version_id == "load_flow_agent:v1"


def test_ab_traffic_split_routing():
    reg = PromptRegistry()
    reg.register_version("arcflash_agent", "Base arc flash prompt.")
    reg.register_version("arcflash_agent", "Candidate compact arc flash prompt.")

    # With 0% candidate traffic, always returns active (v1)
    for _ in range(20):
        ver = reg.get_active_version("arcflash_agent", candidate_traffic_pct=0.0)
        assert ver.version_id == "arcflash_agent:v1"

    # With 100% candidate traffic, always returns candidate (v2)
    for _ in range(20):
        ver = reg.get_active_version("arcflash_agent", candidate_traffic_pct=100.0)
        assert ver.version_id == "arcflash_agent:v2"


def test_record_metrics_and_tradeoff_report():
    reg = PromptRegistry()
    v1 = reg.register_version("short_circuit_agent", "Base prompt (verbose)")
    v2 = reg.register_version("short_circuit_agent", "Candidate prompt (concise)")

    # Record metrics for v1 (baseline)
    reg.record_metrics(v1.version_id, tokens_used=2000, latency_ms=450.0, success=True, quality_score=0.95)
    reg.record_metrics(v1.version_id, tokens_used=2200, latency_ms=470.0, success=True, quality_score=0.93)

    # Record metrics for v2 (candidate - 50% token reduction)
    reg.record_metrics(v2.version_id, tokens_used=1050, latency_ms=250.0, success=True, quality_score=0.96)
    reg.record_metrics(v2.version_id, tokens_used=1050, latency_ms=260.0, success=True, quality_score=0.94)

    report = reg.get_tradeoff_report("short_circuit_agent")
    assert "short_circuit_agent" in report
    sc_data = report["short_circuit_agent"]
    assert sc_data["total_versions"] == 2

    versions = sc_data["versions"]
    # v1 baseline has 0% savings
    assert versions[0]["version_id"] == "short_circuit_agent:v1"
    assert versions[0]["metrics"]["avg_tokens"] == 2100.0
    assert versions[0]["metrics"]["call_count"] == 2
    assert versions[0]["metrics"]["success_rate"] == 1.0

    # v2 candidate achieves ~50% savings
    assert versions[1]["version_id"] == "short_circuit_agent:v2"
    assert versions[1]["metrics"]["avg_tokens"] == 1050.0
    assert versions[1]["token_savings_pct"] == 50.0
    assert versions[1]["metrics"]["avg_quality_score"] == 0.95


def test_promote_version():
    reg = PromptRegistry()
    v1 = reg.register_version("protection_agent", "Base prompt")
    v2 = reg.register_version("protection_agent", "Candidate prompt")

    assert reg.get_active_version("protection_agent").version_id == "protection_agent:v1"

    promoted = reg.promote_version(v2.version_id)
    assert promoted is True

    assert reg.get_active_version("protection_agent").version_id == "protection_agent:v2"


def test_promote_nonexistent_version_returns_false():
    reg = PromptRegistry()
    assert reg.promote_version("unknown_agent:v99") is False
