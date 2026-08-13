"""
ETAP Expert — Classification module.

Rule-based, deterministic classification of user questions into one of
four modes: ``complete``, ``incomplete``, ``wrong``, ``adms``.

This is the C6 refactor extract from ``agents/etap_expert_agent.py``.
The classification patterns are the single source of truth — defined here
and imported by the main agent class.

Decision order (first match wins):
    1. ADMS — any ADMS keyword present
    2. WRONG — a wrong-study pattern matches
    3. INCOMPLETE — a missing-data pattern matches
    4. COMPLETE — otherwise (default)
"""

from __future__ import annotations

import re
from typing import Literal

Classification = Literal["complete", "incomplete", "wrong", "adms"]

# ADMS / DER trigger words (from skill Section 5 + 11)
_ADMS_KEYWORDS: tuple[str, ...] = (
    "flisr",
    "fdir",
    "vvo",
    "volt/var",
    "cvr",
    "derms",
    "dms",
    "oms",
    "escada",
    "scada",
    "adms",
    "state estimation",
    "load forecasting",
    "prass",
    "feeder balancing",
    "switching order",
    "outage management",
    "predictive simulation",
    "real-time",
    "real time",
    "operator training",
    "iap",
    "intelligent alarm",
)

# Wrong-study patterns (from skill Section 14 — Mistake Category 1)
# Each entry: (regex, problem_description, correct_approach)
_WRONG_STUDY_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"load\s*flow.*fault\s*current|fault\s*current.*load\s*flow",
        "Load Flow calculates steady-state power flow, not fault currents",
        "Short Circuit study per ANSI C37 or IEC 60909",
    ),
    (
        r"load\s*flow.*arc\s*flash|arc\s*flash.*load\s*flow",
        "Arc Flash requires Short Circuit results first, then IEEE 1584 calculation",
        "Run Short Circuit study, then Arc Flash study",
    ),
    (
        r"short\s*circuit.*cable\s*siz|cable\s*siz.*short\s*circuit",
        "Cable sizing needs Load Flow for ampacity + voltage drop, then Short Circuit for withstand",
        "Run Load Flow first, then verify with Short Circuit",
    ),
    (
        r"load\s*flow.*motor\s*start|motor\s*start.*load\s*flow",
        "Motor starting transients require dynamic Motor Acceleration study",
        "Run Motor Acceleration study",
    ),
    (
        r"load\s*flow.*protect|protect.*load\s*flow",
        "Protection coordination requires relay TCC curves via Star module",
        "Run Protection Coordination study (Star/StarZ)",
    ),
    (
        r"etap.*fem|fem.*etap|finite\s*element.*etap",
        "ETAP does not perform finite element analysis",
        "Use ANSYS / COMSOL for FEM. ETAP does power system analysis.",
    ),
    (
        r"etap.*pcb|pcb.*etap",
        "ETAP is for electrical power systems, not electronics design",
        "Use Altium / KiCad / Eagle for PCB design",
    ),
    (
        r"etap.*hvac|hvac.*etap",
        "ETAP is for electrical power, not mechanical HVAC",
        "Use Trace 700 / HAP for HVAC sizing",
    ),
]

# Missing-data patterns (from skill Section 14 — Mistake Category 2)
# Each entry: (regex, missing_data_description, clarifying_question)
_INCOMPLETE_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"size\s+transformer.*?(\d+)\s*kw|transformer.*?for\s*(\d+)\s*kw",
        "Voltage, power factor, load type, future growth factor",
        "What is the primary and secondary voltage? What is the load power factor and type (continuous/intermittent)?",
    ),
    (
        r"set\s+relay.*?motor|relay.*?for\s+motor",
        "Motor HP, starting method, CT ratio, full-load current",
        "What is the motor HP, rated voltage, and CT ratio? What starting method is used (DOL, star-delta, VFD)?",
    ),
    (
        r"calculate\s+voltage\s+drop(?!.*\d)",
        "Cable size, length, load current, power factor",
        "What is the cable size, run length, and load current? What is the load power factor?",
    ),
    (
        r"run\s+arc\s+flash(?!.*(?:kv|ka|voltage|current))",
        "Voltage, bolted fault current, arc duration, working distance",
        "What is the system voltage (kV), bolted fault current (kA), assumed arc duration (s), and working distance (mm)?",
    ),
    (
        r"size\s+battery(?!.*(?:ah|kwh|hours|backup))",
        "Load profile, backup time required, temperature, allowable DOD",
        "What is the load profile (kW) and required backup time (hours)? What is the battery chemistry and allowable depth of discharge?",
    ),
    (
        r"size\s+cable.*?(?!.*(?:a\b|amp|amps|\d+\s*ft|\d+\s*m\b))",
        "Load current, length, voltage, installation method",
        "What is the load current (A), cable run length (ft or m), system voltage (V), and installation method (conduit/tray/direct buried)?",
    ),
]


def classify(question: str) -> Classification:
    """Classify a question into complete / incomplete / wrong / adms.

    Decision order (first match wins):
      1. ADMS — if any ADMS keyword is present
      2. WRONG — if a wrong-study pattern matches
      3. INCOMPLETE — if a missing-data pattern matches
      4. COMPLETE — otherwise (default)
    """
    q = question.lower()

    if any(kw in q for kw in _ADMS_KEYWORDS):
        return "adms"

    for pattern, _, _ in _WRONG_STUDY_PATTERNS:
        if re.search(pattern, q):
            return "wrong"

    for pattern, _, _ in _INCOMPLETE_PATTERNS:
        if re.search(pattern, q):
            return "incomplete"

    return "complete"


def find_wrong_pattern(question: str) -> tuple[str, str]:
    """Return (problem_description, correct_approach) for the first
    matching wrong-study pattern, or a generic fallback."""
    q = question.lower()
    for pattern, problem, correct in _WRONG_STUDY_PATTERNS:
        if re.search(pattern, q):
            return problem, correct
    return (
        "The requested approach does not match the physical phenomenon to be analyzed",
        "Use the correct ETAP study type for the goal (see skills/etap-expert.md Section 14)",
    )


def find_incomplete_pattern(question: str) -> tuple[str, str]:
    """Return (missing_data_description, clarifying_question) for the first
    matching incomplete pattern, or a generic fallback."""
    q = question.lower()
    for pattern, missing, clarifying in _INCOMPLETE_PATTERNS:
        if re.search(pattern, q):
            return missing, clarifying
    return (
        "Required numerical parameters",
        "Please provide the specific numerical parameters (voltage, current, length, etc.)",
    )
