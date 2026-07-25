/*
 * Idempotency-Key support.
 * Storage: RATE_LIMIT_KV (scoped by 'idem:' prefix), in-memory fallback.
 */
import type { Env } from './types.js';
import { CONFIG } from './config.js';

interface CachedResponse {
  status: number;
  body: string;
  contentType: string;
  storedAt: number;
}

const _mem: Map<string, CachedResponse> = new Map();

function makeKey(apiKeyId: string, route: string, idempotencyKey: string): string {
  return `idem:${apiKeyId}:${route}:${idempotencyKey}`;
}

export async function getCachedResponse(
  env: Env, apiKeyId: string, route: string, idempotencyKey: string
): Promise<CachedResponse | null> {
  const key = makeKey(apiKeyId, route, idempotencyKey);
  if (env.RATE_LIMIT_KV) {
    try {
      const raw = (await env.RATE_LIMIT_KV.get(key, { type: 'json' })) as CachedResponse | null;
      if (raw) return raw;
    } catch { /* fall through */ }
  }
  const mem = _mem.get(key);
  if (mem && Date.now() - mem.storedAt < CONFIG.IDEMPOTENCY_TTL_MS) return mem;
  _mem.delete(key);
  return null;
}

export async function cacheResponse(
  env: Env, apiKeyId: string, route: string, idempotencyKey: string,
  status: number, body: string, contentType: string
): Promise<void> {
  const key = makeKey(apiKeyId, route, idempotencyKey);
  const ttl = Math.ceil(CONFIG.IDEMPOTENCY_TTL_MS / 1000);
  const cached: CachedResponse = { status, body, contentType, storedAt: Date.now() };
  if (env.RATE_LIMIT_KV) {
    try {
      await env.RATE_LIMIT_KV.put(key, JSON.stringify(cached), { expirationTtl: ttl });
      return;
    } catch { /* fall through */ }
  }
  _mem.set(key, cached);
}
