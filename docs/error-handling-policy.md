# Error Handling Policy — ETAP AI

> **Source principle:** Adapted from harness's orchestrator error handling methodology.
> **Scope:** Applies to all agents in `agents/`, all API routes in `api/`, all Celery tasks in `worker/`.

## Core Principle

> **1 retry, then proceed without that result. Report what's missing. Conflicting data is kept with both sources noted — never silently deleted.**

This principle ensures:
- **Resilience:** A single agent failure doesn't block the entire workflow
- **Transparency:** Users see what's missing, not a silent gap
- **Auditability:** Conflicting data is preserved for human review

## Implementation

### In `agents/orchestrator.py`

The `BaseAgent.execute()` method returns `AgentResult` with:
- `status: AgentStatus` — `COMPLETED` | `FAILED` | `VALIDATING`
- `validation_errors: List[str]` — descriptive error messages
- `data: Dict[str, Any]` — may be empty on failure

**Pattern:**
```python
async def execute(self, task: EngineeringTask) -> AgentResult:
    try:
        # ... agent logic ...
        return AgentResult(
            agent_name=self.agent_name,
            study_type=task.study_types[0],
            status=AgentStatus.COMPLETED,
            data=result_data,
        )
    except Exception as exc:
        self.log_execution(f"Agent failed: {exc}", level="ERROR")
        return AgentResult(
            agent_name=self.agent_name,
            study_type=task.study_types[0],
            status=AgentStatus.FAILED,
            data={},
            validation_errors=[str(exc)],
        )
```

### In `worker/celery_app.py`

Celery config (in `worker/celery_app.py`):
- `task_acks_late=True` — task is re-delivered if worker crashes
- `task_reject_on_worker_lost=True` — re-queue on worker death
- `task_time_limit=3600` — hard kill after 1 hour
- `task_soft_time_limit=3300` — soft warning at 55 minutes
- `worker_max_tasks_per_child=100` — recycle worker to prevent memory leaks

### In `core/retry.py` (existing)

The retry module implements the "1 retry" portion. Circuit breaker in `core/circuitBreaker.ts`
opens after 5 consecutive failures, preventing cascade.

### In API routes (`api/*.py`)

- Return HTTP 500 with `{"success": false, "errors": [...], "trace_id": "..."}` on agent failure
- Never swallow exceptions silently — always log + return trace_id
- Conflicting data from multiple agents: return both in `data` with `source` field

## When to Retry vs When to Fail

| Situation | Action |
|-----------|--------|
| Network timeout to Redis/Postgres | Retry once (3s backoff), then fail gracefully |
| LLM API rate limit | Retry once (30s backoff), then return partial result |
| Engineering calculation fails (e.g. non-convergence) | Do NOT retry — return FAILED with diagnostic info |
| Validation finds non-compliance | Do NOT retry — return COMPLETED with `validation_status=False` |
| Agent crashes mid-execution | Celery re-delivers (task_acks_late), new worker picks up |

## Conflict Resolution

When two agents produce conflicting results (e.g. load flow says voltage is 1.02pu, validation says it's out of range):

1. **Keep both results** in the final `AgentResult.data`
2. **Flag the conflict** in `validation_errors`
3. **Include source attribution:** `{"load_flow": {"voltage": 1.02}, "validation": {"compliant": false, "expected_range": [0.95, 1.05]}}`
4. **Never delete** the conflicting data — the user decides which to trust

## Monitoring

- `core/metrics.py` exposes Prometheus metrics for: agent execution count, failure rate, retry count
- `core/tracing.py` adds OpenTelemetry spans for each agent execution
- Failed agents appear in Grafana dashboard with trace_id for debugging

## See Also

- `docs/agent-architecture-patterns.md` — how agents coordinate
- `docs/agent-validation-checklist.md` — checklist for adding new agents
- `core/retry.py` — retry implementation
- `core/circuitBreaker.ts` — circuit breaker pattern
