# Prompts — Writing Guide

> **Source:** Adapted from harness's `skill-writing-guide.md` (8 principles).
> **Scope:** All 29 prompt YAML files in `prompts/`.

## The 8 Principles

### 1. Description is the only trigger mechanism

The `description` field (if present) is how the system decides whether to use this prompt. Claude is conservative — write it "pushy" with specific trigger keywords.

**Bad:** `"Load flow analysis prompt"`
**Good:** `"Load flow analysis for electrical power systems. Use when the user requests voltage magnitudes, branch flows, convergence analysis, or IEEE 3002.7 compliance. Triggers on: 'load flow', 'power flow', 'voltage profile', 'convergence'."`

### 2. Why-first, not rule-first

LLMs generalize better from reasoning than from rigid rules.

**Bad:** `ALWAYS use Newton-Raphson. NEVER use Gauss-Seidel.`
**Good:** `Use Newton-Raphson for load flow because it converges quadratically near the solution and handles ill-conditioned systems better than Gauss-Seidel, which may diverge for systems with high R/X ratios.`

### 3. Generalize — don't overfit

**Bad:** `If the bus voltage is 1.05, flag it as high.`
**Good:** `Flag any bus voltage outside the range [0.95, 1.05] pu as a violation. The range follows IEEE 3002.7 recommended practice for industrial power systems.`

### 4. Lean body — context window is a public good

- SKILL.md body: < 500 lines
- If larger, split to `prompts/<name>/main.yaml` + `prompts/<name>/references/*.yaml`
- Every line must justify its token cost

### 5. Progressive Disclosure (3-tier loading)

| Tier | What | When loaded | Size target |
|------|------|-------------|-------------|
| 1 | YAML frontmatter (name, description) | Always | ~100 words |
| 2 | Main body (system + user messages) | When prompt is triggered | < 500 lines |
| 3 | Reference files | On demand | Unlimited |

### 6. Imperative tone

Use "~한다", "~하라" (Korean) or imperative mood (English). The prompt is an instruction, not a description.

**Bad:** `This agent can perform load flow analysis.`
**Good:** `Perform load flow analysis using the Newton-Raphson method.`

### 7. Bundle repetitive code

If multiple agents need the same helper logic, put it in a Python module (`agents/helpers/`) — don't repeat it in prompts.

### 8. Don't include what Claude already knows

- Don't explain what numpy is
- Don't explain Python syntax
- Don't explain IEEE standards in detail — reference them by number

## YAML Structure

```yaml
model: gpt-4o
temperature: 0.2
description: "..."  # optional but recommended for trigger reliability
messages:
  - role: system
    content: |
      You are a [Agent Name] for [domain].
      
      Standards Compliance: [IEEE/IEC standard number]
      
      Your primary function is to [one-sentence purpose].
      
      When performing [task type]:
      - Use [tool/method] for [reason].
      - Do not [forbidden action] because [reason].
      - Ask for missing [data] when needed.
      - Return [output format] in a clear technical format.
      - Flag [violations/risks].
      
      Keep responses technical, concise, and focused on [domain] decisions.
  - role: user
    content: "{{input}}"
```

## Audit Checklist (run before commit)

- [ ] Description field exists and is "pushy" (specific trigger keywords)
- [ ] Body < 500 lines
- [ ] No `ALWAYS`/`NEVER` rules without reasoning
- [ ] No overfitting to specific examples
- [ ] Imperative tone throughout
- [ ] IEEE/IEC standards referenced by number
- [ ] `python scripts/validate_prompts.py` passes
- [ ] `python scripts/audit_agent_drift.py` shows no new drift

## See Also

- `agents/prompt_loader.py` — 3-tier loading (LangWatch → YAML → hardcoded)
- `docs/agent-validation-checklist.md` — full checklist for adding agents
- `scripts/validate_prompts.py` — existing validation script
