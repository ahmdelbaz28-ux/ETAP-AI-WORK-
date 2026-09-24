"""
services/dspy_copilot/modules.py — DSPy Modules for SLD Ingestion and Diagnostics.

Defines DspySldIngestModule and DspyDiagnosticModule with lazy dspy imports,
JSONAdapter integration, bounded LM timeout (timeout=30s) and token budget (max_tokens=4096),
and strict two-tier validation:
1. Structural JSON generation via DSPy adapter
2. Strict runtime schema validation via Pydantic v2
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from services.dspy_copilot.schemas import DiagnosticOutput, SldIngestOutput
from services.dspy_copilot.signatures import DiagnosticSignature, SldIngestSignature

logger = logging.getLogger(__name__)

try:
    import dspy
    _BaseModule = dspy.Module
except ImportError:  # pragma: no cover
    class _BaseModule:  # type: ignore[no-redef]
        """Stub module base class when dspy is not installed."""
        pass


class DspySldIngestModule(_BaseModule):
    """DSPy module for translating unverified SLD notes into validated SldIngestOutput."""

    def __init__(self, predictor: Any = None):
        super().__init__()
        if predictor is not None:
            self.prog = predictor
        else:
            try:
                import dspy
            except ImportError as err:
                raise RuntimeError("dspy is not installed. DSPy Copilot requires dspy-ai.") from err

            adapter = getattr(dspy, "JSONAdapter", None)
            try:
                if adapter:
                    dspy.settings.configure(adapter=adapter(), timeout=30, max_tokens=4096)
                else:
                    dspy.settings.configure(timeout=30, max_tokens=4096)
            except Exception as exc:
                logger.warning("dspy.settings.configure(timeout=30, max_tokens=4096) failed: %s", exc)
            self.prog = dspy.Predict(SldIngestSignature)

    def forward(self, sld_notes: str) -> SldIngestOutput:
        """Run SLD ingestion through predictor and validate output with Pydantic."""
        try:
            prediction = self.prog(sld_notes=sld_notes)
        except Exception as exc:
            logger.error("DSPy ingest prediction failed: %s", exc)
            raise ValueError(f"dspy_ingest_prediction_failed: {exc}") from exc

        # Extract payload_json from prediction
        payload_raw = getattr(prediction, "payload_json", None)
        if payload_raw is None and isinstance(prediction, dict):
            payload_raw = prediction.get("payload_json")

        if not payload_raw or not isinstance(payload_raw, (str, dict)):
            raise ValueError("dspy_ingest_validation_failed: missing payload_json in response")

        try:
            data = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
            output = SldIngestOutput.model_validate(data)
            if len(output.buses) == 0:
                raise ValueError("dspy_ingest_validation_failed: 0 buses returned")
            return output
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as val_err:
            logger.warning("SldIngestOutput validation failed: %s", val_err)
            raise ValueError(f"dspy_ingest_validation_failed: {val_err}") from val_err


class DspyDiagnosticModule(_BaseModule):
    """DSPy module for synthesizing diagnostic reports from deterministic study results."""

    def __init__(self, predictor: Any = None):
        super().__init__()
        if predictor is not None:
            self.prog = predictor
        else:
            try:
                import dspy
            except ImportError as err:
                raise RuntimeError("dspy is not installed. DSPy Copilot requires dspy-ai.") from err

            adapter = getattr(dspy, "JSONAdapter", None)
            try:
                if adapter:
                    dspy.settings.configure(adapter=adapter(), timeout=30, max_tokens=4096)
                else:
                    dspy.settings.configure(timeout=30, max_tokens=4096)
            except Exception as exc:
                logger.warning("dspy.settings.configure(timeout=30, max_tokens=4096) failed: %s", exc)
            self.prog = dspy.ChainOfThought(DiagnosticSignature)

    def forward(self, results_json: str) -> DiagnosticOutput:
        """Synthesize diagnostic report from study results JSON and validate output."""
        try:
            prediction = self.prog(results_json=results_json)
        except Exception as exc:
            logger.error("DSPy diagnostic prediction failed: %s", exc)
            raise ValueError(f"dspy_diagnostic_prediction_failed: {exc}") from exc

        report_raw = getattr(prediction, "report_json", None)
        if report_raw is None and isinstance(prediction, dict):
            report_raw = prediction.get("report_json")

        if not report_raw or not isinstance(report_raw, (str, dict)):
            raise ValueError("dspy_diagnostic_validation_failed: missing report_json in response")

        try:
            data = json.loads(report_raw) if isinstance(report_raw, str) else report_raw
            return DiagnosticOutput.model_validate(data)
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as val_err:
            logger.warning("DiagnosticOutput validation failed: %s", val_err)
            raise ValueError(f"dspy_diagnostic_validation_failed: {val_err}") from val_err
