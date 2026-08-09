/**
 * LLM token-usage tracker — the production-side counterpart to the
 * Python ``integrations/langfuse_llm.py::PROMPT_CACHE_STATS``.
 *
 * WHY THIS EXISTS
 * ---------------
 * Before this module, ``generateOnce`` in ``providers.ts`` read
 * ``usage.prompt_tokens`` and ``usage.completion_tokens`` from the
 * OpenAI-compatible response but **discarded**
 * ``usage.prompt_tokens_details.cached_tokens``. As a result:
 *
 *   - We had zero visibility into whether OpenAI's automatic prompt
 *     caching was actually firing for the long coordinator/specialist
 *     system prompts (5–6 KB each).
 *   - We could not measure the real input-token cost reduction from
 *     prompt caching across multi-agent fan-out calls.
 *   - Operators looking at ``/metrics`` saw ``agentChats`` going up
 *     but had no idea what fraction of those tokens were billed at
 *     the discounted cache rate vs. full price.
 *
 * WHAT THIS MODULE DOES
 * ---------------------
 *   - ``recordTokenUsage({ provider, model, promptTokens, cachedTokens, completionTokens })``
 *     accumulates per-call usage into a thread-safe in-memory tally.
 *   - ``getTokenStats()`` returns an immutable snapshot suitable for
 *     JSON-serializing into the ``/metrics`` response.
 *   - ``resetTokenStats()`` clears the tally — intended for tests.
 *
 * The tracker is in-memory only (Cloudflare Workers don't have a
 * long-lived process, but within a single isolate this gives an
 * accurate picture of the cache-hit ratio for that isolate's
 * lifetime). For cross-isolate observability, hook this into the
 * existing ``METRICS_KV`` persistence layer in a follow-up.
 *
 * THREAD-SAFETY
 * -------------
 * Cloudflare Workers run JavaScript single-threaded per isolate, so
 * no explicit locking is needed. The ``_calls`` array is only
 * mutated from ``recordTokenUsage`` which is synchronous and
 * non-reentrant.
 */

export interface TokenUsageRecord {
  provider: string;
  model: string;
  promptTokens: number;
  cachedTokens: number;
  completionTokens: number;
}

export interface TokenStatsSnapshot {
  callCount: number;
  totalPromptTokens: number;
  totalCachedTokens: number;
  totalCompletionTokens: number;
  /** Prompt tokens that were actually billed (after cache discount). */
  totalBilledPromptTokens: number;
  /** cachedTokens / promptTokens. 0 when no calls have been recorded. */
  cacheHitRatio: number;
  perProvider: Record<string, {
    callCount: number;
    promptTokens: number;
    cachedTokens: number;
    completionTokens: number;
    cacheHitRatio: number;
  }>;
  perModel: Record<string, {
    callCount: number;
    promptTokens: number;
    cachedTokens: number;
    completionTokens: number;
    cacheHitRatio: number;
  }>;
}

const _calls: TokenUsageRecord[] = [];

export function recordTokenUsage(rec: TokenUsageRecord): void {
  // Defensive — never let a malformed record corrupt the tally.
  const safe: TokenUsageRecord = {
    provider: String(rec.provider ?? 'unknown'),
    model: String(rec.model ?? 'unknown'),
    promptTokens: Math.max(0, Number(rec.promptTokens) || 0),
    cachedTokens: Math.max(0, Number(rec.cachedTokens) || 0),
    completionTokens: Math.max(0, Number(rec.completionTokens) || 0),
  };
  // Cap cachedTokens at promptTokens — providers shouldn't return
  // cached > prompt, but if they do (bug, misconfiguration) we don't
  // want a misleading >100% cache-hit ratio.
  if (safe.cachedTokens > safe.promptTokens) {
    safe.cachedTokens = safe.promptTokens;
  }
  _calls.push(safe);
}

export function getTokenStats(): TokenStatsSnapshot {
  let totalPrompt = 0;
  let totalCached = 0;
  let totalCompletion = 0;
  const perProvider: TokenStatsSnapshot['perProvider'] = {};
  const perModel: TokenStatsSnapshot['perModel'] = {};

  for (const c of _calls) {
    totalPrompt += c.promptTokens;
    totalCached += c.cachedTokens;
    totalCompletion += c.completionTokens;

    if (!perProvider[c.provider]) {
      perProvider[c.provider] = {
        callCount: 0, promptTokens: 0, cachedTokens: 0, completionTokens: 0, cacheHitRatio: 0,
      };
    }
    const pp = perProvider[c.provider]!;
    pp.callCount += 1;
    pp.promptTokens += c.promptTokens;
    pp.cachedTokens += c.cachedTokens;
    pp.completionTokens += c.completionTokens;

    if (!perModel[c.model]) {
      perModel[c.model] = {
        callCount: 0, promptTokens: 0, cachedTokens: 0, completionTokens: 0, cacheHitRatio: 0,
      };
    }
    const pm = perModel[c.model]!;
    pm.callCount += 1;
    pm.promptTokens += c.promptTokens;
    pm.cachedTokens += c.cachedTokens;
    pm.completionTokens += c.completionTokens;
  }

  // Compute ratios
  for (const k of Object.keys(perProvider)) {
    const pp = perProvider[k]!;
    pp.cacheHitRatio = pp.promptTokens > 0
      ? Number((pp.cachedTokens / pp.promptTokens).toFixed(4))
      : 0;
  }
  for (const k of Object.keys(perModel)) {
    const pm = perModel[k]!;
    pm.cacheHitRatio = pm.promptTokens > 0
      ? Number((pm.cachedTokens / pm.promptTokens).toFixed(4))
      : 0;
  }

  return {
    callCount: _calls.length,
    totalPromptTokens: totalPrompt,
    totalCachedTokens: totalCached,
    totalCompletionTokens: totalCompletion,
    totalBilledPromptTokens: totalPrompt - totalCached,
    cacheHitRatio: totalPrompt > 0 ? Number((totalCached / totalPrompt).toFixed(4)) : 0,
    perProvider,
    perModel,
  };
}

export function resetTokenStats(): void {
  _calls.length = 0;
}
