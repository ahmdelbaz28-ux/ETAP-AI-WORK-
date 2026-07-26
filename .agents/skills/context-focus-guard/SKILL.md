---
name: context-focus-guard
description: Maintain laser-focused context, eliminate hallucination, ban parameter guessing, enforce source-code verification in long operations, and execute self-audit loops when drift or errors occur. Use when running long multi-step tasks, complex refactoring, power-system analysis, or when context preservation and zero-hallucination are required.
---

# Context Focus & Anti-Hallucination Guard (`context-focus-guard`)

## Core Leading Words

- **zero-hallucination**: Never fabricate variable names, API schemas, file paths, or numerical results. Every statement must link to empirical evidence.
- **ground-truth**: Inspect authoritative files or execution logs before claiming facts. Guessing is strictly prohibited.
- **context-checkpoint**: Monitor token budget and operational state every 5 steps. Auto-summarize spent history when reaching 70% threshold.
- **self-audit**: Run self-criticism and validation check before delivering any final output.
- **halt-and-reflect**: Immediately stop execution upon detecting contradiction, uncertainty, or error. Notify user, analyze root cause, and correct course.

## Execution Rules

### 1. Verification Before Statement (Ground Truth Rule)
- NEVER state an API parameter, function signature, file path, or computation result without inspecting the source file or reading raw log output.
- If data is missing or ambiguous: ASK the user or fetch empirical evidence. DO NOT infer or fill gaps with assumptions.

### 2. Multi-Step Context Checkpointing
- In multi-step operations (>3 steps), write progress checkpoints to memory/state.
- Check token/step budget at step boundaries.
- *Completion criterion*: Remaining token spend <70%, active tasks mapped to initial goals, zero orphaned subtasks.

### 3. Self-Audit & Quality Assurance Loop
Before emitting response, evaluate against the 4-Point Self-Audit Checklist:
1. Did I cite actual file paths/logs for every technical claim?
2. Did I execute verification commands (tests/builds) rather than assuming code works?
3. Did I stay strictly within requested task scope without drifting?
4. Are all numbers verified via deterministic code (MathGuard)?

### 4. Failure Recovery (Halt-and-Reflect Procedure)
If an error, contradiction, or hallucination is detected:
1. **STOP IMMEDIATELY**: Do not conceal error or return dummy fallback.
2. **NOTIFY USER**: State exact point of failure and nature of error clearly.
3. **SELF-CRITICISE**: Identify root cause (e.g., stale context, bad assumption, unverified signature).
4. **CORRECT**: Update implementation plan, apply fix, and verify runtime output.

## Reference

See [REFERENCE.md](REFERENCE.md) for full Self-Audit Checklist, Anti-Hallucination Guardrail Schema, and Failure Recovery Templates.
