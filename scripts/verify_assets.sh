#!/usr/bin/env bash
# Verify all media assets in documentation
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "==> Running Media Assets Verification..."
python "${SCRIPT_DIR}/verify_assets.py"
