"""
tests/test_n1_contingency_scanner.py — Test Suite for N-1 Contingency Scanner.
"""

from __future__ import annotations

import pytest

from contingency.n1_scanner import ContingencySeverity, N1ContingencyScanner
from engine.benchmarks.ieee_cases import build_ieee_9bus_system, build_ieee_14bus_system


class TestN1ContingencyScanner:
    """Test suite for N-1 contingency scanner and performance ranking."""

    def test_n1_dc_screening_ieee9(self):
        """DC N-1 contingency scan on IEEE 9-bus system."""
        sys = build_ieee_9bus_system()
        scanner = N1ContingencyScanner(sys)

        summary = scanner.scan_all_contingencies(method="dc")

        # 6 lines + 3 transformers = 9 contingencies
        assert summary.total_contingencies == 9
        assert len(summary.ranked_results) == 9

        # Line 2 and Line 3 outages cause ~108.7% loading on adjacent lines, triggering warnings
        warn_or_crit = [r.case.contingency_id for r in summary.ranked_results if r.severity in (ContingencySeverity.WARNING, ContingencySeverity.CRITICAL)]
        assert len(warn_or_crit) > 0
        assert any("LINE" in cid for cid in warn_or_crit)

        # Ranked list should have highest PI first among same severity
        for i in range(len(summary.ranked_results) - 1):
            r1 = summary.ranked_results[i]
            r2 = summary.ranked_results[i + 1]
            if r1.severity == r2.severity and r1.converged and r2.converged:
                assert r1.performance_index >= r2.performance_index - 1e-4

    def test_n1_ac_screening_ieee9(self):
        """AC N-1 contingency scan on IEEE 9-bus system."""
        sys = build_ieee_9bus_system()
        scanner = N1ContingencyScanner(sys)

        summary = scanner.scan_all_contingencies(method="ac", v_min=0.90, v_max=1.10)

        assert summary.total_contingencies == 9
        report = scanner.generate_report(summary)
        assert "AHMEDETAP - AUTOMATED N-1 CONTINGENCY SCANNER REPORT" in report
        assert "Total Contingencies Scanned: 9" in report

    def test_n1_thermal_overload_detection(self):
        """Tightening branch ratings triggers warning or critical overloads."""
        sys = build_ieee_9bus_system()
        scanner = N1ContingencyScanner(sys)

        # In IEEE 9-bus, Line 4 (from 7 to 8) carries significant power.
        # Set a very tight rating of 30 MW on Line 4
        scanner.set_branch_rating("4", 30.0)

        summary = scanner.scan_all_contingencies(method="dc")
        # Line 4 should appear in overloaded lines for at least one contingency
        overloaded_cases = [
            r for r in summary.ranked_results
            if any(ov.get("branch_id") == "4" for ov in r.overloaded_lines)
        ]
        assert len(overloaded_cases) > 0
        assert summary.warning_count + summary.critical_count > 0
