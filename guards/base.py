"""
Base Guard Framework
=====================
Shared abstractions for all guard validators.  The severity framework,
violation model, and guard-mode enum are derived from the guard-skills
project's design (github.com/amElnagdy/guard-skills).

Severity mapping to existing ETAP security layers:
  MUST_FIX   → maps to RASPSeverity.CRITICAL / HIGH (blocks execution)
  SHOULD_FIX → maps to RASPSeverity.MEDIUM    (warns but proceeds)
  WORTH_NOTING → maps to RASPSeverity.LOW     (informational)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


class GuardSeverity(Enum):
    """Violation severity — mirrors the guard-skills triage model."""
    MUST_FIX = "must_fix"        # Blocks merge / execution
    SHOULD_FIX = "should_fix"    # Should fix before shipping
    WORTH_NOTING = "worth_noting"  # Informational, no block


class GuardMode(Enum):
    """Execution mode for a guard pass.

    Adapted from the three-mode design of guard-skills:
      - GUARD_PASS: reactive review after code generation (recommended)
      - LIVE:       apply rules proactively during writing
      - REVIEW:     structured audit producing a findings report
    """
    GUARD_PASS = "guard_pass"
    LIVE = "live"
    REVIEW = "review"


@dataclass
class GuardViolation:
    """A single rule violation detected by a guard.

    Attributes
    ----------
    rule_id : str
        Short identifier for the violated rule (e.g. "CC-07", "T-03", "D-01").
    rule_name : str
        Human-readable rule name.
    severity : GuardSeverity
        How serious this violation is.
    description : str
        What was found.
    location : str
        Where the violation was found (line number, symbol, path, etc.).
    suggestion : str
        How to fix it.
    evidence : str
        The offending code/text fragment (truncated for safety).
    """
    rule_id: str
    rule_name: str
    severity: GuardSeverity
    description: str
    location: str = ""
    suggestion: str = ""
    evidence: str = ""


@dataclass
class GuardResult:
    """Aggregate result of a guard pass.

    Attributes
    ----------
    guard_name : str
        Name of the guard that produced this result.
    mode : GuardMode
        Which mode was used for this pass.
    violations : list[GuardViolation]
        All detected violations.
    passed : bool
        True if no MUST_FIX violations were found.
    metadata : dict
        Additional info (scan time, lines scanned, etc.).
    """
    guard_name: str
    mode: GuardMode
    violations: List[GuardViolation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """True when no MUST_FIX violations exist."""
        return not any(v.severity == GuardSeverity.MUST_FIX for v in self.violations)

    @property
    def must_fix_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == GuardSeverity.MUST_FIX)

    @property
    def should_fix_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == GuardSeverity.SHOULD_FIX)

    @property
    def worth_noting_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == GuardSeverity.WORTH_NOTING)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses and audit logs."""
        return {
            "guard_name": self.guard_name,
            "mode": self.mode.value,
            "passed": self.passed,
            "must_fix": self.must_fix_count,
            "should_fix": self.should_fix_count,
            "worth_noting": self.worth_noting_count,
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "rule_name": v.rule_name,
                    "severity": v.severity.value,
                    "description": v.description,
                    "location": v.location,
                    "suggestion": v.suggestion,
                    "evidence": v.evidence[:200],
                }
                for v in self.violations
            ],
            "metadata": self.metadata,
        }


class BaseGuard:
    """Abstract base for all guard validators.

    Subclasses must implement ``scan`` which receives source text and
    returns a ``GuardResult``.
    """

    name: str = "base"

    def __init__(self, mode: GuardMode = GuardMode.GUARD_PASS) -> None:
        self.mode = mode

    def scan(self, source: str, language: str = "python", context: Optional[Dict[str, Any]] = None) -> GuardResult:
        """Run the guard against *source* text.

        Parameters
        ----------
        source : str
            The source code, test code, or documentation to scan.
        language : str
            Primary language hint (python, typescript, markdown, etc.).
        context : dict, optional
            Extra context (file path, surrounding code, etc.).

        Returns
        -------
        GuardResult
        """
        raise NotImplementedError("Subclasses must implement scan()")

    def _make_result(self, violations: Optional[List[GuardViolation]] = None, **meta: Any) -> GuardResult:
        """Convenience to build a GuardResult with the current guard name/mode."""
        return GuardResult(
            guard_name=self.name,
            mode=self.mode,
            violations=violations or [],
            metadata=meta,
        )
