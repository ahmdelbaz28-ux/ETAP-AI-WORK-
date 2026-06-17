---
title: AhmedETAP
emoji: "⚡"
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
license: mit
app_port: 7860
---

# AhmedETAP - Enterprise Engineering Intelligence Platform

**Developed by Eng. Ahmed Elbaz**

Enterprise-grade autonomous engineering intelligence for power-system analysis, ETAP automation, and AI-powered engineering decision support.

## Features

- Load Flow Analysis (Newton-Raphson, Fast Decoupled, DC-OPF)
- Short Circuit Analysis (IEC 60909 compliant)
- Arc Flash Analysis (IEEE 1584-2018)
- Harmonic Analysis (IEEE 519-2022)
- Protection Coordination (IEC 60255 relay curves)
- 23 Specialized AI Agents with RAG context
- REST API with Swagger docs at `/docs`

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Platform info |
| `GET /healthz` | Liveness probe |
| `GET /readyz` | Readiness probe |
| `GET /health` | Detailed health check |
| `GET /docs` | Swagger API documentation |
| `POST /api/v1/studies/run` | Run engineering study |

## Quick Test

```bash
curl https://ahmdelbaz28-ETAP-AI-Platform.hf.space/healthz
```

## Links

- [GitHub Repository](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-)
- [Author Email](mailto:ahmdelbaz28@gmail.com)
