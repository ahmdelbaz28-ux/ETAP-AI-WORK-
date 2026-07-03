/**
 * Response helpers: JSON responses, CORS, request size guard.
 */
import { CONFIG } from '../core/config.js';

export type Json = Record<string, unknown>;

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
      ...extraHeaders,
    },
  });
}

export function corsHeaders(origin: string): Record<string, string> {
  return {
    'Access-Control-Allow-Origin': origin || '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, x-api-key, Idempotency-Key',
    'Access-Control-Max-Age': '86400',
  };
}

export function errorResponse(status: number, message: string, traceId: string, extraHeaders?: Record<string, string>): Response {
  return jsonResponse(
    status,
    { error: true, status, message, traceId, timestamp: new Date().toISOString() },
    extraHeaders
  );
}

/**
 * Hardening: reject oversized request bodies with HTTP 413.
 * Returns null if the request is acceptable, or a 413 Response otherwise.
 */
export async function checkBodySize(request: Request): Promise<Response | null> {
  const contentLength = request.headers.get('content-length');
  if (contentLength) {
    const n = Number.parseInt(contentLength, 10);
    if (!Number.isNaN(n) && n > CONFIG.MAX_BODY_SIZE) {
      return errorResponse(413, `Request body exceeds maximum size of ${CONFIG.MAX_BODY_SIZE} bytes`, crypto.randomUUID());
    }
  }
  return null;
}

/** Extract the Idempotency-Key header if present. */
export function getIdempotencyKey(request: Request): string | null {
  return request.headers.get('Idempotency-Key') || request.headers.get('idempotency-key');
}
