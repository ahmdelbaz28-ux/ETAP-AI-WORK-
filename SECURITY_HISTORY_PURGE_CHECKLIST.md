# Security: Git History Secret Purge Checklist

> **Source**: `AhmedETAP_Error_Report_AR.pdf` — HIGH #10
> **Status**: ⚠️ Pending — requires manual execution by repository admin
> **Severity**: HIGH — a TestSprite MCP `API_KEY` was committed to git history
> in `.mcp.json` and remains recoverable from old commits even though the file
> is now in `.gitignore` and removed from `HEAD`.

## 1. Identify the leaked secret

A TestSprite MCP API key was committed in `.mcp.json` and is recoverable
from git history in these commits:

```bash
git log --all -p -- .mcp.json | grep -E "^\+.*API_KEY"
```

Output (redacted):

```
+        "API_KEY": "***REDACTED-TESTSPRITE-KEY-PREFIX***"
```

The key is **already rotated** at TestSprite (the `.mcp.json.example`
placeholder uses `${TESTSPRITE_API_KEY}` env var), but the **literal string
remains in git history** and must be purged to comply with security best
practice.

## 2. Pre-purge checklist (DO THIS BEFORE running BFG)

- [ ] **Rotate the leaked secret at TestSprite** — even though it's been
      removed from `HEAD`, anyone with read access to the repo can recover
      it from git history. Treat it as compromised.
- [ ] **Notify all collaborators** — `git push --force` after history
      rewrite will require everyone to re-clone or `git reset --hard origin/main`.
- [ ] **Backup the repo** — `git clone --mirror <repo> repo-backup.git`
      so you can restore if anything goes wrong.
- [ ] **Verify no open PRs** depend on the commits you're about to rewrite.
- [ ] **Confirm you have admin access** to the GitHub repo (required for
      `git push --force` to a protected branch).

## 3. Purge with BFG Repo-Cleaner (recommended)

```bash
# 1. Mirror-clone the repo (BFG requires a bare mirror)
git clone --mirror https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git etap-mirror.git

# 2. Create a secrets.txt file with the literal strings to remove
#    (one per line; BFG replaces them with `***REMOVED***`)
cat > secrets.txt <<'EOF'
***REDACTED-TESTSPRITE-KEY***
EOF

# 3. Run BFG (requires Java)
bfg --replace-text secrets.txt etap-mirror.git

# 4. Clean up the reflog and gc the mirror
cd etap-mirror.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 5. Force-push the cleaned history
git push --force
```

## 4. Alternative: git filter-repo (if BFG unavailable)

```bash
pip install git-filter-repo

# Mirror-clone
git clone --mirror https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git etap-mirror.git
cd etap-mirror.git

# Remove .mcp.json from ALL commits
git filter-repo --invert-paths --path .mcp.json

# Force-push
git push --force
```

## 5. Post-purge checklist

- [ ] **Verify the secret is gone**: `git log --all -p | grep "***REDACTED***"`
      should return nothing.
- [ ] **Verify `.mcp.json` is no longer in any commit**:
      `git log --all -- .mcp.json` should return nothing.
- [ ] **Notify collaborators** to re-clone the repo (their local clones
      still contain the old history with the secret).
- [ ] **Trigger CI** to make sure nothing breaks (`.mcp.json` is in
      `.gitignore` so it should never be required by CI).
- [ ] **Update HuggingFace Space** by triggering a redeploy (the
      `sync-platforms.yml` workflow will do this automatically on push).
- [ ] **Audit other secret patterns** in git history:
      ```bash
      git log --all -p | grep -E "(ghp_[a-zA-Z0-9]{36}|hf_[a-zA-Z0-9]{30,}|sk-[a-zA-Z0-9]{20,})"
      ```
      If anything shows up, repeat the purge for those secrets.

## 6. Prevention: pre-commit hook

A `.pre-commit-config.yaml` is already in the repo. Make sure it includes
`detect-secrets` or `gitleaks` so future commits are scanned:

```yaml
# Already configured — see .pre-commit-config.yaml in the repo root
- repo: https://github.com/Yelp/detect-secrets
  rev: v1.5.0
  hooks:
    - id: detect-secrets
      args: ['--baseline', '.secrets.baseline']
```

If `.secrets.baseline` doesn't exist yet, generate it:

```bash
detect-secrets scan > .secrets.baseline
git add .secrets.baseline
git commit -m "chore: add detect-secrets baseline"
```

## 7. Status tracking

| Step | Status | Owner | Date |
|------|--------|-------|------|
| Rotate TestSprite API key | ⬜ Pending | repo admin | — |
| Backup mirror clone | ⬜ Pending | repo admin | — |
| Run BFG / filter-repo | ⬜ Pending | repo admin | — |
| Force-push cleaned history | ⬜ Pending | repo admin | — |
| Notify collaborators | ⬜ Pending | repo admin | — |
| Verify secret gone | ⬜ Pending | repo admin | — |
| Audit other secrets | ⬜ Pending | repo admin | — |
| Generate detect-secrets baseline | ⬜ Pending | repo admin | — |

---

**Note**: This checklist is a *manual* procedure because rewriting git history
is destructive and cannot be automated safely from inside a CI/CD pipeline.
The repo admin must execute it locally and force-push. The `.gitignore` and
`.mcp.json.example` placeholder already prevent future leaks — this checklist
only addresses the *historical* leak.
