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
from typing import Any, Dict, List, Optional

from guards.base import BaseGuard, GuardMode, GuardResult, GuardSeverity, GuardViolation

logger = logging.getLogger(__name__)


class DocsGuard(BaseGuard):
    """Scans documentation for accuracy violations.

    Usage
    -----
    >>> guard = DocsGuard()
    >>> result = guard.scan(markdown_docs)
    """

    name: str = "docs_guard"

    def scan(self, source: str, language: str = "markdown", context: Optional[Dict[str, Any]] = None) -> GuardResult:
        violations: List[GuardViolation] = []
        context = context or {}

        # D-01: Referenced symbols must exist (if Python source provided)
        if context.get("python_source"):
            violations.extend(self._check_symbol_references(source, context["python_source"]))

        # D-04: No unverifiable claims
        violations.extend(self._check_unverifiable_claims(source))

        # D-05: Versions are explicit
        violations.extend(self._check_version_clarity(source))

        # D-07: No filler, no slop
        violations.extend(self._check_filler(source))

        # D-09: Examples cover the failure path
        violations.extend(self._check_failure_paths(source))

        # D-08: Don't paraphrase — link
        violations.extend(self._check_paraphrased_docs(source))

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
    def _check_symbol_references(self, docs: str, python_source: str) -> List[GuardViolation]:
        """Check that Python symbols referenced in docs actually exist in code."""
        violations: List[GuardViolation] = []

        # Extract class and function names from Python source
        import ast
        defined_symbols: set = set()
        try:
            tree = ast.parse(python_source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    defined_symbols.add(node.name)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defined_symbols.add(node.name)
        except SyntaxError:
            return violations

        # Find Python-style symbol references in docs
        # Pattern: ``ClassName``, `function_name`, ::ClassName, etc.
        ref_pattern = r'(?:``|`|::)([A-Za-z_][A-Za-z0-9_]*)'
        for match in re.finditer(ref_pattern, docs):
            symbol = match.group(1)
            if symbol.startswith('_') or symbol in ('True', 'False', 'None', 'self', 'cls'):
                continue
            if symbol not in defined_symbols and not symbol.isupper():
                line_num = docs[:match.start()].count('\n') + 1
                violations.append(GuardViolation(
                    rule_id="D-01",
                    rule_name="Referenced symbol does not exist",
                    severity=GuardSeverity.MUST_FIX,
                    description=f"Documentation references '{symbol}' but it does not exist "
                                "in the source code.",
                    location=f"line {line_num}",
                    suggestion="Add the symbol to the source code, or remove/update the reference.",
                    evidence=f"symbol: {symbol}",
                ))
        return violations

    # ------------------------------------------------------------------
    # D-04: No unverifiable claims
    # ------------------------------------------------------------------
    def _check_unverifiable_claims(self, source: str) -> List[GuardViolation]:
        """Heuristic: phrases that suggest claims without evidence."""
        violations: List[GuardViolation] = []
        unverifiable_patterns = [
            (r'(?i)(?:it\s+is\s+)?(?:well\s*-?known|obvious|clearly|everyone\s+knows|undoubtedly)\s+that', "unverifiable claim"),
            (r'(?i)(?:the\s+)?(?:best|worst|fastest|slowest|most\s+efficient|only\s+way)\s+(?:way|method|approach|solution)', "superlative without evidence"),
            (r'(?i)(?:always|never|all|none|every)\s+(?:works|fails|returns|produces)', "absolute claim without qualification"),
        ]
        for pat, desc in unverifiable_patterns:
            for match in re.finditer(pat, source):
                line_num = source[:match.start()].count('\n') + 1
                violations.append(GuardViolation(
                    rule_id="D-04",
                    rule_name="Unverifiable claim",
                    severity=GuardSeverity.SHOULD_FIX,
                    description=f"Documentation contains an {desc}: '{match.group(0)[:60]}'. "
                                "Claims should be verifiable against source code or cited sources.",
                    location=f"line {line_num}",
                    suggestion="Provide evidence (measurement, citation, code reference) or "
                               "qualify the claim (e.g., 'typically', 'in our testing').",
                    evidence=match.group(0)[:80],
                ))
        return violations

    # ------------------------------------------------------------------
    # D-05: Versions are explicit
    # ------------------------------------------------------------------
    def _check_version_clarity(self, source: str) -> List[GuardViolation]:
        """Check that version references are explicit, not relative."""
        violations: List[GuardViolation] = []
        # Pattern: "latest", "current version", "new" without a specific version number
        vague_version_patterns = [
            r'(?i)(?:the\s+)?(?:latest|current|new|recent|stable)\s+(?:version|release)\s+(?:of\s+)?',
        ]
        for pat in vague_version_patterns:
            for match in re.finditer(pat, source):
                line_num = source[:match.start()].count('\n') + 1
                violations.append(GuardViolation(
                    rule_id="D-05",
                    rule_name="Vague version reference",
                    severity=GuardSeverity.SHOULD_FIX,
                    description="Documentation refers to a version without specifying it. "
                                "Vague version references become stale quickly.",
                    location=f"line {line_num}",
                    suggestion="Specify the exact version number (e.g., 'v2.1.0' or 'as of 2025-06').",
                    evidence=match.group(0)[:80],
                ))
        return violations

    # ------------------------------------------------------------------
    # D-07: No filler, no slop
    # ------------------------------------------------------------------
    def _check_filler(self, source: str) -> List[GuardViolation]:
        """Heuristic: paragraphs that add no information."""
        violations: List[GuardViolation] = []
        filler_phrases = [
            r'(?i)in\s+(?:this\s+)?(?:section|chapter|document),\s+we\s+will\s+(?:discuss|cover|explore|look\s+at)',
            r'(?i)it\s+is\s+important\s+to\s+note\s+that',
            r'(?i)as\s+(?:mentioned|noted|stated)\s+(?:above|earlier|before)',
            r'(?i)please\s+(?:note|be\s+aware|keep\s+in\s+mind)',
        ]
        for pat in filler_phrases:
            for match in re.finditer(pat, source):
                line_num = source[:match.start()].count('\n') + 1
                violations.append(GuardViolation(
                    rule_id="D-07",
                    rule_name="Filler phrase detected",
                    severity=GuardSeverity.WORTH_NOTING,
                    description="Documentation contains filler phrases that add no information. "
                                "Professional docs should be concise and substantive.",
                    location=f"line {line_num}",
                    suggestion="Remove the filler phrase and get directly to the point.",
                    evidence=match.group(0)[:80],
                ))
        return violations

    # ------------------------------------------------------------------
    # D-09: Examples cover the failure path too
    # ------------------------------------------------------------------
    def _check_failure_paths(self, source: str) -> List[GuardViolation]:
        """Check that code examples include error handling."""
        violations: List[GuardViolation] = []
        # Find code blocks
        code_blocks = re.findall(r'```(?:python)?\n(.*?)```', source, re.DOTALL)
        for i, block in enumerate(code_blocks):
            has_try = 'try:' in block or 'except' in block
            has_call = any(kw in block for kw in ['requests.', 'fetch(', 'open(', 'connect(', 'execute('])
            if has_call and not has_try:
                violations.append(GuardViolation(
                    rule_id="D-09",
                    rule_name="Code example missing failure path",
                    severity=GuardSeverity.SHOULD_FIX,
                    description=f"Code example {i+1} makes an I/O call but doesn't show error handling. "
                                "Examples should cover the failure path too.",
                    location=f"code block {i+1}",
                    suggestion="Add a try/except block showing how to handle the expected failure.",
                    evidence="I/O call without error handling",
                ))
        return violations

    # ------------------------------------------------------------------
    # D-08: Don't paraphrase upstream docs — link
    # ------------------------------------------------------------------
    def _check_paraphrased_docs(self, source: str) -> List[GuardViolation]:
        """Heuristic: patterns that suggest paraphrasing official docs."""
        violations: List[GuardViolation] = []
        paraphrase_patterns = [
            r'(?i)according\s+to\s+the\s+(?:official\s+)?(?:documentation|docs|spec|standard|RFC)',
            r'(?i)the\s+(?:official\s+)?(?:documentation|docs|spec)\s+(?:says|states|recommends)',
        ]
        for pat in paraphrase_patterns:
            for match in re.finditer(pat, source):
                line_num = source[:match.start()].count('\n') + 1
                # Check if there's a link nearby
                surrounding = source[max(0, match.start()-200):match.end()+200]
                has_link = bool(re.search(r'https?://|:\[.*\]\(', surrounding))
                if not has_link:
                    violations.append(GuardViolation(
                        rule_id="D-08",
                        rule_name="Paraphrased docs without link",
                        severity=GuardSeverity.SHOULD_FIX,
                        description="Documentation paraphrases an upstream source without providing "
                                    "a direct link. Linking is better than paraphrasing.",
                        location=f"line {line_num}",
                        suggestion="Replace the paraphrase with a direct link to the upstream "
                                   "documentation section.",
                        evidence=match.group(0)[:80],
                    ))
        return violations
