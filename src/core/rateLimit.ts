/*
 * Rate limiting: per-key + per-agent + per-endpoint + per-IP brute-force defense.
 *
 * Security additions per Better Auth skill:
 *   - Per-IP rate limiting for unauthenticated requests
 *   - IP ban mechanism (sustained abuse = auto 15-min ban)
 *   - Per-endpoint custom rate limits (studies tighter than chat)
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

function _evictStaleEntries(): void {
  const now = Date.now();
  for (const [key, state] of _rateLimitMap) {
    if (now > state.resetAt) _rateLimitMap.delete(key);
  }
  if (_rateLimitMap.size > _RATE_LIMIT_MAP_MAX_SIZE) {
    const entries = [..._rateLimitMap.entries()].sort((a, b) => a[1].resetAt - b[1].resetAt);
    for (const [key] of entries.slice(0, entries.length - _RATE_LIMIT_MAP_MAX_SIZE)) {
      _rateLimitMap.delete(key);
    }
  }
}

function isRlState(value: unknown): value is RateLimitState {
  return typeof value === 'object' && value !== null &&
    typeof (value as Record<string, unknown>).count === 'number' &&
    typeof (value as Record<string, unknown>).resetAt === 'number';
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

async function kvCheck(env: Env, key: string, limit: number): Promise<{ allowed: boolean; retryAfter?: number } | null> {
  if (!env.RATE_LIMIT_KV) return null;
  try {
    const raw = await env.RATE_LIMIT_KV.get(key, { type: 'json' });
    const stored = isRlState(raw) ? raw : null;
    const result = evaluateLimit(stored, Date.now(), limit);
    if (result.newState) {
      await env.RATE_LIMIT_KV.put(key, JSON.stringify(result.newState), { expirationTtl: 120 });
    }
    return { allowed: result.allowed, retryAfter: result.retryAfter };
  } catch { return null; }
}

function mapCheck(key: string, limit: number): { allowed: boolean; retryAfter?: number } {
  const now = Date.now();
  if (now - _lastMapCleanup > _MAP_CLEANUP_INTERVAL_MS) {
    _lastMapCleanup = now;
    _evictStaleEntries();
  }
  const result = evaluateLimit(_rateLimitMap.get(key) ?? null, now, limit);
  if (result.newState) _rateLimitMap.set(key, result.newState);
  return { allowed: result.allowed, retryAfter: result.retryAfter };
}

function resolveKeyLimit(env: Env): number {
  if (env.RATE_LIMIT_REQUESTS_PER_MINUTE) {
    const n = Number.parseInt(env.RATE_LIMIT_REQUESTS_PER_MINUTE, 10);
    if (!Number.isNaN(n) && n > 0) return n;
  }
  return CONFIG.RATE_LIMIT_PER_KEY_PER_MINUTE;
}

/*
 * Per-endpoint rate limit (most sensitive routes get tighter limits).
 * Per Better Auth skill: customRules per endpoint.
 */
async function checkEndpointLimit(env: Env, method: string, path: string, apiKeyId: string): Promise<{ allowed: boolean; retryAfter?: number }> {
  const key = `${method}:${path}`;
  const rule = CONFIG.ENDPOINT_RATE_LIMITS[key];
  if (!rule) return { allowed: true };
  const kvKey = `rl:endpoint:${apiKeyId}:${key}`;
  const kv = await kvCheck(env, kvKey, rule.max);
  return kv ?? mapCheck(kvKey, rule.max);
}

/*
 * Check if an IP is banned.
 */
export async function isIpBanned(env: Env, clientIp: string): Promise<boolean> {
  if (!env.IP_BLOCK_KV || clientIp === 'unknown') return false;
  try {
    const rec = await env.IP_BLOCK_KV.get(`ban:${clientIp}`, { type: 'json' }) as { expiresAt: number } | null;
    if (!rec) return false;
    if (Date.now() > rec.expiresAt) {
      await env.IP_BLOCK_KV.delete(`ban:${clientIp}`);
      return false;
    }
    return true;
  } catch { return false; }
}

/*
 * Per-IP rate limiting for unauthenticated requests.
 * Tracks failures and auto-bans after IP_RATE_LIMIT_BAN_THRESHOLD.
 */
export async function checkIpRateLimit(env: Env, clientIp: string): Promise<{ allowed: boolean; banned: boolean; retryAfter?: number }> {
  if (clientIp === 'unknown') return { allowed: true, banned: false };

  const banned = await isIpBanned(env, clientIp);
  if (banned) return { allowed: false, banned: true, retryAfter: CONFIG.IP_RATE_LIMIT_BAN_DURATION_SECONDS };

  const key = `rl:ip:${clientIp}`;
  const kv = await kvCheck(env, key, CONFIG.IP_RATE_LIMIT_PER_MINUTE);
  const result = kv ?? mapCheck(key, CONFIG.IP_RATE_LIMIT_PER_MINUTE);

  if (!result.allowed) {
    // Increment failure counter for ban threshold
    if (env.RATE_LIMIT_KV) {
      const failKey = `rl:ip-fail:${clientIp}`;
      try {
        const raw = await env.RATE_LIMIT_KV.get(failKey, { type: 'json' }) as { count: number; resetAt: number } | null;
        const now = Date.now();
        const count = (raw && now <= raw.resetAt) ? raw.count + 1 : 1;
        await env.RATE_LIMIT_KV.put(failKey, JSON.stringify({ count, resetAt: now + CONFIG.IP_RATE_LIMIT_WINDOW_SECONDS * 1000 }), {
          expirationTtl: CONFIG.IP_RATE_LIMIT_BAN_DURATION_SECONDS,
        });
        if (count >= CONFIG.IP_RATE_LIMIT_BAN_THRESHOLD) {
          await env.IP_BLOCK_KV?.put(`ban:${clientIp}`, JSON.stringify({ expiresAt: now + CONFIG.IP_RATE_LIMIT_BAN_DURATION_SECONDS * 1000 }), {
            expirationTtl: Math.ceil(CONFIG.IP_RATE_LIMIT_BAN_DURATION_SECONDS * 1.1),
          });
          return { allowed: false, banned: true, retryAfter: CONFIG.IP_RATE_LIMIT_BAN_DURATION_SECONDS };
        }
      } catch { /* best effort */ }
    }
  }

  return { allowed: result.allowed, banned: false, retryAfter: result.retryAfter };
}

/*
 * Record an IP auth failure (for ban threshold tracking).
 */
export async function recordIpAuthFailure(env: Env, clientIp: string): Promise<void> {
  if (clientIp === 'unknown' || !env.RATE_LIMIT_KV) return;
  const failKey = `rl:ip-fail:${clientIp}`;
  const now = Date.now();
  try {
    const raw = await env.RATE_LIMIT_KV.get(failKey, { type: 'json' }) as { count: number; resetAt: number } | null;
    const count = (raw && now <= raw.resetAt) ? raw.count + 1 : 1;
    await env.RATE_LIMIT_KV.put(failKey, JSON.stringify({ count, resetAt: now + CONFIG.IP_RATE_LIMIT_WINDOW_SECONDS * 1000 }), {
      expirationTtl: CONFIG.IP_RATE_LIMIT_BAN_DURATION_SECONDS,
    });
    if (count >= CONFIG.IP_RATE_LIMIT_BAN_THRESHOLD && env.IP_BLOCK_KV) {
      await env.IP_BLOCK_KV.put(`ban:${clientIp}`, JSON.stringify({ expiresAt: now + CONFIG.IP_RATE_LIMIT_BAN_DURATION_SECONDS * 1000 }), {
        expirationTtl: Math.ceil(CONFIG.IP_RATE_LIMIT_BAN_DURATION_SECONDS * 1.1),
      });
    }
  } catch { /* best effort */ }
}

export type RateLimitResult = {
  allowed: boolean;
  retryAfter?: number;
  dimension?: 'key' | 'agent' | 'endpoint';
};

/*
 * Per-API-key rate limit with per-agent and per-endpoint dimensions.
 */
export async function checkRateLimit(
  env: Env,
  apiKeyId: string,
  agentId?: string,
  method?: string,
  path?: string
): Promise<RateLimitResult> {
  const baseKey = `rl:key:${apiKeyId}`;
  const keyLimit = resolveKeyLimit(env);
  const kv = await kvCheck(env, baseKey, keyLimit);
  const result = kv ?? mapCheck(baseKey, keyLimit);
  if (!result.allowed) return { ...result, dimension: 'key' };

  if (agentId) {
    const agentKey = `rl:key:${apiKeyId}:agent:${agentId}`;
    const kvAgent = await kvCheck(env, agentKey, CONFIG.RATE_LIMIT_PER_KEY_PER_AGENT_PER_MINUTE);
    const agentResult = kvAgent ?? mapCheck(agentKey, CONFIG.RATE_LIMIT_PER_KEY_PER_AGENT_PER_MINUTE);
    if (!agentResult.allowed) return { ...agentResult, dimension: 'agent' };
  }

  if (method && path) {
    const epResult = await checkEndpointLimit(env, method, path, apiKeyId);
    if (!epResult.allowed) return { ...epResult, dimension: 'endpoint' };
  }

  return { allowed: true };
}
