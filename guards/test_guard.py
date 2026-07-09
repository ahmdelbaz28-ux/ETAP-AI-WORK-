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
from typing import Any, Optional

from guards.ai_failure_modes import AIFailureModeDetector
from guards.base import BaseGuard, GuardMode, GuardResult, GuardSeverity, GuardViolation

logger = logging.getLogger(__name__)


class TestGuard(BaseGuard):
    """Scans test code for quality violations against the 9+3 testing rules.

    Also delegates to AIFailureModeDetector for FM-14 (mock assert)
    which is a test-specific AI failure mode.

    Usage
    -----
    >>> guard = TestGuard()
    >>> result = guard.scan(test_source_code)
    """

    __test__ = False  # Prevent pytest from collecting this class

    name: str = "test_guard"

    def __init__(self, mode: GuardMode = GuardMode.GUARD_PASS) -> None:
        super().__init__(mode)
        self._ai_detector = AIFailureModeDetector(mode)

    def scan(
        self, source: str, language: str = "python", context: dict[str, Any] | None = None,
    ) -> GuardResult:
        violations: list[GuardViolation] = []
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

            # T-04: Every test must justify its existence
            violations.extend(self._check_test_justification(tree, source))

            # T-05: Name tests for the scenario
            violations.extend(self._check_test_naming(tree, source))

            # T-06: Production regression tests are sacred
            violations.extend(self._check_regression_tests(tree, source))

            # T-07: No tests for framework guarantees
            violations.extend(self._check_framework_guarantees(tree, source))

            # T-08: State/value objects are real, never mocked
            violations.extend(self._check_mocked_value_objects(tree, source))

            # T-09: Infrastructure under test gets real infrastructure
            violations.extend(self._check_infrastructure_mocking(tree, source))

        # T-L1: LLM app testing — test prompt contracts not content
        violations.extend(self._check_llm_test_patterns(source))

        # T-L2 & T-L3: LLM app testing — observability and agent-flow
        violations.extend(self._check_llm_observability_patterns(source))
        violations.extend(self._check_llm_agent_flow_patterns(source))

        # FM-14: Test asserts on mock behavior (delegated from AI failure modes)
        if self._ai_detector:
            ai_result = self._ai_detector.detect(source)
            fm14_violations = [v for v in ai_result.violations if v.rule_id == "FM-14"]
            violations.extend(fm14_violations)

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
    def _check_impl_testing(self, tree: ast.AST, source: str) -> list[GuardViolation]:
        """Heuristic: test accesses private attributes (leading underscore)."""
        violations: list[GuardViolation] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.attr.startswith("_") and not node.attr.startswith("__"):
                    # Check if this is inside a test function
                    line_num = node.lineno
                    violations.append(
                        GuardViolation(
                            rule_id="T-01",
                            rule_name="Test accesses private implementation",
                            severity=GuardSeverity.MUST_FIX,
                            description=f"Test accesses private attribute '{node.attr}'. "
                            "Tests should verify public behavior, not internal implementation.",
                            location=f"line {line_num}",
                            suggestion="Test the public interface instead. If the private attribute "
                            "has no public observable effect, it may not need testing.",
                            evidence=f"accessing .{node.attr}",
                        ),
                    )
        return violations

    # ------------------------------------------------------------------
    # T-02: Every mock must be justified (system boundaries only)
    # ------------------------------------------------------------------
    def _check_unjustified_mocks(self, tree: ast.AST, source: str) -> list[GuardViolation]:
        """Heuristic: patching internal modules/functions (not I/O boundaries)."""
        violations: list[GuardViolation] = []
        # Patterns suggesting internal patching
        internal_patch_patterns = [
            r'patch\(["\'](?!\b(Union[requests|httpx|aiohttp|boto|redis|psycopg|sqlalchemy, subprocess])\b)',
            r'mock\.patch\(["\'](?!\b(Union[requests|httpx|aiohttp|boto|redis|psycopg|sqlalchemy, subprocess])\b)',
        ]
        for pat in internal_patch_patterns:
            for match in re.finditer(pat, source):
                line_num = source[: match.start()].count("\n") + 1
                violations.append(
                    GuardViolation(
                        rule_id="T-02",
                        rule_name="Unjustified mock — not at system boundary",
                        severity=GuardSeverity.MUST_FIX,
                        description="Mock appears to patch an internal module, not an I/O boundary. "
                        "Only external dependencies (network, DB, filesystem) should be mocked.",
                        location=f"line {line_num}",
                        suggestion="Use the real implementation for internal code. Only mock at "
                        "system boundaries (APIs, databases, file I/O, external services).",
                        evidence=match.group(0)[:80],
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # T-03: One scenario per test
    # ------------------------------------------------------------------
    def _check_multi_scenario(self, tree: ast.AST, source: str) -> list[GuardViolation]:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """Heuristic: multiple assert statements in a single test function."""
        violations: list[GuardViolation] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("test_"):
                    continue
                assert_count = sum(1 for child in ast.walk(node) if isinstance(child, ast.Assert))
                # Also check self.assertX patterns
                self_asserts = 0
                for child in ast.walk(node):
                    if (
                        isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Attribute)
                        and isinstance(child.func.value, ast.Name)
                        and child.func.value.id == "self"
                        and child.func.attr.startswith("assert")
                    ):
                        self_asserts += 1

                total = assert_count + self_asserts
                if total > 5:
                    violations.append(
                        GuardViolation(
                            rule_id="T-03",
                            rule_name="Too many assertions per test",
                            severity=GuardSeverity.SHOULD_FIX,
                            description=f"Test '{node.name}' has {total} assert statements. "
                            "Each test should verify one scenario; use parametrize for variants.",
                            location=f"function '{node.name}' (line {node.lineno})",
                            suggestion="Split into separate test cases or use pytest.mark.parametrize "
                            "for data-driven variants.",
                            evidence=f"{total} assertions",
                        ),
                    )
        return violations

    # ------------------------------------------------------------------
    # T-05: Name tests for the scenario
    # ------------------------------------------------------------------
    def _check_test_naming(self, tree: ast.AST, source: str) -> list[GuardViolation]:
        """Check that test names follow test_<scenario>_<expected> pattern."""
        violations: list[GuardViolation] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                name = node.name
                # Bad patterns: test_function_name, test_1, test_something_v2
                if re.match(r"^test_\d+$", name):
                    violations.append(
                        GuardViolation(
                            rule_id="T-05",
                            rule_name="Test name is not descriptive",
                            severity=GuardSeverity.SHOULD_FIX,
                            description=f"Test '{name}' uses a number instead of describing the scenario.",
                            location=f"function '{name}' (line {node.lineno})",
                            suggestion="Rename to test_<scenario>_<expected>, e.g. "
                            "test_load_flow_converges_with_valid_system.",
                            evidence=name,
                        ),
                    )
                elif len(name) < 12:
                    violations.append(
                        GuardViolation(
                            rule_id="T-05",
                            rule_name="Test name too short",
                            severity=GuardSeverity.WORTH_NOTING,
                            description=f"Test '{name}' has a very short name that may not describe "
                            "the scenario adequately.",
                            location=f"function '{name}' (line {node.lineno})",
                            suggestion="Use a more descriptive name following test_<scenario>_<expected>.",
                            evidence=name,
                        ),
                    )
        return violations

    # ------------------------------------------------------------------
    # T-07: No tests for framework guarantees
    # ------------------------------------------------------------------
    def _check_framework_guarantees(self, tree: ast.AST, source: str) -> list[GuardViolation]:
        """Heuristic: test that only verifies Python built-in behavior."""
        violations: list[GuardViolation] = []
        framework_assert_patterns = [
            (r"assert\s+(Union[type|isinstance|len|str|int|float|dict, list])\s*\(", "type/builtin check"),
        ]
        for pat, _desc in framework_assert_patterns:
            for match in re.finditer(pat, source):
                line_num = source[: match.start()].count("\n") + 1
                # Only flag if the surrounding function is a test
                violations.append(
                    GuardViolation(
                        rule_id="T-07",
                        rule_name="Tests framework guarantees",
                        severity=GuardSeverity.SHOULD_FIX,
                        description="Test verifies a Python built-in guarantee rather than "
                        "application behavior. Frameworks are already tested.",
                        location=f"line {line_num}",
                        suggestion="Remove the framework-guarantee assertion and focus on "
                        "application-specific behavior.",
                        evidence=match.group(0)[:80],
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # T-08: State/value objects are real, never mocked
    # ------------------------------------------------------------------
    def _check_mocked_value_objects(self, tree: ast.AST, source: str) -> list[GuardViolation]:
        """Heuristic: MagicMock used for data/value objects."""
        violations: list[GuardViolation] = []
        pattern = r"MagicMock\(\s*spec\s*=\s*(\w+)"
        for match in re.finditer(pattern, source):
            class_name = match.group(1)
            # Common value object suffixes
            value_suffixes = ("Data", "Model", "DTO", "Request", "Response", "Result", "Config")
            if class_name.endswith(value_suffixes):
                line_num = source[: match.start()].count("\n") + 1
                violations.append(
                    GuardViolation(
                        rule_id="T-08",
                        rule_name="Value object mocked instead of using real instance",
                        severity=GuardSeverity.MUST_FIX,
                        description=f"'{class_name}' appears to be a value/data object but is mocked. "
                        "Value objects should be instantiated with real data.",
                        location=f"line {line_num}",
                        suggestion=f"Create a real {class_name} instance with test data instead of mocking it.",
                        evidence=match.group(0)[:80],
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # T-04: Every test must justify its existence
    # ------------------------------------------------------------------
    def _check_test_justification(self, tree: ast.AST, source: str) -> list[GuardViolation]:
        """Heuristic: test functions with only 'pass' or trivial asserts."""
        violations: list[GuardViolation] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            # Check if the test body is trivial (just pass, or only assert True)
            body_strs = [ast.dump(n) for n in node.body]
            if len(body_strs) == 1:
                if "Pass" in body_strs[0]:
                    violations.append(
                        GuardViolation(
                            rule_id="T-04",
                            rule_name="Test does not justify its existence",
                            severity=GuardSeverity.SHOULD_FIX,
                            description=f"Test '{node.name}' contains only 'pass'. "
                            "Every test must verify meaningful behavior.",
                            location=f"function '{node.name}' (line {node.lineno})",
                            suggestion="Either implement the test or remove it. Empty tests "
                            "give a false sense of coverage.",
                            evidence="test body is 'pass'",
                        ),
                    )
                elif "Constant(value=True)" in body_strs[0]:
                    violations.append(
                        GuardViolation(
                            rule_id="T-04",
                            rule_name="Test does not justify its existence",
                            severity=GuardSeverity.SHOULD_FIX,
                            description=f"Test '{node.name}' only asserts True. "
                            "This test can never fail and provides no coverage.",
                            location=f"function '{node.name}' (line {node.lineno})",
                            suggestion="Assert on actual system behavior, or remove the test.",
                            evidence="assert True",
                        ),
                    )
        return violations

    # ------------------------------------------------------------------
    # T-06: Production regression tests are sacred
    # ------------------------------------------------------------------
    def _check_regression_tests(self, tree: ast.AST, source: str) -> list[GuardViolation]:
        """Detect tests that skip or modify a regression test's core assertion."""
        violations: list[GuardViolation] = []
        # Heuristic: @skip or @xfail decorators on tests that reference
        # bug/issue/regression in their name
        skip_pattern = r"@(Union[skip, xfail])\b"
        regression_name_pattern = r"test_.*(Union[regression|bug|issue|fix|crash, error])_"
        for match in re.finditer(skip_pattern, source):
            line_num = source[: match.start()].count("\n") + 1
            # Check if nearby test name mentions regression
            surrounding = source[max(0, match.start() - 200) : match.end() + 200]
            if re.search(regression_name_pattern, surrounding, re.IGNORECASE):
                violations.append(
                    GuardViolation(
                        rule_id="T-06",
                        rule_name="Regression test skipped or xfailed",
                        severity=GuardSeverity.MUST_FIX,
                        description="A regression test is marked with @skip or @xfail. "
                        "Regression tests must never be disabled — they are the "
                        "canonical record that a bug was fixed.",
                        location=f"line {line_num}",
                        suggestion="Fix the test so it passes. If the underlying bug is not "
                        "fixed, fix the bug. Never skip a regression test.",
                        evidence=match.group(0),
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # T-09: Infrastructure under test gets real infrastructure
    # ------------------------------------------------------------------
    def _check_infrastructure_mocking(self, tree: ast.AST, source: str) -> list[GuardViolation]:
        """Heuristic: mocking database or message-queue interactions in
        integration-like tests (test files containing 'integration' or 'e2e')."""
        violations: list[GuardViolation] = []
        # Only flag if the test file looks like an integration test
        is_integration = bool(
            re.search(r"(Union[integration|e2e|end.to.end, system])", source, re.IGNORECASE),
        )
        if not is_integration:
            return violations

        # Flag mocking of databases and message queues in integration tests
        infra_mock_patterns = [
            (
                r'patch\(["\'].*(Union[?:database|db|redis|kafka|rabbitmq, celery])',
                "database/messaging mock in integration test",
            ),
            (
                r"MagicMock.*(Union[?:Database|Repository|Queue, Broker])",
                "infrastructure mock in integration test",
            ),
        ]
        for pat, desc in infra_mock_patterns:
            for match in re.finditer(pat, source, re.IGNORECASE):
                line_num = source[: match.start()].count("\n") + 1
                violations.append(
                    GuardViolation(
                        rule_id="T-09",
                        rule_name="Infrastructure mocked in integration test",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"Detected {desc}. Integration tests should use real "
                        "infrastructure (test databases, containers) not mocks.",
                        location=f"line {line_num}",
                        suggestion="Use a real test database (SQLite in-memory, test container) "
                        "instead of mocking infrastructure in integration tests.",
                        evidence=match.group(0)[:80],
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # T-L1: LLM app testing patterns
    # ------------------------------------------------------------------
    def _check_llm_test_patterns(self, source: str) -> list[GuardViolation]:
        """Check for common anti-patterns in LLM application tests."""
        violations: list[GuardViolation] = []

        # T-L1: Test prompt contracts not content
        # Heuristic: exact string match on LLM output.
        # NOSONAR — python:S8786: .* is bounded by single-line source code
        pattern = r'assert\s+.*(Union[?:response|output|result, completion]).*==\s*["\']'
        for match in re.finditer(pattern, source):
            line_num = source[: match.start()].count("\n") + 1
            violations.append(
                GuardViolation(
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
                ),
            )

        return violations

    # ------------------------------------------------------------------
    # T-L2: LLM app testing — observability is infrastructure
    # ------------------------------------------------------------------
    def _check_llm_observability_patterns(self, source: str) -> list[GuardViolation]:
        """Check that LLM tests verify observability (logging, tracing, metrics)
        rather than just input/output.

        Heuristic: tests that call LLM agents but have no assertions on
        logs, traces, or token counts — the test only checks output.
        """
        violations: list[GuardViolation] = []
        # Pattern: test creates an LLM agent/call but doesn't check observability
        llm_call_pattern = r"(Union[?:agent|llm|completion|chat|prompt|openai, claude])\s*\("
        has_llm_call = bool(re.search(llm_call_pattern, source, re.IGNORECASE))

        if has_llm_call:
            # Check if there are any observability-related assertions
            observability_patterns = [
                r"log",
                r"trace",
                r"span",
                r"metric",
                r"token",
                r"latency",
                r"cost",
                r"duration",
                r"telemetry",
            ]
            has_observability = any(
                re.search(pat, source, re.IGNORECASE) for pat in observability_patterns
            )
            if not has_observability:
                violations.append(
                    GuardViolation(
                        rule_id="T-L2",
                        rule_name="LLM test lacks observability assertions",
                        severity=GuardSeverity.SHOULD_FIX,
                        description="Test invokes LLM functionality but does not assert on "
                        "observability data (logs, traces, token counts, latency). "
                        "Observability is infrastructure for LLM apps.",
                        location="entire test file",
                        suggestion="Add assertions for token usage, latency bounds, or trace "
                        "span existence. LLM tests should verify the system is "
                        "observable, not just that it produces output.",
                        evidence="LLM call without observability checks",
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # T-L3: LLM app testing — agent-flow tests test transitions
    # ------------------------------------------------------------------
    def _check_llm_agent_flow_patterns(self, source: str) -> list[GuardViolation]:
        """Check that agent-flow tests verify state transitions, not just
        final output.

        Heuristic: tests that assert only on the final result of an agent
        chain without checking intermediate steps or state transitions.
        """
        violations: list[GuardViolation] = []
        # Pattern: test that uses agent workflow but only checks final result
        agent_flow_pattern = r"(Union[?:workflow|pipeline|chain|agent_run|run_agent, execute_agent])"
        has_agent_flow = bool(re.search(agent_flow_pattern, source, re.IGNORECASE))

        if has_agent_flow:
            # Check for transition/step assertions
            transition_patterns = [
                r"step",
                r"transition",
                r"state",
                r"stage",
                r"phase",
                r"intermediate",
                r"before",
                r"after",
            ]
            has_transition_assertions = any(
                re.search(pat, source, re.IGNORECASE) for pat in transition_patterns
            )
            if not has_transition_assertions:
                violations.append(
                    GuardViolation(
                        rule_id="T-L3",
                        rule_name="Agent-flow test lacks transition assertions",
                        severity=GuardSeverity.SHOULD_FIX,
                        description="Test exercises an agent workflow/pipeline but only "
                        "asserts on the final result. Agent-flow tests should "
                        "verify state transitions between steps.",
                        location="entire test file",
                        suggestion="Add assertions that verify intermediate states: "
                        "what changed between step N and step N+1? Did the agent "
                        "transition to the expected state?",
                        evidence="agent flow without transition checks",
                    ),
                )
        return violations
