# ETAP AI Platform — Capacity Plan

**Version:** 1.0.0  
**Date:** 2026-06-10  
**Classification:** INTERNAL — OPERATIONS  
**Owner:** Site Reliability Engineering & Product  
**Status:** ACTIVE

---

## 1. Current Capacity Baseline

### 1.1 Infrastructure

| Component | Current Spec | Usage |
|---|---|---|
| Cloudflare Worker | Free Tier | Active |
| KV Namespace | 1 namespace (rate-limit-kv) | Active |
| Mastra Storage | LibSQL (local file) | Active |
| DuckDB Observability | Lazy-initialized | Active |
| ETAP Python Engine | Single process (Docker) | Active |
| Redis Cache | 512 MB (Docker) | Optional |

### 1.2 Load Test Results (Evidence)

| Metric | Value | Evidence |
|---|---|---|
| Max concurrent users (100% success) | 100 users | Load test: 100/100 success |
| Max concurrent users (98.8% success) | 500 users | Load test: 494/500 success |
| Max throughput (health check) | 42 req/s | Load test: Run Study (50 users) |
| Max throughput (sustained) | 50 req/s | Stress test: 500 req/10s |
| Burst capacity | 1,000 req/s | Stress test: 643/1,000 success |
| P95 latency at 100 users | 3,545 ms | Load test evidence |
| P99 latency at 100 users | 6,488 ms | Load test evidence |

### 1.3 Current Limits

| Limit | Value | Hard/Soft |
|---|---|---|
| Cloudflare Worker requests/day | 100,000 | Hard (free tier) |
| Cloudflare Worker CPU time | 50 ms/request | Hard (free tier) |
| KV reads/day | 100,000 | Hard (free tier) |
| KV writes/day | 1,000 | Hard (free tier) |
| KV list/day | 1,000 | Hard (free tier) |
| KV storage | 1 GB | Hard (free tier) |
| In-memory task store | 1,000 tasks | Soft (configurable) |
| Rate limit window | 60 seconds | Soft (configurable) |
| Rate limit default | 60 req/min | Soft (configurable) |

---

## 2. Maximum Capacity Calculations

### 2.1 API Gateway (Cloudflare Worker)

**Free Tier Limits:**
- 100,000 requests/day = 69.4 requests/minute average
- 50 ms CPU time per request

**Realistic Maximum (with 95% success rate):**
```
Concurrent Users: 200
Requests per User: 10/minute
Total Requests: 2,000/minute = 120,000/hour
Daily Capacity: 100,000 requests/day

Conclusion: Free tier supports ~150 active users making 10 requests/minute.
```

**Paid Tier (Workers Paid):**
- $0.50 per million requests
- No daily limit
- 400 ms CPU time per request

**Realistic Maximum (Paid):**
```
Concurrent Users: 1,000
Requests per User: 10/minute
Total Requests: 10,000/minute = 600,000/hour
Daily Capacity: 14,400,000 requests/day

Conclusion: Paid tier supports ~1,000 concurrent users.
```

### 2.2 KV Storage (Rate Limiting + Audit Logs)

**Current Usage:**
- Rate limiting: ~1 write per unique IP per minute
- Audit logs: ~1 write per 100 requests (batched)

**Free Tier (1 GB):**
- Audit logs: 100 entries/day × 90 days = 9,000 entries ≈ 5 MB
- Rate limit counters: 1,000 IPs × 100 bytes = 100 KB
- **Total: < 10 MB** — well within 1 GB limit

**At Scale (1,000 users):**
- Audit logs: 10,000 entries/day × 90 days = 900,000 entries ≈ 500 MB
- Rate limit counters: 10,000 IPs × 100 bytes = 1 MB
- **Total: ~500 MB** — still within 1 GB limit

### 2.3 Mastra Database (LibSQL)

**Current:**
- `mastra.db` file size: ~10 MB (estimated)
- Agent memory: ~1 MB per agent
- Observability: DuckDB lazy init

**Growth Projection:**
- 100 users × 100 conversations/day = 10,000 records/day
- 1 year: 3.65 million records ≈ 500 MB
- **Recommendation:** Migrate to PostgreSQL at 500 MB

### 2.4 ETAP Python Engine

**Current:**
- Single process
- 2 CPU cores, 4 GB RAM (Docker)

**Capacity:**
- Load Flow: 1 study/second (small system)
- Short Circuit: 2 studies/second
- Arc Flash: 0.5 studies/second (complex calculation)

**Scaling:**
- Horizontal: Multiple engine containers with RabbitMQ queue
- Vertical: 4 CPU cores, 8 GB RAM for 2× throughput

---

## 3. Capacity Forecasts

### 3.1 User Growth Forecast

| Month | Users | Concurrent Users | Daily Requests | Monthly Requests |
|---|---|---|---|---|
| **M1 (Current)** | 50 | 10 | 5,000 | 150,000 |
| **M3** | 150 | 30 | 15,000 | 450,000 |
| **M6** | 500 | 100 | 50,000 | 1,500,000 |
| **M12** | 2,000 | 400 | 200,000 | 6,000,000 |
| **M24** | 10,000 | 2,000 | 1,000,000 | 30,000,000 |

### 3.2 Infrastructure Scaling Plan

| Month | Worker Tier | KV Tier | Database | Engine | Cost/Month |
|---|---|---|---|---|---|
| **M1–M3** | Free | Free | LibSQL | 1 container | $0 |
| **M4–M6** | Paid ($5) | Free | LibSQL | 2 containers | $50 |
| **M7–M12** | Paid ($20) | Paid ($5) | PostgreSQL | 3 containers | $200 |
| **M13–M24** | Enterprise ($100) | Enterprise ($20) | PostgreSQL + read replicas | 5 containers | $500 |

### 3.3 Resource Requirements

| Month | CPU Cores | RAM | Storage | Bandwidth |
|---|---|---|---|---|
| **M1–M3** | 2 | 4 GB | 50 GB | 100 GB |
| **M4–M6** | 4 | 8 GB | 100 GB | 500 GB |
| **M7–M12** | 8 | 16 GB | 500 GB | 2 TB |
| **M13–M24** | 16 | 32 GB | 2 TB | 10 TB |

---

## 4. Scaling Triggers

| Trigger | Threshold | Action | Owner |
|---|---|---|---|
| Daily requests | > 80,000 | Upgrade to Workers Paid | SRE |
| P95 latency | > 3,000 ms (10 min) | Enable caching + horizontal scaling | SRE |
| Error rate | > 1% | Investigate + scale engine | SRE |
| KV write limit | > 800/day | Upgrade KV tier | SRE |
| Task queue depth | > 800 | Add engine containers | SRE |
| DB size | > 400 MB | Migrate to PostgreSQL | SRE |
| AI provider latency | > 10,000 ms | Enable additional provider | Platform |

---

## 5. Capacity Limits by Feature

| Feature | Max Concurrent | Max Daily | Bottleneck |
|---|---|---|---|
| Health Check | 500 | 100,000 | Worker free tier |
| List Agents | 500 | 100,000 | Worker free tier |
| Agent Chat | 100 | 50,000 | AI provider rate limits |
| Run Study | 50 | 10,000 | Python engine CPU |
| ETAP Automation | 10 | 1,000 | ETAP COM single-thread |
| Audit Log Retrieval | 100 | 100,000 | KV read limits |

---

## 6. Cost Scaling Model

| Users | Monthly Cost | Cost per User |
|---|---|---|
| 50 | $0 | $0.00 |
| 150 | $50 | $0.33 |
| 500 | $200 | $0.40 |
| 2,000 | $500 | $0.25 |
| 10,000 | $2,000 | $0.20 |

**Cost Breakdown at 2,000 Users:**
- Cloudflare Workers: $100
- Cloudflare KV: $20
- PostgreSQL (managed): $150
- Redis (managed): $50
- ETAP Engine containers: $100
- Monitoring (Prometheus/Grafana): $30
- AI providers (OpenAI): $500
- **Total: $950/month**

---

## 7. Recommendations

### Immediate (M1–M3)
1. **Monitor free tier limits** — Set alerts at 80% of daily request quota.
2. **Enable Workers Paid** — Prepare for $5/month plan before hitting limits.
3. **Database backup** — Automate hourly `mastra.db` backups.

### Short-term (M4–M6)
1. **Migrate to PostgreSQL** — When `mastra.db` exceeds 200 MB.
2. **Scale ETAP Engine** — Run 2 containers with RabbitMQ queue.
3. **Enable KV Paid** — When write limits approach 1,000/day.

### Medium-term (M7–M12)
1. **Horizontal scaling** — 3 Worker instances with load balancer.
2. **Read replicas** — PostgreSQL read replicas for analytics.
3. **CDN caching** — Cache agent responses for 5 minutes.

### Long-term (M13–M24)
1. **Multi-region** — Deploy to 2 Cloudflare regions.
2. **Auto-scaling** — Kubernetes HPA for engine containers.
3. **Cost optimization** — Implement usage-based billing.

---

*Document Classification: INTERNAL — OPERATIONS*  
*Distribution: SRE, Product, Engineering Leadership, Finance*  
*Review: Monthly or after capacity trigger*
