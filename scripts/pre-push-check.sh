#!/bin/bash
# Pre-push Safety Check for AhmedETAP repo
# Run this BEFORE every `git push` to protect concurrent agents' work.
set -e

REPO_DIR="${1:-/home/z/my-project/audit/ETAP-AI-WORK-}"
cd "$REPO_DIR" || { echo "✗ Cannot cd to $REPO_DIR"; exit 2; }

echo "=========================================="
echo "  Pre-push Safety Check — AhmedETAP"
echo "=========================================="
echo ""

# 1. Branch check
BRANCH=$(git branch --show-current)
if [ "$BRANCH" = "main" ] || [ -z "$BRANCH" ]; then
  echo "✗ REFUSE: on 'main' or detached HEAD — cannot push directly"
  echo "  Create a feature branch first: git checkout -b audit/critical-fixes-YYYY-MM-DD"
  exit 1
fi
echo "✓ [1/8] Branch: $BRANCH (not main)"

# 2. Clean working tree (only allow .agents-coordination.md to be modified)
DIRTY=$(git status --porcelain | grep -v "^.. .agents-coordination.md$" || true)
if [ -n "$DIRTY" ]; then
  echo "✗ REFUSE: uncommitted changes (excluding .agents-coordination.md):"
  echo "$DIRTY"
  echo ""
  echo "  Commit or stash first."
  exit 1
fi
echo "✓ [2/8] Working tree clean (or only coordination file modified)"

# 3. Fetch latest from origin
echo "→ Fetching origin..."
git fetch origin --quiet
echo "✓ [3/8] Fetched latest from origin"

# 4. Check for new commits on origin/main
NEW_COMMITS=$(git log HEAD..origin/main --oneline 2>/dev/null || true)
if [ -n "$NEW_COMMITS" ]; then
  echo "⚠ [4/8] origin/main has new commits from other agents:"
  echo "$NEW_COMMITS"
  echo ""
  echo "  You MUST rebase before pushing:"
  echo "    git rebase origin/main"
  echo "  Resolve any conflicts, then re-run this check."
  exit 1
fi
echo "✓ [4/8] Up to date with origin/main (no other agent pushed)"

# 5. No real .env files in diff (allow .env.example which contains only placeholders)
ENV_FILES=$(git diff origin/main --name-only 2>/dev/null | grep -E "^\.env" | grep -v "^\.env\.example" || true)
if [ -n "$ENV_FILES" ]; then
  echo "✗ REFUSE: .env file(s) in diff — secrets would leak:"
  echo "$ENV_FILES"
  exit 1
fi
echo "✓ [5/8] No real .env files in diff (.env.example allowed)"

# 6. Scan diff for real-looking secrets
SECRETS=$(git diff origin/main 2>/dev/null | grep -iE \
  "(sb_secret_[A-Za-z0-9_-]{20,}|sbp_[a-f0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|hf_[A-Za-z0-9]{30,}|vcp_[A-Za-z0-9]{30,}|sk-lf-[a-f0-9-]{30,}|pk-lf-[a-f0-9-]{30,}|napi_[A-Za-z0-9]{40,}|cfut_[A-Za-z0-9]{30,}|re_[A-Za-z0-9]{20,}|dtn_[a-f0-9]{40,}|csb_v1_[A-Za-z0-9_-]{30,})" \
  | head -10 || true)
if [ -n "$SECRETS" ]; then
  echo "✗ REFUSE: real-looking secrets detected in diff:"
  echo "$SECRETS"
  echo ""
  echo "  Rotate the secret, remove from code, and use env vars instead."
  exit 1
fi
echo "✓ [6/8] No real-looking secrets in diff"

# 7. Check .agents-coordination.md was updated
if ! git diff --cached --name-only | grep -q ".agents-coordination.md"; then
  if ! git diff origin/main --name-only 2>/dev/null | grep -q ".agents-coordination.md"; then
    echo "⚠ [7/8] .agents-coordination.md NOT updated"
    echo "  Update Push Log in .agents-coordination.md before pushing:"
    echo "    - Timestamp (UTC+3)"
    echo "    - Branch: $BRANCH"
    echo "    - Commit SHA: $(git rev-parse HEAD)"
    echo "    - Action: 'pushing'"
    echo ""
    read -p "  Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "✗ Aborted by user"
      exit 1
    fi
  else
    echo "✓ [7/8] .agents-coordination.md updated"
  fi
else
  echo "✓ [7/8] .agents-coordination.md staged"
fi

# 8. Commit message format check (last 5 commits)
echo "→ Checking recent commit messages..."
BAD_COMMITS=$(git log --format="%H %s" -5 | grep -vE "^[a-f0-9]+ (fix|feat|chore|docs|ci|refactor|test|style|perf|build|revert)\(([a-z0-9_-]+)\): .+ \[E-[0-9]+\]$" | grep -vE "^[a-f0-9]+ (fix|feat|chore|docs|ci|refactor|test|style|perf|build|revert): .+" || true)
if [ -n "$BAD_COMMITS" ]; then
  echo "⚠ [8/8] Some recent commits don't follow conventional format:"
  echo "$BAD_COMMITS"
  echo ""
  echo "  Expected: fix(severity): description [E-XX]"
else
  echo "✓ [8/8] Recent commits follow conventional format"
fi

# 9. Python import check — verify all modified .py files parse and imports resolve
echo "→ Checking Python imports in modified files..."
PY_FILES=$(git diff origin/main --name-only 2>/dev/null | grep '\.py$' || true)
IMPORT_ERRORS=0
for f in $PY_FILES; do
  if [ -f "$f" ]; then
    # Check syntax
    if ! python3 -c "import ast; ast.parse(open('$f').read())" 2>/dev/null; then
      echo "  ✗ SYNTAX ERROR in $f"
      IMPORT_ERRORS=$((IMPORT_ERRORS + 1))
    fi
    # Check for common missing imports: Depends, get_api_key, Request, etc.
    # used in decorators but not imported
    if grep -q "Depends(" "$f" && ! grep -q "from fastapi import.*Depends\|from fastapi import Depends" "$f" && ! grep -q "import Depends" "$f"; then
      # Check if Depends is imported via wildcard or star import
      if ! grep -q "from fastapi import \*" "$f"; then
        echo "  ⚠ POSSIBLE MISSING IMPORT: Depends used in $f but not imported"
        IMPORT_ERRORS=$((IMPORT_ERRORS + 1))
      fi
    fi
    if grep -q "get_api_key(" "$f" && ! grep -qE "from api\.dependencies import.*get_api_key|import get_api_key" "$f"; then
      echo "  ⚠ POSSIBLE MISSING IMPORT: get_api_key used in $f but not imported"
      IMPORT_ERRORS=$((IMPORT_ERRORS + 1))
    fi
    if grep -q "get_current_user_from_header(" "$f" && ! grep -qE "from api\.dependencies import.*get_current_user_from_header" "$f"; then
      echo "  ⚠ POSSIBLE MISSING IMPORT: get_current_user_from_header used in $f but not imported"
      IMPORT_ERRORS=$((IMPORT_ERRORS + 1))
    fi
  fi
done
if [ "$IMPORT_ERRORS" -gt 0 ]; then
  echo "  ⚠ $IMPORT_FILES import warnings — review before pushing"
else
  echo "✓ [9/9] Python imports look correct"
fi

echo ""
echo "=========================================="
echo "  ✅ ALL CHECKS PASSED — safe to push"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. git push origin $BRANCH"
echo "  2. Open PR on GitHub with title: 'fix(severity): description [E-XX]'"
echo "  3. Wait for CI to pass"
echo "  4. Only merge after CI green + your review"
echo "  5. Update .agents-coordination.md with PR URL after merge"
echo ""
echo "Branch: $BRANCH"
echo "Latest commit: $(git rev-parse --short HEAD)"
echo "Message: $(git log -1 --format=%s)"
