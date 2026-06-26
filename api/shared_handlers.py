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
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

UTC = timezone.utc

logger = logging.getLogger("etap-ai")

# ---------------------------------------------------------------------------
# Constants — single source of truth
# ---------------------------------------------------------------------------

VERSION = "2.1.0"

AGENT_COUNT: int = 23
ETAP_MANUAL_COUNT: int = 35
ZENON_GUIDE_COUNT: int = 4

START_TIME: float = time.time()
BUILD_TIME: str = datetime.now(UTC).isoformat()

# ---------------------------------------------------------------------------
# Study types
# ---------------------------------------------------------------------------

STUDY_TYPES: List[str] = [
    "load_flow",
    "short_circuit",
    "arc_flash",
    "protection_coordination",
    "motor_starting",
    "transient_stability",
    "harmonic_analysis",
    "optimal_power_flow",
    "cable_sizing",
    "earth_grid",
    "renewable_integration",
    "battery_storage",
    "scada",
    "etap_expert",   # ETAP Expert skill — 6-step workflow with Format A/B/C/D
    "etap_gui",      # ETAP GUI Agent — Computer Use Agent for desktop apps
]

# ---------------------------------------------------------------------------
# Agents list
# ---------------------------------------------------------------------------

AGENTS: List[Dict[str, str]] = [
    {"id": "load-flow-agent", "name": "Load Flow Agent", "standard": "IEEE 3002.7", "status": "active"},
    {"id": "short-circuit-agent", "name": "Short Circuit Agent", "standard": "IEC 60909", "status": "active"},
    {"id": "arcflash-agent", "name": "Arc Flash Agent", "standard": "IEEE 1584", "status": "active"},
    {"id": "protection-agent", "name": "Protection Agent", "standard": "IEC 60255", "status": "active"},
    {"id": "motorstarting-agent", "name": "Motor Starting Agent", "standard": "IEEE 399", "status": "active"},
    {"id": "stability-agent", "name": "Stability Agent", "standard": "IEEE 399", "status": "active"},
    {"id": "harmonic-agent", "name": "Harmonic Analysis Agent", "standard": "IEEE 519", "status": "active"},
    {"id": "cable-sizing-agent", "name": "Cable Sizing Agent", "standard": "IEC 60364", "status": "active"},
    {"id": "earth-grid-agent", "name": "Earth Grid Agent", "standard": "IEEE 80", "status": "active"},
    {"id": "opf-agent", "name": "Optimal Power Flow Agent", "standard": "IEEE 3002.7", "status": "active"},
    {"id": "renewable-agent", "name": "Renewable Energy Agent", "standard": "IEEE 1547", "status": "active"},
    {"id": "battery-storage-agent", "name": "Battery Storage Agent", "standard": "IEC 62933", "status": "active"},
    {"id": "scada-agent", "name": "SCADA Agent", "standard": "IEC 61850", "status": "active"},
    {"id": "digital-twin-agent", "name": "Digital Twin Agent", "standard": "IEC 61970", "status": "active"},
    {"id": "predictive-agent", "name": "Predictive Maintenance", "standard": "ISO 13381", "status": "active"},
    {"id": "anomaly-agent", "name": "Anomaly Detection Agent", "standard": "IEEE 1159", "status": "active"},
    {"id": "coordination-agent", "name": "Coordination Agent", "standard": "IEC 60255", "status": "active"},
    {"id": "report-agent", "name": "Report Generation Agent", "standard": "IEEE 3002.7", "status": "active"},
    {"id": "validation-agent", "name": "Validation Agent", "standard": "IEC 60038", "status": "active"},
    {"id": "etap-engineer-agent", "name": "ETAP Engineer Agent", "standard": "ETAP Manual", "status": "active"},
    {"id": "goal-planner-agent", "name": "Goal Planner Agent", "standard": "Internal", "status": "active"},
    {"id": "weather-agent", "name": "Weather Agent", "standard": "IEC 60721", "status": "active"},
    {"id": "power-system-coordinator", "name": "Power System Coordinator", "standard": "All", "status": "active"},
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

# ---------------------------------------------------------------------------
# Pydantic request models (lightweight — no heavy deps)
# ---------------------------------------------------------------------------


class SharedStudyRequest(BaseModel):
    """Lightweight study request used by both HF Space and main API."""

    study_type: str
    system: Dict[str, Any] = {}
    options: Dict[str, Any] = {}
    parameters: Dict[str, Any] = {}
    use_etap: bool = False


class SharedETAPExpertChatRequest(BaseModel):
    """Request body for ETAP Expert chat."""

    question: str
    context: Dict[str, Any] = {}


class SharedETAPGUIChatRequest(BaseModel):
    """Request body for ETAP GUI Agent chat."""

    question: str
    context: Dict[str, Any] = {}


class SharedContextRetrieveRequest(BaseModel):
    """Request body for AI Context Engine retrieve endpoint."""

    query: str
    top_k: int = 5
    max_tokens: int = 2000


# ---------------------------------------------------------------------------
# Paths that should skip authentication
# ---------------------------------------------------------------------------

PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/",
        "/healthz",
        "/readyz",
        "/health",
        "/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics",
    }
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
    if not expected_key:
        return  # No key configured → open access

    _skip = skip_paths if skip_paths is not None else PUBLIC_PATHS
    if request.url.path in _skip:
        return

    provided = request.headers.get("x-api-key") or ""
    if not hmac.compare_digest(provided, expected_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# In-memory rate limiter (no Redis needed)
# ---------------------------------------------------------------------------


class InMemoryRateLimiter:
    """Thread-safe, per-client sliding-window rate limiter.

    This is the lightweight alternative to the Redis-backed limiter in
    ``api/routes.py``.  It is suitable for single-process deployments like
    Hugging Face Spaces.
    """

    def __init__(
        self,
        window_seconds: int | None = None,
        max_requests: int | None = None,
        max_entries: int = 10_000,
    ) -> None:
        self.window = window_seconds or int(os.environ.get("RATE_LIMIT_WINDOW", "60"))
        self.max_requests = max_requests or int(os.environ.get("RATE_LIMIT_MAX", "120"))
        self.max_entries = max_entries
        self._store: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, client_id: str) -> bool:
        """Return ``True`` if the request is allowed, ``False`` if rate-limited."""
        now = time.time()
        with self._lock:
            # Evict stale entries if the store is too large
            if len(self._store) > self.max_entries:
                stale = [
                    cid
                    for cid, timestamps in self._store.items()
                    if not timestamps or now - timestamps[-1] > self.window
                ]
                for cid in stale:
                    del self._store[cid]

            if client_id not in self._store:
                self._store[client_id] = [now]
                return True

            # Prune timestamps outside the window
            self._store[client_id] = [
                t for t in self._store[client_id] if now - t < self.window
            ]
            if len(self._store[client_id]) >= self.max_requests:
                return False

            self._store[client_id].append(now)
            return True


# Module-level convenience instance
rate_limiter = InMemoryRateLimiter()

# ---------------------------------------------------------------------------
# Health / readiness / metrics response builders
# ---------------------------------------------------------------------------


def build_health_response(platform: str = "huggingface-spaces") -> Dict[str, Any]:
    """Return a health-status dictionary."""
    uptime = round(time.time() - START_TIME, 2)
    return {
        "status": "healthy",
        "uptime_seconds": uptime,
        "build_time": BUILD_TIME,
        "version": VERSION,
        "platform": platform,
        "agents": AGENT_COUNT,
        "etap_manuals": ETAP_MANUAL_COUNT,
        "zenon_guides": ZENON_GUIDE_COUNT,
    }


def build_ready_response() -> Dict[str, Any]:
    """Return a readiness-status dictionary."""
    return {"status": "ready", "uptime": round(time.time() - START_TIME, 2)}


def build_metrics_response(platform: str = "huggingface-spaces") -> Dict[str, Any]:
    """Return a metrics dictionary."""
    return {
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "platform": platform,
        "version": VERSION,
    }


# ---------------------------------------------------------------------------
# Platform info & knowledge-base info builders
# ---------------------------------------------------------------------------


def build_platform_info() -> Dict[str, Any]:
    """Return platform metadata."""
    return {
        "name": "AhmedETAP",
        "version": VERSION,
        "description": "Enterprise Engineering Intelligence Platform",
        "author": "Eng. Ahmed Elbaz",
        "standards": [
            "IEEE 3002.7",
            "IEC 60909",
            "IEEE 1584",
            "IEC 60255",
            "IEEE 519",
            "IEC 61850",
            "IEEE 80",
            "IEC 60364",
            "IEEE 399",
            "IEC 62933",
        ],
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


def build_knowledge_info() -> Dict[str, Any]:
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
            "standards": ["IEEE 3002.7", "IEC 60909", "IEEE 1584", "IEC 60255", "IEEE 519"],
        },
        "zenon": {
            "guides": ZENON_GUIDE_COUNT,
            "topics": [
                "Zenon SCADA Fundamentals",
                "Zenon Energy Management",
                "Zenon IEC 61850 Module 1",
                "Zenon IEC 61850 Module 2",
            ],
            "standards": ["IEC 61850", "IEC 61968", "IEC 61970"],
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
            return obj.tolist()
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
        pass

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


def run_study_lightweight(study_type: str, system: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
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

    # -- ETAP Expert skill --------------------------------------------------
    if study_type == "etap_expert":
        question = str(parameters.get("question", "")).strip()
        if not question:
            return {
                "error": "'question' field is required for study_type='etap_expert'",
                "_status": 400,
            }
        try:
            from agents.etap_expert_agent import ETAPExpertAgent  # type: ignore

            agent = ETAPExpertAgent()
            result = agent.answer(question)
            return {
                "study_type": "etap_expert",
                "reference": f"ETAP-EXPERT-{int(time.time())}",
                "status": "completed",
                "success": True,
                "data": result,
            }
        except Exception as exc:
            logger.exception("etap_expert study failed")
            return {"error": f"ETAP Expert agent error: {exc}", "_status": 500}

    # -- ETAP GUI Agent -----------------------------------------------------
    if study_type == "etap_gui":
        question = str(parameters.get("question", "")).strip()
        if not question:
            return {
                "error": "'question' field is required for study_type='etap_gui'",
                "_status": 400,
            }
        try:
            from agents.etap_gui_agent import ETAPGUIAgent  # type: ignore

            agent = ETAPGUIAgent()
            result = agent.answer(question)
            return {
                "study_type": "etap_gui",
                "reference": f"ETAP-GUI-{int(time.time())}",
                "status": "completed",
                "success": True,
                "data": result,
            }
        except Exception as exc:
            logger.exception("etap_gui study failed")
            return {"error": f"ETAP GUI agent error: {exc}", "_status": 500}

    # -- Load Flow (native engine) ------------------------------------------
    result_data: Any = None
    engine_error: Optional[str] = None

    if study_type == "load_flow" and system:
        try:
            from core_model.bus import Bus  # type: ignore
            from core_model.line import Line  # type: ignore
            from core_model.system import System  # type: ignore

            sys_model = System(base_mva=system.get("base_mva", 100.0))
            bus_map: Dict[int, Any] = {}
            for b in system.get("buses", []):
                bus = Bus(
                    bus_id=b["bus_id"],
                    voltage_magnitude=b.get("voltage_magnitude", 1.0),
                    voltage_angle=b.get("voltage_angle", 0.0),
                    bus_type=b.get("bus_type", "pq"),
                )
                bus.generation_power = complex(
                    b.get("generation_power_real", 0.0),
                    b.get("generation_power_imag", 0.0),
                )
                bus.load_power = complex(
                    b.get("load_power_real", 0.0),
                    b.get("load_power_imag", 0.0),
                )
                sys_model.add_bus(bus)
                bus_map[b["bus_id"]] = bus

            for ln in system.get("lines", []):
                line = Line(
                    line_id=ln["line_id"],
                    from_bus=bus_map[ln["from_bus_id"]],
                    to_bus=bus_map[ln["to_bus_id"]],
                    z1=complex(ln.get("r1", 0.01), ln.get("x1", 0.05)),
                    z0=complex(
                        ln.get("r0", ln.get("r1", 0.01)),
                        ln.get("x0", ln.get("x1", 0.05)),
                    ),
                    yshunt1=complex(0, ln.get("bshunt1", 0.02)),
                    yshunt0=complex(0, ln.get("bshunt0", ln.get("bshunt1", 0.02))),
                )
                sys_model.add_line(line)

            from engine.engine import PowerSystemEngine  # type: ignore

            engine = PowerSystemEngine(sys_model)
            result_data = engine.run_load_flow()
            result_data = sanitize_result(result_data)
        except ImportError:
            engine_error = "Engine modules not available in HF Space deployment"
        except Exception as exc:
            engine_error = str(exc)

    # -- Build response -----------------------------------------------------
    response: Dict[str, Any] = {
        "study_type": study_type,
        "reference": f"STUDY-{int(time.time())}",
    }
    if result_data is not None:
        response["status"] = "completed"
        response["result"] = result_data
    else:
        response["status"] = "accepted"
        response["message"] = f"Study '{study_type}' queued for processing."
        if engine_error:
            response["engine_note"] = engine_error
        response["note"] = (
            "Full computation engine available in self-hosted deployment. See /docs for details."
        )
    return response


# ---------------------------------------------------------------------------
# Agent chat handlers
# ---------------------------------------------------------------------------


def handle_etap_expert_chat(question: str) -> Dict[str, Any]:
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
    except Exception as exc:
        logger.exception("etap_expert chat failed")
        return {"error": f"ETAP Expert agent error: {exc}", "_status": 500}


def handle_etap_gui_chat(question: str) -> Dict[str, Any]:
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
    except Exception as exc:
        logger.exception("etap_gui chat failed")
        return {"error": f"ETAP GUI agent error: {exc}", "_status": 500}


# ---------------------------------------------------------------------------
# ML / Predictive handlers (lazy-import numpy + ml.predictive)
# ---------------------------------------------------------------------------


def handle_ml_capabilities() -> Dict[str, Any]:
    """Discover available ML/AI capabilities and their status."""
    try:
        from ml.predictive import get_ml_capabilities  # type: ignore

        caps = get_ml_capabilities()
        return {"success": True, "data": caps}
    except Exception as e:
        return {"success": False, "errors": [str(e)], "_status": 500}


def handle_predict_load(body: Dict[str, Any]) -> Dict[str, Any]:
    """Predict future load using Prophet/LSTM/Linear LoadForecaster."""
    try:
        import numpy as np  # type: ignore

        from ml.predictive import LoadForecaster  # type: ignore

        historical = body.get("historical_data", [])
        horizon = body.get("horizon_hours", 24)
        method = body.get("method", "auto")

        if not historical:
            return {"error": "historical_data is required", "_status": 400}

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
    except Exception as e:
        return {"success": False, "errors": [str(e)], "_status": 500}


def handle_detect_anomalies(body: Dict[str, Any]) -> Dict[str, Any]:
    """Detect anomalies using Isolation Forest / PyOD."""
    try:
        import numpy as np  # type: ignore

        from ml.predictive import AnomalyDetector  # type: ignore

        data = body.get("data", [])
        method = body.get("method", "iforest")
        contamination = body.get("contamination", 0.05)

        if not data:
            return {"error": "data is required", "_status": 400}

        ad = AnomalyDetector(contamination=contamination, method=method)
        X = np.array(data, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        ad.train(X)
        result = ad.detect(X)

        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "errors": [str(e)], "_status": 500}


def handle_context_retrieval(query: str, top_k: int = 5, max_tokens: int = 2000) -> Dict[str, Any]:
    """Retrieve and compress relevant code chunks based on semantic search."""
    try:
        from ai_context_engine.retriever import CodeRetriever

        # Determine path to Chroma DB (default to ./index/)
        index_dir = os.environ.get("CODE_CONTEXT_INDEX_DIR", "./index")
        
        retriever = CodeRetriever(index_dir=index_dir)
        compressed = retriever.retrieve_and_compress(query, top_k=top_k, max_tokens=max_tokens)
        
        return {
            "success": True,
            "query": query,
            "count": len(compressed),
            "chunks": compressed
        }
    except Exception as e:
        return {"success": False, "errors": [str(e)], "_status": 500}
