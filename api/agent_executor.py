"""
api/agent_executor.py — Secure Agent Execution Path (P4a).

The narrow gateway through which an autonomous agent may turn a *tool plan*
into real work:

* ``POST /api/v1/agent-exec/plan``     — submit a :class:`ToolPlan` for vetting.
  Runs the Tool Policy Engine (:func:`api.tool_policy.evaluate_tool_policy`),
  enforces engineering provenance and refuses tools denied for agent exec.
* ``POST /api/v1/agent-exec/execute``  — execute a previously vetted plan by
  ``plan_id``, guarded by an ``Idempotency-Key`` header (single logical run;
  replays return the stored response with ``idempotent_replay: true``).

Security invariants (all enforced server-side, per request):

1. Tools flagged ``deny_in_agent_exec`` (and the hard-denied constant list
   ``powershell-tool`` / ``node-tool``) are rejected at /plan AND re-checked
   at /execute — belt and braces, independent of the policy table contents.
2. Engineering values must carry provenance: when the tool policy marks the
   tool ``requires_engineering_source`` OR any argument key appears in
   ``ENGINEERING_PARAMS``, a valid ``source.kind``
   (user_input | project_data | computed | standard) is mandatory,
   otherwise the plan is refused with 422 ``UNSOURCED_ENGINEERING_VALUE``.
   Agents/LLMs may never invent engineering numbers.
3. Plans are ephemeral (TTL ``PLAN_TTL_SECONDS = 300 s``); executing an
   expired plan is refused with 410 ``PLAN_EXPIRED``.
4. Only ``auto_approved`` plans reach execution; ``pending`` plans must go
   through the Approval Gateway first (409 ``APPROVAL_REQUIRED``).
5. Every endpoint requires a Bearer access token
   (:func:`api.dependencies.get_current_user_from_header`).

Streaming integration (P3): lifecycle events are published on the
:class:`api.session_stream.SessionStreamHub` for the plan's ``session_id``:
``action_proposed`` + ``approval_result`` for pending/rejected decisions,
``job_progress`` / ``result_ready`` around executions. Streaming is strictly
best-effort and never breaks the HTTP flow.

State note: plans / executions / idempotency reservations live in bounded
in-process registries (single-replica deployment, mirroring the WS-ticket
choice in api/session_stream.py). Multi-replica deployments swap these three
registries for Redis/DB backing behind the same helpers.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from api.dependencies import CurrentUser, get_current_user_from_header

from api.tool_policy import (
    ALLOWED_SOURCE_KINDS,
    ENGINEERING_PARAMS,
    TOOL_ALIASES,
    TOOL_DENIED_IN_AGENT_EXEC,
    UNSOURCED_ENGINEERING_VALUE,
    _resolve_policy,
    evaluate_tool_policy,
)

logger = logging.getLogger("api.agent_executor")

router = APIRouter(prefix="/api/v1/agent-exec", tags=["agent-exec"])

# ─── Configuration ─────────────────────────────────────────────────────────
PLAN_TTL_SECONDS = 300  # vetted plans live for 5 minutes
IDEMPOTENCY_TTL_SECONDS = 86400  # replay window: 24 h
MAX_REGISTRIES_PER_MAP = 4096  # self-prune threshold for every in-memory map

# Tools that must NEVER run through the agent loop, regardless of any future
# change to TOOL_POLICIES (e.g. someone deleting their registry entry).
HARD_DENIED_TOOLS = frozenset({"powershell-tool", "node-tool"})

EXECUTION_STATUS_COMPLETED = "completed"
EXECUTION_STATUS_FAILED = "failed"

# Reason codes surfaced by this module.
MISSING_IDEMPOTENCY_KEY = "MISSING_IDEMPOTENCY_KEY"
PLAN_NOT_FOUND = "PLAN_NOT_FOUND"
PLAN_EXPIRED = "PLAN_EXPIRED"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
IDEMPOTENCY_KEY_CONFLICT = "IDEMPOTENCY_KEY_CONFLICT"
NO_EXECUTOR_REGISTERED = "NO_EXECUTOR_REGISTERED"


def _utc_ts() -> float:
    return time.time()


def _canonical_tool(tool_name: str) -> str:
    """Map a Mastra-style alias onto its canonical policy key."""
    return TOOL_ALIASES.get(tool_name, tool_name)


# ─── Request models ────────────────────────────────────────────────────────


class EngineeringSource(BaseModel):
    """Provenance of an engineering value (who/what produced it)."""

    kind: str
    ref: Optional[str] = Field(
        default=None,
        description="Free-form reference: standard clause, dataset id, hash, ...",
    )


class ToolPlan(BaseModel):
    """A single tool invocation proposed by an agent."""

    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[EngineeringSource] = None
    session_id: Optional[str] = None
    tenant_id: Optional[str] = None


class ExecuteRequest(BaseModel):
    plan_id: str


# ─── In-memory registries ──────────────────────────────────────────────────


@dataclass
class PlanRecord:
    plan_id: str
    tool: str  # canonical name
    requested_tool: str  # exactly as the caller wrote it
    args: Dict[str, Any] = field(default_factory=dict)
    source: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    decision: str = ""
    reason: str = ""
    created_at: float = 0.0
    expires_at: float = 0.0


@dataclass
class ExecutionRecord:
    execution_id: str
    plan_id: str
    tool: str
    status: str
    result: Dict[str, Any] = field(default_factory=dict)
    started_at: float = 0.0
    finished_at: float = 0.0


_PLANS: Dict[str, PlanRecord] = {}
_EXECUTIONS: Dict[str, ExecutionRecord] = {}
# key -> {"plan_id": str, "response": dict|None, "expires_at": float,
#         "done": Optional[asyncio.Event]}
_IDEMPOTENCY: Dict[str, Dict[str, Any]] = {}

ExecutorFn = Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]]
_EXECUTORS: Dict[str, ExecutorFn] = {}


def register_executor(tool_name: str, fn: ExecutorFn) -> None:
    """Register the coroutine ``(args, ctx) -> result`` that runs *tool*."""
    _EXECUTORS[_canonical_tool(tool_name)] = fn


def reset_agent_exec_state() -> None:
    """Test/deploy helper — drop plans, executions, idempotency + executors."""
    _PLANS.clear()
    _EXECUTIONS.clear()
    _IDEMPOTENCY.clear()
    _EXECUTORS.clear()


def _prune_registries(now: float) -> None:
    """Self-prune so long-lived processes cannot grow without bound."""
    for pmap in (_PLANS, _IDEMPOTENCY):
        if len(pmap) <= MAX_REGISTRIES_PER_MAP:
            continue
        for k in [
            k for k, v in pmap.items() if isinstance(v, dict) and v.get("expires_at", 0) <= now
        ]:
            pmap.pop(k, None)


def _http_error(code: str, message: str, http_status: int) -> HTTPException:
    """Consistent error envelope: ``{"detail": {"code", "message"}}``."""
    return HTTPException(
        status_code=http_status, detail={"code": code, "message": message}
    )


def get_plan(plan_id: str) -> Optional[PlanRecord]:
    """Return a live (non-expired) plan record, or ``None``."""
    rec = _PLANS.get(plan_id)
    if rec is None or rec.expires_at <= _utc_ts():
        return None
    return rec


# ─── Session-stream bridge (P3) ────────────────────────────────────────────


async def _emit(session_id: Optional[str], etype: str, payload: Dict[str, Any]) -> None:
    """Best-effort publish on the session stream hub (never raises)."""
    if not session_id:
        return
    try:  # pragma: no cover - exercised via live WS tests in P3 suite
        from api.session_stream import get_hub

        # publish() is sync + thread-safe; it fans out and records the event.
        get_hub().publish(session_id, etype, dict(payload))
    except Exception:  # noqa: BLE001 — streaming must never break HTTP flow

        logger.debug("session-stream emit failed (%s)", etype, exc_info=True)


# ─── /plan ─────────────────────────────────────────────────────────────────


def _source_enforcement_required(policy: Dict[str, Any], args_keys: set) -> bool:
    """True when this invocation MUST carry a provenance source object."""
    if policy.get("requires_engineering_source"):
        return True
    return any(key in ENGINEERING_PARAMS for key in args_keys)


@router.post("/plan", summary="Vet an agent tool plan")
async def submit_plan(
    plan: ToolPlan,
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
) -> Dict[str, Any]:
    """Vet a :class:`ToolPlan` against the Tool Policy Engine.

    Returns ``{plan_id, decision, reason}`` where decision is
    ``auto_approved`` | ``pending`` | ``rejected``.
    """
    now = _utc_ts()
    _prune_registries(now)

    requested_tool = plan.tool
    canonical = _canonical_tool(requested_tool)
    policy = _resolve_policy(canonical)
    raw_args: Dict[str, Any] = dict(plan.args or {})
    src_dict: Optional[Dict[str, Any]] = (
        {"kind": plan.source.kind, "ref": plan.source.ref} if plan.source else None
    )

    # ── Gate 1: hard-denied tools (independent of the policy table) ───────
    if (
        policy.get("deny_in_agent_exec")
        or canonical in HARD_DENIED_TOOLS
        or requested_tool in HARD_DENIED_TOOLS
    ):
        reason = TOOL_DENIED_IN_AGENT_EXEC
        decision = "rejected"
        await _emit(
            plan.session_id,
            "action_proposed",
            {"tool": canonical, "requested_tool": requested_tool},
        )
        await _emit(
            plan.session_id,
            "approval_result",
            {"tool": canonical, "decision": decision, "reason": reason},
        )
        raise _http_error(
            TOOL_DENIED_IN_AGENT_EXEC,
            f"Tool '{requested_tool}' may never be executed by an agent.",
            status.HTTP_403_FORBIDDEN,
        )

    # ── Gate 2: engineering-source enforcement ───────────────────────────
    if _source_enforcement_required(policy, set(raw_args.keys())):
        kinds_ok = bool(src_dict) and src_dict.get("kind") in ALLOWED_SOURCE_KINDS
        if not kinds_ok:
            decision = "rejected"
            reason = UNSOURCED_ENGINEERING_VALUE
            await _emit(
                plan.session_id,
                "action_proposed",
                {"tool": canonical, "requested_tool": requested_tool},
            )
            await _emit(
                plan.session_id,
                "approval_result",
                {"tool": canonical, "decision": decision, "reason": reason},
            )
            raise _http_error(
                UNSOURCED_ENGINEERING_VALUE,
                "Engineering parameter(s) require a valid source.kind "
                "(user_input | project_data | computed | standard).",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

    # ── Gate 3: Tool Policy Engine evaluation ────────────────────────────
    # evaluate_tool_policy reads the provenance envelope from inside args,
    # so merge the plan-level source in for evaluation only (stored args
    # remain exactly as the caller sent them).
    eval_args: Dict[str, Any] = dict(raw_args)
    if src_dict is not None:
        eval_args.setdefault("source", src_dict)
    from api.approvals import get_session_auto_approve

    decision_result = evaluate_tool_policy(
        tool_name=canonical,
        args=eval_args,
        auto_approve_enabled=get_session_auto_approve(plan.session_id or ""),
    )
    decision = decision_result["decision"]
    reason = decision_result["reason"]

    plan_id = f"plan_{uuid.uuid4().hex}"
    _PLANS[plan_id] = PlanRecord(
        plan_id=plan_id,
        tool=canonical,
        requested_tool=requested_tool,
        args=raw_args,
        source=src_dict,
        session_id=plan.session_id,
        tenant_id=plan.tenant_id or user.tenant_id,
        user_id=user.user_id,
        decision=decision,
        reason=reason,
        created_at=now,
        expires_at=now + PLAN_TTL_SECONDS,
    )

    if decision != "auto_approved":
        await _emit(
            plan.session_id,
            "action_proposed",
            {
                "tool": canonical,
                "requested_tool": requested_tool,
                "plan_id": plan_id,
            },
        )
        await _emit(
            plan.session_id,
            "approval_result",
            {"tool": canonical, "decision": decision, "reason": reason, "plan_id": plan_id},
        )

    return {
        "plan_id": plan_id,
        "decision": decision,
        "reason": reason,
    }


# ─── /execute ──────────────────────────────────────────────────────────────


async def _resolve_idempotency(
    key: str, plan_id: str
) -> Optional[Dict[str, Any]]:
    """Return a replayable payload, or reserve *key* for a fresh execution.

    - miss                      -> None (caller executes; key now reserved)
    - hit on same plan          -> stored response (or wait for the in-flight
                                   run to finish) with ``idempotent_replay``
    - hit on a different plan   -> HTTPException 409 conflict
    """
    existing = _IDEMPOTENCY.get(key)
    if existing is None:
        _IDEMPOTENCY[key] = {
            "plan_id": plan_id,
            "response": None,
            "expires_at": _utc_ts() + IDEMPOTENCY_TTL_SECONDS,
            "done": asyncio.Event(),
        }
        return None

    if existing.get("plan_id") != plan_id:
        raise _http_error(
            IDEMPOTENCY_KEY_CONFLICT,
            "Idempotency-Key was already used for a different plan.",
            status.HTTP_409_CONFLICT,
        )

    response = existing.get("response")
    if response is not None:
        return {**response, "idempotent_replay": True}

    done: Optional[asyncio.Event] = existing.get("done")
    if done is not None:
        # A concurrent execution holds this key; wait for its result.
        try:
            await asyncio.wait_for(done.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            pass
        response = existing.get("response")
        if response is not None:
            return {**response, "idempotent_replay": True}
    raise _http_error(
        IDEMPOTENCY_KEY_CONFLICT,
        "Idempotency-Key is currently in flight for another request.",
        status.HTTP_409_CONFLICT,
    )


def _finish_idempotent(key: str, payload: Dict[str, Any]) -> None:
    entry = _IDEMPOTENCY.get(key)
    if entry is None:
        return
    entry["response"] = payload
    done = entry.get("done")
    if done is not None:
        done.set()


@router.post("/execute", summary="Execute a vetted agent tool plan")
async def execute_plan(
    body: ExecuteRequest,
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),  # noqa: B008
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
) -> Dict[str, Any]:
    """Execute a previously vetted plan exactly once per Idempotency-Key."""
    if not idempotency_key:
        raise _http_error(
            MISSING_IDEMPOTENCY_KEY,
            "The Idempotency-Key header is required for /agent-exec/execute.",
            status.HTTP_400_BAD_REQUEST,
        )
    replay = await _resolve_idempotency(idempotency_key, body.plan_id)
    if replay is not None:
        return replay

    plan_rec = get_plan(body.plan_id)
    if plan_rec is None:
        # Distinguish "never existed" (404) from "expired" (410).
        if body.plan_id in _PLANS:
            raise _http_error(
                PLAN_EXPIRED,
                "Plan has expired (TTL 300 s). Submit a new /plan.",
                status.HTTP_410_GONE,
            )
        raise _http_error(
            PLAN_NOT_FOUND,
            f"Plan '{body.plan_id}' not found.",
            status.HTTP_404_NOT_FOUND,
        )

    # ── Decision gate: only auto-approved plans may execute ───────────────
    if plan_rec.decision != "auto_approved":
        await _emit(
            plan_rec.session_id,
            "approval_result",
            {
                "tool": plan_rec.tool,
                "decision": plan_rec.decision,
                "reason": plan_rec.reason,
                "plan_id": plan_rec.plan_id,
                "execution_blocked": True,
            },
        )
        raise _http_error(
            APPROVAL_REQUIRED,
            f"Plan decision is '{plan_rec.decision}'; execution requires an "
            "approved plan (Approval Gateway).",
            status.HTTP_409_CONFLICT,
        )

    # ── Belt-and-braces: hard-denied tools never execute, even if a plan
    #    record somehow reached this point (e.g. policy table edited later).
    if plan_rec.tool in HARD_DENIED_TOOLS or plan_rec.requested_tool in HARD_DENIED_TOOLS:
        raise _http_error(
            TOOL_DENIED_IN_AGENT_EXEC,
            f"Tool '{plan_rec.requested_tool}' may never be executed by an agent.",
            status.HTTP_403_FORBIDDEN,
        )

    executor = _EXECUTORS.get(plan_rec.tool)
    if executor is None:
        raise _http_error(
            NO_EXECUTOR_REGISTERED,
            f"No executor registered for tool '{plan_rec.tool}'.",
            status.HTTP_501_NOT_IMPLEMENTED,
        )

    execution_id = f"exec_{uuid.uuid4().hex}"
    started = _utc_ts()
    _EXECUTIONS[execution_id] = ExecutionRecord(
        execution_id=execution_id,
        plan_id=plan_rec.plan_id,
        tool=plan_rec.tool,
        status="running",
        started_at=started,
    )

    await _emit(
        plan_rec.session_id,
        "job_progress",
        {
            "execution_id": execution_id,
            "plan_id": plan_rec.plan_id,
            "phase": "parsing",
            "pct": 5,
            "tool": plan_rec.tool,
        },
    )

    ctx = {
        "user_id": user.user_id,
        "tenant_id": plan_rec.tenant_id or user.tenant_id,
        "session_id": plan_rec.session_id,
        "execution_id": execution_id,
        "plan_id": plan_rec.plan_id,
    }

    try:
        result = await executor(plan_rec.args, ctx)
        _EXECUTIONS[execution_id].status = EXECUTION_STATUS_COMPLETED
        _EXECUTIONS[execution_id].result = result
    except Exception as exc:  # noqa: BLE001 — surface as failed execution
        logger.exception("agent-exec tool '%s' failed", plan_rec.tool)
        _EXECUTIONS[execution_id].status = EXECUTION_STATUS_FAILED
        payload = {
            "success": False,
            "data": {
                "execution_id": execution_id,
                "status": EXECUTION_STATUS_FAILED,
                "error_code": "EXECUTION_FAILED",
            },
        }
        _finish_idempotent(idempotency_key, payload)
        await _emit(
            plan_rec.session_id,
            "job_progress",
            {
                "execution_id": execution_id,
                "phase": "failed",
                "pct": 100,
                "tool": plan_rec.tool,
                "error": str(exc),
            },
        )
        return payload

    await _emit(
        plan_rec.session_id,
        "job_progress",
        {
            "execution_id": execution_id,
            "phase": "validating",
            "pct": 85,
            "tool": plan_rec.tool,
        },
    )
    result_id = f"res_{uuid.uuid4().hex}"
    payload = {
        "success": True,
        "data": {
            "execution_id": execution_id,
            "status": EXECUTION_STATUS_COMPLETED,
            "result_id": result_id,
            "tool": plan_rec.tool,
        },
    }
    _EXECUTIONS[execution_id].finished_at = _utc_ts()
    _finish_idempotent(idempotency_key, payload)
    await _emit(
        plan_rec.session_id,
        "job_progress",
        {"execution_id": execution_id, "phase": "completed", "pct": 100},
    )
    await _emit(
        plan_rec.session_id,
        "result_ready",
        {
            "execution_id": execution_id,
            "result_id": result_id,
            "tool": plan_rec.tool,
            "plan_id": plan_rec.plan_id,
        },
    )
    return payload


# ─── Built-in study executor (run_python → orchestrator) ──────────────────


async def _run_python_executor(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a study through ChiefEngineeringOrchestrator.execute_autonomous_workflow.

    ``args`` may carry the user goal and power-system model:
      - goal: natural-language objective (default derived from ctx)
      - system: power-system model dict (default minimal valid system)
    The session id is propagated inside parameters so the P3 JobProgress
    bridge streams job_progress/result_ready for this execution.
    """
    from agents.orchestrator import ChiefEngineeringOrchestrator

    system_data = args.get("system")
    if not isinstance(system_data, dict) or not system_data:
        system_data = {
            "base_mva": 100.0,
            "buses": [
                {"id": "BUS-1", "type": "slack", "voltage_kv": 132.0},
                {"id": "BUS-2", "type": "pq", "voltage_kv": 33.0, "load_mw": 40.0},
            ],
            "lines": [
                {
                    "from_bus": "BUS-1",
                    "to_bus": "BUS-2",
                    "r_pu": 0.02,
                    "x_pu": 0.08,
                }
            ],
        }

    parameters = dict(args.get("parameters") or {})
    if ctx.get("session_id"):
        parameters.setdefault("session_id", ctx["session_id"])

    orchestrator = ChiefEngineeringOrchestrator()
    return await orchestrator.execute_autonomous_workflow(
        user_goal=str(args.get("goal") or f"agent-exec tool run ({ctx.get('execution_id')})"),
        system_data=system_data,
        parameters=parameters,
    )


register_executor("run_python", _run_python_executor)








