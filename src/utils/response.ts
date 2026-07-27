/*
 * Response helpers: JSON responses, CORS, request size guard.
 *
 * Security hardening:
 *   - CORS uses trusted origin whitelist (NEVER reflects arbitrary origin)
 *   - CSRF validation for state-changing methods (Origin + Fetch Metadata + Referer)
 *   - extractClientIp: validated IP extraction (cf-connecting-ip > x-real-ip > xff)
 *   - 500 error messages never leak internal details
 *   - Cache-Control: no-store on all API responses
 */
import { CONFIG } from '../core/config.js';
import type { Env } from '../core/types.js';

export type Json = Record<string, unknown>;

function resolveTrustedOrigins(env?: Env): Set<string> {
  const origins = new Set<string>(CONFIG.DEFAULT_TRUSTED_ORIGINS);
  if (env?.TRUSTED_ORIGINS) {
    for (const o of env.TRUSTED_ORIGINS.split(',').map((s) => s.trim()).filter(Boolean)) {
      origins.add(o);
    }
  }
  return origins;
}

// SonarCloud typescript:S7780: avoid backslash escapes inside string / template
// literals by using a non-escaped constant for the regex-escape backslash.
// (String.raw could not be used to produce a single trailing backslash.)
const REGEX_ESCAPE_BACKSLASH = String.fromCodePoint(92); // ASCII 92 = '\\'
const REGEX_SPECIAL_CHARS = /[.+?^${}()|[\]\\]/g;

function isOriginTrusted(origin: string, trusted: Set<string>): boolean {
  if (trusted.has(origin)) return true;
  for (const pattern of trusted) {
    if (pattern.includes('*')) {
      // Escape regex special chars (prefix each with a backslash), then turn
      // the glob `*` into the regex `.*` wildcard.
      const escaped = pattern
        .replace(REGEX_SPECIAL_CHARS, (ch) => REGEX_ESCAPE_BACKSLASH + ch)
        .replaceAll('*', '.*');
      const regex = new RegExp('^' + escaped + '$');
      if (regex.test(origin)) return true;
    }
  }
  return false;
}

/*
 * CORS headers with trusted origin whitelist.
 * CRITICAL FIX: previously `origin || '*'` — ANY site could call the API.
 * Now only whitelisted origins get Access-Control-Allow-Origin.
 */
export function corsHeaders(origin: string, env?: Env): Record<string, string> {
  const trusted = resolveTrustedOrigins(env);
  const allowed = origin && origin !== '*' && isOriginTrusted(origin, trusted);
  return {
    'Access-Control-Allow-Origin': allowed ? origin : '',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, x-api-key, Idempotency-Key, X-Request-ID',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}

/*
 * CSRF validation: state-changing requests must have a trusted origin.
 * Checks: Origin header > Sec-Fetch-Site > Referer.
 * Per Better Auth skill: origin validation + Fetch Metadata.
 */
export function validateCsrf(request: Request, method: string, traceId: string, env?: Env): Response | null {
  if (!CONFIG.CSRF_REQUIRED_METHODS.includes(method)) return null;
  if (request.headers.has('x-api-key')) return null;


  const origin = request.headers.get('origin');
  const referer = request.headers.get('referer');
  const secFetchSite = request.headers.get('sec-fetch-site');
  const trusted = resolveTrustedOrigins(env);

  if (origin) {
    if (isOriginTrusted(origin, trusted)) return null;
    return jsonResponse(403, { error: true, status: 403, message: 'CSRF: untrusted origin', traceId, timestamp: new Date().toISOString() }, { 'Vary': 'Origin' });
  }

  if (secFetchSite === 'same-origin' || secFetchSite === 'same-site') return null;

  if (referer) {
    try {
      const refOrigin = new URL(referer).origin;
      if (isOriginTrusted(refOrigin, trusted)) return null;
    } catch { /* invalid URL */ }
  }

  return jsonResponse(403, { error: true, status: 403, message: 'CSRF validation failed', traceId, timestamp: new Date().toISOString() }, { 'Vary': 'Origin' });
}

/*
 * Extract client IP with validation.
 * Per Better Auth skill: ipAddressHeaders + chain depth limit.
 */
export function extractClientIp(request: Request): string {
  const cfIp = request.headers.get('cf-connecting-ip');
  if (cfIp) return cfIp;
  const realIp = request.headers.get('x-real-ip');
  if (realIp) return realIp.trim();
  const xff = request.headers.get('x-forwarded-for');
  if (xff) {
    const ips = xff.split(',').map((s) => s.trim()).filter(Boolean);
    if (ips.length > 0 && ips.length <= CONFIG.MAX_IP_HEADER_CHAIN) return ips[0];
  }
  return 'unknown';
}

export function jsonResponse(status: number, body: Json, extraHeaders?: Record<string, string>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'no-referrer',
      'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
      'Content-Security-Policy': "default-src 'none'; script-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
      'X-Frame-Options': 'DENY',
      'Cache-Control': 'no-store, no-cache, must-revalidate',
      'Pragma': 'no-cache',
      ...extraHeaders,
    },
  });
}

export function errorResponse(status: number, message: string, traceId: string, extraHeaders?: Record<string, string>): Response {
  const safeMessage = status === 500 ? 'Internal server error' : message;
  return jsonResponse(status, { error: true, status, message: safeMessage, traceId, timestamp: new Date().toISOString() }, extraHeaders);
}


export async function checkBodySize(request: Request): Promise<Response | null> {
  const cl = request.headers.get('content-length');
  if (cl) {
    const n = Number.parseInt(cl, 10);
    if (!Number.isNaN(n) && n > CONFIG.MAX_BODY_SIZE) {
      return errorResponse(413, `Request body exceeds maximum size of ${CONFIG.MAX_BODY_SIZE} bytes`, crypto.randomUUID());
    }
  }
  return null;
}

export function getIdempotencyKey(request: Request): string | null {
  return request.headers.get('Idempotency-Key') || request.headers.get('idempotency-key');
}
