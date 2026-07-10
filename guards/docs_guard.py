"""
Docs Guard — Documentation Accuracy Gate
==========================================
Adapted from the docs-guard skill (github.com/amElnagdy/guard-skills).

Implements 10 documentation accuracy rules:

  D-01: Every referenced symbol must exist
  D-02: Every code sample must work
  D-03: Document actual behavior, not intended
  D-04: No unverifiable claims
  D-05: Versions are explicit
  D-06: A code change owes a docs change
  D-07: No filler, no slop
  D-08: Don't paraphrase upstream docs — link
  D-09: Examples cover the failure path too
  D-10: Navigation tells the truth
"""

from __future__ import annotations

import logging
import re
from typing import Any

from guards.base import BaseGuard, GuardResult, GuardSeverity, GuardViolation

logger = logging.getLogger(__name__)


class DocsGuard(BaseGuard):
    """Scans documentation for accuracy violations.

    Usage
    -----
    >>> guard = DocsGuard()
    >>> result = guard.scan(markdown_docs)
    """

    name: str = "docs_guard"

    def scan(
        self, source: str, language: str = "markdown", context: dict[str, Any] | None = None,
    ) -> GuardResult:
        violations: list[GuardViolation] = []
        context = context or {}

        # D-01: Referenced symbols must exist (if Python source provided)
        if context.get("python_source"):
            violations.extend(self._check_symbol_references(source, context["python_source"]))

        # D-02: Every code sample must work
        violations.extend(self._check_code_samples(source))

        # D-03: Document actual behavior, not intended
        violations.extend(self._check_actual_vs_intended(source))

        # D-04: No unverifiable claims
        violations.extend(self._check_unverifiable_claims(source))

        # D-05: Versions are explicit
        violations.extend(self._check_version_clarity(source))

        # D-06: A code change owes a docs change
        violations.extend(self._check_docs_owed(source, context))

        # D-07: No filler, no slop
        violations.extend(self._check_filler(source))

        # D-08: Don't paraphrase — link
        violations.extend(self._check_paraphrased_docs(source))

        # D-09: Examples cover the failure path
        violations.extend(self._check_failure_paths(source))

        # D-10: Navigation tells the truth
        violations.extend(self._check_navigation_truth(source))

        return GuardResult(
            guard_name=self.name,
            mode=self.mode,
            violations=violations,
            metadata={
                "language": language,
                "source_length": len(source),
                "rules_checked": 10,
            },
        )

    # ------------------------------------------------------------------
    # D-01: Referenced symbols must exist
    # ------------------------------------------------------------------
    def _check_symbol_references(self, docs: str, python_source: str) -> list[GuardViolation]:
        """Check that Python symbols referenced in docs actually exist in code."""
        violations: list[GuardViolation] = []

        # Extract class and function names from Python source
        import ast

        defined_symbols: set = set()
        try:
            tree = ast.parse(python_source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    defined_symbols.add(node.name)
        except SyntaxError:
            return violations

        # Find Python-style symbol references in docs
        # Pattern: ``ClassName``, `function_name`, ::ClassName, etc.
        ref_pattern = r"(``|`|::)([A-Za-z_]\w*)"
        for match in re.finditer(ref_pattern, docs):
            symbol = match.group(1)
            if symbol.startswith("_") or symbol in ("True", "False", "None", "self", "cls"):
                continue
            if symbol not in defined_symbols and not symbol.isupper():
                line_num = docs[: match.start()].count("\n") + 1
                violations.append(
                    GuardViolation(
                        rule_id="D-01",
                        rule_name="Referenced symbol does not exist",
                        severity=GuardSeverity.MUST_FIX,
                        description=f"Documentation references '{symbol}' but it does not exist "
                        "in the source code.",
                        location=f"line {line_num}",
                        suggestion="Add the symbol to the source code, or remove/update the reference.",
                        evidence=f"symbol: {symbol}",
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # D-04: No unverifiable claims
    # ------------------------------------------------------------------
    def _check_unverifiable_claims(self, source: str) -> list[GuardViolation]:
        """Heuristic: phrases that suggest claims without evidence."""
        violations: list[GuardViolation] = []
        unverifiable_patterns = [
            (
                r"(?i)(?:it\s+is\s+)?(Union[?:well\s*-?known|obvious|clearly|everyone\s+knows, undoubtedly])\s+that",
                "unverifiable claim",
            ),
            (
                r"(?i)(?:the\s+)?(Union[?:best|worst|fastest|slowest|most\s+efficient, only\s+way])\s+(Union[?:way|method|approach, solution])",
                "superlative without evidence",
            ),
            (
                r"(?i)(Union[?:always|never|all|none, every])\s+(Union[?:works|fails|returns, produces])",
                "absolute claim without qualification",
            ),
        ]
        for pat, desc in unverifiable_patterns:
            for match in re.finditer(pat, source):
                line_num = source[: match.start()].count("\n") + 1
                violations.append(
                    GuardViolation(
                        rule_id="D-04",
                        rule_name="Unverifiable claim",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"Documentation contains an {desc}: '{match.group(0)[:60]}'. "
                        "Claims should be verifiable against source code or cited sources.",
                        location=f"line {line_num}",
                        suggestion="Provide evidence (measurement, citation, code reference) or "
                        "qualify the claim (e.g., 'typically', 'in our testing').",
                        evidence=match.group(0)[:80],
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # D-05: Versions are explicit
    # ------------------------------------------------------------------
    def _check_version_clarity(self, source: str) -> list[GuardViolation]:
        """Check that version references are explicit, not relative."""
        violations: list[GuardViolation] = []
        # Pattern: "latest", "current version", "new" without a specific version number
        vague_version_patterns = [
            r"(?i)(?:the\s+)?(Union[?:latest|current|new|recent, stable])\s+(Union[?:version, release])\s+(?:of\s+)?",
        ]
        for pat in vague_version_patterns:
            for match in re.finditer(pat, source):
                line_num = source[: match.start()].count("\n") + 1
                violations.append(
                    GuardViolation(
                        rule_id="D-05",
                        rule_name="Vague version reference",
                        severity=GuardSeverity.SHOULD_FIX,
                        description="Documentation refers to a version without specifying it. "
                        "Vague version references become stale quickly.",
                        location=f"line {line_num}",
                        suggestion="Specify the exact version number (e.g., 'v2.1.0' or 'as of 2025-06').",
                        evidence=match.group(0)[:80],
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # D-07: No filler, no slop
    # ------------------------------------------------------------------
    def _check_filler(self, source: str) -> list[GuardViolation]:
        """Heuristic: paragraphs that add no information."""
        violations: list[GuardViolation] = []
        filler_phrases = [
            r"(?i)in\s+(?:this\s+)?(Union[?:section|chapter, document]),\s+we\s+will\s+(Union[?:discuss|cover|explore, look\s+at])",
            r"(?i)it\s+is\s+important\s+to\s+note\s+that",
            r"(?i)as\s+(Union[?:mentioned|noted, stated])\s+(Union[?:above|earlier, before])",
            r"(?i)please\s+(Union[?:note|be\s+aware, keep\s+in\s+mind])",
        ]
        for pat in filler_phrases:
            for match in re.finditer(pat, source):
                line_num = source[: match.start()].count("\n") + 1
                violations.append(
                    GuardViolation(
                        rule_id="D-07",
                        rule_name="Filler phrase detected",
                        severity=GuardSeverity.WORTH_NOTING,
                        description="Documentation contains filler phrases that add no information. "
                        "Professional docs should be concise and substantive.",
                        location=f"line {line_num}",
                        suggestion="Remove the filler phrase and get directly to the point.",
                        evidence=match.group(0)[:80],
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # D-09: Examples cover the failure path too
    # ------------------------------------------------------------------
    def _check_failure_paths(self, source: str) -> list[GuardViolation]:
        """Check that code examples include error handling."""
        violations: list[GuardViolation] = []
        # Find code blocks
        code_blocks = re.findall(r"```(?:python)?\n(.*?)```", source, re.DOTALL)
        for i, block in enumerate(code_blocks):
            has_try = "try:" in block or "except" in block
            has_call = any(
                kw in block for kw in ["requests.", "fetch(", "open(", "connect(", "execute("]
            )
            if has_call and not has_try:
                violations.append(
                    GuardViolation(
                        rule_id="D-09",
                        rule_name="Code example missing failure path",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"Code example {i + 1} makes an I/O call but doesn't show error handling. "
                        "Examples should cover the failure path too.",
                        location=f"code block {i + 1}",
                        suggestion="Add a try/except block showing how to handle the expected failure.",
                        evidence="I/O call without error handling",
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # D-08: Don't paraphrase upstream docs — link
    # ------------------------------------------------------------------
    def _check_paraphrased_docs(self, source: str) -> list[GuardViolation]:
        """Heuristic: patterns that suggest paraphrasing official docs."""
        violations: list[GuardViolation] = []
        paraphrase_patterns = [
            r"(?i)according\s+to\s+the\s+(?:official\s+)?(Union[?:documentation|docs|spec|standard, RFC])",
            r"(?i)the\s+(?:official\s+)?(Union[?:documentation|docs, spec])\s+(Union[?:says|states, recommends])",
        ]
        for pat in paraphrase_patterns:
            for match in re.finditer(pat, source):
                line_num = source[: match.start()].count("\n") + 1
                # Check if there's a link nearby
                surrounding = source[max(0, match.start() - 200) : match.end() + 200]
                has_link = bool(re.search(r"https?://", surrounding))
                if not has_link:
                    violations.append(
                        GuardViolation(
                            rule_id="D-08",
                            rule_name="Paraphrased docs without link",
                            severity=GuardSeverity.SHOULD_FIX,
                            description="Documentation paraphrases an upstream source without providing "
                            "a direct link. Linking is better than paraphrasing.",
                            location=f"line {line_num}",
                            suggestion="Replace the paraphrase with a direct link to the upstream "
                            "documentation section.",
                            evidence=match.group(0)[:80],
                        ),
                    )
        return violations

    # ------------------------------------------------------------------
    # D-02: Every code sample must work
    # ------------------------------------------------------------------
    def _check_code_samples(self, source: str) -> list[GuardViolation]:
        """Heuristic: check Python code blocks for syntax errors."""
        violations: list[GuardViolation] = []
        import ast as _ast

        code_blocks = re.findall(r"```(?:python)?\n(.*?)```", source, re.DOTALL)
        for i, block in enumerate(code_blocks):
            if not block.strip():
                continue
            try:
                _ast.parse(block)
            except SyntaxError as e:
                violations.append(
                    GuardViolation(
                        rule_id="D-02",
                        rule_name="Code sample has syntax error",
                        severity=GuardSeverity.MUST_FIX,
                        description=f"Code example {i + 1} has a syntax error: {e.msg} at line {e.lineno}. "
                        "Every code sample in documentation must be valid.",
                        location=f"code block {i + 1}",
                        suggestion="Fix the syntax error in the code sample. Consider running "
                        "the sample through a linter before committing.",
                        evidence=f"SyntaxError: {e.msg}",
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # D-03: Document actual behavior, not intended
    # ------------------------------------------------------------------
    def _check_actual_vs_intended(self, source: str) -> list[GuardViolation]:
        """Heuristic: phrases that describe intended rather than actual behavior."""
        violations: list[GuardViolation] = []
        intended_patterns = [
            (
                r"(?i)(Union[?:should|will|is\s+going\s+to, supposed\s+to])\s+(Union[?:return|compute|calculate|generate, produce])",
                "documents intended behavior, not actual",
            ),
            (
                r"(?i)this\s+(Union[?:function|method|class, module])\s+(Union[?:should, will])\s+",
                "describes future intent, not current behavior",
            ),
        ]
        for pat, desc in intended_patterns:
            for match in re.finditer(pat, source):
                line_num = source[: match.start()].count("\n") + 1
                violations.append(
                    GuardViolation(
                        rule_id="D-03",
                        rule_name="Documents intended behavior, not actual",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"Documentation {desc}: '{match.group(0)[:60]}'. "
                        "Docs should describe what the code actually does now, "
                        "not what it should or will do.",
                        location=f"line {line_num}",
                        suggestion="Rewrite to describe current behavior. If the code doesn't "
                        "match the docs, fix the code or update the docs to match.",
                        evidence=match.group(0)[:80],
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # D-06: A code change owes a docs change
    # ------------------------------------------------------------------
    def _check_docs_owed(self, source: str, context: dict[str, Any] | None) -> list[GuardViolation]:
        """Heuristic: if context provides changed_symbols, check that docs
        mention those symbols."""
        violations: list[GuardViolation] = []
        if not context or "changed_symbols" not in context:
            return violations

        changed = context["changed_symbols"]
        if not isinstance(changed, (list, set)):
            return violations

        for symbol in changed:
            if symbol not in source:
                violations.append(
                    GuardViolation(
                        rule_id="D-06",
                        rule_name="Code change not reflected in docs",
                        severity=GuardSeverity.SHOULD_FIX,
                        description=f"Symbol '{symbol}' was changed in code but is not mentioned "
                        "in this documentation. A code change owes a docs change.",
                        location="entire document",
                        suggestion=f"Add documentation for the changed symbol '{symbol}'. If the "
                        f"change is breaking, document the migration path.",
                        evidence=f"'{symbol}' not in docs",
                    ),
                )
        return violations

    # ------------------------------------------------------------------
    # D-10: Navigation tells the truth
    # ------------------------------------------------------------------
    def _check_navigation_truth(self, source: str) -> list[GuardViolation]:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """Heuristic: check markdown links for common broken patterns."""
        violations: list[GuardViolation] = []
        # Check for relative links to files that likely don't exist
        # (local-only check — can't verify HTTP links without network)
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        for match in re.finditer(link_pattern, source):
            link_text = match.group(1)
            link_target = match.group(2)
            line_num = source[: match.start()].count("\n") + 1

            # Check for common broken-link patterns
            if link_target.startswith("#"):
                # Anchor link — check if a matching heading exists
                anchor = link_target[1:].lower()
                # Look for markdown headings that match this anchor.
                # NOSONAR — python:S8786: .* is bounded by single-line markdown
                heading_pattern = r"^#+\s+.*$"
                headings = [
                    re.sub(r"^#+\s+", "", m.group().lower()).strip()
                    for m in re.finditer(heading_pattern, source, re.MULTILINE)
                ]
                # Normalize headings to anchor format (lowercase, hyphens for spaces, strip punctuation)
                normalized_headings = set()
                for h in headings:
                    nh = re.sub(r"[^\w\s-]", "", h).replace(" ", "-").strip()
                    normalized_headings.add(nh)

                if anchor and anchor not in normalized_headings:
                    violations.append(
                        GuardViolation(
                            rule_id="D-10",
                            rule_name="Broken anchor link",
                            severity=GuardSeverity.SHOULD_FIX,
                            description=f"Anchor link '#{link_target[1:]}' does not match any heading "
                            "in the document. Navigation must tell the truth — broken links "
                            "erode trust.",
                            location=f"line {line_num}",
                            suggestion="Verify the anchor matches a heading. Generate anchors from "
                            "headings using the markdown convention (lowercase, hyphens "
                            "for spaces, no punctuation).",
                            evidence=f"[{link_text}](#{link_target[1:]})",
                        ),
                    )
            elif link_target.endswith(".md", ".py"):  # NOSONAR — python:S8513: false positive — already tuple form
                # Relative file link — check if it looks like a placeholder
                if "TODO" in link_target or "PLACEHOLDER" in link_target:
                    violations.append(
                        GuardViolation(
                            rule_id="D-10",
                            rule_name="Placeholder link in documentation",
                            severity=GuardSeverity.MUST_FIX,
                            description=f"Link target '{link_target}' contains a placeholder. "
                            "Navigation must point to real resources.",
                            location=f"line {line_num}",
                            suggestion="Replace the placeholder with a real file path or URL.",
                            evidence=f"[{link_text}]({link_target})",
                        ),
                    )
        return violations
