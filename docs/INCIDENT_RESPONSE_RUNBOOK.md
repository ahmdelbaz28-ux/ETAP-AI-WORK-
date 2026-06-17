# AhmedETAP — Incident Response Runbook

**Version:** 1.0.0  
**Date:** 2026-06-10  
**Classification:** INTERNAL — OPERATIONS  
**Owner:** Site Reliability Engineering Team  
**Status:** ACTIVE

---

## 1. Incident Severity Levels

### SEV-1 — Critical
**Definition:** Complete service outage or severe degradation affecting all users.  
**Examples:**
- All API endpoints returning 500/502 for >5 minutes
- Cloudflare Worker completely unreachable
- ETAP engine unavailable and all AI providers down
- Security breach (credential compromise, unauthorized access)
- Data loss or corruption

**Response:**
- **Page immediately:** On-call SRE, Engineering Manager, Security Lead
- **Slack channel:** `#incidents-sev1`
- **War room:** Zoom/Meet within 10 minutes
- **Update frequency:** Every 15 minutes until resolved
- **Post-mortem:** Within 24 hours

### SEV-2 — Major
**Definition:** Significant degradation affecting a large portion of users or critical functionality.  
**Examples:**
- `/api/v1/studies/run` failing for >50% of requests
- AI provider failover exhausted (all 3 providers down)
- Rate limiting incorrectly blocking all users
- ETAP Worker service down (but AI fallback works)
- Data inconsistency in task store

**Response:**
- **Page:** On-call SRE
- **Slack channel:** `#incidents-sev2`
- **War room:** Optional (decision within 30 minutes)
- **Update frequency:** Every 30 minutes until resolved
- **Post-mortem:** Within 48 hours

### SEV-3 — Minor
**Definition:** Partial degradation affecting a small subset of users or non-critical functionality.  
**Examples:**
- Single agent endpoint returning errors
- Increased latency (>5s) on specific endpoints
- One AI provider down (failover working)
- Metrics endpoint returning stale data
- Non-critical UI elements broken

**Response:**
- **Notify:** On-call SRE (no page, Slack notification)
- **Slack channel:** `#incidents-sev3`
- **Update frequency:** Every 2 hours
- **Post-mortem:** Optional (within 1 week)

### SEV-4 — Informational
**Definition:** Issues that do not affect users or require immediate action.  
**Examples:**
- Warning logs increasing
- Deprecation notices
- Capacity approaching threshold
- Non-urgent security patches available
- Documentation gaps

**Response:**
- **Log:** In incident tracking system
- **Slack channel:** `#incidents-sev4`
- **Action:** Schedule during business hours
- **Post-mortem:** Not required

---

## 2. Escalation Matrix

| Time Since Detection | SEV-1 | SEV-2 | SEV-3 | SEV-4 |
|---|---|---|---|---|
| **0 min** | Page on-call SRE | Page on-call SRE | Slack notify SRE | Log ticket |
| **15 min** | Page Engineering Manager | — | — | — |
| **30 min** | Page CTO / VP Engineering | Page Engineering Manager | — | — |
| **1 hour** | Page CEO (if customer-facing) | — | Escalate to SRE lead | — |
| **2 hours** | Executive briefing | Escalate to CTO | — | — |
| **4 hours** | External comms (if needed) | Customer comms (if needed) | — | — |

**Escalation Path:**
1. On-call SRE
2. SRE Team Lead
3. Engineering Manager
4. CTO / VP Engineering
5. CEO (for SEV-1 with customer impact)

---

## 3. Incident Response Procedures

### 3.1 Detection

**Monitoring Sources:**
- Cloudflare Workers Analytics Dashboard
- `/health` endpoint polling (every 30s from 3 regions)
- `/metrics` endpoint for anomaly detection
- Error rate alerts (SEV-1: >10% error rate for 5 min)
- PagerDuty integration for automated paging

**Detection Commands:**
```bash
# Check health from multiple regions
curl -s https://ahmed-etap.ahmdelbaz28.workers.dev/health | jq .
curl -s https://ahmed-etap.ahmdelbaz28.workers.dev/metrics | jq .

# Check error rate
# (via Cloudflare Workers dashboard or log aggregation)

# Check provider health
curl -s https://ahmed-etap.ahmdelbaz28.workers.dev/api/v1/providers \
  -H "x-api-key: <secret>" | jq .
```

### 3.2 Triage

**Within 5 minutes of detection:**
1. Verify the issue is real (not a false alarm).
2. Determine severity level (SEV-1 to SEV-4).
3. Create incident ticket in tracking system.
4. Post initial status in `#incidents` Slack channel.

**Triage Questions:**
- Is the service completely down? → SEV-1
- Are users unable to run studies? → SEV-2
- Is one feature broken? → SEV-3
- Is this a warning? → SEV-4
- Is there a security component? → Escalate +1 level

### 3.3 Response

**SEV-1 Response Checklist:**
- [ ] Page on-call SRE
- [ ] Create `#incidents-sev1` Slack channel
- [ ] Start war room (Zoom/Meet)
- [ ] Identify incident commander (first SRE on call)
- [ ] Assess scope: number of affected users, endpoints, regions
- [ ] Apply immediate mitigation if known (e.g., rollback, disable feature)
- [ ] Communicate status every 15 minutes
- [ ] Page Engineering Manager at 15 min if not resolved
- [ ] Page CTO at 30 min if not resolved
- [ ] Document all actions in incident ticket

**SEV-2 Response Checklist:**
- [ ] Page on-call SRE
- [ ] Create `#incidents-sev2` Slack channel
- [ ] Assess scope
- [ ] Apply mitigation
- [ ] Communicate status every 30 minutes
- [ ] Page Engineering Manager at 30 min if not resolved

### 3.4 Mitigation

**Common Mitigations:**

| Issue | Mitigation | Time to Apply |
|---|---|---|
| Worker deployment broken | Rollback: `npx wrangler deploy --env=production` | 5 min |
| KV namespace issues | Recreate KV, update `wrangler.jsonc`, re-deploy | 10 min |
| AI provider down | Verify failover (automatic) — check `/api/v1/providers` | 2 min |
| All AI providers down | Enable static response mode (return queued status) | 5 min |
| Rate limiting too aggressive | Temporarily increase `RATE_LIMIT_REQUESTS_PER_MINUTE` | 2 min |
| ETAP Worker down | Restart container, check license | 10 min |
| High error rate | Enable maintenance mode (return 503 with retry-after) | 5 min |

### 3.5 Resolution

**Resolution Criteria:**
- All health checks pass for 5 consecutive minutes.
- Error rate returns to <1% for 10 minutes.
- Latency returns to P95 <2s for 10 minutes.
- All critical metrics within normal thresholds.

**Resolution Steps:**
1. Verify fix in production.
2. Close incident ticket with resolution timestamp.
3. Post final status in Slack.
4. Schedule post-mortem within 24h (SEV-1) or 48h (SEV-2).

### 3.6 Post-Mortem

**Required for:** SEV-1 (within 24h), SEV-2 (within 48h)  
**Optional for:** SEV-3 (within 1 week)

**Post-Mortem Template:**
```
# Incident Post-Mortem: <INCIDENT-ID>

## Summary
- Incident ID: <ID>
- Date: <DATE>
- Severity: <SEV>
- Duration: <START> to <END>
- Impact: <AFFECTED USERS / ENDPOINTS>

## Timeline
- <TIME>: Detection
- <TIME>: Triage
- <TIME>: Mitigation applied
- <TIME>: Resolution

## Root Cause
<Detailed description of what caused the incident>

## Impact
- Users affected: <COUNT>
- Requests failed: <COUNT>
- Data loss: <YES/NO, details>
- Financial impact: <IF APPLICABLE>

## Lessons Learned
- What went well?
- What went poorly?
- What was confusing?

## Action Items
| Action | Owner | Due Date | Priority |
|--------|-------|----------|----------|
| <Action> | <Owner> | <Date> | <P0/P1/P2> |

## Prevention
- How can we prevent this from happening again?
- What monitoring/alerting should be added?
```

---

## 4. Emergency Contacts

| Role | Name | Slack | Phone | Escalation |
|---|---|---|---|---|
| On-Call SRE | Rotation | @sre-oncall | PagerDuty | +30 min |
| SRE Team Lead | TBD | @sre-lead | — | +1 hour |
| Engineering Manager | TBD | @eng-manager | — | +2 hours |
| CTO / VP Engineering | TBD | @cto | — | +4 hours |
| Security Lead | TBD | @security-lead | — | Immediate for security |
| Cloudflare Support | — | — | https://support.cloudflare.com | Platform issues |
| ETAP Support | — | — | support@etap.com | ETAP engine issues |

---

## 5. Outage Procedures

### 5.1 Planned Maintenance

**Notification:** 24 hours in advance for maintenance windows >15 minutes.  
**Window:** Sundays 02:00–04:00 UTC (lowest traffic).  
**Procedure:**
1. Post maintenance notice in `#platform-status`.
2. Enable maintenance mode (if applicable).
3. Execute maintenance.
4. Verify all systems.
5. Post completion notice.

### 5.2 Unplanned Outage

**Immediate:**
1. Detect via monitoring or user report.
2. Triage and classify.
3. Apply fastest mitigation.
4. Communicate status.

**Communication Templates:**

**SEV-1 Initial:**
```
🚨 SEV-1 Incident: AhmedETAP is experiencing a complete outage.
- All API endpoints are returning errors.
- We are investigating and will update every 15 minutes.
- Incident channel: #incidents-sev1
- ETA: Unknown
```

**SEV-1 Update:**
```
🔔 SEV-1 Update (15 min): Root cause identified: <CAUSE>
- Mitigation in progress.
- ETA to resolution: <TIME>
```

**SEV-1 Resolved:**
```
✅ SEV-1 Resolved: Service is fully restored.
- Duration: <TIME>
- Root cause: <CAUSE>
- Post-mortem scheduled: <DATE/TIME>
```

---

## 6. Incident Response Tools

| Tool | Purpose | URL |
|---|---|---|
| PagerDuty | On-call paging and escalation | https://pagerduty.com |
| Slack | Real-time communication | #incidents, #incidents-sev1 |
| Cloudflare Dashboard | Worker analytics and logs | https://dash.cloudflare.com |
| Cloudflare Status | Platform status | https://www.cloudflarestatus.com |
| GitHub | Deployment history and rollback | https://github.com |
| wrangler CLI | Deployment and KV management | `npx wrangler` |

---

## 7. Training & Drills

| Drill | Frequency | Last Run | Next Run |
|---|---|---|---|
| SEV-1 simulation | Quarterly | — | 2026-09-10 |
| SEV-2 simulation | Quarterly | — | 2026-09-10 |
| Rollback drill | Monthly | 2026-06-10 | 2026-07-10 |
| Escalation test | Quarterly | — | 2026-09-10 |

---

*Document Classification: INTERNAL — OPERATIONS*  
*Distribution: All Engineering, SRE, Security, Leadership*  
*Review: Quarterly or after any SEV-1 incident*
