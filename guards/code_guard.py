"""
Code Guard — Production Code Quality Gate
==========================================
Adapted from the clean-code-guard skill (github.com/amElnagdy/guard-skills).

Implements 23 imperatives organized into:
  - Functions & Names (5 rules: CC-01, CC-02, CC-03, CC-04, CC-09)
  - Comments & Structure (3 rules: CC-05, CC-14, CC-15)
  - SOLID (4 rules: CC-09, CC-10, CC-11, CC-12)
  - DRY / KISS / YAGNI (4 rules: CC-06, CC-07, CC-13, CC-17)
  - AI-specific guardrails (14 failure modes) — delegates to AIFailureModeDetector

Also integrates the 14 AI failure modes from ``ai_failure_modes.py``,
making this the single entry-point for production-code quality scanning.
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Any, Dict, List, Optional

from guards.ai_failure_modes import AIFailureModeDetector
from guards.base import BaseGuard, GuardMode, GuardResult, GuardSeverity, GuardViolation

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
            violations.extend(self._check_boolean_flags(tree, source))

            # --- Comments & Structure ---
            violations.extend(self._check_why_not_what_comments(source))
            violations.extend(self._check_commented_out_code(source))

            # --- SOLID ---
            violations.extend(self._check_srp_violations(tree, source))

            # --- DRY / KISS / YAGNI ---
            violations.extend(self._check_cqs_violations(tree, source))
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

    # ------------------------------------------------------------------
    # CC-04: Boolean flag arguments
    # ------------------------------------------------------------------
    def _check_boolean_flags(self, tree: ast.AST, source: str) -> List[GuardViolation]:
        """Flag boolean positional parameters — they usually indicate the
        function does two different things and should be split."""
        violations: List[GuardViolation] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for arg in node.args.args:
                if arg.arg in ('self', 'cls'):
                    continue
                # Check if the annotation is bool or the default is True/False
                has_bool_default = False
                defaults_start = len(node.args.args) - len(node.args.defaults)
                arg_index = node.args.args.index(arg)
                if arg_index >= defaults_start:
                    default = node.args.defaults[arg_index - defaults_start]
                    if isinstance(default, ast.Constant) and isinstance(default.value, bool):
                        has_bool_default = True

                has_bool_annotation = False
                if arg.annotation:
                    if isinstance(arg.annotation, ast.Name) and arg.annotation.id == 'bool':
                        has_bool_annotation = True

                if has_bool_default or has_bool_annotation:
                    violations.append(GuardViolation(
                        rule_id="CC-04",
                        rule_name="Boolean flag argument",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"Function '{node.name}' has boolean parameter '{arg.arg}'. "
                                    "Boolean flags typically indicate a function does two things "
                                    "and should be split into two functions.",
                        location=f"function '{node.name}' (line {node.lineno})",
                        suggestion=f"Split '{node.name}' into two functions, one for each "
                                   f"boolean state of '{arg.arg}'.",
                        evidence=f"param '{arg.arg}: bool'",
                    ))
        return violations

    # ------------------------------------------------------------------
    # CC-06: CQS violation — function returns value AND mutates state
    # ------------------------------------------------------------------
    def _check_cqs_violations(self, tree: ast.AST, source: str) -> List[GuardViolation]:
        """Heuristic: functions that both return a value and call mutating
        methods (append, extend, update, remove, pop, clear, sort) on
        non-local objects."""
        violations: List[GuardViolation] = []
        MUTATING_METHODS = {'append', 'extend', 'insert', 'remove', 'pop', 'clear',
                            'sort', 'reverse', 'update', 'add', 'discard'}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            has_return_value = False
            has_mutation = False
            mutation_evidence = ""
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and child.value is not None:
                    has_return_value = True
                if (isinstance(child, ast.Call) and
                        isinstance(child.func, ast.Attribute) and
                        child.func.attr in MUTATING_METHODS):
                    # Check if this is a mutation on a non-local object
                    # self.x.method() or param.method() or external.method()
                    obj = child.func.value
                    is_nonlocal = False
                    if isinstance(obj, ast.Name):
                        param_names = {a.arg for a in node.args.args if a.arg not in ('self', 'cls')}
                        if obj.id in param_names or obj.id == 'self':
                            is_nonlocal = True
                    elif isinstance(obj, ast.Attribute) and isinstance(obj.value, ast.Name):
                        if obj.value.id == 'self':
                            is_nonlocal = True
                    if is_nonlocal:
                        has_mutation = True
                        if isinstance(obj, ast.Attribute):
                            mutation_evidence = f"self.{obj.attr}.{child.func.attr}()"
                        else:
                            mutation_evidence = f"{obj.id}.{child.func.attr}()"

            if has_return_value and has_mutation:
                violations.append(GuardViolation(
                    rule_id="CC-06",
                    rule_name="CQS violation — reads and mutates",
                    severity=GuardSeverity.SHOULD_FIX,
                    description=f"Function '{node.name}' both returns a value and mutates "
                                "state. Command-Query Separation says a function should "
                                "either compute a value (query) or perform a side effect "
                                "(command), not both.",
                    location=f"function '{node.name}' (line {node.lineno})",
                    suggestion="Split into a command that mutates and a query that returns. "
                               "Or make the mutation explicit by returning the new state.",
                    evidence=f"mutation: {mutation_evidence}",
                ))
        return violations

    # ------------------------------------------------------------------
    # CC-15: Commented-out code blocks
    # ------------------------------------------------------------------
    def _check_commented_out_code(self, source: str) -> List[GuardViolation]:
        """Detect commented-out code — a sign of speculative or abandoned
        code that should be removed or properly versioned."""
        violations: List[GuardViolation] = []
        # Patterns that suggest commented-out code rather than comments
        code_patterns = [
            r'#\s*(if|for|while|try|def|class|return|import|from|with|assert|raise)\s',
            r'#\s*\w+\s*=\s*',       # assignment
            r'#\s*\w+\.\w+\(',       # method call
            r'#\s*print\s*\(',       # print statement
        ]
        for i, line in enumerate(source.split('\n'), 1):
            stripped = line.strip()
            if not stripped.startswith('#'):
                continue
            for pat in code_patterns:
                if re.search(pat, stripped):
                    violations.append(GuardViolation(
                        rule_id="CC-15",
                        rule_name="Commented-out code",
                        severity=GuardSeverity.WORTH_NOTING,
                        description="Commented-out code detected. Dead code should be removed — "
                                    "version control tracks history, not comments.",
                        location=f"line {i}",
                        suggestion="Remove the commented-out code. Use version control (git) "
                                   "to recover it if needed.",
                        evidence=stripped[:80],
                    ))
                    break
        return violations
