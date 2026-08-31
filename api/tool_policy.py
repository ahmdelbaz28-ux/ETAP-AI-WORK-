"""
api/tool_policy.py — Tool Policy Engine.

Classifies agent tools as read / mutating / critical so that tool calls
receive an explicit decision: ``auto_approved``, ``pending`` (human approval
required), or ``rejected``. Enforces **deny-by-default**: any tool that is not
explicitly registered is treated as ``critical`` (highest risk) and therefore
always ``pending``.

Why this exists
---------------
The Mastra agent runtime (TypeScript) exposes several execution tools
(``src/mastra/tools/*``): ``weather-tool``, ``run_python``,
``powershell-tool``, ``node-tool``, ``provider-settings-tool``. Before an agent
action (or an API client) is allowed to proceed, the backend evaluates the
tool against this policy. Tools that mutate state or run code in a sandbox are
either auto-approved (when the client has approved auto-run) or held for
approval. Tools that are too dangerous to ever run inside an autonomous agent
(``powershell-tool``, ``node-tool``) are rejected outright.

Deny-by-default
---------------
Any tool name not present in ``TOOL_POLICIES`` (and not resolvable via
``TOOL_ALIASES``) falls back to ``critical`` and is always ``pending``.

Engineering-source enforcement
-------------------------------
Any argument key listed in ``ENGINEERING_PARAMS`` MUST be backed by a
``source`` object whose ``kind`` is one of the allowed provenance values
(``user_input``, ``project_data``, ``computed``, ``standard``). An engineering
value without a valid source is rejected with ``UNSOURCED_ENGINEERING_VALUE`` —
agents/LLMs must never guess engineering parameters.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

# ─── Tool registry (deny-by-default) ───────────────────────────────────────
# Canonical tool policies. Keyed by the names used by callers; unknown tools
# fall through to a `critical` default.
TOOL_POLICIES: dict[str, dict[str, Any]] = {
    "weather-tool": {
        "classification": "read",
        "deny_in_agent_exec": False,
    },
    "run_python": {
        "classification": "mutating",
        "deny_in_agent_exec": False,
    },
    "powershell-tool": {
        "classification": "critical",
        "deny_in_agent_exec": True,
    },
    "node-tool": {
        "classification": "critical",
        "deny_in_agent_exec": True,
    },
    "provider-settings-tool": {
        "classification": "critical",
        "deny_in_agent_exec": False,
    },
}

# Alias map: actual Mastra tool names (variable names / `id` strings seen in
# src/mastra/tools/*) -> canonical policy key above. This keeps the engine
# working regardless of whether a caller passes the file-style name
# (`weather-tool`) or the registered Mastra tool name (`weather` /
# `run-python` / ...).
TOOL_ALIASES: dict[str, str] = {
    # weather-tool.ts -> id 'weather'
    "weather": "weather-tool",
    # python-tool.ts -> export const run_python, id 'run-python'
    "run-python": "run_python",
    # powershell-tool.ts -> export const run_powershell, id 'run-powershell'
    "run-powershell": "powershell-tool",
    "run_powershell": "powershell-tool",
    # node-tool.ts -> export const run_node, id 'run-node'
    "run-node": "node-tool",
    "run_node": "node-tool",
    # provider-settings-tool.ts -> export const providerSettingsTool, id 'provider-settings'
    "provider-settings": "provider-settings-tool",
    "providerSettingsTool": "provider-settings-tool",
}

# Default fallback for unknown / unregistered tools (deny-by-default).
_DEFAULT_POLICY: dict[str, Any] = {
    "classification": "critical",
    "deny_in_agent_exec": False,
}

# Allowed provenance kinds for engineering parameters.
ALLOWED_SOURCE_KINDS: frozenset[str] = frozenset(
    {"user_input", "project_data", "computed", "standard"}
)


# ─── Engineering parameters that MUST be sourced ──────────────────────────
ENGINEERING_PARAMS: tuple[str, ...] = (
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
)

# Reason codes.
TOOL_DENIED_IN_AGENT_EXEC = "TOOL_DENIED_IN_AGENT_EXEC"
UNSOURCED_ENGINEERING_VALUE = "UNSOURCED_ENGINEERING_VALUE"


# ─── Evaluation logic ──────────────────────────────────────────────────────
def _resolve_policy(tool_name: str) -> dict[str, Any]:
    """Return the policy for a tool name, falling back to deny-by-default."""
    canonical = TOOL_ALIASES.get(tool_name, tool_name)
    return TOOL_POLICIES.get(canonical) or _DEFAULT_POLICY


def validate_engineering_source(args: dict, source: dict | None) -> bool:
    """Check that every engineering-typed argument carries a valid source.

    Returns ``True`` when *no* engineering parameter is present in ``args``,
    or when a ``source`` dict with an allowed ``kind`` is supplied. Returns
    ``False`` (→ ``UNSOURCED_ENGINEERING_VALUE``) when an engineering
    parameter is present without a valid source.

    Security Gate: detection recurses into nested containers
    (dicts / lists, bounded depth) so an LLM cannot dodge provenance by
    wrapping a value as ``{"parameters": {"ct_ratio": 100}}`` instead of
    passing it top-level. The provenance ``source`` envelope itself remains
    a top-level sibling of the arguments it covers.
    """
    if not isinstance(args, dict):
        return True
    if not _contains_engineering_param(args):
        return True
    if not isinstance(source, dict):
        return False
    return source.get("kind") in ALLOWED_SOURCE_KINDS


# Bound the recursive scan so deeply-nested payloads cannot DoS the check.
_ENGINEERING_SCAN_MAX_DEPTH = 6


def _contains_engineering_param(value: Any, depth: int = 0) -> bool:
    """Recursively detect an ENGINEERING_PARAMS key inside *value*."""
    if depth > _ENGINEERING_SCAN_MAX_DEPTH:
        return False
    if isinstance(value, dict):
        for key, sub_value in value.items():
            if isinstance(key, str) and key in ENGINEERING_PARAMS:
                return True
            if _contains_engineering_param(sub_value, depth + 1):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_engineering_param(item, depth + 1) for item in value)
    return False


def evaluate_tool_policy(
    tool_name: str,
    args: dict,
    auto_approve_enabled: bool = False,
) -> dict[str, str]:
    """Evaluate whether a tool invocation is approved / pending / rejected.

    Args:
        tool_name: The tool to evaluate (canonical name or Mastra alias).
        args: Tool invocation arguments (may carry a ``source`` envelope).
        auto_approve_enabled: True when the caller has opted into auto-run for
            mutating tools.

    Returns:
        ``{"decision": "auto_approved"|"pending"|"rejected", "reason": str}``

    Rules (in order):
      1. Tools denied in agent exec (``powershell-tool``, ``node-tool``) are
         rejected immediately -> ``TOOL_DENIED_IN_AGENT_EXEC``.
      2. Engineering arguments without a valid source are rejected ->
         ``UNSOURCED_ENGINEERING_VALUE``.
      3. ``read`` tools -> ``auto_approved``.
      4. ``critical`` tools -> always ``pending`` (even with auto-approve).
      5. ``mutating`` tools -> ``auto_approved`` when ``auto_approve_enabled``
          is True, else ``pending``.
    """
    policy = _resolve_policy(tool_name)
    classification = policy.get("classification", "critical")

    # Rule 1 - deny tools that must never run inside an agent loop.
    if policy.get("deny_in_agent_exec"):
        return {"decision": "rejected", "reason": TOOL_DENIED_IN_AGENT_EXEC}

    # Rule 2 - engineering-source enforcement (no guessing).
    source = args.get("source") if isinstance(args, dict) else None
    if not validate_engineering_source(args, source):
        return {"decision": "rejected", "reason": UNSOURCED_ENGINEERING_VALUE}

    # Rule 3/4/5 - classification decision.
    if classification == "read":
        return {"decision": "auto_approved", "reason": "read-only tool auto-approved"}
    if classification == "critical":
        return {"decision": "pending", "reason": "critical tool requires approval"}
    # mutating (and any non-read/non-critical fallback)
    if auto_approve_enabled:
        return {"decision": "auto_approved", "reason": "mutating tool auto-approved"}
    return {"decision": "pending", "reason": "mutating tool requires approval"}


# ─── API surface (optional: registered in api/routes.py) ──────────────────
router = APIRouter(prefix="/api/v1/tool-policy", tags=["tool-policy"])


class ToolPolicyRequest(BaseModel):
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    auto_approve_enabled: bool = False


@router.post("/evaluate")
async def evaluate_endpoint(req: ToolPolicyRequest) -> dict[str, Any]:
    """Evaluate a tool invocation against the Tool Policy Engine."""
    result = evaluate_tool_policy(
        tool_name=req.tool_name,
        args=req.args,
        auto_approve_enabled=req.auto_approve_enabled,
    )
    return {"success": True, "data": result}
