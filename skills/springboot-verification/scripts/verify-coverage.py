#!/usr/bin/env python3
"""
JaCoCo Coverage Verification Script
====================================
Parses JaCoCo coverage reports (CSV or XML) and verifies that
coverage meets the configured threshold.

Supports both Maven and Gradle project layouts.

Usage:
    python3 verify-coverage.py [OPTIONS]

Options:
    -b, --build-tool <maven|gradle>   Build tool (default: auto-detect)
    -t, --threshold <pct>             Coverage threshold percentage (default: 80)
    -p, --project-dir <path>          Project root directory (default: .)
    -o, --output <file>               Output report file (default: stdout)
    --percentage-only                 Output only the coverage percentage number
    --per-class                       Show per-class coverage breakdown
    -v, --verbose                     Verbose output
    -h, --help                        Show help

Exit codes:
    0 — Coverage meets threshold
    1 — Coverage below threshold
    2 — Error (no report found, parse failure, etc.)
"""

import argparse
import csv
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CoverageResult:
    """Holds coverage data for a single class or the entire project."""
    name: str
    line_covered: int = 0
    line_missed: int = 0
    branch_covered: int = 0
    branch_missed: int = 0
    instruction_covered: int = 0
    instruction_missed: int = 0

    @property
    def line_total(self) -> int:
        return self.line_covered + self.line_missed

    @property
    def line_coverage_pct(self) -> float:
        if self.line_total == 0:
            return 100.0
        return (self.line_covered / self.line_total) * 100.0

    @property
    def branch_total(self) -> int:
        return self.branch_covered + self.branch_missed

    @property
    def branch_coverage_pct(self) -> float:
        if self.branch_total == 0:
            return 100.0
        return (self.branch_covered / self.branch_total) * 100.0

    @property
    def instruction_total(self) -> int:
        return self.instruction_covered + self.instruction_missed

    @property
    def instruction_coverage_pct(self) -> float:
        if self.instruction_total == 0:
            return 100.0
        return (self.instruction_covered / self.instruction_total) * 100.0


def find_jacoco_report(project_dir: str, build_tool: str) -> Optional[str]:
    """Find the JaCoCo report file in the project build output."""
    project_path = Path(project_dir)

    # Possible report locations
    maven_csv = project_path / "target" / "site" / "jacoco" / "jacoco.csv"
    maven_xml = project_path / "target" / "site" / "jacoco" / "jacoco.xml"
    gradle_csv = project_path / "build" / "reports" / "jacoco" / "test" / "jacocoTestReport.csv"
    gradle_xml = project_path / "build" / "reports" / "jacoco" / "test" / "jacocoTestReport.xml"

    # Also check multi-module projects
    search_paths = []
    if build_tool == "maven":
        search_paths = [maven_csv, maven_xml]
        # Also search for multi-module
        for csv_path in project_path.rglob("target/site/jacoco/jacoco.csv"):
            search_paths.insert(0, csv_path)
        for xml_path in project_path.rglob("target/site/jacoco/jacoco.xml"):
            search_paths.insert(0, xml_path)
    else:
        search_paths = [gradle_csv, gradle_xml]
        for csv_path in project_path.rglob("build/reports/jacoco/test/jacocoTestReport.csv"):
            search_paths.insert(0, csv_path)
        for xml_path in project_path.rglob("build/reports/jacoco/test/jacocoTestReport.xml"):
            search_paths.insert(0, xml_path)

    for path in search_paths:
        if path.exists():
            return str(path)

    return None


def parse_csv_report(csv_path: str) -> list[CoverageResult]:
    """Parse a JaCoCo CSV report file."""
    results = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            return results

        # JaCoCo CSV columns: Group, Package, Class, INSTRUCTION_MISSED, INSTRUCTION_COVERED,
        #                     BRANCH_MISSED, BRANCH_COVERED, LINE_MISSED, LINE_COVERED, ...
        for row in reader:
            if len(row) < 9:
                continue
            try:
                result = CoverageResult(
                    name=f"{row[1]}.{row[2]}" if len(row) > 2 else row[2],
                    instruction_missed=int(row[3]),
                    instruction_covered=int(row[4]),
                    branch_missed=int(row[5]),
                    branch_covered=int(row[6]),
                    line_missed=int(row[7]),
                    line_covered=int(row[8]),
                )
                results.append(result)
            except (ValueError, IndexError):
                continue

    return results


def parse_xml_report(xml_path: str) -> list[CoverageResult]:
    """Parse a JaCoCo XML report file."""
    results = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError:
        return results

    for package in root.iter("package"):
        package_name = package.get("name", "")
        for cls in package.iter("class"):
            class_name = cls.get("name", "").replace("/", ".")

            result = CoverageResult(name=f"{package_name}.{class_name}")

            for method in cls.iter("method"):
                for counter in method.iter("counter"):
                    counter_type = counter.get("type", "")
                    missed = int(counter.get("missed", 0))
                    covered = int(counter.get("covered", 0))

                    if counter_type == "LINE":
                        result.line_missed += missed
                        result.line_covered += covered
                    elif counter_type == "BRANCH":
                        result.branch_missed += missed
                        result.branch_covered += covered
                    elif counter_type == "INSTRUCTION":
                        result.instruction_missed += missed
                        result.instruction_covered += covered

            results.append(result)

    # If no class-level data, aggregate from package counters
    if not results:
        for package in root.iter("package"):
            result = CoverageResult(name=package.get("name", ""))
            for counter in package.iter("counter"):
                counter_type = counter.get("type", "")
                missed = int(counter.get("missed", 0))
                covered = int(counter.get("covered", 0))
                if counter_type == "LINE":
                    result.line_missed += missed
                    result.line_covered += covered
                elif counter_type == "BRANCH":
                    result.branch_missed += missed
                    result.branch_covered += covered
                elif counter_type == "INSTRUCTION":
                    result.instruction_missed += missed
                    result.instruction_covered += covered
            results.append(result)

    return results


def aggregate_coverage(results: list[CoverageResult]) -> CoverageResult:
    """Aggregate coverage data across all classes into a single result."""
    total = CoverageResult(name="TOTAL")
    for r in results:
        total.line_covered += r.line_covered
        total.line_missed += r.line_missed
        total.branch_covered += r.branch_covered
        total.branch_missed += r.branch_missed
        total.instruction_covered += r.instruction_covered
        total.instruction_missed += r.instruction_missed
    return total


def main():
    parser = argparse.ArgumentParser(
        description="JaCoCo Coverage Verification Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-b", "--build-tool", choices=["maven", "gradle"],
                        help="Build tool (default: auto-detect)")
    parser.add_argument("-t", "--threshold", type=int, default=80,
                        help="Coverage threshold percentage (default: 80)")
    parser.add_argument("-p", "--project-dir", default=".",
                        help="Project root directory (default: .)")
    parser.add_argument("-o", "--output", help="Output report file")
    parser.add_argument("--percentage-only", action="store_true",
                        help="Output only the coverage percentage number")
    parser.add_argument("--per-class", action="store_true",
                        help="Show per-class coverage breakdown")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    # Auto-detect build tool
    build_tool = args.build_tool
    if not build_tool:
        if os.path.exists(os.path.join(args.project_dir, "pom.xml")):
            build_tool = "maven"
        elif os.path.exists(os.path.join(args.project_dir, "build.gradle")) or \
             os.path.exists(os.path.join(args.project_dir, "build.gradle.kts")):
            build_tool = "gradle"
        else:
            print("ERROR: Cannot detect build tool — no pom.xml or build.gradle found",
                  file=sys.stderr)
            sys.exit(2)

    # Find JaCoCo report
    report_path = find_jacoco_report(args.project_dir, build_tool)
    if not report_path:
        if args.percentage_only:
            print("0")
        else:
            print("ERROR: No JaCoCo report found. Run tests with coverage first.",
                  file=sys.stderr)
        sys.exit(2)

    if args.verbose:
        print(f"Found JaCoCo report: {report_path}")

    # Parse report
    results = []
    if report_path.endswith(".csv"):
        results = parse_csv_report(report_path)
    elif report_path.endswith(".xml"):
        results = parse_xml_report(report_path)

    if not results:
        if args.percentage_only:
            print("0")
        else:
            print("ERROR: Could not parse JaCoCo report", file=sys.stderr)
        sys.exit(2)

    # Aggregate
    total = aggregate_coverage(results)

    # Percentage-only mode (for scripting)
    if args.percentage_only:
        print(f"{total.line_coverage_pct:.0f}")
        sys.exit(0 if total.line_coverage_pct >= args.threshold else 1)

    # Full report
    output_lines = []
    output_lines.append("=" * 60)
    output_lines.append("  JACOCO COVERAGE REPORT")
    output_lines.append("=" * 60)
    output_lines.append("")
    output_lines.append(f"  Project:     {os.path.abspath(args.project_dir)}")
    output_lines.append(f"  Build Tool:  {build_tool}")
    output_lines.append(f"  Report:      {report_path}")
    output_lines.append(f"  Threshold:   {args.threshold}%")
    output_lines.append("")
    output_lines.append("-" * 60)
    output_lines.append("  Overall Coverage")
    output_lines.append("-" * 60)
    output_lines.append(f"  Instructions:  {total.instruction_coverage_pct:6.1f}%  "
                       f"({total.instruction_covered}/{total.instruction_total})")
    output_lines.append(f"  Lines:         {total.line_coverage_pct:6.1f}%  "
                       f"({total.line_covered}/{total.line_total})")
    output_lines.append(f"  Branches:      {total.branch_coverage_pct:6.1f}%  "
                       f"({total.branch_covered}/{total.branch_total})")
    output_lines.append("")

    # Per-class breakdown
    if args.per_class:
        output_lines.append("-" * 60)
        output_lines.append("  Per-Class Coverage")
        output_lines.append("-" * 60)
        for r in sorted(results, key=lambda x: x.line_coverage_pct):
            status = "PASS" if r.line_coverage_pct >= args.threshold else "FAIL"
            output_lines.append(f"  [{status}] {r.name}: {r.line_coverage_pct:.1f}% lines")
        output_lines.append("")

    # Threshold check
    output_lines.append("-" * 60)
    if total.line_coverage_pct >= args.threshold:
        output_lines.append(f"  RESULT: PASS — Coverage {total.line_coverage_pct:.1f}% "
                           f">= {args.threshold}% threshold")
    else:
        output_lines.append(f"  RESULT: FAIL — Coverage {total.line_coverage_pct:.1f}% "
                           f"< {args.threshold}% threshold")
    output_lines.append("-" * 60)
    output_lines.append("")

    report_text = "\n".join(output_lines)
    print(report_text)

    # Save to file if requested
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report_text)

    sys.exit(0 if total.line_coverage_pct >= args.threshold else 1)


if __name__ == "__main__":
    main()
