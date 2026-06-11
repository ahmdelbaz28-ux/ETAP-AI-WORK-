# ENTERPRISE OPERATIONS HANDBOOK

## ETAP AI Engineering Platform — Operational Procedures

**Document ID:** OPS-001  
**Version:** 1.0  
**Date:** 2026-06-10  
**Classification:** Internal — Operational  
**Owner:** Enterprise Operations Director  
**Review Cycle:** Quarterly

---

## 1. SYSTEM OVERVIEW

### 1.1 Architecture Components

| Component | Technology | Purpose | Deployment |
|-----------|-----------|---------|------------|
| API Gateway | Cloudflare Workers | HTTP API, auth, rate limiting | `ahmed-etap.ahmdelbaz28.workers.dev` |
| Multi-Agent System | Mastra + TypeScript | Agent orchestration, reasoning | Cloudflare Workers |
| Python Engine | Python 3.11+ | ETAP calculations, load flow, short circuit | Docker / Kubernetes (future) |
| ETAP Integration | REST API | Remote ETAP worker communication | Cloudflare Workers (if remote) |
| State Store | Cloudflare KV | Rate limiting, audit logs, sessions | Cloudflare KV |
| Observability | LangWatch + Metrics API | Tracing, monitoring, alerting | Cloudflare Workers + LangWatch |
| Prompt Registry | Local YAML + LangWatch CLI | Prompt versioning, deployment | Git repository |

### 1.2 Service Dependencies

```
ETAP AI Platform
├── Cloudflare Workers Runtime (required)
│   ├── API_KEY_SECRET (required)
│   ├── JWT_SECRET (required)
│   ├── RATE_LIMIT_KV (required)
│   └── MASTRA_DUCKDB_PATH (optional)
├── LLM Providers (optional, failover enabled)
│   ├── OpenAI (primary)
│   ├── Qwen (secondary)
│   └── GLM (tertiary)
├── ETAP Backend (optional)
│   └── ETAP_WORKER_API_KEY (if remote)
└── LangWatch (optional)
    └── LANGWATCH_API_KEY
```

### 1.3 Health Endpoints

| Endpoint | Method | Expected | Purpose |
|----------|--------|----------|---------|
| `/health` | GET | `{"ok":true}` | Liveness probe |
| `/metrics` | GET | JSON counters | Observability metrics |
| `/api/v1/agents` | GET | Agent list | API readiness |
| `/api/v1/providers` | GET | Provider status | LLM provider health |
| `/api/v1/audit/logs` | GET | Audit entries | Audit log retrieval |

---

## 2. STARTUP PROCEDURES

### 2.1 New Environment Setup

#### Step 1: Cloudflare Workers Prerequisites
```bash
# 1. Ensure Cloudflare account is active
# 2. Ensure Workers subscription enabled
# 3. Ensure KV namespace created:
wrangler kv:namespace create "RATE_LIMIT_KV"
# 4. Note the KV namespace ID for wrangler.jsonc
```

#### Step 2: Secrets Configuration
```bash
# Set all required secrets
wrangler secret put API_KEY_SECRET
# Enter: <32-byte hex secret>

wrangler secret put JWT_SECRET
# Enter: <32-byte hex secret>

# Optional secrets
wrangler secret put OPENAI_API_KEY
wrangler secret put QWEN_API_KEY
wrangler secret put GLM_API_KEY
wrangler secret put ETAP_WORKER_API_KEY
wrangler secret put LANGWATCH_API_KEY
```

#### Step 3: Configuration Files
```bash
# Verify wrangler.jsonc has correct KV namespace ID
# Verify .env has all required variables
# Verify tsconfig.json is valid
```

#### Step 4: Build and Deploy
```bash
pnpm install
pnpm build
npx tsc --noEmit
npx wrangler deploy
```

#### Step 5: Validation
```bash
# Health check
curl https://<your-worker>.workers.dev/health

# API check (with valid key)
curl -H "x-api-key: <your-key>" \
  https://<your-worker>.workers.dev/api/v1/agents

# Metrics check
curl https://<your-worker>.workers.dev/metrics
```

### 2.2 Post-Startup Verification

- [ ] All health endpoints return 200
- [ ] All 9 agents are listed via `/api/v1/agents`
- [ ] Authentication rejects invalid keys (401)
- [ ] Rate limiting triggers after threshold
- [ ] Audit logging records test requests
- [ ] Metrics endpoint shows non-zero counters
- [ ] Provider health endpoint shows configured providers

---

## 3. SHUTDOWN PROCEDURES

### 3.1 Planned Shutdown

```bash
# 1. Notify users via status page or communication channel
# 2. Stop accepting new requests (if using a load balancer)
# 3. Wait for in-flight requests to complete (60s grace)
# 4. Deploy a maintenance page if needed
# 5. Stop the Cloudflare Worker:
#    - Option A: Deploy a maintenance Worker
#    - Option B: Remove the route in Cloudflare dashboard
# 6. Verify no traffic is reaching the Worker
# 7. Document shutdown in operations log
```

### 3.2 Emergency Shutdown

```bash
# 1. Immediately revoke API_KEY_SECRET:
wrangler secret put API_KEY_SECRET
# Enter a random invalid value

# 2. All authenticated requests will now fail

# 3. Notify Security Operations and Platform Owner

# 4. Investigate reason for shutdown

# 5. Restore when safe by rotating back to valid secret
```

### 3.3 Shutdown Verification

```bash
# Verify Worker is not responding
curl -I https://<your-worker>.workers.dev/health
# Expected: 404 or 503

# Verify no traffic in Cloudflare Analytics
# Dashboard → Workers → Overview
```

---

## 4. RECOVERY PROCEDURES

### 4.1 Worker Recovery (Fast — < 5 min)

**Scenario:** Worker deployment failed, runtime error, or 500 errors

```bash
# 1. Identify the issue via Cloudflare Logs
# 2. Check the last successful deployment

# 3. Rollback to previous version:
#    - Cloudflare Dashboard → Workers → Deployments
#    - Select previous deployment → Rollback

# 4. Verify recovery:
curl https://<your-worker>.workers.dev/health

# 5. If rollback fails, deploy a minimal health-only Worker:
#    wrangler deploy --name <worker-name>
#    with a minimal fetch handler that only returns /health

# 6. Fix the issue in the codebase
# 7. Re-deploy
```

### 4.2 Secret Recovery (Medium — < 15 min)

**Scenario:** Secret lost, corrupted, or accidentally deleted

```bash
# 1. Identify which secret is missing
# 2. Generate new secret:
NEW_SECRET=$(openssl rand -hex 32)

# 3. Deploy new secret:
wrangler secret put <SECRET_NAME>

# 4. Update all dependent services
# 5. Test all endpoints
# 6. Document in security incident log
```

### 4.3 KV Data Recovery (Medium — < 30 min)

**Scenario:** KV namespace data lost or corrupted

```bash
# 1. Check if backup exists:
#    - scripts/backup-mastra-db.ps1 (Windows)
#    - scripts/backup-mastra-db.sh (Linux/Mac)

# 2. If backup exists, restore:
#    - Re-upload rate limit keys
#    - Re-upload audit log entries

# 3. If no backup:
#    - Rate limits will reset (acceptable for short outage)
#    - Audit logs are lost (document in incident report)
#    - Re-initialize with empty state

# 4. Verify KV operations:
curl -H "x-api-key: <key>" https://<worker>/api/v1/studies/run
# Should succeed without rate limit errors
```

### 4.4 Full Environment Rebuild (Slow — < 60 min)

**Scenario:** Complete infrastructure loss, account compromise, or region failure

```bash
# 1. Create new Cloudflare account or use alternate account
# 2. Create new KV namespace
# 3. Update wrangler.jsonc with new KV ID
# 4. Re-deploy all secrets
# 5. Deploy the Worker:
wrangler deploy

# 6. Verify all endpoints
# 7. Update DNS if needed
# 8. Notify users
# 9. Update incident documentation
```

---

## 5. UPGRADE PROCEDURES

### 5.1 Dependency Upgrade

```bash
# 1. Check for outdated packages
pnpm outdated

# 2. Review changelogs for breaking changes

# 3. Upgrade in stages:
pnpm update <package-name>

# 4. Run typecheck
npx tsc --noEmit

# 5. Run tests
npx vitest run

# 6. Test locally
npx wrangler dev

# 7. Deploy to staging (if available)
# 8. Deploy to production
npx wrangler deploy

# 9. Verify production health
```

### 5.2 Node.js / pnpm Upgrade

```bash
# 1. Check current version
node --version
pnpm --version

# 2. Upgrade Node.js (via nvm or official installer)
# 3. Upgrade pnpm:
npm install -g pnpm

# 4. Re-install dependencies
rm -rf node_modules
pnpm install

# 5. Run full test suite
```

### 5.3 Cloudflare Workers Runtime Upgrade

```bash
# 1. Check wrangler compatibility
npx wrangler --version

# 2. Update wrangler:
pnpm update wrangler

# 3. Review Cloudflare Workers changelog
# 4. Test locally
# 5. Deploy
```

### 5.4 Python Engine Upgrade

```bash
# 1. Update requirements.txt
# 2. Test in Python 3.11+ environment
# 3. Run unit tests
python -m pytest tests/unit_tests.py

# 4. Update Docker image if applicable
# 5. Deploy to container runtime
```

---

## 6. ROLLBACK PROCEDURES

### 6.1 Code Rollback

```bash
# 1. Identify last known good deployment
# 2. Git checkout to that commit
git checkout <commit-hash>

# 3. Re-deploy
npx wrangler deploy

# 4. Verify
# 5. Create hotfix branch from stable commit
# 6. Fix the issue
# 7. Deploy fix
# 8. Merge fix back to main
```

### 6.2 Configuration Rollback

```bash
# 1. Identify last known good configuration
# 2. Restore from version control:
git checkout <commit-hash> -- wrangler.jsonc

# 3. Re-deploy
npx wrangler deploy

# 4. Verify
```

### 6.3 Secret Rollback

```bash
# Secrets cannot be retrieved once set.
# If you have a backup of the secret value:

# 1. Restore the secret
wrangler secret put <SECRET_NAME>
# Enter the backed-up value

# 2. Verify
# 3. If no backup, generate new secret and redistribute
```

---

## 7. MONITORING PROCEDURES

### 7.1 Daily Monitoring Checklist

```
[ ] Check /health endpoint on all environments
[ ] Review /metrics for API request counts
[ ] Check Cloudflare Workers dashboard for errors
[ ] Review rate limit hit patterns
[ ] Check LangWatch dashboard (if enabled)
[ ] Verify backup jobs completed
[ ] Check for any SEV incidents
```

### 7.2 Weekly Monitoring Checklist

```
[ ] Review API latency trends
[ ] Review error rate trends
[ ] Check LLM provider failover events
[ ] Review audit logs for anomalies
[ ] Verify capacity plan assumptions
[ ] Check cost dashboard
[ ] Review security event logs
```

### 7.3 Monthly Monitoring Checklist

```
[ ] Full capacity planning review
[ ] SLA/SLO compliance review
[ ] Cost optimization review
[ ] Security operations review
[ ] Disaster recovery readiness check
[ ] Backup verification test
[ ] Incident response drill
[ ] Documentation review
```

### 7.4 Alerting Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| API error rate | > 1% | > 5% | Investigate → Escalate |
| API latency (p95) | > 2s | > 5s | Optimize → Escalate |
| Rate limit hits | > 10% | > 25% | Review → Scale |
| Provider failures | 1 failover | 3 failovers | Investigate → Escalate |
| KV errors | Any | Sustained | Escalate |
| Authentication failures | > 5% | > 10% | Investigate → Security |

---

## 8. TROUBLESHOOTING GUIDE

### 8.1 Worker Returns 500

```
1. Check Cloudflare Logs (Dashboard → Workers → Logs)
2. Check for recent deployment
3. If recent deployment: ROLLBACK immediately
4. Check for missing secrets
5. Check for KV namespace errors
6. Test locally: npx wrangler dev
7. Fix and re-deploy
```

### 8.2 Authentication Failures (401)

```
1. Verify API key is correct
2. Check if secret was rotated recently
3. Check if key is passed in x-api-key header
4. Check KV namespace binding
5. Verify API_KEY_SECRET is set in wrangler
6. Test with known good key
```

### 8.3 Rate Limiting Issues (429)

```
1. Check current rate limit configuration
2. Review /metrics for rate_limit_hit count
3. Check if client is sending too many requests
4. Consider increasing limit if legitimate growth
5. Check for DDoS or abusive traffic
6. Implement additional IP-based blocking if needed
```

### 8.4 LLM Provider Failures

```
1. Check /api/v1/providers for provider status
2. Check provider API key validity
3. Review failover events in /metrics
4. Check provider-specific status pages
5. Verify fallback providers are configured
6. If all providers fail: queue requests for retry
```

### 8.5 ETAP Integration Failures

```
1. Check ETAP worker connectivity
2. Verify ETAP_WORKER_API_KEY
3. Check ETAP worker logs
4. Verify network connectivity
5. Check ETAP worker status endpoint
6. Retry with exponential backoff
```

### 8.6 DuckDB / Mastra Initialization Slow

```
1. Check if lazy initialization is enabled
2. Verify DuckDBStore is not blocking on startup
3. Check memory usage in Cloudflare Workers
4. Consider warm-start strategies
5. Monitor initialization time in /metrics
```

### 8.7 Audit Logs Not Appearing

```
1. Check if _flushAuditLog is being called
2. Verify KV namespace has write permissions
3. Check KV TTL settings (90 days)
4. Test with manual audit log write
5. Check /api/v1/audit/logs endpoint
```

---

## 9. MAINTENANCE WINDOWS

### 9.1 Scheduled Maintenance

| Window | Frequency | Activities |
|--------|-----------|------------|
| Low-traffic hours | Weekly | Deploy non-critical updates, dependency patches |
| Weekend | Monthly | Major upgrades, configuration changes |
| Planned downtime | Quarterly | Infrastructure changes, capacity adjustments |

### 9.2 Maintenance Procedures

```
1. Schedule maintenance window
2. Notify stakeholders (48 hours advance)
3. Put system in maintenance mode (if applicable)
4. Execute maintenance tasks
5. Verify system health
6. Remove maintenance mode
7. Notify stakeholders of completion
8. Document in operations log
```

---

## 10. OPERATIONAL CONTACTS

| Role | Primary | Secondary |
|------|---------|-----------|
| Platform Owner | platform@company.com | platform-backup@company.com |
| SRE On-Call | sre-oncall@company.com | sre-backup@company.com |
| Security Operations | secops@company.com | secops-backup@company.com |
| ETAP Architect | etap@company.com | etap-backup@company.com |
| Cloud Architect | cloud@company.com | cloud-backup@company.com |
| AI Infrastructure | ai-infra@company.com | ai-infra-backup@company.com |
| Observability Lead | observability@company.com | observability-backup@company.com |

---

## 11. DOCUMENT CONTROL

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-06-10 | Enterprise Operations | Initial release |

**Next Review:** 2026-09-10

**Approved By:** _________________

---

**END OF DOCUMENT**
