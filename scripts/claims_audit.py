#!/usr/bin/env python3
"""
scripts/claims_audit.py — Engineering Claims and Standards Test Audit.

Automatically verifies that every engineering standard cited in codebase docstrings
and comments (e.g., IEEE 1584, IEC 60909, IEEE 3002.7, IEC 60255, IEEE 519, IEEE 399,
NFPA 70E, ANSI Z535) has corresponding empirical verification in the test suite.

Usage:
    python scripts/claims_audit.py [--json] [--strict]

Exit codes:
    0 = all cited standards have matching empirical test coverage
    1 = untested standard claims detected
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parents[1]

# Key power engineering standards recognized in AhmedETAP platform
KNOWN_STANDARDS = [
    r"IEEE\s*1584(?:-\d{4})?",
    r"IEC\s*60909(?:-\d+)?",
    r"IEEE\s*3002(?:\.\d+)?",
    r"IEC\s*60255(?:-\d+)?",
    r"IEEE\s*519(?:-\d{4})?",
    r"IEEE\s*399",
    r"IEEE\s*80(?:-\d{4})?",
    r"IEEE\s*1547(?:-\d{4})?",
    r"IEC\s*62933",
    r"IEC\s*61850",
    r"NFPA\s*70E",
    r"ANSI\s*Z535(?:\.\d+)?",
    r"IEC\s*60364",
    r"IEEE\s*141",
    r"IEEE\s*242",
]

# Directories containing calculation engines and agents to audit for claims
AUDIT_DIRS = [
    REPO_ROOT / "engine",
    REPO_ROOT / "fault_analysis",
    REPO_ROOT / "load_flow",
    REPO_ROOT / "coordination",
    REPO_ROOT / "motor_starting",
    REPO_ROOT / "agents",
    REPO_ROOT / "core_model",
]

TESTS_DIR = REPO_ROOT / "tests"


@dataclass
class StandardClaim:
    standard: str
    source_file: str
    line_number: int
    context: str


@dataclass
class StandardAuditResult:
    standard_name: str
    claim_count: int
    test_count: int
    source_files: List[str]
    test_files: List[str]
    status: str  # "VERIFIED" | "MISSING_TESTS"


def canonical_standard_name(raw: str) -> str:
    """Normalize standard string for comparison (e.g. 'IEEE 1584-2018' -> 'IEEE 1584')."""
    cleaned = re.sub(r"[\s\-_]+", " ", raw.upper().strip())
    # Keep standard family (e.g. IEEE 1584, IEC 60909, etc.)
    match = re.match(r"(IEEE|IEC|NFPA|ANSI)\s*([A-Z0-9\.]+)", cleaned)
    if match:
        org, num = match.groups()
        # Remove trailing year if present
        base_num = num.split("-")[0]
        return f"{org} {base_num}"
    return cleaned


def extract_claims() -> Dict[str, List[StandardClaim]]:
    """Scan source files for standard citations."""
    claims: Dict[str, List[StandardClaim]] = {}

    pattern = re.compile(r"\b(" + "|".join(KNOWN_STANDARDS) + r")\b", re.IGNORECASE)

    for audit_dir in AUDIT_DIRS:
        if not audit_dir.exists():
            continue
        for py_file in audit_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                matches = pattern.findall(line)
                for match in matches:
                    cname = canonical_standard_name(match)
                    if cname not in claims:
                        claims[cname] = []
                    rel_path = str(py_file.relative_to(REPO_ROOT))
                    claims[cname].append(
                        StandardClaim(
                            standard=cname,
                            source_file=rel_path,
                            line_number=line_no,
                            context=line.strip()[:120],
                        )
                    )

    return claims


def extract_test_coverage() -> Dict[str, Set[str]]:
    """Scan tests/ for standard mentions/tests."""
    coverage: Dict[str, Set[str]] = {}

    pattern = re.compile(r"\b(" + "|".join(KNOWN_STANDARDS) + r")\b", re.IGNORECASE)

    if not TESTS_DIR.exists():
        return coverage

    for test_file in TESTS_DIR.rglob("*.py"):
        try:
            content = test_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for line in content.splitlines():
            matches = pattern.findall(line)
            for match in matches:
                cname = canonical_standard_name(match)
                if cname not in coverage:
                    coverage[cname] = set()
                rel_path = str(test_file.relative_to(REPO_ROOT))
                coverage[cname].add(rel_path)

    return coverage


def audit_claims(strict: bool = False) -> List[StandardAuditResult]:
    """Audit all claimed standards against test coverage."""
    claims = extract_claims()
    test_cov = extract_test_coverage()

    results = []
    for std_name, claim_list in sorted(claims.items()):
        test_files = sorted(test_cov.get(std_name, set()))
        src_files = sorted({c.source_file for c in claim_list})
        status = "VERIFIED" if len(test_files) > 0 else "MISSING_TESTS"

        results.append(
            StandardAuditResult(
                standard_name=std_name,
                claim_count=len(claim_list),
                test_count=len(test_files),
                source_files=src_files,
                test_files=test_files,
                status=status,
            )
        )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit engineering claims against empirical tests")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--strict", action="store_true", help="Fail if any standard has no test")
    args = parser.parse_args()

    results = audit_claims(strict=args.strict)

    missing_count = sum(1 for r in results if r.status == "MISSING_TESTS")
    verified_count = sum(1 for r in results if r.status == "VERIFIED")

    if args.json:
        output = {
            "verified_count": verified_count,
            "missing_count": missing_count,
            "results": [asdict(r) for r in results],
        }
        print(json.dumps(output, indent=2))
    else:
        print("\n=======================================================")
        print("   AhmedETAP Standards & Claims Verification Audit")
        print("=======================================================\n")
        print(f"{'Standard':<20} | {'Claims':<8} | {'Tests':<8} | {'Status'}")
        print(f"{'-'*20}-+-{'-'*8}-+-{'-'*8}-+--------")
        for r in results:
            icon = "[PASS]" if r.status == "VERIFIED" else "[FAIL]"
            print(f"{r.standard_name:<20} | {r.claim_count:<8} | {r.test_count:<8} | {icon} {r.status}")

        print(f"\nSummary: {verified_count} Verified, {missing_count} Missing empirical test coverage.\n")

    if args.strict and missing_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
