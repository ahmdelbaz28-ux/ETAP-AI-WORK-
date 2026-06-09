/**
 * ETAP AI Platform - Cloudflare Worker API Gateway
 * ==================================================
 * Production-ready entry point for the power system engineering platform.
 *
 * Endpoints:
 *   GET  /health                          - Service health check
 *   GET  /api/v1/agents                   - List available Mastra agents
 *   POST /api/v1/agents/:agentId/chat     - Chat with a specific agent
 *   POST /api/v1/studies/run              - Run a power system study
 *   GET  /api/v1/providers                - List configured AI providers
 *
 * Security:
 *   - CORS preflight handling
 *   - API key authentication (x-api-key header)
 *   - Rate limiting via Cloudflare Cache API
 *   - Structured error responses with trace IDs
 */

import { createOpenAI } from "@ai-sdk/openai";
import { generateText } from "ai";

// ---------------------------------------------------------------------------
// Cloudflare Workers globals
// ---------------------------------------------------------------------------
declare const caches: { default: { match(request: Request): Promise<Response | undefined>; put(request: Request, response: Response): Promise<void> } } | undefined;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isRateLimitEntry(value: unknown): value is { count: number; resetAt: number } {
  return (
    typeof value === 'object' &&
    value !== null &&
    'count' in value &&
    'resetAt' in value &&
    typeof (value as Record<string, unknown>).count === 'number' &&
    typeof (value as Record<string, unknown>).resetAt === 'number'
  );
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Json = Record<string, unknown>;

// Minimal KVNamespace interface for when @cloudflare/workers-types is not installed.
// Renamed to avoid collisions with the global KVNamespace from @cloudflare/workers-types.
interface MinimalKVNamespace {
  get(key: string, options?: { type?: 'text' | 'json' | 'arrayBuffer' | 'stream' }): Promise<unknown | null>;
  put(key: string, value: string | ArrayBuffer | ReadableStream, options?: { expirationTtl?: number; expiration?: number }): Promise<void>;
  delete(key: string): Promise<void>;
}

export interface Env {
  MASTRA_API_URL?: string;
  MASTRA_API_KEY?: string;
  OPENAI_API_KEY?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_MODEL?: string;
  RATE_LIMIT_REQUESTS_PER_MINUTE?: string;
  API_KEY_SECRET?: string;
  RATE_LIMIT_KV?: MinimalKVNamespace;
}

// Minimal ExecutionContext for Cloudflare Workers compatibility
// If @cloudflare/workers-types is installed, this merges with the official type.
export interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

// ---------------------------------------------------------------------------
// Response helpers
// ---------------------------------------------------------------------------

const jsonResponse = (status: number, body: Json, extraHeaders?: Record<string, string>): Response => {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      ...extraHeaders,
    },
  });
};

const corsHeaders = (origin: string): Record<string, string> => ({
  "Access-Control-Allow-Origin": origin || "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, x-api-key",
  "Access-Control-Max-Age": "86400",
});

const errorResponse = (status: number, message: string, traceId: string, extraHeaders?: Record<string, string>): Response => {
  return jsonResponse(
    status,
    {
      error: true,
      status,
      message,
      traceId,
      timestamp: new Date().toISOString(),
    },
    extraHeaders
  );
};

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

function authenticate(request: Request, env: Env): { authenticated: boolean; error?: string } {
  const apiKey = request.headers.get("x-api-key");
  const secret = env.API_KEY_SECRET;

  if (!secret) {
    return { authenticated: false, error: "API_KEY_SECRET is not configured in environment" };
  }

  if (!apiKey) {
    return { authenticated: false, error: "Missing x-api-key header" };
  }

  if (apiKey !== secret) {
    return { authenticated: false, error: "Invalid API key" };
  }

  return { authenticated: true };
}

// ---------------------------------------------------------------------------
// Rate limiting (KV-first with Cache API and in-memory Map fallbacks)
// ---------------------------------------------------------------------------

const _rateLimitMap = new Map<string, { count: number; resetAt: number }>();

interface RateLimitState {
  count: number;
  resetAt: number;
}

function parseRateLimitEnv(request: Request, env: Env): { limit: number; windowMs: number; clientIp: string; key: string; now: number; ttlSeconds: number } {
  const limit = parseInt(env.RATE_LIMIT_REQUESTS_PER_MINUTE || "60", 10);
  const windowMs = 60_000;
  const clientIp = request.headers.get("cf-connecting-ip") || "unknown";
  const key = `rate-limit:${clientIp}`;
  const now = Date.now();
  const ttlSeconds = Math.ceil(windowMs / 1000);
  return { limit, windowMs, clientIp, key, now, ttlSeconds };
}

function evaluateLimit(state: RateLimitState | null, now: number, limit: number): { allowed: boolean; retryAfter?: number; newState?: RateLimitState } {
  if (!state || now > state.resetAt) {
    return { allowed: true, newState: { count: 1, resetAt: now + 60_000 } };
  }
  if (state.count >= limit) {
    return { allowed: false, retryAfter: Math.ceil((state.resetAt - now) / 1000) };
  }
  return { allowed: true, newState: { count: state.count + 1, resetAt: state.resetAt } };
}

async function checkRateLimitKV(env: Env, ctx: ReturnType<typeof parseRateLimitEnv>): Promise<{ allowed: boolean; retryAfter?: number } | null> {
  if (!env.RATE_LIMIT_KV) return null;
  const { limit, key, now, ttlSeconds } = ctx;
  try {
    const raw = await env.RATE_LIMIT_KV.get(key, { type: 'json' });
    const stored = isRateLimitEntry(raw) ? raw : null;
    const result = evaluateLimit(stored, now, limit);
    if (result.newState) {
      await env.RATE_LIMIT_KV.put(key, JSON.stringify(result.newState), { expirationTtl: ttlSeconds });
    }
    return { allowed: result.allowed, retryAfter: result.retryAfter };
  } catch {
    return null;
  }
}

async function checkRateLimitCache(request: Request, env: Env, ctx: ReturnType<typeof parseRateLimitEnv>): Promise<{ allowed: boolean; retryAfter?: number } | null> {
  if (typeof caches === "undefined" || !caches.default) return null;
  const { limit, key, now, ttlSeconds } = ctx;
  try {
    const cache = caches.default;
    const cacheKey = new Request(`https://rate-limit.internal/${key}`);
    const cached = await cache.match(cacheKey);
    let state: RateLimitState | null = null;
    if (cached) {
      const data = JSON.parse(await cached.text());
      if (isRateLimitEntry(data)) state = data;
    }
    const result = evaluateLimit(state, now, limit);
    if (result.newState) {
      await cache.put(cacheKey, new Response(JSON.stringify(result.newState), {
        headers: {
          "content-type": "application/json",
          "Cache-Control": `max-age=${ttlSeconds}`,
        },
      }));
    }
    return { allowed: result.allowed, retryAfter: result.retryAfter };
  } catch {
    return null;
  }
}

function checkRateLimitMap(env: Env, ctx: ReturnType<typeof parseRateLimitEnv>): { allowed: boolean; retryAfter?: number } {
  const { limit, key, now } = ctx;
  const state = _rateLimitMap.get(key) ?? null;
  const result = evaluateLimit(state, now, limit);
  if (result.newState) {
    _rateLimitMap.set(key, result.newState);
  }
  return { allowed: result.allowed, retryAfter: result.retryAfter };
}

// Uses Cloudflare KV when available (production), otherwise falls back to
// Cache API, then to an in-memory Map for local dev/test environments.
// NOTE: KV lacks atomic operations, so concurrent requests from the same IP
// may briefly exceed the limit. For strict atomic rate limiting, use a Durable Object.
async function checkRateLimit(request: Request, env: Env): Promise<{ allowed: boolean; retryAfter?: number }> {
  const ctx = parseRateLimitEnv(request, env);
  const kvResult = await checkRateLimitKV(env, ctx);
  if (kvResult !== null) return kvResult;

  const cacheResult = await checkRateLimitCache(request, env, ctx);
  if (cacheResult !== null) return cacheResult;

  return checkRateLimitMap(env, ctx);
}

// ---------------------------------------------------------------------------
// AI Provider
// ---------------------------------------------------------------------------

function getAIProvider(env: Env) {
  const apiKey = env.OPENAI_API_KEY;
  const baseURL = env.OPENAI_BASE_URL;
  const modelId = env.OPENAI_MODEL || "gpt-4o-mini";

  if (!apiKey) {
    return null;
  }

  const openai = createOpenAI({
    apiKey,
    baseURL,
  });

  return { openai, modelId };
}

// ---------------------------------------------------------------------------
// Agent registry (mirrors src/mastra agents)
// ---------------------------------------------------------------------------

// In-memory task store for study execution tracking (production: use Redis/KV)
const MAX_TASK_STORE_SIZE = 1000;
const _taskStore = new Map<string, { studyType: string; parameters: unknown; status: string; createdAt: number; startedAt?: number; completedAt?: number; result?: unknown }>();

function _evictStaleTasks(): void {
  if (_taskStore.size <= MAX_TASK_STORE_SIZE) return;
  const cutoff = Date.now() - 3600_000; // 1 hour TTL
  for (const [key, task] of _taskStore) {
    if (task.createdAt < cutoff) _taskStore.delete(key);
  }
  // If still over limit, remove oldest entries
  if (_taskStore.size > MAX_TASK_STORE_SIZE) {
    const entries = [..._taskStore.entries()].sort((a, b) => a[1].createdAt - b[1].createdAt);
    const toRemove = entries.slice(0, entries.length - MAX_TASK_STORE_SIZE);
    for (const [key] of toRemove) _taskStore.delete(key);
  }
}

const AGENT_REGISTRY: Record<string, { name: string; description: string; capabilities: string[] }> = {
  "power-system-coordinator-agent": {
    name: "Power System Coordinator Agent",
    description: "Orchestrates multi-study power system engineering workflows.",
    capabilities: ["load_flow", "short_circuit", "protection", "harmonics", "arc_flash", "motor_starting"],
  },
  "load-flow-agent": {
    name: "Load Flow Analysis Agent",
    description: "Performs AC load flow analysis using Newton-Raphson.",
    capabilities: ["load_flow", "voltage_profile", "power_balance"],
  },
  "short-circuit-agent": {
    name: "Short Circuit Analysis Agent",
    description: "Calculates fault currents per IEC 60909.",
    capabilities: ["short_circuit", "fault_analysis", "iec_60909"],
  },
  "arcflash-agent": {
    name: "Arc Flash Analysis Agent",
    description: "Computes incident energy per IEEE 1584-2018.",
    capabilities: ["arc_flash", "incident_energy", "ppe_level"],
  },
  "etap-engineer-agent": {
    name: "ETAP Engineering Agent",
    description: "Interfaces with ETAP for project automation.",
    capabilities: ["etap_automation", "project_management", "study_execution"],
  },
  "protection-agent": {
    name: "Protection Coordination Agent",
    description: "Validates relay coordination per IEC 60255.",
    capabilities: ["protection_coordination", "relay_settings", "tcc_curves"],
  },
  "motorstarting-agent": {
    name: "Motor Starting Agent",
    description: "Analyzes motor starting voltage dip and acceleration.",
    capabilities: ["motor_starting", "voltage_dip", "acceleration_time"],
  },
  "goal-planner-agent": {
    name: "Goal Planner Agent",
    description: "Breaks down engineering goals into actionable tasks.",
    capabilities: ["task_planning", "priority_estimation", "workflow_design"],
  },
  "weather-agent": {
    name: "Weather Agent",
    description: "Retrieves weather data for engineering planning.",
    capabilities: ["weather_forecast", "temperature", "wind_speed"],
  },
};

// ---------------------------------------------------------------------------
// Worker
// ---------------------------------------------------------------------------

export default {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  async fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const method = request.method.toUpperCase();
    const path = url.pathname;
    const origin = request.headers.get("origin") || "*";
    const traceId = crypto.randomUUID();
    const cors = corsHeaders(origin);

    // Handle CORS preflight
    if (method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    // Health check (no auth required)
    if (path === "/health" && method === "GET") {
      return jsonResponse(
        200,
        {
          ok: true,
          service: "etap-ai-platform",
          version: "1.0.0",
          traceId,
          timestamp: new Date().toISOString(),
        },
        cors
      );
    }

    // Root endpoint
    if (path === "/" && method === "GET") {
      return jsonResponse(
        200,
        {
          service: "ETAP AI Platform",
          version: "1.0.0",
          documentation: "/api/v1/docs",
          health: "/health",
          traceId,
        },
        cors
      );
    }

    // Rate limit check
    const rateLimit = await checkRateLimit(request, env);
    if (!rateLimit.allowed) {
      return errorResponse(
        429,
        "Rate limit exceeded. Too many requests.",
        traceId,
        {
          ...cors,
          "Retry-After": String(rateLimit.retryAfter || 60),
        }
      );
    }

    // Authenticate all /api/v1 routes
    if (path.startsWith("/api/v1")) {
      const auth = authenticate(request, env);
      if (!auth.authenticated) {
        return errorResponse(401, auth.error || "Unauthorized", traceId, cors);
      }
    }

    // -----------------------------------------------------------------------
    // API v1 Routes
    // -----------------------------------------------------------------------

    // List agents
    if (path === "/api/v1/agents" && method === "GET") {
      return jsonResponse(
        200,
        {
          agents: Object.entries(AGENT_REGISTRY).map(([id, meta]) => ({
            id,
            ...meta,
          })),
          traceId,
        },
        cors
      );
    }

    // Chat with an agent
    const agentChatMatch = path.match(/^\/api\/v1\/agents\/([^/]+)\/chat$/);
    if (agentChatMatch && method === "POST") {
      const agentId = agentChatMatch[1];
      if (!AGENT_REGISTRY[agentId]) {
        return errorResponse(404, `Agent "${agentId}" not found`, traceId, cors);
      }

      let body: any = {};
      try {
        body = await request.json();
      } catch {
        return errorResponse(400, "Invalid JSON body", traceId, cors);
      }

      const messages = body.messages || [];
      if (!Array.isArray(messages) || messages.length === 0) {
        return errorResponse(400, "messages array is required", traceId, cors);
      }

      // Try to proxy to Mastra backend if configured
      if (env.MASTRA_API_URL) {
        try {
          const proxyRes = await fetch(`${env.MASTRA_API_URL}/api/agents/${agentId}/generate`, {
            method: "POST",
            headers: {
              "content-type": "application/json",
              ...(env.MASTRA_API_KEY ? { "x-api-key": env.MASTRA_API_KEY } : {}),
            },
            body: JSON.stringify({ messages, threadId: body.threadId, resourceId: body.resourceId }),
          });
          if (proxyRes.ok) {
            const proxyJson = (await proxyRes.json()) as Record<string, unknown>;
            return jsonResponse(200, { ...proxyJson, traceId }, cors);
          }
        } catch {
          // Fall through to direct AI generation
        }
      }

      // Fallback: direct AI generation via configured provider
      const provider = getAIProvider(env);
      if (!provider) {
        return errorResponse(
          503,
          "No AI provider configured. Set OPENAI_API_KEY or MASTRA_API_URL.",
          traceId,
          cors
        );
      }

      try {
        const systemPrompt = `You are the ${AGENT_REGISTRY[agentId].name}. ${AGENT_REGISTRY[agentId].description}.
Respond with professional engineering analysis. Be concise, accurate, and cite relevant standards when applicable.`;

        const validRoles = new Set(["system", "user", "assistant", "tool", "function"]);
        const mappedMessages = messages.map((m: any) => {
          const rawRole = m.role;
          const role = validRoles.has(rawRole) ? rawRole : "user";
          const content = typeof m.content === "string" ? m.content : JSON.stringify(m.content);
          return { role, content };
        });

        const result = await generateText({
          model: provider.openai(provider.modelId),
          system: systemPrompt,
          messages: mappedMessages,
        });

        return jsonResponse(
          200,
          {
            agentId,
            text: result.text,
            provider: provider.modelId,
            traceId,
            finishReason: result.finishReason,
          } as Record<string, unknown>,
          cors
        );
      } catch (aiError) {
        const msg = aiError instanceof Error ? aiError.message : "AI generation failed";
        return errorResponse(502, msg, traceId, cors);
      }
    }

    // Run a study
    if (path === "/api/v1/studies/run" && method === "POST") {
      let body: any = {};
      try {
        body = await request.json();
      } catch {
        return errorResponse(400, "Invalid JSON body", traceId, cors);
      }

      const studyType = body.studyType;
      const parameters = body.parameters || {};

      if (!studyType) {
        return errorResponse(400, "studyType is required", traceId, cors);
      }

      const validStudyTypes = [
        "load_flow",
        "short_circuit",
        "arc_flash",
        "harmonic_analysis",
        "optimal_power_flow",
        "protection_coordination",
        "motor_starting",
      ];

      if (!validStudyTypes.includes(studyType)) {
        return errorResponse(
          400,
          `Invalid studyType. Must be one of: ${validStudyTypes.join(", ")}`,
          traceId,
          cors
        );
      }

      // Store task and attempt proxy to Mastra backend for execution
      _evictStaleTasks();
      const taskId = traceId;
      _taskStore.set(taskId, {
        studyType,
        parameters,
        status: "queued",
        createdAt: Date.now(),
      });

      // Try to proxy study execution to Mastra backend
      let executionStatus = "queued";
      let executionMessage = "Study queued for execution. Use GET /api/v1/studies/status/:taskId to poll for results.";

      if (env.MASTRA_API_URL) {
        try {
          const proxyRes = await fetch(`${env.MASTRA_API_URL}/api/studies/run`, {
            method: "POST",
            headers: {
              "content-type": "application/json",
              ...(env.MASTRA_API_KEY ? { "x-api-key": env.MASTRA_API_KEY } : {}),
            },
            body: JSON.stringify({ studyType, parameters, taskId }),
            signal: AbortSignal.timeout(10000),
          });
          if (proxyRes.ok) {
            executionStatus = "submitted";
            const task = _taskStore.get(taskId);
            if (task) {
              task.status = "submitted";
              task.startedAt = Date.now();
            }
            executionMessage = "Study submitted to execution backend. Use GET /api/v1/studies/status/:taskId to poll for results.";
          }
        } catch {
          // Backend unavailable — task remains queued for retry
        }
      }

      // Try direct AI-powered analysis as fallback
      if (executionStatus === "queued" && env.OPENAI_API_KEY) {
        const provider = getAIProvider(env);
        if (provider) {
          try {
            const studyPrompt = `You are a power systems engineer. Perform a ${studyType.replace(/_/g, " ")} analysis with these parameters: ${JSON.stringify(parameters)}. Provide detailed engineering results including numerical values, compliance status, and recommendations. Cite relevant standards (IEEE/IEC).`;

            const result = await generateText({
              model: provider.openai(provider.modelId),
              system: `You are an expert power systems analysis engine. Provide precise, standards-compliant engineering analysis results.`,
              messages: [{ role: "user", content: studyPrompt }],
            });

            const task = _taskStore.get(taskId);
            if (task) {
              task.status = "completed";
              task.startedAt = task.startedAt || Date.now();
              task.completedAt = Date.now();
              task.result = { text: result.text, model: provider.modelId };
            }
            executionStatus = "completed";
            executionMessage = "Study completed via AI analysis.";
          } catch {
            const task = _taskStore.get(taskId);
            if (task) task.status = "failed";
            executionStatus = "failed";
            executionMessage = "AI analysis failed. Verify parameters and try again.";
          }
        }
      }

      return jsonResponse(
        200,
        {
          studyType,
          status: executionStatus,
          message: executionMessage,
          taskId,
          parameters,
          statusUrl: `/api/v1/studies/status/${taskId}`,
          traceId,
        },
        cors
      );
    }

    // Get study status
    const studyStatusMatch = path.match(/^\/api\/v1\/studies\/status\/([^/]+)$/);
    if (studyStatusMatch && method === "GET") {
      const taskId = studyStatusMatch[1];
      const task = _taskStore.get(taskId);
      if (!task) {
        return errorResponse(404, `Task "${taskId}" not found`, traceId, cors);
      }
      return jsonResponse(200, {
        studyType: task!.studyType,
        parameters: task!.parameters,
        status: task!.status,
        createdAt: task!.createdAt,
        startedAt: task!.startedAt,
        completedAt: task!.completedAt,
        result: task!.result,
        taskId,
        traceId,
      }, cors);
    }

    // List providers
    if (path === "/api/v1/providers" && method === "GET") {
      const provider = getAIProvider(env);
      return jsonResponse(
        200,
        {
          providers: [
            {
              id: "openai",
              name: "OpenAI",
              model: provider?.modelId || env.OPENAI_MODEL || "gpt-4o-mini",
              configured: !!provider,
            },
            {
              id: "mastra",
              name: "Mastra Backend",
              configured: !!env.MASTRA_API_URL,
            },
          ],
          traceId,
        },
        cors
      );
    }

    // 404
    return errorResponse(404, `Not Found: ${method} ${path}`, traceId, cors);
  },
};
