# =============================================================================
# Branch Protection & PR Checks
# Per the ci-cd-and-automation skill: Required reviews, status checks, branch protection
# =============================================================================

# This file documents the recommended branch protection settings.
# Apply them manually in GitHub Settings → Branches → Branch protection rules.

# ── Recommended Branch Protection Rules for `main` ──────────────────────────
#
# 1. Require a pull request before merging
#    - Require approvals: 1
#    - Dismiss stale pull request approvals when new commits are pushed
#    - Require review from Code Owners
#
# 2. Require status checks to pass before merging
#    - Require branches to be up to date before merging
#    - Status checks required:
#      - Lint
#      - Type Check
#      - Unit Tests
#      - Build
#      - Integration Tests
#      - Security Audit
#      - Bundle Size Check
#
# 3. Require conversation resolution before merging
#
# 4. Do not allow force pushes
#
# 5. Do not allow deletions
#
# 6. Auto-merge: Enable if all checks pass and approved
#
# ── CODEOWNERS ──────────────────────────────────────────────────────────────
# Place in .github/CODEOWNERS
# * @maintainer
# .github/workflows/ @devops
