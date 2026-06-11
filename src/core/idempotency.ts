/**
 * Idempotency-Key support.
 *
 * If a request includes an `Idempotency-Key: <uuid>` header, the
 * server caches the response (status + body) for CONFIG.IDEMPOTENCY_TTL_MS
 * and replays it on duplicate calls with the same key, route, and API key.
 *
 * Storage: RATE_LIMIT_KV (re-used for simplicity, scoped by key prefix).
 */
import type { Env } from './types.js';
import { CONFIG } from './config.js';

interface CachedResponse {
  status: number;
  body: string;
  contentType: string;
  storedAt: number;
}

const _idempotencyInMemory: Map<string, CachedResponse> = new Map();

function makeKey(apiKeyId: string, route: string, idempotencyKey: string): string {
  return `idem:${apiKeyId}:${route}:${idempotencyKey}`;
}

/** Look up a cached response. Returns null if absent. */
export async function getCachedResponse(
  env: Env,
  apiKeyId: string,
  route: string,
  idempotencyKey: string
): Promise<CachedResponse | null> {
  const key = makeKey(apiKeyId, route, idempotencyKey);
  const ttlSeconds = Math.ceil(CONFIG.IDEMPOTENCY_TTL_MS / 1000);

  if (env.RATE_LIMIT_KV) {
    try {
      const raw = (await env.RATE_LIMIT_KV.get(key, { type: 'json' })) as CachedResponse | null;
      if (raw) return raw;
    } catch {
      // Fall through to in-memory
    }
  }

  const mem = _idempotencyInMemory.get(key);
  if (mem && Date.now() - mem.storedAt < CONFIG.IDEMPOTENCY_TTL_MS) {
    return mem;
  }
  _idempotencyInMemory.delete(key);
  return null;
}

/** Persist a response under the idempotency key. */
export async function cacheResponse(
  env: Env,
  apiKeyId: string,
  route: string,
  idempotencyKey: string,
  status: number,
  body: string,
  contentType: string
): Promise<void> {
  const key = makeKey(apiKeyId, route, idempotencyKey);
  const ttlSeconds = Math.ceil(CONFIG.IDEMPOTENCY_TTL_MS / 1000);
  const cached: CachedResponse = { status, body, contentType, storedAt: Date.now() };

  if (env.RATE_LIMIT_KV) {
    try {
      await env.RATE_LIMIT_KV.put(key, JSON.stringify(cached), { expirationTtl: ttlSeconds });
      return;
    } catch {
      // Fall through to in-memory
    }
  }
  _idempotencyInMemory.set(key, cached);
}
