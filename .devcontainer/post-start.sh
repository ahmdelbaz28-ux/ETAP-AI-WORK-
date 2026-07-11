#!/usr/bin/env bash
# AhmedETAP — devcontainer post-start script
# Runs EVERY TIME the container starts (not just on create).
# Goal: print a quick status snapshot so the developer knows what's running.
# ============================================================================

set -euo pipefail

echo ""
echo "── AhmedETAP Dev Container ────────────────────────────────────"
echo "  Branch:  $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'detached')"
echo "  Python:  $(python --version 2>&1 || echo 'not found')"
echo "  Node:    $(node --version 2>&1 || echo 'not found')"
echo "  Disk:    $(df -h /workspace 2>/dev/null | awk 'NR==2 {print $4 " free"}' || echo 'n/a')"
echo "───────────────────────────────────────────────────────────────"

# Show recently modified files (last 5 commits) for context
if command -v git >/dev/null 2>&1; then
  echo "  Recent commits:"
  git log --oneline -5 2>/dev/null | sed 's/^/    /' || true
fi
echo ""
