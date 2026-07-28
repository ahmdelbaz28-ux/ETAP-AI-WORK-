# 🔐 Cross-Platform Sync — Secrets Setup Guide

This guide explains how to configure all GitHub Secrets so that the `Cross-Platform Sync` workflow can auto-propagate every change to **Vercel + HuggingFace + LangWatch + Smithery**.

## Required GitHub Secrets

Go to: **GitHub Repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Where to get it | Used For |
|-------------|-----------------|----------|
| `VERCEL_TOKEN` | Vercel → Settings → Tokens → Create (scope: Full Account) | Triggering Vercel deployments via API |
| `VERCEL_PROJECT_ID` | Vercel → Project → Settings → General → Project ID (starts with `prj_`) | Identifying the project in Vercel API |
| `HF_TOKEN` | https://huggingface.co/settings/tokens (Write scope) | Pushing to HuggingFace Space |
| `LANGWATCH_API_KEY` | https://app.langwatch.ai/onboarding (starts with `sk-lw-`) | Registering deployment markers |
| `SMITHERY_API_KEY` | https://smithery.ai/console/api-keys | Verifying MCP registry reachability |
| `GH_PAT` | GitHub → Settings → Developer settings → Personal access tokens (Fine-grained, with `Contents: Read+Write` and `Pull requests: Write`) | Drift-detection PRs (HF → GitHub) |
| `DAYTONA_TOKEN` | Daytona → Settings → API Tokens → Create | Automated AI code review on every PR (`daytona-ai-review.yml`) |

## How to set each one (one-liner via GitHub CLI)

```bash
gh secret set VERCEL_TOKEN        -b "YOUR_VERCEL_TOKEN_HERE"
gh secret set VERCEL_PROJECT_ID   -b "prj_YOUR_PROJECT_ID_HERE"
gh secret set HF_TOKEN            -b "hf_YOUR_HF_TOKEN_HERE"
gh secret set LANGWATCH_API_KEY   -b "sk-lw-YOUR_LANGWATCH_KEY_HERE"
gh secret set SMITHERY_API_KEY    -b "YOUR_SMITHERY_API_KEY_HERE"
gh secret set GH_PAT              -b "github_pat_YOUR_GH_PAT_HERE"
gh secret set DAYTONA_TOKEN       -b "day_YOUR_DAYTONA_TOKEN_HERE"
```

> ⚠️ **Security note:** Never paste real token values into README/markdown files — GitHub Secret Scanning will block the push. Always use the `gh secret set` CLI command from your local terminal with the real values, or set them via the GitHub web UI.

## Vercel Project Setup (one-time)

1. Connect the GitHub repo `ahmdelbaz28-ux/ETAP-AI-WORK-` to Vercel.
2. Set **Root Directory** = `ui/`.
3. Set **Build Command** = `npm run build:vercel` (auto-detected from `vercel.json`).
4. Set **Output Directory** = `dist`.
5. Set **Node Version** = `22.x` (matches `.nvmrc`).

## Sync Behavior Summary

| Trigger | What happens |
|---------|--------------|
| Push to `main` (non-docs) | Vercel auto-deploys + HF Space syncs + LangWatch marker + Smithery verified |
| Manual dispatch (`force=true`) | All of the above + explicit Vercel redeploy API call |
| Daily 03:00 UTC | Drift check: compares HF Space README with `README.hf.md` in GitHub; opens a PR if drifted |
| HF Space manual edit (via HF UI) | Caught by the daily drift check → PR opened within 24h |

## Verification

After pushing this commit to `main`:
1. Check **Actions** tab → `Cross-Platform Sync` workflow runs green.
2. Check **Vercel** → new deployment appears within ~2 min.
3. Check **HuggingFace Space** → commit `🔄 Auto-sync from GitHub main @ …` appears.
4. Check **LangWatch** → deployment marker visible in timeline.
5. Smithery just needs API reachability (200/204 = OK).
