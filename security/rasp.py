"""
Runtime Application Self-Protection (RASP) for ETAP AI Platform
================================================================

Provides runtime attack detection and mitigation for the FastAPI
application. Inspects incoming requests for common attack patterns
and blocks them before they reach business logic.

Attack patterns detected:
- SQL Injection (SQLi)
- Cross-Site Scripting (XSS)
- Command Injection (Cmdi)
- Path Traversal
- LDAP Injection
- NoSQL Injection
- Server-Side Request Forgery (SSRF)

Each rule is assigned a severity level and an action (block, log, or
allow with warning).  The middleware can be configured via environment
variables to tune sensitivity.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


class RASPAction(Enum):
    """Action to take when an attack is detected."""
    BLOCK = "block"
    LOG = "log"
    ALLOW = "allow"  # Allow but warn


class RASPSeverity(Enum):
    """Severity of the detected attack."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RASPRule:
    """A single RASP detection rule."""
    name: str
    pattern: re.Pattern
    action: RASPAction = RASPAction.BLOCK
    severity: RASPSeverity = RASPSeverity.HIGH
    description: str = ""
    check_fields: List[str] = field(default_factory=lambda: ["query", "body", "path", "headers"])


@dataclass
class RASPResult:
    """Result of a RASP inspection."""
    is_attack: bool = False
    rule_name: str = ""
    severity: RASPSeverity = RASPSeverity.LOW
    action: RASPAction = RASPAction.ALLOW
    matched_value: str = ""
    matched_field: str = ""


# ---------------------------------------------------------------------------
# Default RASP rules
# ---------------------------------------------------------------------------

_DEFAULT_RULES: List[RASPRule] = [
    RASPRule(
        name="sqli_basic",
        pattern=re.compile(
            r"(?i)(\b(union\s+select|select\s+.+\s+from|insert\s+into|delete\s+from|"
            r"drop\s+table|alter\s+table|exec\s*\(|execute\s*\(|"
            r"'\s*(or|and)\s+.*[=<>]|;\s*(drop|delete|update|insert)|"
            r"waitfor\s+delay|benchmark\s*\(|sleep\s*\()\b)",
            re.IGNORECASE,
        ),
        action=RASPAction.BLOCK,
        severity=RASPSeverity.CRITICAL,
        description="SQL Injection attempt detected",
    ),
    RASPRule(
        name="xss_basic",
        pattern=re.compile(
            r"(?i)(<script[^>]*>|javascript\s*:|on(error|load|click|mouseover)\s*=|"
            r"alert\s*\(|document\.\s*(cookie|location)|eval\s*\()",
            re.IGNORECASE,
        ),
        action=RASPAction.BLOCK,
        severity=RASPSeverity.HIGH,
        description="Cross-Site Scripting (XSS) attempt detected",
    ),
    RASPRule(
        name="command_injection",
        pattern=re.compile(
            r"(?i)(;\s*(rm|del|format|shutdown|reboot|cat|type|dir|ls|pwd|id|whoami|uname)\b|"
            r"\|\s*(bash|sh|cmd|powershell|python|perl|ruby|php)\b|"
            r"`[^`]+`|\$\([^)]+\))",
            re.IGNORECASE,
        ),
        action=RASPAction.BLOCK,
        severity=RASPSeverity.CRITICAL,
        description="Command Injection attempt detected",
    ),
    RASPRule(
        name="path_traversal",
        pattern=re.compile(
            r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e/|\.\.%2f|%252e|/etc/passwd|/etc/shadow|"
            r"c:\\|\\windows\\)",
            re.IGNORECASE,
        ),
        action=RASPAction.BLOCK,
        severity=RASPSeverity.HIGH,
        description="Path Traversal attempt detected",
    ),
    RASPRule(
        name="ldap_injection",
        pattern=re.compile(
            r"(?i)(\*\)|\(\|\(|\(\&\(|\)omiconj|\)(\||&)\()",
            re.IGNORECASE,
        ),
        action=RASPAction.BLOCK,
        severity=RASPSeverity.HIGH,
        description="LDAP Injection attempt detected",
    ),
    RASPRule(
        name="nosql_injection",
        pattern=re.compile(
            r"(?i)(\$where|\$ne|\$gt|\$lt|\$gte|\$lte|\$in|\$nin|\$or|\$and|\$not|\$regex|\$expr)",
        ),
        action=RASPAction.BLOCK,
        severity=RASPSeverity.HIGH,
        description="NoSQL Injection attempt detected — blocked",
    ),
    RASPRule(
        name="ssrf_basic",
        pattern=re.compile(
            r"(?i)(http://(169\.254\.|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|"
            r"192\.168\.\d+\.\d+|127\.0\.0\.1|0\.0\.0\.0|localhost|metadata\.google\.internal|"
            r"100\.100\.100\.200)|file://|gopher://|dict://)",
            re.IGNORECASE,
        ),
        action=RASPAction.BLOCK,
        severity=RASPSeverity.CRITICAL,
        description="SSRF attempt detected — blocked",
    ),
]


class RASPEngine:
    """Runtime Application Self-Protection engine.

    Inspects HTTP request data against a set of attack detection rules
    and returns results indicating whether an attack was detected.

    Parameters
    ----------
    rules : list[RASPRule], optional
        Custom rules.  If not provided, default rules are used.
    enabled : bool
        Whether RASP inspection is active.  Can be toggled at runtime.
    """

    def __init__(
        self,
        rules: Optional[List[RASPRule]] = None,
        enabled: bool = True,
    ) -> None:
        self._rules = rules or _DEFAULT_RULES
        self._enabled = enabled
        self._stats: Dict[str, int] = {
            "total_inspections": 0,
            "attacks_detected": 0,
            "attacks_blocked": 0,
            "attacks_logged": 0,
        }

    @property
    def enabled(self) -> bool:
        """Whether RASP is currently active."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def inspect(self, data: Dict[str, Any]) -> List[RASPResult]:
        """Inspect request data against all RASP rules.

        Parameters
        ----------
        data : dict
            Request data with keys like 'query', 'body', 'path', 'headers'.

        Returns
        -------
        list[RASPResult]
            Results for each detected attack (empty list if clean).
        """
        if not self._enabled:
            return []

        self._stats["total_inspections"] += 1
        results: List[RASPResult] = []

        for rule in self._rules:
            for field_name in rule.check_fields:
                value = data.get(field_name, "")
                if not value:
                    continue
                # Convert non-string values to string for pattern matching
                if not isinstance(value, str):
                    try:
                        value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                    except Exception:
                        value = str(value)
                match = rule.pattern.search(value)
                if match:
                    result = RASPResult(
                        is_attack=True,
                        rule_name=rule.name,
                        severity=rule.severity,
                        action=rule.action,
                        matched_value=match.group(0)[:100],  # Truncate for safety
                        matched_field=field_name,
                    )
                    results.append(result)

                    if rule.action == RASPAction.BLOCK:
                        self._stats["attacks_blocked"] += 1
                        logger.warning(
                            "RASP BLOCKED: rule=%s field=%s value=%s",
                            rule.name, field_name, match.group(0)[:50],
                        )
                    elif rule.action == RASPAction.LOG:
                        self._stats["attacks_logged"] += 1
                        logger.info(
                            "RASP LOGGED: rule=%s field=%s value=%s",
                            rule.name, field_name, match.group(0)[:50],
                        )

        if results:
            self._stats["attacks_detected"] += len(results)

        return results

    def get_stats(self) -> Dict[str, int]:
        """Return RASP inspection statistics."""
        return dict(self._stats)

    def add_rule(self, rule: RASPRule) -> None:
        """Add a custom RASP rule."""
        self._rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name.  Returns True if found and removed."""
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                self._rules.pop(i)
                return True
        return False


def create_default_rasp_engine() -> RASPEngine:
    """Create a RASP engine with default attack detection rules.

    Suitable for the ETAP AI Engineering Service.
    """
    return RASPEngine(rules=_DEFAULT_RULES, enabled=True)
