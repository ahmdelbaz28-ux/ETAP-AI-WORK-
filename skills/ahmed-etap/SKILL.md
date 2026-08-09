---
name: ahmed-etap
description: Orchestrate AhmedETAP's 24 AI agents as a unified engineering team with shared context, token-efficient routing, math-guarded computation, and mandatory peer review. Use when working with AhmedETAP platform, ETAP power-system studies, agent coordination, multi-agent workflows, or when the user mentions ETAP, power system analysis, load flow, short circuit, arc flash, protection coordination, or any engineering study.
---

# AhmedETAP Agent Orchestration

## Quick Start

```
User: "Run load flow on Project-X"
→ /ahmed-etap study load_flow project=Project-X
```

## Core Principles

1. **One Team, One Context** — All 24 agents share a single `SharedContext`. Never reload full prompts per agent.
2. **Token Budget** — Every workflow starts with a token budget. Compress context when >70% spent.
3. **Math Guard** — Every numerical claim passes deterministic Python validation before reaching the user.
4. **Mandatory Peer Review** — No study result ships without a second agent cross-checking it.

## Workflows

### 1. Study Execution
```
/ahmed-etap study <study_type> project=<name> [params...]
```
- Parse → canonical `StudyType`
- Load `SharedContext` with project data + standards
- Route to **Lead Agent** → run computation → **MathGuard** → **Peer Review**
- Pass → format & return | Fail → loop back (max 2)

### 2. Multi-Agent Collaboration
Triggered when request spans >1 study type.
- Decompose → parallel tasks → write to `SharedContext.results`
- **Integration Agent** merges → **MathGuard** → **Peer Review** → unified response

### 3. Context Compression
When token spend >70%: summarize completed tasks, drop intermediate reasoning, keep inputs + final results.

## Agent Communication

Agents speak through `SharedContext` only. Never pass full prompts between agents. See [REFERENCE.md](REFERENCE.md) for schema, Math Guard spec, Peer Review Matrix, and token budgets.
