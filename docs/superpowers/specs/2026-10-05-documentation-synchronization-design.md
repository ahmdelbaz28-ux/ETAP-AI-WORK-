# Documentation Synchronization Design Specification (AhmedETAP Platform)

**Document Reference:** SPEC-DOCS-SYNC-2026-10-05  
**Target Branch:** `fix/docs-sync`  
**Base Commit:** `9d2198e8c7b57a8f7afe06536700566990dc2291`  
**Status:** PROPOSED & REVIEWED  
**Author:** AI Documentation Engineering Agent  

---

## 1. Problem Statement & Motivation

Multiple user-facing and agent-facing documentation files in the AhmedETAP repository have drifted from the physical reality of the codebase. Specifically:
1. **Agent Count Inconsistency:** Documents variously cite 19, 24, 25, or 31 agents without defining what constitutes an "agent."
2. **Outdated Engineering Study Statuses:** `ROADMAP.md` marks studies such as Harmonic Analysis, Optimal Power Flow, Motor Starting, and Transient Stability as "In Development" or "Planned," while the production engines and specialist agents are already implemented, tested, and shipped in the codebase.
3. **Outdated Architecture & Runbooks:** Documents reference obsolete architectures (Next.js API routes, LibSQL, DuckDB, KV storage, `main.py`, `pnpm start` on port 3000, and copied text referencing a `revit` repository), while the platform runs on a hardened dual-runtime architecture: FastAPI (`engineering_service.py` / `api.main:app`), PostgreSQL/Neon persistence, Vite frontend (`ui/`), and Mastra Node.js CLI.
4. **Unclosed Remediation Banners:** Active emergency response plans (`ETAP_Radical_Remediation_Plan_v2.0.md`) and UI remediation task briefs (`CHAT_UI_PATTERNS_PROMPT.md §3`) remain written in the imperative future/present tense even though their execution was completed and verified in commits `697f0336c`, `61d30c493`, and `9d2198e8c`.

This drift creates agent confusion, erodes trust, and leads to contradictory planning in multi-turn interactions.

---

## 2. Hard Governance Constraints

1. **Zero Code Changes:** Absolutely no modifications to `.py`, `.ts`, `.tsx`, or `.yaml` files. Only `.md` and documentation assets may be modified.
2. **Empirical Verification Requirement:** Every status claim (Shipped, Done, Completed) must reference the exact file path, symbol, live test command, and literal test output.
3. **No Force-Push:** All commits must be clean, forward-only git operations on branch `fix/docs-sync`.
4. **Preserve Links (Redirection Stubs):** Any file moved to `docs/archive/` must leave a clear stub with an archival notice at its original location so existing external links do not break.

---

## 3. Authoritative Single Sources of Truth

The documentation synchronization is anchored to the following canonical sources of truth:

| Domain | Canonical Source of Truth | Value / Rule |
|---|---|---|
| **Canonical Agent Keys** | `agents/registry.py:CANONICAL_AGENT_KEYS` | **27 Canonical Specialist Keys** |
| **Agent Key Aliases** | `agents/registry.py:AGENT_KEY_ALIASES` | **3 Aliases** (`harmonic`, `opf`, `protection`) |
| **Total Registered Keys** | `agents/registry.py:create_agent_registry()` | **30 Registry Keys** |
| **Study Types** | `agents/models.py:StudyType` | **17 Study Types** |
| **Mastra TypeScript Agents** | `src/mastra/agents/*.ts` | **11 LLM Specialist Agents** |
| **Prompt Definitions** | `prompts/*.yaml` + `prompts.json` | **32 Prompt YAMLs** (Manifest-First) |
| **Backend Framework** | `engineering_service.py`, `api/main.py` | FastAPI on Port 8000 / HF Space 7860 |
| **Database** | `api/database.py` | PostgreSQL (Neon / Supabase), SQLite dev |
| **Frontend UI** | `ui/` (Vite + React 19 + Tailwind CSS 4) | Chat-First v3.0, port 5173 / dist |
| **Audit & Test Status** | `docs/status/STATUS_BOARD.md` | S0→S8 Closed, 3774 passed, 208/208 UI |

### The Standardized Agent Count Footnote

Whenever agent count is mentioned across `README.md`, `ROADMAP.md`, `AGENTS.md`, and `docs/ARCHITECTURE.md`, the following standardized definition will be cited:

> **AhmedETAP Agent Architecture Definition:**
> The platform operates **27 Canonical Specialist Agents** defined in [`agents/registry.py`](agents/registry.py) (`CANONICAL_AGENT_KEYS`), plus 3 backward-compatibility aliases (`AGENT_KEY_ALIASES`) yielding 30 registered keys, 17 canonical `StudyType` members in [`agents/models.py`](agents/models.py), and 11 conversational TypeScript agents in [`src/mastra/agents/`](src/mastra/agents/).
> *Note on Historical Numbers:* Previous documents listed 19 (early milestone snapshots prior to July 2026), 24 (v2.1.0 drafts), 25 (numbered sections in legacy `AGENTS.md`), or 31 (file count in `PROJECT_INDEX.md` which indexed auxiliary orchestrator scripts as agents). The canonical standard is 27 specialist agents.

---

## 4. Scope of Changes (18 Files in 8 Sequential Groups)

### Group A: `ROADMAP.md`
- **Table v2.1.0 (lines 29-44):** Update statuses for Harmonic Analysis, Optimal Power Flow, Motor Starting, Transient Stability, Cable Sizing, Earth Grid, Renewable Integration, and Battery Storage from "In Development" / "Planned" to "Shipped" with empirical evidence paths (`fault_analysis/harmonic_analysis.py`, `load_flow/optimal_power_flow.py`, `agents/cable_sizing_agent.py`, etc.).
- **Agent Count:** Update heading to "AI Agent System (27 Specialized Agents)" with the standardized footnote.
- **Technical Debt Table (lines 148-154):** Mark TECH-DEBT-001, TECH-DEBT-003, TECH-DEBT-004, and TECH-DEBT-009 as Closed with empirical verification references.

### Group B: `README.md`, `AGENTS.md`, `docs/STATUS.md`, `docs/ARCHITECTURE.md`
- **`README.md`:** Align agent count to 27 canonical agents. Update runtime description to FastAPI + Vite + Postgres + Mastra CLI.
- **`AGENTS.md`:** Synchronize the agent directory list with `agents/registry.py` (27 canonical keys + 11 Mastra agents).
- **`docs/STATUS.md`:** Transition status from "🟡 Production Hardening in Progress" to "🟢 Production Hardened / S0→S8 Closure Complete". Update test metrics: 3774 pytest passed, 208/208 UI tests passed, ruff 0, claims audit 16/16 verified. Close resolved debt items.
- **`docs/ARCHITECTURE.md`:** Update overview to 27 specialized agents. Replace the legacy 9-agent file tree in section 3 with the full 32-file tree. Update sections 5, 7, 13, and 14 to reflect FastAPI, Vite, PostgreSQL, and mark completed studies as Shipped.

### Group C: `docs/AGENT_ARCHITECTURE.md`
- Update document version to 2026-10-05.
- Replace references to Next.js API routes, LibSQL, and DuckDB with FastAPI, Vite, and PostgreSQL.
- Document the `prompts.json` manifest-first loading sequence and Langfuse tracing.
- Update the `agents/` file tree to include `registry.py`, `router.py`, `workflow.py`, `etap_expert_agent.py`, `design_agent.py`, etc.

### Group D: `docs/CONTEXT.md`
- Remove obsolete KV Storage sections (`TASK_STORE_KV`, `API_KEYS_KV`, `RATE_LIMIT_KV`) and replace with relational models in `api/database.py`.
- Elevate the architectural errata banner to an authoritative architecture summary.

### Group E: `CHAT_UI_PATTERNS_PROMPT.md`
- Mark §3 (Tables A through H: Light Mode Remediation) as **COMPLETED & VERIFIED** under commits `61d30c493` and `9d2198e8c`, citing 208/208 passing Vitest tests.
- Retain §2 as the ongoing AI UI design backlog.

### Group F: `ETAP_Radical_Remediation_Plan_v2.0.md` & `SONARCLOUD_FIX_PROMPT.md`
- Move `ETAP_Radical_Remediation_Plan_v2.0.md` to `docs/archive/ETAP_Radical_Remediation_Plan_v2.0.md`.
- Create a redirect stub at root `ETAP_Radical_Remediation_Plan_v2.0.md` stamped `[STATUS: COMPLETED & ARCHIVED on 2026-09-21 at commit 697f0336c / PR #598]`.
- Record the prior removal of `SONARCLOUD_FIX_PROMPT.md` (deleted in commit `9d2198e8c`).

### Group G: Operational Guides
- **`docs/internal/AGENTS.md`:** Add top banner: `> [!CAUTION] NON-AUTHORITATIVE ARCHIVAL DOCUMENT. For canonical agent specifications, see AGENTS.md.`
- **`docs/internal/NEXT_STEPS.md`:** Replace `python main.py`, `pnpm dev`, `mastra.db`, `ETAP 19.0` with `uvicorn api.main:app`, `cd ui && npm run dev`, PostgreSQL, and real test counts (3798 tests).
- **`docs/INSTALLATION.md`, `docs/DEPLOYMENT.md`, `docs/QUICKSTART.md`:** Remove rogue `revit` repository URLs and outdated package commands. Standardize on `ahmdelbaz28-ux/ETAP-AI-WORK-`, FastAPI, and Vite.
- **Root `ARCHITECTURE.md` & `INSTALLATION.md`:** Verify that pointer references correctly direct to the updated files.

### Group H: Quality, Standards & UI Documentation
- **`CHANGELOG.md`:** Update `[Unreleased]` with S0→S8 achievements, Chat-First v3.0, Light Mode token remediation, and PR #598 squash commit (`697f0336c`).
- **`docs/VALIDATION_REPORT.md`:** Update verification commit to `9d2198e8c` / `697f0336c`. Confirm 4/4 IEEE benchmarks passing, 16/16 standards verified.
- **`prompts/README.md` & `prompts/PROMPT_RESOLUTION_SPEC.md`:** Document `prompts.json` manifest-first priority order, Langfuse remote tracing/override, and total 32 prompt YAML files.
- **`ui/README.md`:** Replace Vite template text with AhmedETAP Chat-First v3.0 documentation: workspace architecture, BYOK headers (`X-User-LLM-Key`, `X-User-LLM-Provider`), theme tokens, and test execution (`npx vitest run` 208/208).
- **`docs/AR/*` & `docs/SUMMARY_AR.md`:** Document Chat-First v3.0 capabilities and the BYOK channel.

---

## 5. Verification Gate & Deliverables

1. **Quality Gates:**
   - `ruff check .` → Must return 0 errors.
   - `python scripts/claims_audit.py --strict` → Must return 16 Verified / 0 Missing.
   - `python scripts/run_ieee_benchmarks.py` → Must return 4/4 PASS.
   - `cd ui && npm run build` → Must build with 0 TypeScript/Vite errors.
   - `cd ui && npx vitest run` → Must execute and pass 208/208 tests.
2. **Deliverables:**
   - Single git branch: `fix/docs-sync`.
   - Comprehensive audit report conforming to `docs/status/REPORT_TEMPLATE.md` documenting for each file: Before / After / Evidence / Command.
