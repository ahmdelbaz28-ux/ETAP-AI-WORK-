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
import { validateApiKey, scopePermitsRoute, type AuthResult, type RouteCategory } from './core/auth.js';
import { checkRateLimit, checkIpRateLimit, recordIpAuthFailure, isIpBanned } from './core/rateLimit.js';
import { recordAudit, flushAuditLog } from './utils/audit.js';
import { bumpApiMetric, loadMetrics, saveMetrics } from './utils/metrics.js';
import { loadCircuitBreakers } from './core/circuitBreaker.js';

/**
 * AhmedETAP - Cloudflare Worker (Production Hardened)
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

export { CONFIG } from './core/config.js';
export type { Env, ExecutionContext };

// ---------------------------------------------------------------------------
// Request-pipeline helpers (extracted to module scope so the main `fetch`
// handler stays under SonarCloud typescript:S3776 cognitive-complexity
// threshold of 15 — the original handler was 48).
// ---------------------------------------------------------------------------

interface RequestContext {
  request: Request;
  env: Env;
  ctx: ExecutionContext;
  url: URL;
  method: string;
  path: string;
  traceId: string;
  clientIp: string;
  cors: Record<string, string>;
}

/** Common audit fields derived from the request — avoids repeating the same
 *  object literal in every recordAudit() call below. */
function baseAuditFields(rc: RequestContext) {
  return {
    timestamp: new Date().toISOString(),
    traceId: rc.traceId,
    clientIp: rc.clientIp,
    method: rc.method,
    path: rc.path,
    userAgent: rc.request.headers.get('user-agent') || 'unknown',
  };
}

/** Record an audit entry and flush audit log + metrics in the background.
 *  The background Promise is .catch()'d so a rejection inside flushAuditLog
 *  or saveMetrics cannot surface as an unhandled promise rejection (SonarCloud
 *  typescript:S4822). Audit flushing is best-effort by design — a failure
 *  to persist audit/metrics must not break the response path. */
function auditAndFlush(rc: RequestContext, audit: Parameters<typeof recordAudit>[0]): void {
  recordAudit(audit);
  rc.ctx.waitUntil(
    Promise.all([flushAuditLog(rc.env), saveMetrics(rc.env)]).catch(() => {
      // Best-effort flush; suppress rejection to avoid unhandled promise rejection.
    }),
  );
}

/** 0) IP ban check — runs before anything else. Returns a 429 Response if
 *  the IP is banned, otherwise null. */
async function checkIpBan(rc: RequestContext): Promise<Response | null> {
  if (!(await isIpBanned(rc.env, rc.clientIp))) return null;
  bumpApiMetric('rateLimited');
  auditAndFlush(rc, {
    ...baseAuditFields(rc),
    statusCode: 429,
    action: 'IP_BANNED',
    authenticated: false,
    rateLimited: true,
  });
  return errorResponse(429, 'Your IP has been temporarily blocked due to suspicious activity.', rc.traceId, {
    ...rc.cors, 'Retry-After': String(900),
  });
}

/** 2) Public routes (no auth required). Returns a Response if the route is
 *  public, otherwise null. */
async function handlePublicRoute(rc: RequestContext): Promise<Response | null> {
  if (rc.path === '/' && rc.method === 'GET') return handleRoot(rc.request, rc.env, rc.ctx);
  if (rc.path === '/health' && rc.method === 'GET') {
    if (!_circuitsLoaded) {
      _circuitsLoaded = true;
      rc.ctx.waitUntil(loadCircuitBreakers(rc.env));
    }
    return handleHealth(rc.request, rc.env, rc.ctx);
  }
  if (rc.path === '/metrics' && rc.method === 'GET') {
    if (!_metricsLoaded) {
      _metricsLoaded = true;
      rc.ctx.waitUntil(loadMetrics(rc.env));
      if (!_circuitsLoaded) {
        _circuitsLoaded = true;
        rc.ctx.waitUntil(loadCircuitBreakers(rc.env));
      }
    }
    return handleMetrics(rc.request, rc.env, rc.ctx);
  }
  return null;
}

/** 3a) CSRF validation. Returns a 403 Response if CSRF validation fails,
 *  otherwise null. */
function checkCsrf(rc: RequestContext): Response | null {
  const csrfErr = validateCsrf(rc.request, rc.method, rc.traceId, rc.env);
  if (!csrfErr) return null;
  bumpApiMetric('authFailures');
  recordAudit({
    ...baseAuditFields(rc),
    statusCode: 403,
    action: 'CSRF_REJECTED',
    authenticated: false,
    rateLimited: false,
    details: {
      origin: rc.request.headers.get('origin'),
      referer: rc.request.headers.get('referer'),
      secFetchSite: rc.request.headers.get('sec-fetch-site'),
    },
  });
  rc.ctx.waitUntil(flushAuditLog(rc.env));
  return csrfErr;
}

/** 3b) Body-size guard. Returns a 413 Response if the body is too large,
 *  otherwise null. */
async function checkBodySizeGuard(rc: RequestContext): Promise<Response | null> {
  if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(rc.method)) return null;
  const sizeErr = await checkBodySize(rc.request);
  if (!sizeErr) return null;
  bumpApiMetric('bodySizeRejections');
  recordAudit({
    ...baseAuditFields(rc),
    statusCode: 413,
    action: 'BODY_SIZE_REJECTED',
    authenticated: false,
    rateLimited: false,
  });
  rc.ctx.waitUntil(flushAuditLog(rc.env));
  return sizeErr;
}

/** 3c) Authenticate. Returns either a 401/429 Response (on failure) or the
 *  valid AuthResult (on success). */
async function authenticateRequest(
  rc: RequestContext,
): Promise<Response | Extract<AuthResult, { valid: true }>> {
  const apiKey = rc.request.headers.get('x-api-key');
  const auth = await validateApiKey(rc.env, apiKey);
  if (auth.valid) return auth;

  bumpApiMetric('authFailures');
  // Track IP auth failure for ban threshold
  rc.ctx.waitUntil(recordIpAuthFailure(rc.env, rc.clientIp));
  // Per-IP rate limit on auth failures
  const ipRl = await checkIpRateLimit(rc.env, rc.clientIp);
  if (!ipRl.allowed) {
    bumpApiMetric('rateLimited');
    auditAndFlush(rc, {
      ...baseAuditFields(rc),
      statusCode: 429,
      action: ipRl.banned ? 'IP_BANNED' : 'RATE_LIMITED',
      authenticated: false,
      rateLimited: true,
    });
    return errorResponse(429, 'Too many authentication attempts. Try again later.', rc.traceId, {
      ...rc.cors, 'Retry-After': String(ipRl.retryAfter || 60),
    });
  }
  auditAndFlush(rc, {
    ...baseAuditFields(rc),
    statusCode: 401,
    action: auth.auditAction,
    authenticated: false,
    rateLimited: false,
  });
  return errorResponse(401, auth.error, rc.traceId, rc.cors);
}

/** 3d) Per-route scope check. Returns a 403 Response if the API key's scope
 *  is not permitted for the route, otherwise null. */
function checkScope(rc: RequestContext, auth: Extract<AuthResult, { valid: true }>): Response | null {
  const category = categorize(rc.path, rc.method);
  if (scopePermitsRoute(auth.scope, category)) return null;
  auditAndFlush(rc, {
    ...baseAuditFields(rc),
    statusCode: 403,
    action: 'SCOPE_DENIED',
    authenticated: true,
    rateLimited: false,
    apiKeyId: auth.keyId,
    scope: auth.scope,
    details: { category },
  });
  return errorResponse(403, `API key scope "${auth.scope}" is not permitted for this route`, rc.traceId, rc.cors);
}

/** 3e) Per-API-key rate limit. Returns a 429 Response if the limit is
 *  exceeded, otherwise null. Also exposes the agent-id match (used by the
 *  chat route) via the second return value. */
async function checkApiRateLimit(
  rc: RequestContext,
  auth: Extract<AuthResult, { valid: true }>,
): Promise<{ response: Response | null; agentIdMatch: RegExpMatchArray | null }> {
  const agentIdMatch = /^\/api\/v1\/agents\/([^/]+)\/chat$/.exec(rc.path);
  const agentIdForLimit = agentIdMatch ? agentIdMatch[1] : undefined;
  const rl = await checkRateLimit(rc.env, auth.keyId, agentIdForLimit, rc.method, rc.path);
  if (rl.allowed) return { response: null, agentIdMatch };
  bumpApiMetric('rateLimited');
  auditAndFlush(rc, {
    ...baseAuditFields(rc),
    statusCode: 429,
    action: 'RATE_LIMITED',
    authenticated: true,
    rateLimited: true,
    apiKeyId: auth.keyId,
    scope: auth.scope,
    details: rl.dimension ? { dimension: rl.dimension } : undefined,
  });
  return {
    response: errorResponse(429, 'Rate limit exceeded. Try again later.', rc.traceId, {
      ...rc.cors, 'Retry-After': String(rl.retryAfter || 60),
    }),
    agentIdMatch,
  };
}

/** 4) Route dispatch. Returns the route handler's Response, or a 404 if no
 *  route matches. Throws on internal error (caught by the caller). */
async function dispatchRoute(
  rc: RequestContext,
  auth: Extract<AuthResult, { valid: true }>,
  agentIdMatch: RegExpMatchArray | null,
): Promise<Response> {
  const { request, env, ctx, method, path, traceId } = rc;
  if (path === '/api/v1/agents' && method === 'GET') return handleListAgents(request, env, ctx, auth.keyId, auth.scope, traceId);
  if (agentIdMatch && method === 'POST') return handleChat(request, env, ctx, auth.keyId, auth.scope, agentIdMatch[1], traceId);
  if (path === '/api/v1/providers' && method === 'GET') return handleListProviders(request, env, ctx, auth.keyId, auth.scope, traceId);
  if (path === '/api/v1/providers' && method === 'POST') return handleRegisterProvider(request, env, ctx, auth.keyId, auth.scope, traceId);
  if (path === '/api/v1/studies/run' && method === 'POST') return handleStudyRun(request, env, ctx, auth.keyId, auth.scope, traceId);
  const studyStatusMatch = /^\/api\/v1\/studies\/status\/([^/]+)$/.exec(path);
  if (studyStatusMatch && method === 'GET') return handleStudyStatus(request, env, ctx, auth.keyId, auth.scope, traceId, studyStatusMatch[1]);
  if (path === '/api/v1/audit/logs' && method === 'GET') return handleAuditLogs(request, env, ctx, auth.keyId, auth.scope, traceId);

  // 404
  auditAndFlush(rc, {
    ...baseAuditFields(rc),
    statusCode: 404,
    action: 'NOT_FOUND',
    authenticated: true,
    rateLimited: false,
    apiKeyId: auth.keyId,
    scope: auth.scope,
  });
  return errorResponse(404, `Not Found: ${method} ${path}`, traceId, rc.cors);
}

// ---------------------------------------------------------------------------
// Main handler — thin orchestration of the request-pipeline helpers above.
// ---------------------------------------------------------------------------

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const rc: RequestContext = {
      request, env, ctx,
      url: new URL(request.url),
      method: request.method.toUpperCase(),
      path: new URL(request.url).pathname,
      traceId: crypto.randomUUID(),
      clientIp: extractClientIp(request),
      cors: corsHeaders(request.headers.get('origin') || '', env),
    };

    // 0) IP ban check (before anything else)
    const banResponse = await checkIpBan(rc);
    if (banResponse) return banResponse;

    // 1) CORS preflight — only for trusted origins
    if (rc.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: rc.cors });
    }

    // 2) Public routes (no auth required)
    const publicResponse = await handlePublicRoute(rc);
    if (publicResponse) return publicResponse;

    // 3) Authenticated routes
    if (!rc.path.startsWith('/api/v1')) {
      return errorResponse(404, `Not Found: ${rc.method} ${rc.path}`, rc.traceId, rc.cors);
    }

    // 3a) CSRF validation for state-changing methods
    const csrfResponse = checkCsrf(rc);
    if (csrfResponse) return csrfResponse;

    // 3b) Body size guard
    const sizeResponse = await checkBodySizeGuard(rc);
    if (sizeResponse) return sizeResponse;

    // 3c) Authenticate
    const authOrResponse = await authenticateRequest(rc);
    if (authOrResponse instanceof Response) return authOrResponse;
    const auth = authOrResponse;

    // 3d) Per-route scope check
    const scopeResponse = checkScope(rc, auth);
    if (scopeResponse) return scopeResponse;

    // 3e) Per-API-key rate limit
    const { response: rlResponse, agentIdMatch } = await checkApiRateLimit(rc, auth);
    if (rlResponse) return rlResponse;

    // 4) Route dispatch
    try {
      return await dispatchRoute(rc, auth, agentIdMatch);
    } catch (err) {
      bumpApiMetric('errors');
      const msg = err instanceof Error ? err.message : 'Internal error';
      auditAndFlush(rc, {
        ...baseAuditFields(rc),
        statusCode: 500,

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

    // 3a) Body size guard — all methods that can carry a body
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
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
      return errorResponse(500, 'Internal server error', rc.traceId, rc.cors);
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
