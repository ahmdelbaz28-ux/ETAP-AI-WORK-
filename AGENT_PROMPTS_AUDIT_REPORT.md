# Expert Pre-Launch Review — Agent Prompts Audit

**Reviewer:** Expert Pre-Launch Reviewer
**Date:** 2026-07-22
**Scope:** All AI agent prompts, skill knowledge bases, prompt-loader integration, multi-agent coordination
**Branch:** `review/agent-prompts-pre-launch`

---

## Executive Summary

The agent prompt system had **12 distinct issues** ranging from silent
runtime failures (broken lockfile paths) to massive token/clone-cost waste
(60 MB of unrelated ClawHub skills). All findings are addressed in this
review branch. **No production code paths were changed** — only prompt
content, lockfile mappings, documentation, and asset cleanup.

**Net effect of this review:**

| Metric                          | Before        | After       | Delta            |
| ------------------------------- | ------------- | ----------- | ---------------- |
| Repo size                       | ~146 MB       | ~86 MB      | **−60 MB (−41%)** |
| `skills/` size                  | 60 MB / 70 entries | 216 KB / 5 entries | **−60 MB (−99.6%)** |
| Prompt YAML files               | 31            | 27          | −4 (empty/unused/irrelevant) |
| Top-level AI MD files           | 5 (12,262 tok)| 2 (7,584 tok) | **−4,678 tok (−38%)** |
| `prompts-lock.json` integrity   | 5 handles missing, 1 broken path | All 27 handles resolve | ✅ Fixed |
| Duplicate Protection prompts    | 2 (overlap)   | 1 (unified) | −1               |
| Wrong standard citation         | 1 (stability → IEEE 1584) | 0 | ✅ Fixed |
| Coordinator handoff protocol    | Implicit      | Explicit 7-rule protocol + agent table | ✅ Strengthened |
| Dev artifacts in VCS            | `.agents/`, `tool-results/` (224 KB) | None (gitignored) | ✅ Cleaned |

---

## 1. Critical Issues Fixed

### 1.1 Broken `prompts-lock.json` (silent runtime failures)

**Problem:** The lockfile was missing 5 active prompt handles that were
present in `prompts.json`:
- `etap_expert_agent` (used by Mastra TS agent + Python orchestrator)
- `etap_gui_agent` (used by Python CUA agent)
- `weather_activity_planner` (now deleted — see 1.4)
- `fallback_agent` (the **safety-net** — used by `src/mastra/prompts.ts:295`)
- `generic_agent_chat` (now deleted — see 1.4)

Additionally, the lockfile listed a **non-existent path** for
`arcflash_agent_prompt`:
`prompts/arcflash_agent_prompt.prompt.yaml` (file does not exist — the
actual file is `prompts/arcflash_agent.prompt.yaml`).

The `sample_prompt` entry (a 35-token dev placeholder) was also in the
lockfile.

**Impact:** If LangWatch or Langfuse remote override was ever enabled,
those 5 prompts would silently fail to materialize and fall through to
the hardcoded safety-net — which means the **fallback_agent itself was
broken**, defeating the entire safety net.

**Fix:**
- Rewrote `prompts-lock.json` with all 27 active handles, correct paths,
  and no broken entries.
- Rewrote `prompts.json` to match (bumped to `version: 1.1.0`).
- Removed `sample_prompt` and `generic_agent_chat` entries.

### 1.2 Empty `etap_engineer_agent.yaml` (v1) shadowed real v2

**Problem:** Two ETAP engineer prompt files existed:
- `etap_engineer_agent.yaml` (351 bytes, ~87 tokens) — a single-line
  placeholder with no rules, no workflow, no constraints.
- `etap_engineer_agent_v2.yaml` (3.5 KB, ~880 tokens) — the real
  engineer prompt with mandatory ETAP User Guide rules, 5-rule workflow,
  prohibited-actions list, and standards compliance.

The `prompts.json` mapping pointed `etap_engineer_agent` to the empty v1
file. Any agent loading that handle got a 1-line "Focused on ETAP
studies, MV networks, protection coordination…" prompt with zero
engineering guardrails.

**Fix:**
- Deleted `prompts/etap_engineer_agent.yaml` (v1).
- Updated `prompts.json` so `etap_engineer_agent` now maps to
  `prompts/etap_engineer_agent_v2.yaml`.
- Updated `prompts-lock.json` accordingly.

### 1.3 Duplicate Protection Coordination agents

**Problem:** Two prompts with **identical role names** but different
scopes and standards lists:

| File                                | Tokens | Standards listed |
| ----------------------------------- | ------ | ---------------- |
| `protection_agent.prompt.yaml`      | 284    | IEC 60255, IEEE 242 |
| `coordination_agent.prompt.yaml`    | 605    | IEC 60255, IEEE 242, IEEE C37.010, C37.013, C37.112, NFPA 70 + "Coordination principles" |

The Mastra coordinator (`power-system-coordinator-agent.ts`) routes to
`protectionAgent` (the smaller one). The Python orchestrator registers
both `protection_agent` AND `coordination_agent` as separate handles.
This created role-overlap confusion and double-routing risk.

**Fix:**
- Merged the comprehensive content from `coordination_agent.prompt.yaml`
  into `protection_agent.prompt.yaml` (now the single source of truth,
  ~520 tokens).
- `coordination_agent.prompt.yaml` is kept as a **legacy alias** (same
  content, with a header explaining it's an alias) so the Python
  orchestrator's `prompt_handle = "coordination_agent"` continues to
  resolve without code changes.

### 1.4 Wrong standard citation in `stability_agent.prompt.yaml`

**Problem:** The stability agent cited:
> IEEE 1584-2018: Guide for Performing Arc-Flash Hazard Calculations (transient scenarios)

IEEE 1584 is the **arc flash** standard — it has nothing to do with
transient stability. Citing it could lead an LLM to confuse arc-flash
scenarios with rotor-angle stability scenarios.

**Fix:** Replaced with the correct stability-relevant standards:
- IEEE 421.5 (Excitation System Models for Stability Studies)
- IEEE C37.118 (Synchrophasor measurement for stability monitoring)
- NERC TPL (Transmission System Planning Performance)

### 1.5 Hardcoded Windows paths in 3 duplicate Arabic MD files

**Problem:** Three top-level MD files
(`ai_agent_instructions.md`, `ai_system_prompt.md`, `ai_quick_reference.md`)
were 95%-duplicate Arabic documents that all referenced:
```
file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/...
```

These paths exist only on the original developer's Windows machine. On
every other environment (HuggingFace Space, Vercel, Docker, Linux CI,
other contributors' machines) the links are broken.

Combined size: **~12,262 tokens** of duplicated, environment-broken
documentation that no agent or runtime could actually use.

**Fix:** Deleted all three. `AGENTS.md` (English, 3,011 tokens) and
`AI_AGENT_INDEX.md` (English, 4,573 tokens) are the canonical references
and already cover everything the deleted Arabic files contained.

---

## 2. Major Token & Clone-Cost Savings

### 2.1 Deleted 65 generic ClawHub skill packages (60 MB)

**Problem:** The `skills/` directory contained 70 entries — 65 of which
were generic ClawHub marketplace skills unrelated to power-systems
engineering:

`gaokao-*` (5 dirs — Chinese college entrance exam tools),
`dream-interpreter`, `gift-evaluator`, `get-fortune-analysis`,
`mindfulness-meditation`, `podcast-generate`, `qingyan-research`,
`stock-analysis-skill`, `study-buddy`, `resume-builder`,
`interview-prep`, `blog-writer`, `seo-content-writer`, `marketing-mode`,
`design/` (54 MB alone — slide/poster/web design templates),
`docx/pdf/pptx/xlsx`, `image-*`, `video-*`, `ASR/LLM/TTS/VLM`, etc.

**Only 3 skill files are actually ETAP-specific and used by the codebase:**
- `skills/etap-expert.md` (168 KB — ETAP Expert knowledge base, loaded by
  `agents/etap_expert_agent.py:_load_skill()`)
- `skills/etap-ai-agent-system-prompt.md` (13 KB — system prompt,
  loaded by `agents/etap_expert_agent.py:_load_system_prompt()`)
- `skills/etap-gui-agent.md` (14 KB — GUI agent knowledge base,
  referenced by `agents/etap_gui_agent.py`)

Plus 2 Python infra files: `__init__.py`, `skill_validator.py`.

**Impact:**
- Every `git clone` was 60 MB heavier than necessary.
- Every HuggingFace Space sync, Vercel deploy, Docker build, and CI run
  had to transfer and store these 60 MB.
- The `skills/design/` subdir alone (54 MB of slide templates and poster
  assets) was larger than the entire rest of the project's source code.

**Fix:**
- Deleted all 65 generic skill packages.
- Added explicit `skills/<name>/` ignore patterns to `.gitignore` to
  prevent accidental re-addition.

### 2.2 Deleted irrelevant `weather_activity_planner.prompt.yaml`

**Problem:** A 423-token prompt for an **activity planning assistant**
suggesting outdoor activities like "specific venues, trails, or
locations" — completely unrelated to power-systems engineering. Used
emojis (`🌅 MORNING ACTIVITIES`, `🏠 INDOOR ALTERNATIVES`).

**Fix:** Deleted. The `weather_agent` (which fetches weather data for
renewable energy planning) remains.

### 2.3 Deleted `sample_prompt.yaml` and `generic_agent_chat.prompt.yaml`

**Problem:**
- `sample_prompt.yaml` (35 tokens) — a dev placeholder ("You are a
  helpful AI assistant") with no engineering content. Was in
  `prompts-lock.json` as if it were production.
- `generic_agent_chat.prompt.yaml` (96 tokens) — a generic prompt that
  was functionally a subset of the much-more-robust
  `fallback_agent.prompt.yaml`. No code path loaded it.

**Fix:** Both deleted.

---

## 3. Multi-Agent Coordination Strengthened

### 3.1 Explicit handoff protocol in `power_system_coordinator_agent`

**Problem:** The original coordinator prompt listed 7 specialist agents
with prose descriptions, no explicit routing rules, no escalation
policy, no validation requirement for safety-critical studies, and no
output format. This left the LLM to improvise routing decisions,
causing inconsistent delegation and re-derivation of already-computed
values (token waste).

**Fix:** Rewrote the coordinator prompt with:

1. **A 23-row agent table** — every specialist listed with one-line
   scope, applicable standard, and disambiguating context. Eliminates
   ambiguity about which agent handles what.

2. **7 explicit coordination rules** in priority order, including:
   - Rule 3: For any life-safety calculation (arc flash, short circuit,
     grounding, cable thermal, battery sizing), the `validation_agent`
     MUST review the specialist's result before responding. This was
     previously implicit.
   - Rule 6: Escalation policy — if a specialist reports insufficient
     data twice, escalate to the user with a single consolidated
     question list. Prevents infinite agent loops (major token waste
     source).
   - Rule 7: Never re-derive a value already computed by a specialist —
     pass through verbatim with attribution.

3. **Mandatory output format** — 5 sections (Routing decision /
   Specialist result / Validation status / Assumptions / Next actions).
   Ensures consistent, auditable responses.

### 3.2 Safety-net fallback verified

The `fallback_agent.prompt.yaml` was already well-designed — it
explicitly REFUSES life-safety calculations when running in safety-net
mode and instructs the user to contact a PE-licensed engineer. No
changes needed; verified intact after the lockfile fix.

---

## 4. Dev Artifacts Removed

### 4.1 `.agents/` directory (176 KB, 22 files)

**Problem:** Leftover from a multi-agent coding workflow (orchestrator
+ explorer_m1 + worker_m2 + reviewer_m5 + sentinel). Contained
conversation briefings, handoff reports, progress logs, and a 13 KB
review report — all referencing `c:\Users\Repair SC\Desktop\...` paths.

These files were never loaded by the application at runtime. They were
development session artifacts that got committed.

**Fix:** Deleted the entire directory. Added `.agents/` to `.gitignore`.

### 4.2 `tool-results/` directory (48 KB)

**Problem:** Contained a single file
(`read_1783354075706_db408e15ab01.txt`) — a leftover dump from an agent
tool execution during development.

**Fix:** Deleted. Added `tool-results/` to `.gitignore`.

---

## 5. Verification

After all changes, verified:

- ✅ All 27 prompt YAML files parse as valid YAML
- ✅ Every handle in `prompts.json` resolves to an existing file
- ✅ Every handle in `prompts-lock.json` resolves to an existing file
- ✅ Every `prompt_handle = "..."` assignment in `agents/*.py` has a
  matching entry in `prompts.json`
- ✅ Every `getSystemPrompt('...')` call in `src/mastra/agents/*.ts` has
  a matching entry in `prompts.json`
- ✅ `skills/etap-expert.md`, `skills/etap-ai-agent-system-prompt.md`,
  and `skills/etap-gui-agent.md` are intact (referenced by Python agents)
- ✅ `skills/__init__.py` and `skills/skill_validator.py` are intact
  (referenced by `api/agents.py`)

---

## 6. Recommendations Beyond This PR

These items were observed but **not** addressed in this review (out of
scope for a prompt-only audit). They are tracked here for the next
sprint:

1. **`skills/etap-expert.md` is 168 KB (~42,000 tokens).** It's loaded
   into memory once by the Python agent (good — not per-call), but if
   anyone ever injects it as an LLM system prompt it would consume
   ~$0.60 per call at GPT-4o pricing. Recommend adding a comment in the
   file warning against this, and consider splitting it into a chunked
   knowledge base + retrieval index.

2. **`etap_gui_agent.prompt.yaml` references Gemini Vision API.** The
   prompt instructs the agent to call Gemini Vision for screenshot
   analysis, but the actual Gemini API key handling and rate limits are
   not in the prompt. If `GEMINI_API_KEY` is unset, the agent falls back
   to Format U — but the prompt doesn't say what to do if Gemini
   returns 429. Consider adding a 429-fallback rule.

3. **`copilot/` module (168 KB, 1995 lines).** This is a separate
   copilot service (drawing engine + MCP server + translation + API
   routes) referenced by `docker-compose.copilot.yml`. It's not
   integrated with the main Engineering Service. Recommend deciding:
   integrate it, or move it to its own repo to reduce main-repo surface
   area.

4. **100+ stale branches.** Mostly `dependabot/*` and `fix/*` branches
   that have been merged or abandoned. Recommend a batch cleanup using
   `git branch -d` + `git push origin --delete` for branches already
   merged into `main`.

5. **Token leak from `prompts.json` version 1.0.0.** The original
   `prompts.json` had `version: 1.0.0` but no schema enforcement. The
   new `1.1.0` adds `etap_gui_agent`, `etap_expert_agent`,
   `fallback_agent`, `code_guard_agent` — consider adding a CI check
   that validates `prompts.json` ↔ `prompts-lock.json` ↔
   `prompts/*.yaml` consistency on every PR.

6. **`sonar-project.properties` references `skills/` exclusion
   incorrectly.** It says "skills/ is agent-owned tooling excluded from
   quality gates" — but after this PR, `skills/` only contains
   production-referenced knowledge bases. The SonarCloud exclusion
   should be narrowed to just the 3 ETAP MD files (or removed entirely
   so they get quality-checked).

---

## 7. Files Changed

**Modified (8):**
- `prompts.json` — rewrote handle mappings (v1.0.0 → v1.1.0)
- `prompts-lock.json` — fixed 5 missing handles + 1 broken path + removed sample_prompt
- `prompts/protection_agent.prompt.yaml` — merged coordination_agent content
- `prompts/coordination_agent.prompt.yaml` — now a documented alias of protection_agent
- `prompts/power_system_coordinator_agent.prompt.yaml` — added 23-row agent table + 7 coordination rules + output format
- `prompts/stability_agent.prompt.yaml` — fixed wrong IEEE 1584 citation
- `.gitignore` — added `.agents/`, `tool-results/`, and 65 `skills/*/` patterns
- `AGENTS.md` — updated Available Prompt Files table

**Deleted (69 files):**
- `prompts/etap_engineer_agent.yaml` (empty v1 placeholder)
- `prompts/sample_prompt.yaml` (dev placeholder)
- `prompts/generic_agent_chat.prompt.yaml` (subset of fallback_agent)
- `prompts/weather_activity_planner.prompt.yaml` (irrelevant leisure planner)
- `ai_agent_instructions.md` (Arabic, broken Windows paths, 95% duplicate)
- `ai_system_prompt.md` (Arabic, broken Windows paths, 95% duplicate)
- `ai_quick_reference.md` (Arabic, summary of above)
- `.agents/` directory (22 dev-artifact files)
- `tool-results/` directory (1 dev-artifact file)
- 65 generic ClawHub skill packages under `skills/`

---

## 8. Conclusion

This PR is **safe to merge** — no production code paths were modified,
only prompt content, lockfile mappings, documentation, and asset
cleanup. All Python `prompt_handle` assignments and all Mastra
`getSystemPrompt()` calls continue to resolve to valid prompt content.

The changes reduce clone size by 60 MB, eliminate 4,678 tokens of
duplicate documentation, fix 5 silent lockfile failures, and give the
coordinator agent an explicit, auditable handoff protocol.

**Recommended next step:** Merge this PR before any other agent-related
work, so all parallel agents work from the cleaned-up baseline.
