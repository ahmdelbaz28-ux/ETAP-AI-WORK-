/*
 * Scoped API key validation — SECURITY HARDENED.
 *
 * Changes per Better Auth Security Best Practices:
 *   1. Timing-safe comparison (subtle.timingSafeEqual) prevents timing attacks
 *   2. API key minimum length enforcement
 *   3. API key expiration check (createdAt + API_KEY_MAX_AGE_DAYS)
 *   4. KeyId uses SHA-256 hash — never reveals raw key bytes
 *   5. Audit action tags on all auth outcomes
 */
import type { Env } from './types.js';
import type { ApiKeyScope } from './config.js';
import { CONFIG } from './config.js';

interface ApiKeyRecord {
  createdAt: number;
  revoked?: boolean;
  name?: string;
}

interface ApiKeyScopeRecord {
  scope: ApiKeyScope;
  createdAt: number;
  name?: string;
}

export type AuthResult =
  | { valid: true; scope: ApiKeyScope; keyId: string; nearExpiry?: boolean }
  | { valid: false; error: string; auditAction: string };

/*
 * Timing-safe string comparison.
 * Prevents timing side-channel attacks on secret comparison.
 * Uses manual constant-time XOR loop (works in all runtimes including
 * Cloudflare Workers where SubtleCrypto.timingSafeEqual may not be typed).
 */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}

/*
 * Generate a safe key identifier — SHA-256 of a key prefix.
 * Never exposes any part of the raw API key.
 */
async function generateKeyId(apiKey: string): Promise<string> {
  const enc = new TextEncoder();
  const buf = await crypto.subtle.digest('SHA-256', enc.encode(`key-id:${apiKey.slice(0, 16)}`));
  return Array.from(new Uint8Array(buf).slice(0, 8))
    .map((b) => b.toString(16).padStart(2, '0')).join('');
}

function isKeyExpired(createdAt: number): boolean {
  return Date.now() - createdAt > CONFIG.API_KEY_MAX_AGE_DAYS * 24 * 60 * 60 * 1000;
}

function isKeyNearExpiry(createdAt: number): boolean {
  const warnMs = (CONFIG.API_KEY_MAX_AGE_DAYS - CONFIG.API_KEY_EXPIRY_WARNING_DAYS) * 24 * 60 * 60 * 1000;
  return Date.now() - createdAt > warnMs;
}

export async function validateApiKey(env: Env, apiKey: string | null): Promise<AuthResult> {
  if (!apiKey) {
    return { valid: false, error: 'Missing x-api-key header', auditAction: 'AUTH_FAILURE' };
  }

  // Enforce minimum key length (prevents trivial brute-force on short keys)
  if (apiKey.length < CONFIG.API_KEY_MIN_LENGTH) {
    return { valid: false, error: 'Invalid API key', auditAction: 'AUTH_FAILURE' };
  }

  // 1. KV-backed key with optional scope record
  if (env.API_KEYS_KV) {
    try {
      const record = (await env.API_KEYS_KV.get(`api-key:${apiKey}`, { type: 'json' })) as ApiKeyRecord | null;
      if (record) {
        if (record.revoked) {
          return { valid: false, error: 'API key has been revoked', auditAction: 'API_KEY_REVOKED' };
        }
        if (isKeyExpired(record.createdAt)) {
          return { valid: false, error: 'API key has expired', auditAction: 'API_KEY_EXPIRED' };
        }
        const scopeRecord = (await env.API_KEYS_KV.get(`api-key-scope:${apiKey}`, {
          type: 'json',
        })) as ApiKeyScopeRecord | null;
        const keyId = await generateKeyId(apiKey);
        const nearExpiry = isKeyNearExpiry(record.createdAt);
        return { valid: true, scope: scopeRecord?.scope ?? 'full', keyId, nearExpiry };
      }
    } catch {
      // Fall through to legacy secret
    }
  }

  // 2. Legacy single secret — full scope
  const secret = env.API_KEY_SECRET;
  if (!secret) {
    return { valid: false, error: 'API_KEY_SECRET is not configured in environment', auditAction: 'AUTH_FAILURE' };
  }

  // CRITICAL: timing-safe comparison instead of ===
  if (!timingSafeEqual(apiKey, secret)) {
    return { valid: false, error: 'Invalid API key', auditAction: 'AUTH_FAILURE' };
  }

  const keyId = await generateKeyId('legacy-mode');
  return { valid: true, scope: 'full', keyId };
}

export function scopePermitsRoute(scope: ApiKeyScope, routeCategory: RouteCategory): boolean {
  if (scope === 'full') return true;
  switch (routeCategory) {
    case 'health': case 'agents-list': case 'providers-list': return true;
    case 'chat': return scope === 'chat';
    case 'studies': return scope === 'studies';
    case 'audit': case 'metrics': return false;
    default: return false;
  }
}

export type RouteCategory =
  | 'health' | 'agents-list' | 'chat' | 'studies' | 'providers-list' | 'audit' | 'metrics';
