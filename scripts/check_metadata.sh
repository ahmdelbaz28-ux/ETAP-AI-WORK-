#!/usr/bin/env bash
# Check metadata frontmatter and TOC on major documentation files
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "==> Running Metadata and Structure Verification..."
python "${SCRIPT_DIR}/check_metadata.py"
