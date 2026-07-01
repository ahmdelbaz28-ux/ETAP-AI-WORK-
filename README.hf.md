---
title: AhmedETAP
emoji: "⚡"
colorFrom: yellow
colorTo: red
sdk: docker
pinned: false
license: mit
app_port: 7860
---

# AhmedETAP — Enterprise Engineering Intelligence Platform

**Developed by Eng. Ahmed Elbaz** | v2.1.0

Enterprise-grade autonomous engineering intelligence for power-system analysis, ETAP automation, and AI-powered engineering decision support.

## Features

- Load Flow Analysis (Newton-Raphson, Fast Decoupled, DC-OPF)
- Short Circuit Analysis (IEC 60909 compliant)
- Arc Flash Analysis (IEEE 1584-2018)
- Harmonic Analysis (IEEE 519-2022)
- Protection Coordination (IEC 60255 relay curves)
- 25 Specialized AI Agents with rule-based expert system
- 10 IEEE/IEC engineering standards supported
- REST API with Swagger docs at `/docs`
- Computer Use Agent (Browser CUA) via Playwright + Gemini Vision
- Life-safety system with kill-switch + tamper-evident audit chain

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Platform homepage |
| `GET /healthz` | Liveness probe |
| `GET /readyz` | Readiness probe |
| `GET /health` | Detailed health check |
| `GET /docs` | Swagger API documentation |
| `GET /redoc` | ReDoc API documentation |
| `GET /api/v1/agents` | List all AI agents |
| `GET /api/v1/info` | Platform metadata |
| `GET /api/v1/knowledge` | Knowledge base info |
| `POST /api/v1/agents/etap-expert/chat` | Chat with ETAP Expert agent |
| `POST /api/v1/agents/etap-gui/execute` | Execute Browser CUA loop |
| `POST /api/v1/studies/run` | Run engineering study |
| `POST /api/v1/context/impact` | Code Property Graph impact analysis |

## Quick Test

```bash
# Health check
curl https://ahmdelbaz28-ahmedetap.hf.space/healthz

# List agents
curl https://ahmdelbaz28-ahmedetap.hf.space/api/v1/agents

# Chat with ETAP Expert (cable sizing — needs ft + V format)
curl -X POST https://ahmdelbaz28-ahmedetap.hf.space/api/v1/agents/etap-expert/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"cable sizing for 200A load, 250 ft run, 480V system"}'
```

## Platform Stats

| Metric | Value |
|--------|-------|
| AI Agents | 25 (rule-based expert system) |
| ETAP Manuals | 35 |
| Zenon SCADA Guides | 4 |
| Engineering Standards | 10 (IEEE/IEC) |
| Study Types | 15 |

## Securing the API (Optional)

By default the HF Space deployment is open (no authentication) so visitors can
explore the API. To require an API key:

1. Go to the Space **Settings** tab on Hugging Face.
2. Add a new secret named `HF_API_KEY` with a strong random value.
3. Restart the Space.

All non-public endpoints (everything except `/`, `/healthz`, `/readyz`,
`/health`, `/ready`, `/docs`, `/redoc`, `/openapi.json`, `/metrics`) will then
require the header `x-api-key: <your-key>`.

## ML / Predictive Analytics

The `/api/v1/ml/capabilities`, `/api/v1/predict/load`, and
`/api/v1/predict/anomaly` endpoints require `numpy` + `scikit-learn`. On HF
Space cpu-basic hardware these are intentionally omitted to keep the image
small. The endpoints return a clear 503 with a `deployment_note` explaining
how to enable them on a self-hosted deployment.

## Links

- [GitHub Repository](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-)
- [Author Email](mailto:ahmdelbaz28@gmail.com)
