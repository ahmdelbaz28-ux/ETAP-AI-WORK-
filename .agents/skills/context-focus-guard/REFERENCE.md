# Context Focus & Anti-Hallucination Guard Reference

## Self-Audit Checklist

| Checkpoint | Requirement | Validation Method |
|---|---|---|
| **Fact Source** | Every path/function verified | `view_file` or `grep_search` empirical proof |
| **No Assumptions** | Zero fabricated parameters | Check exact schema definition |
| **Math Integrity** | Numerical claims recomputed | Python script execution (0.01% tolerance) |
| **Scope Boundary** | Stayed within task objective | Compare current turn to user initial request |
| **Runtime Proof** | Fix verified with command | Run test/build command and inspect exit code |

## Halt-and-Reflect Notification Template

When drift, error, or hallucination is detected, emit response following this exact structure:

```markdown
⚠️ **HALT & REFLECT: Self-Correction Triggered**

- **Point of Failure**: [Describe exact step where contradiction/error occurred]
- **Root Cause Analysis**: [Explain bad assumption or unverified parameter]
- **Self-Criticism**: [State what was missed during legwork]
- **Correction Plan**: [Step-by-step resolution path]
```

## Anti-Hallucination Guardrail Schema

```json
{
  "guardrails": {
    "disallow_unverified_imports": true,
    "disallow_dummy_fallbacks": true,
    "disallow_silent_exceptions": true,
    "require_log_evidence_before_fix": true,
    "require_math_guard_for_numbers": true,
    "max_context_spend_threshold": 0.70
  }
}
```
