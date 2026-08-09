/*
 * Idempotency-Key support.
 * Storage: RATE_LIMIT_KV (scoped by 'idem:' prefix), in-memory fallback.
 *
 * Security notes:
 *   - Uses RATE_LIMIT_KV (same namespace, different prefix 'idem:').
 *     This is acceptable because: (a) prefix isolation prevents collisions,
 *     (b) idempotency data is not security-sensitive (it caches responses),
 *     (c) creating a dedicated KV for this would add cost without security benefit.
 *   - Key length is bounded to prevent KV key-length abuse.
 *   - TTL is enforced both in-memory and in KV.
 */

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

const _mem: Map<string, CachedResponse> = new Map();
const _IDEMPOTENCY_KEY_MAX_LENGTH = 256;
const _MEM_MAP_MAX = 5000;

function makeKey(apiKeyId: string, route: string, idempotencyKey: string): string {
  return `idem:${apiKeyId}:${route}:${idempotencyKey}`;
}

function validateIdempotencyKey(key: string): boolean {
  if (key.length === 0 || key.length > _IDEMPOTENCY_KEY_MAX_LENGTH) return false;
  // Only allow printable ASCII + common UUID format chars
  return /^[a-zA-Z0-9_\-./:]+$/.test(key);
}

export async function getCachedResponse(
  env: Env, apiKeyId: string, route: string, idempotencyKey: string
): Promise<CachedResponse | null> {
  if (!validateIdempotencyKey(idempotencyKey)) return null;

  const key = makeKey(apiKeyId, route, idempotencyKey);
  if (env.RATE_LIMIT_KV) {
    try {
      const raw = (await env.RATE_LIMIT_KV.get(key, { type: 'json' })) as CachedResponse | null;
      if (raw && typeof raw === 'object' && 'status' in raw && 'body' in raw) return raw;
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
  if (!validateIdempotencyKey(idempotencyKey)) return;

  const key = makeKey(apiKeyId, route, idempotencyKey);
  const ttl = Math.ceil(CONFIG.IDEMPOTENCY_TTL_MS / 1000);
  const cached: CachedResponse = { status, body, contentType, storedAt: Date.now() };
  if (env.RATE_LIMIT_KV) {
    try {
      await env.RATE_LIMIT_KV.put(key, JSON.stringify(cached), { expirationTtl: ttl });
      return;
    } catch { /* fall through */ }
  }
  // Bound in-memory map size
  if (_mem.size >= _MEM_MAP_MAX) {
    const oldest = [..._mem.entries()].sort((a, b) => a[1].storedAt - b[1].storedAt);
    for (const [k] of oldest.slice(0, Math.floor(_MEM_MAP_MAX * 0.25))) _mem.delete(k);
  }
  _mem.set(key, cached);
}
