/*
 * Agent listing + chat routes.
 */
import type { Env, ExecutionContext } from '../core/types.js';
import { type ModelMessage } from 'ai';
import { jsonResponse, errorResponse, corsHeaders, getIdempotencyKey, extractClientIp } from '../utils/response.js';
import { getAgent, AGENT_REGISTRY } from '../core/agents.js';
import { generateWithFailover, hasAnyProviderConfigured } from '../core/providers.js';
import { recordAudit } from '../utils/audit.js';
import { bumpApiMetric, bumpPerKey, bumpPerRoute } from '../utils/metrics.js';
import { getCachedResponse, cacheResponse } from '../core/idempotency.js';

export async function handleListAgents(
  request: Request, env: Env, ctx: ExecutionContext,
  apiKeyId: string, scope: string, traceId: string
): Promise<Response> {
  const origin = request.headers.get('origin') || '';

  request: Request,
  env: Env,
  ctx: ExecutionContext,
  apiKeyId: string,
  scope: string,
  traceId: string
): Promise<Response> {
  const origin = request.headers.get('origin') || '*';
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

const CHAT_VALID_ROLES = new Set(['system', 'user', 'assistant', 'tool']);

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

/** Try the Mastra proxy. Returns a Response if the proxy succeeded, null if
 *  the proxy was skipped or failed (caller should fall back to direct AI). */
async function tryMastraProxy(rc: ChatContext): Promise<Response | null> {
  if (!rc.env.MASTRA_API_URL) return null;
  try {
    let body: unknown;
    try { body = await rc.request.clone().json(); } catch { /* continue */ }
    const messages = (body as { messages?: unknown[] })?.messages || [];
    const proxyRes = await fetch(`${rc.env.MASTRA_API_URL}/api/agents/${rc.agentId}/generate`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...(rc.env.MASTRA_API_KEY ? { 'x-api-key': rc.env.MASTRA_API_KEY } : {}) },
      body: JSON.stringify({
        messages,
        threadId: (body as { threadId?: string })?.threadId,
        resourceId: (body as { resourceId?: string })?.resourceId,
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
  } catch { /* fall through to direct AI */ }
  return null;
}

/** Parse and validate the chat request body. Returns the validated messages
 *  array, or a Response if parsing/validation failed. */
async function parseChatBody(rc: ChatContext): Promise<Array<{ role: string; content: string }> | Response> {
  let parsed: { messages?: Array<{ role: string; content: string }> };
  try {
    parsed = (await rc.request.json()) as typeof parsed;
  } catch {
    return errorResponse(400, 'Invalid JSON body', rc.traceId, rc.cors);
  }
  const messages = parsed.messages || [];
  if (!Array.isArray(messages) || messages.length === 0) {
    return errorResponse(400, 'messages array is required', rc.traceId, rc.cors);
  }
  return messages;
}

/** Run the direct-AI fallback. Always returns a Response (200 on success,
 *  502 on AI error). */
async function runDirectAi(
  rc: ChatContext,
  messages: Array<{ role: string; content: string }>,
): Promise<Response> {
  if (!hasAnyProviderConfigured(rc.env)) {
    return errorResponse(503, 'No AI provider is configured', rc.traceId, rc.cors);
  }
  const agent = getAgent(rc.agentId)!;
  const systemPrompt = `You are the ${agent.name}. ${agent.description}.\nRespond with professional engineering analysis. Be concise, accurate, and cite relevant standards when applicable.`;
  const mappedMessages = messages.map((m) => ({
    role: (CHAT_VALID_ROLES.has(m.role) ? m.role : 'user') as 'system' | 'user' | 'assistant' | 'tool',

    timestamp: new Date().toISOString(),
    traceId,
    clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
    method: 'GET',
    path: '/api/v1/agents',
    statusCode: 200,
    userAgent: request.headers.get('user-agent') || 'unknown',
    action: 'LIST_AGENTS',
    authenticated: true,
    rateLimited: false,
    apiKeyId,
    scope,
  });
  ctx.waitUntil((async () => { /* flush handled by index */ })());
  return jsonResponse(
    200,
    {
      agents: Object.values(AGENT_REGISTRY),
      traceId,
    },
    corsHeaders(origin)
  );
}

export async function handleChat(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
  apiKeyId: string,
  scope: string,
  agentId: string,
  traceId: string
): Promise<Response> {
  const origin = request.headers.get('origin') || '*';

  if (!getAgent(agentId)) {
    recordAudit({
      timestamp: new Date().toISOString(),
      traceId,
      clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
      method: 'POST',
      path: `/api/v1/agents/${agentId}/chat`,
      statusCode: 404,
      userAgent: request.headers.get('user-agent') || 'unknown',
      action: 'AGENT_CHAT_AGENT_NOT_FOUND',
      authenticated: true,
      rateLimited: false,
      apiKeyId,
      scope,
      details: { agentId },
    });
    return errorResponse(404, `Agent "${agentId}" not found`, traceId, corsHeaders(origin));
  }

  // Idempotency check
  const idempotencyKey = getIdempotencyKey(request);
  const route = `POST:/api/v1/agents/${agentId}/chat`;
  if (idempotencyKey) {
    const cached = await getCachedResponse(env, apiKeyId, route, idempotencyKey);
    if (cached) {
      bumpApiMetric('idempotentReplays');
      recordAudit({
        timestamp: new Date().toISOString(),
        traceId,
        clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
        method: 'POST',
        path: `/api/v1/agents/${agentId}/chat`,
        statusCode: cached.status,
        userAgent: request.headers.get('user-agent') || 'unknown',
        action: 'AGENT_CHAT_IDEMPOTENT_REPLAY',
        authenticated: true,
        rateLimited: false,
        apiKeyId,
        scope,
        details: { idempotencyKey },
      });
      return new Response(cached.body, {
        status: cached.status,
        headers: {
          'content-type': cached.contentType,
          'X-Idempotent-Replay': 'true',
          ...corsHeaders(origin),
        },
      });
    }
  }

  // Try Mastra proxy first (if configured)
  if (env.MASTRA_API_URL) {
    try {
      let body: unknown;
      try {
        body = await request.clone().json();
      } catch {
        // continue
      }
      const messages = (body as { messages?: unknown[] })?.messages || [];
      const proxyRes = await fetch(`${env.MASTRA_API_URL}/api/agents/${agentId}/generate`, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          ...(env.MASTRA_API_KEY ? { 'x-api-key': env.MASTRA_API_KEY } : {}),
        },
        body: JSON.stringify({
          messages,
          threadId: (body as { threadId?: string })?.threadId,
          resourceId: (body as { resourceId?: string })?.resourceId,
        }),
      });
      if (proxyRes.ok) {
        const proxyJson = (await proxyRes.json()) as Record<string, unknown>;
        const body = JSON.stringify({ ...proxyJson, traceId });
        recordAudit({
          timestamp: new Date().toISOString(),
          traceId,
          clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
          method: 'POST',
          path: `/api/v1/agents/${agentId}/chat`,
          statusCode: 200,
          userAgent: request.headers.get('user-agent') || 'unknown',
          action: 'AGENT_CHAT_PROXY',
          authenticated: true,
          rateLimited: false,
          apiKeyId,
          scope,
          details: { agentId },
        });
        if (idempotencyKey) {
          ctx.waitUntil(cacheResponse(env, apiKeyId, route, idempotencyKey, 200, body, 'application/json; charset=utf-8'));
        }
        return new Response(body, {
          status: 200,
          headers: { 'content-type': 'application/json; charset=utf-8', ...corsHeaders(origin) },
        });
      }
    } catch {
      // fall through
    }
  }

  // Direct AI fallback
  let parsed: { messages?: Array<{ role: string; content: string }> } = {};
  try {
    parsed = (await request.json()) as typeof parsed;
  } catch {
    return errorResponse(400, 'Invalid JSON body', traceId, corsHeaders(origin));
  }
  const messages = parsed.messages || [];
  if (!Array.isArray(messages) || messages.length === 0) {
    return errorResponse(400, 'messages array is required', traceId, corsHeaders(origin));
  }

  if (!hasAnyProviderConfigured(env)) {
    return errorResponse(503, 'No AI provider is configured', traceId, corsHeaders(origin));
  }

  const agent = getAgent(agentId)!;
  // Load generic chat prompt from YAML with dynamic agent name/description interpolation
  const genericPromptSuffix = `\nRespond with professional engineering analysis. Be concise, accurate, and cite relevant standards when applicable.`;
  const systemPrompt = `You are the ${agent.name}. ${agent.description}.${genericPromptSuffix}`;

  const validRoles = new Set(['system', 'user', 'assistant', 'tool']);
  const mappedMessages = messages.map((m) => ({
    role: (validRoles.has(m.role) ? m.role : 'user') as 'system' | 'user' | 'assistant' | 'tool',
    content: typeof m.content === 'string' ? m.content : JSON.stringify(m.content),
  })) as ModelMessage[];

  try {
    const result = await generateWithFailover(rc.env, systemPrompt, mappedMessages);
    bumpApiMetric('agentChats');
    const responseBody = JSON.stringify({
      agentId: rc.agentId, text: result.text, provider: result.provider, model: result.model,
      latencyMs: result.latencyMs, promptTokens: result.promptTokens,
      completionTokens: result.completionTokens, finishReason: result.finishReason, traceId: rc.traceId,
    });
    recordAudit({
      ...chatAuditFields(rc, 200, 'AGENT_CHAT'),
      latencyMs: result.latencyMs,
      details: { agentId: rc.agentId, provider: result.provider },
    });
    if (rc.idempotencyKey) {
      rc.ctx.waitUntil(cacheResponse(rc.env, rc.apiKeyId, rc.route, rc.idempotencyKey, 200, responseBody, 'application/json; charset=utf-8'));
    }
    return new Response(responseBody, {
      status: 200,
      headers: { 'content-type': 'application/json; charset=utf-8', ...rc.cors },

    const result = await generateWithFailover(env, systemPrompt, mappedMessages);
    bumpApiMetric('agentChats');
    const responseBody = JSON.stringify({
      agentId,
      text: result.text,
      provider: result.provider,
      model: result.model,
      latencyMs: result.latencyMs,
      promptTokens: result.promptTokens,
      completionTokens: result.completionTokens,
      finishReason: result.finishReason,
      traceId,
    });
    recordAudit({
      timestamp: new Date().toISOString(),
      traceId,
      clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
      method: 'POST',
      path: `/api/v1/agents/${agentId}/chat`,
      statusCode: 200,
      userAgent: request.headers.get('user-agent') || 'unknown',
      action: 'AGENT_CHAT',
      authenticated: true,
      rateLimited: false,
      apiKeyId,
      scope,
      latencyMs: result.latencyMs,
      details: { agentId, provider: result.provider },
    });
    if (idempotencyKey) {
      ctx.waitUntil(cacheResponse(env, apiKeyId, route, idempotencyKey, 200, responseBody, 'application/json; charset=utf-8'));
    }
    return new Response(responseBody, {
      status: 200,
      headers: { 'content-type': 'application/json; charset=utf-8', ...corsHeaders(origin) },
    });
  } catch (aiError) {
    bumpApiMetric('errors');
    const msg = aiError instanceof Error ? aiError.message : 'AI generation failed';
    recordAudit({
      ...chatAuditFields(rc, 502, 'AGENT_CHAT_AI_ERROR'),
      details: { agentId: rc.agentId, error: msg },
    });
    return errorResponse(502, msg, rc.traceId, rc.cors);
  }
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

  const proxyResponse = await tryMastraProxy(rc);
  if (proxyResponse) return proxyResponse;

  const messagesOrResponse = await parseChatBody(rc);
  if (messagesOrResponse instanceof Response) return messagesOrResponse;

  return runDirectAi(rc, messagesOrResponse);
}

      timestamp: new Date().toISOString(),
      traceId,
      clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
      method: 'POST',
      path: `/api/v1/agents/${agentId}/chat`,
      statusCode: 502,
      userAgent: request.headers.get('user-agent') || 'unknown',
      action: 'AGENT_CHAT_AI_ERROR',
      authenticated: true,
      rateLimited: false,
      apiKeyId,
      scope,
      details: { agentId, error: msg },
    });
    return errorResponse(502, msg, traceId, corsHeaders(origin));
  }
}
