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
import type { ModelMessage } from 'ai';
import type { Env } from './types.js';
import { CONFIG, BUILTIN_PROVIDERS } from './config.js';
import { isCircuitOpen, recordProviderFailure, recordProviderSuccess } from './circuitBreaker.js';
import { recordTokenUsage } from './tokenStats.js';

// ---------------------------------------------------------------------------
// M4.5 — Single provider policy point (shared with Python)
// ---------------------------------------------------------------------------
//
// config/llm-provider-policy.json is THE provider/model policy document.
// Python (api/chat_stream.py, integrations/model_router.py) and TypeScript
// (this file, src/mastra/lib/model-config.ts) all derive from it, so changing
// the document once changes every consumer.
import rawPolicy from '../../config/llm-provider-policy.json';

/** One provider declaration inside the policy document. */
export interface ProviderPolicyEntry {
  id: string;
  enabled: boolean;
  surfaces: string[];
  default_model: string;
  base_url: string;
  env: { api_key: string; base_url: string; model: string };
  extra_env?: string[];
  base_url_transform?: string;
}

/** Shape of config/llm-provider-policy.json (M4.5). */
export interface ProviderPolicy {
  version: number;
  policy_id: string;
  surfaces: string[];
  providers: ProviderPolicyEntry[];
  model_tiers: Record<string, string[]>;
  cascade: {
    enabled: boolean;
    default_tier: string;
    escalation: Record<string, string | null>;
  };
}

/** The loaded policy document. */
export const PROVIDER_POLICY = rawPolicy as unknown as ProviderPolicy;

/** Surface this runtime serves. */
export const EDGE_GATEWAY_SURFACE = 'edge_gateway';

/** Enabled providers declared for ``surface`` in the policy. */
export function policyProvidersFor(
  surface: string,
  policy: ProviderPolicy = PROVIDER_POLICY,
): ProviderPolicyEntry[] {
  return (policy.providers ?? []).filter(
    (p) => p.enabled === true && Array.isArray(p.surfaces) && p.surfaces.includes(surface),
  );
}

/** Allow-list this gateway actually iterates (policy-derived, not hard-coded). */
export const POLICY_PROVIDERS: readonly string[] = Object.freeze(
  policyProvidersFor(EDGE_GATEWAY_SURFACE).map((p) => p.id),
);

/**
 * Fail-closed startup check: ``src/core/config.ts`` must not drift from the
 * policy document. Throws at module load if the two disagree, so a provider
 * can never be added to one and forgotten in the other.
 */
export function assertPolicyConsistency(policy: ProviderPolicy = PROVIDER_POLICY): void {
  const fromPolicy = policyProvidersFor(EDGE_GATEWAY_SURFACE, policy).map((p) => p.id);
  const fromConfig = BUILTIN_PROVIDERS as readonly string[];
  const onlyInPolicy = fromPolicy.filter((id) => !fromConfig.includes(id));
  const onlyInConfig = fromConfig.filter((id) => !fromPolicy.includes(id));
  if (onlyInPolicy.length || onlyInConfig.length) {
    throw new Error(
      `[M4.5] provider policy drift between config/llm-provider-policy.json and ` +
        `src/core/config.ts — only in policy: [${onlyInPolicy.join(', ')}], ` +
        `only in config.ts: [${onlyInConfig.join(', ')}]. ` +
        `config/llm-provider-policy.json is the single decision point.`,
    );
  }
}

assertPolicyConsistency();

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
  /**
   * Portion of prompt_tokens served from the provider's prompt cache.
   * OpenAI auto-caches prefixes >= 1024 tokens on gpt-4o* models and
   * reports it via ``usage.prompt_tokens_details.cached_tokens``.
   * Tracking this is what makes the cache-hit ratio observable.
   */
  cachedTokens?: number;
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

export function getProviderLatency(): Record<
  string,
  { avgMs: number; failureRate: number; count: number }
> {
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

/** Registry of all built-in providers, DERIVED from the policy document. */
function _descriptorFor(p: ProviderPolicyEntry): ProviderDescriptor {
  const desc: ProviderDescriptor = {
    envKey: p.env.api_key,
    baseUrlKey: p.env.base_url,
    modelKey: p.env.model,
  };
  if (p.extra_env && p.extra_env.length > 0) desc.extraKeys = p.extra_env;
  if (p.base_url_transform === 'placeholder_substitute') {
    desc.transformBaseUrl = (url, env) => url.replace('PLACEHOLDER', env.CLOUDFLARE_ACCOUNT_ID || '');
  }
  return desc;
}

function _policyEntries(surface: string, policy: ProviderPolicy = PROVIDER_POLICY): ProviderPolicyEntry[] {
  return policyProvidersFor(surface, policy);
}

function _getProviderConfig(env: Env, name: string, policy: ProviderPolicy = PROVIDER_POLICY): ProviderConfig | null {
  const entry = _policyEntries(EDGE_GATEWAY_SURFACE, policy).find((p) => p.id === name);
  if (!entry) return null;
  const desc = _descriptorFor(entry);

  const e = env as Record<string, string | undefined>;
  const apiKey = e[desc.envKey];
  if (!apiKey) return null;

  // Check any extra required keys
  if (desc.extraKeys) {
    for (const k of desc.extraKeys) {
      if (!e[k]) return null;
    }
  }

  let baseURL = e[desc.baseUrlKey] || entry.base_url;
  if (desc.transformBaseUrl) {
    baseURL = desc.transformBaseUrl(baseURL!, env);
  }

  return {
    name,
    apiKey,
    baseURL: baseURL!,
    model: e[desc.modelKey] || entry.default_model,
  };
}

function _listConfiguredProviders(env: Env, policy: ProviderPolicy = PROVIDER_POLICY): ProviderConfig[] {
  const out: ProviderConfig[] = [];
  // M4.5: iterate the policy-derived allow-list, not a duplicated constant.
  for (const entry of _policyEntries(EDGE_GATEWAY_SURFACE, policy)) {
    const cfg = _getProviderConfig(env, entry.id, policy);
    if (cfg) out.push(cfg);
  }
  return out;
}

/**
 * List configured providers.
 *
 * M4.5: accepts an optional policy document so a test (or a deployment) can
 * prove that changing the single policy point changes this consumer's
 * behaviour. The default is the shared ``config/llm-provider-policy.json``.
 * Startup validation against ``src/core/config.ts`` happens once at module
 * load (``assertPolicyConsistency()``), not per call.
 */
export function listConfiguredProviders(env: Env, policy?: ProviderPolicy): ProviderConfig[] {
  return _listConfiguredProviders(env, policy ?? PROVIDER_POLICY);
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
  signal?: AbortSignal,
): Promise<ChatResult> {
  const start = Date.now();
  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(new Error('provider-timeout')),
    CONFIG.PROVIDER_TIMEOUT_MS,
  );

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
    const choices = data.choices as
      | Array<{ message?: { content?: string }; finish_reason?: string }>
      | undefined;
    const text = choices?.[0]?.message?.content || '';
    const finishReason = choices?.[0]?.finish_reason || 'stop';
    const usage = data.usage as {
      prompt_tokens?: number;
      completion_tokens?: number;
      prompt_tokens_details?: { cached_tokens?: number } | undefined;
    } | undefined;

    const cachedTokens = usage?.prompt_tokens_details?.cached_tokens ?? 0;

    // Record into the global token-stats tracker so /metrics can expose
    // the production cache-hit ratio. Fail-safe: never let a tracker
    // bug crash the actual chat call.
    try {
      recordTokenUsage({
        provider: provider.name,
        model: provider.model,
        promptTokens: usage?.prompt_tokens ?? 0,
        cachedTokens,
        completionTokens: usage?.completion_tokens ?? 0,
      });
    } catch {
      // swallow — tracker is best-effort
    }

    return {
      text,
      finishReason,
      provider: provider.name,
      model: provider.model,
      latencyMs: Date.now() - start,
      promptTokens: usage?.prompt_tokens,
      completionTokens: usage?.completion_tokens,
      cachedTokens,
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Bounded failover: try up to MAX_PROVIDERS_PER_REQUEST providers,
 * skipping open circuits, with MAX_RETRIES=1 per provider.
 */
export async function generateWithFailover(
  // NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
  env: Env,
  system: string,
  messages: ModelMessage[],
  signal?: AbortSignal,
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
