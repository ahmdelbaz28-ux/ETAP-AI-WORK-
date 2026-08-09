# AhmedETAP — Operations Risk Register

**Version:** 1.0.0  
**Date:** 2026-06-10  
**Classification:** INTERNAL — OPERATIONS  
**Owner:** Site Reliability Engineering Team  
**Review Cycle:** Quarterly  

---

## 1. Risk Summary

| Risk ID | Category | Description | Likelihood | Impact | Risk Level | Owner | Status |
|---|---|---|---|---|---|---|---|
| R-001 | Infrastructure | Single Cloudflare Worker instance (no multi-region) | Medium | High | **HIGH** | SRE | ACCEPTED |
| R-002 | Infrastructure | Single KV namespace for rate limiting (no cross-region replication) | Low | Medium | **MEDIUM** | SRE | ACCEPTED |
| R-003 | Data | In-memory task store (`_taskStore`) — data lost on Worker restart | High | High | **HIGH** | Platform | MITIGATED |
| R-004 | Data | No persistent database for task queue — studies may be lost | Medium | High | **HIGH** | Platform | MITIGATED |
| R-005 | Data | `mastra.db` (LibSQL) is local file — not backed up automatically | Medium | Medium | **MEDIUM** | SRE | OPEN |
| R-006 | Data | Prompt files in `prompts/` directory not versioned with backup | Low | Medium | **MEDIUM** | DevOps | OPEN |
| R-007 | Security | `API_KEY_SECRET` is single static key — no rotation policy | Medium | High | **HIGH** | Security | OPEN |
| R-008 | Security | No audit logging of API requests, agent actions, or ETAP executions | Medium | High | **HIGH** | Security | OPEN |
| R-009 | Security | No RBAC enforcement in Worker API (all authenticated users have same access) | Medium | Medium | **MEDIUM** | Security | OPEN |
| R-010 | Reliability | No health check endpoint for ETAP Worker backend | Medium | High | **MEDIUM** | SRE | OPEN |
| R-011 | Reliability | No automated failover for ETAP Worker (Docker Compose only) | Medium | High | **MEDIUM** | SRE | OPEN |
| R-012 | Reliability | No retry mechanism for failed study submissions | Medium | Medium | **MEDIUM** | Platform | OPEN |
| R-013 | Scalability | Worker runs on free tier — 1000 req/s bursts fail (load test evidence) | High | Medium | **MEDIUM** | Platform | OPEN |
| R-014 | Scalability | In-memory task store capped at 1000 tasks — queue may drop old items | Medium | Medium | **MEDIUM** | Platform | OPEN |
| R-015 | Scalability | No horizontal scaling for Python engine (single process) | Medium | High | **HIGH** | SRE | OPEN |
| R-016 | Observability | No structured audit logs for compliance | Medium | High | **HIGH** | Security | OPEN |
| R-017 | Observability | No log retention policy defined | Low | Medium | **LOW** | SRE | OPEN |
| R-018 | Cost | No cost monitoring for LLM provider usage | Medium | Medium | **MEDIUM** | Finance | OPEN |
| R-019 | Cost | No budget alerts for Cloudflare Workers or KV usage | Low | Low | **LOW** | Finance | OPEN |
| R-020 | Compliance | No incident response runbook documented | Medium | High | **HIGH** | SRE | OPEN |
| R-021 | Compliance | No disaster recovery plan documented | Medium | High | **HIGH** | SRE | OPEN |
| R-022 | Compliance | No backup & restore validation performed | Medium | High | **HIGH** | SRE | OPEN |
| R-023 | Compliance | No SLA/SLO defined for customers | Medium | Medium | **MEDIUM** | Product | OPEN |
| R-024 | Deployment | Docker Compose and K8s manifests exist but are not actively used | Low | Medium | **LOW** | DevOps | ACCEPTED |
| R-025 | Deployment | No blue-green or canary deployment strategy | Medium | Medium | **MEDIUM** | DevOps | OPEN |
| R-026 | Secrets | `.env` file is the only secrets management mechanism | Medium | High | **HIGH** | Security | OPEN |
| R-027 | Secrets | `wrangler secret put` is manual — no automation or rotation | Medium | High | **HIGH** | Security | OPEN |
| R-028 | Business | No documented RTO/RPO targets | Medium | High | **HIGH** | SRE | OPEN |
| R-029 | Business | No capacity planning for user growth | Medium | Medium | **MEDIUM** | Product | OPEN |
| R-030 | Business | No cost optimization strategy or usage controls | Medium | Medium | **MEDIUM** | Finance | OPEN |

---

## 2. Risk Details

### R-001 — Single Cloudflare Worker Instance
**Description:** The platform runs on a single Cloudflare Worker (`ahmed-etap.ahmdelbaz28.workers.dev`). There is no multi-region deployment or edge replication.
**Impact:** Regional outage or Worker platform degradation would cause total unavailability.
**Mitigation:** Cloudflare Workers run on Cloudflare's edge network which is inherently distributed. The risk is the single account/namespace, not the single Worker.
**Action:** Accept — Cloudflare's edge network provides built-in availability. Document fallback DNS in DR plan.

### R-003 — In-Memory Task Store
**Description:** Study tasks are stored in `_taskStore` (in-memory Map). All tasks are lost on Worker restart.
**Impact:** Users lose queued/completed studies. No audit trail.
**Mitigation:** Tasks are ephemeral by design. Completed studies are returned to the client immediately. The status endpoint is for polling only.
**Action:** For production, migrate to KV-backed or Durable Object-backed task store.

### R-007 — Static API Key Secret
**Description:** `API_KEY_SECRET` is a single static key stored in Cloudflare Workers secrets. No rotation, no multiple keys, no key scoping.
**Impact:** Key compromise gives total access. No way to revoke individual keys without changing the secret for all users.
**Mitigation:** The key is stored in Cloudflare's encrypted secret store. No hardcoded secrets in code.
**Action:** Implement multi-key support with per-key scopes and rotation in the Worker.

### R-015 — Python Engine Single Process
**Description:** The Python engine (`engine/engine.py`) runs as a single process. No worker pool or async queue.
**Impact:** CPU-intensive studies (load flow, short circuit) block the engine.
**Mitigation:** Studies are offloaded to AI providers when available. The Python engine is a fallback.
**Action:** For production, containerize the Python engine with RabbitMQ or Celery for async execution.

### R-026 — Single Secrets Management Mechanism
**Description:** `.env` is the only place secrets are managed locally. `wrangler secret put` is used for production.
**Impact:** Risk of secrets leaking in logs or being shared incorrectly.
**Mitigation:** `.env` is in `.gitignore`. Production uses Cloudflare's encrypted secret store.
**Action:** Implement HashiCorp Vault or Cloudflare Secrets Store for centralized secrets management.

---

## 3. Risk Acceptance Criteria

A risk is **ACCEPTED** when:
- The mitigation is proportionate to the risk level.
- The cost of mitigation exceeds the potential impact.
- The risk is inherent to the chosen architecture (e.g., Cloudflare Workers single-tenant model).

A risk is **OPEN** when:
- A mitigation plan exists but is not yet implemented.
- The risk requires a design decision or budget allocation.

A risk is **CLOSED** when:
- The mitigation is implemented and verified.
- The risk is no longer applicable.

---

## 4. Review History

| Date | Reviewer | Action | Notes |
|---|---|---|---|
| 2026-06-10 | SRE Team | Initial register created | 30 risks identified, 3 accepted, 27 open |

---

## 5. Next Review

**Next Review Date:** 2026-09-10 (Quarterly)  
**Trigger Events:**
- Major deployment or architecture change
- Incident with SEV-2 or higher
- New regulatory requirement
- Cost threshold exceeded

---

*Document Classification: INTERNAL — OPERATIONS*
*Distribution: SRE Team, Security Team, Engineering Leadership*
