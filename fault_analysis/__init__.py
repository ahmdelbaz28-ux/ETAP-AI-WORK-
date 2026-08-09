"""Fault Analysis - Short-circuit and arc-flash analysis engine.

Provides fault analysis capabilities including IEC 60909 short-circuit
calculations, IEEE 1584 arc-flash hazard analysis, and harmonic analysis
for electrical power systems.
"""

from fault_analysis.arc_flash_calc import calculate_arc_flash
from fault_analysis.arc_flash_engine import (
    ArcFlashEngine,
    ArcFlashResult,
    ElectrodeConfig,
    EnclosureType,
)
from fault_analysis.fault import FaultAnalyzer
from fault_analysis.harmonic_analysis import (
    HarmonicAnalysisEngine,
    HarmonicAnalysisResult,
    HarmonicResult,
    HarmonicSource,
    HarmonicStandard,
)
from fault_analysis.iec60909_engine import (
    FaultType,
    IEC60909Engine,
    ShortCircuitResult,
    VoltageFactorC,
)
from fault_analysis.ieee1584_database import (
    ElectrodeConfig as IEEE1584ElectrodeConfig,
)
from fault_analysis.ieee1584_database import (
    EnclosureType as IEEE1584EnclosureType,
)
from fault_analysis.ieee1584_database import (
    IEEE1584Database,
    IEEE1584Result,
)

__all__ = [
    "FaultAnalyzer",
    # Short-circuit
    "IEC60909Engine",
    "FaultType",
    "ShortCircuitResult",
    "VoltageFactorC",
    # Arc flash
    "ArcFlashEngine",
    "ArcFlashResult",
    "ElectrodeConfig",
    "EnclosureType",
    "calculate_arc_flash",
    # IEEE 1584
    "IEEE1584Database",
    "IEEE1584Result",
    "IEEE1584ElectrodeConfig",
    "IEEE1584EnclosureType",
    # Harmonics
    "HarmonicAnalysisEngine",
    "HarmonicStandard",
    "HarmonicSource",
    "HarmonicResult",
    "HarmonicAnalysisResult",
]
