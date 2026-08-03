"""
agents/output_schema_guard.py — Code-Gated Output Validation
============================================================

ARCHITECTURE AUDIT FIX (F-03): Enforces "mandatory" format rules from
prompt YAML files in CODE, not just prompt text.

The agent-architecture-audit found 14 prompt YAML files declaring
"Return format (mandatory)" and "MUST USE" rules with no code enforcement.
This module provides structured output validation that runs AFTER every
agent call, rejecting outputs that violate declared mandatory formats.

Usage:
    from agents.output_schema_guard import validate_agent_output

    result = agent.execute(...)
    guard_result = validate_agent_output("load_flow_agent", result)
    if not guard_result.passed:
        # Reject or retry — the model ignored a mandatory rule
        logger.error("Output violated mandatory format: %s", guard_result.violations)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class GuardViolation:
    """A single violation of a mandatory output rule."""

    rule_id: str
    description: str
    severity: str = "error"  # error | warning


@dataclass
class GuardResult:
    """Result of output schema validation."""

    agent_handle: str
    passed: bool
    violations: list[GuardViolation] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


# ─── Mandatory format rules per agent ──────────────────────────────────────
# These rules are extracted from the prompt YAML files that declare
# "Return format (mandatory)". Each rule is now code-gated.

MANDATORY_RULES: dict[str, list[dict[str, Any]]] = {
    "load_flow_agent": [
        {
            "rule_id": "LF-M1",
            "description": "Must contain bus voltage results (magnitude + angle)",
            "check": "dict_keys_contain",
            "required_keys": ["bus_results", "voltage"],
            "severity": "error",
        },
        {
            "rule_id": "LF-M2",
            "description": "Must contain convergence status",
            "check": "dict_keys_contain",
            "required_keys": ["converged"],
            "severity": "error",
        },
    ],
    "short_circuit_agent": [
        {
            "rule_id": "SC-M1",
            "description": "Must contain fault current results",
            "check": "dict_keys_contain",
            "required_keys": ["fault_results"],
            "severity": "error",
        },
    ],
    "arcflash_agent": [
        {
            "rule_id": "AF-M1",
            "description": "Must contain incident energy (cal/cm²)",
            "check": "dict_keys_contain",
            "required_keys": ["incident_energy"],
            "severity": "error",
        },
        {
            "rule_id": "AF-M2",
            "description": "Must use IEEE 1584-2018 method (declared mandatory in prompt)",
            "check": "field_value_contains",
            "key": "method",
            "expected_substring": "IEEE 1584",
            "severity": "warning",
        },
    ],
    "protection_agent": [
        {
            "rule_id": "PR-M1",
            "description": "Must contain relay coordination results",
            "check": "dict_keys_contain",
            "required_keys": ["coordination_results"],
            "severity": "error",
        },
    ],
    "cable_sizing_agent": [
        {
            "rule_id": "CS-M1",
            "description": "Must contain cable ampacity results",
            "check": "dict_keys_contain",
            "required_keys": ["cable_results"],
            "severity": "error",
        },
    ],
    "earth_grid_agent": [
        {
            "rule_id": "EG-M1",
            "description": "Must contain grounding grid results",
            "check": "dict_keys_contain",
            "required_keys": ["grid_results"],
            "severity": "error",
        },
    ],
    "fallback_agent": [
        {
            "rule_id": "FB-M1",
            "description": "MUST REFUSE life-safety calculations (prompt declares MUST REFUSE)",
            "check": "output_contains_refusal",
            "severity": "error",
        },
    ],
    "scada_agent": [
        {
            "rule_id": "SD-M1",
            "description": "GOOSE must use multicast (declared mandatory in prompt)",
            "check": "field_value_contains_if_present",
            "key": "goose_config",
            "expected_substring": "multicast",
            "severity": "warning",
        },
    ],
}


def _check_dict_keys_contain(
    data: dict, required_keys: list[str]
) -> list[str]:
    """Check that data dict contains all required keys (recursively)."""
    missing = []
    for key in required_keys:
        if key not in data:
            # Also check nested dicts
            found = False
            for v in data.values() if isinstance(data, dict) else []:
                if isinstance(v, dict) and key in v:
                    found = True
                    break
            if not found:
                missing.append(key)
    return missing


def _check_field_value_contains(
    data: dict, key: str, expected_substring: str
) -> bool:
    """Check that data[key] contains the expected substring."""
    value = data.get(key, "")
    return expected_substring in str(value)


def _check_output_contains_refusal(output: Any) -> bool:
    """Check that output contains refusal language for life-safety calculations."""
    text = ""
    if isinstance(output, str):
        text = output
    elif isinstance(output, dict):
        text = json.dumps(output)
    refusal_patterns = [
        r"refuse",
        r"cannot",
        r"must.*consult.*engineer",
        r"cannot.*perform.*safety",
        r"not.*qualified",
        r"professional.*engineer",
    ]
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in refusal_patterns)


def validate_agent_output(
    agent_handle: str,
    output: Any,
    strict: bool = False,
) -> GuardResult:
    """Validate agent output against declared mandatory format rules.

    Parameters
    ----------
    agent_handle : str
        The agent's prompt handle (e.g. "load_flow_agent").
    output : Any
        The agent's output data (dict or string).
    strict : bool
        If True, warning-level violations also cause failure.

    Returns
    -------
    GuardResult
        Passed=True if all mandatory rules are satisfied.
    """
    rules = MANDATORY_RULES.get(agent_handle, [])
    if not rules:
        # No mandatory rules declared for this agent — pass by default
        return GuardResult(agent_handle=agent_handle, passed=True)

    violations: list[GuardViolation] = []
    data = output if isinstance(output, dict) else {}

    for rule in rules:
        check_type = rule.get("check", "")
        severity = rule.get("severity", "error")

        if check_type == "dict_keys_contain":
            missing = _check_dict_keys_contain(data, rule.get("required_keys", []))
            if missing:
                violations.append(
                    GuardViolation(
                        rule_id=rule["rule_id"],
                        description=f"{rule['description']} — missing keys: {missing}",
                        severity=severity,
                    )
                )

        elif check_type == "field_value_contains":
            if not _check_field_value_contains(
                data, rule.get("key", ""), rule.get("expected_substring", "")
            ):
                violations.append(
                    GuardViolation(
                        rule_id=rule["rule_id"],
                        description=rule["description"],
                        severity=severity,
                    )
                )

        elif check_type == "field_value_contains_if_present":
            key = rule.get("key", "")
            if key in data and not _check_field_value_contains(
                data, key, rule.get("expected_substring", "")
            ):
                violations.append(
                    GuardViolation(
                        rule_id=rule["rule_id"],
                        description=rule["description"],
                        severity=severity,
                    )
                )

        elif check_type == "output_contains_refusal":
            if not _check_output_contains_refusal(output):
                violations.append(
                    GuardViolation(
                        rule_id=rule["rule_id"],
                        description=rule["description"],
                        severity=severity,
                    )
                )

    # Determine pass/fail
    error_violations = [v for v in violations if v.severity == "error"]
    warning_violations = [v for v in violations if v.severity == "warning"]

    passed = len(error_violations) == 0 and (not strict or len(warning_violations) == 0)

    if not passed:
        logger.warning(
            "Agent '%s' output violates %d mandatory rules: %s",
            agent_handle,
            len(violations),
            [v.rule_id for v in violations],
        )

    return GuardResult(
        agent_handle=agent_handle,
        passed=passed,
        violations=violations,
    )
