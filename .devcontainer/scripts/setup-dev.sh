#!/usr/bin/env bash
set -euo pipefail

echo "=== AhmedETAP Platform — Devcontainer Setup ==="

# ── Virtual environment ─────────────────────────────────────────────────────
if [ ! -d ".venv312" ]; then
    echo "[1/4] Creating Python 3.12 virtual environment..."
    python -m venv .venv312
else
    echo "[1/4] Virtual environment already exists — skipping"
fi

echo "[2/4] Installing Python dependencies..."
.venv312/bin/pip install --upgrade pip setuptools wheel
.venv312/bin/pip install -r requirements.txt
.venv312/bin/pip install -r requirements-dev.txt

# ── Node.js / pnpm ──────────────────────────────────────────────────────────
echo "[3/4] Installing Node.js workspace dependencies..."
corepack enable || true
pnpm install --no-frozen-lockfile

# ── Node sandbox native addon ───────────────────────────────────────────────
# isolated-vm@7 requires Node 22+ and a working node-gyp toolchain.
# build-essential and python3-dev are pre-installed in the devcontainer image.
echo "[4/4] Installing isolated-vm (Node sandbox native addon)..."
pnpm add -D isolated-vm@7.0.0 --no-save 2>&1 || \
    echo "  ⚠  isolated-vm install failed — Node sandbox will be disabled in dev"
echo "  → Run 'pnpm rebuild isolated-vm' after container start to retry."

echo ""
echo "✅ Devcontainer setup complete!"
echo "   Backend:  source .venv312/bin/activate && python engineering_service.py"
echo "   Frontend: pnpm dev"
echo "   Docker:   docker-compose up -d    (from host terminal, not devcontainer)"
