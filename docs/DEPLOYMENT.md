# AhmedETAP Platform — Production Deployment Guide

## Docker Deployment (Recommended)

### Prerequisites
- Docker Engine 24.0+ and Docker Compose 2.20+
- Cryptographically generated secrets (`JWT_SECRET_KEY`, `ENGINEERING_SERVICE_API_KEY`)
- PostgreSQL database instance (e.g. Neon PostgreSQL, AWS RDS, or Azure Database for PostgreSQL)

### Steps

1. Configure production environment variables in `.env`:
```bash
JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
ENGINEERING_SERVICE_API_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
DATABASE_URL="postgresql+asyncpg://etapuser:etappass@postgres:5432/etap_db"
```

2. Start the full stack with Docker Compose:
```bash
docker compose -f docker-compose.yml up -d --build
```

3. Verify service health:
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","version":"2.1.0"}
```

---

## Container Security & Hardening

- Container runs as non-root service user (`engsvc` / `hfuser`).
- Read-only root filesystem with ephemeral tmpfs volumes for temporary solver files.
- Fail-closed security architecture: Missing required API keys or invalid database strings terminate boot immediately.
- Dual-control Maker-Checker enforcement on critical substation switching operations.
- Health probes configured at `/health`, `/healthz`, and `/readyz`.

---

## Standalone Host Deployment (Linux / Windows Server)

1. Clone and install dependencies:
```bash
git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
cd ETAP-AI-WORK-
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

2. Build the Chat-First v3.0 UI:
```bash
cd ui
npm install
npm run build
cd ..
```

3. Run with production ASGI server (Uvicorn / Gunicorn):
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```