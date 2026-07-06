/**
 * AI provider management with bounded failover.
 *
 * Hardening changes:
 *   - Only built-in providers listed in CONFIG (NVIDIA, OpenAI)
 *   - Dynamic provider registration is disabled
 *   - Hard 8s timeout via AbortController on every fetch
 *   - Max 2 providers attempted per request (no long cascade chains)
 *   - Circuit breaker filters out open providers at runtime
 *   - MAX_RETRIES=1 (was 2)
 */
import { type ModelMessage } from 'ai';
import type { Env } from './types.js';
import { CONFIG, BUILTIN_BASE_URLS, BUILTIN_MODELS, BUILTIN_PROVIDERS } from './config.js';
import { isCircuitOpen, recordProviderFailure, recordProviderSuccess } from './circuitBreaker.js';

export interface ProviderConfig {
  name: string;
  apiKey: string;
  baseURL: string;
  model: string;
}

export interface ChatResult {
  text: string;
  finishReason: string;
  provider: string;
  model: string;
  latencyMs: number;
  promptTokens?: number;
  completionTokens?: number;
}

interface ProviderLatencyBucket {
  count: number;
  totalMs: number;
  failures: number;
}

const _providerLatency: Map<string, ProviderLatencyBucket> = new Map();

function recordLatency(name: string, ms: number, failed: boolean): void {
  let b = _providerLatency.get(name);
  if (!b) {
    b = { count: 0, totalMs: 0, failures: 0 };
    _providerLatency.set(name, b);
  }
  b.count++;
  b.totalMs += ms;
  if (failed) b.failures++;
}

export function getProviderLatency(): Record<string, { avgMs: number; failureRate: number; count: number }> {
  const out: Record<string, { avgMs: number; failureRate: number; count: number }> = {};
  for (const [name, b] of _providerLatency.entries()) {
    out[name] = {
      avgMs: b.count > 0 ? Math.round(b.totalMs / b.count) : 0,
      failureRate: b.count > 0 ? b.failures / b.count : 0,
      count: b.count,
    };
  }
  return out;
}

function _getProviderConfig(env: Env, name: string): ProviderConfig | null {
  switch (name) {
    case 'openai': {
      const apiKey = env.OPENAI_API_KEY;
      if (!apiKey) return null;
      return {
        name: 'openai',
        apiKey,
        baseURL: env.OPENAI_BASE_URL || BUILTIN_BASE_URLS.openai,
        model: env.OPENAI_MODEL || BUILTIN_MODELS.openai,
      };
    }
    case 'nvidia': {
      const apiKey = env.NVIDIA_API_KEY;
      if (!apiKey) return null;
      return {
        name: 'nvidia',
        apiKey,
        baseURL: env.NVIDIA_BASE_URL || BUILTIN_BASE_URLS.nvidia,
        model: env.NVIDIA_MODEL || BUILTIN_MODELS.nvidia,
      };
    }
    case 'fireworks': {
      const apiKey = env.FIREWORKS_API_KEY;
      if (!apiKey) return null;
      return {
        name: 'fireworks',
        apiKey,
        baseURL: env.FIREWORKS_BASE_URL || BUILTIN_BASE_URLS.fireworks,
        model: env.FIREWORKS_MODEL || BUILTIN_MODELS.fireworks,
      };
    }
    case 'github-models': {
      const apiKey = env.GITHUB_MODELS_API_KEY;
      if (!apiKey) return null;
      return {
        name: 'github-models',
        apiKey,
        baseURL: env.GITHUB_MODELS_BASE_URL || BUILTIN_BASE_URLS['github-models'],
        model: env.GITHUB_MODELS_MODEL || BUILTIN_MODELS['github-models'],
      };
    }
    case 'modal': {
      const apiKey = env.MODAL_API_KEY;
      if (!apiKey) return null;
      return {
        name: 'modal',
        apiKey,
        baseURL: env.MODAL_BASE_URL || BUILTIN_BASE_URLS.modal,
        model: env.MODAL_MODEL || BUILTIN_MODELS.modal,
      };
    }
    case 'openmodel': {
      const apiKey = env.OPENMODEL_API_KEY;
      if (!apiKey) return null;
      return {
        name: 'openmodel',
        apiKey,
        baseURL: env.OPENMODEL_BASE_URL || BUILTIN_BASE_URLS.openmodel,
        model: env.OPENMODEL_MODEL || BUILTIN_MODELS.openmodel,
      };
    }
    case 'render': {
      const apiKey = env.RENDER_API_KEY;
      if (!apiKey) return null;
      return {
        name: 'render',
        apiKey,
        baseURL: env.RENDER_BASE_URL || BUILTIN_BASE_URLS.render,
        model: env.RENDER_MODEL || BUILTIN_MODELS.render,
      };
    }
    case 'zenmux': {
      const apiKey = env.ZENMUX_API_KEY;
      if (!apiKey) return null;
      return {
        name: 'zenmux',
        apiKey,
        baseURL: env.ZENMUX_BASE_URL || BUILTIN_BASE_URLS.zenmux,
        model: env.ZENMUX_MODEL || BUILTIN_MODELS.zenmux,
      };
    }
    default:
      return null;
  }
}

function _listConfiguredProviders(env: Env): ProviderConfig[] {
  const out: ProviderConfig[] = [];
  for (const name of BUILTIN_PROVIDERS) {
    const cfg = _getProviderConfig(env, name);
    if (cfg) out.push(cfg);
  }
  return out;
}

export function listConfiguredProviders(env: Env): ProviderConfig[] {
  return _listConfiguredProviders(env);
}

export function hasAnyProviderConfigured(env: Env): boolean {
  return _listConfiguredProviders(env).length > 0;
}

/**
 * Generate a chat completion against a single provider with hard timeout.
 * No retry, no cascade — caller decides what to do next.
 */
export async function generateOnce(
  provider: ProviderConfig,
  system: string,
  messages: ModelMessage[],
  signal?: AbortSignal
): Promise<ChatResult> {
  const start = Date.now();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(new Error('provider-timeout')), CONFIG.PROVIDER_TIMEOUT_MS);

  // Link external signal if provided
  if (signal) {
    if (signal.aborted) controller.abort(signal.reason);
    signal.addEventListener('abort', () => controller.abort(signal.reason), { once: true });
  }

  try {
    const openaiMessages = [
      { role: 'system' as const, content: system },
      ...messages.map((m) => ({
        role: m.role as string,
        content: typeof m.content === 'string' ? m.content : JSON.stringify(m.content),
      })),
    ];

    const res = await fetch(`${provider.baseURL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${provider.apiKey}`,
      },
      body: JSON.stringify({ model: provider.model, messages: openaiMessages, max_tokens: 4096 }),
      signal: controller.signal,
    });

    if (!res.ok) {
      const errText = await res.text().catch(() => '');
      throw new Error(`${res.status} ${res.statusText}: ${errText.slice(0, 200)}`);
    }

    const data = (await res.json()) as Record<string, unknown>;
    const choices = data.choices as Array<{ message?: { content?: string }; finish_reason?: string }> | undefined;
    const text = choices?.[0]?.message?.content || '';
    const finishReason = choices?.[0]?.finish_reason || 'stop';
    const usage = data.usage as { prompt_tokens?: number; completion_tokens?: number } | undefined;

    return {
      text,
      finishReason,
      provider: provider.name,
      model: provider.model,
      latencyMs: Date.now() - start,
      promptTokens: usage?.prompt_tokens,
      completionTokens: usage?.completion_tokens,
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Bounded failover: try up to MAX_PROVIDERS_PER_REQUEST providers,
 * skipping open circuits, with MAX_RETRIES=1 per provider.
 */
export async function generateWithFailover(  // NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
  env: Env,
  system: string,
  messages: ModelMessage[],
  signal?: AbortSignal
): Promise<ChatResult> {
  const candidates = _listConfiguredProviders(env).filter((p) => !isCircuitOpen(p.name));

  if (candidates.length === 0) {
    throw new Error('All configured providers are unavailable (circuits open)');
  }

  // Cap to MAX_PROVIDERS_PER_REQUEST — never cascade beyond 2.
  const queue = candidates.slice(0, CONFIG.MAX_PROVIDERS_PER_REQUEST);
  let lastError: Error | null = null;

  for (const provider of queue) {
    // External abort
    if (signal?.aborted) {
      throw new Error('client-disconnected');
    }

    let attemptErr: Error | null = null;
    for (let attempt = 0; attempt <= CONFIG.MAX_RETRIES; attempt++) {
      try {
        const result = await generateOnce(provider, system, messages, signal);
        recordProviderSuccess(provider.name, env);
        recordLatency(provider.name, result.latencyMs, false);
        return result;
      } catch (e) {
        attemptErr = e instanceof Error ? e : new Error(String(e));
        // AbortController/timeout — no point retrying
        if (signal?.aborted) throw new Error('client-disconnected');
      }
    }

    // Provider exhausted all retries — record and move to next.
    recordProviderFailure(provider.name, env);
    if (attemptErr) {
      recordLatency(provider.name, CONFIG.PROVIDER_TIMEOUT_MS, true);
      lastError = attemptErr;
    }
  }

  throw lastError || new Error('All providers failed');
}
