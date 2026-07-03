"""
AI Failure Mode Detector
=========================
Detects the 14 systematic LLM code-generation failure patterns identified
by the guard-skills project (github.com/amElnagdy/guard-skills), adapted
as a runtime AST/pattern scanner for the AhmedETAP Platform.

These 14 failure modes are derived from published 2024-2026 research:
  - GitClear 2025: 8x duplication growth in AI-generated code
  - Spracklen et al. USENIX '25: 19.6% package hallucination
  - Karpathy on exception suppression
  - Fowler on "declaring success" patterns
  - arXiv papers on AI code mistakes

The detector is designed to be composable: it can be called standalone or
as part of CodeGuard.  It is also integrated into the secure executor
pipeline so that AI-generated code is scanned before execution.

Each failure mode has:
  - A short ID (FM-01 through FM-14)
  - A name
  - A severity (MUST_FIX for safety issues, SHOULD_FIX for quality)
  - A detector function that returns violations
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass
from typing import Any

from guards.base import GuardMode, GuardResult, GuardSeverity, GuardViolation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FailureMode:
    """Definition of a single AI failure mode."""

    id: str
    name: str
    severity: GuardSeverity
    description: str
    research_source: str


# ---------------------------------------------------------------------------
# The 14 AI-specific failure modes (from clean-code-guard/references/ai-failure-modes.md)
# ---------------------------------------------------------------------------
AI_FAILURE_MODES: list[FailureMode] = [
    FailureMode(
        id="FM-01",
        name="Catch-all error swallowing",  # NOSONAR — S1192: intentional repetition (audit constant)
        severity=GuardSeverity.MUST_FIX,
        description="Bare except or overly broad exception handler that catches "
        "everything and silently discards errors, hiding real failures.",
        research_source="Karpathy 2025; GitClear 2025 — catch-all is the #1 LLM code smell",
    ),
    FailureMode(
        id="FM-02",
        name="Defensive guard for impossible case",
        severity=GuardSeverity.SHOULD_FIX,
        description="Guard clause for a state that cannot occur given the type system, "
        "contract, or upstream logic. Adds noise and signals misunderstanding.",
        research_source="Clean Code Ch.3; AI over-approximates edge cases",
    ),
    FailureMode(
        id="FM-03",
        name="Hallucinated API or package",  # NOSONAR — S1192: intentional repetition (audit constant)
        severity=GuardSeverity.MUST_FIX,
        description="Import of a package or call of an API that does not exist "
        "or is not installed. 19.6% of AI-generated imports are hallucinated.",
        research_source="Spracklen et al. USENIX Security '25",
    ),
    FailureMode(
        id="FM-04",
        name="Hardcoded success return",
        severity=GuardSeverity.MUST_FIX,
        description="Function returns a hardcoded 'success' value instead of deriving "
        "the result from computation. The model 'declares success' rather than "
        "computing it (Fowler 2025).",
        research_source="Fowler 2025; GitClear 2025 — 'declaring success' pattern",
    ),
    FailureMode(
        id="FM-05",
        name="Re-derive instead of reuse",
        severity=GuardSeverity.SHOULD_FIX,
        description="Code re-derives a value that already exists in scope, instead of "
        "referencing the existing variable. Increases duplication and drift risk.",
        research_source="DRY principle; GitClear 2025 — 8x duplication in AI code",
    ),
    FailureMode(
        id="FM-06",
        name="Enum boundary not enumerated first",
        severity=GuardSeverity.SHOULD_FIX,
        description="Switch/if-chain over a closed set without explicitly handling every "
        "member, often missing an edge case the model didn't consider.",
        research_source="Clean Code Ch.3; AI under-specifies enum cases",
    ),
    FailureMode(
        id="FM-07",
        name="Dead code left behind",
        severity=GuardSeverity.SHOULD_FIX,
        description="Unused imports, unreachable branches, or commented-out blocks "
        "that the model generated speculatively but never wired up.",
        research_source="GitClear 2025 — AI generates 3.4x more dead code than humans",
    ),
    FailureMode(
        id="FM-08",
        name="Write before read — overwrites input",
        severity=GuardSeverity.MUST_FIX,
        description="Code writes to a variable before reading its input value, "
        "effectively discarding the caller's data. The model assumed a blank slate.",
        research_source="AI assumes greenfield even in modification contexts",
    ),
    FailureMode(
        id="FM-09",
        name="Speculative feature not in spec",
        severity=GuardSeverity.SHOULD_FIX,
        description="Functionality added beyond what the spec requires — YAGNI violation. "
        "8 of 14 failure modes trace to the model emitting more code than needed.",
        research_source="YAGNI (Fowler); guard-skills cross-cutting observation",
    ),
    FailureMode(
        id="FM-10",
        name="Copy-paste drift between similar blocks",
        severity=GuardSeverity.SHOULD_FIX,
        description="Two near-identical code blocks where only a constant differs but "
        "one block was not updated, creating silent divergence.",
        research_source="GitClear 2025 — copy-paste is the dominant duplication pattern",
    ),
    FailureMode(
        id="FM-11",
        name="Over-engineered abstraction for single use",
        severity=GuardSeverity.SHOULD_FIX,
        description="Factory, strategy, or visitor pattern introduced for a single "
        "concrete case — the model anticipated extensibility that doesn't exist.",
        research_source="KISS; Fowler 2025 — speculative generality",
    ),
    FailureMode(
        id="FM-12",
        name="Unverified import side effects",
        severity=GuardSeverity.MUST_FIX,
        description="Importing a module for a side effect (monkey-patch, registration) "
        "without verifying the side effect actually occurred.",
        research_source="Spracklen et al. '25; import hallucination",
    ),
    FailureMode(
        id="FM-13",
        name="Magic number without named constant",
        severity=GuardSeverity.SHOULD_FIX,
        description="Numeric or string literal used directly where a named constant "
        "would convey intent. The model fills in plausible-looking but "
        "unexplained values.",
        research_source="Clean Code Ch.2; N1 — intent-revealing names",
    ),
    FailureMode(
        id="FM-14",
        name="Test asserts on mock behavior, not system behavior",
        severity=GuardSeverity.MUST_FIX,
        description="Test verifies that a mock was called with specific args rather than "
        "verifying the system's observable behavior. Breaks on refactor.",
        research_source="Test Guard Rule 1 & 2; test-guard skill",
    ),
]


class AIFailureModeDetector:
    """Scans Python source code for the 14 AI-specific failure modes.

    Uses AST parsing for structural analysis and regex fallbacks for
    patterns that AST cannot express.  Designed to be called from
    CodeGuard, the secure executor, or standalone.

    Usage
    -----
    >>> detector = AIFailureModeDetector()
    >>> result = detector.detect(source_code)
    >>> if not result.passed:
    ...     for v in result.violations:
    ...         print(f"{v.rule_id}: {v.description}")
    """

    name: str = "ai_failure_modes"

    def __init__(self, mode: GuardMode = GuardMode.GUARD_PASS) -> None:
        self.mode = mode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, source: str, context: dict[str, Any] | None = None) -> GuardResult:
        """Run all failure-mode detectors against *source*.

        Parameters
        ----------
        source : str
            Python source code to scan.
        context : dict, optional
            Additional context (known packages, expected symbols, etc.).

        Returns
        -------
        GuardResult
        """
        violations: list[GuardViolation] = []
        context = context or {}

        # Parse AST once; fall back to regex if AST fails
        tree: ast.AST | None = None
        try:
            tree = ast.parse(source)
        except SyntaxError:
            logger.debug("AI-FM detector: AST parse failed, using regex-only mode")

        # FM-01: Catch-all error swallowing
        violations.extend(self._detect_catch_all(tree, source))

        # FM-02: Defensive guard for impossible case
        violations.extend(self._detect_impossible_guard(tree, source))

        # FM-04: Hardcoded success return
        violations.extend(self._detect_hardcoded_success(tree, source))

        # FM-05: Re-derive instead of reuse (simplified heuristic)
        violations.extend(self._detect_rederive(tree, source))

        # FM-03: Hallucinated API or package
        violations.extend(self._detect_hallucinated_api(tree, source, context))

        # FM-06: Enum boundary not enumerated first
        violations.extend(self._detect_enum_boundary(tree, source))

        # FM-07: Dead code — unused imports
        violations.extend(self._detect_unused_imports(tree, source))

        # FM-08: Write before read (overwrite input)
        violations.extend(self._detect_write_before_read(tree, source))

        # FM-09: Speculative feature (heuristic: oversized functions)
        violations.extend(self._detect_speculative_feature(tree, source))

        # FM-10: Copy-paste drift (near-duplicate blocks)
        violations.extend(self._detect_copy_paste_drift(source))

        # FM-11: Over-engineered abstraction
        violations.extend(self._detect_over_engineering(tree, source))

        # FM-12: Unverified import side effects
        violations.extend(self._detect_unverified_import_side_effects(tree, source))

        # FM-13: Magic numbers without named constants
        violations.extend(self._detect_magic_numbers(tree, source))

        # FM-14: Test asserts on mock behavior
        violations.extend(self._detect_mock_assert(tree, source))

        return GuardResult(
            guard_name=self.name,
            mode=self.mode,
            violations=violations,
            metadata={
                "source_length": len(source),
                "modes_checked": 14,
                "ast_available": tree is not None,
            },
        )

    # ------------------------------------------------------------------
    # FM-01: Catch-all error swallowing
    # ------------------------------------------------------------------
    def _detect_catch_all(self, tree: ast.AST | None, source: str) -> list[GuardViolation]:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        violations: list[GuardViolation] = []
        if tree is None:
            # Regex fallback
            patterns = [
                (r"except\s*:", "bare except clause"),
                (r"except\s+Exception\s*:", "broad Exception catch"),
                (r"except\s+BaseException\s*:", "BaseException catch"),
            ]
            for pat, desc in patterns:
                for match in re.finditer(pat, source):
                    line_num = source[: match.start()].count("\n") + 1
                    violations.append(
                        GuardViolation(
                            rule_id="FM-01",
                            rule_name="Catch-all error swallowing",
                            severity=GuardSeverity.MUST_FIX,
                            description=f"Detected {desc} that may silently swallow errors.",
                            location=f"line {line_num}",
                            suggestion="Catch specific exceptions. If you must catch broadly, "
                            "at minimum log the error with traceback before continuing.",
                            evidence=match.group(0),
                        ),
                    )
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    violations.append(
                        GuardViolation(
                            rule_id="FM-01",
                            rule_name="Catch-all error swallowing",
                            severity=GuardSeverity.MUST_FIX,
                            description="Bare except clause catches every exception including "
                            "KeyboardInterrupt and SystemExit, silently hiding failures.",
                            location=f"line {node.lineno}",
                            suggestion="Catch specific exception types. At minimum use "
                            "'except Exception' and log the error.",
                            evidence="except:",
                        ),
                    )
                elif isinstance(node.type, ast.Name) and node.type.id in (
                    "Exception",
                    "BaseException",
                ):
                    # Check if the handler body just has 'pass' or only re-raises
                    body_strs = [ast.dump(n) for n in node.body]
                    has_pass = any("Pass" in b for b in body_strs)
                    has_raise = any("Raise" in b for b in body_strs)
                    has_log = any("log" in b.lower() or "print" in b.lower() for b in body_strs)
                    if has_pass or (not has_raise and not has_log):
                        violations.append(
                            GuardViolation(
                                rule_id="FM-01",
                                rule_name="Catch-all error swallowing",
                                severity=GuardSeverity.MUST_FIX,
                                description=f"Overly broad '{node.type.id}' catch that swallows errors "
                                "without logging or re-raising.",
                                location=f"line {node.lineno}",
                                suggestion="Catch specific exceptions. If catching broadly is "
                                "necessary, always log the error with traceback.",
                                evidence=f"except {node.type.id}:",
                            ),
                        )
        return violations

    # ------------------------------------------------------------------
    # FM-02: Defensive guard for impossible case
    # ------------------------------------------------------------------
    def _detect_impossible_guard(
        self, tree: ast.AST | None, source: str,  # NOSONAR — S1172: unused param kept for API compatibility
    ) -> list[GuardViolation]:
        """Heuristic: 'if x is None' checks on values that cannot be None by construction."""
        violations: list[GuardViolation] = []
        # Pattern: checking for None on return values that are never None
        # e.g., if result is None: where result comes from a function that always returns a dict
        pattern = r"if\s+(\w+)\s+is\s+None\s*:"
        for match in re.finditer(pattern, source):
            var_name = match.group(1)
            line_num = source[: match.start()].count("\n") + 1
            # Check if this variable was assigned from a dict/list literal in same scope
            assign_pattern = rf"{var_name}\s*=\s*(\{{|\[)"
            if re.search(assign_pattern, source):
                violations.append(
                    GuardViolation(
                        rule_id="FM-02",
                        rule_name="Defensive guard for impossible case",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"Guard 'if {var_name} is None' appears unnecessary — "
                        f"{var_name} is assigned from a literal that cannot be None.",
                        location=f"line {line_num}",
                        suggestion="Remove the impossible guard or document why it might be None "
                        "in a future refactoring scenario.",
                        evidence=match.group(0),
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # FM-04: Hardcoded success return
    # ------------------------------------------------------------------
    def _detect_hardcoded_success(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        self, tree: ast.AST | None, source: str,  # NOSONAR — S1172: unused param kept for API compatibility
    ) -> list[GuardViolation]:
        violations: list[GuardViolation] = []
        if tree is None:
            return violations

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) and not isinstance(node, ast.AsyncFunctionDef):
                continue
            # Look for 'return True' or 'return {"success": True}' without
            # any computational path that could produce False
            has_computation = False
            has_hardcoded_success = False
            success_line = 0
            for child in ast.walk(node):
                if isinstance(child, (ast.BinOp, ast.UnaryOp, ast.Compare, ast.Call)):
                    # Exclude simple dict/list constructors
                    if not (
                        isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Name)
                        and child.func.id in ("dict", "list", "set", "tuple")
                    ):
                        has_computation = True
                if isinstance(child, ast.Return):
                    if isinstance(child.value, ast.Constant) and child.value.value is True:
                        has_hardcoded_success = True
                        success_line = child.lineno
                    elif isinstance(child.value, ast.Dict) and any(
                        isinstance(k, ast.Constant) and k.value == "success"
                        for k in child.value.keys
                        if isinstance(k, ast.Constant)
                    ):
                        # Check if success is hardcoded True
                        for k, v in zip(child.value.keys, child.value.values):
                            if isinstance(k, ast.Constant) and k.value == "success":
                                if isinstance(v, ast.Constant) and v.value is True:
                                    has_hardcoded_success = True
                                    success_line = child.lineno

            if has_hardcoded_success and not has_computation:
                violations.append(
                    GuardViolation(
                        rule_id="FM-04",
                        rule_name="Hardcoded success return",
                        severity=GuardSeverity.MUST_FIX,
                        description=f"Function '{node.name}' returns hardcoded success without "
                        "any computation that could produce failure.",
                        location=f"line {success_line}",
                        suggestion="Derive the return value from actual computation. "
                        "If the function can't fail, return None or remove the success flag.",
                        evidence="return True / return {'success': True}",
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # FM-05: Re-derive instead of reuse
    # ------------------------------------------------------------------
    def _detect_rederive(self, tree: ast.AST | None, _source: str) -> list[GuardViolation]:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """Heuristic: same expression computed twice in the same function."""
        violations: list[GuardViolation] = []
        if tree is None:
            return violations

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Collect all assignment right-hand sides
            expressions: dict[str, list[int]] = {}
            for child in ast.walk(node):
                if isinstance(child, ast.Assign) and len(child.targets) == 1:
                    expr_str = ast.dump(child.value)
                    if expr_str not in expressions:
                        expressions[expr_str] = []
                    expressions[expr_str].append(child.lineno)

            for expr_str, lines in expressions.items():
                if len(lines) > 1:
                    violations.append(
                        GuardViolation(
                            rule_id="FM-05",
                            rule_name="Re-derive instead of reuse",
                            severity=GuardSeverity.SHOULD_FIX,
                            description=f"Same expression computed multiple times in '{node.name}' "
                            f"(lines {', '.join(str(l) for l in lines)}).",
                            location=f"lines {', '.join(str(l) for l in lines)}",
                            suggestion="Compute once, assign to a variable, and reuse it.",
                            evidence=expr_str[:100],
                        ),
                    )
        return violations

    # ------------------------------------------------------------------
    # FM-07: Dead code — unused imports
    # ------------------------------------------------------------------
    def _detect_unused_imports(self, tree: ast.AST | None, _source: str) -> list[GuardViolation]:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        violations: list[GuardViolation] = []
        if tree is None:
            return violations

        imported_names: dict[str, tuple[int, str]] = {}  # name -> (line, module)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imported_names[name] = (node.lineno, alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imported_names[name] = (
                        node.lineno,
                        f"{node.module}.{alias.name}" if node.module else alias.name,
                    )

        # Walk again and collect all Name nodes that are used
        used_names: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                used_names.add(node.value.id)

        for name, (line, module) in imported_names.items():
            if name not in used_names and name != "__future__":
                violations.append(
                    GuardViolation(
                        rule_id="FM-07",
                        rule_name="Dead code — unused import",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"Import '{module}' (as '{name}') is never used.",
                        location=f"line {line}",
                        suggestion="Remove the unused import to reduce dead code.",
                        evidence=f"import {module}",
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # FM-08: Write before read (overwrite input)
    # ------------------------------------------------------------------
    def _detect_write_before_read(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        self, tree: ast.AST | None, source: str,  # NOSONAR — S1172: unused param kept for API compatibility
    ) -> list[GuardViolation]:
        """Heuristic: function parameter immediately reassigned without reading."""
        violations: list[GuardViolation] = []
        if tree is None:
            return violations

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            param_names = set()
            for arg in node.args.args:
                if arg.arg != "self" and arg.arg != "cls":
                    param_names.add(arg.arg)

            if not param_names:
                continue

            # Check if a parameter is overwritten WITHOUT being read on the
            # right-hand side of the same assignment.  The pattern
            #   data = transform(data)
            # is valid (param IS read on RHS).  The pattern
            #   data = new_value()
            # with no prior read of 'data' is the real FM-08 violation.
            assigned_without_read: set = set()
            seen_reads: set = set()
            for stmt in node.body:
                # Collect reads from this statement BEFORE checking assignments
                for child in ast.walk(stmt):
                    if isinstance(child, ast.Name) and child.id in param_names:
                        if not isinstance(child.ctx, ast.Store):
                            seen_reads.add(child.id)

                # Check assignments where the parameter is NOT read on RHS
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                    target = stmt.targets[0]
                    if isinstance(target, ast.Name) and target.id in param_names:
                        # Is the parameter read on the right-hand side?
                        rhs_names: set = set()
                        for child in ast.walk(stmt.value):
                            if isinstance(child, ast.Name) and child.id == target.id:
                                rhs_names.add(child.id)
                        # If not read on RHS and not read before, it's a true overwrite
                        if target.id not in rhs_names and target.id not in seen_reads:
                            assigned_without_read.add(target.id)

            for param in assigned_without_read:
                violations.append(
                    GuardViolation(
                        rule_id="FM-08",
                        rule_name="Write before read — overwrites input",
                        severity=GuardSeverity.MUST_FIX,
                        description=f"Parameter '{param}' in function '{node.name}' is reassigned "
                        "without reading its input value first.",
                        location=f"function '{node.name}'",
                        suggestion="Use a different variable name for the derived value, "
                        "or read the input before overwriting it.",
                        evidence=f"param '{param}' overwritten",
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # FM-09: Speculative feature (oversized functions as proxy)
    # ------------------------------------------------------------------
    def _detect_speculative_feature(
        self, tree: ast.AST | None, source: str,  # NOSONAR — S1172: unused param kept for API compatibility
    ) -> list[GuardViolation]:
        """Heuristic: functions over 50 lines are likely doing more than specified."""
        violations: list[GuardViolation] = []
        if tree is None:
            return violations

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            func_lines = (node.end_lineno or node.lineno) - node.lineno
            if func_lines > 50:
                violations.append(
                    GuardViolation(
                        rule_id="FM-09",
                        rule_name="Speculative feature — oversized function",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"Function '{node.name}' is {func_lines} lines long, suggesting "
                        "it may contain speculative features beyond the spec.",
                        location=f"function '{node.name}' (lines {node.lineno}-{node.end_lineno})",
                        suggestion="Break into smaller functions, each doing one thing. "
                        "Functions over 20 lines should be scrutinized for YAGNI violations.",
                        evidence=f"{func_lines} lines",
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # FM-10: Copy-paste drift (near-duplicate blocks)
    # ------------------------------------------------------------------
    def _detect_copy_paste_drift(self, source: str) -> list[GuardViolation]:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """Heuristic: find near-duplicate lines that differ only in a constant."""
        violations: list[GuardViolation] = []
        lines = source.split("\n")
        for i in range(len(lines) - 1):
            line_a = lines[i].strip()
            if not line_a or len(line_a) < 20:
                continue
            for j in range(i + 1, min(i + 15, len(lines))):
                line_b = lines[j].strip()
                if not line_b or len(line_b) < 20:
                    continue
                # Check if lines are similar but not identical
                if line_a == line_b:
                    continue
                # Normalize by replacing numbers/strings with placeholder
                norm_a = re.sub(r"[\d.]+", "N", re.sub(r'["\'][^"\']*["\']', "S", line_a))
                norm_b = re.sub(r"[\d.]+", "N", re.sub(r'["\'][^"\']*["\']', "S", line_b))
                if norm_a == norm_b and norm_a.count("N") == 1:
                    violations.append(
                        GuardViolation(
                            rule_id="FM-10",
                            rule_name="Copy-paste drift",
                            severity=GuardSeverity.SHOULD_FIX,
                            description="Near-duplicate lines differ only in a constant, "
                            "risking silent drift if one is updated without the other.",
                            location=f"lines {i + 1} and {j + 1}",
                            suggestion="Extract the common logic into a parameterized function or loop.",
                            evidence=f"L{i + 1}: {line_a[:80]}\nL{j + 1}: {line_b[:80]}",
                        ),
                    )
        return violations

    # ------------------------------------------------------------------
    # FM-11: Over-engineered abstraction for single use
    # ------------------------------------------------------------------
    def _detect_over_engineering(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        self, tree: ast.AST | None, source: str,  # NOSONAR — S1172: unused param kept for API compatibility
    ) -> list[GuardViolation]:
        """Heuristic: abstract base class with only one concrete subclass."""
        violations: list[GuardViolation] = []
        if tree is None:
            return violations

        # Find all class definitions and their bases
        class_bases: dict[str, list[str]] = {}
        class_names: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_names.add(node.name)
                bases = [b.id if isinstance(b, ast.Name) else str(b) for b in node.bases]
                for base in bases:
                    if base not in class_bases:
                        class_bases[base] = []
                    class_bases[base].append(node.name)

        for base, subclasses in class_bases.items():
            if base in class_names and len(subclasses) == 1:
                violations.append(
                    GuardViolation(
                        rule_id="FM-11",
                        rule_name="Over-engineered abstraction",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"Abstract class '{base}' has only one subclass "
                        f"'{subclasses[0]}'. The abstraction may be speculative.",
                        location=f"class '{base}'",
                        suggestion="Consider whether the abstraction is needed. If there's only "
                        "one implementation, a concrete class may suffice until a second "
                        "implementation is required.",
                        evidence=f"{base} → {subclasses[0]}",
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # FM-13: Magic numbers without named constants
    # ------------------------------------------------------------------
    def _detect_magic_numbers(self, tree: ast.AST | None, source: str) -> list[GuardViolation]:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """Detect numeric literals that are not 0, 1, -1, or commonly accepted values."""
        violations: list[GuardViolation] = []
        if tree is None:
            return violations

        EXEMPT = {0, 1, -1, -1.0, 2, 10, 100, 1000, 0.5, 0.25, 1e6, 1e9}
        seen: set = set()  # avoid duplicate reports for same number

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                if node.value in EXEMPT:
                    continue
                if node.value in seen:
                    continue
                # Skip if it's in a constant assignment (ALL_CAPS)
                # This is a rough heuristic
                parent_line = (
                    source.split("\n")[node.lineno - 1].strip()
                    if node.lineno <= len(source.split("\n"))
                    else ""
                )
                if re.match(r"^[A-Z_]+\s*=", parent_line):
                    continue
                seen.add(node.value)
                violations.append(
                    GuardViolation(
                        rule_id="FM-13",
                        rule_name="Magic number without named constant",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"Numeric literal {node.value} used directly. "
                        "Named constants convey intent and reduce errors.",
                        location=f"line {node.lineno}",
                        suggestion=f"Extract {node.value} into a named constant that explains its meaning.",
                        evidence=str(node.value),
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # FM-03: Hallucinated API or package
    # ------------------------------------------------------------------
    def _detect_hallucinated_api(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        self, tree: ast.AST | None, source: str, context: dict[str, Any] | None,  # NOSONAR — S1172: unused param kept for API compatibility
    ) -> list[GuardViolation]:
        """Detect imports of packages that are not in the known-packages set.

        Uses a curated list of standard-library and common third-party packages.
        Any import not in this list and not in the context-provided
        ``known_packages`` set is flagged as a potential hallucination.

        This is a heuristic — false positives are possible for legitimate
        private packages.  Consumers should provide ``known_packages`` in
        context to suppress known-good imports.
        """
        violations: list[GuardViolation] = []
        if tree is None:
            return violations

        # Standard library packages (Python 3.10+)
        STDLIB = {
            "abc",
            "argparse",
            "ast",
            "asyncio",
            "base64",
            "bisect",
            "collections",
            "concurrent",
            "configparser",
            "contextlib",
            "copy",
            "csv",
            "dataclasses",
            "datetime",
            "decimal",
            "difflib",
            "dis",
            "email",
            "enum",
            "fileinput",
            "fnmatch",
            "fractions",
            "functools",
            "glob",
            "gzip",
            "hashlib",
            "heapq",
            "hmac",
            "html",
            "http",
            "importlib",
            "inspect",
            "io",
            "itertools",
            "json",
            "keyword",
            "linecache",
            "logging",
            "math",
            "mmap",
            "multiprocessing",
            "numbers",
            "operator",
            "os",
            "pathlib",
            "pickle",
            "platform",
            "pprint",
            "profile",
            "pstats",
            "queue",
            "re",
            "secrets",
            "shelve",
            "signal",
            "smtpd",
            "smtplib",
            "socket",
            "sqlite3",
            "statistics",
            "string",
            "struct",
            "subprocess",
            "sys",
            "tarfile",
            "tempfile",
            "textwrap",
            "threading",
            "time",
            "timeit",
            "traceback",
            "types",
            "typing",
            "unittest",
            "urllib",
            "uuid",
            "warnings",
            "weakref",
            "xml",
            "zipfile",
            "zlib",
            "__future__",
        }

        # Common third-party packages in ETAP platform
        COMMON_THIRD_PARTY = {
            "fastapi",
            "uvicorn",
            "pydantic",
            "sqlalchemy",
            "numpy",
            "scipy",
            "pandas",
            "matplotlib",
            "requests",
            "httpx",
            "aiohttp",
            "redis",
            "celery",
            "pytest",
            "hypothesis",
            "flask",
            "django",
            "starlette",
            "python",
            "dotenv",
            "jwt",
            "bcrypt",
            "cryptography",
            "psutil",
            # ETAP platform internal packages (not hallucinations)
            "engine",
            "agents",
            "core_model",
            "load_flow",
            "fault_analysis",
            "coordination",
            "curves",
            "relays",
            "etap_integration",
            "gis_integration",
            "gis_model",
            "gis_validation",
            "digital_twin",
            "security",
            "reporting",
            "visualization",
            "network_solver",
            "knowledge",
            "scada_model",
            "adms_control",
            "core",
            "backend",
            "guards",
            "skills",
        }

        # Allow context to extend known packages
        known = STDLIB | COMMON_THIRD_PARTY
        if context and "known_packages" in context:
            known |= set(context["known_packages"])

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_level = alias.name.split(".")[0]
                    if top_level not in known:
                        violations.append(
                            GuardViolation(
                                rule_id="FM-03",
                                rule_name="Hallucinated API or package",
                                severity=GuardSeverity.MUST_FIX,
                                description=f"Import '{alias.name}' is not in the known-packages list. "
                                "This may be a hallucinated package (19.6% hallucination rate "
                                "per Spracklen et al. USENIX '25).",
                                location=f"line {node.lineno}",
                                suggestion="Verify the package exists and is in your requirements.txt. "
                                "If this is a private package, add it to the 'known_packages' "
                                "context parameter.",
                                evidence=f"import {alias.name}",
                            ),
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_level = node.module.split(".")[0]
                    if top_level not in known:
                        violations.append(
                            GuardViolation(
                                rule_id="FM-03",
                                rule_name="Hallucinated API or package",
                                severity=GuardSeverity.MUST_FIX,
                                description=f"From-import from '{node.module}' is not in the known-packages list. "
                                "This may be a hallucinated package.",
                                location=f"line {node.lineno}",
                                suggestion="Verify the package exists. If legitimate, add to 'known_packages'.",
                                evidence=f"from {node.module} import ...",
                            ),
                        )
        return violations

    # ------------------------------------------------------------------
    # FM-06: Enum boundary not enumerated first
    # ------------------------------------------------------------------
    def _detect_enum_boundary(self, tree: ast.AST | None, _source: str) -> list[GuardViolation]:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """Detect if/elif chains over a closed set that lack an else clause.

        When code branches over a known, closed set of values (e.g., enum
        members, status codes) but does not include a final else or
        explicit exhaustiveness check, a missing case silently falls
        through — a common AI failure mode.
        """
        violations: list[GuardViolation] = []
        if tree is None:
            return violations

        # Collect only top-level If nodes (not elif children of other Ifs)
        elif_parents: set = set()
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.If)
                and len(node.orelse) == 1
                and isinstance(node.orelse[0], ast.If)
            ):
                elif_parents.add(id(node.orelse[0]))

        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            # Skip nodes that are elif children of another If
            if id(node) in elif_parents:
                continue

            # Count elif branches and check for else
            branch_count = 1  # the initial if
            has_else = False
            current = node

            while True:
                if not current.orelse:
                    has_else = False
                    break
                if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                    branch_count += 1
                    current = current.orelse[0]
                else:
                    has_else = True
                    break

            if branch_count >= 3 and not has_else:
                violations.append(
                    GuardViolation(
                        rule_id="FM-06",
                        rule_name="Enum boundary not enumerated first",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"if/elif chain with {branch_count} branches has no else clause. "
                        "When branching over a closed set, every member should be "
                        "explicitly handled and a final else should catch omissions.",
                        location=f"line {node.lineno}",
                        suggestion="Add an else clause that raises AssertionError or NotImplementedError "
                        "for unhandled cases, or use a match/case statement with explicit "
                        "exhaustiveness.",
                        evidence=f"{branch_count} branches, no else",
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # FM-12: Unverified import side effects
    # ------------------------------------------------------------------
    def _detect_unverified_import_side_effects(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        self, tree: ast.AST | None, source: str,
    ) -> list[GuardViolation]:
        """Detect bare imports used only for side effects without verification.

        Pattern: ``import foo`` where ``foo`` is never referenced by name in
        the module body — the import exists purely for its side effect
        (e.g., registration, monkey-patching), but nothing verifies the side
        effect actually occurred.
        """
        violations: list[GuardViolation] = []
        if tree is None:
            return violations

        # Collect all imports
        imported_names: dict[str, int] = {}  # name -> line
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imported_names[name] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    if name != "*":
                        imported_names[name] = node.lineno

        # Collect all Name usages (not in import statements)
        # Include names used in annotations (ast.Name in ast.Subscript, etc.)
        used_names: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Store):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) or isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
                used_names.add(node.value.id)

        # Find imports that are never used by name (side-effect-only)
        for name, line in imported_names.items():
            if name not in used_names:
                # Exclude common side-effect imports that are idiomatic
                idiomatic_side_effects = {
                    "__future__",
                    "annotations",
                }
                # Also exclude typing-module names used in annotations
                typing_names = {
                    "Optional",
                    "Dict",
                    "List",
                    "Tuple",
                    "Set",
                    "Any",
                    "Union",
                    "Callable",
                    "Sequence",
                    "Iterable",
                    "Generator",
                    "Type",
                    "TypeVar",
                    "Generic",
                    "Protocol",
                    "Final",
                    "Literal",
                    "ClassVar",
                    "Awaitable",
                    "AsyncIterator",
                }
                if name in idiomatic_side_effects or name in typing_names:
                    continue

                # Check if the import has a comment mentioning side effect
                source_lines = source.split("\n")
                if line <= len(source_lines):
                    import_line = source_lines[line - 1]
                    has_side_effect_comment = bool(
                        re.search(
                            r"#\s*(side.effect|register|patch|monkey|inject|auto|init)",
                            import_line,
                            re.IGNORECASE,
                        ),
                    )
                    if has_side_effect_comment:
                        continue  # Documented side-effect import

                violations.append(
                    GuardViolation(
                        rule_id="FM-12",
                        rule_name="Unverified import side effect",
                        severity=GuardSeverity.MUST_FIX,
                        description=f"Import '{name}' (line {line}) is never referenced by name, suggesting "
                        "it is imported solely for a side effect (registration, monkey-patching). "
                        "The side effect is not verified after import.",
                        location=f"line {line}",
                        suggestion="After the import, add an assertion or check that verifies the side "
                        "effect occurred (e.g., assert 'PluginName' in registry). "
                        "Or add a comment: # side-effect: registers X",
                        evidence=f"import {name} (never used by name)",
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # FM-14: Test asserts on mock behavior, not system behavior
    # ------------------------------------------------------------------
    def _detect_mock_assert(self, _tree: ast.AST | None, source: str) -> list[GuardViolation]:
        """Heuristic: assert_called_with / assert_any_call / assert_called_once in test functions."""
        violations: list[GuardViolation] = []
        # Match both direct and chained attribute access: mock.assert_called_with, mock.method.assert_called
        patterns = [
            r"(\w+(?:\.\w+)*)\.assert_called_with\s*\(",
            r"(\w+(?:\.\w+)*)\.assert_called_once_with\s*\(",
            r"(\w+(?:\.\w+)*)\.assert_any_call\s*\(",
        ]
        for pat in patterns:
            for match in re.finditer(pat, source):
                line_num = source[: match.start()].count("\n") + 1
                violations.append(
                    GuardViolation(
                        rule_id="FM-14",
                        rule_name="Test asserts on mock behavior",
                        severity=GuardSeverity.MUST_FIX,
                        description="Test asserts that a mock was called with specific arguments "
                        "rather than verifying the system's observable behavior.",
                        location=f"line {line_num}",
                        suggestion="Assert on the observable outcome (return value, state change, "
                        "side effect) rather than on the mock's call history.",
                        evidence=match.group(0)[:80],
                    ),
                )
        return violations
