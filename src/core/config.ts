/**
 * Centralized configuration constants.
 * Single source of truth for all production-hardened behavior.
 * No magic numbers elsewhere in the codebase.
 *
 * Security hardening applied per Better Auth Security Best Practices skill:
 *   - Trusted origins whitelist (CORS never reflects arbitrary origins)
 *   - Per-IP rate limiting for unauthenticated requests (brute-force defense)
 *   - Per-endpoint rate limit rules for sensitive routes
 *   - API key minimum length and expiration
 *   - CSRF protection method list
 *   - IP header chain validation
 *   - Dedicated audit KV namespace separation
 *   - HMAC audit log integrity
 *   - Security-critical event categorization
 *   - Cache-Control on all API responses
 */
export const CONFIG = {
  // Body size limit (HTTP 413 above this)
  MAX_BODY_SIZE: 100_000, // 100 KB

  // Provider retry / timeout
  MAX_RETRIES: 1,
  PROVIDER_TIMEOUT_MS: 8_000,

  // Failover bounds
  MAX_PROVIDERS_PER_REQUEST: 2,

  MAX_RETRIES: 1, // Per-provider retry budget
  PROVIDER_TIMEOUT_MS: 8_000, // 8 s hard timeout via AbortController

  // Failover bounds
  MAX_PROVIDERS_PER_REQUEST: 2, // Never cascade beyond 2 providers per request

  // Circuit breaker
  CIRCUIT_BREAKER_FAILURE_THRESHOLD: 3,
  CIRCUIT_BREAKER_COOLDOWN_MS: 60_000,

  // Rate limiting — per API key
  RATE_LIMIT_PER_KEY_PER_MINUTE: 60,
  RATE_LIMIT_PER_KEY_PER_AGENT_PER_MINUTE: 30,

  // Rate limiting — per IP (brute-force defense for auth endpoint)
  IP_RATE_LIMIT_PER_MINUTE: 10,
  IP_RATE_LIMIT_WINDOW_SECONDS: 60,
  IP_RATE_LIMIT_BAN_DURATION_SECONDS: 900,
  IP_RATE_LIMIT_BAN_THRESHOLD: 20,

  // Per-endpoint rate limits (most sensitive routes get tighter limits)
  ENDPOINT_RATE_LIMITS: {
    'POST:/api/v1/studies/run': { window: 60, max: 10 },
    'GET:/api/v1/audit/logs': { window: 60, max: 30 },
  } as Record<string, { window: number; max: number }>,

  // API Key security
  API_KEY_MIN_LENGTH: 32,
  API_KEY_MAX_AGE_DAYS: 90,
  API_KEY_EXPIRY_WARNING_DAYS: 14,

  // Trusted origins — CORS whitelist.
  // Configure via TRUSTED_ORIGINS env var (comma-separated).
  // NEVER use '*' in production.
  DEFAULT_TRUSTED_ORIGINS: [
    'https://etap-ai-work.vercel.app',
    'https://ahmdelbaz28-ahmedetap-platform.hf.space',
  ] as readonly string[],

  // CSRF protection — methods that require origin validation
  CSRF_REQUIRED_METHODS: ['POST', 'PUT', 'PATCH', 'DELETE'] as readonly string[],

  // IP security
  MAX_IP_HEADER_CHAIN: 2,

  // Idempotency
  IDEMPOTENCY_TTL_MS: 5 * 60 * 1000, // 5 minutes

  // Metrics persistence
  METRICS_SAVE_INTERVAL_MS: 60_000,
  MAX_AUDIT_BUFFER: 500,
  AUDIT_FLUSH_THRESHOLD: 50,
  AUDIT_INTEGRITY_ENABLED: true,
  AUDIT_RETENTION_DAYS: 90,

  // Tasks
  MAX_TASK_STORE_SIZE: 1000,
  TASK_TTL_SECONDS: 24 * 60 * 60,

  // Engineering Service
  ENGINEERING_SERVICE_TIMEOUT_MS: 30_000,
  ENGINEERING_SERVICE_MAX_RETRIES: 2,

  // Security-critical actions that trigger elevated audit
  SECURITY_CRITICAL_ACTIONS: [
    'AUTH_FAILURE',
    'RATE_LIMITED',
    'SCOPE_DENIED',
    'CSRF_REJECTED',
    'ORIGIN_REJECTED',
    'IP_BANNED',
    'API_KEY_EXPIRED',
    'API_KEY_REVOKED',
  ] as readonly string[],
} as const;

export const BUILTIN_PROVIDERS = [
  'openai', 'nvidia', 'fireworks', 'github-models',
  'modal', 'openmodel', 'render', 'zenmux', 'bynara', 'cloudflare',
] as const;
export type BuiltinProviderName = (typeof BUILTIN_PROVIDERS)[number];

export const BUILTIN_BASE_URLS: Readonly<Record<string, string>> = Object.freeze({
  openai: 'https://api.openai.com/v1',
  nvidia: 'https://integrate.api.nvidia.com/v1',
  fireworks: 'https://api.fireworks.ai/inference/v1',
  'github-models': 'https://models.inference.ai.azure.com/v1',
  modal: 'https://api.us-west-2.modal.direct/v1',
  openmodel: 'https://api.openmodel.ai/v1',
  render: 'https://api.render.com/v1',
  zenmux: 'https://api.zenmux.ai/v1',
  bynara: 'https://router.bynara.id/v1',
  cloudflare: 'https://api.cloudflare.com/client/v4/accounts/PLACEHOLDER/ai/v1',
});

export const BUILTIN_MODELS: Readonly<Record<string, string>> = Object.freeze({
  openai: 'gpt-4o-mini',
  nvidia: 'meta/llama-3.1-8b-instruct',
  fireworks: 'accounts/fireworks/models/kimi-k2p7-code',
  'github-models': 'gpt-4o',
  modal: 'zai-org/GLM-5.1-FP8',
  openmodel: 'gpt-4o',
  render: 'gpt-4o-mini',
  zenmux: 'gpt-4o-mini',
  bynara: 'mimo-v2.5',
  cloudflare: '@cf/moonshotai/kimi-k2.6',
});


} as const;

/**
 * Built-in provider allowlist.
 * Hardening decision: only providers with verified working credentials
 * are included. Qwen and GLM are intentionally excluded because
 * their API keys are expired/invalid and they cause cascade failures.
 * Kilo and OpenCode are also excluded — see "No single-provider
 * dependency" followup below. To re-enable, add a new entry here and
 * set the corresponding wrangler secret.
 */
export const BUILTIN_PROVIDERS = ['nvidia', 'openai'] as const;
export type BuiltinProviderName = (typeof BUILTIN_PROVIDERS)[number];

/**
 * Default base URLs for built-in providers.
 * Only used when the corresponding env secret is not set.
 */
export const BUILTIN_BASE_URLS: Readonly<Record<string, string>> = Object.freeze({
  nvidia: 'https://integrate.api.nvidia.com/v1',
  openai: 'https://api.openai.com/v1',
});

/**
 * Default model identifiers per provider.
 * Only used when the corresponding env secret is not set.
 */
export const BUILTIN_MODELS: Readonly<Record<string, string>> = Object.freeze({
  nvidia: 'meta/llama-3.1-8b-instruct',
  openai: 'gpt-4o-mini',
});

/**
 * API key scopes.
 * - full: every route
 * - chat: only chat + status endpoints
 * - studies: only studies + status
 * - read: only listing / health / metrics
 */
export type ApiKeyScope = 'full' | 'chat' | 'studies' | 'read';
