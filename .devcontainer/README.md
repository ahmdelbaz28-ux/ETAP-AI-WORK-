# ─────────────────────────────────────────────────────────────────────────────
# AhmedETAP — Dev Container README
# Unified dev environment for the entire team
# Works on: GitHub Codespaces • CodeSandbox Devboxes • Daytona • VS Code local
# ─────────────────────────────────────────────────────────────────────────────

## Quick start

| Platform | Action |
|:---|:---|
| **GitHub Codespaces** | Repo → green `Code` button → `Codespaces` tab → `Create codespace on main` |
| **CodeSandbox Devbox** | Repo → `Code` → `Open in CodeSandbox` (uses `.devcontainer/devcontainer.json`) |
| **Daytona** | `daytona create --git-url https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-` |
| **VS Code (local)** | Install Docker + `Dev Containers` extension → `Reopen in Container` |

All four platforms read the **same** `.devcontainer/devcontainer.json`, so every
developer gets a byte-identical environment — no "works on my machine".

## What's inside

| Layer | Version | Purpose |
|:---|:---|:---|
| Python | 3.12 (matches `pyproject.toml`) | Backend, agents, ML |
| Node | 22 LTS (matches `.nvmrc`) | Vite 6, React 19, Electron |
| Docker (outside-of-docker) | latest | Run `docker-compose.yml` from inside the container |
| Playwright + Chromium | latest | E2E tests, BrowserCUA executor |
| GitHub CLI | latest | PR review, issue triage from terminal |
| ruff, uv, pip | latest | Python linting + fast installs |

## Ports auto-forwarded

| Port | Service |
|:---|:---|
| 5173 | Vite dev server (UI) |
| 8000 | FastAPI backend |
| 5432 | PostgreSQL (when run via docker-compose) |
| 6379 | Redis (when run via docker-compose) |
| 7860 | HF Space local port (mirror of production) |

## Secrets

The `remoteEnv` block in `devcontainer.json` passes through secrets from your
**local machine** (via `localEnv:`) into the container. Set these on your host
machine — never commit them.

```bash
# On your host machine (NOT in the repo):
export HF_TOKEN=hf_xxx
export LANGFUSE_SECRET_KEY=sk-lf-xxx
export LANGFUSE_PUBLIC_KEY=pk-lf-xxx
export LANGFUSE_BASE_URL=https://cloud.langfuse.com
export SUPABASE_URL=https://xxx.supabase.co
export SUPABASE_ANON_KEY=xxx
export SUPABASE_SERVICE_ROLE_KEY=xxx
export VERCEL_TOKEN=vcp_xxx
export DAYTONA_API_KEY=dtn_xxx        # optional — for AI agent sandbox
export DAYTONA_API_URL=https://app.daytona.io
export DAYTONA_TARGET=local           # or your workspace target name
```

Then start the dev container — those vars will be visible inside it via
`process.env` / `os.environ` automatically. The `.env` file inside the
container (created from `.env.example`) handles the rest.

## Running the stack

```bash
# Option A: Full stack via docker-compose (uses postgres + redis)
docker-compose up -d postgres redis
uvicorn engineering_service:app --reload --port 8000 &
cd ui && npm run dev

# Option B: Lightweight (SQLite + in-memory cache, no docker)
# .env must have DATABASE_URL=sqlite+aiosqlite:///./etap.db
uvicorn engineering_service:app --reload --port 8000 &
cd ui && npm run dev
```

## Free-tier memory budget

| Platform | RAM available | Stack peak usage | Headroom |
|:---|:---|:---:|:---:|
| CodeSandbox Free | 8 GB | ~2.3 GB | ✅ plenty |
| GitHub Codespaces Free | 8 GB (4-core) | ~2.3 GB | ✅ plenty |
| GitHub Codespaces 2-core | 8 GB | ~2.3 GB | ✅ plenty |
| Daytona Free | 3 GB | ~2.3 GB | ⚠ tight — disable Playwright if OOM |
| HF Spaces Free | 16 GB | ~2.3 GB | ✅✅ lots of room |

If you hit OOM on Daytona, set `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` in your
`.env` and use a different platform for E2E tests.

## Troubleshooting

### `npm install` fails inside the container
The container uses `--ignore-scripts` to avoid Electron postinstall issues on
Linux. If you need Electron for desktop builds, run:
```bash
cd ui && npm rebuild electron --foreground-scripts
```

### `pip install` fails
The container tries `requirements.txt` first, falls back to
`requirements-minimal.txt`. If both fail, your network is offline — check
Codespaces/CodeSandbox region settings.

### Port 5173/8000 not auto-forwarded
On GitHub Codespaces: check the `Ports` tab. On CodeSandbox: ports are
auto-exposed. On local VS Code: `Forward Ports` panel.

### Container runs out of disk
The `etap-pip-cache`, `etap-npm-cache`, and `etap-bashhistory` volumes are
persisted across rebuilds. To clear everything:
```bash
docker volume ls | grep etap- | awk '{print $2}' | xargs docker volume rm
```
