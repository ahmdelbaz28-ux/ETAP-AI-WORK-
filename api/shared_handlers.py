"""
Shared Handlers & Utilities for AhmedETAP
==========================================

Lightweight, dependency-free implementations of common logic used by both
``api/routes.py`` (via its sub-routers) and ``hf-space/app.py``.

Design principles
-----------------
* **No Redis, Celery, or PostgreSQL** — everything works with in-memory
  alternatives or falls back gracefully.
* **Lazy heavy imports** — numpy, engine, and agent modules are imported
  inside functions so that importing this module never pulls in unavailable
  packages on HF Space.
* **Single source of truth** — VERSION, STUDY_TYPES, AGENTS, and other
  constants live here once.
"""

from __future__ import annotations

import hmac
import logging
import os
import time
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from api._messages import MSG_INTERNAL_ERROR, MSG_INVALID_INPUT

logger = logging.getLogger("etap-ai")

# ---------------------------------------------------------------------------
# Constants — single source of truth
# ---------------------------------------------------------------------------

VERSION = "2.1.0"

# NOTE: AGENT_COUNT is computed from len(AGENTS) at the bottom of the AGENTS list
# (see "AGENT_COUNT = len(AGENTS)" below). Do NOT hardcode it here — the previous
# hardcoded value of 23 drifted out of sync with the actual list length.
ETAP_MANUAL_COUNT: int = 35
ZENON_GUIDE_COUNT: int = 4

# Engineering standards supported by the platform — single source of truth.
# Used by build_platform_info() and by the homepage stat card. Adding a new
# standard here automatically updates both places.
#
# Each standard is defined as a module-level constant (SonarCloud S1192:
# string literals should not be duplicated) and aggregated into
# SUPPORTED_STANDARDS below. Importing code should reference these
# constants rather than re-typing the string.
STD_IEEE_3002_7 = "IEEE 3002.7"
STD_IEC_60909 = "IEC 60909"
STD_IEEE_1584 = "IEEE 1584"
STD_IEC_60255 = "IEC 60255"
STD_IEEE_519 = "IEEE 519"
STD_IEC_61850 = "IEC 61850"
STD_IEEE_80 = "IEEE 80"
STD_IEC_60364 = "IEC 60364"
STD_IEEE_399 = "IEEE 399"
STD_IEC_62933 = "IEC 62933"

SUPPORTED_STANDARDS: list[str] = [
    STD_IEEE_3002_7,
    STD_IEC_60909,
    STD_IEEE_1584,
    STD_IEC_60255,
    STD_IEEE_519,
    STD_IEC_61850,
    STD_IEEE_80,
    STD_IEC_60364,
    STD_IEEE_399,
    STD_IEC_62933,
]

START_TIME: float = time.time()
BUILD_TIME: str = datetime.now(UTC).isoformat()

# ---------------------------------------------------------------------------
# Study types — derived canonically from agents.models.StudyType (ADR-0001)
# ---------------------------------------------------------------------------

from agents.models import StudyType

STUDY_TYPES: list[str] = [st.value for st in StudyType] + ["ahmed_etap_orchestration"]

# ---------------------------------------------------------------------------
# Agents list
# ---------------------------------------------------------------------------

AGENTS: list[dict[str, str]] = [
    {
        "id": "load-flow-agent",
        "name": "Load Flow Agent",
        "standard": STD_IEEE_3002_7,
        "status": "active",
    },
    {
        "id": "short-circuit-agent",
        "name": "Short Circuit Agent",
        "standard": STD_IEC_60909,
        "status": "active",
    },
    {
        "id": "arcflash-agent",
        "name": "Arc Flash Agent",
        "standard": STD_IEEE_1584,
        "status": "beta",
    },
    {
        "id": "protection-agent",
        "name": "Protection Agent",
        "standard": STD_IEC_60255,
        "status": "active",
    },
    {
        "id": "motorstarting-agent",
        "name": "Motor Starting Agent",
        "standard": STD_IEEE_399,
        "status": "beta",
    },
    {
        "id": "stability-agent",
        "name": "Stability Agent",
        "standard": STD_IEEE_399,
        "status": "beta",
    },
    {
        "id": "harmonic-agent",
        "name": "Harmonic Analysis Agent",
        "standard": STD_IEEE_519,
        "status": "active",
    },
    {
        "id": "cable-sizing-agent",
        "name": "Cable Sizing Agent",
        "standard": STD_IEC_60364,
        "status": "beta",
    },
    {
        "id": "earth-grid-agent",
        "name": "Earth Grid Agent",
        "standard": STD_IEEE_80,
        "status": "beta",
    },
    {
        "id": "opf-agent",
        "name": "Optimal Power Flow Agent",
        "standard": STD_IEEE_3002_7,
        "status": "active",
    },
    {
        "id": "renewable-agent",
        "name": "Renewable Energy Agent",
        "standard": "IEEE 1547",
        "status": "beta",
    },
    {
        "id": "battery-storage-agent",
        "name": "Battery Storage Agent",
        "standard": STD_IEC_62933,
        "status": "beta",
    },
    {"id": "scada-agent", "name": "SCADA Agent", "standard": STD_IEC_61850, "status": "beta"},
    {
        "id": "digital-twin-agent",
        "name": "Digital Twin Agent",
        "standard": "IEC 61970",
        "status": "beta",
    },
    {
        "id": "predictive-agent",
        "name": "Predictive Maintenance",
        "standard": "ISO 13381",
        "status": "beta",
    },
    {
        "id": "anomaly-agent",
        "name": "Anomaly Detection Agent",
        "standard": "IEEE 1159",
        "status": "beta",
    },
    {
        "id": "coordination-agent",
        "name": "Coordination Agent",
        "standard": STD_IEC_60255,
        "status": "beta",
    },
    {
        "id": "report-agent",
        "name": "Report Generation Agent",
        "standard": STD_IEEE_3002_7,
        "status": "active",
    },
    {
        "id": "validation-agent",
        "name": "Validation Agent",
        "standard": "IEC 60038",
        "status": "active",
    },
    {
        "id": "etap-engineer-agent",
        "name": "ETAP Engineer Agent",
        "standard": "ETAP Manual",
        "status": "active",
    },
    {
        "id": "goal-planner-agent",
        "name": "Goal Planner Agent",
        "standard": "Internal",
        "status": "beta",
    },
    {"id": "weather-agent", "name": "Weather Agent", "standard": "IEC 60721", "status": "beta"},
    {
        "id": "power-system-coordinator",
        "name": "Power System Coordinator",
        "standard": "All",
        "status": "active",
    },
    {
        "id": "etap-expert-agent",
        "name": "ETAP Expert Skill Agent",
        "standard": "IEEE/IEC/NEC/NFPA (all)",
        "status": "active",
        "description": "6-step workflow with Format A/B/C/D responses. Knowledge base: skills/etap-expert.md (4,400+ lines).",
    },
    {
        "id": "etap-gui-agent",
        "name": "ETAP GUI Agent (Computer Use Agent)",
        "standard": "Safety + Audit",
        "status": "active",
        "description": "Computer Use Agent for desktop apps (ETAP, Revit, AutoCAD, SCADA, QGIS, ArcGIS). 4 modes: Analyze/Monitor/Control/Solve. Falls back gracefully on headless servers.",
    },
]

# Single source of truth for the agent count — derived from the list above so
# adding/removing an agent entry automatically updates /health, /api/v1/info,
# and the homepage stat card. Never hardcode this value.
AGENT_COUNT: int = len(AGENTS)

# ---------------------------------------------------------------------------
# Pydantic request models (lightweight — no heavy deps)
# ---------------------------------------------------------------------------


class SharedStudyRequest(BaseModel):
    """Lightweight study request used by both HF Space and main API."""

    study_type: str
    system: dict[str, Any] = {}
    options: dict[str, Any] = {}
    parameters: dict[str, Any] = {}
    use_etap: bool = False


class SharedETAPExpertChatRequest(BaseModel):
    """Request body for ETAP Expert chat."""

    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(alias="message", min_length=1, description="The question to ask")
    context: dict[str, Any] = {}


class SharedETAPGUIChatRequest(BaseModel):
    """Request body for ETAP GUI Agent chat."""

    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(alias="message", min_length=1, description="The question to ask")
    context: dict[str, Any] = {}


class SharedContextRetrieveRequest(BaseModel):
    """Request body for AI Context Engine retrieve endpoint."""

    query: str
    top_k: int = 5
    max_tokens: int = 2000


class SharedImpactAnalysisRequest(BaseModel):
    """Request body for AI Context Engine impact endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    component: str = Field(alias="component_id", description="Component name or ID to analyze")
    max_depth: int = 2


# ---------------------------------------------------------------------------
# Paths that should skip authentication
# ---------------------------------------------------------------------------

PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/",
        "/version",
        "/healthz",
        "/readyz",
        "/health",
        "/ready",
        "/api/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/docs",
        "/api/v1/redoc",
        "/api/v1/openapi.json",
        "/metrics",
        "/prometheus/metrics",
        "/api/v1/csrf/token",
        # Auth endpoints must be public — they ARE the authentication.
        # If these required an API key, no user could ever register or log in.
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/token",
        "/api/v1/auth/refresh",
        "/api/v1/auth/me",  # JWT-protected (not API-key-protected)
    },
)

# ---------------------------------------------------------------------------
# API Key validation
# ---------------------------------------------------------------------------


def verify_api_key(
    request: Request,
    *,
    env_var: str = "HF_API_KEY",
    skip_paths: frozenset[str] | None = None,
) -> None:
    """Validate API key when configured.

    Parameters
    ----------
    request : Request
        The incoming FastAPI request.
    env_var : str
        Environment variable name that holds the expected API key.
        Defaults to ``"HF_API_KEY"`` for HF Space compatibility.
    skip_paths : frozenset[str] | None
        Paths that should bypass auth. Defaults to :data:`PUBLIC_PATHS`.

    Raises
    ------
    HTTPException
        401 if the key is configured but missing / incorrect.
    """
    expected_key = os.environ.get(env_var, "")
    _skip = skip_paths if skip_paths is not None else PUBLIC_PATHS
    if not expected_key:
        # Fail CLOSED by default: an unconfigured key must NOT grant open access to
        # engineering endpoints outside local development. Public/health paths stay exempt.
        _env = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "production")).lower()
        if _env not in ("development", "dev", "local") and request.url.path not in _skip:
            raise HTTPException(status_code=401, detail="API key not configured")
        return  # No key configured → open access ONLY in explicit dev/local
    if request.url.path in _skip:
        return

    # ─── JWT bypass ───────────────────────────────────────────────────────
    # If the request carries a VALID JWT Bearer token, skip the API key
    # check. The frontend (React UI) authenticates users via JWT issued
    # by /api/v1/auth/login — those users should NOT also be required to
    # send an X-API-Key header. Without this bypass, every authenticated
    # UI request to /agents, /reports, /projects, /assets returns 401
    # because the middleware demands X-API-Key even though a valid JWT
    # is present.
    #
    # AUTH CONSOLIDATION 2026-07-26: Added type check (reject refresh tokens)
    # and noted that blacklist check is done by downstream Depends() in route
    # handlers. This middleware is a first-pass gate; the authoritative check
    # happens in ``api.dependencies.get_current_user`` / ``get_api_key``.
    # Note: blacklist check cannot be done here because ``verify_api_key`` is
    # sync and ``_is_token_blacklisted`` is async. The downstream dependency
    # handles the blacklist check for JWT-authenticated requests.
    auth_header = request.headers.get("authorization") or ""
    if auth_header.lower().startswith("bearer "):
        # Validate the JWT here to prevent bypass with any "bearer " string.
        # Import locally to avoid circular imports.
        try:
            from api.dependencies import _validate_jwt_access_token_sync

            token = auth_header[7:].strip()  # Remove "Bearer " prefix
            _validate_jwt_access_token_sync(token, require_sub=False)
            return
        except HTTPException:
            # Invalid/expired JWT or non-access token — fall through to API key check
            pass
        except Exception:
            pass  # SECURITY: Intentional — JWT optional, API key is the fallback

    provided = request.headers.get("x-api-key") or ""
    if not hmac.compare_digest(provided, expected_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# In-memory rate limiter (canonical api._rate_limit.RateLimiter)
# ---------------------------------------------------------------------------

from api._rate_limit import RateLimiter

_RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))
_RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX", "120"))

# Module-level canonical instance
rate_limiter = RateLimiter(max_requests=_RATE_LIMIT_MAX, window_seconds=_RATE_LIMIT_WINDOW)

# ---------------------------------------------------------------------------
# Health / readiness / metrics response builders
# ---------------------------------------------------------------------------


def build_health_response(platform: str = "huggingface-spaces") -> dict[str, Any]:
    """Return a health-status dictionary."""
    uptime = round(time.time() - START_TIME, 2)
    return {
        "success": True,
        "status": "healthy",
        "uptime_seconds": uptime,
        "build_time": BUILD_TIME,
        "version": VERSION,
        "platform": platform,
        "agents": AGENT_COUNT,
        "etap_manuals": ETAP_MANUAL_COUNT,
        "zenon_guides": ZENON_GUIDE_COUNT,
    }


def build_ready_response() -> dict[str, Any]:
    """Return a readiness-status dictionary."""
    return {"status": "ready", "uptime": round(time.time() - START_TIME, 2)}


def build_metrics_response(platform: str = "huggingface-spaces") -> dict[str, Any]:
    """Return a metrics dictionary."""
    return {
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "platform": platform,
        "version": VERSION,
    }


# ---------------------------------------------------------------------------
# Platform info & knowledge-base info builders
# ---------------------------------------------------------------------------


def build_platform_info() -> dict[str, Any]:
    """Return platform metadata."""
    return {
        "name": "AhmedETAP",
        "version": VERSION,
        "description": "Enterprise Engineering Intelligence Platform",
        "author": "Eng. Ahmed Elbaz",
        "standards": SUPPORTED_STANDARDS,
        "agents": AGENT_COUNT,
        "knowledge_base": {
            "etap_manuals": ETAP_MANUAL_COUNT,
            "zenon_guides": ZENON_GUIDE_COUNT,
            "total_chunks": "5000+",
        },
        "endpoints": {
            "docs": "/docs",
            "health": "/healthz",
            "studies": "/api/v1/studies/run",
            "agents": "/api/v1/agents",
        },
    }


def build_knowledge_info() -> dict[str, Any]:
    """Return knowledge-base metadata."""
    return {
        "etap": {
            "manuals": ETAP_MANUAL_COUNT,
            "topics": [
                "AC Networks",
                "Load Flow & Panel",
                "Transformer Sizing",
                "Unbalanced Load Flow",
                "Short Circuit ANSI",
                "Short Circuit IEC",
                "Arc Flash",
                "Motor Acceleration",
                "Parameter Estimation",
                "Transient Stability",
                "Parameter Tuning",
                "UDM",
                "Harmonics",
                "UGS",
                "Cable Pulling",
                "Optimal Power Flow",
                "OCP",
                "Ground Grid",
                "PDE/GIS",
                "DC Load Flow & Short Circuit",
                "BSD",
                "CSD",
                "Reliability Assessment",
                "WTG",
                "Arc Flash Advanced Topics",
                "ETAP ARTTS",
                "Controls",
                "Short Circuit Study",
                "Training (1164 slides)",
                "Renewable Energy",
                "ETAP Solutions Overview",
                "eTrax Rail",
            ],
            "standards": [
                STD_IEEE_3002_7,
                STD_IEC_60909,
                STD_IEEE_1584,
                STD_IEC_60255,
                STD_IEEE_519,
            ],
        },
        "zenon": {
            "guides": ZENON_GUIDE_COUNT,
            "topics": [
                "Zenon SCADA Fundamentals",
                "Zenon Energy Management",
                "Zenon IEC 61850 Module 1",
                "Zenon IEC 61850 Module 2",
            ],
            "standards": [STD_IEC_61850, "IEC 61968", "IEC 61970"],
        },
    }


# ---------------------------------------------------------------------------
# Numpy / engine-result sanitisation
# ---------------------------------------------------------------------------


def sanitize_result(obj: Any) -> Any:
    """Recursively convert numpy types to native Python for JSON serialisation.

    Falls back gracefully if numpy is not installed.
    """
    try:
        import numpy as np  # type: ignore

        if isinstance(obj, dict):
            return {str(k): sanitize_result(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [sanitize_result(x) for x in obj]
        if isinstance(obj, np.ndarray):
            # CRITICAL: .tolist() converts numpy scalars to Python scalars
            # (e.g. numpy.complex128 → complex), but does NOT recurse into
            # dicts-of-complex. We must call sanitize_result on each element
            # to convert complex → {real, imag} for JSON serialisation.
            # Bug #21 root cause: previously returned obj.tolist() directly,
            # leaving complex numbers un-serialised → HTTP 500 from FastAPI
            # jsonable_encoder when returning load_flow results.
            return [sanitize_result(x) for x in obj.tolist()]
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.complexfloating):
            return {"real": float(obj.real), "imag": float(obj.imag)}
        if isinstance(obj, complex):
            return {"real": obj.real, "imag": obj.imag}
    except ImportError:
        pass  # NOSONAR cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)

    if isinstance(obj, dict):
        return {str(k): sanitize_result(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_result(x) for x in obj]
    if isinstance(obj, complex):
        return {"real": obj.real, "imag": obj.imag}
    return obj


# ---------------------------------------------------------------------------
# Study execution (lightweight — no Redis / Celery / cache)
# ---------------------------------------------------------------------------


def run_study_lightweight(  # NOSONAR cognitive complexity; refactoring sprint
    study_type: str,
    system: dict[str, Any],
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Execute an engineering study with **no** external service dependencies.

    This is the lightweight counterpart of the full study runner in
    ``api/studies.py``.  It handles:

    * ``etap_expert`` / ``etap_gui`` — agent-based, no numerical engine needed
    * ``load_flow`` — native engine if available, graceful fallback otherwise
    * All other types — queued response with a helpful note

    Returns
    -------
    dict
        A response payload ready to be returned from a FastAPI endpoint.
    """
    # -- Validate study type ------------------------------------------------
    if study_type not in STUDY_TYPES:
        return {
            "error": f"Unknown study_type '{study_type}'",
            "valid_types": STUDY_TYPES,
            "_status": 400,
        }

    # -- Validate mandatory question for interactive agents -----------------
    if study_type in ("etap_expert", "etap_gui"):
        question = str(parameters.get("question", "")).strip()
        if not question:
            return {
                "error": f"'question' field is required for study_type='{study_type}'",
                "_status": 400,
            }

    # -- Canonical Execution Gateway (Phase 2 Canonical Delegation) ---------
    from services.execution_orchestrator import get_execution_orchestrator
    from services.execution_request import ExecutionRequest
    from services.study_service import _run_async

    req = ExecutionRequest(
        capability_id=study_type,
        tenant_id="hf_space_tenant",
        user_id="service_principal:hf_space",
        user_role="engineer",
        input={"system": system, "parameters": parameters},
        metadata={"deployment": "hf_space", "caller": "run_study_lightweight"},
    )
    orchestrator = get_execution_orchestrator()

    try:
        canonical_res = _run_async(orchestrator.execute(req))
    except Exception as exc:
        logger.exception("HF Space canonical execution failed for %s: %s", study_type, exc)
        return {
            "error": f"Study '{study_type}' encountered an error: {exc}",
            "status": "failed",
            "study_type": study_type,
            "_status": 500,
        }

    ref_prefix = "ETAP-EXPERT" if study_type == "etap_expert" else ("ETAP-GUI" if study_type == "etap_gui" else "STUDY")
    response: dict[str, Any] = {
        "study_type": study_type,
        "reference": f"{ref_prefix}-{int(time.time())}",
    }

    if canonical_res.success:
        response["status"] = "completed"
        response["success"] = True
        response["data"] = sanitize_result(canonical_res.data)
        response["result"] = response["data"]
        return response

    err_msg = canonical_res.errors[0] if canonical_res.errors else "Study execution failed"
    if canonical_res.status in ("unavailable", "rejected") or "unavailable" in err_msg.lower() or "not available" in err_msg.lower():
        response["status"] = "unavailable"
        response["is_simulated"] = True
        response["error"] = err_msg
        response["_status"] = 503
    else:
        response["status"] = "failed"
        response["success"] = False
        response["error"] = err_msg
        response["_status"] = 500
    return response


# ---------------------------------------------------------------------------
# Agent chat handlers
# ---------------------------------------------------------------------------


def handle_etap_expert_chat(question: str) -> dict[str, Any]:
    """Run the ETAP Expert agent and return a response dict.

    Returns a dict with ``success`` / ``data`` or ``error`` / ``_status``.
    """
    question = question.strip()
    if not question:
        return {"error": "'question' field is required and must be non-empty", "_status": 400}
    try:
        from agents.etap_expert_agent import ETAPExpertAgent  # type: ignore

        agent = ETAPExpertAgent()
        result = agent.answer(question)
        return {"success": True, "data": result}
    except Exception:
        logger.exception("etap_expert chat failed")
        return {"error": "ETAP Expert agent error", "_status": 500}


def handle_etap_gui_chat(question: str) -> dict[str, Any]:
    """Run the ETAP GUI agent and return a response dict.

    Returns a dict with ``success`` / ``data`` or ``error`` / ``_status``.
    """
    question = question.strip()
    if not question:
        return {"error": "'question' field is required and must be non-empty", "_status": 400}
    try:
        from agents.etap_gui_agent import ETAPGUIAgent  # type: ignore

        agent = ETAPGUIAgent()
        result = agent.answer(question)
        return {"success": True, "data": result}
    except Exception:
        logger.exception("etap_gui chat failed")
        return {"error": "ETAP GUI agent error", "_status": 500}


# ---------------------------------------------------------------------------
# ML / Predictive handlers (lazy-import numpy + ml.predictive)
# ---------------------------------------------------------------------------


def handle_ml_capabilities() -> dict[str, Any]:
    """Discover available ML/AI capabilities and their status."""
    try:
        from ml.predictive import get_ml_capabilities  # type: ignore

        caps = get_ml_capabilities()
        return {"success": True, "data": caps}
    except ImportError as e:
        # Distinguish "ml/ directory missing" from "numpy not installed"
        msg = str(e)
        if "No module named 'ml'" in msg:
            hint = (
                "The ml/ package is not present in this deployment. "
                "If you are on Hugging Face Spaces, this is a known issue — "
                "the Dockerfile must COPY ml/ into the container. "
                "On self-hosted deployments, ensure the ml/ directory is on PYTHONPATH."
            )
        else:
            hint = (
                "ml.predictive failed to import. Install ML dependencies: "
                "pip install numpy scipy pandas scikit-learn."
            )
        return {
            "success": False,
            "errors": [hint],
            "deployment_note": (
                "ML endpoints (load forecasting, anomaly detection) require "
                "numpy + scikit-learn. On HF Space cpu-basic hardware these are "
                "intentionally omitted to keep the image small. Run the "
                "self-hosted Docker Compose deployment for full ML support."
            ),
            "_status": 503,
        }
    except Exception:
        return {"success": False, "errors": [MSG_INTERNAL_ERROR], "_status": 500}


def handle_predict_load(body: dict[str, Any]) -> dict[str, Any]:
    """Predict future load using Prophet/LSTM/Linear LoadForecaster."""
    # CRITICAL #5 fix (AhmedETAP_Error_Report_AR.pdf):
    # ValueError / TypeError / KeyError are CLIENT errors (bad input) and MUST
    # return HTTP 400, not 500. Only genuine server-side surprises (ImportError,
    # AttributeError, RuntimeError from the ML backend) should be 500.
    try:
        import numpy as np  # type: ignore

        from ml.predictive import LoadForecaster  # type: ignore

        historical = body.get("historical_data") or body.get("data", [])
        # Accept both `horizon_hours` (canonical) and `horizon` (alias used
        # by the Newman/Postman smoke-test collection and several SDK clients).
        # If both are present, `horizon_hours` wins.
        horizon = body.get("horizon_hours")
        if horizon is None:
            horizon = body.get("horizon", 24)
        method = body.get("method", "auto")

        if not historical:
            return {"error": "historical_data (or data) is required", "_status": 400}

        # Validate types before passing to ML backend so we control the
        # status code (the ML backend raises ValueError on bad input, but
        # we want a clearer message + 400 here, not a 500).
        if not isinstance(historical, list) or not all(
            isinstance(x, (int, float)) for x in historical
        ):
            return {
                "error": "historical_data must be a list of numbers",
                "_status": 400,
            }
        if not isinstance(horizon, int) or horizon <= 0:
            return {
                "error": "horizon_hours must be a positive integer",
                "_status": 400,
            }
        if not isinstance(method, str) or method not in ("auto", "prophet", "lstm", "linear"):
            return {
                "error": "method must be one of: auto, prophet, lstm, linear",
                "_status": 400,
            }

        lf = LoadForecaster(method=method)
        data = np.array(historical, dtype=float)
        train_result = lf.train(data)
        predictions = lf.predict(horizon_hours=horizon)

        return {
            "success": True,
            "data": {
                "predictions": predictions.tolist()
                if hasattr(predictions, "tolist")
                else list(predictions),
                "horizon_hours": horizon,
                "method": train_result.get("method", method),
            },
        }
    except (ValueError, TypeError, KeyError):
        # Client-side input problem — return 400 Bad Request.
        return {"success": False, "errors": [MSG_INVALID_INPUT], "_status": 400}
    except Exception:
        # Genuine server-side failure (ImportError, ML backend crash, etc.).
        return {"success": False, "errors": [MSG_INTERNAL_ERROR], "_status": 500}


def handle_detect_anomalies(body: dict[str, Any]) -> dict[str, Any]:
    """Detect anomalies using Isolation Forest / PyOD."""
    try:
        import numpy as np  # type: ignore

        from ml.predictive import AnomalyDetector  # type: ignore

        data = body.get("data") or body.get("values") or body.get("historical_data", [])
        method = body.get("method", "iforest")
        contamination = body.get("contamination", 0.05)

        if not data:
            return {"error": "data (or values) is required", "_status": 400}

        ad = AnomalyDetector(contamination=contamination, method=method)
        X = np.array(data, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        ad.train(X)
        result = ad.detect(X)

        return {"success": True, "data": result}
    except Exception:
        return {"success": False, "errors": [MSG_INTERNAL_ERROR], "_status": 500}


def handle_context_retrieval(
    query: str,
    top_k: int = 5,
    max_tokens: int = 2000,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Retrieve and compress relevant code chunks based on semantic search."""
    try:
        from ai_context_engine.retriever import CHROMA_AVAILABLE, CodeRetriever

        # Determine path to Chroma DB (default to ./index/)
        index_dir = os.environ.get("CODE_CONTEXT_INDEX_DIR", "./index")

        retriever = CodeRetriever(index_dir=index_dir)
        compressed = retriever.retrieve_and_compress(
            query, top_k=top_k, max_tokens=max_tokens, tenant_id=tenant_id
        )

        response: dict[str, Any] = {
            "success": True,
            "query": query,
            "count": len(compressed),
            "chunks": compressed,
        }
        # When 0 chunks are returned, explain WHY so the caller can distinguish
        # "no results matched" from "RAG backend not configured".
        if len(compressed) == 0:
            if not CHROMA_AVAILABLE:
                response["note"] = (
                    "ChromaDB is not installed in this deployment — semantic "
                    "retrieval is disabled. Run the self-hosted Docker Compose "
                    "deployment or pip install chromadb to enable RAG."
                )
            elif not retriever.collection:
                response["note"] = (
                    f"No ChromaDB collection found at '{index_dir}'. The code "
                    "index has not been built yet — run "
                    "`python -m ai_context_engine.indexer <repo_path>` to build it."
                )
            else:
                response["note"] = (
                    "No code chunks matched the query. Try different keywords or "
                    "rebuild the index with `python -m ai_context_engine.indexer .`"
                )
        return response
    except Exception:
        return {"success": False, "errors": [MSG_INTERNAL_ERROR], "_status": 500}


def handle_impact_analysis(component: str, max_depth: int = 2) -> dict[str, Any]:
    """Perform impact analysis on a component using the Code Property Graph."""
    try:
        from ai_context_engine.knowledge_graph import KnowledgeGraph

        # Build graph on the fly (very fast for local files)
        kg = KnowledgeGraph()
        # Scan current workspace directory
        kg.scan_repo(".")

        subgraph = kg.generate_impact_subgraph(component, max_depth=max_depth)

        return {
            "success": True,
            "component": component,
            "max_depth": max_depth,
            "nodes_count": len(subgraph["nodes"]),
            "edges_count": len(subgraph["edges"]),
            "impact": subgraph,
        }
    except Exception:
        logger.exception("Failed to run impact analysis")
        return {"success": False, "errors": [MSG_INTERNAL_ERROR], "_status": 500}
