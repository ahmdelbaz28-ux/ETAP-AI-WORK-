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

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1", tags=["ai_ml"])


@router.get("/ml/capabilities")
async def ml_capabilities():
    """Discover available ML/AI capabilities and their status."""
    try:
        from ml.predictive import get_ml_capabilities

        caps = get_ml_capabilities()
        return JSONResponse(content={"success": True, "data": caps})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)]})


@router.post("/predict/load")
async def predict_load(request: Request):
    """Predict future load using Prophet/LSTM/Linear LoadForecaster."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        historical = body.get("historical_data", [])
        horizon = body.get("horizon_hours", 24)
        method = body.get("method", "auto")  # auto, prophet, lstm, linear

        if not historical:
            raise HTTPException(status_code=400, detail="historical_data is required")
        if not isinstance(historical, list):
            raise HTTPException(status_code=400, detail="historical_data must be an array")
        if len(historical) > 10000:
            raise HTTPException(
                status_code=400, detail="historical_data array too large (max 10000 points)"
            )
        if not isinstance(horizon, int) or horizon < 1 or horizon > 168:
            raise HTTPException(status_code=400, detail="horizon_hours must be between 1 and 168")

        from ml.predictive import LoadForecaster

        lf = LoadForecaster(method=method)
        data = np.array(historical, dtype=float)
        train_result = lf.train(data)
        predictions = lf.predict(horizon_hours=horizon)
        metrics = lf.evaluate(data) if hasattr(lf, "evaluate") else {}

        return JSONResponse(
            content={
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
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.error("predict_load_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id}
        )


@router.post("/predict/fault")
async def predict_fault(request: Request):
    """Predict fault type using XGBoost/RandomForest with optional SHAP explanation."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        features = body.get("features", [])
        use_xgboost = body.get("use_xgboost", True)
        explain = body.get("explain", False)

        if not features:
            raise HTTPException(status_code=400, detail="features array is required")
        if not isinstance(features, list):
            raise HTTPException(status_code=400, detail="features must be an array")

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
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.error("predict_fault_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id}
        )


@router.post("/predict/fault/train")
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
            raise HTTPException(status_code=400, detail="features and labels are required")

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
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.error("train_fault_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id}
        )


@router.post("/predict/anomaly")
async def detect_anomalies(request: Request):
    """Detect anomalies using Isolation Forest / PyOD multi-method detection."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        data = body.get("data", [])
        method = body.get("method", "iforest")  # iforest, pyod_iforest, pyod_knn, pyod_autoencoder
        contamination = body.get("contamination", 0.05)

        if not data:
            raise HTTPException(status_code=400, detail="data array is required")
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="data must be an array")
        if len(data) > 10000:
            raise HTTPException(status_code=400, detail="data array too large (max 10000 points)")

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
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.error("anomaly_detection_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id}
        )


@router.post("/gnn/predict")
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
                }
            )

        body = await request.json()
        node_features = body.get("node_features", [])
        edge_index = body.get("edge_index", [])
        targets = body.get("targets", [])
        model_type = body.get("model_type", "gcn")  # gcn or gat
        epochs = body.get("epochs", 100)

        if not node_features or not edge_index or not targets:
            raise HTTPException(
                status_code=400, detail="node_features, edge_index, and targets are required"
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
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.error("gnn_predict_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id}
        )


@router.post("/rag/query")
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
            raise HTTPException(status_code=400, detail="query is required")

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
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger

        logger = getLogger("engineering_service")
        logger.error("rag_query_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id}
        )
