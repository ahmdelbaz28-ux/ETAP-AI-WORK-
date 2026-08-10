"""
fireai/core/substance_registry.py — Chemical & Substance Safety Registry
========================================================================

Provides physical properties, NFPA 704 ratings, spectral signatures,
and hazardous material classifications by CAS (Chemical Abstracts Service) registry number.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class SubstanceProperties:
    cas_number: str
    name: str
    formula: str = ""
    molecular_weight: float = 0.0
    flash_point_c: Optional[float] = None
    autoignition_temp_c: Optional[float] = None
    flammability_limit_lower_vol_pct: Optional[float] = None
    flammability_limit_upper_vol_pct: Optional[float] = None
    nfpa_health: int = 0
    nfpa_flammability: int = 0
    nfpa_instability: int = 0
    nfpa_special: str = ""
    extra_properties: Dict[str, Any] = field(default_factory=dict)


class SubstanceRegistry:
    """Registry for chemical substances, hazard classifications, and material properties."""

    def __init__(self) -> None:
        self._database: Dict[str, SubstanceProperties] = {}
        self._seed_default_substances()

    def _seed_default_substances(self) -> None:
        """Seed common industrial chemicals and fire safety substances."""
        default_substances = [
            SubstanceProperties(
                cas_number="64-17-5",
                name="Ethanol",
                formula="C2H6O",
                molecular_weight=46.07,
                flash_point_c=13.0,
                autoignition_temp_c=365.0,
                flammability_limit_lower_vol_pct=3.3,
                flammability_limit_upper_vol_pct=19.0,
                nfpa_health=2,
                nfpa_flammability=3,
                nfpa_instability=0,
            ),
            SubstanceProperties(
                cas_number="67-64-1",
                name="Acetone",
                formula="C3H6O",
                molecular_weight=58.08,
                flash_point_c=-20.0,
                autoignition_temp_c=465.0,
                flammability_limit_lower_vol_pct=2.5,
                flammability_limit_upper_vol_pct=12.8,
                nfpa_health=1,
                nfpa_flammability=3,
                nfpa_instability=0,
            ),
            SubstanceProperties(
                cas_number="74-82-8",
                name="Methane",
                formula="CH4",
                molecular_weight=16.04,
                flash_point_c=-188.0,
                autoignition_temp_c=537.0,
                flammability_limit_lower_vol_pct=5.0,
                flammability_limit_upper_vol_pct=15.0,
                nfpa_health=1,
                nfpa_flammability=4,
                nfpa_instability=0,
            ),
            SubstanceProperties(
                cas_number="7782-44-7",
                name="Oxygen",
                formula="O2",
                molecular_weight=32.00,
                nfpa_health=0,
                nfpa_flammability=0,
                nfpa_instability=0,
                nfpa_special="OX",
            ),
        ]
        for sub in default_substances:
            self._database[sub.cas_number] = sub

    def get_by_cas(self, cas_number: str) -> Optional[SubstanceProperties]:
        """Look up a substance by its CAS number."""
        if not cas_number:
            return None
        clean_cas = cas_number.strip()
        return self._database.get(clean_cas)

    def register_substance(self, substance: SubstanceProperties) -> None:
        """Register a new substance in the registry."""
        self._database[substance.cas_number] = substance
