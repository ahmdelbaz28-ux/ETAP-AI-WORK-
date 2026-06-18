"""
AI/ML Endpoints API Router
==========================
Handles all AI/ML and predictive analytics endpoints.
Separated from main engineering service for better modularity.
"""

import numpy as np

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1", tags=["ai_ml"])


@router.post("/predict/load")
async def predict_load(request: Request):
    """Predict future load using the LSTM-based LoadForecaster."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        historical = body.get("historical_data", [])
        horizon = body.get("horizon_hours", 24)

        if not historical:
            raise HTTPException(status_code=400, detail="historical_data is required")
        if not isinstance(historical, list):
            raise HTTPException(status_code=400, detail="historical_data must be an array")
        if len(historical) > 10000:
            raise HTTPException(status_code=400, detail="historical_data array too large (max 10000 points)")
        if not isinstance(horizon, int) or horizon < 1 or horizon > 168:
            raise HTTPException(status_code=400, detail="horizon_hours must be between 1 and 168")

        from ml.predictive import LoadForecaster
        lf = LoadForecaster()
        data = np.array(historical, dtype=float)
        lf.train(data)
        predictions = lf.predict(horizon_hours=horizon)
        metrics = lf.evaluate(data) if hasattr(lf, 'evaluate') else {}

        return JSONResponse(content={
            "success": True,
            "data": {
                "predictions": predictions.tolist() if hasattr(predictions, 'tolist') else list(predictions),
                "horizon_hours": horizon,
                "input_points": len(historical),
                "metrics": metrics,
            },
            "trace_id": trace_id,
        })
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger
        logger = getLogger("engineering_service")
        logger.error("predict_load_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


@router.post("/predict/fault")
async def predict_fault(request: Request):
    """Predict fault type using the Random Forest FaultPredictor."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        features = body.get("features", [])

        if not features:
            raise HTTPException(status_code=400, detail="features array is required")
        if not isinstance(features, list):
            raise HTTPException(status_code=400, detail="features must be an array")
        if len(features) > 1000:
            raise HTTPException(status_code=400, detail="features array too large (max 1000 elements)")

        from ml.predictive import FaultPredictor
        fp = FaultPredictor()
        X = np.array(features, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        prediction = fp.predict(X)

        return JSONResponse(content={
            "success": True,
            "data": prediction if isinstance(prediction, dict) else {"prediction": prediction},
            "trace_id": trace_id,
        })
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger
        logger = getLogger("engineering_service")
        logger.error("predict_fault_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


@router.post("/predict/anomaly")
async def detect_anomalies(request: Request):
    """Detect anomalies in measurement data using Isolation Forest."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        data = body.get("data", [])

        if not data:
            raise HTTPException(status_code=400, detail="data array is required")
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="data must be an array")
        if len(data) > 10000:
            raise HTTPException(status_code=400, detail="data array too large (max 10000 points)")

        from ml.predictive import AnomalyDetector
        ad = AnomalyDetector()
        X = np.array(data, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        result = ad.detect(X)

        return JSONResponse(content={
            "success": True,
            "data": result,
            "trace_id": trace_id,
        })
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger
        logger = getLogger("engineering_service")
        logger.error("anomaly_detection_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


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

        return JSONResponse(content={
            "success": True,
            "data": {
                "query": query,
                "results": results if isinstance(results, list) else str(results),
                "top_k": top_k,
                "standards_covered": [
                    "IEEE 1584-2018", "IEC 60909", "IEEE 519-2022",
                    "IEC 60255", "IEEE 3002.7", "IEEE 399", "IEEE 80",
                ],
            },
            "trace_id": trace_id,
        })
    except HTTPException:
        raise
    except Exception as e:
        from logging import getLogger
        logger = getLogger("engineering_service")
        logger.error("rag_query_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})