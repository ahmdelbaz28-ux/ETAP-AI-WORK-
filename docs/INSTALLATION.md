# AhmedETAP Platform — Installation Guide

## Prerequisites

- **Python 3.12+** (tested on Python 3.12 and 3.13)
- **Node.js 20+** and npm / pnpm (for frontend UI and Mastra CLI)
- **Git** 2.30+
- **ETAP** 2021/2022 (optional, required only for Windows COM automation)

---

## Quick Start (Development)

```bash
# 1. Clone the repository
git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
cd ETAP-AI-WORK-

# 2. Create environment configuration
cp .env.example .env
# Edit .env and configure secrets and database credentials:
#   JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
#   ENGINEERING_SERVICE_API_KEY=<your-service-key>

# 3. Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Start the FastAPI backend engine
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
# Or start the engineering service directly:
python engineering_service.py

# 6. Install and start the Chat-First v3.0 frontend
cd ui
npm install
npm run dev
# The UI will be available at http://localhost:5173

# 7. Run validation and automated test suites
pytest tests/ -q
cd ui && npx vitest run
```

---

## Docker Deployment (Production)

```bash
# 1. Set required production environment variables
export JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export ENGINEERING_SERVICE_API_KEY="your-production-key"
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/etap_prod"

# 2. Build and run with Docker Compose
docker compose up -d

# 3. Verify health check
curl http://localhost:8000/health
# Expected output: {"status":"healthy","version":"2.1.0"}
```

---

## Environment Variables Reference

| Variable | Description | Default / Example |
|---|---|---|
| `JWT_SECRET_KEY` | 256-bit secret for signing user tokens | `openssl rand -hex 32` |
| `ENGINEERING_SERVICE_API_KEY` | Fail-closed API key for backend routes | `secret-api-key` |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql+asyncpg://...` |
| `ETAP_INSTALL_PATH` | Installation directory of ETAP (Windows) | `C:\ETAP 210` |
| `ETAP_VERSION` | Installed ETAP software version | `21.0` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse LLM tracing public key | `pk-lf-...` |
| `LANGFUSE_SECRET_KEY` | Langfuse LLM tracing secret key | `sk-lf-...` |