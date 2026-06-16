# AhmedETAP — Disaster Recovery Plan

**Version:** 1.0.0  
**Date:** 2026-06-10  
**Classification:** INTERNAL — CRITICAL  
**Owner:** Disaster Recovery Architect  
**RTO Target:** < 30 minutes  
**RPO Target:** < 15 minutes  
**Activation Threshold:** Any SEV-1 incident or complete service unavailability

---

## 1. Recovery Objectives

| Objective | Target | Measurement |
|---|---|---|
| **RTO (Recovery Time Objective)** | < 30 minutes | Time from incident declaration to full service restoration |
| **RPO (Recovery Point Objective)** | < 15 minutes | Maximum acceptable data loss (last backup to incident time) |
| **MTO (Maximum Tolerable Outage)** | 60 minutes | Maximum time the business can tolerate outage before critical impact |
| **WRT (Work Recovery Time)** | 30 minutes | Time to validate all systems are operational post-recovery |

---

## 2. Service Inventory & Criticality

| Service | Tier | RTO | RPO | Recovery Method | Owner |
|---|---|---|---|---|---|
| Cloudflare Worker API Gateway | Tier 1 | 15 min | 0 min | Re-deploy via `wrangler deploy` | SRE |
| KV Namespace (Rate Limiting) | Tier 2 | 30 min | 15 min | Recreate + rebind in `wrangler.jsonc` | SRE |
| Mastra Backend (LibSQL/DuckDB) | Tier 2 | 30 min | 15 min | Restore from `mastra.db` backup | SRE |
| ETAP Python Engine | Tier 1 | 20 min | 0 min | Restart Docker container / K8s pod | SRE |
| ETAP Worker Service | Tier 1 | 20 min | 0 min | Restart Windows container | SRE |
| Prompt Registry | Tier 3 | 60 min | 60 min | Restore from Git repository | DevOps |
| Agent Configuration | Tier 3 | 60 min | 60 min | Restore from Git repository | DevOps |
| Secrets (API keys, JWT) | Tier 1 | 15 min | 0 min | Re-set via `wrangler secret put` | Security |
| Redis Cache | Tier 3 | 45 min | 0 min | Warm restart (data rebuildable) | SRE |

---

## 3. Disaster Scenarios & Recovery Procedures

### 3.1 Scenario A — Cloudflare Worker Platform Outage
**Impact:** All API endpoints unreachable.  
**Detection:** Health check endpoint (`/health`) fails from multiple regions.  
**Recovery:**

1. **Declare incident** (5 min) — Page on-call SRE, create SEV-1 ticket.
2. **Verify Cloudflare status** (5 min) — Check `https://www.cloudflarestatus.com/`.
3. **If Cloudflare platform is down:**
   - Activate DNS failover to backup origin (if configured).
   - Switch to Docker Compose deployment on backup VM (15 min).
4. **If Worker-specific issue:**
   - Roll back to last known good deployment: `npx wrangler deploy --env=production` (5 min).
   - Verify `/health` returns 200.
5. **Post-recovery validation** (10 min):
   - Run `curl -s https://<domain>/health`
   - Run `curl -s https://<domain>/api/v1/agents -H "x-api-key: <secret>"`
   - Run `curl -s https://<domain>/metrics`
   - Confirm all provider health is `true`.

**RTO:** 15–25 minutes  
**RPO:** 0 minutes (stateless Worker)

---

### 3.2 Scenario B — KV Namespace Corruption / Loss
**Impact:** Rate limiting data lost. Users may experience incorrect rate limits.  
**Detection:** KV `get` operations returning null unexpectedly.  
**Recovery:**

1. **Verify KV status** (5 min) — `npx wrangler kv namespace list`
2. **If namespace is corrupted:**
   - Create new KV namespace: `npx wrangler kv namespace create "rate-limit-kv-backup"`
   - Update `wrangler.jsonc` with new ID.
   - Re-deploy Worker: `npx wrangler deploy`
3. **Data loss impact:** Minimal — rate limit counters are reset. No critical data lost.
4. **Validation:** Confirm rate limiting works on test requests.

**RTO:** 10 minutes  
**RPO:** 15 minutes (counters are transient)

---

### 3.3 Scenario C — Mastra Database (`mastra.db`) Corruption
**Impact:** Agent memory, observability data, and storage lost.  
**Detection:** Mastra startup errors or DuckDB initialization failures.  
**Recovery:**

1. **Stop Mastra backend** (2 min).
2. **Restore from backup** (10 min):
   - Locate latest backup: `backups/mastra.db.YYYY-MM-DD-HH-MM.bak`
   - Replace `mastra.db` with backup.
   - If no backup, re-initialize with `pnpx mastra init` (creates fresh schema).
3. **Restart Mastra** (3 min).
4. **Validate:**
   - Check `npx tsx -e "import {mastra} from './src/mastra/index.js'; console.log('OK', Object.keys(mastra.getAgents()).length)"`
   - Confirm all 9 agents load.

**RTO:** 20 minutes  
**RPO:** 15 minutes (with hourly backups)

---

### 3.4 Scenario D — ETAP Worker Service Failure
**Impact:** No ETAP COM automation. Python studies cannot run.  
**Detection:** `curl http://etap-worker:8081/health` fails.  
**Recovery:**

1. **Restart container** (5 min):
   - `docker-compose restart etap-worker` (Docker)
   - `kubectl rollout restart deployment/etap-worker -n etap-platform` (K8s)
2. **If restart fails:**
   - Pull latest image: `docker-compose pull etap-worker`
   - Rebuild: `docker-compose up -d --build etap-worker`
3. **Verify health** (5 min):
   - `curl -s http://etap-worker:8081/health`
   - Run Python engine test: `python -c "from engine.engine import PowerSystemEngine; print('OK')"`
4. **If ETAP license is invalid:**
   - Check `ETAP_LICENSE_PATH` environment variable.
   - Re-activate license via ETAP admin console.

**RTO:** 20 minutes  
**RPO:** 0 minutes (ETAP engine is stateless)

---

### 3.5 Scenario E — Complete Environment Destruction
**Impact:** All infrastructure lost. Complete rebuild required.  
**Detection:** Multiple services down simultaneously.  
**Recovery:**

1. **Provision new environment** (10 min):
   - Cloudflare Workers: `npx wrangler deploy` (from CI/CD or local)
   - KV: `npx wrangler kv namespace create "rate-limit-kv"`
   - Update `wrangler.jsonc` with new KV ID.
   - Re-set secrets: `wrangler secret put API_KEY_SECRET`, `wrangler secret put OPENAI_API_KEY`, etc.
2. **Restore databases** (10 min):
   - Restore `mastra.db` from backup.
   - Restore `prompts.json` from Git.
3. **Restore configuration** (5 min):
   - `wrangler.jsonc` from Git.
   - `docker-compose.yml` from Git.
   - `.env` from encrypted backup.
4. **Verify** (5 min):
   - Run full test suite: `npx vitest run`
   - Run Python tests: `python -m pytest tests/unit_tests.py`
   - Verify all endpoints: `curl` test script.

**RTO:** 30 minutes  
**RPO:** 15 minutes

---

## 4. Backup Strategy

| Data | Frequency | Retention | Location | Method |
|---|---|---|---|---|
| `wrangler.jsonc` | Every commit | Infinite | Git repository | Git |
| `src/` | Every commit | Infinite | Git repository | Git |
| `mastra.db` | Hourly | 7 days | Local + Cloud backup | Cron + `cp` |
| `prompts/*.yaml` | Every commit | Infinite | Git repository | Git |
| Cloudflare KV | Weekly | 4 weeks | KV list export | `wrangler kv key list` |
| Secrets | On change | Last 2 versions | Password manager / Vault | Manual + Vault |
| Docker volumes | Daily | 7 days | Backup server | `docker volume backup` |

---

## 5. Emergency Contacts

| Role | Contact | Escalation |
|---|---|---|
| On-Call SRE | PagerDuty / Slack #sre-oncall | +30 min → Engineering Manager |
| Security Lead | Slack #security-oncall | Immediate for credential compromise |
| Cloudflare Support | https://support.cloudflare.com | Tier 2 for platform issues |
| ETAP Support | support@etap.com | For ETAP license/engine issues |

---

## 6. DR Testing Schedule

| Test | Frequency | Last Run | Next Run | Owner |
|---|---|---|---|---|
| Worker rollback | Monthly | 2026-06-10 | 2026-07-10 | SRE |
| KV namespace recreate | Quarterly | — | 2026-09-10 | SRE |
| `mastra.db` restore | Monthly | — | 2026-07-10 | SRE |
| Full environment rebuild | Quarterly | — | 2026-09-10 | SRE |
| ETAP Worker restart | Monthly | — | 2026-07-10 | SRE |
| Secret rotation drill | Quarterly | — | 2026-09-10 | Security |

---

## 7. DR Plan Activation

**Activation Authority:** On-Call SRE, Engineering Manager, or Security Lead  
**Activation Method:**
1. Create SEV-1 incident ticket.
2. Page on-call SRE via PagerDuty.
3. Post in `#incidents` Slack channel.
4. Notify stakeholders in `#platform-status`.

**Deactivation Criteria:**
- All health checks pass for 5 consecutive minutes.
- All critical metrics (RTO, error rate, latency) return to normal.
- Post-incident review scheduled within 24 hours.

---

*Document Classification: INTERNAL — CRITICAL*  
*Distribution: SRE Team, Engineering Leadership, Security Team*  
*Review: Quarterly or after any SEV-1 incident*
