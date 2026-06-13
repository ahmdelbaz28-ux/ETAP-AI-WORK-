"""
api/coverage_report.py — Test coverage analysis tool for the ETAP AI Platform.

Scans all Python source files, identifies functions/methods that have
corresponding tests, identifies those without tests, generates coverage
percentages, suggests specific test cases for untested functions, and
outputs a structured JSON report.

Known low-coverage modules (checked explicitly):
  - engineering_service.py: predict/load, predict/fault, predict/anomaly,
    rag/query, scada/live, digital-twin/status endpoints
  - coordination/coordination.py: suggest_tms_adjustment edge cases
  - engine/engine.py: motor_starting and harmonic_analysis dispatch (MISSING)
  - digital_twin/ module
  - gis_integration/ module
  - etap_integration/ module

Usage (CLI)::

    python -m api.coverage_report --project-root /path/to/repo

Usage (programmatic)::

    from api.coverage_report import CoverageAnalyzer
    report = await CoverageAnalyzer().run()
"""

from __future__ import annotations

import ast
import asyncio
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class CoverageLevel(str, Enum):
    """Coverage quality rating."""

    EXCELLENT = "excellent"   # >= 90%
    GOOD = "good"             # >= 70%
    FAIR = "fair"             # >= 50%
    POOR = "poor"             # >= 25%
    CRITICAL = "critical"     # < 25%
    NONE = "none"             # 0%


@dataclass
class FunctionInfo:
    """Metadata about a discovered Python function or method."""

    name: str
    qualname: str  # e.g. "PowerSystemEngine.run_load_flow"
    module: str    # e.g. "engine.engine"
    file_path: str
    line_number: int
    is_async: bool = False
    is_method: bool = False
    class_name: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    has_test: bool = False
    test_names: List[str] = field(default_factory=list)
    suggested_tests: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return asdict(self)


@dataclass
class ModuleCoverage:
    """Coverage summary for a single Python module."""

    module: str
    file_path: str
    total_functions: int = 0
    tested_functions: int = 0
    untested_functions: int = 0
    coverage_percent: float = 0.0
    level: CoverageLevel = CoverageLevel.NONE
    functions: List[FunctionInfo] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        result = {
            "module": self.module,
            "file_path": self.file_path,
            "total_functions": self.total_functions,
            "tested_functions": self.tested_functions,
            "untested_functions": self.untested_functions,
            "coverage_percent": round(self.coverage_percent, 1),
            "level": self.level.value,
            "functions": [f.to_dict() for f in self.functions],
        }
        return result


@dataclass
class CoverageReport:
    """Top-level coverage report for the entire project."""

    project_root: str
    total_modules: int = 0
    total_functions: int = 0
    tested_functions: int = 0
    untested_functions: int = 0
    overall_coverage_percent: float = 0.0
    overall_level: CoverageLevel = CoverageLevel.NONE
    modules: List[ModuleCoverage] = field(default_factory=list)
    critical_gaps: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "project_root": self.project_root,
            "total_modules": self.total_modules,
            "total_functions": self.total_functions,
            "tested_functions": self.tested_functions,
            "untested_functions": self.untested_functions,
            "overall_coverage_percent": round(self.overall_coverage_percent, 1),
            "overall_level": self.overall_level.value,
            "modules": [m.to_dict() for m in self.modules],
            "critical_gaps": self.critical_gaps,
            "suggestions": self.suggestions,
        }


# ---------------------------------------------------------------------------
# Known low-coverage areas — explicit watch list
# ---------------------------------------------------------------------------

_KNOWN_LOW_COVERAGE: Dict[str, List[str]] = {
    "engineering_service": [
        "predict_load",
        "predict_fault",
        "predict_anomaly",
        "rag_query",
        "get_scada_live_data",
        "get_digital_twin_status",
    ],
    "coordination.coordination": [
        "suggest_tms_adjustment",
    ],
    "engine.engine": [
        "motor_starting",
        "harmonic_analysis",
        "optimal_power_flow",
    ],
    "digital_twin.digital_twin_core": [
        "ChangePropagationEngine",
        "SynchronizationEngine",
        "TimeSteppedSimulator",
        "LivePowerSystemEngine",
    ],
    "digital_twin.state_store": [
        "StateStore",
    ],
    "digital_twin.validation_gateway": [
        "ValidationGateway",
    ],
    "digital_twin.event_bus": [
        "EventBus",
    ],
    "gis_integration.transformer": [
        "GIS_TO_ADMS_Transformer",
    ],
    "gis_integration.base": [
        "GISProviderInterface",
    ],
    "etap_integration.etap_provider": [
        "IEtapProvider",
        "LocalEtapProvider",
        "RemoteEtapProvider",
    ],
    "etap_integration.etap_com": [
        "ETAPAutomation",
    ],
    "etap_integration.etap_error_recovery": [
        "ETAPErrorRecovery",
    ],
}


# ---------------------------------------------------------------------------
# Test-suggestion templates
# ---------------------------------------------------------------------------

_SUGGESTION_TEMPLATES: Dict[str, List[str]] = {
    "endpoint": [
        "test_{name}_success — happy-path request returns 200 with valid payload",
        "test_{name}_missing_api_key — request without X-API-Key returns 401",
        "test_{name}_invalid_input — malformed request body returns 422 or 400",
        "test_{name}_rate_limit — exceed rate limit and expect 429",
    ],
    "engine_method": [
        "test_{name}_nominal — run with valid input and verify result shape",
        "test_{name}_invalid_input — pass invalid parameters and expect ValueError",
        "test_{name}_edge_case_empty — handle empty/zero-valued inputs gracefully",
        "test_{name}_timeout — verify behaviour under heavy computation load",
    ],
    "integration": [
        "test_{name}_connection — verify connection to external system",
        "test_{name}_unavailable — gracefully handle provider unavailability",
        "test_{name}_error_recovery — test error recovery path",
        "test_{name}_compatibility — verify version compatibility check",
    ],
    "general": [
        "test_{name}_basic — verify basic functionality",
        "test_{name}_invalid_input — verify input validation",
        "test_{name}_edge_case — test boundary conditions",
        "test_{name}_error_handling — verify error handling",
    ],
}


# ---------------------------------------------------------------------------
# AST-based function extractor
# ---------------------------------------------------------------------------

class _FunctionExtractor(ast.NodeVisitor):
    """Walk the AST and collect all function/method definitions."""

    def __init__(self, module_name: str, file_path: str) -> None:
        self.module_name = module_name
        self.file_path = file_path
        self.functions: List[FunctionInfo] = []
        self._class_stack: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        """Visit a class definition and track it for qualified names."""
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        """Visit a function definition."""
        self._add_function(node, is_async=False)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        """Visit an async function definition."""
        self._add_function(node, is_async=True)
        self.generic_visit(node)

    def _add_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, is_async: bool) -> None:
        """Record a function/method from the AST."""
        # Skip dunder methods (they are typically infrastructure)
        if node.name.startswith("__") and node.name.endswith("__"):
            return

        # Skip private test helpers
        if node.name.startswith("_") and not node.name.startswith("__"):
            # Still include them but mark appropriately
            pass

        class_name: Optional[str] = None
        if self._class_stack:
            class_name = self._class_stack[-1]

        qualname = f"{'.'.join(self._class_stack)}.{node.name}" if self._class_stack else node.name

        decorators: List[str] = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(ast.dump(dec))
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    decorators.append(ast.dump(dec.func))

        func_info = FunctionInfo(
            name=node.name,
            qualname=qualname,
            module=self.module_name,
            file_path=self.file_path,
            line_number=node.lineno,
            is_async=is_async,
            is_method=bool(self._class_stack),
            class_name=class_name,
            decorators=decorators,
        )
        self.functions.append(func_info)


# ---------------------------------------------------------------------------
# Test-name matching strategies
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    """Normalize a function name for fuzzy matching.

    Converts ``run_load_flow`` to ``runloadflow`` and
    ``runLoadFlow`` to ``runloadflow`` for comparison.
    """
    return re.sub(r"[_\-\s]", "", name).lower()


def _generate_test_patterns(func: FunctionInfo) -> List[str]:
    """Generate possible test-name patterns that would test *func*.

    Common conventions:
      - ``test_<function_name>``
      - ``test_<class_name>_<method_name>``
      - ``test_<module>_<function_name>``
      - ``Test<class_name>.test_<method_name>``
    """
    patterns: List[str] = []
    name = func.name

    # Direct function name
    patterns.append(f"test_{name}")
    patterns.append(_normalize_name(f"test_{name}"))

    # With class name
    if func.class_name:
        patterns.append(f"test_{func.class_name}_{name}")
        patterns.append(f"test_{func.class_name.lower()}_{name}")
        patterns.append(_normalize_name(f"test_{func.class_name}_{name}"))

    # With module prefix
    module_parts = func.module.split(".")
    if module_parts:
        mod_prefix = module_parts[-1]
        patterns.append(f"test_{mod_prefix}_{name}")
        patterns.append(_normalize_name(f"test_{mod_prefix}_{name}"))

    return patterns


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

class CoverageAnalyzer:
    """Analyze test coverage across the entire project.

    Scans all Python source files, identifies functions/methods, and
    cross-references them against test files to determine coverage.
    Generates a structured JSON report with actionable suggestions.

    Example::

        analyzer = CoverageAnalyzer(project_root="/path/to/repo")
        report = await analyzer.run()
        print(json.dumps(report.to_dict(), indent=2))
    """

    def __init__(self, project_root: Optional[str] = None) -> None:
        """Initialize the analyzer.

        Args:
            project_root: Path to the project root directory.
                Defaults to the directory containing this file's parent.
        """
        if project_root is None:
            project_root = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        self.project_root = os.path.abspath(project_root)
        self._source_files: List[str] = []
        self._test_files: List[str] = []
        self._test_names: Set[str] = set()
        self._test_normalized: Set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> CoverageReport:
        """Execute the full coverage analysis pipeline.

        Returns:
            A :class:`CoverageReport` with per-module and overall results.
        """
        # Step 1: Discover files
        await self._discover_files()

        # Step 2: Parse test files and build test-name index
        await self._index_test_names()

        # Step 3: Parse source files and extract functions
        all_functions = await self._extract_all_functions()

        # Step 4: Match functions against test index
        self._match_functions_to_tests(all_functions)

        # Step 5: Build per-module coverage
        module_coverages = self._build_module_coverages(all_functions)

        # Step 6: Generate suggestions for untested functions
        self._generate_suggestions(module_coverages)

        # Step 7: Assemble final report
        report = self._assemble_report(module_coverages)

        return report

    # ------------------------------------------------------------------
    # Step 1: File discovery
    # ------------------------------------------------------------------

    async def _discover_files(self) -> None:
        """Walk the project tree and classify files as source or test."""
        source_files: List[str] = []
        test_files: List[str] = []

        # Directories to skip
        skip_dirs = {
            ".git", "__pycache__", "node_modules", ".venv", "venv",
            ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
            "egg-info", ".eggs", ".ruff_cache", "acp_runtime",
        }

        for dirpath, dirnames, filenames in os.walk(self.project_root):
            # Prune skipped directories in-place
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]

            rel_dir = os.path.relpath(dirpath, self.project_root)

            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                full_path = os.path.join(dirpath, fname)

                # Classify as test or source
                is_test = (
                    fname.startswith("test_")
                    or fname.endswith("_test.py")
                    or "tests" in rel_dir.split(os.sep)
                    or "test" in rel_dir.split(os.sep)
                )

                if is_test:
                    test_files.append(full_path)
                else:
                    source_files.append(full_path)

        self._source_files = source_files
        self._test_files = test_files

    # ------------------------------------------------------------------
    # Step 2: Test name indexing
    # ------------------------------------------------------------------

    async def _index_test_names(self) -> None:
        """Parse all test files and collect test function/method names."""
        test_names: Set[str] = set()
        test_normalized: Set[str] = set()

        for test_file in self._test_files:
            try:
                with open(test_file, "r", encoding="utf-8", errors="replace") as fh:
                    source = fh.read()
                tree = ast.parse(source, filename=test_file)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name.startswith("test_") or node.name.endswith("_test"):
                            test_names.add(node.name)
                            test_normalized.add(_normalize_name(node.name))
            except SyntaxError:
                # Skip files that can't be parsed
                pass
            except Exception:
                pass

        self._test_names = test_names
        self._test_normalized = test_normalized

    # ------------------------------------------------------------------
    # Step 3: Function extraction
    # ------------------------------------------------------------------

    async def _extract_all_functions(self) -> List[FunctionInfo]:
        """Parse all source files and extract function/method definitions."""
        all_functions: List[FunctionInfo] = []

        for src_file in self._source_files:
            rel_path = os.path.relpath(src_file, self.project_root)
            module_name = rel_path.replace(os.sep, ".").removesuffix(".py")

            # Skip __init__.py files (usually empty or re-exports)
            if rel_path.endswith("__init__.py"):
                continue

            try:
                with open(src_file, "r", encoding="utf-8", errors="replace") as fh:
                    source = fh.read()
                tree = ast.parse(source, filename=src_file)

                extractor = _FunctionExtractor(module_name, src_file)
                extractor.visit(tree)
                all_functions.extend(extractor.functions)
            except SyntaxError:
                pass
            except Exception:
                pass

        return all_functions

    # ------------------------------------------------------------------
    # Step 4: Test matching
    # ------------------------------------------------------------------

    def _match_functions_to_tests(self, functions: List[FunctionInfo]) -> None:
        """Cross-reference each function against the test-name index."""
        for func in functions:
            patterns = _generate_test_patterns(func)
            matched_tests: List[str] = []

            for pattern in patterns:
                norm = _normalize_name(pattern)
                if pattern in self._test_names or norm in self._test_normalized:
                    # Find the actual test name(s) that match
                    for tn in self._test_names:
                        if _normalize_name(tn) == norm or tn == pattern:
                            matched_tests.append(tn)

            if matched_tests:
                func.has_test = True
                func.test_names = sorted(set(matched_tests))
            else:
                func.has_test = False
                func.test_names = []

    # ------------------------------------------------------------------
    # Step 5: Module coverage
    # ------------------------------------------------------------------

    def _build_module_coverages(self, functions: List[FunctionInfo]) -> List[ModuleCoverage]:
        """Group functions by module and compute per-module coverage."""
        by_module: Dict[str, List[FunctionInfo]] = {}
        for func in functions:
            by_module.setdefault(func.module, []).append(func)

        module_coverages: List[ModuleCoverage] = []
        for module_name, funcs in sorted(by_module.items()):
            total = len(funcs)
            tested = sum(1 for f in funcs if f.has_test)
            untested = total - tested
            percent = (tested / total * 100.0) if total > 0 else 0.0
            level = self._coverage_level(percent)

            # Get the file path from the first function
            file_path = funcs[0].file_path if funcs else ""

            mc = ModuleCoverage(
                module=module_name,
                file_path=file_path,
                total_functions=total,
                tested_functions=tested,
                untested_functions=untested,
                coverage_percent=percent,
                level=level,
                functions=funcs,
            )
            module_coverages.append(mc)

        return module_coverages

    @staticmethod
    def _coverage_level(percent: float) -> CoverageLevel:
        """Map a coverage percentage to a :class:`CoverageLevel`."""
        if percent >= 90:
            return CoverageLevel.EXCELLENT
        if percent >= 70:
            return CoverageLevel.GOOD
        if percent >= 50:
            return CoverageLevel.FAIR
        if percent >= 25:
            return CoverageLevel.POOR
        if percent > 0:
            return CoverageLevel.CRITICAL
        return CoverageLevel.NONE

    # ------------------------------------------------------------------
    # Step 6: Suggestion generation
    # ------------------------------------------------------------------

    def _generate_suggestions(self, modules: List[ModuleCoverage]) -> None:
        """Generate test-case suggestions for untested functions."""
        for mc in modules:
            for func in mc.functions:
                if not func.has_test:
                    func.suggested_tests = self._suggest_tests_for(func)

    def _suggest_tests_for(self, func: FunctionInfo) -> List[str]:
        """Generate specific test-case suggestions for an untested function."""
        suggestions: List[str] = []

        # Determine the suggestion category
        category = self._categorize_function(func)
        templates = _SUGGESTION_TEMPLATES.get(category, _SUGGESTION_TEMPLATES["general"])

        for template in templates:
            suggestion = template.format(name=func.name)
            suggestions.append(suggestion)

        # Add known-low-coverage warnings
        module_base = func.module.split(".")[-1]
        for known_module, known_funcs in _KNOWN_LOW_COVERAGE.items():
            known_base = known_module.split(".")[-1]
            if known_base == module_base or func.module == known_module:
                if func.name in known_funcs or (func.class_name and func.class_name in known_funcs):
                    suggestions.append(
                        f"⚠ KNOWN GAP: {func.qualname} is on the explicit low-coverage watch list"
                    )

        return suggestions

    def _categorize_function(self, func: FunctionInfo) -> str:
        """Determine which suggestion template category to use."""
        # Endpoint functions (FastAPI route handlers)
        if any(d in func.decorators for d in ("app.get", "app.post", "app.put", "app.delete")):
            return "endpoint"

        # If the function is in engineering_service and its name suggests an endpoint
        if "engineering_service" in func.module:
            if any(kw in func.name for kw in ("predict", "query", "get_", "submit_", "run_", "validate_")):
                return "endpoint"

        # Integration module functions
        if any(kw in func.module for kw in ("etap_integration", "gis_integration", "scada_model")):
            return "integration"

        # Engine methods
        if "engine" in func.module and func.is_method:
            return "engine_method"

        return "general"

    # ------------------------------------------------------------------
    # Step 7: Report assembly
    # ------------------------------------------------------------------

    def _assemble_report(self, modules: List[ModuleCoverage]) -> CoverageReport:
        """Assemble the final coverage report."""
        total_functions = sum(m.total_functions for m in modules)
        tested_functions = sum(m.tested_functions for m in modules)
        untested_functions = total_functions - tested_functions
        overall_percent = (tested_functions / total_functions * 100.0) if total_functions > 0 else 0.0

        # Identify critical gaps (modules on the watch list with low coverage)
        critical_gaps = self._identify_critical_gaps(modules)

        # Top-level suggestions
        suggestions = self._top_suggestions(modules)

        return CoverageReport(
            project_root=self.project_root,
            total_modules=len(modules),
            total_functions=total_functions,
            tested_functions=tested_functions,
            untested_functions=untested_functions,
            overall_coverage_percent=overall_percent,
            overall_level=self._coverage_level(overall_percent),
            modules=modules,
            critical_gaps=critical_gaps,
            suggestions=suggestions,
        )

    def _identify_critical_gaps(self, modules: List[ModuleCoverage]) -> List[Dict[str, Any]]:
        """Identify modules/functions on the known low-coverage watch list."""
        gaps: List[Dict[str, Any]] = []

        for mc in modules:
            for known_module, known_funcs in _KNOWN_LOW_COVERAGE.items():
                # Match by module base name or full module path
                if mc.module != known_module and mc.module.split(".")[-1] != known_module.split(".")[-1]:
                    continue

                for func_name in known_funcs:
                    # Find the function in the module
                    matching = [f for f in mc.functions if f.name == func_name or f.class_name == func_name]
                    if not matching:
                        # Function doesn't exist in the code yet (e.g., motor_starting dispatch)
                        gaps.append({
                            "module": known_module,
                            "function_or_class": func_name,
                            "issue": "NOT IMPLEMENTED — function/class not found in source",
                            "severity": "critical",
                            "recommendation": f"Implement {func_name} in {known_module} and add corresponding tests",
                        })
                    else:
                        for func in matching:
                            if not func.has_test:
                                gaps.append({
                                    "module": known_module,
                                    "function": func.qualname,
                                    "issue": "NO TEST COVERAGE",
                                    "severity": "high",
                                    "recommendation": f"Add tests for {func.qualname} — it is on the explicit low-coverage watch list",
                                })

        return gaps

    def _top_suggestions(self, modules: List[ModuleCoverage]) -> List[Dict[str, Any]]:
        """Generate top-priority suggestions for improving coverage."""
        suggestions: List[Dict[str, Any]] = []

        # Sort modules by coverage (lowest first)
        sorted_modules = sorted(modules, key=lambda m: m.coverage_percent)

        # Suggest improvements for the 10 worst-covered modules
        for mc in sorted_modules[:10]:
            if mc.coverage_percent >= 100:
                continue

            untested = [f for f in mc.functions if not f.has_test]
            if not untested:
                continue

            suggestions.append({
                "priority": "high" if mc.coverage_percent < 25 else "medium",
                "module": mc.module,
                "current_coverage": round(mc.coverage_percent, 1),
                "untested_count": len(untested),
                "top_untested": [f.qualname for f in untested[:5]],
                "suggested_actions": [
                    f"Create test file: tests/test_{mc.module.split('.')[-1]}.py"
                    if mc.coverage_percent == 0 else
                    f"Expand existing tests for {mc.module}",
                ],
            })

        return suggestions


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

async def _main() -> None:
    """CLI entrypoint for running the coverage analyzer."""
    import argparse

    parser = argparse.ArgumentParser(
        description="ETAP AI Platform — Test Coverage Analyzer",
    )
    parser.add_argument(
        "--project-root",
        type=str,
        default=None,
        help="Path to the project root (defaults to this repo)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="-",
        help="Output file path ('-' for stdout)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Output only the JSON report (no summary text)",
    )
    args = parser.parse_args()

    analyzer = CoverageAnalyzer(project_root=args.project_root)
    report = await analyzer.run()

    if args.output == "-":
        out = sys.stdout
    else:
        out = open(args.output, "w", encoding="utf-8")

    try:
        report_dict = report.to_dict()

        if not args.json_only:
            # Print human-readable summary
            print("=" * 72, file=out)
            print("ETAP AI Platform — Test Coverage Report", file=out)
            print("=" * 72, file=out)
            print(f"Project Root:      {report.project_root}", file=out)
            print(f"Total Modules:     {report.total_modules}", file=out)
            print(f"Total Functions:   {report.total_functions}", file=out)
            print(f"Tested:            {report.tested_functions}", file=out)
            print(f"Untested:          {report.untested_functions}", file=out)
            print(f"Overall Coverage:  {report.overall_coverage_percent:.1f}% ({report.overall_level.value})", file=out)
            print(file=out)

            # Critical gaps
            if report.critical_gaps:
                print("-" * 72, file=out)
                print("CRITICAL GAPS (Known Low-Coverage Watch List):", file=out)
                print("-" * 72, file=out)
                for gap in report.critical_gaps:
                    severity = gap.get("severity", "unknown").upper()
                    module = gap.get("module", "?")
                    func = gap.get("function", gap.get("function_or_class", "?"))
                    issue = gap.get("issue", "?")
                    rec = gap.get("recommendation", "")
                    print(f"  [{severity}] {module}::{func} — {issue}", file=out)
                    if rec:
                        print(f"         → {rec}", file=out)
                print(file=out)

            # Top suggestions
            if report.suggestions:
                print("-" * 72, file=out)
                print("TOP PRIORITY SUGGESTIONS:", file=out)
                print("-" * 72, file=out)
                for sug in report.suggestions:
                    priority = sug.get("priority", "?").upper()
                    module = sug.get("module", "?")
                    coverage = sug.get("current_coverage", 0)
                    count = sug.get("untested_count", 0)
                    top_funcs = sug.get("top_untested", [])
                    print(
                        f"  [{priority}] {module} ({coverage:.1f}% covered, {count} untested)",
                        file=out,
                    )
                    for fn in top_funcs:
                        print(f"         - {fn}", file=out)
                print(file=out)

            print("=" * 72, file=out)
            print("Full JSON report follows:", file=out)
            print("=" * 72, file=out)

        json.dump(report_dict, out, indent=2, default=str)
        print(file=out)
    finally:
        if args.output != "-":
            out.close()


if __name__ == "__main__":
    asyncio.run(_main())
