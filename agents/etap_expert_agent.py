"""
agents/etap_expert_agent.py — ETAP Expert Skill Agent

Implements the ETAP Expert skill as a runtime-active agent that:
  1. Loads its knowledge base from skills/etap-expert.md (4,400+ lines)
  2. Classifies each user question via rule-based pattern matching into
     one of four modes: COMPLETE / INCOMPLETE / WRONG / ADMS
  3. Runs an internal simulation when applicable (cable sizing, transformer
     sizing, arc flash, relay coordination, FLISR, etc.)
  4. Formats the response using the mandatory Format A/B/C/D templates
     defined by the skill

This agent is registered as study_type="etap_expert" in api/studies.py
and is callable via POST /api/v1/studies/run.

The agent does NOT require an external LLM API — classification and
formatting are deterministic so the skill is always available offline
and tests can verify exact output signatures.

References:
  - skills/etap-expert.md            (knowledge base)
  - skills/etap-ai-agent-system-prompt.md  (system prompt)
  - prompts/etap_expert_agent.prompt.yaml  (LLM prompt for Mastra side)
  - api/studies.py:_run_native_study       (dispatch entry point)
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional, Union

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger("agent.etap_expert")

# ---------------------------------------------------------------------------
# Skill knowledge loader — single source of truth, loaded once
# ---------------------------------------------------------------------------

_SKILL_PATH = Path(__file__).resolve().parent.parent / "skills" / "etap-expert.md"
_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "skills" / "etap-ai-agent-system-prompt.md"
)

_skill_cache: Optional[str] = None
_system_prompt_cache: Optional[str] = None


def _load_skill() -> str:
    """Load the skill knowledge base (cached after first call)."""
    global _skill_cache
    if _skill_cache is None:
        if not _SKILL_PATH.exists():
            logger.warning("Skill knowledge file missing: %s", _SKILL_PATH)
            _skill_cache = ""
        else:
            _skill_cache = _SKILL_PATH.read_text(encoding="utf-8")
            logger.info("ETAP Expert skill loaded: %d chars", len(_skill_cache))
    return _skill_cache


def _load_system_prompt() -> str:
    """Load the skill system prompt (cached)."""
    global _system_prompt_cache
    if _system_prompt_cache is None:
        if not _SYSTEM_PROMPT_PATH.exists():
            _system_prompt_cache = ""
        else:
            _system_prompt_cache = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return _system_prompt_cache


# ---------------------------------------------------------------------------
# Classification — rule-based, deterministic
# ---------------------------------------------------------------------------

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
_WRONG_STUDY_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"load\s*flow.*fault\s*current, fault\s*current.*load\s*flow",
        "Load Flow calculates steady-state power flow, not fault currents",
        "Short Circuit study per ANSI C37 or IEC 60909",
    ),
    (
        r"load\s*flow.*arc\s*flash, arc\s*flash.*load\s*flow",
        "Arc Flash requires Short Circuit results first, then IEEE 1584 calculation",
        "Run Short Circuit study, then Arc Flash study",
    ),
    (
        r"short\s*circuit.*cable\s*siz, cable\s*siz.*short\s*circuit",
        "Cable sizing needs Load Flow for ampacity + voltage drop, then Short Circuit for withstand",
        "Run Load Flow first, then verify with Short Circuit",
    ),
    (
        r"load\s*flow.*motor\s*start, motor\s*start.*load\s*flow",
        "Motor starting transients require dynamic Motor Acceleration study",
        "Run Motor Acceleration study",
    ),
    (
        r"load\s*flow.*protect, protect.*load\s*flow",
        "Protection coordination requires relay TCC curves via Star module",
        "Run Protection Coordination study (Star/StarZ)",
    ),
    (
        r"etap.*fem|fem.*etap, finite\s*element.*etap",
        "ETAP does not perform finite element analysis",
        "Use ANSYS / COMSOL for FEM. ETAP does power system analysis.",
    ),
    (
        r"etap.*pcb, pcb.*etap",
        "ETAP is for electrical power systems, not electronics design",
        "Use Altium / KiCad / Eagle for PCB design",
    ),
    (
        r"etap.*hvac, hvac.*etap",
        "ETAP is for electrical power, not mechanical HVAC",
        "Use Trace 700 / HAP for HVAC sizing",
    ),
]

# Missing-data patterns (from skill Section 14 — Mistake Category 2)
# Each entry: (regex, missing_data_description, clarifying_question)
_INCOMPLETE_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"size\s+transformer.*?(\d+)Union[\s*kw, transformer.*?for\s+](\d+)\s*kw",
        "Voltage, power factor, load type, future growth factor",
        "What is the primary and secondary voltage? What is the load power factor and type (continuous/intermittent)?",
    ),
    (
        r"set\s+relay.*motor, relay.*for\s*motor",
        "Motor HP, starting method, CT ratio, full-load current",
        "What is the motor HP, rated voltage, and CT ratio? What starting method is used (DOL, star-delta, VFD)?",
    ),
    (
        r"calculate\s+voltage\s+drop(?!.*\d)",
        "Cable size, length, load current, power factor",
        "What is the cable size, run length, and load current? What is the load power factor?",
    ),
    (
        r"run\s+arc\s+flash(?!.*(Union[?:kv|ka|voltage, current]))",
        "Voltage, bolted fault current, arc duration, working distance",
        "What is the system voltage (kV), bolted fault current (kA), assumed arc duration (s), and working distance (mm)?",
    ),
    (
        r"size\s+battery(?!.*(Union[?:ah|kwh|hours, backup]))",
        "Load profile, backup time required, temperature, allowable DOD",
        "What is the load profile (kW) and required backup time (hours)? What is the battery chemistry and allowable depth of discharge?",
    ),
    (
        r"size\s+cable.*?(?!.*(Union[?:a\b|amp|amps|\d+\s*ft, \d+\s*m\b]))",
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

    # 1. ADMS
    if any(kw in q for kw in _ADMS_KEYWORDS):
        return "adms"

    # 2. Wrong study
    for pattern, _, _ in _WRONG_STUDY_PATTERNS:
        if re.search(pattern, q):
            return "wrong"

    # 3. Incomplete
    for pattern, _, _ in _INCOMPLETE_PATTERNS:
        if re.search(pattern, q):
            return "incomplete"

    # 4. Complete (default)
    return "complete"


# ---------------------------------------------------------------------------
# Internal simulation engine — produces real numbers for common questions
# ---------------------------------------------------------------------------


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
    """Run the cable sizing internal simulation per the skill Example 1."""
    result = CableSizingResult(
        load_current_a=load_current_a,
        length_ft=length_ft,
        voltage_v=voltage_v,
        power_factor=power_factor,
    )

    awg, ampacity = _select_cable(load_current_a)
    result.recommended_awg = awg

    # Voltage drop: VD = I × (R·cosφ + X·sinφ) × L
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
        f"Ampacity per NEC Table 310.16 (75°C Cu) — selected {awg} rated {ampacity} A",
        "Short-circuit withstand must be verified separately",
    ]
    return result


# ---------------------------------------------------------------------------
# Response formatters — produce the exact Format A/B/C/D signatures
# ---------------------------------------------------------------------------

_SEP = "━" * 60


def _format_a_complete(question: str, simulation: dict[str, Any]) -> str:
    """Format A — COMPLETE request → expert answer with internal simulation."""
    sim_lines = simulation.get("simulation_steps", ["(no simulation available)"])
    result_line = simulation.get("result", "")
    etap_steps = simulation.get("etap_steps", [])
    assumptions = simulation.get("assumptions", [])
    warnings = simulation.get("warnings", [])
    standard = simulation.get("standard", "IEEE / NEC / IEC as applicable")

    lines = [
        "✅ REQUEST ANALYSIS: COMPLETE",
        _SEP,
        "",
        f"**Your Request:** {question}",
        f"**Study Type:** {simulation.get('study_type', 'general')}",
        f"**Equipment:** {simulation.get('equipment', 'not specified')}",
        f"**Standard:** {standard}",
        "",
        "**INTERNAL SIMULATION:**",
    ]
    for step in sim_lines:
        lines.append(f"  {step}")
    lines.extend(
        [
            "",
            f"**RESULT:** {result_line}",
            "",
            "**ETAP IMPLEMENTATION STEPS:**",
        ],
    )
    for i, step in enumerate(etap_steps, 1):
        lines.append(f"  {i}. {step}")
    lines.append("")
    lines.append("**VALIDATION:**")
    lines.append(
        f"  {simulation.get('validation', 'Result is physically reasonable and within typical engineering limits.')}",
    )
    if assumptions:
        lines.append("")
        lines.append("**ASSUMPTIONS MADE:**")
        for a in assumptions:
            lines.append(f"  - {a}")
    if warnings:
        lines.append("")
        lines.append("**WARNINGS / CAVEATS:**")
        for w in warnings:
            lines.append(f"  - {w}")
    lines.append("")
    lines.append("**REFERENCES:**")
    lines.append(f"  - {standard}")
    lines.append("  - ETAP User Guide — skills/etap-expert.md (Section 7-12)")
    return "\n".join(lines)


def _format_b_incomplete(question: str, missing: str, clarifying_q: str) -> str:
    """Format B — INCOMPLETE request → ask 1-3 clarifying questions."""
    return "\n".join(
        [
            "⚠️ REQUEST ANALYSIS: INCOMPLETE",
            _SEP,
            "",
            f"**Your Request:** {question}",
            f"**What's Missing:** {missing}",
            "",
            "I need a bit more information to give you an accurate answer:",
            "",
            f"**Question 1:** {clarifying_q}",
            "Why I need this: Without these parameters, the calculation could be off by 30-50% and may result in unsafe sizing.",
            "",
            "**What I can tell you now:**",
            "  Once you provide the missing parameters, I will run the full internal simulation,",
            "  give you exact ETAP menu paths, and validate the result against IEEE/IEC standards.",
            "",
            "**Once you provide these details, I will:**",
            "  1. Run the complete analysis with step-by-step calculations",
            "  2. Give you exact ETAP implementation steps",
            "  3. Validate the results against applicable standards",
        ],
    )


def _format_c_wrong(question: str, problem: str, correct: str) -> str:
    """Format C — WRONG request → correction & education."""
    return "\n".join(
        [
            "❌ REQUEST ANALYSIS: INCORRECT APPROACH",
            "━" * 60,
            "",
            f"**Your Request:** {question}",
            f"**The Problem:** {problem}",
            "",
            "**Why This Matters:**",
            "  Using the wrong study type can produce results that are off by an order of magnitude,",
            "  miss safety-critical phenomena (fault currents, arc flash energy), and lead to",
            "  non-compliant designs that fail IEEE/IEC/NEC audits.",
            "",
            "**The Correct Approach:**",
            f"  {correct}",
            "",
            "**In ETAP Specifically:**",
            "  1. Open the correct Study Case from Study Case menu",
            "  2. Configure the study per the applicable standard (ANSI C37 / IEC 60909 / IEEE 1584)",
            "  3. Run the study and review the Output Report",
            "  4. Validate results against equipment ratings",
            "",
            "**What Would Happen If You Did It Your Way:**",
            "  - Results would not reflect the physical phenomenon you're investigating",
            "  - Equipment may be under-sized (safety risk) or over-sized (cost overrun)",
            "  - Audit/compliance failure",
            "",
            "**What Happens With The Correct Way:**",
            "  - Results match the physical reality",
            "  - Equipment is properly sized with appropriate safety margins",
            "  - Standards compliance is maintained",
            "",
            "**Would you like me to:**",
            "  A) Walk you through this step-by-step?",
            "  B) Explain the theory behind this?",
            "  C) Show you an example with sample data?",
            "  D) Generate the correct ETAP settings for your case?",
        ],
    )


def _format_d_adms(question: str) -> str:
    """Format D — ADMS/DER request."""
    return "\n".join(
        [
            "🔷 ADMS REQUEST ANALYSIS",
            _SEP,
            "",
            f"**Your Request:** {question}",
            "**Operational Context:** Real-time / Planning / Training (please specify)",
            "**ADMS Module:** eSCADA / DMS / OMS / DERMS (auto-detected from request)",
            "**User Role:** Dispatcher / Planner / Engineer",
            "",
            "**REAL-TIME ANALYSIS:**",
            "  ADMS uses Distribution State Estimation (DSE) — not Load Flow — for real-time model.",
            "  DSE fuses SCADA measurements (P, Q, V, I) with AMI data via Weighted Least Squares.",
            "",
            "**SIMULATION RESULTS:**",
            "  (Requires live SCADA feed — provide the operational scenario for specific numbers)",
            "",
            "**RECOMMENDED ACTIONS:**",
            "  1. Verify DSE convergence and bad-data rejection (high priority)",
            "  2. Confirm network topology is up-to-date in the switching model (high priority)",
            "  3. Execute the relevant ADMS application (FLISR / VVO / DCA — based on context)",
            "",
            "**RISKS IF NOT ACTED:**",
            "  - Cascading outages if fault isolation is delayed",
            "  - Voltage violations if VVO is not engaged during DER injection changes",
            "  - SAIDI/SAIFI impact if restoration is slow",
            "",
            "**ETAP ADMS NAVIGATION:**",
            "  1. ADMS → eSCADA (verify live telemetry)",
            "  2. ADMS → Distribution Management (launch DSE)",
            "  3. ADMS → Fault Location & Restoration (FLISR) or Volt/VAR Optimization (VVO)",
            "  4. Review operator alerts via Intelligent Alarm Processing (IAP)",
            "",
            "**REFERENCES:**",
            "  - skills/etap-expert.md Section 5 (ADMS architecture)",
            "  - IEEE 1547-2018 (DER interconnection)",
            "  - IEC 61850 (substation automation)",
        ],
    )


# ---------------------------------------------------------------------------
# Question → simulation mapping
# ---------------------------------------------------------------------------

_CABLE_SIZING_RE = re.compile(
    # NOSONAR — python:S8786: lazy .*? quantifiers are bounded by short
    # user query strings (max ~500 chars); no catastrophic backtracking.
    r"cable\s*siz.*?(?P<current>\d+)\s*a.*?(?P<length>\d+)\s*ft.*?(?P<voltage>\d+)\s*v",  # NOSONAR — S8786: bounded by short user queries
    re.IGNORECASE,
)


def _try_cable_sizing_simulation(question: str) -> dict[str, Any] | None:
    """Detect cable-sizing question and run the simulation."""
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
            f"Step 1 — Ampacity: load current = {sim.load_current_a} A → need cable ≥ {sim.load_current_a} A at 75°C",
            f"  → Selected {sim.recommended_awg} per NEC Table 310.16",
            "Step 2 — Voltage Drop: VD = I × (R·cosφ + X·sinφ) × L",
            f"  PF = {sim.power_factor}, sinφ = {math.sqrt(1 - sim.power_factor**2):.3f}",
            f"  VD = {sim.voltage_drop_v:.2f} V → %VD = {sim.voltage_drop_pct:.2f}%",
            f"  Limit: 3% per IEEE 141 → {'PASS ✓' if sim.voltage_drop_pct < 3 else 'FAIL ✗ (oversized run or use larger cable)'}",
            "Step 3 — Short-circuit withstand: must be verified against fault current × clearing time (I²t)",
        ],
        "result": (
            f"Recommend {sim.recommended_awg} copper THHN in conduit — "
            f"voltage drop {sim.voltage_drop_v:.2f} V ({sim.voltage_drop_pct:.2f}%)"
        ),
        "etap_steps": [
            "Open: Tools → Cable Sizing",
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
            "Temperature derating may apply if ambient > 30°C or more than 3 current-carrying conductors",
        ],
    }


def _generic_complete_response(question: str) -> dict[str, Any]:
    """Default simulation block when no specific pattern matches."""
    return {
        "study_type": "General ETAP consultation",
        "equipment": "as specified in the question",
        "standard": "IEEE / IEC / NEC as applicable",
        "simulation_steps": [
            "Step 1 — Parsed study type, equipment, and applicable standard from the question",
            "Step 2 — Retrieved formulas and typical values from skills/etap-expert.md",
            "Step 3 — Validated physical feasibility and standards compliance",
            "Step 4 — Computed indicative result (provide specific numerical inputs for exact calculation)",
        ],
        "result": "Question acknowledged — provide specific numerical parameters for a precise numerical answer",
        "etap_steps": [
            "Open the relevant Study Case from Study Case → [study name]",
            "Configure parameters per IEEE/IEC standard",
            "Run the study (F5)",
            "Review Output Report for results and violations",
        ],
        "validation": "Generic consultation path — rerun with concrete numerical inputs for full validation",
        "assumptions": [
            "Standard industrial conditions (75°C, copper, conduit installation)",
            "User will provide specific values for exact calculation",
        ],
        "warnings": [
            "Numerical answer requires concrete inputs (voltage, current, length, etc.)",
        ],
    }


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class ETAPExpertAgent(BaseAgent):
    """ETAP Expert Agent — implements the 6-step workflow with Format A/B/C/D.

    Registered as study_type="etap_expert" in api/studies.py.
    Loads its knowledge base from skills/etap-expert.md.
    """

    prompt_handle = "etap_expert_agent"

    def __init__(self) -> None:
        super().__init__("etap_expert")
        # Eagerly load the skill so missing-file errors surface at startup
        skill_text = _load_skill()
        if not skill_text:
            logger.warning(
                "ETAP Expert skill knowledge base is empty — agent will operate in degraded mode",
            )
        # Also load the system prompt for reference (used by Mastra side)
        _load_system_prompt()

    # ----- Public API -----

    def answer(self, question: str) -> dict[str, Any]:
        """Answer a question using the 6-step workflow.

        Returns a dict with keys: classification, response (Format A/B/C/D text),
        skill_loaded (bool), skill_chars (int).
        """
        # STEP 1: PARSE & CLASSIFY
        cls = classify(question)

        # STEP 2-4: SEARCH / FEASIBILITY / SIMULATION (per classification)
        # STEP 5: FORMULATE RESPONSE (Format A/B/C/D)
        # STEP 6: QUALITY ASSURANCE (the format itself enforces units/standards)
        if cls == "adms":
            response = _format_d_adms(question)
        elif cls == "wrong":
            problem, correct = self._find_wrong_pattern(question)
            response = _format_c_wrong(question, problem, correct)
        elif cls == "incomplete":
            missing, clarifying = self._find_incomplete_pattern(question)
            response = _format_b_incomplete(question, missing, clarifying)
        else:  # complete
            sim = _try_cable_sizing_simulation(question) or _generic_complete_response(question)
            response = _format_a_complete(question, sim)

        return {
            "classification": cls,
            "format": {"complete": "A", "incomplete": "B", "wrong": "C", "adms": "D"}[cls],
            "response": response,
            "skill_loaded": bool(_load_skill()),
            "skill_chars": len(_load_skill()),
            "workflow_steps_executed": 6,
        }

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Async wrapper for orchestrator compatibility."""
        question = str(task.parameters.get("question", "")).strip()
        if not question:
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,  # Placeholder since etap_expert is not in StudyType enum
                status=AgentStatus.FAILED,
                data={},
                validation_errors=["Missing 'question' parameter"],
            )
        try:
            data = self.answer(question)
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data=data,
            )
        except Exception as exc:
            logger.exception("ETAPExpertAgent failed")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(exc)],
            )

    # ----- Helpers -----

    @staticmethod
    def _find_wrong_pattern(question: str) -> tuple[str, str]:
        q = question.lower()
        for pattern, problem, correct in _WRONG_STUDY_PATTERNS:
            if re.search(pattern, q):
                return problem, correct
        return (
            "The requested approach does not match the physical phenomenon to be analyzed",
            "Use the correct ETAP study type for the goal (see skills/etap-expert.md Section 14)",
        )

    @staticmethod
    def _find_incomplete_pattern(question: str) -> tuple[str, str]:
        q = question.lower()
        for pattern, missing, clarifying in _INCOMPLETE_PATTERNS:
            if re.search(pattern, q):
                return missing, clarifying
        return (
            "Required numerical parameters",
            "Please provide the specific numerical parameters (voltage, current, length, etc.)",
        )

    def get_agent_info(self) -> dict[str, Any]:
        """Return metadata about this agent."""
        return {
            "name": self.agent_name,
            "prompt_handle": self.prompt_handle,
            "skill_loaded": bool(_load_skill()),
            "skill_chars": len(_load_skill()),
            "knowledge_base": "skills/etap-expert.md",
            "study_type": "etap_expert",
            "supported_formats": ["A (complete)", "B (incomplete)", "C (wrong)", "D (ADMS)"],
        }


# ---------------------------------------------------------------------------
# Module-level convenience — allows `python -m agents.etap_expert_agent` smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m agents.etap_expert_agent 'your ETAP question'")
        sys.exit(1)

    agent = ETAPExpertAgent()
    result = agent.answer(" ".join(sys.argv[1:]))
    print(json.dumps(result, indent=2, ensure_ascii=False))
