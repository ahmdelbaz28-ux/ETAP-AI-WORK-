---
title: "AhmedETAP API Quick Reference Cheat-Sheet"
version: "2.1.0"
last_updated: "2026-10-06"
maintainer: "Eng. Ahmed Elbaz / Platform Team"
---

# âڑ، AhmedETAP API Quick Reference (Cheat-Sheet)

> **Note:** This cheat-sheet is automatically derived from the authoritative [API Reference](API_REFERENCE.md).
> For complete request/response JSON schemas, error codes, and field validations, consult [docs/API_REFERENCE.md](API_REFERENCE.md).

## Table of Contents
- [Authentication Overview](#authentication-overview)
- [Endpoints Quick Reference](#endpoints-quick-reference)
- [Quick cURL Recipes](#quick-curl-recipes)
- [WebSocket Protocol](#websocket-protocol)

---

## Authentication Overview

| Mechanism | Header Format | Typical Use |
| :--- | :--- | :--- |
| **JWT Bearer** | `Authorization: Bearer <jwt_token>` | UI, Interactive Sessions, RBAC |
| **API Key** | `X-API-Key: <api_key>` | Automated CI/CD, Microservices, COM Scripts |

Obtain token via `POST /api/auth/login` with username & password.

---

## Endpoints Quick Reference

| Method | Endpoint | Category | Description | Canonical Ref |
| :---: | :--- | :--- | :--- | :---: |
| `POST` | `/api/auth/login` | 📋 Table of Contents | Authenticate and obtain a JWT access token. | [Docs](API_REFERENCE.md#post-apiauthlogin) |
| `GET` | `/health` | Health & Readiness Endpoints | Full health check with service dependency status. | [Docs](API_REFERENCE.md#get-health) |
| `GET` | `/healthz` | Health & Readiness Endpoints | Lightweight liveness probe for Kubernetes. | [Docs](API_REFERENCE.md#get-healthz) |
| `GET` | `/readyz` | Health & Readiness Endpoints | Readiness probe that checks all dependencies. | [Docs](API_REFERENCE.md#get-readyz) |
| `GET` | `/ready` | Health & Readiness Endpoints | Detailed readiness check with service health information. | [Docs](API_REFERENCE.md#get-ready) |
| `GET` | `/metrics` | Health & Readiness Endpoints | Prometheus-compatible metrics endpoint. | [Docs](API_REFERENCE.md#get-metrics) |
| `POST` | `/api/v1/studies/run` | Engineering Study Endpoints | Execute a power system engineering study. This is the primary endpoint for running all analysis types through the native Python engine or ETAP COM automation. | [Docs](API_REFERENCE.md#post-apiv1studiesrun) |
| `POST` | `/api/v1/system/validate` | Engineering Study Endpoints | Validate a power system model without running a study. Checks data integrity, connectivity, and basic feasibility. | [Docs](API_REFERENCE.md#post-apiv1systemvalidate) |
| `POST` | `/api/v1/studies/run` *(Short Circuit)* | Short Circuit Analysis | Execute a short circuit analysis compliant with IEC 60909. | [Docs](API_REFERENCE.md#post-apiv1studiesrun-short-circuit) |
| `POST` | `/api/v1/studies/run` *(Arc Flash)* | Arc Flash Analysis | Execute an arc flash hazard analysis per IEEE 1584-2018 and NFPA 70E. | [Docs](API_REFERENCE.md#post-apiv1studiesrun-arc-flash) |
| `POST` | `/api/v1/studies/run` *(Harmonic)* | Harmonic Analysis | Execute harmonic distortion analysis per IEEE 519-2022. | [Docs](API_REFERENCE.md#post-apiv1studiesrun-harmonic) |
| `GET` | `/api/v1/agents` | Agent Management Endpoints | List all available engineering agents and their capabilities. | [Docs](API_REFERENCE.md#get-apiv1agents) |
| `POST` | `/api/v1/agents/{agent_id}/chat` | Agent Management Endpoints | Send a message to a specific agent for conversational engineering assistance. | [Docs](API_REFERENCE.md#post-apiv1agentsagent_idchat) |
| `GET` | `/api/v1/providers` | Provider Management Endpoints | List configured LLM providers and their health status. | [Docs](API_REFERENCE.md#get-apiv1providers) |
| `GET` | `/api/v1/audit/logs` | Audit Logging Endpoints | Retrieve audit log entries for compliance and security review. | [Docs](API_REFERENCE.md#get-apiv1auditlogs) |
| `GET` | `/api/v1/scada/measurements` | SCADA Real-Time Endpoints | Retrieve real-time measurement data from SCADA integration. | [Docs](API_REFERENCE.md#get-apiv1scadameasurements) |
| `GET` | `/api/v1/scada/alarms` | SCADA Real-Time Endpoints | Retrieve active SCADA alarms and events. | [Docs](API_REFERENCE.md#get-apiv1scadaalarms) |
| `POST` | `/api/v1/scada/state-estimation` | SCADA Real-Time Endpoints | Run state estimation on current SCADA measurements. | [Docs](API_REFERENCE.md#post-apiv1scadastate-estimation) |
| `POST` | `/api/v1/predictive/load-forecast` | Predictive Analytics Endpoints | Generate load forecast using ML models. | [Docs](API_REFERENCE.md#post-apiv1predictiveload-forecast) |
| `POST` | `/api/v1/predictive/anomaly-detect` | Predictive Analytics Endpoints | Detect anomalies in measurement data streams. | [Docs](API_REFERENCE.md#post-apiv1predictiveanomaly-detect) |
| `POST` | `/api/v1/predictive/fault-predict` | Predictive Analytics Endpoints | Predict fault type from measurement signatures. | [Docs](API_REFERENCE.md#post-apiv1predictivefault-predict) |
| `WS` | `/ws/study/{study_id}` | WebSocket Endpoints | Subscribe to real-time updates for a running study. | [Docs](API_REFERENCE.md#ws-wsstudystudy_id) |
| `POST` | `/api/v1/reports/generate` | Report Generation | Generate an engineering report from analysis results. | [Docs](API_REFERENCE.md#post-apiv1reportsgenerate) |
| `GET` | `/api/v1/reports/download/{filename}` | Report Generation | Download a generated report file. | [Docs](API_REFERENCE.md#get-apiv1reportsdownloadfilename) |
| `POST` | `/api/v1/knowledge/search` | Knowledge Base Endpoints | Search the engineering knowledge base using RAG. | [Docs](API_REFERENCE.md#post-apiv1knowledgesearch) |
| `POST` | `/api/v1/knowledge/add` | Knowledge Base Endpoints | Add a document to the engineering knowledge base. | [Docs](API_REFERENCE.md#post-apiv1knowledgeadd) |
| `POST` | `/api/v1/users/register` | User Management Endpoints | Register a new user account. | [Docs](API_REFERENCE.md#post-apiv1usersregister) |
| `GET` | `/api/v1/users/profile` | User Management Endpoints | Get current user profile information. | [Docs](API_REFERENCE.md#get-apiv1usersprofile) |
| `POST` | `/api/v1/webhooks/subscribe` | Webhook Endpoints | Subscribe to platform events. | [Docs](API_REFERENCE.md#post-apiv1webhookssubscribe) |

---

## Quick cURL Recipes

### 1. Health & Readiness Probe
```bash
curl -s http://localhost:8000/healthz
curl -s http://localhost:8000/readyz
```

### 2. Run Newton-Raphson Load Flow
```bash
curl -X POST http://localhost:8000/api/v1/studies/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"study_type": "LOAD_FLOW", "project_id": "substation_alpha", "parameters": {"max_iterations": 20, "tolerance": 0.0001}}'
```

### 3. Run IEC 60909 Short Circuit
```bash
curl -X POST http://localhost:8000/api/v1/studies/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"study_type": "SHORT_CIRCUIT", "project_id": "substation_alpha", "parameters": {"standard": "IEC_60909", "fault_type": "3PHASE"}}'
```

### 4. Query Active Agents Registry
```bash
curl -s http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer $TOKEN"
```

---

## WebSocket Protocol

- **Study Streaming:** `ws://localhost:8000/ws/study/{study_id}`
- Subscribes to real-time iteration logs, convergence metrics, and progress percentages.
- See [WebSocket Protocol in API_REFERENCE.md](API_REFERENCE.md#ws-wsstudystudyid).
