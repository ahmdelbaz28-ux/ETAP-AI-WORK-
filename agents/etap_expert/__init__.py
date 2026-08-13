"""
ETAP Expert Skill — sub-modules package.

Splits the monolithic ``agents/etap_expert_agent.py`` into three deep
modules per the C5 refactor:

- ``classifier``: rule-based question classification (COMPLETE/INCOMPLETE/WRONG/ADMS)
- ``simulator``: internal simulation engine (cable sizing, voltage drop, etc.)
- ``formatter``: Format A/B/C/D response templates

The :class:`ETAPExpertAgent` class in ``agents/etap_expert_agent.py``
imports from these sub-modules. All public functions are re-exported here
so tests can import ``from agents.etap_expert import classify, simulate_cable_sizing``.
"""

from agents.etap_expert.classifier import (
    _ADMS_KEYWORDS,
    _INCOMPLETE_PATTERNS,
    _WRONG_STUDY_PATTERNS,
    Classification,
    classify,
)
from agents.etap_expert.formatter import (
    _SEP,
    format_adms,
    format_complete,
    format_incomplete,
    format_wrong,
)
from agents.etap_expert.simulator import (
    _CABLE_RX,
    _NEC_AMPACITY,
    CableSizingResult,
    _select_cable,
    simulate_cable_sizing,
)

__all__ = [
    "Classification",
    "classify",
    "_ADMS_KEYWORDS",
    "_WRONG_STUDY_PATTERNS",
    "_INCOMPLETE_PATTERNS",
    "CableSizingResult",
    "simulate_cable_sizing",
    "_NEC_AMPACITY",
    "_CABLE_RX",
    "_select_cable",
    "format_complete",
    "format_incomplete",
    "format_wrong",
    "format_adms",
    "_SEP",
]
