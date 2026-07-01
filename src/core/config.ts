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
 * are included. Qwen and GLM are intentionally excluded because
 * their API keys are expired/invalid and they cause cascade failures.
 * Kilo and OpenCode are also excluded — see "No single-provider
 * dependency" followup below. To re-enable, add a new entry here and
 * set the corresponding wrangler secret.
 *
 * Clovie Router added 2026-07-01: OpenAI-compatible gateway that exposes
 * the MiMo model family (mimo-v2.5-pro, mimo-v2.5, mimo-v2-omni,
 * mimo-v2-pro, mimo-v2-flash). Compatible with Hermes, OpenClaw, Cline,
 * and Claude Code agent frameworks. Set CLOVIE_API_KEY + CLOVIE_BASE_URL
 * env vars to enable.
 */
export const BUILTIN_PROVIDERS = ['nvidia', 'openai', 'clovie'] as const;
export type BuiltinProviderName = (typeof BUILTIN_PROVIDERS)[number];

/**
 * Default base URLs for built-in providers.
 * Only used when the corresponding env secret is not set.
 */
export const BUILTIN_BASE_URLS: Readonly<Record<string, string>> = Object.freeze({
  nvidia: 'https://integrate.api.nvidia.com/v1',
  openai: 'https://api.openai.com/v1',
  clovie: 'https://clovievalen-clovie-router.hf.space/v1',
});

/**
 * Default model identifiers per provider.
 * Only used when the corresponding env secret is not set.
 */
export const BUILTIN_MODELS: Readonly<Record<string, string>> = Object.freeze({
  nvidia: 'meta/llama-3.1-8b-instruct',
  openai: 'gpt-4o-mini',
  // MiMo v2-flash is the cheapest model — good default for cost-sensitive
  // scenarios. Override with CLOVIE_MODEL env var to switch to a stronger one.
  clovie: 'mimo-v2-flash',
});

/**
 * All MiMo models available via the Clovie Router gateway.
 * Use these when constructing user-facing model pickers.
 */
export const CLOVIE_MIMO_MODELS = [
  'mimo-v2.5-pro',   // Latest flagship — strongest reasoning
  'mimo-v2.5',       // Latest balanced
  'mimo-v2-omni',    // Multimodal (vision + text)
  'mimo-v2-pro',     // Previous-gen pro
  'mimo-v2-flash',   // Fastest, cheapest — default
] as const;

/**
 * API key scopes.
 * - full: every route
 * - chat: only chat + status endpoints
 * - studies: only studies + status
 * - read: only listing / health / metrics
 */
export type ApiKeyScope = 'full' | 'chat' | 'studies' | 'read';
