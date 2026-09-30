/**
 * Active model configuration and provider status for Mastra agents.
 *
 * Exports:
 *   - getActiveModelConfig(): LanguageModel for the active provider
 *   - getProviderStatus(): list of configured providers with their settings
 *   - testProviderById(id): test a specific provider's connectivity
 *   - ProviderConfig: the provider config type
 *
 * The same OpenAI-compatible client is used for both model resolution
 * and provider status / testing. If OPENAI_API_KEY is not set, the
 * provider is still listed but its test will fail with a clear error.
 */
import { createOpenAI } from '@ai-sdk/openai';
import type { LanguageModel } from 'ai';

// ---------------------------------------------------------------------------
// M4.5 — Single provider policy point (shared with Python and src/core)
// ---------------------------------------------------------------------------
// config/llm-provider-policy.json is THE provider/model policy document.
// This Mastra runtime only consumes providers whose policy `surfaces` include
// "mastra", so adding/removing a provider there changes this module too.
import rawPolicy from '../../../config/llm-provider-policy.json';

interface PolicyProvider {
  id: string;
  enabled: boolean;
  surfaces: string[];
  default_model: string;
  base_url: string;
  env: { api_key: string; base_url: string; model: string };
}

const POLICY = rawPolicy as unknown as { providers: PolicyProvider[] };

/** Enabled providers declared for the "mastra" surface (policy-derived). */
export function getPolicyProviders(): PolicyProvider[] {
  return (POLICY.providers ?? []).filter(
    (p) => p.enabled === true && Array.isArray(p.surfaces) && p.surfaces.includes('mastra'),
  );
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ProviderConfig {
  name: string;
  apiKey: string;
  baseURL: string;
  model: string;
}

export interface ProviderTestResult {
  success: boolean;
  error?: string;
  latencyMs?: number;
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const OPENAI_API_KEY = process.env.OPENAI_API_KEY ?? '';
const OPENAI_BASE_URL = process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1';
const ACTIVE_MODEL_ID = process.env.OPENAI_MODEL_ID || process.env.OPENAI_MODEL || 'gpt-4o';

// Single shared OpenAI client. createOpenAI() does NOT throw if the API
// key is missing — it only fails when an actual API call is made. This
// lets `mastra build` succeed in CI without secrets.
const openai = createOpenAI({
  apiKey: OPENAI_API_KEY,
  baseURL: OPENAI_BASE_URL,
});

// ---------------------------------------------------------------------------
// Model resolution
// ---------------------------------------------------------------------------

/**
 * Returns the active model for Mastra agents.
 *
 * Safe to call at module-load time (no API key validation happens until
 * an agent is actually invoked).
 */
export function getActiveModelConfig(): LanguageModel {
  // Type assertion: @ai-sdk/openai returns LanguageModelV1 which is structurally
  // compatible with Mastra's expected MastraLanguageModelV2 at runtime.
  // The mismatch is purely a TypeScript types-version drift between
  // @ai-sdk/openai (still on V1) and @mastra/core (expects V2/V3).
  return openai(ACTIVE_MODEL_ID) as unknown as LanguageModel;
}

// ---------------------------------------------------------------------------
// Provider status & testing
// ---------------------------------------------------------------------------

/**
 * Returns the list of configured providers with their non-secret details.
 *
 * M4.5: derived from config/llm-provider-policy.json (surface = "mastra") —
 * previously a hard-coded openai-only list, now policy-driven.
 */
export function getProviderStatus(): ProviderConfig[] {
  const providers: ProviderConfig[] = [];
  for (const p of getPolicyProviders()) {
    const apiKey = process.env[p.env.api_key];
    if (!apiKey) continue;
    providers.push({
      name: p.id,
      apiKey,
      baseURL: process.env[p.env.base_url] || p.base_url,
      model: process.env[p.env.model] || p.default_model,
    });
  }
  return providers;
}

/**
 * Tests connectivity to a specific provider by ID.
 * Returns { success: true } on success, { success: false, error } on failure.
 *
 * The test is a no-op network call against the provider's /models
 * endpoint (OpenAI-compatible). If the API key is missing or invalid,
 * the test fails with a clear error message.
 */
export async function testProviderById(id: string): Promise<ProviderTestResult> {
  const providers = getProviderStatus();
  const provider = providers.find((p) => p.name === id);
  if (!provider) {
    return {
      success: false,
      error: `Unknown provider: ${id}. Configured providers: ${
        providers.map((p) => p.name).join(', ') || '(none)'
      }`,
    };
  }

  const t0 = Date.now();
  try {
    const resp = await fetch(`${provider.baseURL}/models`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${provider.apiKey}`,
        'Content-Type': 'application/json',
      },
      // Hard 8s timeout to avoid hanging CI jobs.
      signal: AbortSignal.timeout(8_000),
    });
    if (!resp.ok) {
      const body = await resp.text().catch(() => '');
      // SonarCloud typescript:S4624: extracted nested template literal
      const bodySnippet = body ? `: ${body.slice(0, 200)}` : '';
      return {
        success: false,
        error: `HTTP ${resp.status} ${resp.statusText}${bodySnippet}`,
        latencyMs: Date.now() - t0,
      };
    }
    return {
      success: true,
      latencyMs: Date.now() - t0,
    };
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return {
      success: false,
      error: msg,
      latencyMs: Date.now() - t0,
    };
  }
}
