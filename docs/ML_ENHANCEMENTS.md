# AhmedETAP — ML/AI Enhancement Documentation

## Overview

This document describes the comprehensive ML/AI enhancements integrated into the AhmedETAP platform, leveraging libraries identified from the [awesome-machine-learning](https://github.com/josephmisiti/awesome-machine-learning) repository.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     ML/AI Enhancement Layer                      │
├──────────────┬──────────────┬──────────────┬───────────────────┤
│  Load        │  Fault       │  Anomaly     │  Power Grid       │
│  Forecasting │  Prediction  │  Detection   │  GNN              │
├──────────────┼──────────────┼──────────────┼───────────────────┤
│  Prophet     │  XGBoost     │  PyOD IForest│  PyTorch          │
│  LSTM/TF     │  SHAP        │  PyOD KNN    │  Geometric (GCN)  │
│  Linear Reg  │  Optuna      │  PyOD AutoEnc│  Geometric (GAT)  │
├──────────────┴──────────────┴──────────────┴───────────────────┤
│                     Model Management (MLflow)                     │
├─────────────────────────────────────────────────────────────────┤
│              Capability Detection (get_ml_capabilities)           │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. LoadForecaster (`ml/predictive.py`)

| Method | Library | Best For | Auto-Selection Priority |
|--------|---------|----------|------------------------|
| LSTM | TensorFlow/Keras | Non-linear patterns, large datasets | 1st (if TF available) |
| Prophet | prophet | Seasonal data with holidays | 2nd (if Prophet available) |
| Linear Regression | numpy only | Quick fallback, no dependencies | 3rd (always available) |

**Usage:**
```python
from ml.predictive import LoadForecaster

# Auto-select best available method
lf = LoadForecaster(method="auto")
lf.train(historical_data)  # 1-D numpy array
predictions = lf.predict(horizon_hours=24)
metrics = lf.evaluate(test_data)

# Force specific method
lf_prophet = LoadForecaster(method="prophet")
lf_prophet.train(historical_data)
```

### 2. FaultPredictor (`ml/predictive.py`)

| Feature | Library | Description |
|---------|---------|-------------|
| Primary model | XGBoost | Gradient boosting, superior to RF |
| Fallback model | scikit-learn RF | When XGBoost unavailable |
| Explainability | SHAP | TreeExplainer for feature contributions |
| Optimization | Optuna | Hyperparameter tuning with cross-validation |

**Usage:**
```python
from ml.predictive import FaultPredictor

fp = FaultPredictor(use_xgboost=True, optimize=True)
result = fp.train(features, labels)
prediction = fp.predict(single_sample)
explanation = fp.explain(single_sample)  # SHAP values
importance = fp.feature_importance()
```

### 3. AnomalyDetector (`ml/predictive.py`)

| Method | Library | Description |
|--------|---------|-------------|
| iforest | scikit-learn | Classic Isolation Forest |
| pyod_iforest | PyOD | Enhanced Isolation Forest |
| pyod_knn | PyOD | K-Nearest Neighbors |
| pyod_autoencoder | PyOD | Deep learning AutoEncoder |

**Usage:**
```python
from ml.predictive import AnomalyDetector

ad = AnomalyDetector(contamination=0.05, method="pyod_knn")
ad.train(normal_data)
result = ad.detect(test_data)
```

### 4. PowerGridGNN (`ml/predictive.py`)

Graph Neural Network for power grid analysis using PyTorch Geometric.

- **GCN**: Graph Convolutional Network — captures local neighborhood patterns
- **GAT**: Graph Attention Network — learns attention weights for edge importance

**Usage:**
```python
from ml.predictive import PowerGridGNN

gnn = PowerGridGNN(model_type="gcn", hidden_dim=64, num_layers=3)
result = gnn.train_model(node_features, edge_index, targets, epochs=100)
predictions = gnn.predict(node_features, edge_index)
```

### 5. GNNStateEstimator (`scada_model/state_estimation.py`)

Combines traditional WLS with GNN refinement:

```
WLS State Estimation → GNN Refinement → Blended Result (80% WLS + 20% GNN)
```

Falls back to pure WLS when GNN is not trained or PyTorch Geometric is unavailable.

### 6. ModelRegistry (`ml/predictive.py`)

MLflow-based model tracking and versioning with SQLite backend.

**Usage:**
```python
from ml.predictive import ModelRegistry

registry = ModelRegistry(tracking_uri="sqlite:///mlflow.db")
exp_id = registry.create_experiment("load_forecasting")
run = registry.start_run("load_forecasting", run_name="prophet_v1")
registry.log_params({"method": "prophet", "horizon": 24})
registry.log_metrics({"mae": 2.3, "rmse": 3.1})
registry.end_run()
```

## Agent Integration

### PredictiveAgent (`agents/predictive_agent.py`)

New analysis types:
- `ml_short_term_forecast`: Uses Prophet/LSTM from LoadForecaster
- `ml_fault_prediction`: Uses XGBoost with SHAP explanations
- `full_ml`: Runs all ML-enhanced analyses

### AnomalyAgent (`agents/anomaly_agent.py`)

New detection method:
- `ml`: Uses PyOD multi-method anomaly detection

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/ml/capabilities` | GET | Discover available ML capabilities |
| `/api/v1/predict/load` | POST | Load forecasting with Prophet/LSTM/Linear |
| `/api/v1/predict/fault/train` | POST | Train fault predictor with XGBoost |
| `/api/v1/predict/anomaly` | POST | Anomaly detection with PyOD |
| `/api/v1/gnn/predict` | POST | GNN prediction on power grid graph |
| `/api/v1/rag/query` | POST | RAG query with sentence-transformers |

## HuggingFace Space

The HF Space deployment (`hf-space/app.py`) includes:
- `/api/v1/ml/capabilities` — capability discovery
- `/api/v1/predict/load` — load forecasting
- `/api/v1/predict/anomaly` — anomaly detection

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| prophet | >=1.1.0 | Seasonal load forecasting |
| xgboost | >=2.0.0 | Gradient boosting fault prediction |
| shap | >=0.43.0 | Model explainability |
| optuna | >=3.0.0 | Hyperparameter optimization |
| pyod | >=1.0.0 | 30+ anomaly detection algorithms |
| torch | >=2.0.0 | Deep learning foundation |
| torch-geometric | >=2.3.0 | Graph Neural Networks |
| mlflow | >=2.0.0 | Model tracking and versioning |
| transformers | >=4.30.0 | NLP and RAG enhancement |
| sentence-transformers | >=2.2.0 | Sentence embeddings for RAG |

## Graceful Degradation

All ML features gracefully degrade when optional dependencies are unavailable:

```python
from ml.predictive import get_ml_capabilities
caps = get_ml_capabilities()
# Returns which libraries are available and the best available method
```

This ensures the platform works in minimal environments (HF Spaces, Docker slim)
while providing enhanced capabilities when all libraries are installed.
