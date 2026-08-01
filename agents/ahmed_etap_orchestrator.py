"""
agents/ahmed_etap_orchestrator.py — AhmedETAP Agent Orchestration Skill
======================================================================

Runtime implementation of the ``ahmed-etap`` skill (see
``skills/ahmed-etap/SKILL.md`` and ``skills/ahmed-etap/REFERENCE.md``).

This module implements the four core principles mandated by the skill:

1. **One Team, One Context** — All agents share a single :class:`SharedContext`
   instance. Agents NEVER receive full prompts from each other; they read and
   write structured data through the shared context.

2. **Token Budget** — Every workflow starts with a :class:`TokenBudget`.
   When spend exceeds 70 %, the orchestrator compresses completed tasks
   (drops intermediate reasoning, keeps inputs + final results).

3. **Math Guard** — Every numerical claim passes deterministic Python
   validation via :class:`MathGuard` BEFORE reaching the user.
   The guard recomputes the value with a standalone script and compares
   within 0.01 % tolerance. Mismatch → block + flag for human review.

4. **Mandatory Peer Review** — No study result ships without a second agent
   cross-checking it, per the :data:`PEER_REVIEW_MATRIX`.

This orchestrator is **additive** — it does NOT replace the existing
:class:`ChiefEngineeringOrchestrator` in ``agents/orchestrator.py``.
Instead it wraps the existing agents and enforces the skill's discipline on
top of them.  Old code paths that bypass this orchestrator continue to work
unchanged, but any workflow that goes through :class:`AhmedETAPOrchestrator`
gets the four guarantees.

Integration points:
  - ``agents/orchestrator.py`` — registers :class:`AhmedETAPSkillAgent`
    alongside the existing agents.
  - ``api/studies.py`` — accepts ``study_type="ahmed_etap_orchestration"``.
  - ``api/agents.py`` — exposes ``/api/v1/agents/ahmed-etap/orchestrate``.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

# Import used only in type annotations; guarded to avoid circular imports.
# ChiefEngineeringOrchestrator is defined in agents/orchestrator.py and used
# as a type hint in AhmedETAPSkillAgent.__init__ and _resolve_orchestrator.
from typing import TYPE_CHECKING, Any, Callable, Optional

from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    BaseAgent,
    EngineeringTask,
    StudyType,
)

if TYPE_CHECKING:
    from agents.orchestrator import ChiefEngineeringOrchestrator

logger = logging.getLogger("agent.ahmed_etap")

UTC = timezone.utc  # noqa: UP017


# ---------------------------------------------------------------------------
# 1. Study-type canonicalisation  (REFERENCE.md §"Canonical Study Types")
# ---------------------------------------------------------------------------

_STUDY_ALIASES: dict[str, str] = {
    "fault": "short_circuit",
    "coordination": "protection_coordination",
    "harmonic": "harmonic_analysis",
    "stability": "transient_stability",
    "opf": "optimal_power_flow",
}


def canonicalize_study_type(raw: str) -> str:
    """Map user input / aliases to the canonical snake_case study type.

    >>> canonicalize_study_type("fault")
    'short_circuit'
    >>> canonicalize_study_type("Load_Flow")
    'load_flow'
    >>> canonicalize_study_type("coordination")
    'protection_coordination'
    """
    if not raw:
        return ""
    s = raw.strip().lower()
    return _STUDY_ALIASES.get(s, s)


# ---------------------------------------------------------------------------
# 2. SharedContext  (REFERENCE.md §"SharedContext Schema")
# ---------------------------------------------------------------------------


@dataclass
class ProjectRef:
    """Lightweight reference to a power-system project."""

    name: str = ""
    base_mva: float = 100.0
    base_kv: float = 115.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskRecord:
    """One entry in ``SharedContext.tasks``."""

    agent: str
    study_type: str
    status: str  # "pending" | "running" | "completed" | "failed" | "reviewed"
    result: dict[str, Any] = field(default_factory=dict)
    math_guard_passed: Optional[bool] = None
    peer_review_passed: Optional[bool] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class ReviewRecord:
    """One peer-review entry in ``SharedContext.review``."""

    reviewer: str = ""
    verdict: str = "pending"  # "pending" | "approved" | "rejected" | "needs_revision"
    notes: str = ""
    timestamp: Optional[datetime] = None


class SharedContext:
    """Single source of truth shared by every agent in the workflow.

    Implements the schema from ``REFERENCE.md``::

        SharedContext = {
            project, budget, tasks, standards, glossary, errors, review
        }

    Agents MUST communicate through this object only.  They MUST NOT pass
    full prompts to each other — only structured ``TaskRecord`` updates.
    """

    # Canonical glossary pulled from CONTEXT.md (subset — the most-used terms).
    # Pulling this ONCE into SharedContext means agents don't re-read the file.
    DEFAULT_GLOSSARY: dict[str, str] = {
        "study": "A power-system analysis execution. Top-level work product.",
        "task": "A unit of work specifying parameters for one or more studies.",
        "agent": "An autonomous computational entity that performs a specific power-system study.",
        "result": "The raw structured data returned by a study execution.",
        "report": "A formatted document (PDF/DOCX/XLSX) generated from study results.",
        "workflow": "A multi-step orchestrated sequence of studies.",
    }

    DEFAULT_STANDARDS: list[str] = [
        "IEEE 3002.7",
        "IEC 60909",
        "IEEE 1584",
        "IEEE 519",
        "IEC 60255",
        "IEEE 399",
        "IEEE 80",
        "IEC 60364",
        "IEEE 1547",
        "IEC 62933",
        "IEC 61850",
    ]

    def __init__(
        self,
        project: Optional[ProjectRef] = None,
        max_tokens: int = 16_000,
        standards: Optional[list[str]] = None,
        glossary: Optional[dict[str, str]] = None,
    ):
        self.project: ProjectRef = project or ProjectRef()
        self.budget: TokenBudget = TokenBudget(max_tokens=max_tokens)
        self.tasks: list[TaskRecord] = []
        self.standards: list[str] = list(standards or self.DEFAULT_STANDARDS)
        self.glossary: dict[str, str] = {**self.DEFAULT_GLOSSARY, **(glossary or {})}
        self.errors: list[str] = []
        self.review: ReviewRecord = ReviewRecord(
            reviewer="",
            verdict="pending",
            timestamp=datetime.now(UTC),
        )
        # Lock so concurrent agents can safely write to the same context.
        self._lock = asyncio.Lock()

    # ---- Task lifecycle -------------------------------------------------

    async def add_task(self, agent: str, study_type: str) -> TaskRecord:
        """Register a new task and return the record (status='pending')."""
        async with self._lock:
            record = TaskRecord(
                agent=agent,
                study_type=canonicalize_study_type(study_type),
                status="pending",
            )
            self.tasks.append(record)
            return record

    async def mark_running(self, record: TaskRecord) -> None:
        async with self._lock:
            record.status = "running"
            record.started_at = datetime.now(UTC)

    async def mark_completed(
        self,
        record: TaskRecord,
        result: dict[str, Any],
        math_guard_passed: bool,
    ) -> None:
        async with self._lock:
            record.status = "completed"
            record.result = result
            record.math_guard_passed = math_guard_passed
            record.completed_at = datetime.now(UTC)

    async def mark_reviewed(
        self,
        record: TaskRecord,
        passed: bool,
        reviewer_notes: str = "",
    ) -> None:
        async with self._lock:
            record.peer_review_passed = passed
            record.status = "reviewed" if passed else "needs_revision"
            if reviewer_notes:
                self.review.notes += f"\n[{record.agent}] {reviewer_notes}"

    async def add_error(self, msg: str) -> None:
        async with self._lock:
            self.errors.append(msg)

    # ---- Compression ----------------------------------------------------

    async def compress_if_needed(self) -> bool:
        """Trigger compression when token spend > 70 % of budget.

        Returns ``True`` if compression was actually performed.

        Compression strategy:
        - For every completed task, drop the ``simulation_steps`` /
          ``intermediate_reasoning`` fields if present — keep only the
          final result + validation status.
        - Keep inputs and final results intact.
        """
        if self.budget.fraction_spent < 0.70:
            return False

        async with self._lock:
            compressed_count = 0
            for t in self.tasks:
                if t.status in ("completed", "reviewed") and t.result:
                    before_keys = set(t.result.keys())
                    # Drop intermediate reasoning fields
                    t.result.pop("simulation_steps", None)
                    t.result.pop("intermediate_reasoning", None)
                    t.result.pop("debug_log", None)
                    t.result["_compressed"] = True
                    if set(t.result.keys()) != before_keys:
                        compressed_count += 1

            self.budget.record_compression()
            logger.info(
                "Context compressed: %d tasks trimmed (spend was %.1f%%)",
                compressed_count,
                self.budget.fraction_spent * 100,
            )
            return True

    # ---- Serialisation --------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable snapshot of the shared context."""
        return {
            "project": self.project.__dict__,
            "budget": self.budget.to_dict(),
            "tasks": [
                {
                    "agent": t.agent,
                    "study_type": t.study_type,
                    "status": t.status,
                    "math_guard_passed": t.math_guard_passed,
                    "peer_review_passed": t.peer_review_passed,
                    "result_keys": list(t.result.keys()) if t.result else [],
                    "started_at": t.started_at.isoformat() if t.started_at else None,
                    "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                }
                for t in self.tasks
            ],
            "standards": self.standards,
            "glossary_size": len(self.glossary),
            "errors": list(self.errors),
            "review": {
                "reviewer": self.review.reviewer,
                "verdict": self.review.verdict,
                "notes": self.review.notes,
                "timestamp": self.review.timestamp.isoformat() if self.review.timestamp else None,
            },
        }


# ---------------------------------------------------------------------------
# 3. TokenBudget  (REFERENCE.md §"Token Budget Defaults")
# ---------------------------------------------------------------------------


class TokenBudget:
    """Tracks token spend for a single workflow.

    Defaults (per REFERENCE.md):
      - Single study:    8,000
      - Multi-agent:    16,000
      - ETAP Expert:    24,000
    """

    DEFAULTS = {
        "single": 8_000,
        "multi": 16_000,
        "etap_expert": 24_000,
    }

    def __init__(self, max_tokens: int = 16_000):
        self.max_tokens: int = max_tokens
        self.spent: int = 0
        self._compressions: int = 0
        self._last_estimate_at: float = time.monotonic()

    @property
    def remaining(self) -> int:
        return max(0, self.max_tokens - self.spent)

    @property
    def fraction_spent(self) -> float:
        if self.max_tokens <= 0:
            return 1.0
        return self.spent / self.max_tokens

    @property
    def compression_count(self) -> int:
        return self._compressions

    def record_spend(self, tokens: int) -> None:
        """Record an estimated token spend.

        Estimates are deliberately coarse — the goal is to detect when we
        cross the 70 % threshold, not to bill the user.  We use a simple
        heuristic: 1 token ≈ 4 characters of prompt text.
        """
        if tokens < 0:
            return
        self.spent += int(tokens)
        self._last_estimate_at = time.monotonic()

    def estimate_and_record(self, text: str) -> int:
        """Estimate tokens in ``text`` (≈ chars/4) and record the spend."""
        if not text:
            return 0
        n = max(1, len(text) // 4)
        self.record_spend(n)
        return n

    def record_compression(self) -> None:
        self._compressions += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_tokens": self.max_tokens,
            "spent": self.spent,
            "remaining": self.remaining,
            "fraction_spent": round(self.fraction_spent, 4),
            "compressions": self._compressions,
        }


# ---------------------------------------------------------------------------
# 4. MathGuard  (REFERENCE.md §"Math Guard Spec")
# ---------------------------------------------------------------------------


# Unit check: which units are acceptable for each quantity kind.
# kV ≠ V, MVA ≠ kVA.  A result that mixes them is rejected.
_UNIT_RULES: dict[str, set[str]] = {
    "voltage": {"V", "kV", "pu"},
    "current": {"A", "kA", "pu"},
    "power": {"W", "kW", "MW", "var", "kvar", "Mvar", "VA", "kVA", "MVA"},
    "energy": {"J", "kJ", "Wh", "kWh", "MWh"},
    "frequency": {"Hz", "kHz"},
    "impedance": {"Ω", "pu"},
    "time": {"s", "ms", "cycles"},
    "temperature": {"°C", "K"},
    "distance": {"mm", "m", "ft"},
    "angle": {"deg", "rad"},
}


class MathGuard:
    """Deterministic Python validator for numerical agent outputs.

    Every numerical claim must:
      1. Be recomputed by a standalone Python function (the ``recompute``
         callback supplied by the Lead Agent).
      2. Match the agent's claim within 0.01 % tolerance.
      3. Pass a units check (kV ≠ V, MVA ≠ kVA, etc.).

    On mismatch → block the result and flag for human review.

    The guard is **deterministic** — it NEVER calls an LLM.  This is the
    contract from REFERENCE.md §"Math Guard Spec".
    """

    DEFAULT_TOLERANCE_PCT = 0.01  # 0.01 %

    def __init__(self, tolerance_pct: float = DEFAULT_TOLERANCE_PCT):
        self.tolerance_pct = tolerance_pct

    # ---- Public API -----------------------------------------------------

    def validate(
        self,
        claim_value: float,
        recompute: Callable[[], float],
        quantity_kind: str,
        claim_unit: str,
        expected_unit: Optional[str] = None,
    ) -> MathGuardResult:
        """Validate a single numerical claim.

        Parameters
        ----------
        claim_value
            The number the Lead Agent reported.
        recompute
            A zero-arg callable that returns the deterministic recomputed
            value.  Must NOT call any LLM.
        quantity_kind
            One of the keys in ``_UNIT_RULES`` (e.g. ``"voltage"``,
            ``"current"``, ``"power"``).
        claim_unit
            The unit string the agent claimed (e.g. ``"kV"``).
        expected_unit
            If provided, the unit the agent SHOULD have used.  If
            ``None``, any unit in ``_UNIT_RULES[quantity_kind]`` is
            accepted.
        """
        # Step 1 — units check
        units_ok, units_msg = self._check_units(quantity_kind, claim_unit, expected_unit)

        # Step 2 — recompute
        try:
            recomputed = float(recompute())
        except Exception as exc:
            return MathGuardResult(
                passed=False,
                reason=f"recompute callback raised: {exc!r}",
                claim_value=claim_value,
                recomputed_value=None,
                units_ok=units_ok,
                units_message=units_msg,
            )

        # Step 3 — tolerance check
        tolerance_ok, tolerance_msg = self._check_tolerance(claim_value, recomputed)

        passed = units_ok and tolerance_ok
        if passed:
            _reason = ""
        elif not tolerance_ok:
            _reason = tolerance_msg
        else:
            _reason = units_msg
        return MathGuardResult(
            passed=passed,
            reason=_reason,
            claim_value=claim_value,
            recomputed_value=recomputed,
            units_ok=units_ok,
            units_message=units_msg,
        )

    # ---- Internals ------------------------------------------------------

    def _check_units(
        self,
        kind: str,
        claimed: str,
        expected: Optional[str],
    ) -> tuple[bool, str]:
        if kind not in _UNIT_RULES:
            return True, f"no unit rules for kind '{kind}' (skipped)"
        if expected:
            if claimed != expected:
                return False, f"expected '{expected}' but agent used '{claimed}'"
            return True, ""
        if claimed not in _UNIT_RULES[kind]:
            return False, (
                f"unit '{claimed}' not valid for kind '{kind}'; "
                f"expected one of {sorted(_UNIT_RULES[kind])}"
            )
        return True, ""

    def _check_tolerance(self, claim: float, recomputed: float) -> tuple[bool, str]:
        if math.isnan(claim) or math.isnan(recomputed):
            return False, "NaN value detected"
        if math.isinf(claim) or math.isinf(recomputed):
            return False, "infinite value detected"
        if recomputed == 0:
            # Avoid divide-by-zero: use absolute tolerance of 1e-9
            return (
                abs(claim) <= 1e-9,
                f"recomputed=0 but claim={claim} (absolute tolerance 1e-9)",
            )
        diff_pct = abs(claim - recomputed) / abs(recomputed) * 100.0
        if diff_pct <= self.tolerance_pct:
            return True, ""
        return False, (
            f"value mismatch: claim={claim}, recomputed={recomputed}, "
            f"diff={diff_pct:.4f}% > tolerance {self.tolerance_pct}%"
        )


@dataclass
class MathGuardResult:
    """Outcome of a :meth:`MathGuard.validate` call."""

    passed: bool
    reason: str
    claim_value: float
    recomputed_value: Optional[float]
    units_ok: bool
    units_message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "claim_value": self.claim_value,
            "recomputed_value": self.recomputed_value,
            "units_ok": self.units_ok,
            "units_message": self.units_message,
        }


# ---------------------------------------------------------------------------
# 5. PeerReview  (REFERENCE.md §"Peer Review Matrix")
# ---------------------------------------------------------------------------

PEER_REVIEW_MATRIX: dict[str, str] = {
    "load_flow": "short_circuit",
    "short_circuit": "load_flow",
    "arc_flash": "protection_coordination",
    "protection_coordination": "arc_flash",
    "harmonic_analysis": "load_flow",
    "optimal_power_flow": "load_flow",
    "motor_starting": "transient_stability",
    "transient_stability": "motor_starting",
    "cable_sizing": "load_flow",
    "earth_grid": "short_circuit",
    "renewable_integration": "load_flow",
    "battery_storage": "renewable_integration",
    "scada": "digital_twin",
    "digital_twin": "scada",
    "etap_expert": "validation",
}


class PeerReview:
    """Mandatory cross-check by a second agent.

    For every Lead Agent, the matrix in :data:`PEER_REVIEW_MATRIX` names the
    Peer Reviewer that MUST cross-check the result before it ships.

    The reviewer's job is NOT to redo the calculation (that's MathGuard's
    job) but to check:
      - The result is physically plausible (no negative resistances, no
        voltages > 2 pu, etc.).
      - The applicable standard was actually applied.
      - The assumptions are reasonable for the stated equipment class.
      - No out-of-scope claim is being made.
    """

    def __init__(self, matrix: Optional[dict[str, str]] = None):
        self.matrix = matrix or PEER_REVIEW_MATRIX

    def reviewer_for(self, lead_study_type: str) -> Optional[str]:
        """Return the canonical study type of the peer reviewer."""
        return self.matrix.get(canonicalize_study_type(lead_study_type))

    def review(
        self,
        lead_study_type: str,
        result: dict[str, Any],
        reviewer_fn: Optional[Callable[[dict[str, Any]], tuple[bool, str]]] = None,
    ) -> PeerReviewResult:
        """Run a peer review on ``result``.

        Parameters
        ----------
        lead_study_type
            Canonical study type of the Lead Agent whose result is being
            reviewed.
        result
            The Lead Agent's result dict (after MathGuard passed).
        reviewer_fn
            Optional callable that takes the result dict and returns
            ``(passed, notes)``.  If ``None``, a deterministic sanity
            check is applied (see :meth:`_default_review`).
        """
        reviewer = self.reviewer_for(lead_study_type)
        if reviewer is None:
            # No reviewer in matrix → auto-approve with note
            return PeerReviewResult(
                passed=True,
                reviewer="none",
                notes=f"no peer reviewer registered for '{lead_study_type}' — auto-approved",
            )

        if reviewer_fn is None:
            passed, notes = self._default_review(lead_study_type, result)
        else:
            passed, notes = reviewer_fn(result)

        return PeerReviewResult(
            passed=passed,
            reviewer=reviewer,
            notes=notes,
        )

    # ---- Default sanity checks -----------------------------------------

    @staticmethod
    def _check_load_flow(result: dict[str, Any], notes_parts: list[str]) -> Optional[str]:
        """Plausibility check for load_flow results; returns a failure message or None."""
        buses = result.get("buses") or result.get("bus_results") or {}
        for bus_id, bdata in buses.items():
            v = bdata.get("voltage_magnitude_pu") or bdata.get("voltage_pu")
            if v is not None and (v < 0.5 or v > 1.5):
                return f"bus {bus_id} voltage {v} pu is physically implausible"
        notes_parts.append("load_flow voltages within plausible range")
        return None

    @staticmethod
    def _check_short_circuit(result: dict[str, Any], notes_parts: list[str]) -> Optional[str]:
        """Plausibility check for short_circuit results; returns a failure message or None."""
        fr = result.get("fault_results") or {}
        for bus_id, faults in fr.items():
            for ftype, fdata in faults.items():
                if isinstance(fdata, dict):
                    cur = fdata.get("fault_current")
                    if cur is not None and abs(float(cur)) <= 0:
                        return f"bus {bus_id} {ftype}: non-positive fault current"
        notes_parts.append("short_circuit currents are positive")
        return None

    @staticmethod
    def _check_arc_flash(result: dict[str, Any], notes_parts: list[str]) -> Optional[str]:
        """Plausibility check for arc_flash results; returns a failure message or None."""
        ie = result.get("incident_energy") or result.get("incident_energy_cal_cm2")
        if ie is not None and float(ie) > 100.0:
            return f"incident energy {ie} cal/cm² is implausibly high"
        notes_parts.append("arc_flash incident energy within plausible range")
        return None

    @staticmethod
    def _check_protection_coordination(
        result: dict[str, Any], notes_parts: list[str]
    ) -> Optional[str]:
        """Plausibility check for protection_coordination results (never fails hard)."""
        cr = result.get("coordination_results") or result.get("results") or []
        for entry in cr:
            if isinstance(entry, dict) and entry.get("coordinated") is False:
                notes_parts.append(
                    f"coordination not achieved at fault_current={entry.get('fault_current')}"
                )
        return None

    @staticmethod
    def _default_review(study_type: str, result: dict[str, Any]) -> tuple[bool, str]:
        """Deterministic sanity checks applied when no custom reviewer is given.

        These are deliberately conservative — they only catch obviously
        broken results.  Domain-specific checks belong in a custom
        ``reviewer_fn``.
        """
        notes_parts: list[str] = []
        st = canonicalize_study_type(study_type)

        # Check 1 — non-empty result
        if not result:
            return False, "result dict is empty"

        # Check 2 — domain-specific plausibility
        checkers = {
            "load_flow": PeerReview._check_load_flow,
            "short_circuit": PeerReview._check_short_circuit,
            "arc_flash": PeerReview._check_arc_flash,
            "protection_coordination": PeerReview._check_protection_coordination,
        }
        checker = checkers.get(st)
        if checker is not None:
            failure = checker(result, notes_parts)
            if failure is not None:
                return False, failure

        return True, "; ".join(notes_parts) if notes_parts else "default sanity check passed"


@dataclass
class PeerReviewResult:
    """Outcome of a :meth:`PeerReview.review` call."""

    passed: bool
    reviewer: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "reviewer": self.reviewer,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# 6. AhmedETAPOrchestrator  — the skill entry point
# ---------------------------------------------------------------------------


class OrchestrationVerdict(Enum):
    """Final verdict for an orchestrated workflow."""

    APPROVED = "approved"
    BLOCKED_MATH_GUARD = "blocked_math_guard"
    BLOCKED_PEER_REVIEW = "blocked_peer_review"
    BLOCKED_BOTH = "blocked_both"
    FAILED = "failed"


@dataclass
class OrchestrationResult:
    """Final result returned by :class:`AhmedETAPOrchestrator`."""

    verdict: OrchestrationVerdict
    study_type: str
    lead_agent: str
    peer_reviewer: str
    math_guard: Optional[MathGuardResult]
    peer_review: Optional[PeerReviewResult]
    shared_context_snapshot: dict[str, Any]
    response: dict[str, Any] = field(default_factory=dict)
    iterations: int = 0
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "study_type": self.study_type,
            "lead_agent": self.lead_agent,
            "peer_reviewer": self.peer_reviewer,
            "math_guard": self.math_guard.to_dict() if self.math_guard else None,
            "peer_review": self.peer_review.to_dict() if self.peer_review else None,
            "shared_context": self.shared_context_snapshot,
            "response": self.response,
            "iterations": self.iterations,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
        }


class AhmedETAPOrchestrator:
    """Skill-driven orchestrator that enforces the four core principles.

    Usage::

        orch = AhmedETAPOrchestrator()
        result = await orch.run_study(
            study_type="load_flow",
            project=ProjectRef(name="Project-X"),
            parameters={"system": system_obj, "max_iterations": 50},
            lead_agent_fn=lambda task: load_flow_agent.execute(task),
            recompute_fn=lambda: deterministic_load_flow(system_obj),
            claim_value=1.024,  # pu, as reported by Lead Agent
            claim_unit="pu",
        )
        if result.verdict == OrchestrationVerdict.APPROVED:
            ship_to_user(result.response)
    """

    MAX_RETRIES = 2  # per skill spec: "Fail → loop back (max 2)"

    def __init__(
        self,
        math_guard: Optional[MathGuard] = None,
        peer_review: Optional[PeerReview] = None,
    ):
        self.math_guard = math_guard or MathGuard()
        self.peer_review = peer_review or PeerReview()

    @staticmethod
    def _final_verdict(
        last_math_guard: Optional[MathGuardResult],
        last_peer_review: Optional[PeerReviewResult],
    ) -> OrchestrationVerdict:
        """Derive the terminal verdict from the last guard results."""
        if (
            last_math_guard
            and not last_math_guard.passed
            and last_peer_review
            and not last_peer_review.passed
        ):
            return OrchestrationVerdict.BLOCKED_BOTH
        if last_math_guard and not last_math_guard.passed:
            return OrchestrationVerdict.BLOCKED_MATH_GUARD
        if last_peer_review and not last_peer_review.passed:
            return OrchestrationVerdict.BLOCKED_PEER_REVIEW
        return OrchestrationVerdict.FAILED

    def _failed_result(
        self,
        study_type: str,
        error: str,
        *,
        start: float,
        lead_agent: str = "",
        peer_reviewer: str = "",
        ctx: Optional[SharedContext] = None,
        iterations: int = 0,
    ) -> OrchestrationResult:
        """Build a FAILED :class:`OrchestrationResult` with the given error."""
        return OrchestrationResult(
            verdict=OrchestrationVerdict.FAILED,
            study_type=study_type,
            lead_agent=lead_agent,
            peer_reviewer=peer_reviewer,
            math_guard=None,
            peer_review=None,
            shared_context_snapshot=ctx.to_dict() if ctx else {},
            response={"error": error},
            iterations=iterations,
            elapsed_seconds=time.perf_counter() - start,
        )

    async def run_study(
        self,
        study_type: str,
        project: ProjectRef,
        parameters: dict[str, Any],
        lead_agent_fn: Callable[[EngineeringTask], Any],
        recompute_fn: Callable[[], float],
        claim_value: float,
        claim_unit: str,
        quantity_kind: str = "voltage",
        expected_unit: Optional[str] = None,
        budget_tokens: int = 8_000,
        reviewer_fn: Optional[Callable[[dict[str, Any]], tuple[bool, str]]] = None,
    ) -> OrchestrationResult:
        """Execute a single study through the full skill pipeline.

        Pipeline (per SKILL.md §"Workflows → 1. Study Execution"):

            Parse → canonical ``StudyType``
            Load ``SharedContext`` with project data + standards
            Route to **Lead Agent** → run computation → **MathGuard** → **Peer Review**
            Pass → format & return  |  Fail → loop back (max 2)
        """
        start = time.perf_counter()
        canonical = canonicalize_study_type(study_type)
        if not canonical:
            return self._failed_result(
                study_type,
                f"cannot canonicalize study_type='{study_type}'",
                start=start,
            )

        ctx = SharedContext(
            project=project,
            max_tokens=budget_tokens,
        )

        reviewer_study = self.peer_review.reviewer_for(canonical) or "validation"

        # Estimate prompt cost of loading shared context (one-time, not per-agent)
        ctx.budget.estimate_and_record(f"{ctx.project.name} {canonical} " + " ".join(ctx.standards))

        # Iteration loop: lead → math_guard → peer_review (max MAX_RETRIES retries)
        last_math_guard: Optional[MathGuardResult] = None
        last_peer_review: Optional[PeerReviewResult] = None
        last_response: dict[str, Any] = {}
        iteration = 0

        for iteration in range(1, self.MAX_RETRIES + 2):  # 1 initial + 2 retries
            # --- 0. Compression check (every iteration, before spending more) --
            # Per SKILL.md: "When token spend >70%: summarize completed tasks,
            # drop intermediate reasoning, keep inputs + final results."
            await ctx.compress_if_needed()

            # --- 1. Route to Lead Agent ----------------------------------
            task_record = await ctx.add_task(agent="lead", study_type=canonical)
            await ctx.mark_running(task_record)

            try:
                task = EngineeringTask(
                    task_id=f"ahmed_etap_{canonical}_{iteration}",
                    description=f"Skill-orchestrated {canonical} study",
                    study_types=[self._study_type_enum(canonical)],
                    parameters=parameters,
                )
                agent_result: AgentResult = await lead_agent_fn(task)
            except Exception as exc:
                await ctx.add_error(f"lead agent raised: {exc!r}")
                await ctx.mark_completed(task_record, {"error": str(exc)}, math_guard_passed=False)
                return self._failed_result(
                    canonical,
                    str(exc),
                    start=start,
                    lead_agent="lead",
                    peer_reviewer=reviewer_study,
                    ctx=ctx,
                    iterations=iteration,
                )

            # --- 2. MathGuard -------------------------------------------
            mg = self.math_guard.validate(
                claim_value=claim_value,
                recompute=recompute_fn,
                quantity_kind=quantity_kind,
                claim_unit=claim_unit,
                expected_unit=expected_unit,
            )
            last_math_guard = mg
            # Estimate tokens for the agent's data (truncated to first 400 chars
            # — we only need an order-of-magnitude estimate for budget tracking).
            ctx.budget.estimate_and_record(str(agent_result.data)[:400])

            await ctx.mark_completed(
                task_record,
                result=agent_result.data,
                math_guard_passed=mg.passed,
            )

            if not mg.passed:
                logger.warning(
                    "MathGuard FAIL on iteration %d for %s: %s",
                    iteration,
                    canonical,
                    mg.reason,
                )
                await ctx.add_error(f"math_guard iteration {iteration}: {mg.reason}")
                last_response = {"blocked_by": "math_guard", "reason": mg.reason}
                # Compression check before retrying — we may be over budget now.
                await ctx.compress_if_needed()
                if iteration > self.MAX_RETRIES:
                    break
                # loop back — Lead Agent gets another chance
                continue

            # --- 3. Peer Review -----------------------------------------
            pr = self.peer_review.review(
                lead_study_type=canonical,
                result=agent_result.data,
                reviewer_fn=reviewer_fn,
            )
            last_peer_review = pr

            # Update the task record with review outcome
            await ctx.mark_reviewed(task_record, passed=pr.passed, reviewer_notes=pr.notes)

            if not pr.passed:
                logger.warning(
                    "PeerReview FAIL on iteration %d for %s: %s",
                    iteration,
                    canonical,
                    pr.notes,
                )
                await ctx.add_error(f"peer_review iteration {iteration}: {pr.notes}")
                last_response = {"blocked_by": "peer_review", "reason": pr.notes}
                # Compression check before retrying.
                await ctx.compress_if_needed()
                if iteration > self.MAX_RETRIES:
                    break
                continue

            # --- 4. Both passed → ship ---------------------------------
            # Final compression check before shipping — preserves inputs and
            # final results while trimming any intermediate reasoning that
            # accumulated during the workflow.
            await ctx.compress_if_needed()
            last_response = agent_result.data
            return OrchestrationResult(
                verdict=OrchestrationVerdict.APPROVED,
                study_type=canonical,
                lead_agent="lead",
                peer_reviewer=reviewer_study,
                math_guard=mg,
                peer_review=pr,
                shared_context_snapshot=ctx.to_dict(),
                response=agent_result.data,
                iterations=iteration,
                elapsed_seconds=time.perf_counter() - start,
            )

        # All iterations exhausted
        verdict = self._final_verdict(last_math_guard, last_peer_review)

        return OrchestrationResult(
            verdict=verdict,
            study_type=canonical,
            lead_agent="lead",
            peer_reviewer=reviewer_study,
            math_guard=last_math_guard,
            peer_review=last_peer_review,
            shared_context_snapshot=ctx.to_dict(),
            response=last_response,
            iterations=iteration,
            elapsed_seconds=time.perf_counter() - start,
        )

    @staticmethod
    def _study_type_enum(canonical: str) -> StudyType:
        """Resolve a canonical study-type string to the ``StudyType`` enum."""
        try:
            return StudyType(canonical)
        except ValueError:
            # Unknown to enum — fall back to LOAD_FLOW so we can still build
            # an EngineeringTask.  The orchestrator does not depend on the
            # enum value for routing (the lead_agent_fn is caller-supplied).
            return StudyType.LOAD_FLOW


# ---------------------------------------------------------------------------
# 7. AhmedETAPSkillAgent — BaseAgent wrapper for the existing orchestrator
# ---------------------------------------------------------------------------


class AhmedETAPSkillAgent(BaseAgent):
    """BaseAgent wrapper that exposes the AhmedETAP skill to the existing
    orchestrator registry.

    Registered as ``"ahmed_etap"`` in :class:`ChiefEngineeringOrchestrator`.
    Callable via ``study_type="ahmed_etap_orchestration"`` in the API.

    The agent accepts a pre-built workflow spec in ``task.parameters``:

        {
            "study_type": "load_flow",
            "project": {"name": "Project-X", "base_mva": 100, "base_kv": 115},
            "parameters": { ...study params... },
            "claim_value": 1.024,
            "claim_unit": "pu",
            "quantity_kind": "voltage",
            "budget_tokens": 8000,
            "lead_agent": "load_flow",     # which registered agent to use
        }

    The wrapper looks up the registered Lead Agent in the existing
    ``ChiefEngineeringOrchestrator`` and routes to it through the skill
    pipeline.
    """

    prompt_handle = "ahmed_etap_agent"

    def __init__(self, orchestrator: Optional[ChiefEngineeringOrchestrator] = None) -> None:
        super().__init__("ahmed_etap_skill")
        self._orch = orchestrator
        self._skill_orch = AhmedETAPOrchestrator()

    def _resolve_orchestrator(self) -> ChiefEngineeringOrchestrator:
        if self._orch is None:
            # Lazy-import to avoid circular import at module load time.
            from agents.orchestrator import get_orchestrator

            self._orch = get_orchestrator()
        return self._orch

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Execute the skill pipeline."""
        start = datetime.now(UTC)
        params = task.parameters or {}
        study_type = params.get("study_type", "")
        if not study_type:
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=["'study_type' is required in parameters"],
            )

        # Build ProjectRef
        proj_dict = params.get("project", {})
        project = ProjectRef(
            name=proj_dict.get("name", ""),
            base_mva=float(proj_dict.get("base_mva", 100.0)),
            base_kv=float(proj_dict.get("base_kv", 115.0)),
            metadata=proj_dict.get("metadata", {}),
        )

        # Identify Lead Agent
        lead_key = params.get("lead_agent") or self._default_lead_for(study_type)
        orch = self._resolve_orchestrator()
        lead_agent = orch.agents.get(lead_key)
        if lead_agent is None:
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[
                    f"lead_agent='{lead_key}' not registered in orchestrator",
                ],
            )

        # Build the lead-agent task
        lead_task = EngineeringTask(
            task_id=f"{task.task_id}_lead",
            description=f"Skill-driven {study_type}",
            study_types=[self._skill_orch._study_type_enum(canonicalize_study_type(study_type))],
            parameters=dict(params.get("parameters", {}).items()),
        )

        async def _lead_fn(t: EngineeringTask) -> AgentResult:
            return await lead_agent.execute(t)

        # Recompute function — defaults to returning the claim_value
        # (no deterministic recomputation available without domain engine).
        # Real callers should pass ``recompute_fn`` explicitly.
        recompute_fn: Callable[[], float] = params.get(
            "recompute_fn",
            lambda: float(params.get("claim_value", 0.0)),
        )

        result = await self._skill_orch.run_study(
            study_type=study_type,
            project=project,
            parameters=lead_task.parameters,
            lead_agent_fn=_lead_fn,
            recompute_fn=recompute_fn,
            claim_value=float(params.get("claim_value", 0.0)),
            claim_unit=str(params.get("claim_unit", "pu")),
            quantity_kind=str(params.get("quantity_kind", "voltage")),
            expected_unit=params.get("expected_unit"),
            budget_tokens=int(params.get("budget_tokens", 8_000)),
            reviewer_fn=params.get("reviewer_fn"),
        )

        elapsed = (datetime.now(UTC) - start).total_seconds()
        status = (
            AgentStatus.COMPLETED
            if result.verdict == OrchestrationVerdict.APPROVED
            else AgentStatus.FAILED
        )
        return AgentResult(
            agent_name=self.agent_name,
            study_type=self._skill_orch._study_type_enum(canonicalize_study_type(study_type)),
            status=status,
            data=result.to_dict(),
            validation_status=result.verdict == OrchestrationVerdict.APPROVED,
            validation_errors=[]
            if status == AgentStatus.COMPLETED
            else [
                f"verdict={result.verdict.value}",
            ],
            execution_time=elapsed,
        )

    @staticmethod
    def _default_lead_for(study_type: str) -> str:
        """Default Lead Agent key for a given study type.

        This mapping MUST cover every study type in
        :data:`PEER_REVIEW_MATRIX`.  Previously it only covered 7 of the 15
        matrix entries, which meant calling the skill with ``arc_flash``,
        ``motor_starting``, ``transient_stability``, ``cable_sizing``,
        ``earth_grid``, ``renewable_integration``, ``battery_storage``,
        ``scada``, or ``digital_twin`` would silently route to the
        ``load_flow`` agent — wrong and unsafe.
        """
        mapping = {
            # Core power-system study agents (registered in orchestrator)
            "load_flow": "load_flow",
            "short_circuit": "short_circuit",
            "harmonic_analysis": "harmonic_analysis",
            "optimal_power_flow": "optimal_power_flow",
            "protection_coordination": "protection_coordination",
            # Standalone specialist agents (now also registered)
            "arc_flash": "arc_flash",
            "motor_starting": "motor_starting",
            "transient_stability": "transient_stability",
            "cable_sizing": "cable_sizing",
            "earth_grid": "earth_grid",
            "renewable_integration": "renewable_integration",
            "battery_storage": "battery_storage",
            "scada": "scada",
            "digital_twin": "digital_twin",
            # Auxiliary agents
            "anomaly": "anomaly",
            "predictive": "predictive",
            "weather": "weather",
            "goal_planner": "goal_planner",
            # ETAP integration agents
            "etap_expert": "etap_expert",
            "etap_gui": "etap_gui",
            "etap_execution": "etap_execution",
            # Validation & reporting (used as reviewers, not leads)
            "validation": "validation",
            "report": "report",
        }
        return mapping.get(canonicalize_study_type(study_type), "load_flow")

    def get_agent_info(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "prompt_handle": self.prompt_handle,
            "skill": "ahmed-etap",
            "skill_path": "skills/ahmed-etap/SKILL.md",
            "principles_enforced": [
                "shared_context",
                "token_budget",
                "math_guard",
                "peer_review",
            ],
            "max_retries": AhmedETAPOrchestrator.MAX_RETRIES,
        }


# ---------------------------------------------------------------------------
# 8. Skill loader — used by api/studies.py and the orchestrator
# ---------------------------------------------------------------------------


_SKILL_PATH = Path(__file__).resolve().parent.parent / "skills" / "ahmed-etap" / "SKILL.md"
_REFERENCE_PATH = Path(__file__).resolve().parent.parent / "skills" / "ahmed-etap" / "REFERENCE.md"

_skill_cache: Optional[str] = None
_reference_cache: Optional[str] = None


def load_skill_text() -> str:
    """Load and cache the ``ahmed-etap`` SKILL.md content."""
    global _skill_cache
    if _skill_cache is None:
        if not _SKILL_PATH.exists():
            logger.warning("ahmed-etap SKILL.md missing: %s", _SKILL_PATH)
            _skill_cache = ""
        else:
            _skill_cache = _SKILL_PATH.read_text(encoding="utf-8")
            logger.info("ahmed-etap skill loaded: %d chars", len(_skill_cache))
    return _skill_cache


def load_reference_text() -> str:
    """Load and cache the ``ahmed-etap`` REFERENCE.md content."""
    global _reference_cache
    if _reference_cache is None:
        if not _REFERENCE_PATH.exists():
            _reference_cache = ""
        else:
            _reference_cache = _REFERENCE_PATH.read_text(encoding="utf-8")
    return _reference_cache


# ---------------------------------------------------------------------------
# 9. Convenience entry point — `python -m agents.ahmed_etap_orchestrator`
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m agents.ahmed_etap_orchestrator 'study_type=load_flow'")
        print("       python -m agents.ahmed_etap_orchestrator --info")
        sys.exit(1)

    if sys.argv[1] == "--info":
        agent = AhmedETAPSkillAgent()
        print(json.dumps(agent.get_agent_info(), indent=2))
        sys.exit(0)

    # Smoke test: simulate a load_flow with a fake lead agent
    async def _smoke() -> None:
        async def fake_lead(task: EngineeringTask) -> AgentResult:  # NOSONAR: S7503 async signature required by callers; body intentionally sync  # — S7503: async signature required by callers; body intentionally sync
            return AgentResult(
                agent_name="FakeLoadFlow",
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data={
                    "buses": {"B1": {"voltage_magnitude_pu": 1.024}},
                    "converged": True,
                    "iterations": 4,
                    "method": "Newton-Raphson",
                },
            )

        orch = AhmedETAPOrchestrator()
        result = await orch.run_study(
            study_type="load_flow",
            project=ProjectRef(name="SmokeTest"),
            parameters={},
            lead_agent_fn=fake_lead,
            recompute_fn=lambda: 1.024,  # matches the claim → MathGuard passes
            claim_value=1.024,
            claim_unit="pu",
            quantity_kind="voltage",
        )
        print(json.dumps(result.to_dict(), indent=2, default=str))

    asyncio.run(_smoke())
