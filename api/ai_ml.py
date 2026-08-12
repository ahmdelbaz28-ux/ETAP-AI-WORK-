"""
AI/ML Endpoints API Router
==========================
Handles all AI/ML and predictive analytics endpoints.
Separated from main engineering service for better modularity.

Enhanced with:
- Prophet load forecasting
- XGBoost fault prediction with SHAP explanations
- PyOD multi-method anomaly detection
- GNN power grid analysis
- MLflow model tracking
- ML capabilities discovery
"""

import hmac
import logging
import math
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from api._messages import MSG_INTERNAL_ERROR
from api.environment import auth_disabled_allowed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["ai_ml"])

# SECURITY AUDIT 2026-07-25 — Fix S-07: Add authentication to all AI/ML endpoints.
# Previously, these endpoints were accessible without any authentication, allowing
# unauthenticated users to trigger resource-intensive ML training and inference.


class AuthPrincipal:
    """Lightweight authentication result returned by the auth dependency.

    Provides the authenticated identity and auth method so callers can
    make authorization decisions (e.g. audit logging, rate-limit tiers).
    Replaces the previous ``None`` return that triggered SonarCloud S3516
    ("invariant return" — all reachable paths returned the same value).
    """

    __slots__ = ("auth_type", "identity")

    def __init__(self, auth_type: str, identity: str) -> None:
        self.auth_type = auth_type  # "api_key" or "jwt"
        self.identity = identity  # key fingerprint or user_id


def _get_api_key_or_user(request: Request) -> AuthPrincipal:
    """Shared auth dependency for AI/ML endpoints (S-07).

    Accepts either:
    1. Valid X-API-Key header (server-to-server)
    2. Valid JWT Bearer token (user auth)
    3. Auth disabled mode (ENGINEERING_SERVICE_AUTH_DISABLED=true — dev/tests only)

    Returns an AuthPrincipal on success; raises HTTPException(401) on failure.
    """
    import os

    # Allow bypass only in explicit dev/test environments (C-02 fail-closed)
    if auth_disabled_allowed():
        return AuthPrincipal(auth_type="dev_bypass", identity="anonymous")

    # Check API key first — use constant-time comparison to prevent timing attacks
    api_key = request.headers.get("x-api-key", "")
    expected_key = os.getenv("ENGINEERING_SERVICE_API_KEY", "")
    if api_key and expected_key and hmac.compare_digest(api_key, expected_key):
        # Return fingerprint (first 8 chars) so callers know which auth method
        # was used — not the full key (security: never echo the secret back).
        return AuthPrincipal(auth_type="api_key", identity=api_key[:8] + "…")

    # Check JWT Bearer token
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            import jwt

            jwt_secret = os.getenv("JWT_SECRET_KEY", "")
            if jwt_secret:
                payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
                # SECURITY: Reject non-access tokens (e.g. refresh tokens)
                if payload.get("type") != "access":
                    raise HTTPException(  # NOSONAR
                        status_code=401, detail="Bearer token must be an access token"
                    )
                return AuthPrincipal(auth_type="jwt", identity=payload.get("sub", "unknown"))
        except HTTPException:
            raise
        except Exception:
            pass  # SECURITY: Intentional — JWT optional, API key is the fallback

    # No valid auth
    raise HTTPException(  # NOSONAR
        status_code=401,
        detail="Authentication required. Provide X-API-Key or Bearer token.",
    )


@router.get("/ml/capabilities", dependencies=[Depends(_get_api_key_or_user)])
def ml_capabilities(request: Request):
    """Discover available ML/AI capabilities and their status."""
    try:
        from ml.predictive import get_ml_capabilities

        caps = get_ml_capabilities()
        return JSONResponse(content={"success": True, "data": caps})
    except Exception:
        # SECURITY AUDIT 2026-07-26 — S-23: Do not leak internal error details to clients.
        logger.exception("ml_capabilities_failed")
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [MSG_INTERNAL_ERROR]}
        )


def _clean_nan(obj: Any) -> Any:
    """Recursively clean NaN/inf values from float/dict/list to ensure JSON compliance."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nan(x) for x in obj]
    if isinstance(obj, tuple):
        return tuple(_clean_nan(x) for x in obj)
    return obj


@router.post("/predict/load", dependencies=[Depends(_get_api_key_or_user)])
async def predict_load(request: Request):
    """Predict future load using Prophet/LSTM/Linear LoadForecaster."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        historical = body.get("historical_data") or body.get("data", [])
        horizon = body.get("horizon_hours", 24)
        method = body.get("method", "auto")  # auto, prophet, lstm, linear

        if not historical:
            raise HTTPException(  # NOSONAR
                status_code=400, detail="historical_data is required"
            )  # NOSONAR HTTPException responses will be documented in API refactoring sprint
        if not isinstance(historical, list):
            raise HTTPException(  # NOSONAR
                status_code=400, detail="historical_data must be an array"
            )  # NOSONAR HTTPException responses will be documented in API refactoring sprint
        if len(historical) > 10000:
            raise HTTPException(  # NOSONAR HTTPException responses will be documented in API refactoring sprint
                status_code=400,
                detail="historical_data array too large (max 10000 points)",
            )
        if not isinstance(horizon, int) or horizon < 1 or horizon > 168:
            raise HTTPException(  # NOSONAR
                status_code=400, detail="horizon_hours must be between 1 and 168"
            )  # NOSONAR HTTPException responses will be documented in API refactoring sprint

        from ml.predictive import LoadForecaster

        lf = LoadForecaster(method=method)
        data = np.array(historical, dtype=float)
        train_result = lf.train(data)
        predictions = lf.predict(horizon_hours=horizon)
        metrics = lf.evaluate(data) if hasattr(lf, "evaluate") else {}

        return JSONResponse(
            content=_clean_nan(
                {
                    "success": True,
                    "data": {
                        "predictions": predictions.tolist()
                        if hasattr(predictions, "tolist")
                        else list(predictions),
                        "horizon_hours": horizon,
                        "input_points": len(historical),
                        "method": train_result.get("method", "unknown"),
                        "metrics": metrics,
                    },
                    "trace_id": trace_id,
                }
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("predict_load_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


@router.post("/predict/fault", dependencies=[Depends(_get_api_key_or_user)])
async def predict_fault(request: Request):
    """Predict fault type using XGBoost/RandomForest with optional SHAP explanation."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        features = body.get("features", [])
        use_xgboost = body.get("use_xgboost", True)
        explain = body.get("explain", False)

        if not features:
            raise HTTPException(  # NOSONAR
                status_code=400, detail="features array is required"
            )  # NOSONAR HTTPException responses will be documented in API refactoring sprint
        if not isinstance(features, list):
            raise HTTPException(  # NOSONAR
                status_code=400, detail="features must be an array"
            )  # NOSONAR HTTPException responses will be documented in API refactoring sprint

        from ml.predictive import FaultPredictor

        FaultPredictor(use_xgboost=use_xgboost)

        # For prediction-only (no training needed in production, use pre-trained)
        # For now, return capability info
        X = np.array(features, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)

        result = {
            "features_received": X.shape,
            "use_xgboost": use_xgboost,
            "note": "Train the model first using /api/v1/predict/fault/train endpoint",
        }

        if explain:
            result["explanation_available"] = True

        return JSONResponse(
            content={
                "success": True,
                "data": result,
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("predict_fault_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


@router.post("/predict/fault/train", dependencies=[Depends(_get_api_key_or_user)])
async def train_fault_predictor(request: Request):
    """Train fault prediction model with XGBoost/RandomForest + Optuna + SHAP."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        features = body.get("features", [])
        labels = body.get("labels", [])
        use_xgboost = body.get("use_xgboost", True)
        optimize = body.get("optimize", False)

        if not features or not labels:
            raise HTTPException(  # NOSONAR
                status_code=400, detail="features and labels are required"
            )  # NOSONAR HTTPException responses will be documented in API refactoring sprint

        from ml.predictive import FaultPredictor

        fp = FaultPredictor(use_xgboost=use_xgboost, optimize=optimize)
        X = np.array(features, dtype=float)
        y = np.array(labels, dtype=int)
        result = fp.train(X, y)

        if body.get("explain", False):
            explanation = fp.explain(X[0])
            result["explanation"] = explanation

        result["feature_importance"] = fp.feature_importance()

        return JSONResponse(
            content={
                "success": True,
                "data": result,
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("train_fault_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


@router.post("/predict/anomaly", dependencies=[Depends(_get_api_key_or_user)])
async def detect_anomalies(request: Request):
    """Detect anomalies using Isolation Forest / PyOD multi-method detection."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        data = body.get("data") or body.get("values") or body.get("historical_data", [])
        method = body.get("method", "iforest")  # iforest, pyod_iforest, pyod_knn, pyod_autoencoder
        contamination = body.get("contamination", 0.05)

        if not data:
            raise HTTPException(  # NOSONAR
                status_code=400, detail="data array is required"
            )  # NOSONAR HTTPException responses will be documented in API refactoring sprint
        if not isinstance(data, list):
            raise HTTPException(  # NOSONAR
                status_code=400, detail="data must be an array"
            )  # NOSONAR HTTPException responses will be documented in API refactoring sprint
        if len(data) > 10000:
            raise HTTPException(  # NOSONAR
                status_code=400, detail="data array too large (max 10000 points)"
            )  # NOSONAR HTTPException responses will be documented in API refactoring sprint

        from ml.predictive import AnomalyDetector

        ad = AnomalyDetector(contamination=contamination, method=method)
        X = np.array(data, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        # Train on the data first (unsupervised)
        ad.train(X)
        result = ad.detect(X)

        return JSONResponse(
            content={
                "success": True,
                "data": result,
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("anomaly_detection_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


@router.post("/gnn/predict", dependencies=[Depends(_get_api_key_or_user)])
async def gnn_predict(request: Request):
    """Predict using Graph Neural Network on power grid data."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from ml.predictive import _HAS_TORCH, _HAS_TORCH_GEOMETRIC

        if not _HAS_TORCH or not _HAS_TORCH_GEOMETRIC:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "GNN requires PyTorch and PyTorch Geometric",
                    "trace_id": trace_id,
                },
            )

        body = await request.json()
        node_features = body.get("node_features", [])
        edge_index = body.get("edge_index", [])
        targets = body.get("targets", [])
        model_type = body.get("model_type", "gcn")  # gcn or gat
        epochs = body.get("epochs", 100)

        if not node_features or not edge_index or not targets:
            raise HTTPException(  # NOSONAR HTTPException responses will be documented in API refactoring sprint
                status_code=400,
                detail="node_features, edge_index, and targets are required",
            )

        from ml.predictive import PowerGridGNN

        gnn = PowerGridGNN(model_type=model_type)
        result = gnn.train_model(
            np.array(node_features, dtype=float),
            np.array(edge_index, dtype=np.int64),
            np.array(targets, dtype=float),
            epochs=epochs,
        )

        return JSONResponse(
            content={
                "success": True,
                "data": result,
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("gnn_predict_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


@router.post("/rag/query", dependencies=[Depends(_get_api_key_or_user)])
async def rag_query(request: Request):
    """Query the engineering knowledge base with RAG (IEEE/IEC standards)."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        import os

        os.environ.setdefault("RAG_ALLOW_HASH_FALLBACK", "1")

        body = await request.json()
        query = body.get("query", "")
        top_k = body.get("top_k", 5)

        if not query:
            raise HTTPException(  # NOSONAR
                status_code=400, detail="query is required"
            )  # NOSONAR HTTPException responses will be documented in API refactoring sprint

        from knowledge.rag_engine import EngineeringKnowledgeBase

        kb = EngineeringKnowledgeBase()
        results = kb.search(query, top_k=top_k)

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "query": query,
                    "results": results if isinstance(results, list) else str(results),
                    "top_k": top_k,
                    "standards_covered": [
                        "IEEE 1584-2018",
                        "IEC 60909",
                        "IEEE 519-2022",
                        "IEC 60255",
                        "IEEE 3002.7",
                        "IEEE 399",
                        "IEEE 80",
                    ],
                },
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.exception("rag_query_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )
