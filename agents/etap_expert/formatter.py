"""
ETAP Expert — Response Formatter module.

Produces the mandatory Format A/B/C/D response templates defined by the
ETAP Expert skill (skills/etap-expert.md Section 6).

- Format A: COMPLETE request → expert answer with internal simulation
- Format B: INCOMPLETE request → ask 1-3 clarifying questions
- Format C: WRONG request → correction & education
- Format D: ADMS/DER request → operational context + actions

This is the C6 refactor extract from ``agents/etap_expert_agent.py``.
"""

from __future__ import annotations

from typing import Any

_SEP = "-" * 60


def format_complete(question: str, simulation: dict[str, Any]) -> str:
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


def format_incomplete(question: str, missing: str, clarifying_q: str) -> str:
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


def format_wrong(question: str, problem: str, correct: str) -> str:
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


def format_adms(question: str) -> str:
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
            "  1. ADMS -> eSCADA (verify live telemetry)",
            "  2. ADMS -> Distribution Management (launch DSE)",
            "  3. ADMS -> Fault Location & Restoration (FLISR) or Volt/VAR Optimization (VVO)",
            "  4. Review operator alerts via Intelligent Alarm Processing (IAP)",
            "",
            "**REFERENCES:**",
            "  - skills/etap-expert.md Section 5 (ADMS architecture)",
            "  - IEEE 1547-2018 (DER interconnection)",
            "  - IEC 61850 (substation automation)",
        ],
    )
