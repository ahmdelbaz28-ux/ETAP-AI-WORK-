/**
 * Agent listing + chat routes.
 */
import type { Env, ExecutionContext } from '../core/types.js';
import type { ModelMessage } from 'ai';
import { jsonResponse, errorResponse, corsHeaders, getIdempotencyKey } from '../utils/response.js';
import { getAgent, AGENT_REGISTRY } from '../core/agents.js';
import { generateWithFailover, hasAnyProviderConfigured } from '../core/providers.js';
import { recordAudit } from '../utils/audit.js';
import { bumpApiMetric, bumpPerKey, bumpPerRoute } from '../utils/metrics.js';
import { getCachedResponse, cacheResponse } from '../core/idempotency.js';

export async function handleListAgents(
  request: Request,
  _env: Env,
  ctx: ExecutionContext,
  apiKeyId: string,
  scope: string,
  traceId: string,
): Promise<Response> {
  const origin = request.headers.get('origin') || '*';
  bumpApiMetric('totalRequests');
  bumpPerKey(apiKeyId);
  bumpPerRoute('agents-list');
  recordAudit({
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
  ctx.waitUntil(
    (async () => {
      /* flush handled by index */
    })(),
  );
  return jsonResponse(
    200,
    {
      agents: Object.values(AGENT_REGISTRY),
      traceId,
    },
    corsHeaders(origin),
  );
}

export async function handleChat(
  // NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
  request: Request,
  env: Env,
  ctx: ExecutionContext,
  apiKeyId: string,
  scope: string,
  agentId: string,
  traceId: string,
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
          ctx.waitUntil(
            cacheResponse(
              env,
              apiKeyId,
              route,
              idempotencyKey,
              200,
              body,
              'application/json; charset=utf-8',
            ),
          );
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

  const agent = getAgent(agentId);
  if (!agent) {
    // Defensive: should be unreachable because L66 already checked, but
    // satisfies the type checker without a non-null assertion.
    return errorResponse(404, `Agent '${agentId}' not found`, traceId, corsHeaders(origin));
  }
  // Load generic chat prompt from YAML with dynamic agent name/description interpolation
  const genericPromptSuffix = `\nRespond with professional engineering analysis. Be concise, accurate, and cite relevant standards when applicable.`;
  const systemPrompt = `You are the ${agent.name}. ${agent.description}.${genericPromptSuffix}`;

  const validRoles = new Set(['system', 'user', 'assistant', 'tool']);
  const mappedMessages = messages.map((m) => ({
    role: (validRoles.has(m.role) ? m.role : 'user') as 'system' | 'user' | 'assistant' | 'tool',
    content: typeof m.content === 'string' ? m.content : JSON.stringify(m.content),
  })) as ModelMessage[];

  try {
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
      ctx.waitUntil(
        cacheResponse(
          env,
          apiKeyId,
          route,
          idempotencyKey,
          200,
          responseBody,
          'application/json; charset=utf-8',
        ),
      );
    }
    return new Response(responseBody, {
      status: 200,
      headers: { 'content-type': 'application/json; charset=utf-8', ...corsHeaders(origin) },
    });
  } catch (aiError) {
    bumpApiMetric('errors');
    const msg = aiError instanceof Error ? aiError.message : 'AI generation failed';
    recordAudit({
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
