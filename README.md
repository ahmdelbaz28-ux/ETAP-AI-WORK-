---
title: AhmedETAP
emoji: "⚡"
colorFrom: yellow
colorTo: red
sdk: docker
pinned: false
license: mit
app_port: 7860
---

<div align="center">

<h1>⚡ AhmedETAP Platform</h1>
<h3>Enterprise AI-Powered Power Systems Engineering</h3>

<p>
  An autonomous engineering-intelligence system that fuses 25 specialist AI agents
  with rigorous IEC / IEEE computational engines — taking engineers from a natural-language
  question to a validated, auditable engineering report in seconds.
</p>

<br/>

<!-- Identity badges -->
[![Version](https://img.shields.io/badge/version-2.1.0-gold?style=for-the-badge&logo=semantic-release&logoColor=white)](#)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge&logo=open-source-initiative&logoColor=white)](LICENSE)

<br/>

<!-- Live status badges -->
[![UI](https://img.shields.io/badge/UI-Vercel-000000?style=flat-square&logo=vercel&logoColor=white)](https://etap-ai-work.vercel.app)
[![API](https://img.shields.io/badge/API-HF%20Space-FFD21E?style=flat-square&logo=huggingface&logoColor=black)](https://ahmdelbaz28-ahmedetap-platform.hf.space/health)
[![DB](https://img.shields.io/badge/Postgres-Supabase-3ECF8E?style=flat-square&logo=supabase&logoColor=white)](https://supabase.com)
[![LLM Obs](https://img.shields.io/badge/LLM%20Obs-Langfuse-7C3AED?style=flat-square&logo=langfuse&logoColor=white)](https://cloud.langfuse.com)
[![Eval](https://img.shields.io/badge/Eval-LangWatch-FF6B6B?style=flat-square&logo=datadog&logoColor=white)](https://app.langwatch.ai)
[![MCP](https://img.shields.io/badge/MCP-Smithery-FFB400?style=flat-square&logo=data:image/svg%2Bxml;base64,&logoColor=white)](https://smithery.ai)
[![CI/CD](https://img.shields.io/badge/CI/CD-GitHub%20Actions-2088FF?style=flat-square&logo=github-actions&logoColor=white)](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/actions)
[![Standards](https://img.shields.io/badge/Standards-IEEE%20%7C%20IEC-0052cc?style=flat-square&logo=ieee&logoColor=white)](docs/ARCHITECTURE.md)

<br/>

**[🚀 Live UI — Vercel](https://etap-ai-work.vercel.app)** &nbsp;•&nbsp;
**[🧠 Live API — HF Space](https://ahmdelbaz28-ahmedetap-platform.hf.space/docs)** &nbsp;•&nbsp;
**[📚 Docs](docs/)** &nbsp;•&nbsp;
**[🔧 API Reference](docs/API_REFERENCE.md)** &nbsp;•&nbsp;
**[📋 Project Index](PROJECT_INDEX.md)**

</div>

---

## 🏭 Platform Identity

**AhmedETAP** is a production-grade, autonomous engineering-intelligence platform that
wraps ETAP-style power-systems analysis in a conversational, agent-driven interface.
It pairs a FastAPI backend (25 specialist agents, 51 API endpoints, IEEE/IEC engines
for load-flow / short-circuit / arc-flash / protection-coordination) with a React 19 +
Vite 6 single-page application that runs in any modern browser.

The platform is intentionally split across two hosting tiers so each tier plays to
its strength:

| Tier | Hosting | Tech | Role |
|:---|:---|:---|:---|
| **Frontend SPA** | Vercel | React 19 + Vite 6 + Tailwind 4 | Static UI, served from global edge CDN |
| **Backend API** | Hugging Face Space (Docker SDK) | FastAPI + uvicorn + Python 3.11 | AI agents, engineering engines, auth, persistence |
| **Postgres** | Supabase | Managed Postgres + Storage | Durable data (HF Space filesystem is ephemeral) |
| **LLM observability** | Langfuse Cloud | Prompt management + traces | Unlimited prompts, 50k observations / month |
| **LLM evaluation** | LangWatch | Scenario evals + drift detection | Continuous agent quality monitoring |
| **MCP tooling** | Smithery | Model Context Protocol registry | Secure external tool discovery |

The frontend talks to the backend over a single env var, `VITE_API_URL`, which is
baked into the Vite bundle at build time on Vercel.

---

## ✅ Recent Platform Fixes (2026-07-07 → 2026-07-08)

This release stabilises a deployment pipeline that had accumulated **520+ failed
Vercel preview deploys** in a row. The root cause and remediation are summarised
below — full detail is in [`DEPLOYMENT_FIX.md`](DEPLOYMENT_FIX.md).

### 1. Vercel auto-detection of MkDocs (root cause of the 520 failures)

`mkdocs.yml` was sitting at the repository root, which caused Vercel to
auto-detect the project as an MkDocs documentation site — overriding the
explicit `framework: vite` setting in `vercel.json`. Vercel's MkDocs preset
then ran `mkdocs build --strict`, which aborted on 36 broken-link warnings.

**Fix:** moved `mkdocs.yml` to `docs/mkdocs.yml` (with `docs_dir: .` so
MkDocs still finds its source files). Vercel now correctly builds the Vite UI.

### 2. `vercel-build.sh` — safety wrapper around the Vite build

A new executable at the repo root is now the Vercel `buildCommand`. It performs
three pre-flight checks before invoking `npm run build:vercel`:

1. **Refuse to build** if `mkdocs.yml` ever reappears at repo root (prevents
   regression of fix #1).
2. Verify `ui/package.json` is present.
3. Verify `docs/mkdocs.yml` is present (warning only).

Then it runs `npm --prefix ui run build:vercel` and asserts that
`ui/dist/index.html` exists before exiting 0. Distinct exit codes (1 / 2 / 3 / 4)
make any future failure trivially diagnosable from the Vercel build log.

### 3. MkDocs strict build now passes with **0 warnings**

The 36 historical warnings had three root causes, all fixed:

| Cause | Fix |
|:---|:---|
| `docs/index.md` referenced `docs/X.md` paths (wrong — index.md lives *inside* `docs/`) | Rewrote 7 links to `X.md` |
| `docs/index.md` referenced `.github/...` and `PROJECT_INDEX.md` (repo-root paths MkDocs can't serve) | Rewrote to absolute `https://github.com/.../blob/main/...` URLs |
| `README_AR.md`, `FINAL_COMPLETION_REPORT.md`, `ETAP_GUIDE_COMPLETION.md`, `DEVELOPER_GUIDE.md`, `internal/`, `AR/` all reference repo-root paths | Added an `exclude_docs:` block in `docs/mkdocs.yml` (correct mkdocs 1.6 syntax) |
| `docs/index.html` (legacy static) conflicted with `docs/index.md` | Added `index.html` to `exclude_docs` |
| `validation.links.info` is not a valid key in mkdocs 1.6 | Replaced with the proper `validation:` block |

The docs site can now be deployed to GitHub Pages / Netlify / HF Space static
without any warnings, in strict mode.

### 4. Vercel project settings synced with `vercel.json`

The Vercel project dashboard had stale build settings pointing to a
`frontend/` directory that does not exist in this repo. Patched via the
Vercel REST API to match the committed `vercel.json`:

| Setting | Old (stale) | New (synced) |
|:---|:---|:---|
| Framework Preset | vite | vite |
| Build Command | `cd frontend && npm run build` | `bash vercel-build.sh` |
| Install Command | (default) | `npm --prefix ui install --no-audit --no-fund` |
| Output Directory | `frontend/dist` | `ui/dist` |
| Node Version | 24.x | 22.x |

### 5. Vercel env vars synced with live credentials

11 env vars were updated via the Vercel REST API with fresh values:

- `VITE_API_URL` → `https://ahmdelbaz28-ahmedetap-platform.hf.space`
  (so the deployed UI talks to the live HF Space backend)
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`
- `LANGWATCH_API_KEY`
- `SMITHERY_API_KEY`
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- `GITHUB_TOKEN`, `GITHUB_REPO`

The unused `VITE_NEON_AUTH_URL` (a Vercel integration default — Neon is not
part of this stack) was deleted so it would not be embedded in the client
bundle.

### 6. Production deploy verified end-to-end

A new production deployment was triggered from `main` and reached `READY`
state. The deployed Vite bundle contains the HF Space URL, the SPA mounts
correctly, all assets return HTTP 200 with the immutable cache header from
`vercel.json`, and the UI's first API call lands on the live FastAPI backend
(which itself reports `{"status":"healthy", "agents":25, "etap_manuals":35,
"version":"2.1.0"}`).

---

## 🏗️ Architecture

```
 ┌──────────────────────────┐         ┌────────────────────────────────────┐
 │  Vercel Edge (CDN)       │         │  Hugging Face Space (Docker SDK)   │
 │  ──────────────────────  │  HTTPS  │  ───────────────────────────────── │
 │  React 19 SPA            │ ──────► │  FastAPI 0.115 + uvicorn           │
 │  Vite 6 build            │  JSON   │  25 AI agents                      │
 │  Tailwind 4              │         │  51 API endpoints (/api/v1/*)      │
 │  React Router 7          │         │  IEEE/IEC computational engines    │
 │  Zustand + React Query 5 │         │  JWT auth + bcrypt password hash   │
 │  i18next (ar/en)         │         │  ETAP / Zenon / GIS integrations   │
 └──────────────────────────┘         └───────────────┬────────────────────┘
                                                      │
                       ┌──────────────────────────────┴───────────────────────┐
                       │                                                      │
                       ▼                                                      ▼
            ┌─────────────────────┐                          ┌──────────────────────────┐
            │  Supabase           │                          │  Langfuse Cloud          │
            │  ─────────────────  │                          │  ──────────────────────  │
            │  Managed Postgres   │                          │  Prompt management       │
            │  (durable storage)  │                          │  LLM traces + scores     │
            │  Storage (artifacts)│                          │  Safety alerts           │
            └─────────────────────┘                          └──────────────────────────┘
                                                                      │
                                                                      ▼
                                                          ┌──────────────────────────┐
                                                          │  LangWatch               │
                                                          │  ──────────────────────  │
                                                          │  Scenario evaluations    │
                                                          │  Drift detection         │
                                                          │  Free-plan prompt limit  │
                                                          └──────────────────────────┘
```

### Why this split?

- **Vercel** serves a static Vite bundle from a global edge CDN. Cold-start is
  near zero, assets are cacheable for a year, and there is nothing to scale —
  it just works.
- **Hugging Face Space** runs the FastAPI backend as a Docker container. This
  is where the AI agents, the IEEE/IEC engines, and the heavy lifting live.
  HF Space handles container orchestration for free, including GPU access if
  needed later.
- **Supabase** provides durable Postgres storage — critical because the HF
  Space filesystem is wiped on every container restart, so any local SQLite
  database would be lost.
- **Langfuse** manages prompts as versioned, deployable artefacts and records
  every LLM call as a structured trace. Its free Hobby plan supports unlimited
  prompts (LangWatch's free plan is capped at 3).
- **LangWatch** runs scenario-based agent evaluations and drift detection on
  top of Langfuse traces.
- **Smithery** is the Model Context Protocol registry that the agents use to
  discover and bind external tools at runtime.

---

## 🚀 Quick Start

### Prerequisites

- **Node.js 22+** (for the UI) — see `.nvmrc`
- **Python 3.11+** (for the backend) — see `.python-version`
- **Docker 24+** (optional, for full-stack local dev) — see `docker-compose.yml`

### Run the UI locally

```bash
cd ui
npm install --no-audit --no-fund
npm run dev          # http://localhost:5173 (proxies /api to :8000)
```

### Run the backend locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in real values
uvicorn api.main:app --reload --port 8000
```

The UI dev server proxies `/api`, `/health`, `/docs`, and `/openapi.json` to
`http://localhost:8000` automatically (see `ui/vite.config.ts`).

### Run the full stack with Docker

```bash
docker-compose up -d   # Postgres + Redis + backend + UI + Prometheus + Grafana
```

See [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md) for production hardening.

---

## 📦 Deployment

### Frontend → Vercel

The Vercel project is configured (both in the dashboard and in
[`vercel.json`](vercel.json)) to:

1. Run `npm --prefix ui install --no-audit --no-fund`
2. Run `bash vercel-build.sh` (the safety wrapper)
3. Serve `ui/dist/` as static assets
4. Apply SPA fallback rewrites so client-side routes work on refresh
5. Apply immutable cache headers to `/assets/*` and security headers everywhere

Every push to `main` triggers a preview deploy; promoting a deploy to
production is a one-click action in the Vercel dashboard, or via:

```bash
vercel --prod
```

### Backend → Hugging Face Space

The HF Space uses the Docker SDK with `app_port: 7860` (see YAML frontmatter
at the top of this file). The Dockerfile at [`Dockerfile.hf`](Dockerfile.hf)
builds the FastAPI image and exposes the uvicorn server. Secrets
(`SUPABASE_*`, `LANGFUSE_*`, `LANGWATCH_API_KEY`, `OPENAI_API_KEY`, etc.)
are set in the HF Space settings UI and injected as env vars at container
startup.

### Docs → optional

The MkDocs site at [`docs/mkdocs.yml`](docs/mkdocs.yml) builds cleanly in
strict mode and can be deployed to GitHub Pages, Netlify, or as a static
attachment to the HF Space. Run locally with:

```bash
mkdocs serve -f docs/mkdocs.yml   # http://127.0.0.1:8000
```

---

## 🤖 AI Agent Inventory

25 specialist agents, each backed by an IEEE/IEC computational core and
governed by Langfuse prompt-versioning + safety alerts. Highlights:

| Domain | Agents |
|:---|:---|
| **Power-system analysis** | load-flow, short-circuit, arc-flash, protection-coordination, motor-starting, harmonic, transient-stability |
| **ETAP automation** | ETAP GUI agent (computer-use via Gemini Vision), ETAP RAG (35 manuals indexed), single-line diagram extraction |
| **GIS / SCADA** | ArcGIS connector, Zenon guide agent (4 guides indexed), SCADA topology ingest |
| **Engineering ops** | report generation, audit logging, validation, code-guard (prompt-injection defence) |
| **Orchestration** | master coordinator, memory agent (semantic + graph), context-engine RAG |

Full list with prompts: [`agents/`](agents/) and [`PROJECT_INDEX.md`](PROJECT_INDEX.md).

---

## 🔒 Security Posture

- **Auth:** JWT (HS256, 32+ char secret) + bcrypt password hashing
- **Authorisation:** role-based access control on every `/api/v1/*` route
- **LLM guardrails:** prompt-injection defence, model allow-list, agent-tag
  requirement, 50k-char input cap — see `LLM_*` env vars in `.env.example`
- **Audit:** life-safety events (lethal blocks, kill-switch, dual confirmation)
  forwarded to SIEM via Syslog RFC 5424
- **Secrets:** never committed; managed via Vercel env vars (frontend),
  HF Space secrets (backend), and Supabase dashboard (database)
- **Dependencies:** scanned by Bandit, SonarCloud, and Trivy in CI

See [`SECURITY.md`](SECURITY.md) and [`docs/SECURITY_OPERATIONS_MANUAL.md`](docs/SECURITY_OPERATIONS_MANUAL.md).

---

## 📁 Repository Layout

```
.
├── ui/                       # React 19 + Vite 6 SPA (Vercel deploy target)
│   ├── src/                  #   application source
│   ├── public/               #   static assets
│   └── vite.config.ts        #   Vite config + dev-server proxy
├── api/                      # FastAPI routers (51 endpoints under /api/v1/)
├── agents/                   # 25 specialist AI agent definitions + prompts
├── core/                     # Shared core (auth, redis_state, logging)
├── core_model/               # Domain models (load-flow, short-circuit, ...)
├── security/                 # LLM guardrails, audit, SIEM integration
├── integrations/             # ETAP, ArcGIS, Zenon, Gemini Vision connectors
├── ai_context_engine/        # RAG over ETAP manuals + Zenon guides
├── docs/                     # MkDocs documentation site (mkdocs.yml lives here)
│   └── mkdocs.yml            #   build with: mkdocs build -f docs/mkdocs.yml
├── docker/                   # Dockerfiles for HF Space, Windows worker, etc.
├── helm/                     # Kubernetes Helm charts (optional prod deploy)
├── tests/                    # pytest + vitest suites
├── vercel.json               # Vercel project config (framework, build, output)
├── vercel-build.sh           # Safety wrapper around the Vite build
├── Dockerfile.hf             # HF Space backend image
├── docker-compose.yml        # Full-stack local dev (Postgres + Redis + UI + API)
├── requirements.txt          # Python dependencies
├── .env.example              # Full env-var reference (376 lines)
└── PROJECT_INDEX.md          # Auto-generated codebase map
```

---

## 🧪 Testing & CI

- **Unit tests:** `pytest` (backend), `vitest` (UI)
- **Integration tests:** `pytest-asyncio` against a real Postgres + Redis
- **Scenario tests:** `vitest --config vitest.scenarios.config.ts` (agent evals)
- **Lint:** `ruff` + `mypy` (backend), `biome` + `tsc --noEmit` (UI)
- **CI:** GitHub Actions runs lint + tests on every PR — see
  [`.github/workflows/`](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/tree/main/.github/workflows)

---

## 🤝 Contributing

1. Fork the repo and create a feature branch: `git checkout -b feat/your-feature`
2. Install pre-commit hooks: `pre-commit install`
3. Run the test suite: `pytest && cd ui && npm test`
4. Open a PR — CI must pass before merge
5. Squash-merge to `main` → Vercel auto-deploys a preview → promote to prod

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full workflow.

---

## 📜 License

MIT — see [`LICENSE`](LICENSE).

---

## 🆘 Support

- **Issues:** [GitHub Issues](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/issues)
- **Bug report template:** [`.github/ISSUE_TEMPLATE/bug_report.md`](.github/ISSUE_TEMPLATE/bug_report.md)
- **Feature request template:** [`.github/ISSUE_TEMPLATE/feature_request.md`](.github/ISSUE_TEMPLATE/feature_request.md)
- **Security disclosures:** see [`SECURITY.md`](SECURITY.md) (do NOT open a public issue for security bugs)

---

<div align="center">

<sub>Built with ❤️ for power-systems engineers. © AhmedETAP Team.</sub>

</div>
