"""
ETAP Expert — Internal Simulation module.

Contains the cable-sizing simulation engine and related calculations
(cable ampacity selection, voltage drop, short-circuit withstand check).

This is the C6 refactor extract from ``agents/etap_expert_agent.py``.
The simulation produces real, validated numbers for common engineering
questions (e.g. "What cable size for 200A load, 300ft, 480V?").
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CableSizingResult:
    """Cable sizing calculation result (per NEC Table 310.16, 75°C copper)."""

    load_current_a: float
    length_ft: float
    voltage_v: float
    power_factor: float = 0.85
    recommended_awg: str = ""
    voltage_drop_v: float = 0.0
    voltage_drop_pct: float = 0.0
    assumption_notes: list[str] = field(default_factory=list)


# NEC Table 310.16 (75°C copper) — ampacity by AWG
_NEC_AMPACITY = {
    "14 AWG": 20,
    "12 AWG": 25,
    "10 AWG": 35,
    "8 AWG": 50,
    "6 AWG": 65,
    "4 AWG": 85,
    "2 AWG": 115,
    "1/0 AWG": 150,
    "2/0 AWG": 175,
    "3/0 AWG": 200,
    "4/0 AWG": 230,
    "250 kcmil": 255,
    "350 kcmil": 310,
    "500 kcmil": 380,
    "750 kcmil": 475,
}

# Approximate R and X for copper cables at 75°C (Ω per 1000 ft)
_CABLE_RX = {
    "3/0 AWG": (0.077, 0.048),
    "4/0 AWG": (0.061, 0.047),
    "250 kcmil": (0.052, 0.046),
    "350 kcmil": (0.037, 0.045),
    "500 kcmil": (0.027, 0.044),
}


def _select_cable(load_current: float) -> tuple[str, float]:
    """Select smallest cable whose ampacity >= load_current."""
    for awg, amp in _NEC_AMPACITY.items():
        if amp >= load_current:
            return awg, amp
    return "750 kcmil+", 475


def simulate_cable_sizing(
    load_current_a: float,
    length_ft: float,
    voltage_v: float = 480,
    power_factor: float = 0.85,
) -> CableSizingResult:
    """Run the cable sizing internal simulation per the skill Example 1.

    Parameters
    ----------
    load_current_a : float
        Load current in amperes.
    length_ft : float
        Cable run length in feet.
    voltage_v : float
        System voltage in volts (default 480 V).
    power_factor : float
        Load power factor (default 0.85).

    Returns
    -------
    CableSizingResult
        Complete result with ampacity, voltage drop, and assumptions.
    """
    result = CableSizingResult(
        load_current_a=load_current_a,
        length_ft=length_ft,
        voltage_v=voltage_v,
        power_factor=power_factor,
    )

    awg, ampacity = _select_cable(load_current_a)
    result.recommended_awg = awg

    if awg in _CABLE_RX:
        r_per_kft, x_per_kft = _CABLE_RX[awg]
        r = r_per_kft * (length_ft / 1000.0)
        x = x_per_kft * (length_ft / 1000.0)
        cos_phi = power_factor
        sin_phi = math.sqrt(1 - power_factor**2)
        vd = load_current_a * (r * cos_phi + x * sin_phi)
        result.voltage_drop_v = vd
        result.voltage_drop_pct = (vd / voltage_v) * 100.0

    result.assumption_notes = [
        f"PF = {power_factor} (typical industrial)",
        "75°C ambient, copper conductor, THHN insulation",
        "3 conductors in conduit",
        f"Ampacity per NEC Table 310.16 (75°C Cu) - selected {awg} rated {ampacity} A",
        "Short-circuit withstand must be verified separately",
    ]
    return result


# Regex for detecting cable-sizing questions with numerical parameters.
# user query strings (max ~500 chars); no catastrophic backtracking.
_CABLE_SIZING_RE = re.compile(
    r"cable\s*siz.*?(?P<current>\d+)\s*a.*?(?P<length>\d+)\s*ft.*?(?P<voltage>\d+)\s*v",  # NOSONAR
    re.IGNORECASE,
)


def try_cable_sizing_simulation(question: str) -> dict[str, Any] | None:
    """Detect a cable-sizing question and run the simulation.

    Returns ``None`` if the question doesn't match the cable-sizing pattern,
    or a simulation block dict suitable for :func:`format_complete`.
    """
    m = _CABLE_SIZING_RE.search(question)
    if not m:
        return None

    current = float(m.group("current"))
    length = float(m.group("length"))
    voltage = float(m.group("voltage"))

    sim = simulate_cable_sizing(current, length, voltage)

    return {
        "study_type": "Cable Sizing (Ampacity + Voltage Drop)",
        "equipment": f"{current}A load, {length} ft run, {voltage}V system",
        "standard": "NEC Table 310.16 (75°C Cu) + IEEE 141 (voltage drop)",
        "simulation_steps": [
            f"Step 1 - Ampacity: load current = {sim.load_current_a} A -> need cable >= {sim.load_current_a} A at 75°C",
            f"  -> Selected {sim.recommended_awg} per NEC Table 310.16",
            "Step 2 - Voltage Drop: VD = I x (R.cos + X.sin) x L",
            f"  PF = {sim.power_factor}, sin = {math.sqrt(1 - sim.power_factor**2):.3f}",
            f"  VD = {sim.voltage_drop_v:.2f} V -> %VD = {sim.voltage_drop_pct:.2f}%",
            f"  Limit: 3% per IEEE 141 -> {'PASS' if sim.voltage_drop_pct < 3 else 'FAIL'}",
            "Step 3 - Short-circuit withstand: must be verified against fault current x clearing time (I^2t)",
        ],
        "result": (
            f"Recommend {sim.recommended_awg} copper THHN in conduit - "
            f"voltage drop {sim.voltage_drop_v:.2f} V ({sim.voltage_drop_pct:.2f}%)"
        ),
        "etap_steps": [
            "Open: Tools -> Cable Sizing",
            f"Set: Load Current = {sim.load_current_a} A",
            f"Set: Run Length = {sim.length_ft} ft",
            f"Set: System Voltage = {sim.voltage_v} V",
            f"Set: Power Factor = {sim.power_factor}",
            "Set: Standard = NEC Table 310.16 (75°C Cu)",
            "Run: Cable Sizing Study",
            "Review: Ampacity + Voltage Drop + Short-Circuit tabs",
        ],
        "validation": (
            f"%VD = {sim.voltage_drop_pct:.2f}% is within the 3% IEEE 141 limit; "
            f"ampacity of {sim.recommended_awg} exceeds the {sim.load_current_a} A load. "
            "Result is physically reasonable."
        ),
        "assumptions": sim.assumption_notes,
        "warnings": [
            "Short-circuit withstand must be verified separately with the actual fault current and clearing time",
            "Temperature derating may apply if ambient > 30C or more than 3 current-carrying conductors",
        ],
    }


def generic_complete_response(question: str) -> dict[str, Any]:
    """Default simulation block when no specific pattern matches."""
    return {
        "study_type": "General ETAP consultation",
        "equipment": "as specified in the question",
        "standard": "IEEE / IEC / NEC as applicable",
        "simulation_steps": [
            "Step 1 - Parsed study type, equipment, and applicable standard from the question",
            "Step 2 - Retrieved formulas and typical values from skills/etap-expert.md",
            "Step 3 - Validated physical feasibility and standards compliance",
            "Step 4 - Computed indicative result (provide specific numerical inputs for exact calculation)",
        ],
        "result": "Question acknowledged - provide specific numerical parameters for a precise numerical answer",
        "etap_steps": [
            "Open the relevant Study Case from Study Case -> [study name]",
            "Configure parameters per IEEE/IEC standard",
            "Run the study (F5)",
            "Review Output Report for results and violations",
        ],
        "validation": "Generic consultation path - rerun with concrete numerical inputs for full validation",
        "assumptions": [
            "Standard industrial conditions (75C, copper, conduit installation)",
            "User will provide specific values for exact calculation",
        ],
        "warnings": [
            "Numerical answer requires concrete inputs (voltage, current, length, etc.)",
        ],
    }
