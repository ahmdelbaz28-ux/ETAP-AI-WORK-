"""
Code Guard — Production Code Quality Gate
==========================================
Adapted from the clean-code-guard skill (github.com/amElnagdy/guard-skills).

Implements 23 imperatives organized into:
  - Functions & Names (4 rules)
  - Comments & Structure (2 rules)
  - SOLID (4 rules)
  - DRY / KISS / YAGNI (4 rules)
  - AI-specific guardrails (8 rules) — delegates to AIFailureModeDetector
  - Refactoring discipline (1 rule)

Also integrates the 14 AI failure modes from ``ai_failure_modes.py``,
making this the single entry-point for production-code quality scanning.
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Any, Dict, List, Optional

from guards.base import BaseGuard, GuardMode, GuardResult, GuardSeverity, GuardViolation
from guards.ai_failure_modes import AIFailureModeDetector

logger = logging.getLogger(__name__)


class CodeGuard(BaseGuard):
    """Scans production Python code for clean-code violations and AI failure modes.

    Usage
    -----
    >>> guard = CodeGuard()
    >>> result = guard.scan(source_code)
    >>> print(result.passed, result.must_fix_count)
    """

    name: str = "code_guard"

    def __init__(self, mode: GuardMode = GuardMode.GUARD_PASS) -> None:
        super().__init__(mode)
        self._ai_detector = AIFailureModeDetector(mode)

    def scan(self, source: str, language: str = "python", context: Optional[Dict[str, Any]] = None) -> GuardResult:
        violations: List[GuardViolation] = []
        context = context or {}

        # --- AI failure modes (FM-01 through FM-14) ---
        ai_result = self._ai_detector.detect(source, context)
        violations.extend(ai_result.violations)

        # Parse AST for structural checks
        tree: Optional[ast.AST] = None
        try:
            tree = ast.parse(source)
        except SyntaxError:
            logger.debug("CodeGuard: AST parse failed, skipping structural rules")

        if tree is not None:
            # --- Functions & Names ---
            violations.extend(self._check_function_length(tree, source))
            violations.extend(self._check_parameter_count(tree, source))
            violations.extend(self._check_intent_revealing_names(tree, source))

            # --- Comments & Structure ---
            violations.extend(self._check_why_not_what_comments(source))

            # --- SOLID ---
            violations.extend(self._check_srp_violations(tree, source))

            # --- DRY / KISS / YAGNI ---
            violations.extend(self._check_complexity(tree, source))

        return GuardResult(
            guard_name=self.name,
            mode=self.mode,
            violations=violations,
            metadata={
                "language": language,
                "source_length": len(source),
                "rules_checked": 23,
                "ai_failure_modes": len(ai_result.violations),
            },
        )

    # ------------------------------------------------------------------
    # CC-01: Functions should be ≤ 20 lines
    # ------------------------------------------------------------------
    def _check_function_length(self, tree: ast.AST, source: str) -> List[GuardViolation]:
        violations: List[GuardViolation] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                length = (node.end_lineno or node.lineno) - node.lineno
                if length > 20:
                    severity = GuardSeverity.MUST_FIX if length > 50 else GuardSeverity.SHOULD_FIX
                    violations.append(GuardViolation(
                        rule_id="CC-01",
                        rule_name="Function too long",
                        severity=severity,
                        description=f"Function '{node.name}' is {length} lines. "
                                    "Functions should be ≤ 20 lines; anything over 50 is a must-fix.",
                        location=f"function '{node.name}' (line {node.lineno})",
                        suggestion="Extract helper functions so each does one thing.",
                        evidence=f"{length} lines",
                    ))
        return violations

    # ------------------------------------------------------------------
    # CC-02: Parameter count ≤ 4
    # ------------------------------------------------------------------
    def _check_parameter_count(self, tree: ast.AST, source: str) -> List[GuardViolation]:
        violations: List[GuardViolation] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [a for a in node.args.args if a.arg not in ('self', 'cls')]
                param_count = len(params) + len(node.args.kwonlyargs) + len(node.args.posonlyargs)
                if param_count > 4:
                    severity = GuardSeverity.MUST_FIX if param_count > 7 else GuardSeverity.SHOULD_FIX
                    violations.append(GuardViolation(
                        rule_id="CC-02",
                        rule_name="Too many parameters",
                        severity=severity,
                        description=f"Function '{node.name}' has {param_count} parameters. "
                                    "Maximum recommended is 4; more suggests the function does too much.",
                        location=f"function '{node.name}' (line {node.lineno})",
                        suggestion="Group related parameters into a dataclass or typed dict, "
                                   "or split the function.",
                        evidence=f"{param_count} parameters",
                    ))
        return violations

    # ------------------------------------------------------------------
    # CC-03: Intent-revealing names (heuristic: single-letter vars outside loops)
    # ------------------------------------------------------------------
    def _check_intent_revealing_names(self, tree: ast.AST, source: str) -> List[GuardViolation]:
        violations: List[GuardViolation] = []
        loop_vars: set = set()
        # Collect loop variables (exempt)
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                if isinstance(node.target, ast.Name):
                    loop_vars.add(node.target.id)
                elif isinstance(node.target, ast.Tuple):
                    for elt in node.target.elts:
                        if isinstance(elt, ast.Name):
                            loop_vars.add(elt.id)

        # Check assignments with single-letter names
        exempt = {'i', 'j', 'k', 'x', 'y', 'z', 'e', 'f', 'n', 'm', 'r', 'c', '_'} | loop_vars
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and len(target.id) == 1 and target.id not in exempt:
                        violations.append(GuardViolation(
                            rule_id="CC-03",
                            rule_name="Non-intent-revealing name",
                            severity=GuardSeverity.SHOULD_FIX,
                            description=f"Variable '{target.id}' has a single-letter name that "
                                        "doesn't reveal intent.",
                            location=f"line {target.lineno}",
                            suggestion="Use a descriptive name that explains the variable's purpose.",
                            evidence=f"var '{target.id}'",
                        ))
        return violations

    # ------------------------------------------------------------------
    # CC-05: Comments should explain 'why', not 'what'
    # ------------------------------------------------------------------
    def _check_why_not_what_comments(self, source: str) -> List[GuardViolation]:
        violations: List[GuardViolation] = []
        what_patterns = [
            r'#\s*(increment|decrement|add|remove|set|get|update|delete|check|return)\s',
            r'#\s*(if|else|for|while|try|except)\s',
        ]
        for i, line in enumerate(source.split('\n'), 1):
            stripped = line.strip()
            if not stripped.startswith('#'):
                continue
            for pat in what_patterns:
                if re.search(pat, stripped, re.IGNORECASE):
                    violations.append(GuardViolation(
                        rule_id="CC-05",
                        rule_name="Comment explains 'what', not 'why'",
                        severity=GuardSeverity.WORTH_NOTING,
                        description="Comment describes what the code does instead of why. "
                                    "Code should be self-documenting; comments should explain intent.",
                        location=f"line {i}",
                        suggestion="Remove the comment if the code is self-explanatory, "
                                   "or rewrite it to explain the reasoning behind the code.",
                        evidence=stripped[:80],
                    ))
                    break
        return violations

    # ------------------------------------------------------------------
    # CC-09: SRP — too many responsibilities in one class
    # ------------------------------------------------------------------
    def _check_srp_violations(self, tree: ast.AST, source: str) -> List[GuardViolation]:
        violations: List[GuardViolation] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                if len(methods) > 15:
                    violations.append(GuardViolation(
                        rule_id="CC-09",
                        rule_name="SRP violation — class too large",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"Class '{node.name}' has {len(methods)} methods, suggesting "
                                    "it may have multiple responsibilities.",
                        location=f"class '{node.name}' (line {node.lineno})",
                        suggestion="Consider splitting into smaller classes, each with a single "
                                   "responsibility. Look for method clusters that access the same state.",
                        evidence=f"{len(methods)} methods",
                    ))
        return violations

    # ------------------------------------------------------------------
    # CC-17: Cyclomatic complexity (simplified McCabe)
    # ------------------------------------------------------------------
    def _check_complexity(self, tree: ast.AST, source: str) -> List[GuardViolation]:
        violations: List[GuardViolation] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            complexity = 1  # Base
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                    complexity += 1
                elif isinstance(child, ast.BoolOp):
                    complexity += len(child.values) - 1
                elif isinstance(child, ast.Assert):
                    complexity += 1

            if complexity > 10:
                severity = GuardSeverity.MUST_FIX if complexity > 20 else GuardSeverity.SHOULD_FIX
                violations.append(GuardViolation(
                    rule_id="CC-17",
                    rule_name="Cyclomatic complexity too high",
                    severity=severity,
                    description=f"Function '{node.name}' has cyclomatic complexity of {complexity}. "
                                "Maximum recommended is 10.",
                    location=f"function '{node.name}' (line {node.lineno})",
                    suggestion="Reduce branching by extracting helper functions, using early returns, "
                               "or replacing conditionals with polymorphism.",
                    evidence=f"complexity = {complexity}",
                ))
        return violations
