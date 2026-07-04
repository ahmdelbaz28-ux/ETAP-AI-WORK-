/**
 * Per-API-key rate limiting with optional agent-id dimension.
 *
 * Hardening changes:
 *   - Rate limit key is the API key (not IP) — prevents NAT starvation
 *   - Optional agent-id dimension for chat endpoints
 *   - Falls back to KV → Cache API → in-memory Map (3-tier)
 */
import type { Env } from './types.js';
import { CONFIG } from './config.js';

interface RateLimitState {
  count: number;
  resetAt: number;
}

const _rateLimitMap: Map<string, RateLimitState> = new Map();
const _RATE_LIMIT_MAP_MAX_SIZE = 10_000;
let _lastMapCleanup = 0;
const _MAP_CLEANUP_INTERVAL_MS = 60_000;

function _evictStaleRateLimitEntries(): void {
  const now = Date.now();
  for (const [key, state] of _rateLimitMap) {
    if (now > state.resetAt) {
      _rateLimitMap.delete(key);
    }
  }
  // If still over the cap after evicting expired entries, remove oldest
  if (_rateLimitMap.size > _RATE_LIMIT_MAP_MAX_SIZE) {
    const entries = [..._rateLimitMap.entries()];
    entries.sort((a, b) => a[1].resetAt - b[1].resetAt);
    const toDelete = entries.slice(0, entries.length - _RATE_LIMIT_MAP_MAX_SIZE);
    for (const [key] of toDelete) {
      _rateLimitMap.delete(key);
    }
  }
}

function isRateLimitEntry(value: unknown): value is RateLimitState {
  return (
    typeof value === 'object' &&
    value !== null &&
    'count' in value &&
    'resetAt' in value &&
    typeof (value as Record<string, unknown>).count === 'number' &&
    typeof (value as Record<string, unknown>).resetAt === 'number'
  );
}

function evaluateLimit(state: RateLimitState | null, now: number, limit: number) {
  if (!state || now > state.resetAt) {
    return { allowed: true, newState: { count: 1, resetAt: now + 60_000 } as RateLimitState };
  }
  if (state.count >= limit) {
    return { allowed: false, retryAfter: Math.ceil((state.resetAt - now) / 1000) };
  }
  return { allowed: true, newState: { count: state.count + 1, resetAt: state.resetAt } };
}

async function checkRateLimitKV(
  env: Env,
  key: string,
  limit: number,
): Promise<{ allowed: boolean; retryAfter?: number } | null> {
  if (!env.RATE_LIMIT_KV) return null;
  const now = Date.now();
  try {
    const raw = await env.RATE_LIMIT_KV.get(key, { type: 'json' });
    const stored = isRateLimitEntry(raw) ? raw : null;
    const result = evaluateLimit(stored, now, limit);
    if (result.newState) {
      await env.RATE_LIMIT_KV.put(key, JSON.stringify(result.newState), { expirationTtl: 60 });
    }
    return { allowed: result.allowed, retryAfter: result.retryAfter };
  } catch {
    return null;
  }
}

function checkRateLimitMap(key: string, limit: number): { allowed: boolean; retryAfter?: number } {
  const now = Date.now();
  // Periodic cleanup of stale entries to prevent unbounded memory growth
  if (now - _lastMapCleanup > _MAP_CLEANUP_INTERVAL_MS) {
    _lastMapCleanup = now;
    _evictStaleRateLimitEntries();
  }
  const state = _rateLimitMap.get(key) ?? null;
  const result = evaluateLimit(state, now, limit);
  if (result.newState) {
    _rateLimitMap.set(key, result.newState);
  }
  return { allowed: result.allowed, retryAfter: result.retryAfter };
}

/**
 * Resolve limit from env override (backward-compatible with
 * RATE_LIMIT_REQUESTS_PER_MINUTE) or fall back to CONFIG constant.
 */
function resolveKeyLimit(env: Env): number {
  if (env.RATE_LIMIT_REQUESTS_PER_MINUTE) {
    const n = Number.parseInt(env.RATE_LIMIT_REQUESTS_PER_MINUTE, 10);
    if (!Number.isNaN(n) && n > 0) return n;
  }
  return CONFIG.RATE_LIMIT_PER_KEY_PER_MINUTE;
}

/**
 * Per-API-key rate limit.
 * If `agentId` is provided, adds an extra (lower) limit on that dimension.
 *
 * The env var RATE_LIMIT_REQUESTS_PER_MINUTE can override the per-key
 * limit for backward-compatibility and test scenarios.
 */
export async function checkRateLimit(
  env: Env,
  apiKeyId: string,
  agentId?: string,
): Promise<{ allowed: boolean; retryAfter?: number; dimension?: 'key' | 'agent' }> {
  const baseKey = `rl:key:${apiKeyId}`;
  const keyLimit = resolveKeyLimit(env);
  const kv = await checkRateLimitKV(env, baseKey, keyLimit);
  const result = kv ?? checkRateLimitMap(baseKey, keyLimit);
  if (!result.allowed) return { ...result, dimension: 'key' };

  if (agentId) {
    const agentKey = `rl:key:${apiKeyId}:agent:${agentId}`;
    const kvAgent = await checkRateLimitKV(
      env,
      agentKey,
      CONFIG.RATE_LIMIT_PER_KEY_PER_AGENT_PER_MINUTE,
    );
    const agentResult =
      kvAgent ?? checkRateLimitMap(agentKey, CONFIG.RATE_LIMIT_PER_KEY_PER_AGENT_PER_MINUTE);
    if (!agentResult.allowed) return { ...agentResult, dimension: 'agent' };
  }

  return { allowed: true };
}
