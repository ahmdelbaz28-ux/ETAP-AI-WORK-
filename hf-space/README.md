---
title: AhmedETAP
emoji: ⚡
colorFrom: yellow
colorTo: red
sdk: docker
pinned: true
license: mit
app_port: 7860
short_description: Enterprise AI Engineering Platform — Power Systems Analysis
---

# ⚡ AhmedETAP — Enterprise Engineering Intelligence Platform

**Developed by Eng. Ahmed Elbaz** | v2.1.0

Enterprise-grade autonomous AI engineering platform for power system analysis, ETAP automation, and AI-powered engineering decision support — powered by **25 specialized AI agents** backed by **35 ETAP manuals** and **4 Zenon SCADA guides** as primary knowledge base.

---

## 🎯 Capabilities

| Study Type | Standard | Agent |
|---|---|---|
| Load Flow Analysis | IEEE 3002.7 | `load-flow-agent` |
| Short Circuit Analysis | IEC 60909 | `short-circuit-agent` |
| Arc Flash Analysis | IEEE 1584-2018 | `arcflash-agent` |
| Protection Coordination | IEC 60255 | `protection-agent` |
| Motor Starting | IEEE 399 | `motorstarting-agent` |
| Transient Stability | IEEE 399 | `stability-agent` |
| Harmonic Analysis | IEEE 519-2022 | `harmonic-agent` |
| Cable Sizing | IEC 60364 | `cable-sizing-agent` |
| Earth Grid Design | IEEE 80 | `earth-grid-agent` |
| Optimal Power Flow | IEEE 3002.7 | `opf-agent` |
| Renewable Integration | IEEE 1547 | `renewable-agent` |
| Battery Storage (BESS) | IEC 62933 | `battery-storage-agent` |
| SCADA (Zenon) | IEC 61850 | `scada-agent` |
| Digital Twin | IEC 61970 | `digital-twin-agent` |

---

## 🔌 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Platform dashboard (HTML) |
| `/healthz` | GET/HEAD | Liveness probe |
| `/readyz` | GET | Readiness probe |
| `/health` | GET | Detailed health status |
| `/docs` | GET | Swagger UI |
| `/redoc` | GET | ReDoc documentation |
| `/api/v1/info` | GET | Platform info |
| `/api/v1/agents` | GET | List all 25 AI agents |
| `/api/v1/agents/{id}` | GET | Get specific agent info |
| `/api/v1/studies/types` | GET | Available study types |
| `/api/v1/studies/run` | POST | Run engineering study |
| `/api/v1/knowledge` | GET | Knowledge base info |
| `/metrics` | GET | Platform metrics |

---

## 🚀 Quick Test

```bash
# Health check
curl https://ahmdelbaz28-ahmedetap.hf.space/healthz

# List all agents
curl https://ahmdelbaz28-ahmedetap.hf.space/api/v1/agents

# Run a load flow study
curl -X POST https://ahmdelbaz28-ahmedetap.hf.space/api/v1/studies/run \
  -H "Content-Type: application/json" \
  -d '{
    "study_type": "load_flow",
    "system": {
      "base_mva": 100,
      "buses": [
        {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.0},
        {"bus_id": 2, "bus_type": "pq", "load_power_real": 1.0}
      ],
      "lines": [
        {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05}
      ]
    }
  }'
```

---

## 📊 Platform Stats

| Metric | Value |
|---|---|
| AI Agents | 25 specialized |
| ETAP Manuals | 35 documents |
| Zenon Guides | 4 SCADA documents |
| Standards | 10 IEEE/IEC |
| Tests | 1680+ passing |
| Study Types | 15 |

---

## 🔗 Links

- [GitHub Repository](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-)
- [API Documentation](https://ahmdelbaz28-ahmedetap.hf.space/docs)
- [Author Email](mailto:ahmdelbaz28@gmail.com)
