/*
 * Agent listing + chat routes.
 */
import type { Env, ExecutionContext } from '../core/types.js';
import { jsonResponse, errorResponse, corsHeaders, getIdempotencyKey, extractClientIp } from '../utils/response.js';
import { getAgent, AGENT_REGISTRY } from '../core/agents.js';
import { recordAudit } from '../utils/audit.js';
import { bumpApiMetric, bumpPerKey, bumpPerRoute } from '../utils/metrics.js';
import { getCachedResponse, cacheResponse } from '../core/idempotency.js';

export async function handleListAgents(
  request: Request, env: Env, ctx: ExecutionContext,
  apiKeyId: string, scope: string, traceId: string
): Promise<Response> {
  const origin = request.headers.get('origin') || '';
  bumpApiMetric('totalRequests');
  bumpPerKey(apiKeyId);
  bumpPerRoute('agents-list');
  recordAudit({
    timestamp: new Date().toISOString(), traceId,
    clientIp: extractClientIp(request),
    method: 'GET', path: '/api/v1/agents', statusCode: 200,
    userAgent: request.headers.get('user-agent') || 'unknown',
    action: 'LIST_AGENTS', authenticated: true, rateLimited: false, apiKeyId, scope,
  });
  return jsonResponse(200, { agents: Object.values(AGENT_REGISTRY), traceId }, corsHeaders(origin, env));
}

// ---------------------------------------------------------------------------
// handleChat request-pipeline helpers (extracted to module scope so the
// main handler stays under SonarCloud typescript:S3776 cognitive-complexity
// threshold of 15 — the original handler was 23).
// ---------------------------------------------------------------------------

interface ChatContext {
  request: Request;
  env: Env;
  ctx: ExecutionContext;
  apiKeyId: string;
  scope: string;
  agentId: string;
  traceId: string;
  origin: string;
  cors: Record<string, string>;
  idempotencyKey: string | null;
  route: string;
}

/** Parsed chat payload (M4.3: parsed once, then routed). */
interface ChatPayload {
  messages: Array<{ role: string; content: string }>;
  threadId?: string;
  resourceId?: string;
}

/** Build the common audit fields for a chat request. */
function chatAuditFields(rc: ChatContext, statusCode: number, action: string) {
  return {
    timestamp: new Date().toISOString(),
    traceId: rc.traceId,
    clientIp: extractClientIp(rc.request),
    method: 'POST' as const,
    path: `/api/v1/agents/${rc.agentId}/chat`,
    statusCode,
    userAgent: rc.request.headers.get('user-agent') || 'unknown',
    action,
    authenticated: true,
    rateLimited: false,
    apiKeyId: rc.apiKeyId,
    scope: rc.scope,
  };
}

/** Return a 404 Response if the agent doesn't exist, otherwise null. */
function rejectUnknownAgent(rc: ChatContext): Response | null {
  if (getAgent(rc.agentId)) return null;
  recordAudit({
    ...chatAuditFields(rc, 404, 'AGENT_CHAT_AGENT_NOT_FOUND'),
    details: { agentId: rc.agentId },
  });
  return errorResponse(404, `Agent "${rc.agentId}" not found`, rc.traceId, rc.cors);
}

/** Return a cached idempotent response if one exists, otherwise null. */
async function getIdempotentReplay(rc: ChatContext): Promise<Response | null> {
  if (!rc.idempotencyKey) return null;
  const cached = await getCachedResponse(rc.env, rc.apiKeyId, rc.route, rc.idempotencyKey);
  if (!cached) return null;
  bumpApiMetric('idempotentReplays');
  recordAudit({
    ...chatAuditFields(rc, cached.status, 'AGENT_CHAT_IDEMPOTENT_REPLAY'),
    details: { idempotencyKey: rc.idempotencyKey },
  });
  return new Response(cached.body, {
    status: cached.status,
    headers: { 'content-type': cached.contentType, 'X-Idempotent-Replay': 'true', ...rc.cors },
  });
}

/** Try the capability-preserving Mastra proxy. Returns a Response if the
 *  proxy succeeded, null if the proxy was skipped or failed.
 *
 *  M4.3: this is the ONLY downstream execution path for agent chat. There is
 *  no raw-LLM fallback anymore — when the capability-preserving path is
 *  unreachable the caller must fail closed with
 *  SPECIALIZED_EXECUTION_UNAVAILABLE. */
async function tryMastraProxy(rc: ChatContext, payload: ChatPayload): Promise<Response | null> {
  if (!rc.env.MASTRA_API_URL) return null;
  try {
    const proxyRes = await fetch(`${rc.env.MASTRA_API_URL}/api/agents/${rc.agentId}/generate`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...(rc.env.MASTRA_API_KEY ? { 'x-api-key': rc.env.MASTRA_API_KEY } : {}) },
      body: JSON.stringify({
        messages: payload.messages,
        threadId: payload.threadId,
        resourceId: payload.resourceId,
      }),
    });
    if (!proxyRes.ok) return null;
    const proxyJson = (await proxyRes.json()) as Record<string, unknown>;
    const respBody = JSON.stringify({ ...proxyJson, traceId: rc.traceId });
    recordAudit({
      ...chatAuditFields(rc, 200, 'AGENT_CHAT_PROXY'),
      details: { agentId: rc.agentId },
    });
    if (rc.idempotencyKey) {
      rc.ctx.waitUntil(cacheResponse(rc.env, rc.apiKeyId, rc.route, rc.idempotencyKey, 200, respBody, 'application/json; charset=utf-8'));
    }
    return new Response(respBody, {
      status: 200,
      headers: { 'content-type': 'application/json; charset=utf-8', ...rc.cors },
    });
  } catch { /* fall through to fail-closed response */ }
  return null;
}

/** Parse and validate the chat request body. Returns the validated payload,
 *  or a Response if parsing/validation failed. */
async function parseChatBody(rc: ChatContext): Promise<ChatPayload | Response> {
  let parsed: {
    messages?: Array<{ role: string; content: string }>;
    threadId?: string;
    resourceId?: string;
  };
  try {
    parsed = (await rc.request.json()) as typeof parsed;
  } catch {
    return errorResponse(400, 'Invalid JSON body', rc.traceId, rc.cors);
  }
  const messages = parsed.messages || [];
  if (!Array.isArray(messages) || messages.length === 0) {
    return errorResponse(400, 'messages array is required', rc.traceId, rc.cors);
  }
  return { messages, threadId: parsed.threadId, resourceId: parsed.resourceId };
}

/**
 * Fail-closed response for an unreachable capability-preserving execution path
 * (M4.3). Previously this endpoint answered through a raw LLM fallback built
 * on `/chat/completions` without tools or schema — that path is deleted.
 * An unregistered / unreachable capability must NEVER produce an engineering
 * answer; it fails with the unified SPECIALIZED_EXECUTION_UNAVAILABLE error.
 */
function capabilityUnavailableResponse(rc: ChatContext): Response {
  bumpApiMetric('errors');
  recordAudit({
    ...chatAuditFields(rc, 503, 'AGENT_CHAT_SPECIALIZED_UNAVAILABLE'),
    details: { agentId: rc.agentId, code: 'SPECIALIZED_EXECUTION_UNAVAILABLE' },
  });
  return jsonResponse(
    503,
    {
      error: true,
      status: 503,
      code: 'SPECIALIZED_EXECUTION_UNAVAILABLE',
      message:
        `Specialized execution unavailable for agent "${rc.agentId}". ` +
        'The capability-preserving execution path (Mastra agent runtime) is not reachable; ' +
        'no raw LLM answer is produced (fail-closed, M4.3).',
      agentId: rc.agentId,
      traceId: rc.traceId,
      timestamp: new Date().toISOString(),
    },
    rc.cors,
  );
}

// ---------------------------------------------------------------------------
// Main handler — thin orchestration of the helpers above.
// ---------------------------------------------------------------------------

export async function handleChat(
  request: Request, env: Env, ctx: ExecutionContext,
  apiKeyId: string, scope: string, agentId: string, traceId: string
): Promise<Response> {
  const rc: ChatContext = {
    request, env, ctx, apiKeyId, scope, agentId, traceId,
    origin: request.headers.get('origin') || '',
    cors: corsHeaders(request.headers.get('origin') || '', env),
    idempotencyKey: getIdempotencyKey(request),
    route: `POST:/api/v1/agents/${agentId}/chat`,
  };

  const notFoundResponse = rejectUnknownAgent(rc);
  if (notFoundResponse) return notFoundResponse;

  const replayResponse = await getIdempotentReplay(rc);
  if (replayResponse) return replayResponse;

  const payloadOrResponse = await parseChatBody(rc);
  if (payloadOrResponse instanceof Response) return payloadOrResponse;

  // M4.3: the ONLY downstream execution path is the capability-preserving
  // Mastra agent runtime. No raw LLM fallback exists.
  const proxyResponse = await tryMastraProxy(rc, payloadOrResponse);
  if (proxyResponse) return proxyResponse;

  return capabilityUnavailableResponse(rc);
}
