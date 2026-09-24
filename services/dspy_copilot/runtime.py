"""
services/dspy_copilot/runtime.py — Thread-safe runtime engine for DSPy Copilot.

Provides:
- is_enabled(): Feature flag check
- load_compiled_copilot(): Lock-guarded singleton artifact loader
- run_ingest(): Validated SLD ingestion with bounded retry and zero-tolerance for empty systems
- run_diagnose(): Deterministic guardrails-first diagnostics with fallback
- execute_with_copilot(): Thin hook wrapping StudyExecutor
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from api.feature_flags import is_strict_feature_enabled
from core_model.specs import StudyRequest, StudyResult, SystemSpec
from services.dspy_copilot.metrics import check_physics_guards
from services.dspy_copilot.modules import DspyDiagnosticModule, DspySldIngestModule
from services.dspy_copilot.schemas import DiagnosticFinding, DiagnosticOutput, SldIngestOutput

logger = logging.getLogger(__name__)

ARTIFACT_PATH = Path("artifacts/dspy/v1/compiled_dspy_copilot.json")
MAX_INPUT_CHARS = 50000

_COMPILED_LOCK = threading.Lock()
_COMPILED_LOADED = False
_COMPILED_MODULE: Any = None


class DspyIngestError(Exception):
    """Raised when SLD ingestion fails validation, length caps, or parsing."""
    pass


class DspyTransientError(Exception):
    """Typed transient error for LM calls that can be retried (network/timeout).

    Tenacity retries on this type.  modules.py must raise DspyTransientError
    (not ValueError) for TimeoutError and ConnectionError so they reach the
    retry boundary.  After exhaustion, the caller converts to DspyIngestError
    or the diagnostic fallback.
    """
    pass


def is_enabled() -> bool:
    """Check if dspy_copilot feature flag is enabled.

    Uses is_strict_feature_enabled — never returns True for dev/test by default.
    Must be explicitly enabled via FEATURE_FLAG_DSPY_COPILOT=true or stored flag.
    This guarantees the experimental copilot is strict-opt-in in EVERY environment.
    """
    return is_strict_feature_enabled("dspy_copilot", default=False)


def load_compiled_copilot(path: Path = ARTIFACT_PATH) -> Any | None:
    """Thread-safe singleton loader for compiled DSPy copilot program.

    Returns a ready-to-use dspy module via dspy.load, or None if the artifact is missing/corrupted.
    """
    global _COMPILED_LOADED, _COMPILED_MODULE
    with _COMPILED_LOCK:
        if _COMPILED_LOADED:
            return _COMPILED_MODULE
        if not path.exists():
            _COMPILED_LOADED = True
            _COMPILED_MODULE = None
            return None
        try:
            import dspy
            _COMPILED_MODULE = dspy.load(str(path)) if hasattr(dspy, "load") else None
        except Exception as exc:
            logger.warning("Failed to load compiled DSPy copilot from %s: %s", path, exc)
            _COMPILED_MODULE = None
        _COMPILED_LOADED = True
        return _COMPILED_MODULE


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    retry=retry_if_exception_type(DspyTransientError),
    reraise=True,
)
def _invoke_ingest_predictor(module: DspySldIngestModule, sld_notes: str) -> SldIngestOutput:
    """Invoke ingest with typed transient retry (max 2 attempts)."""
    return module.forward(sld_notes=sld_notes)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    retry=retry_if_exception_type(DspyTransientError),
    reraise=True,
)
def _invoke_diagnostic_predictor(
    module: DspyDiagnosticModule, results_json: str
) -> DiagnosticOutput:
    """Invoke diagnostic with typed transient retry (max 2 attempts)."""
    return module.forward(results_json=results_json)


def run_ingest(sld_notes: str) -> SldIngestOutput:
    """Ingest unverified SLD notes into a validated SldIngestOutput.

    Never guesses values. Never returns an empty spec. Raises DspyIngestError on failure.
    """
    # Contract: run_ingest raises DspyIngestError on flag_disabled (fail-closed, never produces executable spec)
    if not is_enabled():
        raise DspyIngestError("flag_disabled")

    if not isinstance(sld_notes, str):
        raise DspyIngestError("sld_notes must be a string")

    # Enforce input length cap
    if len(sld_notes) > MAX_INPUT_CHARS:
        logger.warning("SLD notes exceeded max char cap: len=%d", len(sld_notes))
        raise DspyIngestError("INPUT_TOO_LARGE")

    # Scrubbed logging: length and SHA-256 hash prefix only (zero secret/project leakage)
    digest = hashlib.sha256(sld_notes.encode("utf-8")).hexdigest()[:12]
    logger.info("Executing SLD ingest: len=%d, hash_prefix=%s", len(sld_notes), digest)

    compiled = load_compiled_copilot()
    predictor = compiled if compiled is not None else None

    try:
        module = DspySldIngestModule(predictor=predictor)
        result = _invoke_ingest_predictor(module, sld_notes)
        if len(result.buses) == 0:
            raise DspyIngestError("Ingest produced 0 buses; rejected")
        return result
    except DspyIngestError:
        raise
    except Exception as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        logger.error("SLD ingest failed: %s", exc)
        raise DspyIngestError(f"dspy_ingest_failed: {exc}") from exc


def run_diagnose(
    study_data: dict[str, Any] | StudyResult,
    system_spec: SystemSpec | None = None,
) -> DiagnosticOutput:
    """Synthesize diagnostic findings from deterministic calculation results.

    Guards always run FIRST and win over LLM omissions.
    Returns deterministic fallback output on any AI prediction failure.
    """
    # Contract: run_diagnose returns DiagnosticOutput with code=FLAG_DISABLED on flag_disabled (graceful degrade)
    if not is_enabled():
        return DiagnosticOutput(
            summary="DSPy Copilot is disabled by feature flag.",
            findings=[
                DiagnosticFinding(
                    severity="info",
                    code="FLAG_DISABLED",
                    message="Feature flag 'dspy_copilot' is inactive",
                    bus_id=None,
                    standard_ref=None,
                )
            ],
            recommendations=[],
            citations=[],
        )

    # 1. First validate StudyResult input
    try:
        if isinstance(study_data, dict):
            validated_result = StudyResult.model_validate(study_data)
        elif isinstance(study_data, StudyResult):
            validated_result = study_data
        else:
            raise ValueError(f"Expected dict or StudyResult, got {type(study_data)}")
    except Exception as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        logger.error("Failed validating study_data in run_diagnose: %s", exc)
        return DiagnosticOutput(
            summary="Diagnostic failed due to invalid study_data schema.",
            findings=[
                DiagnosticFinding(
                    severity="info",
                    code="FALLBACK",
                    message=f"Validation error: {exc}",
                    bus_id=None,
                    standard_ref=None,
                )
            ],
            recommendations=[],
            citations=[],
        )

    # 2. Compute physics guard findings deterministically FIRST
    guard_findings = check_physics_guards(system_spec=system_spec, study_data=validated_result)

    # 3. Serialize results to JSON for diagnostic LLM
    try:
        results_json = validated_result.model_dump_json()
    except Exception:
        results_json = json.dumps(validated_result.data or validated_result.results or {})

    # Check input length cap
    if len(results_json) > MAX_INPUT_CHARS:
        logger.warning("Diagnostic input JSON exceeded cap: len=%d", len(results_json))
        return DiagnosticOutput(
            summary="Study results payload exceeded maximum allowed size (INPUT_TOO_LARGE).",
            findings=guard_findings or [
                DiagnosticFinding(
                    severity="info",
                    code="INPUT_TOO_LARGE",
                    message="Payload exceeds 50000 character limit",
                    bus_id=None,
                    standard_ref=None,
                )
            ],
            recommendations=[],
            citations=[],
        )

    # 4. Attempt LLM enhancement (with typed transient retry)
    try:
        module = DspyDiagnosticModule()
        ai_output = _invoke_diagnostic_predictor(module, results_json)

        # Merge findings: deterministic guards ALWAYS win and cannot be downgraded by LLM (FIX-1)
        guard_codes = {gf.code for gf in guard_findings}
        merged_findings = list(guard_findings)
        for af in ai_output.findings:
            if af.code not in guard_codes:
                merged_findings.append(af)
            else:
                logger.debug("Dropped LLM finding colliding with guard code=%s", af.code)

        return DiagnosticOutput(
            summary=ai_output.summary[:2000],
            findings=merged_findings,
            recommendations=ai_output.recommendations,
            citations=ai_output.citations,
        )
    except Exception as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        logger.warning("AI Diagnostic enhancement failed; falling back to deterministic guards: %s", exc)
        # Deterministic fallback
        findings = guard_findings if guard_findings else [
            DiagnosticFinding(
                severity="info",
                code="FALLBACK",
                message="Deterministic fallback invoked (AI copilot unavailable or failed)",
                bus_id=None,
                standard_ref=None,
            )
        ]
        return DiagnosticOutput(
            summary="Deterministic study results evaluated. AI narrative unavailable.",
            findings=findings,
            recommendations=["Verify equipment ratings against catalog parameters manually."],
            citations=["IEEE 3002.7-2018"],
        )


async def execute_with_copilot(
    executor: Any,
    payload: StudyRequest,
    sld_notes: str | None = None,
    trace_id: str = "unknown",
    human_approved: bool = False,
) -> StudyResult:
    """Thin wrapper around StudyExecutor.execute providing pre-ingest and post-diagnostic hooks.

    Safety contract:
    - Pre-hook: Ingests raw SLD notes into SystemSpec PROPOSAL only. Requires
      human_approved=True to use that proposal in execution — never automatic.
    - Post-hook: Adds 'dspy_diagnostic' key to StudyResult.data.
    - Blocking LM calls are run through asyncio.to_thread to avoid event-loop blocking.
    """
    if not is_enabled():
        # Copilot disabled: run standard execution
        return await executor.execute(payload, trace_id=trace_id)

    # 1. Pre-hook: SLD ingestion if notes provided
    if sld_notes:
        # Run blocking ingest in a thread to avoid blocking the event loop
        ingest_res = await asyncio.to_thread(run_ingest, sld_notes)
        if len(ingest_res.buses) == 0:
            raise DspyIngestError("Cannot execute study: ingested system contains 0 buses")

        # SAFETY: LM ingest output is a PROPOSAL only.
        # It must NOT be automatically executed without explicit human confirmation.
        if not human_approved:
            raise DspyIngestError(
                "LM-ingested topology requires explicit human approval before execution. "
                "Set human_approved=True only after a qualified engineer has reviewed "
                "the SldIngestOutput proposal."
            )

        # Build SystemSpec only after human approval
        system_spec = SystemSpec(
            buses=ingest_res.buses,
            lines=ingest_res.lines,
            loads=ingest_res.loads,
            transformers=ingest_res.transformers,
        )
        payload.system = system_spec

    # 2. Deterministic Execution
    result = await executor.execute(payload, trace_id=trace_id)

    # 3. Post-hook: Diagnostic synthesis (run in thread — LM call is blocking)
    sys_spec = payload.system if isinstance(payload.system, SystemSpec) else None
    diagnostic = await asyncio.to_thread(run_diagnose, result, sys_spec)

    # Additive key only: never overwrite physics fields
    if not isinstance(result.data, dict):
        result.data = {}
    result.data["dspy_diagnostic"] = diagnostic.model_dump()

    # Extend warnings ONLY with violation codes prefixed by [copilot]
    for finding in diagnostic.findings:
        if finding.severity == "violation":
            result.warnings.append(f"[copilot] {finding.code}: {finding.message}")

    return result
