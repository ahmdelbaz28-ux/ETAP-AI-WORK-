# AhmedETAP — Cost Optimization Report

**Version:** 1.0.0  
**Date:** 2026-06-10  
**Classification:** INTERNAL — FINANCE  
**Owner:** Finance & Site Reliability Engineering  
**Status:** ACTIVE

---

## 1. Current Cost Analysis

### 1.1 Infrastructure Costs

| Service | Tier | Monthly Cost | Usage |
|---|---|---|---|
| **Cloudflare Workers** | Free | $0 | 100,000 requests/day |
| **Cloudflare KV** | Free | $0 | 1 GB storage, 100K reads/day |
| **LibSQL (Mastra)** | Local file | $0 | 10 MB database |
| **Docker (ETAP Engine)** | Local | $0 | 2 CPU, 4 GB RAM |
| **Redis** | Local | $0 | 512 MB |
| **Prometheus** | Local | $0 | Self-hosted |
| **Grafana** | Local | $0 | Self-hosted |
| **Total Infrastructure** | — | **$0** | — |

### 1.2 AI Provider Costs (Projected)

| Provider | Model | Cost per 1K tokens | Avg Request | Monthly Cost (100 users) |
|---|---|---|---|---|
| **OpenAI** | gpt-4o-mini | $0.15 / $0.60 | 2K tokens | $150 |
| **Qwen** | qwen-max | $0.05 / $0.10 | 2K tokens | $50 |
| **GLM** | glm-4 | $0.03 / $0.06 | 2K tokens | $30 |
| **Total AI** | — | — | — | **$230** |

### 1.3 Current Total Monthly Cost

| Category | Cost |
|---|---|
| Infrastructure | $0 |
| AI Providers | $0 (no live keys) |
| Monitoring | $0 |
| **Total** | **$0** |

---

## 2. Cost Growth Projections

### 2.1 Monthly Cost by User Scale

| Users | Infrastructure | AI Providers | Monitoring | Total |
|---|---|---|---|---|
| **50** | $0 | $115 | $0 | **$115** |
| **150** | $50 | $345 | $30 | **$425** |
| **500** | $200 | $1,150 | $50 | **$1,400** |
| **2,000** | $500 | $4,600 | $100 | **$5,200** |
| **10,000** | $2,000 | $23,000 | $300 | **$25,300** |

### 2.2 Cost per User

| Users | Cost/User/Month |
|---|---|
| 50 | $2.30 |
| 150 | $2.83 |
| 500 | $2.80 |
| 2,000 | $2.60 |
| 10,000 | $2.53 |

**Observation:** Cost per user decreases with scale due to fixed infrastructure costs being amortized.

---

## 3. Cost Controls Implemented

### 3.1 Rate Limiting

| Control | Value | Purpose |
|---|---|---|
| Default rate limit | 60 req/min/user | Prevent abuse |
| KV write batching | 100 entries/batch | Reduce KV write costs |
| AI token limit | 4,096 tokens/request | Control AI provider costs |

### 3.2 Caching

| Control | Value | Purpose |
|---|---|---|
| Agent list cache | 5 minutes | Reduce redundant requests |
| Provider health cache | 1 minute | Reduce health check overhead |
| Task status cache | 30 seconds | Reduce polling costs |

### 3.3 Task Store Eviction

| Control | Value | Purpose |
|---|---|---|
| Max task store size | 1,000 tasks | Limit memory usage |
| Task TTL | 1 hour | Auto-cleanup old tasks |
| Old task eviction | FIFO after 1 hour | Prevent memory bloat |

### 3.4 AI Provider Optimization

| Control | Value | Purpose |
|---|---|---|
| Failover chain | OpenAI → Qwen → GLM | Use cheapest provider first |
| Circuit breaker | 5 failures / 60s reset | Stop calling failed providers |
| Max retries | 2 per provider | Limit retry costs |
| Timeout | 30s per provider | Prevent hanging requests |

---

## 4. Budget Alerts

### 4.1 Alert Thresholds

| Alert | Threshold | Action |
|---|---|---|
| **Daily request quota** | 80% of 100,000 | Notify SRE to upgrade |
| **AI provider spend** | 80% of monthly budget | Throttle non-critical requests |
| **KV write limit** | 80% of 1,000/day | Batch writes more aggressively |
| **Error rate** | > 1% | Investigate (failed requests = wasted money) |
| **P95 latency** | > 3,000 ms | Scale resources |

### 4.2 Alert Implementation

```typescript
// In src/index.ts — cost monitoring
const _costMetrics = {
  aiTokensUsed: 0,
  aiRequests: 0,
  estimatedCost: 0,
};

function estimateCost(provider: string, tokens: number): number {
  const rates: Record<string, number> = {
    openai: 0.00015,
    qwen: 0.00005,
    glm: 0.00003,
  };
  return tokens * (rates[provider] || 0.00015);
}
```

---

## 5. Usage Dashboard

### 5.1 Metrics Endpoint

`GET /metrics` now includes:

```json
{
  "metrics": {
    "api": { "totalRequests": 1000, "authFailures": 5, "rateLimited": 10 },
    "providers": [{ "name": "openai", "calls": 500, "avgLatencyMs": 1200 }],
    "tasks": { "total": 50, "maxSize": 1000 },
    "audit": { "bufferSize": 25, "maxBufferSize": 100 }
  }
}
```

### 5.2 Cost Metrics to Add

| Metric | Source | Implementation |
|---|---|---|
| `aiTokensUsed` | `generateText` result | Add to `_apiMetrics` |
| `aiRequestsByProvider` | Provider metrics | Split by provider |
| `estimatedCost` | Token count × rate | Calculate in real-time |
| `dailyRequestCount` | `_apiMetrics.totalRequests` | Reset at midnight UTC |
| `dailySpend` | Sum of estimated costs | Alert at threshold |

---

## 6. Cost Optimization Recommendations

### 6.1 Immediate (This Month)

1. **Set AI provider budget alerts** — $100/day limit per provider.
2. **Enable request caching** — Cache `/api/v1/agents` for 5 minutes.
3. **Monitor free tier limits** — Alert at 80% of daily quota.

### 6.2 Short-term (Next 3 Months)

1. **Implement usage-based pricing** — Charge per study, per chat, per token.
2. **Add request quotas per API key** — Limit free tier users to 100 requests/day.
3. **Optimize AI prompts** — Shorter system prompts = fewer tokens = lower cost.

### 6.3 Medium-term (Next 6 Months)

1. **Migrate to cheaper models** — Use `gpt-4o-mini` for simple tasks, `gpt-4o` only for complex analysis.
2. **Implement response caching** — Cache study results for identical parameters.
3. **Batch processing** — Process studies in batches during off-peak hours.

### 6.4 Long-term (Next 12 Months)

1. **Fine-tune custom model** — Reduce dependency on OpenAI with a fine-tuned Qwen/GLM model.
2. **Implement tiered pricing** — Standard ($0.10/study), Premium ($0.50/study), Enterprise (custom).
3. **Cost allocation** — Tag resources by customer for chargeback.

---

## 7. Cost Comparison: Providers

| Provider | Cost per 1K Input | Cost per 1K Output | Quality | Reliability |
|---|---|---|---|---|
| **OpenAI (gpt-4o-mini)** | $0.15 | $0.60 | High | High |
| **Qwen (qwen-max)** | $0.05 | $0.10 | High | Medium |
| **GLM (glm-4)** | $0.03 | $0.06 | Medium | Medium |
| **OpenAI (gpt-4o)** | $2.50 | $10.00 | Very High | High |

**Recommendation:** Use `gpt-4o-mini` for 80% of requests, `qwen-max` for 15%, `glm-4` for 5% (failover only).

---

## 8. Monthly Budget Template

| Line Item | M1 (50 users) | M3 (150 users) | M6 (500 users) | M12 (2,000 users) |
|---|---|---|---|---|
| Cloudflare Workers | $0 | $5 | $20 | $100 |
| Cloudflare KV | $0 | $0 | $5 | $20 |
| PostgreSQL | $0 | $0 | $150 | $300 |
| Redis | $0 | $0 | $50 | $100 |
| ETAP Engine | $0 | $50 | $100 | $200 |
| AI Providers | $115 | $345 | $1,150 | $4,600 |
| Monitoring | $0 | $30 | $50 | $100 |
| **Total** | **$115** | **$430** | **$1,525** | **$5,420** |

---

*Document Classification: INTERNAL — FINANCE*  
*Distribution: Finance, SRE, Product, Engineering Leadership*  
*Review: Monthly*
