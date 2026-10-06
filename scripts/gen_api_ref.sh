#!/usr/bin/env bash
# Generate API Quick Reference from Canonical Reference
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Running API Quick Reference Generator..."
python3 "${SCRIPT_DIR}/gen_api_ref.py" "$@"
echo "API Quick Reference check/sync completed successfully."
