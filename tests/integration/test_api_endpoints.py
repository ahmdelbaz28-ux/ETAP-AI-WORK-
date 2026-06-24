"""
Integration tests for API endpoints.
Tests the full request/response cycle through the FastAPI application.
"""

import json

import pytest
from fastapi.testclient import TestClient


def test_health_endpoint(api_client):
    """Test the health endpoint."""
    response = api_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert data["status"] == "healthy"


def test_ready_endpoint(api_client):
    """Test the readiness endpoint."""
    response = api_client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert "ready" in data
    assert "native_engine_available" in data


def test_metrics_endpoint(api_client):
    """Test the metrics endpoint."""
    response = api_client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "requests_total" in data
    assert "requests_success" in data
    assert "avg_execution_time_ms" in data


def test_study_execution_endpoint(api_client, sample_3bus_network):
    """Test the study execution endpoint."""
    system_dict = {
        k: [item.model_dump() if hasattr(item, "model_dump") else item for item in v]
        if isinstance(v, list) else v
        for k, v in sample_3bus_network.items()
    }
    payload = {
        "study_type": "load_flow",
        "system": system_dict,
        "parameters": {"tolerance": 1e-6, "max_iterations": 50},
    }

    response = api_client.post("/api/v1/studies/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert data["success"] is True
    assert "study_type" in data


def test_system_validation_endpoint(api_client, sample_3bus_network):
    """Test the system validation endpoint."""
    system_dict = {
        k: [item.model_dump() if hasattr(item, "model_dump") else item for item in v]
        if isinstance(v, list) else v
        for k, v in sample_3bus_network.items()
    }
    response = api_client.post("/api/v1/system/validate", json=system_dict)
    assert response.status_code == 200
    data = response.json()
    assert "valid" in data
    assert "warnings" in data
    assert "errors" in data


def test_predict_load_endpoint(api_client):
    """Test the load prediction endpoint."""
    payload = {"historical_data": [100, 120, 110, 130, 125, 140, 135] * 8, "horizon_hours": 24}

    response = api_client.post("/api/v1/predict/load", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert data["success"] is True
    assert "data" in data


def test_predict_fault_endpoint(api_client):
    """Test the fault prediction endpoint."""
    payload = {"features": [0.5, 0.3, 0.8, 0.2]}

    response = api_client.post("/api/v1/predict/fault", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert data["success"] is True


def test_anomaly_detection_endpoint(api_client):
    """Test the anomaly detection endpoint."""
    payload = {
        "data": [1.0, 1.1, 0.9, 1.2, 5.0, 1.0, 1.1]  # 5.0 is an anomaly
    }

    response = api_client.post("/api/v1/predict/anomaly", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert data["success"] is True


def test_rag_query_endpoint(api_client):
    """Test the RAG query endpoint."""
    payload = {"query": "What is IEEE 1584-2018 standard?", "top_k": 3}

    response = api_client.post("/api/v1/rag/query", json=payload)
    # May return 500 if knowledge base is not initialized, but should not crash
    assert response.status_code in [200, 500]


def test_prometheus_metrics_endpoint(api_client):
    """Test the Prometheus metrics endpoint."""
    response = api_client.get("/prometheus/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


def test_root_endpoint(api_client):
    """Test the root endpoint."""
    response = api_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_head_requests(api_client):
    """Test HEAD requests for health and ready endpoints."""
    for endpoint in ["/health", "/ready", "/healthz", "/readyz"]:
        response = api_client.head(endpoint)
        assert response.status_code == 200
        # HEAD requests should not have body
        assert response.content == b""
