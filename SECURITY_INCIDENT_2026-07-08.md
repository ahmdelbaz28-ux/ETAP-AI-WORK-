# Security Incident Report — 2026-07-08

## Summary

On 2026-07-08, the platform owner shared live credentials for multiple services
in a plain-text chat session with an AI assistant. The credentials included
tokens for GitHub, Vercel, HuggingFace, Supabase, Langfuse, LangWatch, and
Smithery. This document records the scope of the exposure and the remediation
steps taken.

## Scope of Exposure

The following credentials were transmitted in plain chat:

| Service | Credential Type | Status at time of sharing |
|:---|:---|:---|
| GitHub | Fine-grained PAT (`github_pat_*`) | Valid — used to push commits to `main` |
| Vercel | Access token (`vcp_*`) — first batch | Already invalid (revoked before this session) |
| Vercel | Access token (`vcp_*`) — second batch | Valid — used to PATCH project, update env vars, trigger deploy |
| HuggingFace | Access token (`hf_*`) | Valid — verified via `/api/whoami-v2` |
| Supabase | Publishable key (`sb_publishable_*`) | Valid — verified via GoTrue health |
| Supabase | Secret key (`sb_secret_*`) | Valid — verified via GoTrue health |
| Supabase | PAT-like token (`sbp_*`) | Invalid — appears to be an old/revoked PAT |
| Langfuse | Public key (`pk-lf-*`) | Valid — verified via `/api/public/projects` |
| Langfuse | Secret key (`sk-lf-*`) | Valid — verified via `/api/public/projects` |
| LangWatch | API key (`sk-lw-*`) | Valid at project scope (org-level endpoints correctly reject) |
| Smithery | API key (UUID) | Could not verify via HTTP probe — set on Vercel |
| Neo4j | Three (3) opaque strings | Could not verify — OAuth flow returned proxy errors |

## Discovery During Remediation

While scanning the repository for past secret leaks, a **partial GitHub PAT
prefix** (`github_pat_11CCHF4XA0...`, first 32 chars of the random part) was
found in `worklog.md` at line 2200. This file was a development log that had
been accidentally committed to the repository by a previous author and was
still present in `HEAD`.

The full PAT was never in the repository — only the prefix. However, because
the full PAT was ALSO shared in chat, an attacker with both the chat log and
the git history would have everything needed to authenticate as the repo owner.

## Remediation Actions Taken (Automated)

1. **`worklog.md` removed from the repository.** The file was deleted from the
   working tree and `git rm`'d. It is now in `.gitignore` so it cannot be
   re-committed.
2. **`scripts/security_scan.py` extended** with new patterns for the modern
   token formats: `github_pat_*`, `hf_*`, `vcp_*`, `sb_secret_*`,
   `sb_publishable_*`, `sk-lf-*`, `pk-lf-*`, `sk-lw-*`. The previous scanner
   only caught `ghp_*` (classic PATs) and missed the fine-grained format.
3. **`.gitleaks.toml` added** with project-specific rules covering every
   service in the platform's stack.
4. **`.github/workflows/secret-scan.yml` added** — runs Gitleaks on every
   push to `main` and on every PR, plus weekly full-history scans. Also runs
   `scripts/security_scan.py` as a second layer.
5. **Vercel project env vars synced** with fresh credential values (this was
   done in the same session, before this incident report was written).

## Remediation Actions Required (Manual — Cannot Be Automated)

The following actions MUST be performed by the account owner. The AI assistant
cannot rotate credentials on behalf of the user.

### 1. Rotate every exposed credential

| Service | Rotation URL |
|:---|:---|
| GitHub PAT | https://github.com/settings/tokens |
| Vercel token | https://vercel.com/account/tokens |
| HuggingFace token | https://huggingface.co/settings/tokens |
| Supabase keys | https://supabase.com/dashboard/project/ovjttnsvwrmbvwecxbsq/settings/api |
| Langfuse keys | https://cloud.langfuse.com/settings → API keys |
| LangWatch key | https://app.langwatch.ai/settings/api-keys |
| Smithery key | https://smithery.ai/console/api-keys |

A helper script is provided at [`scripts/rotate-credentials.sh`](scripts/rotate-credentials.sh)
that opens all the rotation URLs in browser tabs at once.

### 2. After rotating, update Vercel env vars with the new values

After generating fresh credentials, update the Vercel project's env vars
either via the dashboard (Settings → Environment Variables) or via the Vercel
API. The relevant env var keys are:

```
VITE_API_URL                  (no rotation needed — just the HF Space URL)
GITHUB_TOKEN
GITHUB_REPO
LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET_KEY
LANGFUSE_BASE_URL
LANGWATCH_API_KEY
SMITHERY_API_KEY
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
```

### 3. (Optional) Scrub git history

The partial PAT prefix is still in historical commits of `worklog.md`. To
fully scrub it from history, use one of:

- `git filter-repo --path worklog.md --invert-paths` (recommended)
- BFG Repo-Cleaner: `bfg --delete-files worklog.md`

Then force-push and have all collaborators re-clone. This is disruptive and
should only be done if you want to be thorough — since the full PAT was only
ever in chat (not in git), rotating the PAT is sufficient to neutralise the
threat.

## Lessons Learned

1. **Never paste live credentials into chat.** Use environment variables,
   `.env` files (gitignored), or a secrets manager. If you need an AI
   assistant to work with credentials, give it access to a secrets manager
   via a scoped integration — never paste the raw values.
2. **Rotate credentials on a schedule.** Even without a known leak, rotating
   every 30–90 days limits the blast radius of any unknown exposure.
3. **Run secret scanners in CI, not just pre-commit.** Pre-commit hooks can
   be bypassed with `--no-verify`; CI scanners cannot. The new
   `secret-scan.yml` workflow enforces this on every PR.
4. **Audit `.gitignore` for development artefacts.** `worklog.md` should
   never have been committed in the first place. Any file that records
   operational activity (logs, notes, scratch files) should be gitignored
   by default.

## Post-Incident Verification

After the remediation actions were taken, the following were verified:

- `scripts/security_scan.py` → `[PASS] No hardcoded secrets detected.`
- `git ls-files | grep worklog` → (empty) — worklog.md no longer tracked
- `.gitleaks.toml` → loaded successfully by the gitleaks config parser
- `.github/workflows/secret-scan.yml` → committed; will run on next push to `main`

The Vercel production deployment continued to serve the Vite UI throughout
the remediation — no production impact.
