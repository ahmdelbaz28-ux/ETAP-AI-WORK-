"""Tests for api/tool_policy.py — Tool Policy Engine (P1).

Covers:
- read tools           -> auto_approved
- mutating tools       -> auto_approved (with auto-approve) / pending (without)
- critical tools       -> always pending (even with auto-approve)
- unknown tools        -> deny-by-default critical -> pending
- denied agent-exec    -> rejected TOOL_DENIED_IN_AGENT_EXEC
- engineering params   -> rejected UNSOURCED_ENGINEERING_VALUE without source;
                          pass-through when a valid source is present.
"""

from __future__ import annotations

from api.tool_policy import (
    ENGINEERING_PARAMS,
    TOOL_DENIED_IN_AGENT_EXEC,
    TOOL_POLICIES,
    UNSOURCED_ENGINEERING_VALUE,
    evaluate_tool_policy,
    validate_engineering_source,
)

# ---------------------------------------------------------------------------
# Classification decisions
# ---------------------------------------------------------------------------


class TestClassification:
    def test_read_tool_auto_approved(self):
        result = evaluate_tool_policy("weather-tool", args={}, auto_approve_enabled=False)
        assert result["decision"] == "auto_approved"

    def test_read_tool_auto_approved_via_alias(self):
        # Actual Mastra id for weather-tool.ts is 'weather'.
        result = evaluate_tool_policy("weather", args={}, auto_approve_enabled=False)
        assert result["decision"] == "auto_approved"

    def test_mutating_auto_approved_when_enabled(self):
        result = evaluate_tool_policy(
            "run_python", args={"code": "print(1)"}, auto_approve_enabled=True
        )
        assert result["decision"] == "auto_approved"

    def test_mutating_pending_when_not_enabled(self):
        result = evaluate_tool_policy(
            "run_python", args={"code": "print(1)"}, auto_approve_enabled=False
        )
        assert result["decision"] == "pending"

    def test_mutating_via_hyphen_alias(self):
        # python-tool.ts id is 'run-python'.
        result = evaluate_tool_policy(
            "run-python", args={"code": "print(1)"}, auto_approve_enabled=True
        )
        assert result["decision"] == "auto_approved"

    def test_critical_always_pending_even_with_auto_approve(self):
        result = evaluate_tool_policy("provider-settings-tool", args={}, auto_approve_enabled=True)
        assert result["decision"] == "pending"

    def test_unknown_tool_deny_by_default_critical_pending(self):
        result = evaluate_tool_policy("some-unknown-tool", args={}, auto_approve_enabled=True)
        assert result["decision"] == "pending"
        assert result["reason"] == "critical tool requires approval"

    def test_unknown_tool_not_auto_approved(self):
        # Deny-by-default means unknown tools never auto-approve.
        result = evaluate_tool_policy("some-unknown-tool", args={}, auto_approve_enabled=True)
        assert result["decision"] != "auto_approved"


# ---------------------------------------------------------------------------
# Denied-in-agent-exec tools
# ---------------------------------------------------------------------------


class TestDeniedInAgentExec:
    def test_powershell_rejected_deny(self):
        result = evaluate_tool_policy(
            "powershell-tool", args={"command": "Get-Process"}, auto_approve_enabled=True
        )
        assert result["decision"] == "rejected"
        assert result["reason"] == TOOL_DENIED_IN_AGENT_EXEC

    def test_powershell_rejected_via_runtime_alias(self):
        result = evaluate_tool_policy(
            "run-powershell", args={"command": "Get-Process"}, auto_approve_enabled=True
        )
        assert result["decision"] == "rejected"
        assert result["reason"] == TOOL_DENIED_IN_AGENT_EXEC

    def test_node_tool_rejected_deny(self):
        result = evaluate_tool_policy("node-tool", args={}, auto_approve_enabled=True)
        assert result["decision"] == "rejected"
        assert result["reason"] == TOOL_DENIED_IN_AGENT_EXEC

    def test_deny_takes_precedence_over_engineering(self):
        # Even without a source, the deny rule fires first (immediate reject).
        result = evaluate_tool_policy(
            "powershell-tool",
            args={"command": "x", "protection_curve": 1.5},
            auto_approve_enabled=True,
        )
        assert result["decision"] == "rejected"
        assert result["reason"] == TOOL_DENIED_IN_AGENT_EXEC


# ---------------------------------------------------------------------------
# Engineering-source enforcement
# ---------------------------------------------------------------------------


class TestEngineeringSource:
    def _valid_sourced(self, kind: str) -> dict:
        return {"protection_curve": 0.14, "source": {"kind": kind}}

    def test_engineering_without_source_rejected(self):
        result = evaluate_tool_policy(
            "weather-tool", args={"protection_curve": 0.14}, auto_approve_enabled=False
        )
        assert result["decision"] == "rejected"
        assert result["reason"] == UNSOURCED_ENGINEERING_VALUE

    def test_engineering_with_valid_source_passes_on_read(self):
        args = self._valid_sourced("user_input")
        result = evaluate_tool_policy("weather-tool", args=args, auto_approve_enabled=False)
        assert result["decision"] == "auto_approved"

    def test_engineering_with_valid_source_passes_on_mutating(self):
        args = {"code": "print(1)", "protection_curve": 0.14, "source": {"kind": "computed"}}
        result = evaluate_tool_policy("run_python", args=args, auto_approve_enabled=False)
        assert result["decision"] == "pending"

    def test_invalid_source_kind_rejected(self):
        args = {"protection_curve": 0.14, "source": {"kind": "guessed"}}
        result = evaluate_tool_policy("weather-tool", args=args, auto_approve_enabled=False)
        assert result["decision"] == "rejected"
        assert result["reason"] == UNSOURCED_ENGINEERING_VALUE

    def test_validate_engineering_source_no_notes(self):
        assert validate_engineering_source({"code": "print(1)"}, None) is True

    def test_validate_engineering_source_no_notes_no_args(self):
        assert validate_engineering_source({}, None) is True


# ---------------------------------------------------------------------------
# Data integrity
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_all_required_engineering_params_registered(self):
        required = [
            "protection_curve",
            "relay_settings",
            "ct_ratio",
            "vt_ratio",
            "cable_ampacity",
            "transformer_impedance",
            "fault_level",
            "voltage_setpoint",
            "load_flow_limit",
            "short_circuit_level",
            "protection_coordination",
            "earth_fault_setting",
            "soil_resistivity",
            "conductor_size",
            "fault_clearing_time",
            "working_distance",
            "bolted_fault_current",
            "electrode_config",
        ]
        for param in required:
            assert param in ENGINEERING_PARAMS

    def test_required_tools_registered(self):
        for name in [
            "weather-tool",
            "run_python",
            "powershell-tool",
            "node-tool",
            "provider-settings-tool",
        ]:
            assert name in TOOL_POLICIES
