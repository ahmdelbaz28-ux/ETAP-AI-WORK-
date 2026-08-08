#!/usr/bin/env bash
# AhmedETAP — devcontainer post-create script
# Runs ONCE when the dev container is first created.
# Goal: install all project dependencies so the workspace is ready to code.
# Safe to re-run (idempotent checks before each step).
# ============================================================================

set -euo pipefail

echo "═══════════════════════════════════════════════════════════════"
echo "  AhmedETAP — Dev Container Setup (post-create)"
echo "═══════════════════════════════════════════════════════════════"

# ─── 1. Python environment ────────────────────────────────────────────────────
echo "▶ [1/6] Python: upgrading pip, installing ruff/uv"
python -m pip install --upgrade pip --quiet
pip install --quiet ruff uv 2>/dev/null || echo "  ⚠ ruff/uv install skipped (offline?)"

# Install core Python deps (use requirements-minimal to keep memory low on free tiers)
if [[ -f requirements.txt ]]; then
  echo "▶ [2/6] Python: installing requirements.txt"
  if pip install --quiet -r requirements.txt 2>/dev/null; then
    echo "  ✓ Full requirements installed"
  else
    echo "  ⚠ Full requirements failed, falling back to requirements-minimal.txt"
    [[ -f requirements-minimal.txt ]] && pip install --quiet -r requirements-minimal.txt || true
  fi
else
  echo "▶ [2/6] No requirements.txt found — skipping"
fi

# ─── 3. Node.js / UI ─────────────────────────────────────────────────────────
echo "▶ [3/6] Node: verifying version"
node --version
npm --version

if [[ -f ui/package.json ]]; then
  echo "▶ [4/6] UI: installing npm dependencies (this may take 2-4 min)"
  cd ui
  if [[ -f package-lock.json ]]; then
    npm ci --no-audit --no-fund --ignore-scripts 2>/dev/null \
      || npm install --no-audit --no-fund --ignore-scripts 2>/dev/null \
      || echo "  ⚠ npm install partially failed — UI features may be limited"
  else
    npm install --no-audit --no-fund --ignore-scripts 2>/dev/null \
      || echo "  ⚠ npm install failed"
  fi
  cd ..
  echo "  ✓ UI dependencies installed"
else
  echo "▶ [4/6] No ui/package.json — skipping UI install"
fi

# ─── 5. Playwright (already installed via feature, just verify) ───────────────
echo "▶ [5/6] Playwright: verifying Chromium"
if command -v playwright >/dev/null 2>&1; then
  playwright install chromium 2>/dev/null || echo "  ⚠ Playwright Chromium install skipped"
else
  echo "  ⚠ Playwright CLI not on PATH — install manually if needed"
fi

# ─── 6. Final touches ────────────────────────────────────────────────────────
echo "▶ [6/6] Final touches"

# Create .env from template if missing (developer must fill real values)
if [[ ! -f .env ]] && [[ -f .env.example ]]; then
  cp .env.example .env
  echo "  ✓ Created .env from .env.example — fill in real values before running"
fi

# Helpful tip
cat <<'TIP'

═══════════════════════════════════════════════════════════════
  ✅ Dev container ready!
═══════════════════════════════════════════════════════════════

  Next steps:
    1. Edit .env and fill in your real credentials
    2. Start backend:  bash quickstart.sh   (or: uvicorn engineering_service:app --reload)
    3. Start UI:       cd ui && npm run dev
    4. Open:           http://localhost:5173

  Docs:    docs/DEVELOPER_GUIDE.md
  Health:  http://localhost:8000/health

TIP

echo "Done."
