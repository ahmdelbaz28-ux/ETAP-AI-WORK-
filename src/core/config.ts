/**
 * Centralized configuration constants.
 * Single source of truth for all production-hardened behavior.
 * No magic numbers elsewhere in the codebase.
 */
export const CONFIG = {
  // Body size limit (HTTP 413 above this)
  MAX_BODY_SIZE: 100_000, // 100 KB

  // Provider retry / timeout
  MAX_RETRIES: 1, // Per-provider retry budget
  PROVIDER_TIMEOUT_MS: 8_000, // 8 s hard timeout via AbortController

  // Failover bounds
  MAX_PROVIDERS_PER_REQUEST: 2, // Never cascade beyond 2 providers per request

  // Circuit breaker
  CIRCUIT_BREAKER_FAILURE_THRESHOLD: 3,
  CIRCUIT_BREAKER_COOLDOWN_MS: 60_000,

  // Rate limiting
  RATE_LIMIT_PER_KEY_PER_MINUTE: 60,
  RATE_LIMIT_PER_KEY_PER_AGENT_PER_MINUTE: 30,

  // Idempotency
  IDEMPOTENCY_TTL_MS: 5 * 60 * 1000, // 5 minutes

  // Metrics persistence
  METRICS_SAVE_INTERVAL_MS: 60_000,
  MAX_AUDIT_BUFFER: 200,
  AUDIT_FLUSH_THRESHOLD: 50, // Flush when buffer reaches this size

  // Tasks
  MAX_TASK_STORE_SIZE: 1000,
  TASK_TTL_SECONDS: 24 * 60 * 60,

  // Engineering Service
  ENGINEERING_SERVICE_TIMEOUT_MS: 30_000,
  ENGINEERING_SERVICE_MAX_RETRIES: 2,
} as const;

/**
 * Built-in provider allowlist.
 * Hardening decision: only providers with verified working credentials
 * are included. To re-enable, add a new entry here and set the
 * corresponding wrangler secret.
 *
 * Providers added 2026-07-07: Render, ZenMux, Fireworks, GitHub Models,
 * OpenModel, Modal — all OpenAI-compatible chat/completions endpoints.
 * Each provider has a default base URL and model that can be overridden
 * via env vars (e.g. FIREWORKS_BASE_URL, FIREWORKS_MODEL).
 */
export const BUILTIN_PROVIDERS = [
  'openai',
  'nvidia',
  'fireworks',
  'github-models',
  'modal',
  'openmodel',
  'render',
  'zenmux',
] as const;
export type BuiltinProviderName = (typeof BUILTIN_PROVIDERS)[number];

/**
 * Default base URLs for built-in providers.
 * Only used when the corresponding env secret is not set.
 */
export const BUILTIN_BASE_URLS: Readonly<Record<string, string>> = Object.freeze({
  openai: 'https://api.openai.com/v1',
  nvidia: 'https://integrate.api.nvidia.com/v1',
  fireworks: 'https://api.fireworks.ai/inference/v1',
  'github-models': 'https://models.inference.ai.azure.com/v1',
  modal: 'https://api.us-west-2.modal.direct/v1',
  openmodel: 'https://api.openmodel.ai/v1',
  render: 'https://api.render.com/v1',
  zenmux: 'https://api.zenmux.ai/v1',
});

/**
 * Default model identifiers per provider.
 * Only used when the corresponding env secret is not set.
 */
export const BUILTIN_MODELS: Readonly<Record<string, string>> = Object.freeze({
  openai: 'gpt-4o-mini',
  nvidia: 'meta/llama-3.1-8b-instruct',
  fireworks: 'accounts/fireworks/models/kimi-k2p7-code',
  'github-models': 'gpt-4o',
  modal: 'zai-org/GLM-5.1-FP8',
  openmodel: 'gpt-4o',
  render: 'gpt-4o-mini',
  zenmux: 'gpt-4o-mini',
});

/**
 * API key scopes.
 * - full: every route
 * - chat: only chat + status endpoints
 * - studies: only studies + status
 * - read: only listing / health / metrics
 */
export type ApiKeyScope = 'full' | 'chat' | 'studies' | 'read';
