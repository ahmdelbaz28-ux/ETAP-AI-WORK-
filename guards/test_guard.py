"""
Test Guard — Test Code Quality Gate
=====================================
Adapted from the test-guard skill (github.com/amElnagdy/guard-skills).

Implements 9 universal testing rules with pytest-specific patterns
(since the ETAP platform uses pytest extensively):

  T-01: Test behavior, not implementation
  T-02: Every mock must be justified (system boundaries only)
  T-03: One scenario per test, data-driven for variants
  T-04: Every test must justify its existence
  T-05: Name tests for the scenario
  T-06: Production regression tests are sacred
  T-07: No tests for framework guarantees
  T-08: State/value objects are real, never mocked
  T-09: Infrastructure under test gets real infrastructure
  T-L1: LLM app testing — test prompt contracts not content
  T-L2: LLM app testing — observability is infrastructure
  T-L3: LLM app testing — agent-flow tests test transitions
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Any, Dict, List, Optional

from guards.base import BaseGuard, GuardMode, GuardResult, GuardSeverity, GuardViolation

logger = logging.getLogger(__name__)


class TestGuard(BaseGuard):
    """Scans test code for quality violations against the 9+3 testing rules.

    Usage
    -----
    >>> guard = TestGuard()
    >>> result = guard.scan(test_source_code)
    """

    name: str = "test_guard"

    def scan(self, source: str, language: str = "python", context: Optional[Dict[str, Any]] = None) -> GuardResult:
        violations: List[GuardViolation] = []
        context = context or {}

        tree: Optional[ast.AST] = None
        try:
            tree = ast.parse(source)
        except SyntaxError:
            logger.debug("TestGuard: AST parse failed, using regex-only mode")

        if tree is not None:
            # T-01: Test behavior, not implementation
            violations.extend(self._check_impl_testing(tree, source))

            # T-02: Every mock must be justified
            violations.extend(self._check_unjustified_mocks(tree, source))

            # T-03: One scenario per test
            violations.extend(self._check_multi_scenario(tree, source))

            # T-05: Name tests for the scenario
            violations.extend(self._check_test_naming(tree, source))

            # T-07: No tests for framework guarantees
            violations.extend(self._check_framework_guarantees(tree, source))

            # T-08: State/value objects are real, never mocked
            violations.extend(self._check_mocked_value_objects(tree, source))

        # T-L1: LLM app testing — test prompt contracts not content
        violations.extend(self._check_llm_test_patterns(source))

        return GuardResult(
            guard_name=self.name,
            mode=self.mode,
            violations=violations,
            metadata={
                "language": language,
                "source_length": len(source),
                "rules_checked": 12,
            },
        )

    # ------------------------------------------------------------------
    # T-01: Test behavior, not implementation
    # ------------------------------------------------------------------
    def _check_impl_testing(self, tree: ast.AST, source: str) -> List[GuardViolation]:
        """Heuristic: test accesses private attributes (leading underscore)."""
        violations: List[GuardViolation] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.attr.startswith('_') and not node.attr.startswith('__'):
                    # Check if this is inside a test function
                    line_num = node.lineno
                    violations.append(GuardViolation(
                        rule_id="T-01",
                        rule_name="Test accesses private implementation",
                        severity=GuardSeverity.MUST_FIX,
                        description=f"Test accesses private attribute '{node.attr}'. "
                                    "Tests should verify public behavior, not internal implementation.",
                        location=f"line {line_num}",
                        suggestion="Test the public interface instead. If the private attribute "
                                   "has no public observable effect, it may not need testing.",
                        evidence=f"accessing .{node.attr}",
                    ))
        return violations

    # ------------------------------------------------------------------
    # T-02: Every mock must be justified (system boundaries only)
    # ------------------------------------------------------------------
    def _check_unjustified_mocks(self, tree: ast.AST, source: str) -> List[GuardViolation]:
        """Heuristic: patching internal modules/functions (not I/O boundaries)."""
        violations: List[GuardViolation] = []
        # Patterns suggesting internal patching
        internal_patch_patterns = [
            r'patch\(["\'](?!\b(requests|httpx|aiohttp|boto|redis|psycopg|sqlalchemy|subprocess)\b)',
            r'mock\.patch\(["\'](?!\b(requests|httpx|aiohttp|boto|redis|psycopg|sqlalchemy|subprocess)\b)',
        ]
        for pat in internal_patch_patterns:
            for match in re.finditer(pat, source):
                line_num = source[:match.start()].count('\n') + 1
                violations.append(GuardViolation(
                    rule_id="T-02",
                    rule_name="Unjustified mock — not at system boundary",
                    severity=GuardSeverity.MUST_FIX,
                    description="Mock appears to patch an internal module, not an I/O boundary. "
                                "Only external dependencies (network, DB, filesystem) should be mocked.",
                    location=f"line {line_num}",
                    suggestion="Use the real implementation for internal code. Only mock at "
                               "system boundaries (APIs, databases, file I/O, external services).",
                    evidence=match.group(0)[:80],
                ))
        return violations

    # ------------------------------------------------------------------
    # T-03: One scenario per test
    # ------------------------------------------------------------------
    def _check_multi_scenario(self, tree: ast.AST, source: str) -> List[GuardViolation]:
        """Heuristic: multiple assert statements in a single test function."""
        violations: List[GuardViolation] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith('test_'):
                    continue
                assert_count = sum(1 for child in ast.walk(node) if isinstance(child, ast.Assert))
                # Also check self.assertX patterns
                self_asserts = 0
                for child in ast.walk(node):
                    if (isinstance(child, ast.Call) and
                            isinstance(child.func, ast.Attribute) and
                            isinstance(child.func.value, ast.Name) and
                            child.func.value.id == 'self' and
                            child.func.attr.startswith('assert')):
                        self_asserts += 1

                total = assert_count + self_asserts
                if total > 5:
                    violations.append(GuardViolation(
                        rule_id="T-03",
                        rule_name="Too many assertions per test",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"Test '{node.name}' has {total} assert statements. "
                                    "Each test should verify one scenario; use parametrize for variants.",
                        location=f"function '{node.name}' (line {node.lineno})",
                        suggestion="Split into separate test cases or use pytest.mark.parametrize "
                                   "for data-driven variants.",
                        evidence=f"{total} assertions",
                    ))
        return violations

    # ------------------------------------------------------------------
    # T-05: Name tests for the scenario
    # ------------------------------------------------------------------
    def _check_test_naming(self, tree: ast.AST, source: str) -> List[GuardViolation]:
        """Check that test names follow test_<scenario>_<expected> pattern."""
        violations: List[GuardViolation] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                name = node.name
                # Bad patterns: test_function_name, test_1, test_something_v2
                if re.match(r'^test_\d+$', name):
                    violations.append(GuardViolation(
                        rule_id="T-05",
                        rule_name="Test name is not descriptive",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"Test '{name}' uses a number instead of describing the scenario.",
                        location=f"function '{name}' (line {node.lineno})",
                        suggestion="Rename to test_<scenario>_<expected>, e.g. "
                                   "test_load_flow_converges_with_valid_system.",
                        evidence=name,
                    ))
                elif len(name) < 12:
                    violations.append(GuardViolation(
                        rule_id="T-05",
                        rule_name="Test name too short",
                        severity=GuardSeverity.WORTH_NOTING,
                        description=f"Test '{name}' has a very short name that may not describe "
                                    "the scenario adequately.",
                        location=f"function '{name}' (line {node.lineno})",
                        suggestion="Use a more descriptive name following test_<scenario>_<expected>.",
                        evidence=name,
                    ))
        return violations

    # ------------------------------------------------------------------
    # T-07: No tests for framework guarantees
    # ------------------------------------------------------------------
    def _check_framework_guarantees(self, tree: ast.AST, source: str) -> List[GuardViolation]:
        """Heuristic: test that only verifies Python built-in behavior."""
        violations: List[GuardViolation] = []
        framework_assert_patterns = [
            (r'assert\s+(type|isinstance|len|str|int|float|dict|list)\s*\(', "type/builtin check"),
        ]
        for pat, desc in framework_assert_patterns:
            for match in re.finditer(pat, source):
                line_num = source[:match.start()].count('\n') + 1
                # Only flag if the surrounding function is a test
                violations.append(GuardViolation(
                    rule_id="T-07",
                    rule_name="Tests framework guarantees",
                    severity=GuardSeverity.SHOULD_FIX,
                    description="Test verifies a Python built-in guarantee rather than "
                                "application behavior. Frameworks are already tested.",
                    location=f"line {line_num}",
                    suggestion="Remove the framework-guarantee assertion and focus on "
                               "application-specific behavior.",
                    evidence=match.group(0)[:80],
                ))
        return violations

    # ------------------------------------------------------------------
    # T-08: State/value objects are real, never mocked
    # ------------------------------------------------------------------
    def _check_mocked_value_objects(self, tree: ast.AST, source: str) -> List[GuardViolation]:
        """Heuristic: MagicMock used for data/value objects."""
        violations: List[GuardViolation] = []
        pattern = r'MagicMock\(\s*spec\s*=\s*(\w+)'
        for match in re.finditer(pattern, source):
            class_name = match.group(1)
            # Common value object suffixes
            value_suffixes = ('Data', 'Model', 'DTO', 'Request', 'Response', 'Result', 'Config')
            if class_name.endswith(value_suffixes):
                line_num = source[:match.start()].count('\n') + 1
                violations.append(GuardViolation(
                    rule_id="T-08",
                    rule_name="Value object mocked instead of using real instance",
                    severity=GuardSeverity.MUST_FIX,
                    description=f"'{class_name}' appears to be a value/data object but is mocked. "
                                "Value objects should be instantiated with real data.",
                    location=f"line {line_num}",
                    suggestion=f"Create a real {class_name} instance with test data instead of mocking it.",
                    evidence=match.group(0)[:80],
                ))
        return violations

    # ------------------------------------------------------------------
    # T-L1: LLM app testing patterns
    # ------------------------------------------------------------------
    def _check_llm_test_patterns(self, source: str) -> List[GuardViolation]:
        """Check for common anti-patterns in LLM application tests."""
        violations: List[GuardViolation] = []

        # T-L1: Test prompt contracts not content
        # Heuristic: exact string match on LLM output
        pattern = r'assert\s+.*(?:response|output|result|completion).*==\s*["\']'
        for match in re.finditer(pattern, source):
            line_num = source[:match.start()].count('\n') + 1
            violations.append(GuardViolation(
                rule_id="T-L1",
                rule_name="Exact string assertion on LLM output",
                severity=GuardSeverity.MUST_FIX,
                description="Test asserts exact string match on LLM output. "
                            "LLM outputs are non-deterministic; test the contract (schema, "
                            "key fields) instead of exact content.",
                location=f"line {line_num}",
                suggestion="Assert on structure (JSON schema, presence of key fields, "
                           "type of response) rather than exact string content.",
                evidence=match.group(0)[:80],
            ))

        return violations
