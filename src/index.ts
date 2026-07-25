/*
 * AhmedETAP - Cloudflare Worker (Security Hardened)
 * ===========================================================
 * Security layers applied per Better Auth Security Best Practices:
 *   1. Trusted Origin whitelist (CORS never reflects arbitrary origin)
 *   2. CSRF validation on all state-changing methods
 *   3. Per-IP rate limiting + auto-ban for brute-force defense
 *   4. Timing-safe API key comparison
 *   5. API key expiration enforcement
 *   6. Safe keyId (SHA-256, no raw key bytes exposed)
 *   7. Per-endpoint rate limits (studies tighter than chat)
 *   8. Dedicated audit KV with HMAC integrity
 *   9. 500 errors never leak internal details
 *  10. Cache-Control: no-store on all responses
 *   11. extractClientIp with header chain validation
 *   12. IP ban mechanism (sustained abuse)
 */
import type { Env, ExecutionContext } from './core/types.js';
import { errorResponse, corsHeaders, checkBodySize, validateCsrf, extractClientIp } from './utils/response.js';
import { validateApiKey, scopePermitsRoute, type RouteCategory } from './core/auth.js';
import { checkRateLimit, checkIpRateLimit, recordIpAuthFailure, isIpBanned } from './core/rateLimit.js';
import { recordAudit, flushAuditLog } from './utils/audit.js';
import { bumpApiMetric, loadMetrics, saveMetrics } from './utils/metrics.js';
import { loadCircuitBreakers } from './core/circuitBreaker.js';

import { handleRoot, handleHealth, handleMetrics } from './routes/health.js';
import { handleListAgents, handleChat } from './routes/agents.js';
import { handleStudyRun, handleStudyStatus } from './routes/studies.js';
import { handleListProviders, handleRegisterProvider } from './routes/providers.js';
import { handleAuditLogs } from './routes/audit.js';

let _metricsLoaded = false;
let _circuitsLoaded = false;

export { CONFIG } from './core/config.js';
export type { Env, ExecutionContext };

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const method = request.method.toUpperCase();
    const path = url.pathname;
    const origin = request.headers.get('origin') || '';
    const traceId = crypto.randomUUID();
    const clientIp = extractClientIp(request);
    const cors = corsHeaders(origin, env);

    // 0) IP ban check (before anything else)
    if (await isIpBanned(env, clientIp)) {
      bumpApiMetric('rateLimited');
      recordAudit({
        timestamp: new Date().toISOString(), traceId, clientIp, method, path, statusCode: 429,
        userAgent: request.headers.get('user-agent') || 'unknown',
        action: 'IP_BANNED', authenticated: false, rateLimited: true,
      });
      ctx.waitUntil(Promise.all([flushAuditLog(env), saveMetrics(env)]));
      return errorResponse(429, 'Your IP has been temporarily blocked due to suspicious activity.', traceId, {
        ...cors, 'Retry-After': String(900),
      });
    }

    // 1) CORS preflight — only for trusted origins
    if (method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }

    // 2) Public routes (no auth required)
    if (path === '/' && method === 'GET') return handleRoot(request, env, ctx);
    if (path === '/health' && method === 'GET') {
      if (!_circuitsLoaded) { _circuitsLoaded = true; ctx.waitUntil(loadCircuitBreakers(env)); }
      return handleHealth(request, env, ctx);
    }
    if (path === '/metrics' && method === 'GET') {
      if (!_metricsLoaded) {
        _metricsLoaded = true; ctx.waitUntil(loadMetrics(env));
        if (!_circuitsLoaded) { _circuitsLoaded = true; ctx.waitUntil(loadCircuitBreakers(env)); }
      }
      return handleMetrics(request, env, ctx);
    }

    // 3) Authenticated routes
    if (!path.startsWith('/api/v1')) {
      return errorResponse(404, `Not Found: ${method} ${path}`, traceId, cors);
    }

    // 3a) CSRF validation for state-changing methods
    const csrfErr = validateCsrf(request, method, traceId, env);
    if (csrfErr) {
      bumpApiMetric('authFailures');
      recordAudit({
        timestamp: new Date().toISOString(), traceId, clientIp, method, path, statusCode: 403,
        userAgent: request.headers.get('user-agent') || 'unknown',
        action: 'CSRF_REJECTED', authenticated: false, rateLimited: false,
        details: { origin: request.headers.get('origin'), referer: request.headers.get('referer'), secFetchSite: request.headers.get('sec-fetch-site') },
      });
      ctx.waitUntil(flushAuditLog(env));
      return csrfErr;
    }

    // 3b) Body size guard
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      const sizeErr = await checkBodySize(request);
      if (sizeErr) {
        bumpApiMetric('bodySizeRejections');
        recordAudit({ timestamp: new Date().toISOString(), traceId, clientIp, method, path, statusCode: 413, userAgent: request.headers.get('user-agent') || 'unknown', action: 'BODY_SIZE_REJECTED', authenticated: false, rateLimited: false });
        ctx.waitUntil(flushAuditLog(env));
        return sizeErr;
      }
    }

    // 3c) Authenticate
    const apiKey = request.headers.get('x-api-key');
    const auth = await validateApiKey(env, apiKey);
    if (!auth.valid) {
      bumpApiMetric('authFailures');
      // Track IP auth failure for ban threshold
      ctx.waitUntil(recordIpAuthFailure(env, clientIp));
      // Per-IP rate limit on auth failures
      const ipRl = await checkIpRateLimit(env, clientIp);
      if (!ipRl.allowed) {
        bumpApiMetric('rateLimited');
        recordAudit({ timestamp: new Date().toISOString(), traceId, clientIp, method, path, statusCode: 429, userAgent: request.headers.get('user-agent') || 'unknown', action: ipRl.banned ? 'IP_BANNED' : 'RATE_LIMITED', authenticated: false, rateLimited: true });
        ctx.waitUntil(Promise.all([flushAuditLog(env), saveMetrics(env)]));
        return errorResponse(429, 'Too many authentication attempts. Try again later.', traceId, { ...cors, 'Retry-After': String(ipRl.retryAfter || 60) });
      }
      recordAudit({ timestamp: new Date().toISOString(), traceId, clientIp, method, path, statusCode: 401, userAgent: request.headers.get('user-agent') || 'unknown', action: auth.auditAction, authenticated: false, rateLimited: false });
      ctx.waitUntil(Promise.all([flushAuditLog(env), saveMetrics(env)]));
      return errorResponse(401, auth.error, traceId, cors);
    }

    // 3d) Per-route scope check
    const category = categorize(path, method);
    if (!scopePermitsRoute(auth.scope, category)) {
      recordAudit({ timestamp: new Date().toISOString(), traceId, clientIp, method, path, statusCode: 403, userAgent: request.headers.get('user-agent') || 'unknown', action: 'SCOPE_DENIED', authenticated: true, rateLimited: false, apiKeyId: auth.keyId, scope: auth.scope, details: { category } });
      ctx.waitUntil(Promise.all([flushAuditLog(env), saveMetrics(env)]));
      return errorResponse(403, `API key scope "${auth.scope}" is not permitted for this route`, traceId, cors);
    }

    // 3e) Per-API-key rate limit (plus per-agent for chat, plus per-endpoint)
    const agentIdMatch = path.match(/^\/api\/v1\/agents\/([^/]+)\/chat$/);
    const agentIdForLimit = agentIdMatch ? agentIdMatch[1] : undefined;
    const rl = await checkRateLimit(env, auth.keyId, agentIdForLimit, method, path);
    if (!rl.allowed) {
      bumpApiMetric('rateLimited');
      recordAudit({ timestamp: new Date().toISOString(), traceId, clientIp, method, path, statusCode: 429, userAgent: request.headers.get('user-agent') || 'unknown', action: 'RATE_LIMITED', authenticated: true, rateLimited: true, apiKeyId: auth.keyId, scope: auth.scope, details: rl.dimension ? { dimension: rl.dimension } : undefined });
      ctx.waitUntil(Promise.all([flushAuditLog(env), saveMetrics(env)]));
      return errorResponse(429, 'Rate limit exceeded. Try again later.', traceId, { ...cors, 'Retry-After': String(rl.retryAfter || 60) });
    }

    // 4) Route dispatch
    try {
      if (path === '/api/v1/agents' && method === 'GET') return handleListAgents(request, env, ctx, auth.keyId, auth.scope, traceId);
      if (agentIdMatch && method === 'POST') return handleChat(request, env, ctx, auth.keyId, auth.scope, agentIdMatch[1], traceId);
      if (path === '/api/v1/providers' && method === 'GET') return handleListProviders(request, env, ctx, auth.keyId, auth.scope, traceId);
      if (path === '/api/v1/providers' && method === 'POST') return handleRegisterProvider(request, env, ctx, auth.keyId, auth.scope, traceId);
      if (path === '/api/v1/studies/run' && method === 'POST') return handleStudyRun(request, env, ctx, auth.keyId, auth.scope, traceId);
      const studyStatusMatch = path.match(/^\/api\/v1\/studies\/status\/([^/]+)$/);
      if (studyStatusMatch && method === 'GET') return handleStudyStatus(request, env, ctx, auth.keyId, auth.scope, traceId, studyStatusMatch[1]);
      if (path === '/api/v1/audit/logs' && method === 'GET') return handleAuditLogs(request, env, ctx, auth.keyId, auth.scope, traceId);

      // 404
      recordAudit({ timestamp: new Date().toISOString(), traceId, clientIp, method, path, statusCode: 404, userAgent: request.headers.get('user-agent') || 'unknown', action: 'NOT_FOUND', authenticated: true, rateLimited: false, apiKeyId: auth.keyId, scope: auth.scope });
      ctx.waitUntil(Promise.all([flushAuditLog(env), saveMetrics(env)]));
      return errorResponse(404, `Not Found: ${method} ${path}`, traceId, cors);
    } catch (err) {
      bumpApiMetric('errors');
      const msg = err instanceof Error ? err.message : 'Internal error';
      recordAudit({ timestamp: new Date().toISOString(), traceId, clientIp, method, path, statusCode: 500, userAgent: request.headers.get('user-agent') || 'unknown', action: 'INTERNAL_ERROR', authenticated: true, rateLimited: false, apiKeyId: auth.keyId, scope: auth.scope, details: { error: msg } });
      ctx.waitUntil(Promise.all([flushAuditLog(env), saveMetrics(env)]));
      return errorResponse(500, 'Internal server error', traceId, cors);
    }
  },
};

function categorize(path: string, method: string): RouteCategory {
  if (path === '/health' || path === '/') return 'health';
  if (path === '/metrics') return 'metrics';
  if (path === '/api/v1/agents' && method === 'GET') return 'agents-list';
  if (path === '/api/v1/providers' && method === 'GET') return 'providers-list';
  if (/^\/api\/v1\/agents\/[^/]+\/chat$/.test(path) && method === 'POST') return 'chat';
  if (path.startsWith('/api/v1/studies/')) return 'studies';
  if (path === '/api/v1/audit/logs') return 'audit';
  return 'health';
}
