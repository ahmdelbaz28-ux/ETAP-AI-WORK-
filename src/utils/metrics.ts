/**
 * API + provider + circuit breaker metrics.
 *
 * Hardening additions:
 *   - per-API-key request counter
 *   - per-route category counter
 *   - per-provider latency, failure rate (delegated to providers module)
 *   - per-circuit-breaker state
 */
import type { Env } from '../core/types.js';
import { CONFIG } from '../core/config.js';
import { getProviderLatency } from '../core/providers.js';
import { getAllCircuitHealth } from '../core/circuitBreaker.js';

interface ApiMetrics {
  totalRequests: number;
  authFailures: number;
  rateLimited: number;
  errors: number;
  studyQueued: number;
  studyCompleted: number;
  studyFailed: number;
  agentChats: number;
  bodySizeRejections: number;
  idempotentReplays: number;
}

const _apiMetrics: ApiMetrics = {
  totalRequests: 0,
  authFailures: 0,
  rateLimited: 0,
  errors: 0,
  studyQueued: 0,
  studyCompleted: 0,
  studyFailed: 0,
  agentChats: 0,
  bodySizeRejections: 0,
  idempotentReplays: 0,
};

// Per-key counter (in-memory; bounded to last 100 keys to prevent leaks)
const _perKeyCounter: Map<string, number> = new Map();
const MAX_KEY_TRACKING = 100;

// Per-route-category counter
const _perRouteCounter: Map<string, number> = new Map();

let _lastMetricsSave = 0;
let _metricsLoaded = false;

export function bumpApiMetric(metric: keyof ApiMetrics, by = 1): void {
  _apiMetrics[metric] += by;
}

export function bumpPerKey(apiKeyId: string, by = 1): void {
  if (_perKeyCounter.size >= MAX_KEY_TRACKING && !_perKeyCounter.has(apiKeyId)) {
    // Evict oldest to keep memory bounded
    const oldest = _perKeyCounter.keys().next().value;
    if (oldest) _perKeyCounter.delete(oldest);
  }
  _perKeyCounter.set(apiKeyId, (_perKeyCounter.get(apiKeyId) ?? 0) + by);
}

export function bumpPerRoute(category: string, by = 1): void {
  _perRouteCounter.set(category, (_perRouteCounter.get(category) ?? 0) + by);
}

export function getApiMetrics(): ApiMetrics {
  return { ..._apiMetrics };
}

export function getPerKeyMetrics(): Record<string, number> {
  return Object.fromEntries(_perKeyCounter.entries());
}

export function getPerRouteMetrics(): Record<string, number> {
  return Object.fromEntries(_perRouteCounter.entries());
}

export async function loadMetrics(env: Env): Promise<void> {
  if (!env.METRICS_KV || _metricsLoaded) return;
  try {
    const raw = (await env.METRICS_KV.get('metrics:api', { type: 'json' })) as ApiMetrics | null;
    if (raw) Object.assign(_apiMetrics, raw);
  } catch {
    // silent
  }
  _metricsLoaded = true;
}

export async function saveMetrics(env: Env): Promise<void> {
  if (!env.METRICS_KV) return;
  const now = Date.now();
  if (now - _lastMetricsSave < CONFIG.METRICS_SAVE_INTERVAL_MS) return;
  _lastMetricsSave = now;
  try {
    await env.METRICS_KV.put('metrics:api', JSON.stringify(_apiMetrics), { expirationTtl: 7 * 24 * 60 * 60 });
  } catch {
    // silent
  }
}

export async function getTaskCount(env: Env): Promise<number> {
  if (!env.TASK_STORE_KV) return 0;
  try {
    const list = await env.TASK_STORE_KV.list({ prefix: 'task:', limit: 1000 });
    return list.keys.length;
  } catch {
    return 0;
  }
}

/** Compose the full metrics payload for /metrics. */
export async function composeMetrics(env: Env) {
  return {
    api: getApiMetrics(),
    providers: getProviderLatency(),
    circuits: getAllCircuitHealth(),
    perKey: getPerKeyMetrics(),
    perRoute: getPerRouteMetrics(),
    tasks: { total: await getTaskCount(env) },
  };
}
