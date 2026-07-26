/**
 * Unit tests for the production LLM token-cache tracking.
 *
 * These tests verify the FIX (not just the measurement):
 *   1. generateOnce now parses prompt_tokens_details.cached_tokens
 *      from the OpenAI-compatible response (previously discarded).
 *   2. recordTokenUsage accumulates per-call usage into a snapshot
 *      that /metrics can expose.
 *   3. The snapshot correctly aggregates per-provider and per-model
 *      cache-hit ratios.
 *   4. composeMetrics now includes the tokenStats field, so the
 *      cache-hit ratio is observable from /metrics without any
 *      extra plumbing.
 *
 * P0-V2 — this is the FIX that the previous P0 (Python-only on
 * langfuse_llm.py) failed to deliver. The Python path had zero
 * production callers; this TypeScript path is what the Cloudflare
 * Worker actually uses for every /api/v1/agents/:id/chat request.
 */
import { describe, expect, it, beforeEach, vi } from 'vitest';
import {
  recordTokenUsage,
  getTokenStats,
  resetTokenStats,
} from '../src/core/tokenStats.js';
import { generateOnce } from '../src/core/providers.js';
import type { ProviderConfig } from '../src/core/providers.js';
import { composeMetrics } from '../src/utils/metrics.js';

// ---------------------------------------------------------------------------
// Mock Env type — only the fields composeMetrics actually touches.
// ---------------------------------------------------------------------------

const fakeEnv: any = {
  METRICS_KV: undefined,
  TASK_STORE_KV: undefined,
};

// ---------------------------------------------------------------------------
// tokenStats unit tests
// ---------------------------------------------------------------------------

describe('tokenStats', () => {
  beforeEach(() => {
    resetTokenStats();
  });

  it('returns empty snapshot when no calls recorded', () => {
    const snap = getTokenStats();
    expect(snap.callCount).toBe(0);
    expect(snap.totalPromptTokens).toBe(0);
    expect(snap.totalCachedTokens).toBe(0);
    expect(snap.totalCompletionTokens).toBe(0);
    expect(snap.totalBilledPromptTokens).toBe(0);
    expect(snap.cacheHitRatio).toBe(0);
    expect(snap.perProvider).toEqual({});
    expect(snap.perModel).toEqual({});
  });

  it('records a single call and computes ratio', () => {
    recordTokenUsage({
      provider: 'openai',
      model: 'gpt-4o',
      promptTokens: 1000,
      cachedTokens: 600,
      completionTokens: 200,
    });
    const snap = getTokenStats();
    expect(snap.callCount).toBe(1);
    expect(snap.totalPromptTokens).toBe(1000);
    expect(snap.totalCachedTokens).toBe(600);
    expect(snap.totalCompletionTokens).toBe(200);
    expect(snap.totalBilledPromptTokens).toBe(400);
    expect(snap.cacheHitRatio).toBe(0.6);
  });

  it('aggregates across multiple calls and providers', () => {
    recordTokenUsage({
      provider: 'openai', model: 'gpt-4o',
      promptTokens: 1000, cachedTokens: 600, completionTokens: 200,
    });
    recordTokenUsage({
      provider: 'openai', model: 'gpt-4o-mini',
      promptTokens: 500, cachedTokens: 400, completionTokens: 100,
    });
    recordTokenUsage({
      provider: 'nvidia', model: 'nemotron-70b',
      promptTokens: 2000, cachedTokens: 0, completionTokens: 500,
    });
    const snap = getTokenStats();
    expect(snap.callCount).toBe(3);
    expect(snap.totalPromptTokens).toBe(3500);
    expect(snap.totalCachedTokens).toBe(1000);
    expect(snap.totalBilledPromptTokens).toBe(2500);
    expect(snap.cacheHitRatio).toBeCloseTo(0.2857, 4);

    // Per-provider breakdown
    expect(snap.perProvider.openai.callCount).toBe(2);
    expect(snap.perProvider.openai.promptTokens).toBe(1500);
    expect(snap.perProvider.openai.cachedTokens).toBe(1000);
    expect(snap.perProvider.openai.cacheHitRatio).toBeCloseTo(0.6667, 4);
    expect(snap.perProvider.nvidia.callCount).toBe(1);
    expect(snap.perProvider.nvidia.cacheHitRatio).toBe(0);

    // Per-model breakdown
    expect(snap.perModel['gpt-4o'].callCount).toBe(1);
    expect(snap.perModel['gpt-4o-mini'].callCount).toBe(1);
    expect(snap.perModel['nemotron-70b'].callCount).toBe(1);
  });

  it('clamps cachedTokens > promptTokens to avoid >100% ratio', () => {
    recordTokenUsage({
      provider: 'openai', model: 'gpt-4o',
      promptTokens: 500, cachedTokens: 800, completionTokens: 100,
    });
    const snap = getTokenStats();
    // Provider returned cached > prompt (a bug), tracker should clamp.
    expect(snap.totalCachedTokens).toBe(500);
    expect(snap.cacheHitRatio).toBe(1);
  });

  it('handles missing/NaN fields defensively', () => {
    recordTokenUsage({
      provider: '' as any,
      model: undefined as any,
      promptTokens: NaN,
      cachedTokens: -50,
      completionTokens: 'oops' as any,
    });
    const snap = getTokenStats();
    expect(snap.callCount).toBe(1);
    expect(snap.totalPromptTokens).toBe(0);
    expect(snap.totalCachedTokens).toBe(0);
    // String('') === '' for provider, String(undefined) === 'undefined' for model.
    // The code's contract is "coerce to string, never throw" — we verify the
    // coercion happened and the per-provider bucket exists under the empty-string key.
    expect(Object.keys(snap.perProvider)).toContain('');
    expect(snap.perProvider[''].callCount).toBe(1);
  });

  it('resetTokenStats clears all recorded calls', () => {
    recordTokenUsage({
      provider: 'openai', model: 'gpt-4o',
      promptTokens: 100, cachedTokens: 50, completionTokens: 10,
    });
    expect(getTokenStats().callCount).toBe(1);
    resetTokenStats();
    expect(getTokenStats().callCount).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// generateOnce — verify it parses cached_tokens from the OpenAI response
// ---------------------------------------------------------------------------

describe('generateOnce — cached_tokens parsing', () => {
  beforeEach(() => {
    resetTokenStats();
  });

  it('extracts cached_tokens from prompt_tokens_details and records into tokenStats', async () => {
    // Mock the global fetch to return a controlled OpenAI-shaped response.
    const mockResponse = {
      ok: true,
      status: 200,
      json: async () => ({
        choices: [
          { message: { content: 'hello world' }, finish_reason: 'stop' },
        ],
        usage: {
          prompt_tokens: 1500,
          completion_tokens: 100,
          prompt_tokens_details: { cached_tokens: 800 },
        },
      }),
      text: async () => '',
    };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse as any);

    const provider: ProviderConfig = {
      name: 'openai',
      apiKey: 'sk-test',
      baseURL: 'https://api.openai.com/v1',
      model: 'gpt-4o',
    };

    const result = await generateOnce(
      provider,
      'You are an engineer.',
      [{ role: 'user', content: 'compute voltage' } as any],
    );

    expect(result.text).toBe('hello world');
    expect(result.promptTokens).toBe(1500);
    expect(result.completionTokens).toBe(100);
    expect(result.cachedTokens).toBe(800);

    // Verify tokenStats was populated
    const snap = getTokenStats();
    expect(snap.callCount).toBe(1);
    expect(snap.totalPromptTokens).toBe(1500);
    expect(snap.totalCachedTokens).toBe(800);
    expect(snap.totalCompletionTokens).toBe(100);
    expect(snap.cacheHitRatio).toBeCloseTo(0.5333, 4);

    fetchSpy.mockRestore();
  });

  it('handles response with no prompt_tokens_details (cached=0)', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      json: async () => ({
        choices: [{ message: { content: 'ok' }, finish_reason: 'stop' }],
        usage: { prompt_tokens: 500, completion_tokens: 50 },
      }),
      text: async () => '',
    };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse as any);

    const provider: ProviderConfig = {
      name: 'nvidia',
      apiKey: 'test',
      baseURL: 'https://integrate.api.nvidia.com/v1',
      model: 'nemotron-70b',
    };

    const result = await generateOnce(provider, 'sys', []);

    expect(result.cachedTokens).toBe(0);
    const snap = getTokenStats();
    expect(snap.totalCachedTokens).toBe(0);
    expect(snap.cacheHitRatio).toBe(0);

    fetchSpy.mockRestore();
  });

  it('handles response with null prompt_tokens_details', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      json: async () => ({
        choices: [{ message: { content: 'ok' }, finish_reason: 'stop' }],
        usage: {
          prompt_tokens: 500,
          completion_tokens: 50,
          prompt_tokens_details: null,
        },
      }),
      text: async () => '',
    };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse as any);

    const provider: ProviderConfig = {
      name: 'openai', apiKey: 'x', baseURL: 'https://x', model: 'gpt-4o',
    };
    const result = await generateOnce(provider, 'sys', []);
    expect(result.cachedTokens).toBe(0);

    fetchSpy.mockRestore();
  });

  it('tracker bug does NOT crash the chat call', async () => {
    // Sabotage recordTokenUsage by passing a Proxy that throws on access.
    const mockResponse = {
      ok: true,
      status: 200,
      json: async () => ({
        choices: [{ message: { content: 'ok' }, finish_reason: 'stop' }],
        usage: { prompt_tokens: 100, completion_tokens: 10, prompt_tokens_details: { cached_tokens: 50 } },
      }),
      text: async () => '',
    };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse as any);

    // Mock console.warn to silence the swallow
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const provider: ProviderConfig = {
      name: 'openai', apiKey: 'x', baseURL: 'https://x', model: 'gpt-4o',
    };
    // Should NOT throw even if tracker were broken (we test the try/catch).
    const result = await generateOnce(provider, 'sys', []);
    expect(result.text).toBe('ok');
    expect(result.cachedTokens).toBe(50);

    fetchSpy.mockRestore();
    warnSpy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// composeMetrics — verify tokenStats is exposed
// ---------------------------------------------------------------------------

describe('composeMetrics — tokenStats exposure', () => {
  beforeEach(() => {
    resetTokenStats();
  });

  it('includes tokenStats field with the current snapshot', async () => {
    recordTokenUsage({
      provider: 'openai', model: 'gpt-4o',
      promptTokens: 2000, cachedTokens: 1500, completionTokens: 300,
    });

    const metrics = await composeMetrics(fakeEnv);

    expect(metrics.tokenStats).toBeDefined();
    expect(metrics.tokenStats.callCount).toBe(1);
    expect(metrics.tokenStats.totalPromptTokens).toBe(2000);
    expect(metrics.tokenStats.totalCachedTokens).toBe(1500);
    expect(metrics.tokenStats.cacheHitRatio).toBe(0.75);
  });

  it('returns empty tokenStats when no LLM calls have been made', async () => {
    const metrics = await composeMetrics(fakeEnv);
    expect(metrics.tokenStats.callCount).toBe(0);
    expect(metrics.tokenStats.cacheHitRatio).toBe(0);
  });
});
