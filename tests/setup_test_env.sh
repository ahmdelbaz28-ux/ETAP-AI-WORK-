#!/bin/bash
# Test environment setup script
# Installs all dependencies needed to run the API server and tests locally.
#
# Usage:
#   bash tests/setup_test_env.sh
#
# This script is idempotent — safe to run multiple times.

set -e

echo "=== AhmedETAP Test Environment Setup ==="
echo ""

# 1. Install Python dependencies from requirements.hf.txt
echo "[1/3] Installing Python dependencies from hf-space/requirements.hf.txt..."
pip install --break-system-packages -r hf-space/requirements.hf.txt 2>&1 | tail -5

# 2. Install additional test dependencies
echo ""
echo "[2/3] Installing test dependencies (selenium, pytest)..."
pip install --break-system-packages selenium pytest pytest-asyncio 2>&1 | tail -3

# 3. Install Node.js dependencies for Selenium IDE runner (optional)
echo ""
echo "[3/3] Installing Node.js dependencies (selenium-side-runner, chromedriver)..."
npm install -g selenium-side-runner chromedriver 2>&1 | tail -3 || echo "  (skipped — npm not available or already installed)"

echo ""
echo "=== Setup complete ==="
echo ""
echo "To start the API server:"
echo "  python3 -c \""
echo "  import sys, os"
echo "  sys.path.insert(0, 'hf-space')"
echo "  sys.path.insert(0, '.')"
echo "  os.environ['ENVIRONMENT'] = 'development'"
echo "  os.environ['ENGINEERING_SERVICE_AUTH_DISABLED'] = 'true'"
echo "  import uvicorn"
echo "  from app import app"
echo "  uvicorn.run(app, host='127.0.0.1', port=7860, log_level='warning')"
echo "  \" &"
echo ""
echo "To run tests:"
echo "  python3 tests/selenium/test_api_values.py"
echo "  python3 tests/selenium/test_ui_real.py"
