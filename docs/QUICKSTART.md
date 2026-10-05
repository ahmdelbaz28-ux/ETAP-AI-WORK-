# AhmedETAP Platform — Quick Start Guide

**AhmedETAP Virtual Power System Engineering Platform v2.1.0**

---

## 1. Prerequisites

- **Python**: 3.12 or 3.13
- **Node.js**: 20+ (with npm or pnpm)
- **Git**: 2.30+
- **Docker**: Optional, for containerized deployments

---

## 2. Installation & Setup

### Method 1: Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
   cd ETAP-AI-WORK-
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Set JWT_SECRET_KEY and ENGINEERING_SERVICE_API_KEY
   ```

3. **Install Python dependencies:**
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Start the FastAPI backend:**
   ```bash
   uvicorn api.main:app --port 8000 --reload
   ```

5. **Start the Chat-First v3.0 frontend:**
   ```bash
   cd ui
   npm install
   npm run dev
   # Open browser at http://localhost:5173
   ```

### Method 2: Docker Compose

```bash
git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
cd ETAP-AI-WORK-
docker compose up -d
# Access the platform at http://localhost:8000
```

---

## 3. Running Your First Study

### In-Chat Natural Language Query
Navigate to the ChatWorkspace UI at `http://localhost:5173` and type:
```text
Run load flow on the IEEE 9-bus WSCC test feeder with 0.001 MVA convergence tolerance.
```
The Coordinator Agent will parse your request, route it to the Load Flow Agent, execute Newton-Raphson solver via `engine/dispatch.py`, and return structured bus voltages, loading percentages, and compliance tables.

### Programmatic REST API
```bash
curl -X POST http://localhost:8000/api/v1/studies/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ENGINEERING_SERVICE_API_KEY" \
  -d '{
    "study_type": "load_flow",
    "parameters": {
      "system_id": "ieee_9bus",
      "max_iterations": 20,
      "tolerance": 0.001
    }
  }'
```