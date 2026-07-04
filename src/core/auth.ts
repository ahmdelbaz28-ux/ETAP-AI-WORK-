/**
 * Scoped API key validation.
 *
 * Backward-compatible: the legacy single API_KEY_SECRET still works
 * but is treated as having the "full" scope.
 *
 * Per-key scope is stored in KV under `api-key-scope:<key>` as
 * JSON: { scope: ApiKeyScope, createdAt: number }.
 */
import type { Env } from './types.js';
import type { ApiKeyScope } from './config.js';

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
  | { valid: true; scope: ApiKeyScope; keyId: string }
  | { valid: false; error: string };

export async function validateApiKey(env: Env, apiKey: string | null): Promise<AuthResult> {
  if (!apiKey) {
    return { valid: false, error: 'Missing x-api-key header' };
  }

  // 1. KV-backed key with optional scope record
  if (env.API_KEYS_KV) {
    try {
      const record = (await env.API_KEYS_KV.get(`api-key:${apiKey}`, {
        type: 'json',
      })) as ApiKeyRecord | null;
      if (record) {
        if (record.revoked) return { valid: false, error: 'API key has been revoked' };
        // Look up scope
        const scopeRecord = (await env.API_KEYS_KV.get(`api-key-scope:${apiKey}`, {
          type: 'json',
        })) as ApiKeyScopeRecord | null;
        return { valid: true, scope: scopeRecord?.scope ?? 'full', keyId: apiKey.slice(0, 8) };
      }
    } catch {
      // Fall through to legacy secret
    }
  }

  // 2. Legacy single secret — full scope
  const secret = env.API_KEY_SECRET;
  if (!secret) {
    return { valid: false, error: 'API_KEY_SECRET is not configured in environment' };
  }
  if (apiKey !== secret) {
    return { valid: false, error: 'Invalid API key' };
  }
  return { valid: true, scope: 'full', keyId: 'legacy' };
}

/**
 * Check whether a scope permits a given route category.
 */
export function scopePermitsRoute(scope: ApiKeyScope, routeCategory: RouteCategory): boolean {
  // 'full' is a superset
  if (scope === 'full') return true;

  switch (routeCategory) {
    case 'health':
    case 'agents-list':
    case 'providers-list':
      return true; // All scopes can read public listings

    case 'chat':
      return scope === 'chat';

    case 'studies':
      return scope === 'studies';

    case 'audit':
    case 'metrics':
      return false; // Only full

    default:
      return false;
  }
}

export type RouteCategory =
  | 'health'
  | 'agents-list'
  | 'chat'
  | 'studies'
  | 'providers-list'
  | 'audit'
  | 'metrics';
