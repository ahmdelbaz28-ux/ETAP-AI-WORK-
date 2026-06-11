/**
 * ETAP AI Platform - Cloudflare Worker (Production Hardened)
 * ===========================================================
 * Thin orchestrator. All real logic lives in src/core/ and src/routes/.
 *
 * Hardening summary:
 *   - Body size limit enforced before any work (HTTP 413)
 *   - Per-API-key + per-(key,agent) rate limiting
 *   - Scoped API keys with per-route authorization
 *   - Bounded AI provider failover (max 2 providers, 8s timeout)
 *   - Circuit breaker filters unhealthy providers
 *   - Idempotency-Key support for safe retries
 *   - Dynamic provider registration disabled (410 Gone)
 *   - Security headers on every response
 *   - No silent audit-log drops
 */
import type { Env, ExecutionContext } from './core/types.js';
import { jsonResponse, errorResponse, corsHeaders, checkBodySize } from './utils/response.js';
import { validateApiKey, scopePermitsRoute, type RouteCategory } from './core/auth.js';
import { checkRateLimit } from './core/rateLimit.js';
import { recordAudit, flushAuditLog } from './utils/audit.js';
import { bumpApiMetric, bumpPerKey, loadMetrics, saveMetrics } from './utils/metrics.js';
import { loadCircuitBreakers } from './core/circuitBreaker.js';
import { CONFIG } from './core/config.js';

import { handleRoot, handleHealth, handleMetrics } from './routes/health.js';
import { handleListAgents, handleChat } from './routes/agents.js';
import { handleStudyRun, handleStudyStatus } from './routes/studies.js';
import { handleListProviders, handleRegisterProvider } from './routes/providers.js';
import { handleAuditLogs } from './routes/audit.js';

let _metricsLoaded = false;
let _circuitsLoaded = false;

export { CONFIG };
export type { Env, ExecutionContext };

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const method = request.method.toUpperCase();
    const path = url.pathname;
    const origin = request.headers.get('origin') || '*';
    const traceId = crypto.randomUUID();
    const cors = corsHeaders(origin);

    // 1) CORS preflight
    if (method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }

    // 2) Public routes (no auth, no body size check)
    if (path === '/' && method === 'GET') {
      return handleRoot(request, env, ctx);
    }
    if (path === '/health' && method === 'GET') {
      // Lazily load persisted circuit breaker state (any public route triggers it)
      if (!_circuitsLoaded) {
        _circuitsLoaded = true;
        ctx.waitUntil(loadCircuitBreakers(env));
      }
      return handleHealth(request, env, ctx);
    }
    if (path === '/metrics' && method === 'GET') {
      if (!_metricsLoaded) {
        _metricsLoaded = true;
        ctx.waitUntil(loadMetrics(env));
        if (!_circuitsLoaded) {
          _circuitsLoaded = true;
          ctx.waitUntil(loadCircuitBreakers(env));
        }
      }
      return handleMetrics(request, env, ctx);
    }

    // 3) Authenticated routes — enforce body size first
    if (!path.startsWith('/api/v1')) {
      return errorResponse(404, `Not Found: ${method} ${path}`, traceId, cors);
    }

    // 3a) Body size guard
    if (method === 'POST') {
      const sizeErr = await checkBodySize(request);
      if (sizeErr) {
        bumpApiMetric('bodySizeRejections');
        recordAudit({
          timestamp: new Date().toISOString(),
          traceId,
          clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
          method,
          path,
          statusCode: 413,
          userAgent: request.headers.get('user-agent') || 'unknown',
          action: 'BODY_SIZE_REJECTED',
          authenticated: false,
          rateLimited: false,
        });
        ctx.waitUntil(flushAuditLog(env));
        return sizeErr;
      }
    }

    // 3b) Authenticate
    const apiKey = request.headers.get('x-api-key');
    const auth = await validateApiKey(env, apiKey);
    if (!auth.valid) {
      bumpApiMetric('authFailures');
      recordAudit({
        timestamp: new Date().toISOString(),
        traceId,
        clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
        method,
        path,
        statusCode: 401,
        userAgent: request.headers.get('user-agent') || 'unknown',
        action: 'AUTH_FAILURE',
        authenticated: false,
        rateLimited: false,
      });
      ctx.waitUntil(Promise.all([flushAuditLog(env), saveMetrics(env)]));
      return errorResponse(401, auth.error, traceId, cors);
    }

    // 3c) Per-route scope check
    const category = categorize(path, method);
    if (!scopePermitsRoute(auth.scope, category)) {
      recordAudit({
        timestamp: new Date().toISOString(),
        traceId,
        clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
        method,
        path,
        statusCode: 403,
        userAgent: request.headers.get('user-agent') || 'unknown',
        action: 'SCOPE_DENIED',
        authenticated: true,
        rateLimited: false,
        apiKeyId: auth.keyId,
        scope: auth.scope,
        details: { category },
      });
      ctx.waitUntil(Promise.all([flushAuditLog(env), saveMetrics(env)]));
      return errorResponse(403, `API key scope "${auth.scope}" is not permitted for this route`, traceId, cors);
    }

    // 3d) Per-API-key rate limit (plus per-agent for chat)
    const agentIdMatch = path.match(/^\/api\/v1\/agents\/([^/]+)\/chat$/);
    const agentIdForLimit = agentIdMatch ? agentIdMatch[1] : undefined;
    const rl = await checkRateLimit(env, auth.keyId, agentIdForLimit);
    if (!rl.allowed) {
      bumpApiMetric('rateLimited');
      recordAudit({
        timestamp: new Date().toISOString(),
        traceId,
        clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
        method,
        path,
        statusCode: 429,
        userAgent: request.headers.get('user-agent') || 'unknown',
        action: 'RATE_LIMITED',
        authenticated: true,
        rateLimited: true,
        apiKeyId: auth.keyId,
        scope: auth.scope,
        details: rl.dimension ? { dimension: rl.dimension } : undefined,
      });
      ctx.waitUntil(Promise.all([flushAuditLog(env), saveMetrics(env)]));
      return errorResponse(429, 'Rate limit exceeded. Try again later.', traceId, {
        ...cors,
        'Retry-After': String(rl.retryAfter || 60),
      });
    }

    // 4) Route dispatch
    try {
      // Agents
      if (path === '/api/v1/agents' && method === 'GET') {
        return handleListAgents(request, env, ctx, auth.keyId, auth.scope, traceId);
      }
      if (agentIdMatch && method === 'POST') {
        return handleChat(request, env, ctx, auth.keyId, auth.scope, agentIdMatch[1], traceId);
      }

      // Providers
      if (path === '/api/v1/providers' && method === 'GET') {
        return handleListProviders(request, env, ctx, auth.keyId, auth.scope, traceId);
      }
      if (path === '/api/v1/providers' && method === 'POST') {
        return handleRegisterProvider(request, env, ctx, auth.keyId, auth.scope, traceId);
      }

      // Studies
      if (path === '/api/v1/studies/run' && method === 'POST') {
        return handleStudyRun(request, env, ctx, auth.keyId, auth.scope, traceId);
      }
      const studyStatusMatch = path.match(/^\/api\/v1\/studies\/status\/([^/]+)$/);
      if (studyStatusMatch && method === 'GET') {
        return handleStudyStatus(request, env, ctx, auth.keyId, auth.scope, traceId, studyStatusMatch[1]);
      }

      // Audit
      if (path === '/api/v1/audit/logs' && method === 'GET') {
        return handleAuditLogs(request, env, ctx, auth.keyId, auth.scope, traceId);
      }

      // 404
      recordAudit({
        timestamp: new Date().toISOString(),
        traceId,
        clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
        method,
        path,
        statusCode: 404,
        userAgent: request.headers.get('user-agent') || 'unknown',
        action: 'NOT_FOUND',
        authenticated: true,
        rateLimited: false,
        apiKeyId: auth.keyId,
        scope: auth.scope,
      });
      ctx.waitUntil(Promise.all([flushAuditLog(env), saveMetrics(env)]));
      return errorResponse(404, `Not Found: ${method} ${path}`, traceId, cors);
    } catch (err) {
      bumpApiMetric('errors');
      const msg = err instanceof Error ? err.message : 'Internal error';
      recordAudit({
        timestamp: new Date().toISOString(),
        traceId,
        clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
        method,
        path,
        statusCode: 500,
        userAgent: request.headers.get('user-agent') || 'unknown',
        action: 'INTERNAL_ERROR',
        authenticated: true,
        rateLimited: false,
        apiKeyId: auth.keyId,
        scope: auth.scope,
        details: { error: msg },
      });
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
  if (/^\/api\/v1\/studies\//.test(path)) return 'studies';
  if (path === '/api/v1/audit/logs') return 'audit';
  return 'health';
}
