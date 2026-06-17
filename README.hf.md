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
| `POST /api/v1/system/validate` | Validate system model |

## Quick Test

```bash
curl https://ahmdelbaz28-etap-ai-platform.hf.space/healthz

curl -X POST https://ahmdelbaz28-etap-ai-platform.hf.space/api/v1/studies/run \
  -H "Content-Type: application/json" \
  -d '{"study_type":"load_flow","system":{"base_mva":100,"buses":[{"bus_id":1,"bus_type":"slack","voltage_magnitude":1.0},{"bus_id":2,"bus_type":"pq","load_power_real":1.0}],"lines":[{"line_id":1,"from_bus_id":1,"to_bus_id":2,"r1":0.01,"x1":0.05}]}}'
```

## Platform Stats

| Metric | Value |
|--------|-------|
| Tests | 548 passing |
| Validation | 31/31 gates |
| AI Agents | 23 specialized |
| Standards | IEEE/IEC/NFPA |

## Links

- [GitHub Repository](https://github.com/ahmdelbaz28-ux/AhmedETAP)
- [Author Email](mailto:ahmdelbaz28@gmail.com)
