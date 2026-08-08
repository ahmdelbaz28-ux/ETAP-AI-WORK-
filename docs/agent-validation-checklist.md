# Agent Validation Checklist — ETAP AI

> **Use this checklist** every time you add a new agent or modify an existing one.
> **Source:** Adapted from harness's output checklist + ETAP-specific requirements.

## Pre-Flight (Before Writing Code)

- [ ] **Classify the pattern:** Which of the 6 architecture patterns does this agent fit?
  (Pipeline / Fan-out/Fan-in / Expert Pool / Producer-Reviewer / Supervisor / Hierarchical Delegation)
  → Document in `docs/agent-architecture-patterns.md`
- [ ] **Check for duplicates:** Run `python scripts/audit_agent_drift.py` — does a similar agent already exist?
- [ ] **Define the prompt handle:** Follow convention `<name>_agent` (e.g. `load_flow_agent`)

## Implementation

- [ ] **Agent class:** Create `agents/<name>_agent.py` with class inheriting `BaseAgent`
- [ ] **prompt_handle:** Set `prompt_handle = "<name>_agent"` as class attribute
- [ ] **execute() method:** Override `BaseAgent.execute()` — return `AgentResult`
- [ ] **validate_result() method:** Override with domain-specific checks
- [ ] **Error handling:** Follow `docs/error-handling-policy.md` — 1 retry, then fail gracefully
- [ ] **Tracing:** Use `@trace_operation` decorator on `execute()`
- [ ] **Logging:** Use `self.log_execution()` for all significant events

## Prompt File

- [ ] **YAML file:** Create `prompts/<name>_agent.prompt.yaml`
- [ ] **Frontmatter:** `model`, `temperature`, `messages` (system + user)
- [ ] **Description:** If adding a `description` field, make it "pushy" (specific trigger keywords)
- [ ] **Line count:** < 500 lines (Progressive Disclosure — split to references/ if larger)
- [ ] **Why-first:** Replace `ALWAYS`/`NEVER` rules with reasoning
- [ ] **Generalized:** No overfitting to specific examples
- [ ] **Standards:** Reference the relevant IEEE/IEC standard (e.g. IEEE 3002.7 for load flow)

## Tests

- [ ] **Unit test:** Create `tests/test_<name>_agent.py` — test `execute()` with mock data
- [ ] **Boundary mismatch:** If the agent exposes an API endpoint, add a test in `tests/boundary_mismatch/`
- [ ] **A/B test case:** Add a test case to `tests/agent_evaluation/test_cases.yaml`
- [ ] **Drift audit:** Run `python scripts/audit_agent_drift.py` — should show 0 new warnings for this agent

## Documentation

- [ ] **Update `docs/agent-architecture-patterns.md`:** Add the new agent to the inventory table
- [ ] **Update `AGENTS.md`** (if it lists agents)
- [ ] **API docs:** If the agent is exposed via API, update `API_DOCUMENTATION.md`

## CI Verification

- [ ] **`ruff check .`** passes
- [ ] **`pytest tests/test_<name>_agent.py`** passes
- [ ] **`python scripts/audit_agent_drift.py`** shows no new drift
- [ ] **`pytest tests/boundary_mismatch/`** passes (no new mismatches introduced)

## Post-Merge

- [ ] **Monitor:** Watch Grafana dashboard for 24h — verify agent executes without errors
- [ ] **A/B test:** Run `python tests/agent_evaluation/run_ab_test.py` with LLM keys — verify prompt adds value
- [ ] **Iterate:** If A/B test shows < 10% improvement, refine the prompt

## Anti-Patterns (Do NOT)

- ❌ Do NOT create `.claude/agents/<name>.md` — ETAP uses Python classes, not Claude Code markdown
- ❌ Do NOT copy harness's SKILL.md format — ETAP uses YAML prompts
- ❌ Do NOT use `TeamCreate`/`SendMessage` APIs — ETAP uses Mastra + Celery, not Claude Code
- ❌ Do NOT add a `CLAUDE.md` pointer — ETAP is not a Claude Code project
- ❌ Do NOT skip the drift audit — it catches missing prompts/agents before they hit production
