#!/usr/bin/env bash
# =============================================================================
# vercel-build.sh — Safe Vercel build wrapper for the ETAP Vite/React UI
# =============================================================================
# This script exists to prevent regressions of the 520-failed-deploys incident,
# which was caused by Vercel auto-detecting MkDocs (mkdocs.yml at repo root)
# and overriding the framework: vite setting in vercel.json.
#
# Pre-flight checks (fail fast before Vercel wastes a build):
#   1. mkdocs.yml MUST NOT exist at repo root (would trigger Vercel MkDocs auto-detect)
#   2. ui/package.json MUST exist (the actual app we are deploying)
#   3. mkdocs.yml SHOULD exist at docs/mkdocs.yml (the intentional location)
#
# Then runs the real build:
#   1. npm --prefix ui install --no-audit --no-fund
#   2. npm --prefix ui run build:vercel
#   3. verify ui/dist/index.html exists before exiting
#
# Exit codes:
#   0 — build succeeded, ui/dist/ populated
#   1 — pre-flight check failed (fix the repo, then redeploy)
#   2 — npm install failed
#   3 — vite build failed
#   4 — build reported success but ui/dist/index.html is missing
# =============================================================================
set -euo pipefail

echo "================================================================"
echo " vercel-build.sh — Vite UI build wrapper"
echo " repo root: $(pwd)"
echo " node:      $(node --version 2>/dev/null || echo 'NOT FOUND')"
echo " npm:       $(npm --version 2>/dev/null || echo 'NOT FOUND')"
echo "================================================================"

# -----------------------------------------------------------------------------
# Pre-flight check 1: mkdocs.yml MUST NOT be at repo root
# -----------------------------------------------------------------------------
if [[ -f mkdocs.yml ]]; then
  echo ""
  echo "❌ PRE-FLIGHT FAIL: mkdocs.yml exists at repo root."
  echo "   This will cause Vercel to auto-detect MkDocs and override the"
  echo "   framework: vite setting in vercel.json — which is what caused the"
  echo "   520-failed-deploys incident in the first place."
  echo ""
  echo "   Fix: move mkdocs.yml into docs/ (the intentional location):"
  echo "       git mv mkdocs.yml docs/mkdocs.yml"
  echo "       # and add 'docs_dir: .' inside docs/mkdocs.yml"
  echo ""
  exit 1
fi
echo "✓ Pre-flight 1: no mkdocs.yml at repo root"

# -----------------------------------------------------------------------------
# Pre-flight check 2: ui/package.json MUST exist
# -----------------------------------------------------------------------------
if [[ ! -f ui/package.json ]]; then
  echo ""
  echo "❌ PRE-FLIGHT FAIL: ui/package.json not found."
  echo "   This script expects the Vite/React UI to live in ui/."
  echo ""
  exit 1
fi
echo "✓ Pre-flight 2: ui/package.json present"

# -----------------------------------------------------------------------------
# Pre-flight check 3: docs/mkdocs.yml SHOULD exist (warning only, not fatal)
# -----------------------------------------------------------------------------
if [[ ! -f docs/mkdocs.yml ]]; then
  echo "⚠  docs/mkdocs.yml not found — MkDocs config has been moved or removed."
  echo "   This is just a warning; the Vite UI build will proceed."
else
  echo "✓ Pre-flight 3: docs/mkdocs.yml present (MkDocs is correctly nested)"
fi

# -----------------------------------------------------------------------------
# Step 1: verify npm install already happened (Vercel runs installCommand first)
# -----------------------------------------------------------------------------
echo ""
echo "=== Step 1/3: verify node_modules present ==="
if [[ ! -d ui/node_modules ]]; then
  echo ""
  echo "⚠  ui/node_modules missing — running npm install now as fallback..."
  if ! npm --prefix ui install --no-audit --no-fund; then
    echo ""
    echo "❌ npm install failed for ui/"
    exit 2
  fi
else
  echo "✓ ui/node_modules present (Vercel installCommand already ran)"
fi

# -----------------------------------------------------------------------------
# Step 2: vite build
# -----------------------------------------------------------------------------
echo ""
echo "=== Step 2/3: vite build (ui/) ==="
if ! npm --prefix ui run build:vercel; then
  echo ""
  echo "❌ vite build failed (npm run build:vercel)"
  exit 3
fi
echo "✓ vite build completed"

# -----------------------------------------------------------------------------
# Step 3: verify output
# -----------------------------------------------------------------------------
echo ""
echo "=== Step 3/3: verify output ==="
if [[ ! -f ui/dist/index.html ]]; then
  echo ""
  echo "❌ Build reported success but ui/dist/index.html is missing."
  echo "   Contents of ui/dist/:"
  ls -la ui/dist/ 2>&1 | head -20 || echo "   (ui/dist/ does not exist)"
  exit 4
fi
echo "✓ ui/dist/index.html present"

echo ""
echo "================================================================"
echo " BUILD SUCCEEDED"
echo " output: $(pwd)/ui/dist/"
echo "================================================================"
ls -la ui/dist/ | head -15
exit 0
