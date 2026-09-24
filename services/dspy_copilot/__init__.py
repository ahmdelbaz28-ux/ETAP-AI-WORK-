"""
services/dspy_copilot — DSPy Copilot Module for AhmedETAP.

Provides pre-processor (SLD Ingestion) and post-processor (Engineering Diagnostic Copilot)
around AhmedETAP's deterministic physics engines. Does not modify calculation engines or solvers.
"""

from __future__ import annotations

from services.dspy_copilot.metrics import check_physics_guards
from services.dspy_copilot.modules import DspyDiagnosticModule, DspySldIngestModule
from services.dspy_copilot.runtime import is_enabled, load_compiled_copilot
from services.dspy_copilot.schemas import validate_ingest

__all__ = [
    "DspySldIngestModule",
    "DspyDiagnosticModule",
    "validate_ingest",
    "check_physics_guards",
    "load_compiled_copilot",
    "is_enabled",
]
