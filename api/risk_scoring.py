"""
Risk scoring for study results.
Evaluates study outputs against engineering thresholds and assigns
a risk level: low | medium | high | critical.
"""
from __future__ import annotations
from typing import Any, Optional

RISK_LEVELS = ("low", "medium", "high", "critical")

def score_load_flow(result: dict[str, Any]) -> dict[str, Any]:
    """Score a load flow study result."""
    buses = result.get("buses", {})
    violations = []
    max_risk = "low"

    for bus_id, bus in buses.items():
        v = bus.get("voltage_magnitude", 1.0)
        if v < 0.85 or v > 1.15:
            max_risk = "critical"
            violations.append(f"Bus {bus_id}: voltage={v:.3f} pu - OUT OF RANGE (<0.85 or >1.15)")
        elif v < 0.90 or v > 1.10:
            if max_risk in ("low", "medium"):
                max_risk = "high"
            violations.append(f"Bus {bus_id}: voltage={v:.3f} pu - ALARM (<0.90 or >1.10)")
        elif v < 0.95 or v > 1.05:
            if max_risk == "low":
                max_risk = "medium"
            violations.append(f"Bus {bus_id}: voltage={v:.3f} pu - CAUTION (<0.95 or >1.05)")

    return {
        "risk_score": max_risk,
        "risk_violations": violations,
    }

def score_short_circuit(result: dict[str, Any]) -> dict[str, Any]:
    """Score a short circuit study result."""
    faults = result.get("fault_currents", {})
    violations = []
    max_risk = "low"

    for bus_id, currents in faults.items():
        for fault_type, ka in currents.items():
            if isinstance(ka, (int, float)):
                if ka > 50:
                    max_risk = "critical"
                    violations.append(f"Bus {bus_id} {fault_type}: {ka:.1f} kA - EXCEEDS 50 kA rating")
                elif ka > 40:
                    if max_risk in ("low", "medium"):
                        max_risk = "high"
                    violations.append(f"Bus {bus_id} {fault_type}: {ka:.1f} kA - EXCEEDS 40 kA")

    return {
        "risk_score": max_risk,
        "risk_violations": violations,
    }

def score_arc_flash(result: dict[str, Any]) -> dict[str, Any]:
    """Score an arc flash study result."""
    equip = result.get("equipment_results", {})
    violations = []
    max_risk = "low"

    for equip_id, data in equip.items():
        ie = data.get("incident_energy_cal_cm2", 0)
        if ie > 40:
            max_risk = "critical"
            violations.append(f"{equip_id}: IE={ie:.1f} cal/cm² - >40 DANGEROUS (NFPA 70E HRC 4+)")
        elif ie > 25:
            if max_risk in ("low", "medium"):
                max_risk = "high"
            violations.append(f"{equip_id}: IE={ie:.1f} cal/cm² - >25 (NFPA 70E HRC 3)")
        elif ie > 8:
            if max_risk == "low":
                max_risk = "medium"
            violations.append(f"{equip_id}: IE={ie:.1f} cal/cm² - >8 (NFPA 70E HRC 2)")

    return {
        "risk_score": max_risk,
        "risk_violations": violations,
    }

def score_harmonic(result: dict[str, Any]) -> dict[str, Any]:
    """Score a harmonic analysis result against IEEE 519."""
    buses = result.get("buses", {})
    violations = []
    max_risk = "low"
    limit = result.get("total_harmonic_distortion_limit_percent", 5.0)

    for bus_id, bus in buses.items():
        vthd = bus.get("voltage_thd_percent", 0)
        if vthd > limit * 1.2:
            max_risk = "critical"
            violations.append(f"Bus {bus_id}: VTHD={vthd:.1f}% - EXCEEDS {limit}% limit")
        elif vthd > limit:
            if max_risk in ("low", "medium"):
                max_risk = "high"
            violations.append(f"Bus {bus_id}: VTHD={vthd:.1f}% - exceeds {limit}% limit")

    return {
        "risk_score": max_risk,
        "risk_violations": violations,
    }

def score_protection_coordination(result: dict[str, Any]) -> dict[str, Any]:
    """Score a protection coordination result."""
    coordinated = result.get("all_coordinated", False)
    if not coordinated:
        return {
            "risk_score": "critical",
            "risk_violations": ["Protection coordination FAILED - relays are NOT coordinated"],
        }
    return {
        "risk_score": "low",
        "risk_violations": [],
    }

STUDY_SCORERS = {
    "load_flow": score_load_flow,
    "short_circuit": score_short_circuit,
    "arc_flash": score_arc_flash,
    "harmonic_analysis": score_harmonic,
    "protection_coordination": score_protection_coordination,
}

def compute_risk(study_type: str, result: dict[str, Any]) -> dict[str, Any]:
    """Compute risk score for a study result."""
    scorer = STUDY_SCORERS.get(study_type)
    if scorer is None:
        return {"risk_score": "low", "risk_violations": []}
    return scorer(result)
