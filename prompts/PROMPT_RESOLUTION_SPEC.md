# Prompt Resolution Specification

## Purpose

This document is the shared seam contract for prompt loading in the
AhmedETAP platform. It defines the resolution order and fallback behavior
that **both runtimes** (Python `agents/prompt_loader.py` and TypeScript
`src/mastra/prompts.ts`) must implement identically.

The local YAML file is always the safety-critical baseline — a remote override
can never silently change a safety-critical prompt (ADR-0003).

## Resolution Order

```
1. Cache (within TTL — default 300 s)
2. Local YAML (Tier 1 — safety-critical source of truth)
3. Remote override (Tier 2: Langfuse / Tier 3: LangWatch — opt-in only)
   - Only consulted when <PROVIDER>_OVERRIDE_MODE=true
   - Hard timeout (default 3 s)
   - Circuit breaker (5 failures → open for 60 s)
   - Integrity check: SHA-256 hash must match local YAML, else local wins
4. Fallback agent prompt (local YAML for "fallback_agent" handle)
5. Hardcoded safety-net (TypeScript) / hardcoded fallback (Python)
```

## File Resolution Order (per handle)

Given a `handle` (e.g. `etap_engineer_agent`):

1. **`prompts.json` manifest (Priority 1 — Canonical Bindings)**: Consulted first. Maps `prompts.prompts[handle]` → canonical path (e.g. `etap_engineer_agent` → `prompts/etap_engineer_agent_v2.yaml`).
2. **Local YAML pattern fallback (Priority 2)**:
   - `{prompts_dir}/{handle}.prompt.yaml`
   - `{prompts_dir}/{handle}.yaml`
3. **Fallback agent prompt**:
   - `prompts/fallback_agent.prompt.yaml` / `fallback_agent.yaml`
4. **Hardcoded safety-net**: Default prompt embedded in runtime code.

### `prompts.json` Manifest

Located at the repository root. Authoritatively pins each agent handle to its canonical prompt file:

```json
{
  "prompts": {
    "etap_engineer_agent": "prompts/etap_engineer_agent_v2.yaml",
    "load_flow_agent": "prompts/load_flow_agent.prompt.yaml"
  }
}
```

## System Message Extraction

After parsing the YAML (using a standard YAML parser — `yaml.safe_load` in
Python, `js-yaml` in TypeScript — **not** a hand-rolled parser):

1. If `messages` is a list of `{ role, content }` objects, find the object
   where `role == "system"` and return its `content` (stringified if it
   contains `text` parts).
2. Otherwise, if `prompt` is a non-empty string, return it.
3. Otherwise, return `null` (caller falls through to the next tier).

## Shared Fallback Text

This exact string is used by both runtimes when no YAML file is found:

```
You are a safety-net fallback AI assistant for power systems engineering. Provide accurate, standards-compliant (IEEE/IEC) analysis and recommendations. If you are uncertain about a life-safety calculation (arc flash, short circuit, grounding, protective coordination), REFUSE to give a numerical answer and instead direct the user to a qualified licensed engineer.
```

## Configuration Constants

| Constant | Default | Environment Variable |
|---|---|---|
| Cache TTL | 300 s | `PROMPT_CACHE_TTL` |
| Remote timeout | 3.0 s | `LANGFUSE_TIMEOUT` / `LANGWATCH_TIMEOUT` |
| Circuit breaker failures | 5 | `PROMPT_CB_FAILURE_THRESHOLD` |
| Circuit breaker reset | 60 s | `PROMPT_CB_RESET_SECONDS` |
| Langfuse override enabled | false | `LANGFUSE_OVERRIDE_MODE` |
| LangWatch override enabled | false | `LANGWATCH_OVERRIDE_MODE` |

## Normative References

- Python implementation: `agents/prompt_loader.py`
- TypeScript implementation: `src/mastra/prompts.ts`
- ADR-0003: Three-tier prompt fallback
