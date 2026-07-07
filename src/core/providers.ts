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

/** Provider descriptor for config lookup. */
interface ProviderDescriptor {
  envKey: string;
  baseUrlKey: string;
  modelKey: string;
  /** For providers that need extra env vars (e.g. account ID). */
  extraKeys?: string[];
  /** Transform base URL at runtime (e.g. placeholder substitution). */
  transformBaseUrl?: (url: string, env: Env) => string;
}

/** Registry of all built-in providers and how to read their env vars. */
const PROVIDER_REGISTRY: Record<string, ProviderDescriptor> = {
  openai:       { envKey: 'OPENAI_API_KEY',       baseUrlKey: 'OPENAI_BASE_URL',       modelKey: 'OPENAI_MODEL' },
  nvidia:       { envKey: 'NVIDIA_API_KEY',        baseUrlKey: 'NVIDIA_BASE_URL',       modelKey: 'NVIDIA_MODEL' },
  fireworks:    { envKey: 'FIREWORKS_API_KEY',     baseUrlKey: 'FIREWORKS_BASE_URL',    modelKey: 'FIREWORKS_MODEL' },
  'github-models': { envKey: 'GITHUB_MODELS_API_KEY', baseUrlKey: 'GITHUB_MODELS_BASE_URL', modelKey: 'GITHUB_MODELS_MODEL' },
  modal:        { envKey: 'MODAL_API_KEY',         baseUrlKey: 'MODAL_BASE_URL',        modelKey: 'MODAL_MODEL' },
  openmodel:    { envKey: 'OPENMODEL_API_KEY',     baseUrlKey: 'OPENMODEL_BASE_URL',    modelKey: 'OPENMODEL_MODEL' },
  render:       { envKey: 'RENDER_API_KEY',        baseUrlKey: 'RENDER_BASE_URL',       modelKey: 'RENDER_MODEL' },
  zenmux:       { envKey: 'ZENMUX_API_KEY',        baseUrlKey: 'ZENMUX_BASE_URL',       modelKey: 'ZENMUX_MODEL' },
  bynara:       { envKey: 'BYNARA_API_KEY',        baseUrlKey: 'BYNARA_BASE_URL',       modelKey: 'BYNARA_MODEL' },
  cloudflare:   {
    envKey: 'CLOUDFLARE_API_KEY',
    baseUrlKey: 'CLOUDFLARE_BASE_URL',
    modelKey: 'CLOUDFLARE_MODEL',
    extraKeys: ['CLOUDFLARE_ACCOUNT_ID'],
    transformBaseUrl: (url, env) => url.replace('PLACEHOLDER', env.CLOUDFLARE_ACCOUNT_ID || ''),
  },
};

function _getProviderConfig(env: Env, name: string): ProviderConfig | null {
  const desc = PROVIDER_REGISTRY[name];
  if (!desc) return null;

  const e = env as Record<string, string | undefined>;
  const apiKey = e[desc.envKey];
  if (!apiKey) return null;

  // Check any extra required keys
  if (desc.extraKeys) {
    for (const k of desc.extraKeys) {
      if (!e[k]) return null;
    }
  }

  let baseURL = e[desc.baseUrlKey] || BUILTIN_BASE_URLS[name as keyof typeof BUILTIN_BASE_URLS];
  if (desc.transformBaseUrl) {
    baseURL = desc.transformBaseUrl(baseURL!, env);
  }

  return {
    name,
    apiKey,
    baseURL: baseURL!,
    model: e[desc.modelKey] || BUILTIN_MODELS[name as keyof typeof BUILTIN_MODELS],
  };
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
