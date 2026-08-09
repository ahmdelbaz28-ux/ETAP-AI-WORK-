# Dev Environment Guide — AhmedETAP

> **One-line summary:** This repo ships with a `.devcontainer/` configuration that
> gives every developer a byte-identical environment on GitHub Codespaces,
> CodeSandbox Devboxes, Daytona, or local VS Code — for **$0/month** on free tiers.

---

## Why we unified

Before this change, every developer ran a slightly different setup: different
Python patch versions, different Node LTS, some had Playwright installed, some
didn't, some used SQLite, some had a local Postgres. The result was the classic
"works on my machine" failures, especially around Playwright/Chromium and the
Python ML stack.

The `.devcontainer/devcontainer.json` in this repo fixes that by declaring the
exact same environment used in production (Python 3.12, Node 22, matching
`pyproject.toml` and `.nvmrc`).

---

## Platform comparison (free tiers, as of July 2026)

| Platform | RAM | Hours/month | Best for | Limit |
|:---|:---:|:---:|:---|:---|
| **CodeSandbox Devbox** | 8 GB | 40 | Daily manual coding | 40h/month is ~2h/day |
| **GitHub Codespaces** | 8 GB | 60-90 (2-core) | Daily manual coding | 120 core-hours/month |
| **Daytona Hobby** | 3 GB | $100 one-time credit | AI agent sandbox | 1-hour session limit |
| **HF Spaces Free** | 16 GB | always-on | Backend preview | 2 vCPU, ephemeral FS |
| **Local VS Code + Docker** | your hardware | unlimited | Power users | requires local Docker |

**Our team policy:**

- **CodeSandbox or Codespaces** for daily manual development (the editor experience is best).
- **Daytona** for automated AI code review on PRs (`.github/workflows/ai-review-daytona.yml`).
- **HF Spaces** for the always-on production backend (already deployed).
- **Local** as a fallback for anyone with a powerful laptop and Docker Desktop.

---

## Quick start (5 minutes)

### Step 1 — Pick a platform

| Platform | How to open |
|:---|:---|
| GitHub Codespaces | Repo → `Code` → `Codespaces` → `Create codespace on feat/your-branch` |
| CodeSandbox | Repo → `Code` → `Open in CodeSandbox` |
| Daytona | `daytona create --git-url https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-` |
| VS Code local | `Cmd/Ctrl+Shift+P` → `Dev Containers: Reopen in Container` |

### Step 2 — Wait for `post-create.sh` to finish (~2-4 min)

You'll see output like:
```
▶ [1/6] Python: upgrading pip, installing ruff/uv
▶ [2/6] Python: installing requirements.txt
▶ [3/6] Node: verifying version
▶ [4/6] UI: installing npm dependencies (this may take 2-4 min)
▶ [5/6] Playwright: verifying Chromium
▶ [6/6] Final touches
✅ Dev container ready!
```

### Step 3 — Configure secrets

The `devcontainer.json` `remoteEnv` block pulls these from your **host machine**
via `localEnv:`. Set them on your host (in `~/.bashrc`, `~/.zshrc`, or system
env settings):

```bash
# Required for backend
export HF_TOKEN=hf_xxx
export LANGFUSE_SECRET_KEY=sk-lf-xxx
export LANGFUSE_PUBLIC_KEY=pk-lf-xxx
export LANGFUSE_BASE_URL=https://cloud.langfuse.com
export SUPABASE_URL=https://xxx.supabase.co
export SUPABASE_ANON_KEY=xxx
export SUPABASE_SERVICE_ROLE_KEY=xxx

# Optional — for Vercel deploys from CLI
export VERCEL_TOKEN=vcp_xxx

# Optional — for AI agent sandbox (Daytona)
export DAYTONA_API_KEY=dtn_xxx
export DAYTONA_API_URL=https://app.daytona.io
export DAYTONA_TARGET=local
```

Then **restart** the dev container so it picks up the new env vars.

### Step 4 — Run the stack

```bash
# Terminal 1: backend
uvicorn engineering_service:app --reload --port 8000

# Terminal 2: UI
cd ui && npm run dev
```

Open http://localhost:5173 — the UI is configured to talk to http://localhost:8000
via `VITE_API_URL` in the devcontainer.json.

---

## Memory budget — does it fit on free tiers?

The AhmedETAP stack at idle consumes approximately:

| Component | RAM (idle) |
|:---|---:|
| FastAPI + uvicorn | ~200 MB |
| Vite dev server | ~500 MB |
| Playwright Chromium (1 instance) | ~400 MB |
| Python ML libs loaded | ~500 MB |
| PostgreSQL (if running) | ~100 MB |
| Redis (if running) | ~30 MB |
| **Total idle** | **~1.7 GB** |
| **Peak (during tests)** | **~2.5 GB** |

Free-tier headroom:

| Platform | Available | Idle headroom | Peak headroom |
|:---|---:|---:|---:|
| HF Spaces Free (16 GB) | 16 GB | ✅ 14.3 GB | ✅ 13.5 GB |
| CodeSandbox (8 GB) | 8 GB | ✅ 6.3 GB | ✅ 5.5 GB |
| Codespaces 4-core (8 GB) | 8 GB | ✅ 6.3 GB | ✅ 5.5 GB |
| Codespaces 2-core (8 GB) | 8 GB | ✅ 6.3 GB | ✅ 5.5 GB |
| Daytona Hobby (3 GB) | 3 GB | ⚠ 1.3 GB | ❌ -0.5 GB |
| Replit Free (1 GB) | 1 GB | ❌ -0.7 GB | ❌ -1.5 GB |

**Recommendation:** Daytona is great for the **AI agent sandbox** (which only
runs lint+tests then exits), but **not** for daily manual coding. Use CodeSandbox
or Codespaces for that.

---

## AI Code Review on PRs (Daytona integration)

When you open a PR against `main` or `develop`, the `ai-review-daytona.yml`
workflow automatically:

1. Spins up an isolated Daytona sandbox (no production secrets).
2. Clones your PR branch.
3. Runs `ruff check` on the **changed Python files only**.
4. Runs `tsc --noEmit` on the UI if any `.ts(x)` files changed.
5. Posts a structured review comment with the results.
6. Tears down the sandbox.

**To enable**, the repo admin must:

1. Add `DAYTONA_API_KEY` as a GitHub repository secret.
2. Add `ENABLE_DAYTONA_REVIEW=true` as a repository variable (Settings → Actions → Variables).

**To disable:** set `ENABLE_DAYTONA_REVIEW=false` (or delete the variable). The
workflow then no-ops, and the existing `ci-cd.yml` pipeline is the authoritative
signal.

---

## Troubleshooting

### `npm ci` fails on Electron postinstall
The devcontainer installs with `--ignore-scripts` to skip Electron's binary
download on Linux. If you need Electron for desktop builds:
```bash
cd ui && npm rebuild electron --foreground-scripts
```

### `pip install` runs out of memory on Daytona
Switch to `requirements-minimal.txt`:
```bash
pip install -r requirements-minimal.txt
```
This skips ML libs, OpenCV, and Tesseract — fine for non-ML work.

### Ports not auto-forwarding
- **Codespaces:** check the `Ports` tab.
- **CodeSandbox:** ports auto-expose; click the URL in the panel.
- **VS Code local:** use the `Forward Ports` panel.

### Container disk full
The devcontainer uses three named volumes (`etap-pip-cache`, `etap-npm-cache`,
`etap-bashhistory`) that persist across rebuilds. To wipe everything:
```bash
docker volume ls | grep etap- | awk '{print $2}' | xargs docker volume rm
```

### Playwright fails to launch Chromium
```bash
playwright install --with-deps chromium
```
On Daytona free tier (3 GB RAM), you may need to set
`PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` and run E2E tests elsewhere.

---

## Contributing changes to the dev environment

The devcontainer is itself versioned. If you need to add a tool:

1. Edit `.devcontainer/devcontainer.json`.
2. Test on at least **two** platforms (Codespaces + CodeSandbox is the minimum).
3. Open a PR with the `dev-infra` label.
4. CI will validate that the JSON is well-formed (the `ci-cd.yml` lint job).

**Never** put real secrets in `.devcontainer/` files. Use `remoteEnv` with
`${localEnv:VAR_NAME}` passthrough only.
