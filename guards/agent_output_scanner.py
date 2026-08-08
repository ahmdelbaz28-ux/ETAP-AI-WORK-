"""
guards/agent_output_scanner.py — Agent Output Scanner (F-12 Fix)
================================================================

ARCHITECTURE AUDIT FIX (F-12): Scans agent TEXT outputs for AI failure
modes BEFORE delivering them to the user, closing the gap where the
14 failure mode detectors only ran inside the secure executor for
Python code, not on agent responses at the API boundary.

This module provides a lightweight text-based scanner that runs the
most critical failure mode detectors (FM-03, FM-04, FM-08) on agent
text output. It does NOT parse AST — it uses regex patterns suitable
for scanning natural language + code mixed output.

Usage:
    from guards.agent_output_scanner import scan_agent_output

    warnings = scan_agent_output("load_flow_agent", agent_text_output)
    if warnings:
        logger.warning("Agent output has failure mode warnings: %s", warnings)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OutputWarning:
    """A single failure mode warning from agent output scanning."""

    failure_mode_id: str
    description: str
    severity: str  # "critical" | "warning"
    matched_text: str = ""


# ─── Lightweight regex detectors for agent text output ─────────────────────
# These patterns detect the 3 most dangerous failure modes in text output
# without requiring AST parsing (which only works for pure Python code).

_DETECTORS: list[dict[str, Any]] = [
    # FM-03: Hallucinated API or package
    # Look for import statements referencing unknown/suspicious packages
    {
        "id": "FM-03",
        "description": "Hallucinated API or package in agent output",
        "severity": "critical",
        "patterns": [
            r"import\s+(etap_auto|power_calc|grid_solver|fault_analyzer|smart_grid_ai)",
            r"from\s+(etap_auto|power_calc|grid_solver|fault_analyzer|smart_grid_ai)\s+import",
            r"pip\s+install\s+(etap-auto|power-calc|grid-solver|fault-analyzer|smart-grid-ai)",
        ],
    },
    # FM-04: Hardcoded success return
    # Look for patterns where the agent declares success without computation
    {
        "id": "FM-04",
        "description": "Hardcoded success declaration in agent output",
        "severity": "critical",
        "patterns": [
            r"return\s+True\s*#\s*success",
            r'"success"\s*:\s*True\s*#\s*assumed',
            r"status\s*=\s*['\"]pass['\"]\s*#\s*no.*check",
            r"converged\s*=\s*True\s*#\s*assumed",
        ],
    },
    # FM-08: Write before read (overwrite input)
    # Look for patterns where input data is overwritten before being read
    {
        "id": "FM-08",
        "description": "Input data overwritten before being read",
        "severity": "warning",
        "patterns": [
            r"input_data\s*=\s*\{[^}]*\}\s*#.*overwrite",
            r"bus_data\s*=\s*None\s*#.*reset",
        ],
    },
]


def scan_agent_output(
    agent_handle: str,
    output: str,
    max_warnings: int = 20,
) -> list[OutputWarning]:
    """Scan agent text output for AI failure modes at the API boundary.

    Parameters
    ----------
    agent_handle : str
        The agent's prompt handle (e.g. "load_flow_agent").
    output : str
        The agent's text output to scan.
    max_warnings : int
        Maximum number of warnings to return (prevents flooding).

    Returns
    -------
    list[OutputWarning]
        Warnings for detected failure modes. Empty list means clean output.
    """
    if not output or not isinstance(output, str):
        return []

    warnings: list[OutputWarning] = []

    for detector in _DETECTORS:
        for pattern in detector.get("patterns", []):
            try:
                for match in re.finditer(pattern, output, re.IGNORECASE | re.MULTILINE):
                    warnings.append(
                        OutputWarning(
                            failure_mode_id=detector["id"],
                            description=detector["description"],
                            severity=detector.get("severity", "warning"),
                            matched_text=match.group(0)[:100],  # Truncate for safety
                        )
                    )
                    if len(warnings) >= max_warnings:
                        break
            except re.error:
                logger.debug("Invalid regex pattern in FM detector: %s", pattern)
                continue

            if len(warnings) >= max_warnings:
                break

        if len(warnings) >= max_warnings:
            break

    if warnings:
        critical_count = sum(1 for w in warnings if w.severity == "critical")
        logger.warning(
            "Agent '%s' output triggered %d failure mode warnings (%d critical, %d regular): %s",
            agent_handle,
            len(warnings),
            critical_count,
            len(warnings) - critical_count,
            [w.failure_mode_id for w in warnings],
        )

    return warnings


def scan_agent_output_to_metadata(
    agent_handle: str,
    output: str,
) -> dict[str, Any]:
    """Scan agent output and return results as metadata dict.

    Convenient for attaching to API response metadata.

    Returns
    -------
    dict
        Metadata with 'fm_warnings' list and 'fm_clean' boolean.
    """
    warnings = scan_agent_output(agent_handle, output)
    return {
        "fm_warnings": [
            {
                "id": w.failure_mode_id,
                "description": w.description,
                "severity": w.severity,
                "matched": w.matched_text,
            }
            for w in warnings
        ],
        "fm_clean": len(warnings) == 0,
    }
